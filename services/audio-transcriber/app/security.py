"""
Middleware de segurança e validação
"""
import time
import mimetypes
from typing import Dict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from .config import get_settings
from .exceptions import SecurityError, ValidationError


class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware de segurança básico"""
    
    def __init__(self, app):
        super().__init__(app)
        self.settings = get_settings()
        self.request_counts: Dict[str, list] = {}
    
    async def dispatch(self, request: Request, call_next):
        # Rate limiting simples
        client_ip = request.client.host
        now = time.time()
        
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = []
        
        # Remove requests antigos
        window_start = now - self.settings['security']['rate_limit_window']
        self.request_counts[client_ip] = [
            req_time for req_time in self.request_counts[client_ip] 
            if req_time > window_start
        ]
        
        # Verifica rate limit
        if len(self.request_counts[client_ip]) >= self.settings['security']['rate_limit_requests']:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        # Adiciona request atual
        self.request_counts[client_ip].append(now)
        
        response = await call_next(request)
        return response


def validate_audio_file(filename: str, content: bytes) -> None:
    """
    Valida arquivo de áudio
    
    Args:
        filename: Nome do arquivo
        content: Conteúdo do arquivo
    
    Raises:
        ValidationError: Se arquivo inválido
        SecurityError: Se arquivo suspeito
    """
    settings = get_settings()
    
    if not settings['security']['enable_file_validation']:
        return
    
    # Verifica extensão
    allowed_extensions = {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.webm', '.mp4'}
    file_ext = '.' + filename.split('.')[-1].lower() if '.' in filename else ''
    
    if file_ext not in allowed_extensions:
        raise ValidationError(f"Tipo de arquivo não suportado: {file_ext}")
    
    # Verifica tamanho
    max_size = get_settings()['max_file_size_mb'] * 1024 * 1024
    if len(content) > max_size:
        raise ValidationError(f"Arquivo muito grande. Máximo: {max_size // (1024*1024)}MB")
    
    # Verifica se não está vazio
    if len(content) < 1000:  # Mínimo 1KB
        raise ValidationError("Arquivo muito pequeno ou corrompido")
    
    # Validação básica de headers de áudio
    if settings['security']['validate_audio_headers']:
        _validate_audio_headers(content)


def _validate_audio_headers(content: bytes) -> None:
    """Validação básica de headers de áudio"""
    if len(content) < 12:
        raise ValidationError("Arquivo corrompido - headers inválidos")
    
    # Verifica alguns headers conhecidos
    headers = content[:12]
    
    # MP3
    if headers[:3] == b'ID3' or headers[:2] == b'\xff\xfb':
        return
    
    # WAV
    if headers[:4] == b'RIFF' and headers[8:12] == b'WAVE':
        return
    
    # FLAC
    if headers[:4] == b'fLaC':
        return
    
    # OGG
    if headers[:4] == b'OggS':
        return
    
    # WebM/MP4 (básico)
    if b'ftyp' in headers or b'mdat' in headers:
        return
    
    # Se chegou aqui, pode ser suspeito
    raise ValidationError("Formato de áudio não reconhecido ou corrompido")