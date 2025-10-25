"""
Sistema de validação e segurança para Audio Transcriber
Validação de arquivos, rate limiting e middleware de segurança
"""
import asyncio
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict, deque

import magic
from fastapi import UploadFile, Request, HTTPException

from app.config import get_settings
from app.logging_config import get_logger, AuditLogger
from app.exceptions import ValidationError, SecurityError

logger = get_logger(__name__)
audit_logger = AuditLogger()


@dataclass
class ValidationResult:
    """Resultado da validação de arquivo"""
    valid: bool
    format: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None


@dataclass
class SecurityResult:
    """Resultado da verificação de segurança"""
    safe: bool
    reason: Optional[str] = None
    entropy: Optional[float] = None
    suspicious_patterns: List[str] = None


class FileValidator:
    """Validador de arquivos de áudio"""
    
    def __init__(self):
        self.settings = get_settings()
        self.supported_formats = self.settings.transcription.supported_formats
        self.max_file_size = self.settings.transcription.max_file_size_mb * 1024 * 1024
        self.max_duration = self.settings.transcription.max_audio_duration_minutes * 60
    
    def validate_file_format(self, file_path: Path) -> ValidationResult:
        """Valida formato e propriedades do arquivo"""
        try:
            if not file_path.exists():
                return ValidationResult(
                    valid=False,
                    error="File does not exist"
                )
            
            # Verifica tamanho
            file_size = file_path.stat().st_size
            if file_size > self.max_file_size:
                return ValidationResult(
                    valid=False,
                    size_bytes=file_size,
                    error=f"File too large: {file_size / (1024*1024):.1f}MB > {self.max_file_size / (1024*1024)}MB"
                )
            
            if file_size == 0:
                return ValidationResult(
                    valid=False,
                    size_bytes=0,
                    error="Empty file"
                )
            
            # Detecta MIME type usando magic bytes
            mime_type = magic.from_file(str(file_path), mime=True)
            
            # Verifica se é formato de áudio suportado
            audio_extensions = {
                'audio/mpeg': 'mp3',
                'audio/wav': 'wav',
                'audio/wave': 'wav',
                'audio/x-wav': 'wav',
                'audio/flac': 'flac',
                'audio/ogg': 'ogg',
                'audio/mp4': 'm4a',
                'audio/aac': 'aac',
                'audio/x-ms-wma': 'wma'
            }
            
            detected_format = audio_extensions.get(mime_type)
            if not detected_format or detected_format not in self.supported_formats:
                return ValidationResult(
                    valid=False,
                    mime_type=mime_type,
                    size_bytes=file_size,
                    error=f"Unsupported audio format: {mime_type}"
                )
            
            # Tenta obter duração do áudio
            duration = self._get_audio_duration(file_path)
            if duration and duration > self.max_duration:
                return ValidationResult(
                    valid=False,
                    format=detected_format,
                    mime_type=mime_type,
                    size_bytes=file_size,
                    duration_seconds=duration,
                    error=f"Audio too long: {duration/60:.1f}min > {self.max_duration/60}min"
                )
            
            return ValidationResult(
                valid=True,
                format=detected_format,
                mime_type=mime_type,
                size_bytes=file_size,
                duration_seconds=duration
            )
            
        except Exception as e:
            logger.error(f"File validation error: {e}")
            return ValidationResult(
                valid=False,
                error=f"Validation failed: {str(e)}"
            )
    
    def _get_audio_duration(self, file_path: Path) -> Optional[float]:
        """Obtém duração do áudio usando librosa"""
        try:
            import librosa
            duration = librosa.get_duration(filename=str(file_path))
            return duration
        except Exception as e:
            logger.debug(f"Could not get audio duration for {file_path}: {e}")
            return None


