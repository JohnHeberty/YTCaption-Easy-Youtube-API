"""
Processador de transcrição atualizado com alta resiliência
Integra todas as funcionalidades de monitoramento e error handling
"""
import asyncio
import time
import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

import whisper
import torch
import librosa
import soundfile as sf
from pydantic import BaseModel

from .models_new import Job, JobStatus, ProcessingResult, TranscriptionSegment
from .config import get_settings
from .exceptions import (
    TranscriptionError, AudioProcessingError, ModelLoadError,
    CircuitBreaker, retry_with_backoff
)
from .resource_manager import ResourceMonitor, TempFileManager, ProcessingLimiter
from .security_validator import FileValidator
from .observability import ObservabilityManager
from .logging_config import get_logger

logger = get_logger(__name__)


class WhisperModelManager:
    """
    Gerenciador de modelos Whisper com cache e pooling
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._models_cache: Dict[str, whisper.Whisper] = {}
        self._model_locks: Dict[str, asyncio.Lock] = {}
        self._load_circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=300,
            name="whisper_model_load"
        )
    
    async def get_model(self, model_name: str) -> whisper.Whisper:
        """
        Obtém modelo Whisper com cache e circuit breaker
        
        Args:
            model_name: Nome do modelo (tiny, base, small, medium, large)
            
        Returns:
            Modelo Whisper carregado
            
        Raises:
            ModelLoadError: Se falhar ao carregar modelo
        """
        if model_name not in self._model_locks:
            self._model_locks[model_name] = asyncio.Lock()
        
        async with self._model_locks[model_name]:
            if model_name in self._models_cache:
                logger.info(f"Using cached Whisper model: {model_name}")
                return self._models_cache[model_name]
            
            return await self._load_model(model_name)
    
    @retry_with_backoff(max_retries=2)
    async def _load_model(self, model_name: str) -> whisper.Whisper:
        """Carrega modelo com retry e circuit breaker"""
        
        async def _load():
            logger.info(f"Loading Whisper model: {model_name}")
            start_time = time.time()
            
            try:
                # Detecta device disponível
                device = "cuda" if torch.cuda.is_available() else "cpu"
                
                # Carrega modelo
                model = whisper.load_model(
                    model_name,
                    device=device,
                    download_root=self.settings.transcription.model_cache_dir
                )
                
                load_time = time.time() - start_time
                logger.info(
                    f"Whisper model loaded successfully",
                    extra={
                        "model_name": model_name,
                        "device": device,
                        "load_time": load_time
                    }
                )
                
                # Cache o modelo
                self._models_cache[model_name] = model
                
                return model
                
            except Exception as e:
                logger.error(f"Failed to load Whisper model {model_name}: {e}")
                raise ModelLoadError(f"Failed to load model {model_name}: {e}")
        
        return await self._load_circuit_breaker.call(_load)
    
    def get_device_info(self) -> Dict[str, Any]:
        """Retorna informações do device"""
        device_info = {"device": "cpu", "cuda_available": False}
        
        if torch.cuda.is_available():
            device_info.update({
                "device": "cuda", 
                "cuda_available": True,
                "gpu_count": torch.cuda.device_count(),
                "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.device_count() > 0 else None
            })
        
        return device_info
    
    def cleanup_cache(self, max_models: int = 3):
        """Remove modelos antigos do cache"""
        if len(self._models_cache) > max_models:
            # Remove o primeiro modelo (FIFO)
            oldest_model = next(iter(self._models_cache))
            del self._models_cache[oldest_model]
            logger.info(f"Removed cached model: {oldest_model}")


class AudioProcessor:
    """
    Processador de áudio com validação e otimização
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.resource_monitor = ResourceMonitor()
        self.temp_manager = TempFileManager()
        
    async def prepare_audio(self, input_path: str) -> str:
        """
        Prepara áudio para transcrição
        
        Args:
            input_path: Caminho do arquivo de entrada
            
        Returns:
            Caminho do arquivo processado
            
        Raises:
            AudioProcessingError: Se falhar ao processar áudio
        """
        try:
            # Valida arquivo de entrada
            if not os.path.exists(input_path):
                raise AudioProcessingError(f"Audio file not found: {input_path}")
            
            # Carrega metadados do áudio
            info = self._get_audio_info(input_path)
            
            # Verifica se precisa converter
            if self._needs_conversion(info):
                return await self._convert_audio(input_path, info)
            
            return input_path
            
        except Exception as e:
            logger.error(f"Failed to prepare audio: {e}")
            raise AudioProcessingError(f"Audio preparation failed: {e}")
    
    def _get_audio_info(self, file_path: str) -> Dict[str, Any]:
        """Obtém informações do arquivo de áudio"""
        try:
            # Tenta carregar com librosa para informações detalhadas
            y, sr = librosa.load(file_path, sr=None, duration=1.0)  # Carrega só 1 segundo
            duration = librosa.get_duration(path=file_path)
            
            return {
                "sample_rate": sr,
                "duration": duration,
                "channels": 1 if y.ndim == 1 else y.shape[0],
                "format": Path(file_path).suffix.lower()
            }
            
        except Exception as e:
            logger.warning(f"Failed to get detailed audio info: {e}")
            
            # Fallback básico
            return {
                "sample_rate": None,
                "duration": None,
                "channels": None,
                "format": Path(file_path).suffix.lower()
            }
    
    def _needs_conversion(self, info: Dict[str, Any]) -> bool:
        """Verifica se áudio precisa ser convertido"""
        
        # Formatos suportados nativamente pelo Whisper
        supported_formats = {'.wav', '.mp3', '.m4a', '.flac', '.ogg'}
        
        if info["format"] not in supported_formats:
            return True
            
        # Verifica sample rate
        target_sr = self.settings.transcription.target_sample_rate
        if info["sample_rate"] and target_sr and info["sample_rate"] != target_sr:
            return True
            
        return False
    
    async def _convert_audio(self, input_path: str, info: Dict[str, Any]) -> str:
        """Converte áudio para formato otimizado"""
        
        output_path = await self.temp_manager.create_temp_file(
            suffix='.wav',
            prefix='converted_audio_'
        )
        
        try:
            logger.info(f"Converting audio: {input_path} -> {output_path}")
            
            # Carrega áudio completo
            y, sr = librosa.load(input_path, sr=self.settings.transcription.target_sample_rate)
            
            # Normaliza áudio se necessário
            if self.settings.transcription.normalize_audio:
                y = librosa.util.normalize(y)
            
            # Salva no formato otimizado
            sf.write(output_path, y, sr, format='WAV', subtype='PCM_16')
            
            logger.info(f"Audio converted successfully: {output_path}")
            return output_path
            
        except Exception as e:
            # Remove arquivo temporário em caso de erro
            await self.temp_manager.cleanup_file(output_path)
            raise AudioProcessingError(f"Audio conversion failed: {e}")


