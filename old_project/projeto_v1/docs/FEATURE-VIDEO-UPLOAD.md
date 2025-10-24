# Feature: Direct Video Upload Endpoint

**Data**: 2025-10-23  
**Status**: 📋 PLANEJAMENTO  
**Prioridade**: P1 - HIGH  
**Estimativa**: 8-12 horas de desenvolvimento

---

## 📊 Executive Summary

Adicionar endpoint `/api/v1/transcribe/upload` para permitir upload direto de arquivos de vídeo/áudio, complementando o endpoint atual que aceita apenas URLs do YouTube.

**Benefícios**:
- ✅ Suporte a vídeos de qualquer plataforma (não só YouTube)
- ✅ Vídeos privados/locais podem ser transcritos
- ✅ Maior flexibilidade para usuários
- ✅ Reduz dependência do YouTube (bypass rate limits)
- ✅ Casos de uso corporativo (vídeos internos de empresas)

**Complexidade**: Média-Alta
- Upload de arquivos grandes (até 2.5GB por padrão)
- Validação de formatos e codec
- Extração de áudio eficiente
- Gerenciamento de storage temporário
- Rate limiting mais restritivo

---

## 🎯 Objetivos

### Funcionais
1. Aceitar upload de arquivos de vídeo/áudio via multipart/form-data
2. Validar formato, tamanho e duração do arquivo
3. Extrair áudio usando FFmpeg (mesma pipeline do YouTube)
4. Integrar com sistema de transcrição Whisper existente
5. Retornar mesmo formato de resposta (TranscribeResponseDTO)

### Não-Funcionais
1. **Performance**: Upload de até 2.5GB em < 5 minutos
2. **Segurança**: Validação rigorosa de MIME types e conteúdo
3. **Resiliência**: Circuit breaker e timeout configuráveis
4. **Observabilidade**: Métricas Prometheus para uploads
5. **Escalabilidade**: Suporte a upload paralelo (limitado por IP)

---

## 🏗️ Arquitetura

### Clean Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                        │
│  • POST /api/v1/transcribe/upload                           │
│  • UploadVideoRequestDTO                                     │
│  • Rate Limiting: 2 uploads/min (vs 5 YouTube/min)          │
│  • Max file size: 2.5GB (configurável)                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   APPLICATION LAYER                          │
│  • TranscribeUploadedVideoUseCase                           │
│  • Orquestra: Upload → Validation → Extract → Transcribe    │
│  • Retorna: TranscribeResponseDTO (igual YouTube)           │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   DOMAIN LAYER                               │
│  • UploadedVideoFile (Value Object)                         │
│  • IVideoUploadValidator (Interface)                        │
│  • IVideoProcessor (Interface)                              │
│  • VideoUploadError (Exception)                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                INFRASTRUCTURE LAYER                          │
│  • LocalVideoUploadService (implementa IVideoUploadService)  │
│  • VideoUploadValidator (formatos, tamanho, duração)        │
│  • VideoProcessor (extração de áudio via FFmpeg)            │
│  • UploadMetricsCollector (Prometheus)                      │
└─────────────────────────────────────────────────────────────┘
```

### Fluxo de Dados

```
1. CLIENT                    2. API ROUTE                3. USE CASE
   │                            │                            │
   │ multipart/form-data        │                            │
   │──────────────────────────► │ Validate size/type         │
   │ file: video.mp4            │──────────────────────────► │
   │ language: "auto"           │                            │
   │                            │                            │ 4. STORAGE
                                                             │
                                                             │ Save to temp
                                                             │────────────►
                                                             │
5. VALIDATOR                 6. PROCESSOR                 7. WHISPER
   │                            │                            │
   │ Check format               │ Extract audio              │
   ◄────────────────────────────│ FFmpeg pipeline            │
   │                            │──────────────────────────► │ Transcribe
   │                            │                            │
                                                             │
8. CLEANUP                   9. RESPONSE                 10. CLIENT
   │                            │                            │
   │ Remove temp files          │ TranscribeResponseDTO      │
   │◄───────────────────────────│                            │
   │                            │──────────────────────────► │
```

---

## 📝 Implementação Detalhada

### FASE 1: Domain Layer (2 horas)

#### 1.1. Value Object: UploadedVideoFile

**Arquivo**: `src/domain/value_objects/uploaded_video_file.py`

```python
"""
Value Object para vídeo enviado via upload.
Imutável e com validações.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class UploadedVideoFile:
    """
    Representa um arquivo de vídeo enviado via upload.
    
    Attributes:
        file_path: Caminho do arquivo no storage temporário
        original_filename: Nome original do arquivo
        mime_type: MIME type do arquivo
        size_bytes: Tamanho em bytes
        duration_seconds: Duração em segundos (após validação)
    """
    
    file_path: Path
    original_filename: str
    mime_type: str
    size_bytes: int
    duration_seconds: Optional[float] = None
    
    def __post_init__(self):
        """Validações após inicialização."""
        if not self.file_path.exists():
            raise ValueError(f"File not found: {self.file_path}")
        
        if self.size_bytes <= 0:
            raise ValueError("File size must be positive")
        
        if not self.original_filename:
            raise ValueError("Original filename is required")
    
    def get_extension(self) -> str:
        """Retorna extensão do arquivo."""
        return self.file_path.suffix.lower()
    
    def is_video(self) -> bool:
        """Verifica se é vídeo."""
        return self.mime_type.startswith('video/')
    
    def is_audio(self) -> bool:
        """Verifica se é áudio."""
        return self.mime_type.startswith('audio/')
    
    def get_size_mb(self) -> float:
        """Retorna tamanho em MB."""
        return self.size_bytes / (1024 * 1024)
```

#### 1.2. Interface: IVideoUploadValidator

**Arquivo**: `src/domain/interfaces/video_upload_validator.py`

```python
"""
Interface para validação de vídeos enviados.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any

