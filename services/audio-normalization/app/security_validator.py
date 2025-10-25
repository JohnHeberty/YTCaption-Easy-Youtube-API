"""
Sistema robusto de validação e segurança para uploads de áudio
"""
import os
import mimetypes
import hashlib
import math
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict, deque
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import UploadFile, Request
from pydub import AudioSegment

from .config import get_settings
from .exceptions import (
    ValidationError, 
    FileValidationError, 
    AudioFormatError,
    FileTooLargeError,
    SecurityError,
    SuspiciousFileError,
    RateLimitExceededError
)
from .logging_config import get_audit_logger

logger = logging.getLogger(__name__)
audit_logger = get_audit_logger()


@dataclass
class FileValidationResult:
    """Resultado da validação de arquivo"""
    valid: bool
    filename: str
    size_bytes: int
    format: Optional[str] = None
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    bitrate: Optional[str] = None
    errors: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


@dataclass
class SecurityCheckResult:
    """Resultado da verificação de segurança"""
    safe: bool
    threats_detected: List[str] = None
    entropy_score: Optional[float] = None
    suspicious_patterns: List[str] = None
    
    def __post_init__(self):
        if self.threats_detected is None:
            self.threats_detected = []
        if self.suspicious_patterns is None:
            self.suspicious_patterns = []


