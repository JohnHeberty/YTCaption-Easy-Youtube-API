"""
Advanced Input Validation

Validação abrangente com sanitization e regras de negócio.
Pattern: Data Transfer Object (DTO) com validação
"""

from pydantic import BaseModel, validator, Field
from typing import Optional, List
from pathlib import Path
from enum import Enum
import re
import logging

from ..core.constants import (
    ProcessingLimits,
    FileExtensions,
    AspectRatios,
    RegexPatterns
)

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Exceção de validação"""
    pass


class SubtitleStyle(str, Enum):
    """Estilos de legenda válidos"""
    STATIC = "static"
    DYNAMIC = "dynamic"
    MINIMAL = "minimal"


class LanguageCode(str, Enum):
    """Códigos de idioma suportados"""
    PT = "pt"
    EN = "en"
    ES = "es"
    FR = "fr"
    DE = "de"


class CreateVideoRequestValidated(BaseModel):
    """
    Request validado com regras de negócio
    
    Pattern: Data Transfer Object (DTO) com validação
    """
    
    query: str = Field(..., min_length=3, max_length=200, description="Search query for shorts")
    max_shorts: int = Field(..., ge=ProcessingLimits.MIN_SHORTS_COUNT, le=ProcessingLimits.MAX_SHORTS_COUNT, description="Maximum number of shorts to use")
    subtitle_language: LanguageCode = Field(default=LanguageCode.PT, description="Subtitle language")
    subtitle_style: SubtitleStyle = Field(default=SubtitleStyle.DYNAMIC, description="Subtitle style")
    aspect_ratio: str = Field(default=AspectRatios.VERTICAL.value, description="Video aspect ratio")
    
    @validator('query')
    def sanitize_query(cls, v: str) -> str:
        """
        Sanitiza query removendo caracteres perigosos
        
        Security: Previne injection attacks
        """
        # Remove caracteres não-alfanuméricos exceto espaços e hífens
        sanitized = re.sub(r'[^\w\s\-]', '', v)
        
        # Remove palavras proibidas (exemplo - expandir conforme necessário)
        forbidden_words = ['exec', 'eval', 'system', 'import', '__']
        for word in forbidden_words:
            sanitized = re.sub(fr'\b{word}\b', '', sanitized, flags=re.IGNORECASE)
        
        # Remove espaços múltiplos
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        if not sanitized:
            raise ValueError("Query cannot be empty after sanitization")
        
        return sanitized
    
    @validator('max_shorts')
    def validate_max_shorts(cls, v: int) -> int:
        """
        Valida max_shorts baseado em lógica de negócio
        
        Business Logic: Diferentes limites para diferentes tiers
        """
        # TODO: Implementar lógica de user tier quando houver autenticação
        # if user_tier == 'premium':
        #     return min(v, 100)
        # elif user_tier == 'free':
        #     return min(v, 20)
        
        return max(ProcessingLimits.MIN_SHORTS_COUNT, min(v, ProcessingLimits.MAX_SHORTS_COUNT))
    
    @validator('aspect_ratio')
    def validate_aspect_ratio(cls, v: str) -> str:
        """Valida formato de aspect ratio"""
        # Verificar se é um dos valores enum válidos
        valid_ratios = [ratio.value for ratio in AspectRatios]
        
        if v not in valid_ratios:
            raise ValueError(f"Invalid aspect ratio. Must be one of: {valid_ratios}")
        
        # Validar formato (X:Y)
        if not re.match(RegexPatterns.ASPECT_RATIO, v):
            raise ValueError("Aspect ratio must be in format X:Y (e.g., 9:16)")
        
        return v
    
    class Config:
        # Não permitir campos extras (security)
        extra = 'forbid'
        
        # Schema para documentação
        schema_extra = {
            "example": {
                "query": "funny cats",
                "max_shorts": 15,
                "subtitle_language": "pt",
                "subtitle_style": "dynamic",
                "aspect_ratio": "9:16"
            }
        }


class AudioFileValidator:
    """
    Validador de arquivo de áudio
    
    Pattern: Validator with multiple checks
    """
    
    @classmethod
    def validate(cls, file_path: Path) -> None:
        """
        Valida arquivo de áudio
        
        Raises:
            ValidationError: se arquivo inválido
        """
        # 1. Verificar existência
        if not file_path.exists():
            raise ValidationError(f"File not found: {file_path}")
        
        # 2. Verificar se é arquivo (não diretório)
        if not file_path.is_file():
            raise ValidationError(f"Path is not a file: {file_path}")
        
        # 3. Verificar extensão
        if file_path.suffix.lower() not in FileExtensions.AUDIO_FORMATS:
            raise ValidationError(
                f"Invalid audio format: {file_path.suffix}. "
                f"Supported: {', '.join(FileExtensions.AUDIO_FORMATS)}"
            )
        
        # 4. Verificar tamanho
        size_mb = file_path.stat().st_size / (1024 * 1024)
        
        MAX_FILE_SIZE_MB = 50
        MIN_FILE_SIZE_KB = 10
        
        if size_mb > MAX_FILE_SIZE_MB:
            raise ValidationError(
                f"File too large: {size_mb:.1f}MB (max {MAX_FILE_SIZE_MB}MB)"
            )
        
        if size_mb < MIN_FILE_SIZE_KB / 1024:
            raise ValidationError(
                f"File too small: {size_mb*1024:.1f}KB (min {MIN_FILE_SIZE_KB}KB)"
            )
        
        # 5. Verificar se é realmente áudio (magic bytes)
        cls._validate_file_type(file_path)
        
        logger.info(f"✅ Audio file validated: {file_path.name} ({size_mb:.1f}MB)")
    
    @classmethod
    def _validate_file_type(cls, file_path: Path):
        """
        Valida tipo real do arquivo via magic bytes
        
        Security: Previne upload de arquivos maliciosos com extensão falsa
        """
        try:
            with open(file_path, 'rb') as f:
                header = f.read(12)
            
            # Magic bytes para formatos de áudio comuns
            valid_signatures = [
                (b'\xFF\xFB', 'MP3'),           # MP3 (MPEG Audio Layer 3)
                (b'\xFF\xF3', 'MP3'),           # MP3 variant
                (b'\xFF\xF2', 'MP3'),           # MP3 variant
                (b'ID3', 'MP3'),                # MP3 with ID3 tag
                (b'RIFF', 'WAV'),               # WAV/RIFF
                (b'ftyp', 'M4A'),               # M4A/MP4
                (b'OggS', 'OGG'),               # OGG Vorbis
                (b'fLaC', 'FLAC'),              # FLAC
            ]
            
            for signature, format_name in valid_signatures:
                if header.startswith(signature):
                    logger.debug(f"Audio format detected: {format_name}")
                    return
            
            # Check especial para WAV (RIFF...WAVE)
            if header.startswith(b'RIFF') and b'WAVE' in header:
                logger.debug("Audio format detected: WAV")
                return
            
            raise ValidationError(
                f"File is not a valid audio file (invalid magic bytes). "
                f"Header: {header[:4].hex()}"
            )
        
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Failed to validate file type: {e}")


class VideoFileValidator:
    """Validador de arquivo de vídeo"""
    
    @classmethod
    def validate(cls, file_path: Path) -> None:
        """
        Valida arquivo de vídeo
        
        Raises:
            ValidationError: se arquivo inválido
        """
        # 1. Verificar existência
        if not file_path.exists():
            raise ValidationError(f"Video file not found: {file_path}")
        
        # 2. Verificar extensão
        if file_path.suffix.lower() not in FileExtensions.VIDEO_FORMATS:
            raise ValidationError(
                f"Invalid video format: {file_path.suffix}. "
                f"Supported: {', '.join(FileExtensions.VIDEO_FORMATS)}"
            )
        
        # 3. Verificar tamanho mínimo (vídeos muito pequenos provavelmente são inválidos)
        size_kb = file_path.stat().st_size / 1024
        
        if size_kb < 100:  # 100KB mínimo
            raise ValidationError(f"Video file too small: {size_kb:.1f}KB")
        
        logger.debug(f"✅ Video file validated: {file_path.name}")
    
    @classmethod
    def validate_with_ffprobe(cls, file_path: Path) -> dict:
        """
        Valida vídeo usando ffprobe (validação profunda)
        
        Returns:
            dict com metadata do vídeo
        """
        import subprocess
        import json
        
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name,width,height,duration,bit_rate',
                '-of', 'json',
                str(file_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                raise ValidationError(f"ffprobe failed: {result.stderr}")
            
            data = json.loads(result.stdout)
            
            if 'streams' not in data or not data['streams']:
                raise ValidationError("No video stream found")
            
            stream = data['streams'][0]
            
            # Validar resolução mínima
            width = stream.get('width', 0)
            height = stream.get('height', 0)
            
            if width < ProcessingLimits.MIN_VIDEO_RESOLUTION or height < ProcessingLimits.MIN_VIDEO_RESOLUTION:
                raise ValidationError(
                    f"Video resolution too low: {width}x{height} "
                    f"(min {ProcessingLimits.MIN_VIDEO_RESOLUTION}p)"
                )
            
            return {
                'codec': stream.get('codec_name'),
                'width': width,
                'height': height,
                'duration': float(stream.get('duration', 0)),
                'bit_rate': int(stream.get('bit_rate', 0))
            }
        
        except subprocess.TimeoutExpired:
            raise ValidationError("ffprobe timeout")
        except json.JSONDecodeError:
            raise ValidationError("Failed to parse ffprobe output")
        except Exception as e:
            raise ValidationError(f"Failed to validate video: {e}")


class JobIdValidator:
    """Validador de Job ID"""
    
    @classmethod
    def validate(cls, job_id: str) -> None:
        """
        Valida formato de Job ID
        
        Job IDs são gerados por shortuuid (22 caracteres alfanuméricos)
        """
        if not job_id:
            raise ValidationError("Job ID cannot be empty")
        
        if not re.match(RegexPatterns.JOB_ID, job_id):
            raise ValidationError(f"Invalid Job ID format: {job_id}")
    
    @classmethod
    def is_valid(cls, job_id: str) -> bool:
        """Retorna True se job_id é válido"""
        try:
            cls.validate(job_id)
            return True
        except ValidationError:
            return False


class QueryValidator:
    """Validador de queries de busca"""
    
    # Palavras proibidas (expandir conforme necessário)
    FORBIDDEN_WORDS = {
        'exec', 'eval', 'system', 'import', '__import__',
        'shell', 'chmod', 'sudo', 'rm -rf',
        'drop', 'delete', 'truncate',  # SQL keywords
    }
    
    # Caracteres perigosos
    DANGEROUS_CHARS = ['<', '>', '|', '&', ';', '`', '$', '(', ')']
    
    @classmethod
    def sanitize(cls, query: str) -> str:
        """
        Sanitiza query de busca
        
        Args:
            query: Query original
        
        Returns:
            Query sanitizada
        """
        if not query:
            raise ValidationError("Query cannot be empty")
        
        # 1. Remove leading/trailing whitespace
        query = query.strip()
        
        # 2. Remove caracteres perigosos
        for char in cls.DANGEROUS_CHARS:
            query = query.replace(char, '')
        
        # 3. Remove palavras proibidas
        words = query.lower().split()
        sanitized_words = [w for w in words if w not in cls.FORBIDDEN_WORDS]
        query = ' '.join(sanitized_words)
        
        # 4. Remove espaços múltiplos
        query = re.sub(r'\s+', ' ', query).strip()
        
        # 5. Limitar tamanho
        if len(query) > 200:
            query = query[:200]
        
        if not query:
            raise ValidationError("Query is empty after sanitization")
        
        return query
    
    @classmethod
    def validate(cls, query: str) -> None:
        """
        Valida query
        
        Raises:
            ValidationError: se query inválida
        """
        if not query:
            raise ValidationError("Query cannot be empty")
        
        if len(query) < 3:
            raise ValidationError("Query too short (min 3 characters)")
        
        if len(query) > 200:
            raise ValidationError("Query too long (max 200 characters)")
        
        # Verificar se contém palavras proibidas
        words = query.lower().split()
        forbidden_found = [w for w in words if w in cls.FORBIDDEN_WORDS]
        
        if forbidden_found:
            raise ValidationError(f"Query contains forbidden words: {', '.join(forbidden_found)}")
        
        # Verificar caracteres perigosos
        dangerous_found = [c for c in cls.DANGEROUS_CHARS if c in query]
        
        if dangerous_found:
            raise ValidationError(f"Query contains dangerous characters: {', '.join(dangerous_found)}")


# Funções helper para uso direto

def validate_audio_file(file_path: Path) -> None:
    """Helper: Valida arquivo de áudio"""
    AudioFileValidator.validate(file_path)


def validate_video_file(file_path: Path) -> None:
    """Helper: Valida arquivo de vídeo"""
    VideoFileValidator.validate(file_path)


def validate_job_id(job_id: str) -> None:
    """Helper: Valida Job ID"""
    JobIdValidator.validate(job_id)


def sanitize_query(query: str) -> str:
    """Helper: Sanitiza query"""
    return QueryValidator.sanitize(query)