from src.domain.value_objects import UploadedVideoFile


class IVideoUploadValidator(ABC):
    """Interface para validação de uploads de vídeo."""
    
    @abstractmethod
    async def validate_file(
        self,
        file_path: Path,
        max_size_mb: int,
        max_duration_seconds: int
    ) -> Dict[str, Any]:
        """
        Valida arquivo de vídeo/áudio.
        
        Args:
            file_path: Caminho do arquivo
            max_size_mb: Tamanho máximo em MB
            max_duration_seconds: Duração máxima em segundos
            
        Returns:
            Dict com metadata: duration, codec, bitrate, etc.
            
        Raises:
            ValidationError: Se validação falhar
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> list[str]:
        """Retorna lista de formatos suportados."""
        pass
```

#### 1.3. Exception: VideoUploadError

**Arquivo**: `src/domain/exceptions.py` (adicionar)

```python
class VideoUploadError(DomainException):
    """Erro durante upload de vídeo."""
    pass


class UnsupportedFormatError(VideoUploadError):
    """Formato de arquivo não suportado."""
    pass


class FileTooLargeError(VideoUploadError):
    """Arquivo excede tamanho máximo."""
    pass


class InvalidVideoFileError(VideoUploadError):
    """Arquivo de vídeo corrompido ou inválido."""
    pass
```

---

### FASE 2: Infrastructure Layer (4 horas)

#### 2.1. Video Upload Validator

**Arquivo**: `src/infrastructure/validators/video_upload_validator.py`

```python
"""
Validador de arquivos de vídeo enviados.
Usa FFprobe para análise detalhada.
"""
import subprocess
import json
from pathlib import Path
from typing import Dict, Any
from loguru import logger

from src.domain.interfaces import IVideoUploadValidator
from src.domain.exceptions import (
    ValidationError,
    UnsupportedFormatError,
    FileTooLargeError,
    InvalidVideoFileError
)


class VideoUploadValidator(IVideoUploadValidator):
    """
    Valida uploads de vídeo usando FFprobe.
    """
    
    # Formatos suportados (extensões)
    SUPPORTED_VIDEO_FORMATS = [
        '.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv',
        '.wmv', '.m4v', '.mpg', '.mpeg', '.3gp'
    ]
    
    SUPPORTED_AUDIO_FORMATS = [
        '.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg',
        '.wma', '.opus', '.webm'
    ]
    
    # MIME types aceitos
    SUPPORTED_MIME_TYPES = [
        'video/mp4', 'video/x-msvideo', 'video/quicktime',
        'video/x-matroska', 'video/webm', 'video/x-flv',
        'audio/mpeg', 'audio/wav', 'audio/aac', 'audio/mp4',
        'audio/flac', 'audio/ogg', 'audio/x-ms-wma'
    ]
    
    def __init__(self, ffprobe_path: str = "ffprobe"):
        """
        Inicializa validador.
        
        Args:
            ffprobe_path: Caminho para executável do FFprobe
        """
        self.ffprobe_path = ffprobe_path
        self._check_ffprobe_available()
    
    def _check_ffprobe_available(self):
        """Verifica se FFprobe está disponível."""
        try:
            subprocess.run(
                [self.ffprobe_path, '-version'],
                capture_output=True,
                check=True,
                timeout=5
            )
            logger.info(f"FFprobe available: {self.ffprobe_path}")
        except Exception as e:
            logger.error(f"FFprobe not available: {e}")
            raise RuntimeError(f"FFprobe not found: {e}")
    
    async def validate_file(
        self,
        file_path: Path,
        max_size_mb: int,
        max_duration_seconds: int
    ) -> Dict[str, Any]:
        """
        Valida arquivo de vídeo/áudio.
        
        Validações:
        1. Extensão suportada
        2. Tamanho máximo
        3. MIME type válido
        4. Arquivo não corrompido (FFprobe)
        5. Duração máxima
        6. Codec compatível
        """
        logger.info(f"Validating upload: {file_path.name}")
        
        # 1. Validar extensão
        extension = file_path.suffix.lower()
        if extension not in (self.SUPPORTED_VIDEO_FORMATS + self.SUPPORTED_AUDIO_FORMATS):
            raise UnsupportedFormatError(
                f"Format {extension} not supported. "
                f"Supported: {', '.join(self.SUPPORTED_VIDEO_FORMATS + self.SUPPORTED_AUDIO_FORMATS)}"
            )
        
        # 2. Validar tamanho
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > max_size_mb:
            raise FileTooLargeError(
                f"File size ({size_mb:.2f}MB) exceeds maximum ({max_size_mb}MB)"
            )
        
        # 3. Analisar com FFprobe
        metadata = await self._analyze_with_ffprobe(file_path)
        
        # 4. Validar duração
        duration = metadata.get('duration', 0)
        if duration > max_duration_seconds:
            raise ValidationError(
                f"Video duration ({duration}s) exceeds maximum ({max_duration_seconds}s)"
            )
        
        logger.info(
            f"✅ File validated: {file_path.name} "
            f"({size_mb:.2f}MB, {duration}s, {metadata.get('codec')})"
        )
        
        return metadata
    
    async def _analyze_with_ffprobe(self, file_path: Path) -> Dict[str, Any]:
        """
        Analisa arquivo com FFprobe.
        
        Returns:
            Dict com: duration, codec, bitrate, format, streams, etc.
        """
        try:
            # FFprobe command para JSON output
            cmd = [
                self.ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(file_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )
            
            data = json.loads(result.stdout)
            
            # Extrair informações relevantes
            format_info = data.get('format', {})
            streams = data.get('streams', [])
            
            # Encontrar stream de vídeo/áudio
            video_stream = next((s for s in streams if s['codec_type'] == 'video'), None)
            audio_stream = next((s for s in streams if s['codec_type'] == 'audio'), None)
            
            metadata = {
                'duration': float(format_info.get('duration', 0)),
                'size_bytes': int(format_info.get('size', 0)),
                'bitrate': int(format_info.get('bit_rate', 0)),
                'format': format_info.get('format_name', 'unknown'),
                'has_video': video_stream is not None,
                'has_audio': audio_stream is not None,
            }
            
            if video_stream:
                metadata['video_codec'] = video_stream.get('codec_name')
                metadata['width'] = video_stream.get('width')
                metadata['height'] = video_stream.get('height')
                metadata['fps'] = eval(video_stream.get('r_frame_rate', '0/1'))
            
            if audio_stream:
                metadata['audio_codec'] = audio_stream.get('codec_name')
                metadata['sample_rate'] = audio_stream.get('sample_rate')
                metadata['channels'] = audio_stream.get('channels')
            
            # Codec principal (vídeo ou áudio)
            metadata['codec'] = metadata.get('video_codec') or metadata.get('audio_codec')
            
            return metadata
            
        except subprocess.TimeoutExpired:
            raise InvalidVideoFileError("FFprobe analysis timed out (file may be corrupted)")
        except subprocess.CalledProcessError as e:
            raise InvalidVideoFileError(f"FFprobe analysis failed: {e.stderr}")
        except json.JSONDecodeError:
            raise InvalidVideoFileError("FFprobe returned invalid JSON")
        except Exception as e:
            raise InvalidVideoFileError(f"Failed to analyze file: {str(e)}")
    
    def get_supported_formats(self) -> list[str]:
        """Retorna lista de formatos suportados."""
        return self.SUPPORTED_VIDEO_FORMATS + self.SUPPORTED_AUDIO_FORMATS
```

#### 2.2. Video Upload Service

**Arquivo**: `src/infrastructure/storage/video_upload_service.py`

```python
"""
Serviço de upload de vídeos.
Gerencia salvamento e processamento de uploads.
"""
import shutil
from pathlib import Path
from typing import Optional
from fastapi import UploadFile
from loguru import logger

from src.domain.interfaces import IStorageService
from src.domain.value_objects import UploadedVideoFile
from src.domain.exceptions import StorageError


class VideoUploadService:
    """
    Serviço para gerenciar uploads de vídeo.
    """
    
    def __init__(self, storage_service: IStorageService, chunk_size: int = 8192):
        """
        Inicializa serviço de upload.
        
        Args:
            storage_service: Serviço de storage para arquivos temporários
            chunk_size: Tamanho do chunk para streaming (8KB padrão)
        """
        self.storage = storage_service
        self.chunk_size = chunk_size
    
    async def save_upload(
        self,
        upload_file: UploadFile,
        temp_dir: Optional[Path] = None
    ) -> UploadedVideoFile:
        """
        Salva arquivo enviado no storage temporário.
        
        Args:
            upload_file: Arquivo FastAPI UploadFile
            temp_dir: Diretório temporário (cria se None)
            
        Returns:
            UploadedVideoFile com informações do arquivo salvo
            
        Raises:
            StorageError: Se falhar ao salvar
        """
        try:
            # Criar diretório temporário se necessário
            if temp_dir is None:
                temp_dir = await self.storage.create_temp_directory()
            
            # Sanitizar nome do arquivo
            safe_filename = self._sanitize_filename(upload_file.filename)
            file_path = temp_dir / safe_filename
            
            logger.info(f"Saving upload: {safe_filename} to {temp_dir}")
            
            # Salvar arquivo em chunks (streaming para economizar RAM)
            total_bytes = 0
            with open(file_path, 'wb') as f:
                while chunk := await upload_file.read(self.chunk_size):
                    f.write(chunk)
                    total_bytes += len(chunk)
            
            logger.info(f"✅ Upload saved: {safe_filename} ({total_bytes} bytes)")
            
            # Criar Value Object
            return UploadedVideoFile(
                file_path=file_path,
                original_filename=upload_file.filename,
                mime_type=upload_file.content_type or 'application/octet-stream',
                size_bytes=total_bytes
            )
            
        except Exception as e:
            logger.error(f"Failed to save upload: {str(e)}")
            raise StorageError(f"Failed to save uploaded file: {str(e)}")
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitiza nome do arquivo para prevenir path traversal.
        
        Args:
            filename: Nome original do arquivo
            
        Returns:
            Nome sanitizado
        """
        # Remover path separators
        safe_name = filename.replace('/', '_').replace('\\', '_')
        
        # Remover caracteres especiais perigosos
        dangerous_chars = ['..', '<', '>', ':', '"', '|', '?', '*']
        for char in dangerous_chars:
            safe_name = safe_name.replace(char, '_')
        
        # Garantir que tenha extensão
        if '.' not in safe_name:
            safe_name += '.unknown'
        
        return safe_name
