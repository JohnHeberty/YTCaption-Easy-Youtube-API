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
        
        # Headers de segurança
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response


def validate_audio_file(filename: str, content: bytes) -> None:
    """
    Valida arquivo básico (sem validação de formato)
    
    IMPORTANTE: NÃO valida formato/MIME type aqui.
    A validação real acontece no processamento com ffprobe.
    
    Args:
        filename: Nome do arquivo
        content: Conteúdo do arquivo
    
    Raises:
        ValidationError: Se arquivo básico inválido
        SecurityError: Se arquivo suspeito por tamanho
    """
    settings = get_settings()
    
    if not settings['security']['enable_file_validation']:
        return
    
    # Verifica apenas tamanho (sem verificar formato)
    max_size = get_settings()['max_file_size_mb'] * 1024 * 1024
    if len(content) > max_size:
        raise ValidationError(f"Arquivo muito grande. Máximo: {max_size // (1024*1024)}MB")
    
    # Verifica se não está vazio
    if len(content) < 100:  # Mínimo 100 bytes (muito permissivo)
        raise ValidationError("Arquivo vazio")
    
    # NÃO faz validação de formato aqui - deixa para o ffprobe


def validate_audio_content_with_ffprobe(file_path: str) -> Dict[str, any]:
    """
    Valida arquivo de áudio usando ffprobe
    
    Args:
        file_path: Caminho para o arquivo
    
    Returns:
        dict: Informações do arquivo
    
    Raises:
        ValidationError: Se não contém stream de áudio
    """
    import subprocess
    import json
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Executa ffprobe para obter informações do arquivo
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams',
            '-show_format',
            str(file_path)
        ]
        
        # Timeout configurável via env var (padrão: 30s)
        from .config import get_settings
        settings = get_settings()
        ffprobe_timeout = int(settings.get('ffprobe_timeout_seconds', 30))
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=ffprobe_timeout
        )
        
        if result.returncode != 0:
            logger.error(f"ffprobe falhou: {result.stderr}")
            raise ValidationError("Arquivo não pode ser analisado pelo ffprobe")
        
        data = json.loads(result.stdout)
        streams = data.get('streams', [])
        
        # Verifica se há pelo menos um stream de áudio
        audio_streams = [s for s in streams if s.get('codec_type') == 'audio']
        
        if not audio_streams:
            raise ValidationError("O arquivo enviado não contém um stream de áudio válido")
        
        logger.info(f"Arquivo válido: {len(audio_streams)} stream(s) de áudio encontrado(s)")
        
        return {
            'audio_streams': audio_streams,
            'video_streams': [s for s in streams if s.get('codec_type') == 'video'],
            'format': data.get('format', {}),
            'has_video': any(s.get('codec_type') == 'video' for s in streams),
            'has_audio': len(audio_streams) > 0
        }
        
    except subprocess.TimeoutExpired:
        raise ValidationError(f"Timeout ao analisar arquivo (limite: {ffprobe_timeout}s)")
    except json.JSONDecodeError:
        raise ValidationError("Resposta inválida do ffprobe")
    except FileNotFoundError:
        raise ValidationError("ffprobe não encontrado - instale ffmpeg")
    except Exception as e:
        logger.error(f"Erro inesperado no ffprobe: {e}")
        raise ValidationError(f"Erro ao validar arquivo: {str(e)}")