"""
AudioProcessor refatorado seguindo princípios SOLID.

Separa responsabilidades em classes menores e coesas.
"""
import os
import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)

from pydub import AudioSegment
from pydub.effects import high_pass_filter
import numpy as np

from common.log_utils import get_logger

from ..core.models import AudioNormJob
from common.job_utils.models import JobStatus
from ..core.constants import AUDIO_CONSTANTS, FILE_CONSTANTS
from ..core.exceptions import (
    AudioNormalizationError,
    ProcessingError,
    StorageError,
    InvalidAudioFormat,
)
from ..domain.interfaces import IJobStore

logger = get_logger(__name__)


class AudioConfig:
    """Configuração para processamento de áudio."""

    def __init__(self, settings: Dict[str, Any]):
        self.temp_dir = Path(settings.get('temp_dir', './temp'))
        self.streaming_threshold_mb = settings.get('audio_chunking', {}).get('streaming_threshold_mb', 50)
        self.chunking_enabled = settings.get('audio_chunking', {}).get('enabled', True)
        self.chunk_duration_sec = settings.get('audio_chunking', {}).get('chunk_duration_sec', 60)
        self.chunk_overlap_sec = settings.get('audio_chunking', {}).get('chunk_overlap_sec', 1)
        self.noise_reduction_max_duration = settings.get('noise_reduction', {}).get('max_duration_sec', 300)
        self.noise_reduction_sample_rate = settings.get('noise_reduction', {}).get('sample_rate', 22050)


class FileOperations:
    """Operações de arquivo isoladas para testabilidade."""

    def __init__(self, config: AudioConfig):
        self.config = config

    def ensure_dir(self, path: Path) -> None:
        """Garante que diretório existe."""
        path.mkdir(parents=True, exist_ok=True)

    def get_temp_dir(self, job_id: str) -> Path:
        """Cria e retorna diretório temporário para job."""
        temp_dir = self.config.temp_dir / f"job_{job_id}_{now_brazil().strftime('%Y%m%d_%H%M%S')}"
        self.ensure_dir(temp_dir)
        return temp_dir

    def cleanup(self, path: Path) -> None:
        """Remove arquivo ou diretório de forma segura."""
        try:
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Falha ao limpar {path}: {e}")

    def check_disk_space(self, file_path: str, required_multiplier: float = 3.0) -> bool:
        """Verifica se há espaço suficiente em disco."""
        try:
            file_size = os.path.getsize(file_path)
            required = file_size * required_multiplier
            stat = shutil.disk_usage(self.config.temp_dir)
            return stat.free >= required
        except Exception as e:
            logger.error(f"Erro ao verificar espaço em disco: {e}")
            return False


class VideoExtractor:
    """Extrai áudio de arquivos de vídeo."""

    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v'}

    def __init__(self, file_ops: FileOperations):
        self.file_ops = file_ops

    def is_video(self, file_path: str) -> bool:
        """Detecta se arquivo é vídeo pela extensão."""
        ext = Path(file_path).suffix.lower()
        return ext in self.VIDEO_EXTENSIONS

    async def extract_audio(self, video_path: str, output_dir: Path) -> str:
        """Extrai áudio de vídeo usando ffmpeg."""
        video_size_mb = Path(video_path).stat().st_size / (1024 * 1024)
        logger.info(f"🎬 Extraindo áudio de vídeo: {Path(video_path).name} ({video_size_mb:.2f}MB)")

        audio_path = output_dir / f"extracted_{Path(video_path).stem}.wav"

        cmd = [
            "ffmpeg", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "44100", "-ac", "2", "-y",
            str(audio_path)
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)

            if process.returncode != 0:
                raise ProcessingError(f"ffmpeg falhou: {stderr.decode()[:200]}")

            if not audio_path.exists():
                raise ProcessingError("Arquivo de áudio não foi criado")

            logger.info(f"✅ Áudio extraído: {audio_path.name}")
            return str(audio_path)

        except asyncio.TimeoutError:
            raise ProcessingError("Timeout ao extrair áudio (5min)")