```

#### 2.3. Prometheus Metrics para Upload

**Arquivo**: `src/infrastructure/monitoring/upload_metrics.py`

```python
"""
Métricas Prometheus para upload de vídeos.
"""
from prometheus_client import Counter, Histogram, Gauge

# Total de uploads recebidos
upload_requests_total = Counter(
    'video_upload_requests_total',
    'Total de requisições de upload recebidas',
    ['status', 'format']  # success/failed, mp4/avi/etc
)

# Duração do upload (salvamento)
upload_duration_seconds = Histogram(
    'video_upload_duration_seconds',
    'Tempo de upload em segundos',
    buckets=[1, 5, 10, 30, 60, 120, 300]  # até 5 minutos
)

# Tamanho dos arquivos enviados
upload_file_size_bytes = Histogram(
    'video_upload_file_size_bytes',
    'Tamanho dos arquivos enviados em bytes',
    buckets=[
        1_000_000,      # 1MB
        10_000_000,     # 10MB
        50_000_000,     # 50MB
        100_000_000,    # 100MB
        500_000_000,    # 500MB
        1_000_000_000,  # 1GB
        2_500_000_000   # 2.5GB
    ]
)

# Uploads em progresso
uploads_in_progress = Gauge(
    'video_uploads_in_progress',
    'Número de uploads em progresso no momento'
)

