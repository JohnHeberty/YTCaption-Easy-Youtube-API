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
    
    # IMPORTANTE: Validação real de formato será feita durante processamento
    # Headers validation removida para evitar rejeições de arquivos .webm válidos


def validate_url(url: str) -> None:
    """
    Valida URL para download (específico para video-downloader)
    
    Args:
        url: URL para validar
        
    Raises:
        ValidationError: Se URL inválida
        SecurityError: Se URL suspeita
    """
    import re
    
    if not url or not isinstance(url, str):
        raise ValidationError("URL é obrigatória")
    
    # Verifica se é uma URL válida
    url_pattern = re.compile(
        r'^https?://'  # http:// ou https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...ou ip
        r'(?::\d+)?'  # porta opcional
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    if not url_pattern.match(url):
        raise ValidationError("URL inválida")
    
    # Lista de domínios permitidos (YouTube, etc)
    allowed_domains = [
        'youtube.com', 'youtu.be', 'vimeo.com', 
        'dailymotion.com', 'twitch.tv'
    ]
    
    domain_found = False
    for domain in allowed_domains:
        if domain in url.lower():
            domain_found = True
            break
    
    if not domain_found:
        raise SecurityError(f"Domínio não permitido. Permitidos: {', '.join(allowed_domains)}")