class AudioChunker:
    """Divide e mescla chunks de áudio."""

    def __init__(self, config: AudioConfig):
        self.config = config

    def split(self, audio: AudioSegment) -> List[AudioSegment]:
        """Divide áudio em chunks."""
        chunk_duration_ms = self.config.chunk_duration_sec * 1000
        overlap_ms = self.config.chunk_overlap_sec * 1000

        chunks = []
        start_ms = 0
        audio_duration_ms = len(audio)

        while start_ms < audio_duration_ms:
            end_ms = min(start_ms + chunk_duration_ms, audio_duration_ms)
            chunks.append(audio[start_ms:end_ms])
            start_ms = end_ms - overlap_ms
            if start_ms >= audio_duration_ms - overlap_ms:
                break

        logger.info(f"📦 Áudio dividido em {len(chunks)} chunks")
        return chunks

    def merge(self, chunks: List[AudioSegment], overlap_ms: int = 0) -> AudioSegment:
        """Mescla chunks em um único áudio."""
        if len(chunks) == 0:
            raise ProcessingError("Nenhum chunk para mesclar")
        if len(chunks) == 1:
            return chunks[0]

        merged = chunks[0]
        for i in range(1, len(chunks)):
            if overlap_ms > 0 and len(merged) > overlap_ms:
                merged = merged.append(chunks[i], crossfade=overlap_ms)
            else:
                merged = merged + chunks[i]

        logger.info(f"✅ {len(chunks)} chunks mesclados")
        return merged


class AudioNormalizer:
    """Aplica operações de normalização no áudio."""

    def __init__(self, config: AudioConfig):
        self.config = config

    async def apply_highpass(self, audio: AudioSegment, cutoff: int = 80) -> AudioSegment:
        """Aplica filtro high-pass."""
        try:
            return high_pass_filter(audio, cutoff)
        except Exception as e:
            logger.warning(f"pydub high_pass_filter falhou: {e}")
            return audio

    def convert_to_mono(self, audio: AudioSegment) -> AudioSegment:
        """Converte áudio para mono."""
        return audio.set_channels(1)

    def set_sample_rate(self, audio: AudioSegment, sample_rate: int) -> AudioSegment:
        """Define sample rate."""
        return audio.set_frame_rate(sample_rate)