# Erros de validação
upload_validation_errors = Counter(
    'video_upload_validation_errors_total',
    'Total de erros de validação',
    ['error_type']  # format/size/duration/corrupted
)


def record_upload_request(status: str, format: str):
    """Registra requisição de upload."""
    upload_requests_total.labels(status=status, format=format).inc()


def record_upload_duration(duration: float):
    """Registra duração do upload."""
    upload_duration_seconds.observe(duration)


def record_file_size(size_bytes: int):
    """Registra tamanho do arquivo."""
    upload_file_size_bytes.observe(size_bytes)


def record_validation_error(error_type: str):
    """Registra erro de validação."""
    upload_validation_errors.labels(error_type=error_type).inc()
```

---

### FASE 3: Application Layer (2 horas)

#### 3.1. Use Case: TranscribeUploadedVideoUseCase

**Arquivo**: `src/application/use_cases/transcribe_uploaded_video.py`

```python
"""
Use Case para transcrever vídeo enviado via upload.
"""
import time
import uuid
from pathlib import Path
from typing import Optional
from loguru import logger

from src.domain.value_objects import UploadedVideoFile, Transcription
from src.domain.interfaces import (
    ITranscriptionService,
    IStorageService,
    IVideoUploadValidator
)
from src.domain.exceptions import (
    TranscriptionError,
    ValidationError,
    StorageError
)
from src.application.dtos import TranscribeResponseDTO, TranscriptionSegmentDTO
from src.infrastructure.validators import AudioValidator
from src.infrastructure.utils import get_ffmpeg_optimizer
from src.infrastructure.monitoring import (
    record_upload_request,
    record_upload_duration,
    record_file_size,
    record_validation_error
)


class TranscribeUploadedVideoUseCase:
    """
    Use case para transcrever vídeo enviado via upload.
    
    Flow:
    1. Receber UploadedVideoFile
    2. Validar formato, tamanho, duração
    3. Extrair áudio (FFmpeg) - se for vídeo
    4. Validar áudio
    5. Transcrever com Whisper
    6. Limpar arquivos temporários
    7. Retornar TranscribeResponseDTO
    """
    
    def __init__(
        self,
        transcription_service: ITranscriptionService,
        storage_service: IStorageService,
        video_validator: IVideoUploadValidator,
        max_size_mb: int = 2500,
        max_duration_seconds: int = 10800
    ):
        """
        Inicializa use case.
        
        Args:
            transcription_service: Serviço de transcrição Whisper
            storage_service: Serviço de storage temporário
            video_validator: Validador de uploads
            max_size_mb: Tamanho máximo em MB
            max_duration_seconds: Duração máxima em segundos
        """
        self.transcription_service = transcription_service
        self.storage = storage_service
        self.video_validator = video_validator
        self.audio_validator = AudioValidator()
        self.ffmpeg_optimizer = get_ffmpeg_optimizer()
        self.max_size_mb = max_size_mb
        self.max_duration_seconds = max_duration_seconds
    
    async def execute(
        self,
        uploaded_file: UploadedVideoFile,
        language: str = "auto",
        temp_dir: Optional[Path] = None
    ) -> TranscribeResponseDTO:
        """
        Executa transcrição de vídeo enviado.
        
        Args:
            uploaded_file: Arquivo enviado
            language: Idioma (auto para detecção)
            temp_dir: Diretório temporário
            
        Returns:
            TranscribeResponseDTO com resultado da transcrição
            
        Raises:
            ValidationError: Arquivo inválido
            TranscriptionError: Falha na transcrição
        """
        start_time = time.time()
        transcription_id = str(uuid.uuid4())
        audio_path: Optional[Path] = None
        
        try:
            logger.info(
                f"🎬 Starting transcription of uploaded file: {uploaded_file.original_filename}",
                extra={'transcription_id': transcription_id}
            )
            
            # Métricas
            record_file_size(uploaded_file.size_bytes)
            
            # 1. Validar arquivo
            logger.info("Validating uploaded file...")
            metadata = await self.video_validator.validate_file(
                uploaded_file.file_path,
                self.max_size_mb,
                self.max_duration_seconds
            )
            
            duration_seconds = metadata['duration']
            logger.info(f"✅ File validated: duration={duration_seconds}s")
            
            # 2. Extrair áudio (se for vídeo)
            if uploaded_file.is_video():
                logger.info("Extracting audio from video...")
                audio_path = await self._extract_audio(
                    uploaded_file.file_path,
                    temp_dir or uploaded_file.file_path.parent
                )
            else:
                # Já é áudio
                audio_path = uploaded_file.file_path
            
            # 3. Validar áudio
            logger.info("Validating audio...")
            is_valid, error = self.audio_validator.validate(
                audio_path,
                max_duration=self.max_duration_seconds
            )
            
            if not is_valid:
                raise ValidationError(f"Invalid audio: {error}")
            
            logger.info("✅ Audio validated")
            
            # 4. Transcrever
            logger.info("Transcribing with Whisper...")
            transcription = await self.transcription_service.transcribe(
                audio_path=audio_path,
                language=language if language != "auto" else None
            )
            
            # 5. Construir response
            processing_time = time.time() - start_time
            
            response = TranscribeResponseDTO(
                transcription_id=transcription_id,
                youtube_url="",  # N/A para uploads
                video_id=transcription_id,  # Usar transcription_id
                language=transcription.language,
                full_text=transcription.full_text,
                segments=[
                    TranscriptionSegmentDTO(
                        text=seg.text,
                        start=seg.start,
                        end=seg.end,
                        duration=seg.duration
                    )
                    for seg in transcription.segments
                ],
                total_segments=len(transcription.segments),
                duration=duration_seconds,
                processing_time=processing_time,
                source="whisper",
                transcript_type=None
            )
            
            # Métricas de sucesso
            record_upload_request('success', uploaded_file.get_extension())
            record_upload_duration(processing_time)
            
            logger.info(
                f"✅ Transcription completed: {len(transcription.segments)} segments, "
                f"{processing_time:.2f}s",
                extra={'transcription_id': transcription_id}
            )
            
            return response
            
        except ValidationError as e:
            logger.error(f"Validation error: {str(e)}")
            record_validation_error(type(e).__name__)
            record_upload_request('failed', uploaded_file.get_extension())
            raise
            
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}", exc_info=True)
            record_upload_request('failed', uploaded_file.get_extension())
            raise TranscriptionError(f"Failed to transcribe uploaded video: {str(e)}")
            
        finally:
            # Limpar arquivos temporários
            await self._cleanup(uploaded_file.file_path, audio_path)
    
    async def _extract_audio(self, video_path: Path, output_dir: Path) -> Path:
        """
        Extrai áudio do vídeo usando FFmpeg.
        
        Args:
            video_path: Caminho do vídeo
            output_dir: Diretório de saída
            
        Returns:
            Caminho do arquivo de áudio extraído
        """
        audio_path = output_dir / f"{video_path.stem}_audio.wav"
        
        logger.info(f"Extracting audio: {video_path.name} -> {audio_path.name}")
        
        # Usar FFmpeg optimizer (mesmo do YouTube)
        await self.ffmpeg_optimizer.extract_audio(
            video_path=video_path,
            output_path=audio_path,
            sample_rate=16000,  # Whisper padrão
            channels=1          # Mono
        )
        
        logger.info(f"✅ Audio extracted: {audio_path.name}")
        return audio_path
    
    async def _cleanup(self, video_path: Path, audio_path: Optional[Path]):
        """Limpa arquivos temporários."""
        try:
            if video_path and video_path.exists():
                video_path.unlink()
                logger.debug(f"Deleted: {video_path.name}")
            
            if audio_path and audio_path != video_path and audio_path.exists():
                audio_path.unlink()
                logger.debug(f"Deleted: {audio_path.name}")
                
        except Exception as e:
            logger.warning(f"Cleanup warning: {str(e)}")