class SecurityChecker:
    """Verificador de segurança de arquivos"""
    
    def __init__(self):
        self.settings = get_settings()
        self.entropy_threshold = 7.5  # Threshold para detectar arquivos suspeitos
        self.max_sample_size = 8192   # Tamanho da amostra para análise
    
    async def check_file_security(self, file_path: Path) -> SecurityResult:
        """Verifica segurança do arquivo"""
        try:
            suspicious_patterns = []
            
            # Verifica entropia se habilitado
            entropy = None
            if self.settings.security.check_file_entropy:
                entropy = self._calculate_entropy(file_path)
                if entropy > self.entropy_threshold:
                    suspicious_patterns.append(f"High entropy: {entropy:.2f}")
            
            # Verifica magic bytes se habilitado
            if self.settings.security.check_file_magic_bytes:
                if not self._verify_magic_bytes(file_path):
                    suspicious_patterns.append("Invalid magic bytes for audio file")
            
            # Verifica padrões suspeitos no conteúdo
            if self._has_suspicious_content(file_path):
                suspicious_patterns.append("Suspicious content patterns detected")
            
            # Considera seguro se não há padrões suspeitos
            is_safe = len(suspicious_patterns) == 0
            
            return SecurityResult(
                safe=is_safe,
                reason="; ".join(suspicious_patterns) if suspicious_patterns else None,
                entropy=entropy,
                suspicious_patterns=suspicious_patterns
            )
            
        except Exception as e:
            logger.error(f"Security check error: {e}")
            return SecurityResult(
                safe=False,
                reason=f"Security check failed: {str(e)}"
            )
    
    def _calculate_entropy(self, file_path: Path) -> float:
        """Calcula entropia do arquivo"""
        import math
        from collections import Counter
        
        try:
            with open(file_path, 'rb') as f:
                # Lê amostra do arquivo
                data = f.read(self.max_sample_size)
                
            if not data:
                return 0.0
            
            # Conta frequência de bytes
            byte_counts = Counter(data)
            file_size = len(data)
            
            # Calcula entropia Shannon
            entropy = 0
            for count in byte_counts.values():
                probability = count / file_size
                entropy -= probability * math.log2(probability)
            
            return entropy
            
        except Exception:
            return 0.0
    
    def _verify_magic_bytes(self, file_path: Path) -> bool:
        """Verifica magic bytes para formatos de áudio"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(12)  # Lê primeiros 12 bytes
            
            # Magic bytes para formatos de áudio comuns
            audio_signatures = [
                b'\xff\xfb',           # MP3
                b'\xff\xf3',           # MP3
                b'\xff\xf2',           # MP3
                b'RIFF',               # WAV (RIFF header)
                b'fLaC',               # FLAC
                b'OggS',               # OGG
                b'\x00\x00\x00\x20ftypM4A',  # M4A
                b'\x00\x00\x00\x18ftypmp42', # MP4 audio
            ]
            
            return any(header.startswith(sig) for sig in audio_signatures)
            
        except Exception:
            return False
    
    def _has_suspicious_content(self, file_path: Path) -> bool:
        """Verifica padrões suspeitos no conteúdo"""
        try:
            with open(file_path, 'rb') as f:
                # Lê amostra do início e fim do arquivo
                start_data = f.read(1024)
                f.seek(-1024, 2)  # Vai para 1024 bytes antes do final
                end_data = f.read(1024)
            
            # Padrões suspeitos (executáveis, scripts)
            suspicious_patterns = [
                b'MZ',              # PE executable
                b'\x7fELF',         # ELF executable
                b'#!/bin/',         # Shell script
                b'<script',         # JavaScript
                b'<?php',           # PHP
                b'eval(',           # Eval functions
                b'exec(',           # Exec functions
            ]
            
            data_to_check = start_data + end_data
            return any(pattern in data_to_check for pattern in suspicious_patterns)
            
        except Exception:
            return False


class RateLimiter:
    """Rate limiter por IP com sliding window"""
    
    def __init__(self, max_requests: int = None, window_seconds: int = None):
        self.settings = get_settings()
        self.max_requests = max_requests or self.settings.security.rate_limit_requests
        self.window_seconds = window_seconds or self.settings.security.rate_limit_window
        
        # Armazenamento de requests por IP
        self._requests: Dict[str, deque] = defaultdict(deque)
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, client_ip: str) -> bool:
        """Verifica se request é permitido para o IP"""
        async with self._lock:
            now = time.time()
            
            # Remove requests antigas da janela
            if client_ip in self._requests:
                while (self._requests[client_ip] and 
                       now - self._requests[client_ip][0] > self.window_seconds):
                    self._requests[client_ip].popleft()
            
            # Verifica se ainda está dentro do limite
            if len(self._requests[client_ip]) >= self.max_requests:
                audit_logger.log_security_event(
                    event_type="rate_limit_exceeded",
                    severity="medium",
                    description=f"Rate limit exceeded for IP: {client_ip}",
                    client_ip=client_ip,
                    request_count=len(self._requests[client_ip])
                )
                return False
            
            # Adiciona nova request
            self._requests[client_ip].append(now)
            return True
    
    async def cleanup_old_entries(self):
        """Remove entradas antigas para economizar memória"""
        async with self._lock:
            now = time.time()
            
            for ip in list(self._requests.keys()):
                # Remove requests antigas
                while (self._requests[ip] and 
                       now - self._requests[ip][0] > self.window_seconds):
                    self._requests[ip].popleft()
                
                # Remove IP se não tem requests recentes
                if not self._requests[ip]:
                    del self._requests[ip]


class ValidationMiddleware:
    """Middleware para validação e segurança"""
    
    def __init__(self):
        self.file_validator = FileValidator()
        self.security_checker = SecurityChecker()
        self.rate_limiter = RateLimiter()
    
    async def validate_upload(
        self, 
        file: UploadFile, 
        client_ip: str
    ) -> Tuple[ValidationResult, SecurityResult]:
        """Valida upload de arquivo com segurança"""
        
        # Rate limiting
        if not await self.rate_limiter.is_allowed(client_ip):
            raise SecurityError(
                "Rate limit exceeded",
                error_code="RATE_LIMIT_EXCEEDED"
            )
        
        # Validação básica do upload
        if not file or not file.filename:
            raise ValidationError(
                "No file uploaded",
                error_code="NO_FILE"
            )
        
        # Cria arquivo temporário para validação
        from app.resource_manager import get_temp_file_manager
        temp_manager = get_temp_file_manager()
        
        with temp_manager.temp_file(suffix=Path(file.filename).suffix) as temp_path:
            # Salva conteúdo
            content = await file.read()
            temp_path.write_bytes(content)
            
            # Log do upload
            audit_logger.log_file_upload(
                file_name=file.filename,
                file_size=len(content),
                client_ip=client_ip
            )
            
            # Validação de formato
            file_result = self.file_validator.validate_file_format(temp_path)
            
            # Verificação de segurança
            security_result = await self.security_checker.check_file_security(temp_path)
            
            return file_result, security_result


# Instâncias globais
_validation_middleware: Optional[ValidationMiddleware] = None


def get_validation_middleware() -> ValidationMiddleware:
    """Obtém instância global do validation middleware"""
    global _validation_middleware
    if _validation_middleware is None:
        _validation_middleware = ValidationMiddleware()
    return _validation_middleware