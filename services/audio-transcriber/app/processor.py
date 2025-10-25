
import logging
from pathlib import Path
from .models import Job, JobStatus

logger = logging.getLogger(__name__)

class TranscriptionProcessor:
    """Processador de transcrição usando Whisper base"""
    def __init__(self, output_dir: str = "./transcriptions", model_dir: str = "./models"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        self.job_store = None
        self._model = None

    def get_whisper_model(self):
        """Lazy load do Whisper base, salva modelo em ./models"""
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                logging.error("Erro ao importar 'faster_whisper': %s", e)
                raise
            self._model = WhisperModel(
                "base",
                device="cpu",
                compute_type="default"
            )
            logger.info("✅ Whisper modelo 'base' carregado em ./models")
        return self._model
    def _update_progress(self, job: Job, progress: float, message: str = ""):
        job.progress = min(progress, 99.9)
        if self.job_store:
            self.job_store.update_job(job)
        logger.info("Job %s: %.1f%% - %s", job.id, progress, message)

    def transcribe_audio(self, job: Job) -> Job:
        from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
        import threading, os
        job.status = JobStatus.PROCESSING
        self._update_progress(job, 5.0, "Iniciando transcrição")
        input_path = Path(job.input_file)
        if not input_path.exists():
            job.status = JobStatus.FAILED
            job.error_message = f"Arquivo não encontrado: {job.input_file}"
            return job
        self._update_progress(job, 10.0, "Carregando modelo Whisper base")
        model = self.get_whisper_model()
        self._update_progress(job, 20.0, "Transcrevendo áudio (pode demorar)")
        language = None if getattr(job, "language", None) in [None, "auto"] else job.language
        beam_size = int(os.getenv("BEAM_SIZE", "5"))
        try:
            segments, info = model.transcribe(
                str(input_path),
                language=language,
                task="transcribe",
                beam_size=beam_size,
                vad_filter=True
            )
        except Exception as e:
            logger.error("Erro na transcrição: %s", e)
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            try:
                if input_path.exists():
                    input_path.unlink()
            except OSError as cleanup_error:
                logger.warning("Erro ao remover arquivo após falha: %s", cleanup_error)
            return job
        self._update_progress(job, 60.0, "Processando segmentos")
        segments_list = list(segments)
        job.detected_language = info.language
        job.segments_count = len(segments_list)
        job.audio_duration = info.duration
        self._update_progress(job, 80.0, f"Gerando arquivo {getattr(job, 'format', 'srt').upper()}")
        output_filename = f"{job.id}.{getattr(job, 'format', 'srt')}"
        output_path = self.output_dir / output_filename
        fmt = getattr(job, "format", "srt")
        if fmt == "srt":
            self._generate_srt(segments_list, output_path)
        elif fmt == "vtt":
            self._generate_vtt(segments_list, output_path)
        else:
            self._generate_txt(segments_list, output_path)
        full_text = " ".join(seg.text.strip() for seg in segments_list)
        job.transcription_text = full_text
        job.output_file = str(output_path)
        job.status = JobStatus.COMPLETED
        job.completed_at = __import__("datetime").datetime.now()
        job.progress = 100.0
        self._update_progress(job, 100.0, "Transcrição concluída")
        # Remove arquivo de input
        try:
            if input_path.exists():
                input_path.unlink()
                logger.info("Arquivo de entrada removido: %s", input_path)
        except OSError as e:
            logger.warning("Erro ao remover arquivo de entrada: %s", e)
        return job
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(segments, start=1):
                f.write(f"{i}\n")
                start = self._format_timestamp_srt(segment.start)
                end = self._format_timestamp_srt(segment.end)
                f.write(f"{start} --> {end}\n")
                f.write(f"{segment.text.strip()}\n\n")

    def _generate_vtt(self, segments, output_path: Path):
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("WEBVTT\n\n")
            for segment in segments:
                start = self._format_timestamp_vtt(segment.start)
                end = self._format_timestamp_vtt(segment.end)
                f.write(f"{start} --> {end}\n")
                f.write(f"{segment.text.strip()}\n\n")

    def _generate_txt(self, segments, output_path: Path):
        with open(output_path, 'w', encoding='utf-8') as f:
            for segment in segments:
                f.write(f"{segment.text.strip()}\n")

    def _format_timestamp_srt(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _format_timestamp_vtt(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
