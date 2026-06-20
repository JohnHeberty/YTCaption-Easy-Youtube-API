from pathlib import Path
from typing import Optional

import torch

from common.log_utils import get_logger

from app.core.constants import (
    STAGE_MODEL_LOADING,
    STAGE_TEXT_CHUNKING,
    STAGE_AUDIO_GENERATION,
    STAGE_AUDIO_ASSEMBLY,
)
from app.domain.models import AudioGenerationJob
from app.domain.interfaces import IModelManager, IJobStore, ITTSGenerator
from app.domain.exceptions import AudioGenerationException, TextValidationError
from app.services.audio_utils import chunk_text, assemble_audio

logger = get_logger(__name__)


class TTSGenerator(ITTSGenerator):
    def __init__(
        self,
        model_manager: IModelManager,
        job_store: IJobStore,
        output_dir: str,
        max_text_length: int = 5000,
        chunk_size: int = 1000,
        silence_between_paras_ms: int = 0,
    ):
        self._model = model_manager
        self._store = job_store
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._max_text_length = max_text_length
        self._chunk_size = chunk_size
        self._silence_ms = silence_between_paras_ms

    def generate(
        self, job: AudioGenerationJob, audio_prompt_path: Optional[str] = None
    ) -> AudioGenerationJob:
        text = job.input_text.strip()

        try:
            self._validate_text(text)
            self._execute_stage(job, STAGE_MODEL_LOADING, lambda: self._model.load_model())

            chunks = chunk_text(text, self._chunk_size)
            self._execute_stage(job, STAGE_TEXT_CHUNKING)

            job.mark_as_processing()
            wave_arrays = self._generate_chunks(job, chunks, audio_prompt_path)

            self._execute_stage(job, STAGE_AUDIO_GENERATION)

            sr = self._model.sample_rate
            audio_bytes = assemble_audio(wave_arrays, sr, self._silence_ms)

            output_path = self._output_dir / f"{job.id}.wav"
            with open(output_path, "wb") as f:
                f.write(audio_bytes)

            self._finalize_job(job, output_path, len(chunks))

        except Exception as e:
            logger.error(f"Job {job.id} failed: {e}")
            job.mark_as_failed(str(e), type(e).__name__)
            self._store.update_job(job)

        return job

    def _execute_stage(
        self, job: AudioGenerationJob, stage_name: str, action=None
    ) -> None:
        stage = job.stages.get(stage_name)
        if stage:
            stage.start()
        if action:
            action()
        if stage:
            stage.complete()
        self._store.update_job(job)

    def _generate_chunks(
        self,
        job: AudioGenerationJob,
        chunks: list[str],
        audio_prompt_path: Optional[str],
    ) -> list:
        stage = job.stages.get(STAGE_AUDIO_GENERATION)
        if stage:
            stage.start()

        wave_arrays = []
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            wav = self._model.generate(
                chunk,
                audio_prompt_path=audio_prompt_path,
                exaggeration=job.exaggeration,
                temperature=job.temperature,
                cfg_weight=job.cfg_weight,
            )
            wave_arrays.append(wav)
            progress = min(90.0, ((i + 1) / total) * 90.0)
            job.update_progress(progress, f"Generated chunk {i + 1}/{total}")
            self._store.update_job(job)

        if stage:
            stage.complete()
        self._store.update_job(job)
        return wave_arrays

    def _cleanup_gpu_cache(self) -> None:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _get_audio_metadata(self, output_path: Path) -> float:
        import soundfile as sf

        info = sf.info(str(output_path))
        return info.duration

    def _finalize_job(
        self, job: AudioGenerationJob, output_path: Path, total_chunks: int
    ) -> None:
        stage = job.stages.get(STAGE_AUDIO_ASSEMBLY)
        if stage:
            stage.start()

        self._cleanup_gpu_cache()
        duration = self._get_audio_metadata(output_path)

        job.output_duration_seconds = duration
        job.output_file = str(output_path)

        if stage:
            stage.complete()
        job.mark_as_completed(
            f"Generated {total_chunks} chunk(s), {duration:.1f}s"
        )
        self._store.update_job(job)
        logger.info(f"Job {job.id} completed: {output_path}")

    def _validate_text(self, text: str) -> None:
        if not text or not text.strip():
            raise TextValidationError("Text cannot be empty")
        if len(text) > self._max_text_length:
            raise TextValidationError(
                f"Text too long: {len(text)} chars (max {self._max_text_length})"
            )