class RateLimiter:
    """Rate limiter baseado em sliding window"""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(deque)
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, client_id: str) -> bool:
        """Verifica se request é permitida"""
        async with self._lock:
            now = time.time()
            client_requests = self.requests[client_id]
            
            # Remove requests antigas da janela
            while client_requests and client_requests[0] <= now - self.window_seconds:
                client_requests.popleft()
            
            # Verifica limite
            if len(client_requests) >= self.max_requests:
                return False
            
            # Adiciona request atual
            client_requests.append(now)
            return True
    
    async def get_remaining_requests(self, client_id: str) -> int:
        """Retorna número de requests restantes"""
        async with self._lock:
            now = time.time()
            client_requests = self.requests[client_id]
            
            # Remove requests antigas
            while client_requests and client_requests[0] <= now - self.window_seconds:
                client_requests.popleft()
            
            return max(0, self.max_requests - len(client_requests))
    
    def cleanup_old_clients(self, max_age_hours: int = 24):
        """Remove dados de clientes inativos"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        clients_to_remove = []
        for client_id, requests in self.requests.items():
            if not requests or requests[-1] < cutoff_time:
                clients_to_remove.append(client_id)
        
        for client_id in clients_to_remove:
            del self.requests[client_id]


class FileValidator:
    """Validador robusto de arquivos de áudio"""
    
    def __init__(self):
        self.settings = get_settings()
        
        # Assinaturas de arquivo (magic bytes)
        self.audio_signatures = {
            b'ID3': {'format': 'mp3', 'offset': 0},
            b'\xff\xfb': {'format': 'mp3', 'offset': 0},
            b'\xff\xf3': {'format': 'mp3', 'offset': 0},
            b'\xff\xf2': {'format': 'mp3', 'offset': 0},
            b'RIFF': {'format': 'wav', 'offset': 0},
            b'fLaC': {'format': 'flac', 'offset': 0},
            b'OggS': {'format': 'ogg', 'offset': 0},
            b'\x00\x00\x00 ftypM4A': {'format': 'm4a', 'offset': 4},
            b'ftypM4A': {'format': 'm4a', 'offset': 4},
            b'\x30\x26\xb2\x75\x8e\x66\xcf\x11': {'format': 'wma', 'offset': 0}
        }
    
    async def validate_file(self, file: UploadFile, client_ip: str = None) -> FileValidationResult:
        """Validação completa de arquivo"""
        result = FileValidationResult(
            valid=False,
            filename=file.filename or "unknown",
            size_bytes=0
        )
        
        try:
            # Lê conteúdo do arquivo
            content = await file.read()
            result.size_bytes = len(content)
            
            # Validações básicas
            self._validate_filename(result)
            self._validate_file_size(result)
            self._validate_file_format(content, result)
            
            # Se passou nas validações básicas, faz validação de áudio
            if not result.errors:
                await self._validate_audio_content(content, result)
            
            # Marca como válido se não há erros
            result.valid = len(result.errors) == 0
            
            # Log de auditoria
            audit_logger.log_file_upload(
                filename=result.filename,
                file_size=result.size_bytes,
                client_ip=client_ip,
                success=result.valid,
                reason='; '.join(result.errors) if result.errors else None
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error validating file {result.filename}: {e}")
            result.errors.append(f"Validation error: {str(e)}")
            return result
        
        finally:
            # Volta ao início do arquivo
            await file.seek(0)
    
    def _validate_filename(self, result: FileValidationResult):
        """Valida nome do arquivo"""
        filename = result.filename
        
        # Verifica se tem nome
        if not filename or filename.strip() == "":
            result.errors.append("Nome de arquivo é obrigatório")
            return
        
        # Verifica extensão
        path = Path(filename)
        extension = path.suffix.lower()
        
        if extension not in self.settings.processing.allowed_formats:
            result.errors.append(
                f"Extensão não permitida: {extension}. "
                f"Permitidas: {', '.join(self.settings.processing.allowed_formats)}"
            )
        
        # Verifica caracteres suspeitos
        suspicious_chars = ['..', '/', '\\', '|', ':', '*', '?', '"', '<', '>', '\x00']
        for char in suspicious_chars:
            if char in filename:
                result.errors.append(f"Nome de arquivo contém caractere suspeito: {char}")
        
        # Verifica tamanho do nome
        if len(filename) > 255:
            result.errors.append("Nome de arquivo muito longo (máximo 255 caracteres)")
    
    def _validate_file_size(self, result: FileValidationResult):
        """Valida tamanho do arquivo"""
        max_size = self.settings.processing.max_file_size_mb * 1024 * 1024
        
        if result.size_bytes == 0:
            result.errors.append("Arquivo vazio")
        elif result.size_bytes > max_size:
            result.errors.append(
                f"Arquivo muito grande: {result.size_bytes / 1024 / 1024:.1f}MB. "
                f"Máximo: {self.settings.processing.max_file_size_mb}MB"
            )
    
    def _validate_file_format(self, content: bytes, result: FileValidationResult):
        """Valida formato do arquivo através de magic bytes"""
        if not self.settings.security.validate_audio_headers:
            return
        
        # Verifica assinaturas conhecidas
        detected_format = None
        
        for signature, info in self.audio_signatures.items():
            offset = info.get('offset', 0)
            if len(content) > len(signature) + offset:
                if content[offset:offset + len(signature)] == signature:
                    detected_format = info['format']
                    break
        
        if detected_format:
            result.format = detected_format
            logger.debug(f"Detected audio format: {detected_format}")
        else:
            # Tenta detectar por MIME type
            mime_type, _ = mimetypes.guess_type(result.filename)
            if mime_type and mime_type.startswith('audio/'):
                logger.debug(f"Format detected by MIME type: {mime_type}")
            else:
                result.errors.append("Formato de arquivo não reconhecido")
    
    async def _validate_audio_content(self, content: bytes, result: FileValidationResult):
        """Valida conteúdo de áudio usando pydub"""
        try:
            # Salva temporariamente para validação
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.tmp', delete=False) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name
            
            try:
                # Carrega com pydub para validação
                audio = AudioSegment.from_file(temp_path)
                
                # Extrai metadados
                result.duration_seconds = len(audio) / 1000.0
                result.sample_rate = audio.frame_rate
                result.channels = audio.channels
                
                # Valida duração
                max_duration = self.settings.processing.max_duration_minutes * 60
                if result.duration_seconds > max_duration:
                    result.errors.append(
                        f"Áudio muito longo: {result.duration_seconds:.1f}s. "
                        f"Máximo: {max_duration}s"
                    )
                
                # Verifica se é realmente áudio
                if result.duration_seconds <= 0:
                    result.errors.append("Arquivo não contém áudio válido")
                
                # Warnings para qualidade
                if result.sample_rate < 8000:
                    result.warnings.append(f"Sample rate baixo: {result.sample_rate}Hz")
                
                if result.channels > 2:
                    result.warnings.append(f"Muitos canais: {result.channels}")
                
            finally:
                # Remove arquivo temporário
                Path(temp_path).unlink(missing_ok=True)
                
        except Exception as e:
            result.errors.append(f"Erro ao validar conteúdo de áudio: {str(e)}")


class SecurityChecker:
    """Verificador de segurança para arquivos"""
    
    def __init__(self):
        self.settings = get_settings()
        
        # Padrões suspeitos
        self.suspicious_patterns = [
            b'#!/bin/bash',
            b'#!/bin/sh',
            b'<?php',
            b'<script',
            b'javascript:',
            b'eval(',
            b'system(',
            b'exec(',
            b'shell_exec(',
            b'<html>',
            b'<body>',
        ]
    
    def check_file_security(self, content: bytes, filename: str) -> SecurityCheckResult:
        """Verificação completa de segurança"""
        result = SecurityCheckResult(safe=True)
        
        if not self.settings.security.enable_file_content_validation:
            return result
        
        try:
            # Verifica padrões suspeitos
            self._check_suspicious_patterns(content, result)
            
            # Calcula entropia para detectar arquivos criptografados/comprimidos suspeitos
            if self.settings.security.check_file_entropy:
                self._check_file_entropy(content, result)
            
            # Verifica tamanho vs conteúdo
            self._check_size_consistency(content, filename, result)
            
            result.safe = len(result.threats_detected) == 0
            
            return result
            
        except Exception as e:
            logger.error(f"Error in security check: {e}")
            result.threats_detected.append(f"Security check failed: {str(e)}")
            result.safe = False
            return result
    
    def _check_suspicious_patterns(self, content: bytes, result: SecurityCheckResult):
        """Verifica padrões suspeitos no conteúdo"""
        for pattern in self.suspicious_patterns:
            if pattern in content:
                threat = f"Suspicious pattern detected: {pattern.decode('utf-8', errors='ignore')}"
                result.threats_detected.append(threat)
                result.suspicious_patterns.append(pattern.decode('utf-8', errors='ignore'))
    
    def _check_file_entropy(self, content: bytes, result: SecurityCheckResult):
        """Calcula entropia do arquivo para detectar anomalias"""
        if len(content) < 1024:  # Skip arquivos muito pequenos
            return
        
        # Calcula entropia de Shannon
        byte_counts = [0] * 256
        for byte in content:
            byte_counts[byte] += 1
        
        entropy = 0.0
        content_length = len(content)
        
        for count in byte_counts:
            if count > 0:
                probability = count / content_length
                entropy -= probability * math.log2(probability)
        
        result.entropy_score = entropy
        
        # Entropia muito alta pode indicar arquivo criptografado ou comprimido anômalos
        if entropy > 7.5:  # Próximo do máximo teórico de 8.0
            result.threats_detected.append(
                f"High entropy detected: {entropy:.2f} (possible encrypted/compressed data)"
            )
        
        # Entropia muito baixa pode indicar arquivo fake ou padding
        elif entropy < 1.0:
            result.threats_detected.append(
                f"Very low entropy: {entropy:.2f} (possible fake/padded file)"
            )
    
    def _check_size_consistency(self, content: bytes, filename: str, result: SecurityCheckResult):
        """Verifica consistência entre tamanho e tipo de arquivo"""
        size_mb = len(content) / 1024 / 1024
        extension = Path(filename).suffix.lower()
        
        # Regras heurísticas baseadas na extensão
        size_rules = {
            '.mp3': {'min_mb_per_minute': 0.5, 'max_mb_per_minute': 5.0},
            '.wav': {'min_mb_per_minute': 5.0, 'max_mb_per_minute': 50.0},
            '.flac': {'min_mb_per_minute': 15.0, 'max_mb_per_minute': 100.0},
            '.ogg': {'min_mb_per_minute': 0.8, 'max_mb_per_minute': 8.0},
            '.m4a': {'min_mb_per_minute': 0.5, 'max_mb_per_minute': 5.0},
        }
        
        if extension in size_rules:
            rules = size_rules[extension]
            
            # Estima duração baseada no tamanho (muito aproximado)
            estimated_duration_min = size_mb / rules['max_mb_per_minute']
            
            # Se arquivo é suspeito muito grande para o formato
            if size_mb > 100:  # 100MB é muito para a maioria dos áudios
                result.suspicious_patterns.append(f"Unusually large {extension} file: {size_mb:.1f}MB")


class ValidationMiddleware:
    """Middleware para validação e rate limiting"""
    
    def __init__(self):
        self.settings = get_settings()
        self.rate_limiter = RateLimiter(
            max_requests=self.settings.security.rate_limit_requests,
            window_seconds=self.settings.security.rate_limit_window
        )
        self.file_validator = FileValidator()
        self.security_checker = SecurityChecker()
        
        # Cache de validações recentes para evitar re-validação
        self._validation_cache = {}
        self._cache_max_age = 300  # 5 minutos
    
    async def check_rate_limit(self, client_id: str) -> bool:
        """Verifica rate limit para cliente"""
        allowed = await self.rate_limiter.is_allowed(client_id)
        
        if not allowed:
            remaining = await self.rate_limiter.get_remaining_requests(client_id)
            raise RateLimitExceededError(
                client_id=client_id,
                limit=self.settings.security.rate_limit_requests,
                window=self.settings.security.rate_limit_window
            )
        
        return True
    
    async def validate_upload(
        self, 
        file: UploadFile, 
        client_ip: str = None
    ) -> Tuple[FileValidationResult, SecurityCheckResult]:
        """Validação completa de upload"""
        
        # Validação do arquivo
        file_result = await self.file_validator.validate_file(file, client_ip)
        
        if not file_result.valid:
            # Não precisa fazer verificação de segurança se arquivo é inválido
            security_result = SecurityCheckResult(safe=False)
            security_result.threats_detected.append("File validation failed")
            return file_result, security_result
        
        # Verificação de segurança
        content = await file.read()
        await file.seek(0)  # Volta ao início
        
        security_result = self.security_checker.check_file_security(content, file_result.filename)
        
        if not security_result.safe:
            audit_logger.log_security_event(
                event_type="suspicious_file_detected",
                severity="high",
                details={
                    "filename": file_result.filename,
                    "threats": security_result.threats_detected,
                    "entropy": security_result.entropy_score
                },
                client_ip=client_ip
            )
        
        return file_result, security_result
    
    def get_client_id(self, request: Request) -> str:
        """Extrai ID do cliente para rate limiting"""
        # Tenta obter IP real (atrás de proxy)
        client_ip = request.headers.get("X-Forwarded-For")
        if client_ip:
            client_ip = client_ip.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        # Adiciona User-Agent para melhor identificação
        user_agent = request.headers.get("User-Agent", "")[:50]  # Primeiros 50 chars
        
        return f"{client_ip}_{hashlib.md5(user_agent.encode()).hexdigest()[:8]}"


# Instância global do middleware de validação
validation_middleware = ValidationMiddleware()