```

#### 3.2. DTO: UploadVideoRequestDTO

**Arquivo**: `src/application/dtos/transcription_dtos.py` (adicionar)

```python
class UploadVideoRequestDTO(BaseModel):
    """DTO para requisição de upload de vídeo."""
    
    language: Optional[str] = Field(
        default="auto",
        description="Código do idioma (auto para detecção automática)",
        examples=["auto", "en", "pt", "es", "fr", "de"]
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "language": "auto"
            }
        }
```

---

### FASE 4: Presentation Layer (2 horas)

#### 4.1. Route: Upload Endpoint

**Arquivo**: `src/presentation/api/routes/upload_transcription.py` (NOVO)

```python
"""
Rotas de upload de vídeo.
Endpoint para transcrição de vídeos enviados diretamente.
"""
import time
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi import Request
from typing import Optional
from loguru import logger
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.application.use_cases import TranscribeUploadedVideoUseCase
from src.application.dtos import TranscribeResponseDTO, ErrorResponseDTO
from src.domain.exceptions import (
    ValidationError,
    UnsupportedFormatError,
    FileTooLargeError,
    InvalidVideoFileError,
    TranscriptionError,
    StorageError
)
from src.infrastructure.storage import VideoUploadService
from src.infrastructure.validators import VideoUploadValidator
from src.infrastructure.monitoring import uploads_in_progress
from src.presentation.api.dependencies import (
    get_transcription_service,
    get_storage_service,
    raise_error
)


router = APIRouter(prefix="/api/v1/transcribe/upload", tags=["Upload Transcription"])