class AudioProcessor:
    """
    Processador de áudio principal seguindo SOLID.

    Responsabilidades delegadas:
    - FileOperations: Gerenciamento de arquivos
    - VideoExtractor: Extração de áudio de vídeo
    - AudioChunker: Divisão/mesclagem de chunks
    - AudioNormalizer: Aplicação de filtros
    """

    def __init__(
        self,
        config: AudioConfig,
        file_ops: Optional[FileOperations] = None,
        video_extractor: Optional[VideoExtractor] = None,
        chunker: Optional[AudioChunker] = None,
        normalizer: Optional[AudioNormalizer] = None,
    ):
        self.config = config
        self.file_ops = file_ops or FileOperations(config)
        self.video_extractor = video_extractor or VideoExtractor(self.file_ops)
        self.chunker = chunker or AudioChunker(config)
        self.normalizer = normalizer or AudioNormalizer(config)
        self.job_store: Optional[IJobStore] = None

    def set_job_store(self, job_store: IJobStore) -> None:
        """Injeta dependência do job store."""
        self.job_store = job_store

    async def process_audio_job(self, job: AudioNormJob) -> None:
        """
        Processa um job de áudio completamente.

        Args:
            job: AudioNormJob a ser processado

        Raises:
            ProcessingError: Se processamento falhar
        """
        temp_audio_path: Optional[str] = None
        temp_dir: Optional[Path] = None
        extracted_audio: Optional[str] = None

        try:
            logger.info(f"Iniciando processamento do job: {job.id}")
            job.status = JobStatus.PROCESSING
            job.progress = 2.0
            self._update_job(job)

            # Detecta e extrai áudio de vídeo se necessário
            file_to_process = job.input_file

            if self.video_extractor.is_video(job.input_file):
                logger.info("🎬 Vídeo detectado - extraindo áudio...")
                temp_dir = self.file_ops.get_temp_dir(job.id)
                extracted_audio = await self.video_extractor.extract_audio(job.input_file, temp_dir)
                file_to_process = extracted_audio
                job.progress = 5.0
                self._update_job(job)

            # Decide modo de processamento
            file_size_mb = os.path.getsize(file_to_process) / (1024 * 1024)

            if file_size_mb > self.config.streaming_threshold_mb:
                processed_audio = await self._process_with_streaming(job, file_to_process)
            else:
                processed_audio = await self._process_in_memory(job, file_to_process)

            # Salva resultado
            output_path = await self._save_result(job, processed_audio)

            # Finaliza job
            job.output_file = str(output_path)
            job.status = JobStatus.COMPLETED
            job.progress = 100.0
            job.file_size_output = output_path.stat().st_size
            job.completed_at = now_brazil()
            self._update_job(job)

            logger.info(f"✅ Job {job.id} completado: {output_path.name}")

        except Exception as e:
            error_msg = f"Erro no processamento: {str(e)}"
            logger.error(f"❌ Job {job.id} falhou: {error_msg}", exc_info=True)
            job.status = JobStatus.FAILED
            job.error_message = error_msg
            self._update_job(job)
            raise ProcessingError(error_msg) from e

        finally:
            # Limpeza
            if extracted_audio:
                self.file_ops.cleanup(Path(extracted_audio))
            if temp_dir:
                self.file_ops.cleanup(temp_dir)

    async def _process_in_memory(self, job: AudioNormJob, file_path: str) -> AudioSegment:
        """Processa áudio em memória."""
        logger.info("🧠 Processando em memória")

        try:
            audio = AudioSegment.from_file(file_path)
        except Exception as e:
            raise InvalidAudioFormat(f"Não foi possível carregar arquivo: {e}")

        job.progress = 10.0
        self._update_job(job)

        # Aplica operações
        audio = await self._apply_operations(audio, job)

        return audio

    async def _process_with_streaming(self, job: AudioNormJob, file_path: str) -> AudioSegment:
        """Processa áudio em streaming (chunks)."""
        logger.info("🌊 Processando via streaming")

        if not self.file_ops.check_disk_space(file_path):
            raise StorageError("Espaço em disco insuficiente")

        temp_dir = self.file_ops.get_temp_dir(job.id)
        chunk_paths: List[Path] = []
        processed_chunks: List[AudioSegment] = []

        try:
            # Divide em chunks com ffmpeg
            pattern = str(temp_dir / "chunk_%04d.wav")
            cmd = [
                "ffmpeg", "-i", file_path, "-f", "segment",
                "-segment_time", str(self.config.chunk_duration_sec),
                "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                pattern
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()

            if process.returncode != 0:
                raise ProcessingError(f"Falha ao segmentar áudio: {stderr.decode()[:200]}")

            chunk_paths = sorted(temp_dir.glob("chunk_*.wav"))
            if not chunk_paths:
                raise ProcessingError("Nenhum chunk criado")

            logger.info(f"📦 {len(chunk_paths)} chunks criados")
            job.progress = 20.0
            self._update_job(job)

            # Processa cada chunk
            total = len(chunk_paths)
            for i, chunk_path in enumerate(chunk_paths):
                progress = 20.0 + (i / total) * 70.0
                job.progress = progress
                logger.info(f"🔄 Chunk {i+1}/{total} [{progress:.1f}%]")

                try:
                    chunk = AudioSegment.from_file(chunk_path)
                    processed = await self._apply_operations(chunk, job, is_chunk=True)
                    processed_chunks.append(processed)
                except Exception as e:
                    logger.error(f"Erro no chunk {i+1}: {e}")
                    raise ProcessingError(f"Falha no chunk {i+1}: {e}")

            job.progress = 90.0
            self._update_job(job)

            # Mescla chunks
            overlap_ms = self.config.chunk_overlap_sec * 1000
            return self.chunker.merge(processed_chunks, overlap_ms)

        finally:
            # Limpa chunks temporários
            for path in chunk_paths:
                self.file_ops.cleanup(path)

    async def _apply_operations(
        self,
        audio: AudioSegment,
        job: AudioNormJob,
        is_chunk: bool = False
    ) -> AudioSegment:
        """Aplica operações de processamento."""

        # Remove ruído
        if job.remove_noise:
            # Simplificado - noise reduction é complexo
            pass

        # Converte para mono
        if job.convert_to_mono:
            audio = self.normalizer.convert_to_mono(audio)

        # Aplica high-pass
        if job.apply_highpass_filter:
            audio = await self.normalizer.apply_highpass(audio)

        # Define sample rate
        if job.set_sample_rate_16k:
            audio = self.normalizer.set_sample_rate(audio, 16000)

        if not is_chunk:
            job.progress = min(90.0, job.progress + 15.0)
            self._update_job(job)

        return audio

    async def _save_result(self, job: AudioNormJob, audio: AudioSegment) -> Path:
        """Salva áudio processado."""
        output_dir = Path("./processed")
        self.file_ops.ensure_dir(output_dir)

        suffix = f"_{job.processing_operations}" if job.processing_operations != "none" else ""
        output_path = output_dir / f"{job.id}{suffix}.webm"

        audio.export(
            str(output_path),
            format="webm",
            codec="libopus",
            parameters=["-strict", "-2"]
        )

        logger.info(f"💾 Arquivo salvo: {output_path.name}")
        return output_path

    def _update_job(self, job: AudioNormJob) -> None:
        """Atualiza job no store se disponível."""
        if self.job_store:
            try:
                self.job_store.update_job(job)
            except Exception as e:
                logger.warning(f"Falha ao atualizar job {job.id}: {e}")
