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
    
    # IMPORTANTE: Validação real de formato será feita com ffprobe durante processamento
    # Headers validation removida para evitar rejeições de arquivos .webm válidos


def validate_audio_content_with_ffprobe(file_path: str) -> dict:
    """
    Valida conteúdo de áudio usando ffprobe - mais robusta que validação de headers
    
    Args:
        file_path: Caminho para o arquivo a ser validado
        
    Returns:
        dict: Informações do arquivo (streams, duração, etc.)
        
    Raises:
        ValidationError: Se arquivo não é válido ou não contém áudio
    """
    import subprocess
    import json
    
    try:
        # Comando ffprobe para analisar o arquivo
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', 
            '-show_streams', '-show_format', str(file_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            raise ValidationError("Arquivo não pode ser analisado pelo ffprobe")
            
        file_info = json.loads(result.stdout)
        
        # Verifica se tem streams de áudio
        audio_streams = [s for s in file_info.get('streams', []) if s.get('codec_type') == 'audio']
        
        if not audio_streams:
            # Pode ser um arquivo de vídeo, vamos verificar se tem streams de vídeo
            video_streams = [s for s in file_info.get('streams', []) if s.get('codec_type') == 'video']
            if video_streams:
                # É um arquivo de vídeo - será necessário extrair áudio
                return {
                    'type': 'video_with_audio',
                    'audio_streams': audio_streams,
                    'video_streams': video_streams,
                    'format': file_info.get('format', {})
                }
            else:
                raise ValidationError("Arquivo não contém streams de áudio")
        
        return {
            'type': 'audio',
            'audio_streams': audio_streams,
            'format': file_info.get('format', {}),
            'duration': float(file_info.get('format', {}).get('duration', 0))
        }
        
    except subprocess.TimeoutExpired:
        raise ValidationError("Timeout ao analisar arquivo com ffprobe")
    except json.JSONDecodeError:
        raise ValidationError("Resposta inválida do ffprobe")
    except Exception as e:
        raise ValidationError(f"Erro ao validar arquivo: {str(e)}")