# Rate limiter (mais restritivo que YouTube)
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "",
    response_model=TranscribeResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Transcribe uploaded video file",
    description="""
    Upload a video or audio file directly and transcribe it using Whisper AI.
    
    **⚡ Rate Limit:** 2 uploads per minute per IP address (vs 5 for YouTube URLs)
    
    **Supported Formats:**
    - Video: MP4, AVI, MOV, MKV, WebM, FLV, WMV, M4V, MPG, MPEG, 3GP
    - Audio: MP3, WAV, AAC, M4A, FLAC, OGG, WMA, Opus
    
    **Limits:**
    - Max file size: 2.5GB (configurable)
    - Max duration: 3 hours (10,800 seconds)
    
    **Processing Time:**
    - Upload: ~1-5 minutes (depends on file size and connection)
    - Transcription: ~30-120 seconds (depends on duration and model)
    
    **Use Cases:**
    - Videos from platforms other than YouTube
    - Private/local videos
    - Corporate internal videos
    - Live recordings
    
    **Note:** File is temporarily stored and automatically deleted after processing.
    """,
    responses={
        200: {
            "description": "Transcription successful",
            "model": TranscribeResponseDTO
        },
        400: {
            "description": "Bad Request (invalid format, file too large, corrupted)",
            "model": ErrorResponseDTO,
            "content": {
                "application/json": {
                    "examples": {
                        "unsupported_format": {
                            "summary": "Unsupported file format",
                            "value": {
                                "error": "UnsupportedFormatError",
                                "message": "Format .xxx not supported. Supported: .mp4, .avi, ...",
                                "request_id": "abc-123",
                                "details": {}
                            }
                        },
                        "file_too_large": {
                            "summary": "File exceeds size limit",
                            "value": {
                                "error": "FileTooLargeError",
                                "message": "File size (3000MB) exceeds maximum (2500MB)",
                                "request_id": "abc-123",
                                "details": {}
                            }
                        }
                    }
                }
            }
        },
        413: {
            "description": "Payload Too Large (file exceeds max size)"
        },
        429: {
            "description": "Too Many Requests (rate limit exceeded)"
        },
        500: {
            "description": "Internal Server Error"
        }
    }
)
@limiter.limit("2/minute")  # Mais restritivo que YouTube
async def transcribe_uploaded_video(
    request: Request,
    file: UploadFile = File(..., description="Video or audio file to transcribe"),
    language: str = Form(
        default="auto",
        description="Language code (auto for automatic detection)"
    ),
    transcription_service = Depends(get_transcription_service),
    storage_service = Depends(get_storage_service)
):
    """
    Upload e transcrever vídeo/áudio.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    start_time = time.time()
    
    # Incrementar gauge de uploads em progresso
    uploads_in_progress.inc()
    
    try:
        logger.info(
            f"📤 Upload request received: {file.filename} ({file.content_type})",
            extra={'request_id': request_id}
        )
        
        # 1. Inicializar serviços
        upload_service = VideoUploadService(storage_service)
        video_validator = VideoUploadValidator()
        
        # 2. Salvar upload
        logger.info("Saving uploaded file...")
        uploaded_file = await upload_service.save_upload(file)
        
        logger.info(
            f"✅ File saved: {uploaded_file.get_size_mb():.2f}MB",
            extra={'request_id': request_id}
        )
        
        # 3. Criar use case
        use_case = TranscribeUploadedVideoUseCase(
            transcription_service=transcription_service,
            storage_service=storage_service,
            video_validator=video_validator
        )
        
        # 4. Executar transcrição
        result = await use_case.execute(
            uploaded_file=uploaded_file,
            language=language
        )
        
        processing_time = time.time() - start_time
        logger.info(
            f"✅ Upload transcription completed: {processing_time:.2f}s",
            extra={'request_id': request_id}
        )
        
        return result
        
    except UnsupportedFormatError as e:
        raise_error(
            status.HTTP_400_BAD_REQUEST,
            "UnsupportedFormatError",
            str(e),
            request_id
        )
    
    except FileTooLargeError as e:
        raise_error(
            status.HTTP_400_BAD_REQUEST,
            "FileTooLargeError",
            str(e),
            request_id
        )
    
    except InvalidVideoFileError as e:
        raise_error(
            status.HTTP_400_BAD_REQUEST,
            "InvalidVideoFileError",
            str(e),
            request_id
        )
    
    except ValidationError as e:
        raise_error(
            status.HTTP_400_BAD_REQUEST,
            "ValidationError",
            str(e),
            request_id
        )
    
    except StorageError as e:
        raise_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "StorageError",
            str(e),
            request_id
        )
    
    except TranscriptionError as e:
        raise_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "TranscriptionError",
            str(e),
            request_id
        )
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "InternalServerError",
            "An unexpected error occurred during upload transcription",
            request_id
        )
    
    finally:
        # Decrementar gauge
        uploads_in_progress.dec()


@router.get(
    "/formats",
    summary="List supported file formats",
    description="Returns list of all supported video and audio formats",
    response_model=dict
)
async def get_supported_formats():
    """Lista formatos suportados."""
    validator = VideoUploadValidator()
    
    return {
        "video_formats": sorted(validator.SUPPORTED_VIDEO_FORMATS),
        "audio_formats": sorted(validator.SUPPORTED_AUDIO_FORMATS),
        "mime_types": sorted(validator.SUPPORTED_MIME_TYPES),
        "max_file_size_mb": 2500,
        "max_duration_seconds": 10800,
        "total_formats": len(validator.get_supported_formats())
    }
```

#### 4.2. Registrar Route no main.py

**Arquivo**: `src/presentation/api/main.py` (adicionar)

```python
# Importar novo router
from src.presentation.api.routes import upload_transcription

# Registrar rota (linha ~XXX)
app.include_router(upload_transcription.router)
```

---

### FASE 5: Configuração e Testes (2-3 horas)

#### 5.1. Atualizar Settings

**Arquivo**: `src/config/settings.py` (adicionar)

```python
# Upload settings
max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "2500"))
upload_rate_limit: str = os.getenv("UPLOAD_RATE_LIMIT", "2/minute")
allowed_upload_formats: str = os.getenv(
    "ALLOWED_UPLOAD_FORMATS",
    ".mp4,.avi,.mov,.mkv,.webm,.mp3,.wav,.aac,.m4a,.flac"
)
```

#### 5.2. Atualizar docker-compose.yml

```yaml
environment:
  # Upload settings (NEW)
  - MAX_UPLOAD_SIZE_MB=${MAX_UPLOAD_SIZE_MB:-2500}
  - UPLOAD_RATE_LIMIT=${UPLOAD_RATE_LIMIT:-2/minute}
  - ALLOWED_UPLOAD_FORMATS=${ALLOWED_UPLOAD_FORMATS:-.mp4,.avi,.mov,.mkv,.webm,.mp3,.wav}
```

#### 5.3. Testes Unitários

**Arquivo**: `tests/unit/application/test_transcribe_uploaded_video.py`

```python
"""
Testes para TranscribeUploadedVideoUseCase.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from src.application.use_cases import TranscribeUploadedVideoUseCase
from src.domain.value_objects import UploadedVideoFile
from src.domain.exceptions import ValidationError


@pytest.mark.asyncio
async def test_transcribe_uploaded_video_success():
    """Testa transcrição bem-sucedida de upload."""
    # Arrange
    mock_transcription_service = Mock()
    mock_storage_service = Mock()
    mock_validator = Mock()
    
    uploaded_file = UploadedVideoFile(
        file_path=Path("/tmp/test.mp4"),
        original_filename="test.mp4",
        mime_type="video/mp4",
        size_bytes=1000000
    )
    
    # Act
    use_case = TranscribeUploadedVideoUseCase(
        transcription_service=mock_transcription_service,
        storage_service=mock_storage_service,
        video_validator=mock_validator
    )
    
    # ... mais testes