class TranscriptionProcessor:
    """
    Processador principal de transcrição com alta resiliência
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.model_manager = WhisperModelManager()
        self.audio_processor = AudioProcessor()
        self.resource_monitor = ResourceMonitor()
        self.processing_limiter = ProcessingLimiter()
        self.observability = ObservabilityManager()
        self.temp_manager = TempFileManager()
        
        # Circuit breakers para operações críticas
        self._transcription_circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=600,
            name="transcription_processing"
        )
    
    async def process_transcription(self, job: Job) -> ProcessingResult:
        """
        Processa transcrição de áudio com monitoramento completo
        
        Args:
            job: Job de transcrição
            
        Returns:
            Resultado do processamento
        """
        
        async with self.processing_limiter.acquire_slot():
            return await self._process_with_monitoring(job)
    
    async def _process_with_monitoring(self, job: Job) -> ProcessingResult:
        """Processa com monitoramento de recursos"""
        
        start_time = time.time()
        
        # Inicia monitoramento
        self.observability.start_transcription(job.id)
        
        try:
            # Verifica recursos disponíveis
            if not await self.resource_monitor.check_capacity_for_transcription(
                job.input_file
            ):
                raise TranscriptionError("Insufficient resources for transcription")
            
            # Atualiza job como processing
            model_info = self.model_manager.get_device_info()
            job.mark_as_processing(
                model=self.settings.transcription.default_model,
                device=model_info["device"]
            )
            
            # Processa transcrição
            result = await self._transcription_circuit_breaker.call(
                lambda: self._transcribe_audio(job)
            )
            
            # Atualiza job como completado
            job.mark_as_completed(
                transcription_text=result["text"],
                output_file=result["output_file"],
                detected_language=result.get("detected_language"),
                confidence_score=result.get("confidence"),
                audio_duration=result.get("audio_duration"),
                segments_count=result.get("segments_count"),
                segments_data=result.get("segments")
            )
            
            # Registra sucesso
            processing_time = time.time() - start_time
            self.observability.complete_transcription(job.id, processing_time, success=True)
            
            return ProcessingResult(
                success=True,
                job_id=job.id,
                transcription_text=result["text"],
                output_file=result["output_file"],
                segments=result.get("segments"),
                processing_time=processing_time,
                metadata=result
            )
            
        except Exception as e:
            # Registra falha
            processing_time = time.time() - start_time
            self.observability.complete_transcription(job.id, processing_time, success=False)
            
            error_msg = str(e)
            job.mark_as_failed(error_msg)
            
            logger.error(
                f"Transcription failed for job {job.id}",
                extra={
                    "job_id": job.id,
                    "error": error_msg,
                    "processing_time": processing_time
                }
            )
            
            return ProcessingResult(
                success=False,
                job_id=job.id,
                error=error_msg,
                processing_time=processing_time
            )
    
    @retry_with_backoff(max_retries=2)
    async def _transcribe_audio(self, job: Job) -> Dict[str, Any]:
        """Executa transcrição do áudio"""
        
        logger.info(f"Starting transcription for job {job.id}")
        
        # Prepara áudio
        prepared_audio = await self.audio_processor.prepare_audio(job.input_file)
        
        try:
            # Carrega modelo
            model = await self.model_manager.get_model(
                self.settings.transcription.default_model
            )
            
            # Atualiza progresso
            job.update_progress(25.0, "Model loaded, starting transcription")
            
            # Configurações de transcrição
            transcribe_options = {
                "language": job.language if job.language != "auto" else None,
                "task": "transcribe",
                "beam_size": job.beam_size,
                "temperature": job.temperature,
                "verbose": False
            }
            
            # Executa transcrição
            start_transcribe = time.time()
            result = model.transcribe(prepared_audio, **transcribe_options)
            transcribe_time = time.time() - start_transcribe
            
            # Atualiza progresso
            job.update_progress(75.0, "Transcription complete, generating output")
            
            # Processa resultado
            transcription_data = await self._process_transcription_result(
                result, job, transcribe_time
            )
            
            # Gera arquivo de saída
            output_file = await self._generate_output_file(
                transcription_data, job
            )
            
            job.update_progress(100.0, "Processing complete")
            
            return {
                **transcription_data,
                "output_file": output_file,
                "processing_time": transcribe_time
            }
            
        finally:
            # Cleanup arquivo temporário se foi criado
            if prepared_audio != job.input_file:
                await self.temp_manager.cleanup_file(prepared_audio)
    
    async def _process_transcription_result(
        self, 
        whisper_result: Dict[str, Any], 
        job: Job,
        processing_time: float
    ) -> Dict[str, Any]:
        """Processa resultado do Whisper"""
        
        # Extrai texto principal
        text = whisper_result.get("text", "").strip()
        
        # Processa segmentos
        segments = []
        if "segments" in whisper_result:
            for i, segment in enumerate(whisper_result["segments"]):
                segments.append({
                    "id": i + 1,
                    "start": segment.get("start", 0.0),
                    "end": segment.get("end", 0.0),
                    "text": segment.get("text", "").strip(),
                    "confidence": segment.get("avg_logprob")
                })
        
        # Calcula estatísticas
        audio_duration = whisper_result.get("segments", [{}])[-1].get("end", 0.0) if segments else None
        detected_language = whisper_result.get("language")
        
        # Calcula confiança média
        confidence = None
        if segments:
            confidences = [s.get("confidence") for s in segments if s.get("confidence")]
            if confidences:
                confidence = sum(confidences) / len(confidences)
        
        return {
            "text": text,
            "segments": segments,
            "detected_language": detected_language,
            "confidence": confidence,
            "audio_duration": audio_duration,
            "segments_count": len(segments),
            "processing_time": processing_time
        }
    
    async def _generate_output_file(
        self, 
        transcription_data: Dict[str, Any], 
        job: Job
    ) -> str:
        """Gera arquivo de saída no formato solicitado"""
        
        output_dir = Path(self.settings.transcription.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Nome do arquivo baseado no job_id
        filename = f"{job.id}.{job.output_format}"
        output_path = output_dir / filename
        
        # Gera conteúdo baseado no formato
        content = await self._format_transcription(transcription_data, job.output_format)
        
        # Escreve arquivo
        async with asyncio.Lock():  # Protege escrita de arquivo
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        logger.info(f"Output file generated: {output_path}")
        return str(output_path)
    
    async def _format_transcription(
        self, 
        data: Dict[str, Any], 
        output_format: str
    ) -> str:
        """Formata transcrição para o formato de saída"""
        
        text = data["text"]
        segments = data.get("segments", [])
        
        if output_format == "txt":
            return text
            
        elif output_format == "json":
            import json
            return json.dumps(data, ensure_ascii=False, indent=2)
            
        elif output_format == "srt":
            return self._format_srt(segments)
            
        elif output_format == "vtt":
            return self._format_vtt(segments)
            
        else:
            return text
    
    def _format_srt(self, segments: List[Dict[str, Any]]) -> str:
        """Formata como arquivo SRT"""
        srt_content = []
        
        for segment in segments:
            start_time = self._seconds_to_srt_time(segment["start"])
            end_time = self._seconds_to_srt_time(segment["end"])
            text = segment["text"].strip()
            
            srt_content.append(f"{segment['id']}")
            srt_content.append(f"{start_time} --> {end_time}")
            srt_content.append(text)
            srt_content.append("")  # Linha em branco
        
        return "\n".join(srt_content)
    
    def _format_vtt(self, segments: List[Dict[str, Any]]) -> str:
        """Formata como arquivo VTT"""
        vtt_content = ["WEBVTT", ""]
        
        for segment in segments:
            start_time = self._seconds_to_vtt_time(segment["start"])
            end_time = self._seconds_to_vtt_time(segment["end"])
            text = segment["text"].strip()
            
            vtt_content.append(f"{start_time} --> {end_time}")
            vtt_content.append(text)
            vtt_content.append("")
        
        return "\n".join(vtt_content)
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """Converte segundos para formato SRT (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds - int(seconds)) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    def _seconds_to_vtt_time(self, seconds: float) -> str:
        """Converte segundos para formato VTT (HH:MM:SS.mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds - int(seconds)) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millisecs:03d}"
    
    async def cleanup_job_files(self, job: Job) -> None:
        """Remove arquivos temporários do job"""
        try:
            # Remove arquivo de saída se expirado
            if job.output_file and os.path.exists(job.output_file):
                os.remove(job.output_file)
                logger.info(f"Cleaned up output file: {job.output_file}")
                
        except Exception as e:
            logger.error(f"Failed to cleanup job files: {e}")
    
    async def get_processing_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de processamento"""
        return {
            "active_jobs": self.processing_limiter.active_count,
            "max_concurrent": self.processing_limiter.max_concurrent,
            "queue_size": self.processing_limiter.queue_size,
            "device_info": self.model_manager.get_device_info(),
            "resource_usage": await self.resource_monitor.get_current_usage()
        }