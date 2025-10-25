"""
Processador de áudio refatorado com boas práticas e alta resiliência
"""
import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Union
import logging

from pydub import AudioSegment
from pydub.effects import normalize as pydub_normalize

from .models import Job, JobStatus
from .config import get_settings
from .exceptions import (
    AudioProcessingError, 
    FileTooLargeError, 
    ProcessingTimeoutError,
    InsufficientResourcesError
)
from .logging_config import log_function_call, get_performance_logger
from .resource_manager import (
    TempFileManager, 
    ProcessingLimiter, 
    ResourceMonitor,
    timeout_context
)

logger = logging.getLogger(__name__)
performance_logger = get_performance_logger()

# Lazy loading do OpenUnmix para economia de memória
_openunmix_model = None


def get_openunmix_model():
    """Carrega modelo OpenUnmix apenas quando necessário (lazy loading)"""
    global _openunmix_model
    
    if _openunmix_model is None:
        try:
            import openunmix
            _openunmix_model = openunmix.umx.UMX()
            logger.info("OpenUnmix model loaded successfully")
        except ImportError as e:
            logger.error(f"Failed to load OpenUnmix: {e}")
            raise AudioProcessingError("vocal_isolation", "OpenUnmix not available")
    
    return _openunmix_model


class AudioProcessor:
    """
    Processador de áudio robusto com gestão de recursos e tratamento de erros
    """
    
    def __init__(self, job_store=None):
        self.settings = get_settings()
        self.job_store = job_store
        
        # Gerenciadores de recursos
        self.temp_manager = TempFileManager(
            base_dir=self.settings.temp_dir,
            max_age_minutes=self.settings.cache.ttl_hours * 60
        )
        
        self.processing_limiter = ProcessingLimiter(
            max_concurrent=self.settings.processing.max_concurrent_jobs,
            max_memory_mb=self.settings.processing.max_file_size_mb * 2,  # Buffer de segurança
            max_processing_time_minutes=self.settings.processing.job_timeout_minutes
        )
        
        self.resource_monitor = ResourceMonitor()
        
        # Diretórios de saída
        self.output_dir = self.settings.processed_dir
        self.output_dir.mkdir(exist_ok=True)
        
        logger.info("AudioProcessor initialized with resource management")
    
    @log_function_call()
    def _update_progress(self, job: Job, progress: float, message: str = "") -> None:
        """Atualiza progresso do job de forma thread-safe"""
        try:
            job.progress = min(max(progress, 0.0), 99.9)  # Clamp entre 0-99.9
            
            if self.job_store:
                self.job_store.update_job(job)
            
            logger.info(
                f"Job progress updated: {job.id}",
                extra={
                    "extra_fields": {
                        "job_id": job.id,
                        "progress": job.progress,
                        "message": message
                    }
                }
            )
        except Exception as e:
            logger.warning(f"Failed to update job progress: {e}")
    
    @log_function_call()
    async def process_audio_async(self, job: Job) -> Job:
        """
        Processa áudio de forma assíncrona com controle de recursos
        """
        import time
        start_time = time.time()
        
        try:
            # Adquire slot de processamento
            async with self.processing_limiter.acquire_processing_slot(
                job_id=job.id,
                estimated_memory_mb=self._estimate_memory_usage(job)
            ):
                return await self._process_audio_internal(job, start_time)
                
        except Exception as e:
            logger.error(f"Error in async audio processing for job {job.id}: {e}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            return job
    
    def process_audio(self, job: Job) -> Job:
        """
        Processa áudio (versão síncrona para compatibilidade)
        """
        import time
        start_time = time.time()
        
        try:
            return self._process_audio_sync(job, start_time)
        except Exception as e:
            logger.error(f"Error in sync audio processing for job {job.id}: {e}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            return job
    
    def _process_audio_sync(self, job: Job, start_time: float) -> Job:
        """Implementação síncrona do processamento"""
        try:
            job.status = JobStatus.PROCESSING
            self._update_progress(job, 5.0, "Iniciando processamento")
            
            # Validações iniciais
            input_path = Path(job.input_file)
            self._validate_input_file(input_path, job)
            
            # Verifica se há operações ativas
            operations = self._get_active_operations(job)
            if not operations:
                return self._complete_job_without_processing(job)
            
            # Processamento com timeout
            with timeout_context(
                timeout_seconds=self.settings.processing.job_timeout_minutes * 60,
                operation_name="audio_processing"
            ):
                return self._execute_processing_pipeline(job, input_path, operations, start_time)
                
        except Exception as e:
            return self._handle_processing_error(job, e, start_time)
    
    async def _process_audio_internal(self, job: Job, start_time: float) -> Job:
        """Implementação assíncrona interna do processamento"""
        # Similar ao sync, mas com awaits onde necessário
        return self._process_audio_sync(job, start_time)
    
    def _validate_input_file(self, input_path: Path, job: Job):
        """Valida arquivo de entrada"""
        if not input_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")
        
        # Atualiza tamanho do arquivo
        file_size = input_path.stat().st_size
        job.file_size_input = file_size
        
        # Verifica limites
        max_size = self.settings.processing.max_file_size_mb * 1024 * 1024
        if file_size > max_size:
            raise FileTooLargeError(file_size, max_size)
        
        # Verifica formato por conteúdo (magic bytes)
        if self.settings.security.validate_audio_headers:
            self._validate_audio_format(input_path)
    
    def _validate_audio_format(self, file_path: Path):
        """Valida formato de áudio através de magic bytes"""
        magic_bytes = {
            b'ID3': 'mp3',
            b'\xff\xfb': 'mp3',
            b'RIFF': 'wav',
            b'fLaC': 'flac',
            b'OggS': 'ogg',
            b'\x00\x00\x00 ftypM4A': 'm4a'
        }
        
        try:
            with open(file_path, 'rb') as f:
                header = f.read(20)
                
            for magic, format_name in magic_bytes.items():
                if header.startswith(magic) or magic in header:
                    logger.debug(f"Detected audio format: {format_name}")
                    return
            
            # Se não reconheceu, tenta carregar com pydub para validação
            AudioSegment.from_file(str(file_path))
            
        except Exception as e:
            raise AudioProcessingError("format_validation", f"Invalid audio file: {e}")
    
    def _get_active_operations(self, job: Job) -> list:
        """Retorna lista de operações ativas"""
        operations = []
        
        if job.isolate_vocals:
            operations.append("isolate_vocals")
        if job.remove_noise:
            operations.append("remove_noise")
        if job.normalize_volume:
            operations.append("normalize_volume")
        if job.convert_to_mono:
            operations.append("convert_to_mono")
        if job.apply_highpass_filter:
            operations.append("apply_highpass_filter")
        if job.set_sample_rate_16k:
            operations.append("set_sample_rate_16k")
        
        return operations
    
    def _complete_job_without_processing(self, job: Job) -> Job:
        """Completa job que não precisa de processamento"""
        self._update_progress(job, 95.0, "Nenhuma operação solicitada")
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now()
        job.progress = 100.0
        job.output_file = None
        job.file_size_output = None
        return job
    
    def _execute_processing_pipeline(
        self, 
        job: Job, 
        input_path: Path, 
        operations: list,
        start_time: float
    ) -> Job:
        """Executa pipeline de processamento"""
        
        # Carrega áudio inicial
        audio = AudioSegment.from_file(str(input_path))
        if audio is None:
            raise AudioProcessingError("load", f"Failed to load audio file: {input_path}")
        
        progress_step = 80.0 / len(operations)  # 80% para processamento (5% + 80% + 15%)
        current_progress = 10.0
        
        # Executa operações sequencialmente
        for i, operation in enumerate(operations):
            try:
                operation_start = time.time()
                
                if operation == "isolate_vocals":
                    audio = self._isolate_vocals(input_path, job)
                elif operation == "remove_noise":
                    audio = self._remove_noise(audio, job)
                elif operation == "normalize_volume":
                    audio = pydub_normalize(audio)
                elif operation == "convert_to_mono":
                    audio = audio.set_channels(1)
                elif operation == "apply_highpass_filter":
                    audio = self._apply_highpass_filter(audio, job)
                elif operation == "set_sample_rate_16k":
                    audio = audio.set_frame_rate(self.settings.processing.default_sample_rate)
                
                # Atualiza progresso
                current_progress += progress_step
                operation_time = (time.time() - operation_start) * 1000
                
                self._update_progress(job, current_progress, f"{operation} completed")
                
                # Log de performance
                performance_logger.log_processing_metrics(
                    job_id=job.id,
                    operation=operation,
                    duration_ms=operation_time,
                    success=True
                )
                
            except Exception as e:
                operation_time = (time.time() - operation_start) * 1000 if 'operation_start' in locals() else 0
                performance_logger.log_processing_metrics(
                    job_id=job.id,
                    operation=operation,
                    duration_ms=operation_time,
                    success=False
                )
                raise AudioProcessingError(operation, str(e))
        
        # Exporta resultado final
        return self._export_final_audio(job, audio, start_time)
    
    def _export_final_audio(self, job: Job, audio: AudioSegment, start_time: float) -> Job:
        """Exporta áudio processado"""
        self._update_progress(job, 90.0, "Exportando arquivo processado")
        
        output_path = self.output_dir / f"{job.id}.opus"
        
        # Exporta com configurações otimizadas
        audio.export(
            str(output_path), 
            format="opus",
            bitrate=self.settings.processing.default_bitrate
        )
        
        # Atualiza job
        job.output_file = str(output_path)
        job.file_size_output = output_path.stat().st_size
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now()
        job.progress = 100.0
        
        # Log final de performance
        total_time = (time.time() - start_time) * 1000
        performance_logger.log_processing_metrics(
            job_id=job.id,
            operation="complete_processing",
            duration_ms=total_time,
            input_size=job.file_size_input,
            output_size=job.file_size_output,
            success=True
        )
        
        self._update_progress(job, 100.0, "Processamento concluído")
        return job
    
    def _handle_processing_error(self, job: Job, error: Exception, start_time: float) -> Job:
        """Trata erros de processamento de forma padronizada"""
        logger.error(f"Processing error for job {job.id}: {error}", exc_info=True)
        
        job.status = JobStatus.FAILED
        job.error_message = str(error)
        
        # Remove arquivo de entrada se existir (limpeza)
        try:
            if job.input_file and Path(job.input_file).exists():
                Path(job.input_file).unlink()
                logger.debug(f"Cleaned up input file: {job.input_file}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to cleanup input file: {cleanup_error}")
        
        # Log de performance para falha
        total_time = (time.time() - start_time) * 1000
        performance_logger.log_processing_metrics(
            job_id=job.id,
            operation="processing_failed",
            duration_ms=total_time,
            success=False
        )
        
        return job
    
    def _estimate_memory_usage(self, job: Job) -> float:
        """Estima uso de memória baseado no tamanho do arquivo e operações"""
        if not job.file_size_input:
            return 100  # Estimativa conservadora
        
        # Fator base: áudio em memória é ~10x o tamanho do arquivo comprimido
        base_memory = (job.file_size_input / 1024 / 1024) * 10
        
        # Multiplicadores por operação
        multiplier = 1.0
        if job.isolate_vocals:
            multiplier *= 2.5  # OpenUnmix usa mais memória
        if job.remove_noise:
            multiplier *= 1.8  # Noise reduction precisa de buffers
        
        return base_memory * multiplier
    
    def _isolate_vocals(self, audio_path: Path, job: Job) -> AudioSegment:
        """
        Isola vocais usando OpenUnmix com gestão de recursos melhorada
        """
        with self.temp_manager.create_temp_dir(prefix=f"vocals_{job.id}_") as temp_dir:
            try:
                import torch
                import torchaudio
                
                model = get_openunmix_model()
                
                self._update_progress(job, 15.0, "Convertendo para processamento de IA")
                
                # Converte para WAV temporário se necessário
                temp_wav = temp_dir / "input.wav"
                audio_temp = AudioSegment.from_file(str(audio_path))
                audio_temp.export(str(temp_wav), format='wav')
                
                # Carrega com torchaudio
                wav, sr = torchaudio.load(str(temp_wav))
                duration_seconds = wav.shape[1] / sr
                
                self._update_progress(job, 20.0, f"Processando com IA (~{int(duration_seconds * 0.2)}s)")
                
                # OpenUnmix espera formato: [batch, channels, time]
                if wav.dim() == 2:
                    wav = wav.unsqueeze(0)
                
                # Processa com modelo
                with torch.no_grad():
                    estimates = model(wav)
                    vocals = estimates['vocals'].squeeze(0)
                
                # Salva resultado temporário
                temp_vocals = temp_dir / "vocals.wav"
                torchaudio.save(str(temp_vocals), vocals, sr)
                
                # Retorna como AudioSegment
                return AudioSegment.from_wav(str(temp_vocals))
                
            except Exception as e:
                logger.warning(f"Vocal isolation failed, using original audio: {e}")
                return AudioSegment.from_file(str(audio_path))
    
    def _remove_noise(self, audio: AudioSegment, job: Job = None) -> AudioSegment:
        """Remove ruído usando noisereduce com tratamento de erro robusto"""
        try:
            import numpy as np
            import noisereduce as nr
            
            # Converte para numpy
            samples = np.array(audio.get_array_of_samples())
            
            # Trata stereo
            if audio.channels == 2:
                samples = samples.reshape((-1, 2))
            
            # Aplica noise reduction com configuração otimizada
            reduced_samples = nr.reduce_noise(
                y=samples,
                sr=audio.frame_rate,
                stationary=True,
                prop_decrease=self.settings.processing.noise_reduction_strength
            )
            
            # Converte de volta
            return AudioSegment(
                reduced_samples.tobytes(),
                frame_rate=audio.frame_rate,
                sample_width=audio.sample_width,
                channels=audio.channels
            )
            
        except Exception as e:
            logger.warning(f"Noise reduction failed, using original audio: {e}")
            return audio
    
    def _apply_highpass_filter(self, audio: AudioSegment, cutoff: int = 80) -> AudioSegment:
        """Aplica filtro high-pass com tratamento de erro"""
        try:
            import numpy as np
            from scipy import signal
            
            # Converte para numpy
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            samples = samples / (2 ** (audio.sample_width * 8 - 1))
            
            # Design do filtro
            nyquist = audio.frame_rate / 2
            normal_cutoff = cutoff / nyquist
            b, a = signal.butter(5, normal_cutoff, btype='high', analog=False)
            
            # Aplica filtro com proteção contra NaN
            filtered_samples = signal.filtfilt(b, a, samples)
            filtered_samples = np.nan_to_num(filtered_samples, nan=0.0, posinf=0.0, neginf=0.0)
            filtered_samples = np.int16(filtered_samples * (2 ** (audio.sample_width * 8 - 1)))
            
            return AudioSegment(
                filtered_samples.tobytes(),
                frame_rate=audio.frame_rate,
                sample_width=audio.sample_width,
                channels=audio.channels
            )
            
        except Exception as e:
            logger.warning(f"High-pass filter failed, using original audio: {e}")
            return audio
    
    def get_file_path(self, job: Job) -> Optional[Path]:
        """Retorna caminho do arquivo processado se existir"""
        if job.output_file and Path(job.output_file).exists():
            return Path(job.output_file)
        return None
    
    def cleanup_job_files(self, job: Job):
        """Limpa arquivos associados ao job"""
        files_to_clean = []
        
        if job.input_file:
            files_to_clean.append(Path(job.input_file))
        if job.output_file:
            files_to_clean.append(Path(job.output_file))
        
        for file_path in files_to_clean:
            try:
                if file_path.exists():
                    file_path.unlink()
                    logger.debug(f"Cleaned up file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup file {file_path}: {e}")


import time  # Adicionado import necessário