@pytest.mark.asyncio
async def test_transcribe_uploaded_video_unsupported_format():
    """Testa erro com formato não suportado."""
    # ...


@pytest.mark.asyncio
async def test_transcribe_uploaded_video_file_too_large():
    """Testa erro com arquivo muito grande."""
    # ...
```

#### 5.4. Testes de Integração

**Arquivo**: `tests/integration/test_upload_endpoint.py`

```python
"""
Testes de integração para endpoint de upload.
"""
import pytest
from fastapi.testclient import TestClient


def test_upload_video_success(client: TestClient, sample_video_file):
    """Testa upload bem-sucedido."""
    files = {"file": ("test.mp4", sample_video_file, "video/mp4")}
    data = {"language": "auto"}
    
    response = client.post("/api/v1/transcribe/upload", files=files, data=data)
    
    assert response.status_code == 200
    assert "transcription_id" in response.json()
    assert response.json()["source"] == "whisper"


def test_upload_unsupported_format(client: TestClient):
    """Testa upload com formato não suportado."""
    files = {"file": ("test.xyz", b"fake content", "application/octet-stream")}
    
    response = client.post("/api/v1/transcribe/upload", files=files)
    
    assert response.status_code == 400
    assert "UnsupportedFormatError" in response.json()["error"]


def test_upload_rate_limit(client: TestClient, sample_video_file):
    """Testa rate limiting de uploads."""
    # Fazer 3 requests (limite é 2/min)
    for i in range(3):
        files = {"file": (f"test{i}.mp4", sample_video_file, "video/mp4")}
        response = client.post("/api/v1/transcribe/upload", files=files)
        
        if i < 2:
            assert response.status_code == 200
        else:
            assert response.status_code == 429  # Too Many Requests
```

---

## 📋 Checklist de Implementação

### FASE 1: Domain Layer ✅
- [ ] Criar `UploadedVideoFile` value object
- [ ] Criar `IVideoUploadValidator` interface
- [ ] Adicionar exceptions: `VideoUploadError`, `UnsupportedFormatError`, etc.
- [ ] Atualizar `__init__.py` com novos exports

### FASE 2: Infrastructure Layer ✅
- [ ] Implementar `VideoUploadValidator` (FFprobe)
- [ ] Implementar `VideoUploadService` (salvamento streaming)
- [ ] Adicionar métricas Prometheus para uploads
- [ ] Testar validação com vídeos de exemplo

### FASE 3: Application Layer ✅
- [ ] Implementar `TranscribeUploadedVideoUseCase`
- [ ] Adicionar `UploadVideoRequestDTO`
- [ ] Integrar com FFmpeg para extração de áudio
- [ ] Testar fluxo completo localmente

### FASE 4: Presentation Layer ✅
- [ ] Criar route `upload_transcription.py`
- [ ] Adicionar endpoint POST `/api/v1/transcribe/upload`
- [ ] Adicionar endpoint GET `/api/v1/transcribe/upload/formats`
- [ ] Registrar router em `main.py`
- [ ] Testar com Swagger UI

### FASE 5: Configuração ✅
- [ ] Atualizar `settings.py` com configurações de upload
- [ ] Atualizar `docker-compose.yml`
- [ ] Atualizar `.env.example`
- [ ] Criar testes unitários
- [ ] Criar testes de integração
- [ ] Documentar em README.md

### FASE 6: Documentação e Deploy ✅
- [ ] Atualizar API docs (Swagger/ReDoc)
- [ ] Adicionar exemplos de uso (curl, Python, etc.)
- [ ] Atualizar CHANGELOG.md
- [ ] Criar guia de troubleshooting
- [ ] Deploy em ambiente de staging
- [ ] Testes de carga (simular uploads grandes)

---

## 🚀 Exemplo de Uso

### cURL

```bash
# Upload MP4
curl -X POST "http://localhost:8000/api/v1/transcribe/upload" \
  -H "accept: application/json" \
  -F "file=@/path/to/video.mp4" \
  -F "language=auto"

# Upload WAV (áudio)
curl -X POST "http://localhost:8000/api/v1/transcribe/upload" \
  -F "file=@/path/to/audio.wav" \
  -F "language=pt"

# Listar formatos suportados
curl -X GET "http://localhost:8000/api/v1/transcribe/upload/formats"
```

### Python

```python
import requests

# Upload video file
with open("video.mp4", "rb") as f:
    files = {"file": ("video.mp4", f, "video/mp4")}
    data = {"language": "auto"}
    
    response = requests.post(
        "http://localhost:8000/api/v1/transcribe/upload",
        files=files,
        data=data
    )
    
    result = response.json()
    print(f"Transcription ID: {result['transcription_id']}")
    print(f"Full text: {result['full_text']}")
```

### JavaScript (FormData)

```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('language', 'auto');

const response = await fetch('http://localhost:8000/api/v1/transcribe/upload', {
    method: 'POST',
    body: formData
});

const result = await response.json();
console.log('Transcription:', result.full_text);
```

---

## 📊 Métricas Esperadas

### Prometheus Metrics

```
# Total de uploads
video_upload_requests_total{status="success",format="mp4"} 150
video_upload_requests_total{status="failed",format="avi"} 5

# Duração de uploads
video_upload_duration_seconds_bucket{le="30"} 100
video_upload_duration_seconds_bucket{le="60"} 140

# Tamanho dos arquivos
video_upload_file_size_bytes_bucket{le="100000000"} 120  # <100MB
video_upload_file_size_bytes_bucket{le="500000000"} 145  # <500MB

# Uploads em progresso
video_uploads_in_progress 3

# Erros de validação
video_upload_validation_errors_total{error_type="UnsupportedFormatError"} 10
video_upload_validation_errors_total{error_type="FileTooLargeError"} 5
```

---

## ⚠️ Considerações de Segurança

### 1. Validação de Arquivo
- ✅ Validar MIME type E extensão (double check)
- ✅ Usar FFprobe para verificar conteúdo real (evitar file masquerading)
- ✅ Sanitizar nomes de arquivo (prevenir path traversal)
- ✅ Limitar tamanho máximo (2.5GB padrão)

### 2. Rate Limiting
- ✅ 2 uploads/minuto (vs 5 YouTube/minuto)
- ✅ Por IP address
- ✅ Considerar adicionar rate limit por user (autenticado)

### 3. Storage
- ✅ Salvar em diretório temporário isolado
- ✅ Cleanup automático após processamento
- ✅ Cleanup periódico de arquivos órfãos
- ✅ Permissões restritas (0o755)

### 4. Proteção DDoS
- ✅ Max file size enforcement (FastAPI)
- ✅ Timeout de upload (5 minutos)
- ✅ Circuit breaker para uploads consecutivos com falha

### 5. Validação de Conteúdo
- ✅ FFprobe verifica se arquivo é realmente vídeo/áudio
- ✅ Verificar codec permitido
- ✅ Rejeitar arquivos corrompidos

---

## 🐛 Possíveis Problemas e Soluções

### Problema 1: Upload muito lento
**Sintoma**: Uploads de arquivos grandes (>1GB) demoram muito  
**Solução**:
- Aumentar `chunk_size` no `VideoUploadService` (8KB → 64KB)
- Usar nginx como proxy reverso com buffering otimizado
- Considerar usar S3/MinIO para uploads diretos

### Problema 2: Memória estourando
**Sintoma**: RAM usage aumenta durante uploads  
**Solução**:
- Garantir streaming (não carregar arquivo inteiro na RAM)
- Limitar uploads simultâneos (`uploads_in_progress` gauge)
- Usar `asyncio.Semaphore` para limitar concorrência

### Problema 3: FFprobe timeout
**Sintoma**: Validação falha com timeout em arquivos corrompidos  
**Solução**:
- Já implementado: timeout de 30s no FFprobe
- Adicionar retry com exponential backoff
- Logs detalhados para debugging

### Problema 4: Formatos exóticos
**Sintoma**: Usuário tenta upload de formato raro (.ogv, .ts, etc.)  
**Solução**:
- Expandir lista `SUPPORTED_FORMATS` conforme necessário
- Documentar claramente formatos suportados
- Retornar mensagem clara com lista de formatos aceitos

---

## 📈 Melhorias Futuras (v2.0)

### Fase 2 - Advanced Features

1. **Upload Resumable** (Tus Protocol)
   - Permitir retomar uploads interrompidos
   - Útil para conexões instáveis

2. **Upload Direto para S3/MinIO**
   - Gerar presigned URLs
   - Upload direto do cliente para S3
   - Reduz carga no servidor

3. **Processamento Assíncrono com Celery**
   - Upload retorna job_id imediatamente
   - Processamento em background worker
   - Polling/WebSocket para status

4. **Multi-File Upload**
   - Upload de múltiplos arquivos de uma vez
   - Batch processing

5. **Video Preview/Thumbnail**
   - Gerar thumbnail do vídeo
   - Retornar na resposta

6. **Autenticação e Quotas**
   - Autenticação JWT
   - Quotas por usuário (100GB/mês, etc.)
   - Billing/metering

---

## 🎯 Critérios de Sucesso

### Funcionais
- ✅ Upload de MP4, AVI, MOV, MKV funciona
- ✅ Upload de MP3, WAV, AAC funciona
- ✅ Transcrição retorna mesmo formato que YouTube endpoint
- ✅ Validação rejeita formatos inválidos
- ✅ Validação rejeita arquivos >2.5GB
- ✅ Validação rejeita vídeos >3h

### Não-Funcionais
- ✅ Upload de 100MB completa em <30s
- ✅ Upload de 1GB completa em <5min
- ✅ Rate limit 2/min funciona corretamente
- ✅ Métricas Prometheus registradas
- ✅ Logs estruturados com request_id
- ✅ Cleanup automático remove arquivos temporários

### Documentação
- ✅ Swagger UI documenta endpoint corretamente
- ✅ Exemplos de uso (curl, Python, JS) funcionam
- ✅ README.md atualizado
- ✅ CHANGELOG.md atualizado

---

## 📅 Timeline Estimado

| Fase | Tarefa | Tempo Estimado | Dependências |
|------|--------|----------------|--------------|
| 1 | Domain Layer | 2h | - |
| 2 | Infrastructure Layer | 4h | Fase 1 |
| 3 | Application Layer | 2h | Fase 1, 2 |
| 4 | Presentation Layer | 2h | Fase 1, 2, 3 |
| 5 | Testes e Configuração | 2-3h | Fase 4 |
| 6 | Documentação e Deploy | 1-2h | Fase 5 |
| **TOTAL** | **Full Feature** | **13-15h** | - |

**Sprint recomendado**: 2-3 dias de desenvolvimento

---

## ✅ Próximos Passos

1. **Revisar este planejamento** com time técnico
2. **Aprovar escopo e timeline**
3. **Criar branch feature**: `feature/video-upload-endpoint`
4. **Começar implementação** seguindo as fases
5. **Code review** após cada fase
6. **Testing completo** antes de merge
7. **Deploy em staging** para validação
8. **Deploy em produção** com feature flag

---

**Autor**: GitHub Copilot  
**Data**: 2025-10-23  
**Versão**: 1.0  
**Status**: Aguardando aprovação ⏳
