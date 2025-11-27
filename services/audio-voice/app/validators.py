"""
Validadores de entrada para API de áudio
"""
import re
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# MIME types de áudio suportados
SUPPORTED_AUDIO_MIMES = {
    'audio/wav',
    'audio/wave',
    'audio/x-wav',
    'audio/mpeg',
    'audio/mp3',
    'audio/ogg',
    'audio/x-m4a',
    'audio/m4a',
    'audio/flac',
    'audio/webm',
}

# Extensões de áudio suportadas
SUPPORTED_AUDIO_EXTENSIONS = {
    '.wav', '.wave',
    '.mp3', '.mpeg',
    '.ogg', '.oga',
    '.m4a',
    '.flac',
    '.webm',
}


def sanitize_text(text: str, max_length: int = 10000) -> str:
    """
    Sanitiza texto para síntese TTS
    
    Args:
        text: Texto a sanitizar
        max_length: Tamanho máximo permitido
    
    Returns:
        Texto sanitizado
    
    Raises:
        ValueError: Se texto inválido ou muito longo
    """
    if not text or not isinstance(text, str):
        raise ValueError("Texto vazio ou inválido")
    
    # Remove espaços em branco excessivos
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    
    # Valida tamanho
    if len(text) > max_length:
        raise ValueError(f"Texto muito longo: {len(text)} chars (máximo {max_length})")
    
    if len(text) == 0:
        raise ValueError("Texto vazio após sanitização")
    
    # Remove caracteres de controle (mas mantém newlines)
    text = ''.join(char for char in text if char.isprintable() or char in ['\n', '\r', '\t'])
    
    logger.debug("Text sanitized: %d chars", len(text))
    
    return text


def validate_audio_mime(mime_type: str, filename: Optional[str] = None) -> bool:
    """
    Valida MIME type de áudio
    
    Args:
        mime_type: MIME type reportado (ex: 'audio/wav')
        filename: Nome do arquivo (opcional, para validação de extensão)
    
    Returns:
        True se válido
    
    Raises:
        ValueError: Se MIME type inválido
    """
    # Normaliza MIME type
    mime_type = mime_type.lower().strip()
    
    # Valida contra lista de MIME types suportados
    if mime_type not in SUPPORTED_AUDIO_MIMES:
        raise ValueError(
            f"Formato de áudio não suportado: {mime_type}. "
            f"Formatos suportados: {', '.join(sorted(SUPPORTED_AUDIO_MIMES))}"
        )
    
    # Validação adicional por extensão (se fornecida)
    if filename:
        extension = Path(filename).suffix.lower()
        if extension and extension not in SUPPORTED_AUDIO_EXTENSIONS:
            logger.warning(
                "Arquivo %s tem extensão %s que pode não corresponder ao MIME %s",
                filename, extension, mime_type
            )
    
    return True


def validate_audio_file(file_path: str, min_size_bytes: int = 1024) -> bool:
    """
    Valida arquivo de áudio existe e tem tamanho mínimo
    
    Args:
        file_path: Caminho do arquivo
        min_size_bytes: Tamanho mínimo em bytes (padrão 1KB)
    
    Returns:
        True se válido
    
    Raises:
        FileNotFoundError: Se arquivo não existe
        ValueError: Se arquivo muito pequeno
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
    
    if not path.is_file():
        raise ValueError(f"Caminho não é um arquivo: {file_path}")
    
    file_size = path.stat().st_size
    if file_size < min_size_bytes:
        raise ValueError(
            f"Arquivo muito pequeno: {file_size} bytes (mínimo {min_size_bytes} bytes)"
        )
    
    logger.debug("Audio file validated: %s (%d bytes)", file_path, file_size)
    
    return True


def validate_language_code(language: str, supported_languages: list) -> str:
    """
    Valida e normaliza código de idioma
    
    Args:
        language: Código de idioma (ex: 'pt-BR', 'en')
        supported_languages: Lista de idiomas suportados
    
    Returns:
        Código normalizado
    
    Raises:
        ValueError: Se idioma não suportado
    """
    if not language:
        raise ValueError("Código de idioma vazio")
    
    # Normaliza para lowercase
    language = language.lower().strip()
    
    # Valida formato básico (xx ou xx-XX)
    if not re.match(r'^[a-z]{2}(-[a-z]{2})?$', language, re.IGNORECASE):
        raise ValueError(
            f"Formato de código de idioma inválido: {language}. "
            "Use formato ISO 639-1 (ex: 'pt', 'pt-BR', 'en-US')"
        )
    
    # Extrai código base (pt de pt-BR)
    lang_base = language.split('-')[0]
    
    # Valida se idioma ou código base está suportado
    supported_lower = [l.lower() for l in supported_languages]
    
    if language in supported_lower:
        return language
    elif lang_base in supported_lower:
        logger.debug("Language code %s normalized to base %s", language, lang_base)
        return lang_base
    else:
        raise ValueError(
            f"Idioma não suportado: {language}. "
            f"Idiomas suportados: {', '.join(supported_languages)}"
        )


def validate_voice_name(name: str, max_length: int = 100) -> str:
    """
    Valida nome de perfil de voz
    
    Args:
        name: Nome do perfil
        max_length: Tamanho máximo
    
    Returns:
        Nome sanitizado
    
    Raises:
        ValueError: Se nome inválido
    """
    if not name or not isinstance(name, str):
        raise ValueError("Nome de voz vazio ou inválido")
    
    # Remove espaços
    name = name.strip()
    
    if len(name) == 0:
        raise ValueError("Nome de voz vazio após sanitização")
    
    if len(name) > max_length:
        raise ValueError(f"Nome muito longo: {len(name)} chars (máximo {max_length})")
    
    # Valida caracteres permitidos (alfanuméricos, espaços, hífens, underscores)
    if not re.match(r'^[a-zA-Z0-9\s_-]+$', name):
        raise ValueError(
            "Nome de voz contém caracteres inválidos. "
            "Use apenas letras, números, espaços, hífens e underscores"
        )
    
    return name


def validate_speed(speed: float) -> float:
    """
    Valida parâmetro de velocidade
    
    Args:
        speed: Velocidade (0.5-2.0)
    
    Returns:
        Velocidade validada
    
    Raises:
        ValueError: Se fora do range
    """
    if not isinstance(speed, (int, float)):
        raise ValueError(f"Velocidade deve ser número, recebido: {type(speed)}")
    
    if speed < 0.5 or speed > 2.0:
        raise ValueError(f"Velocidade fora do range: {speed} (permitido: 0.5-2.0)")
    
    return float(speed)


def validate_temperature(temperature: float) -> float:
    """
    Valida parâmetro de temperatura (variação de emoção)
    
    Args:
        temperature: Temperatura (0.1-1.0)
    
    Returns:
        Temperatura validada
    
    Raises:
        ValueError: Se fora do range
    """
    if not isinstance(temperature, (int, float)):
        raise ValueError(f"Temperature deve ser número, recebido: {type(temperature)}")
    
    if temperature < 0.1 or temperature > 1.0:
        raise ValueError(f"Temperature fora do range: {temperature} (permitido: 0.1-1.0)")
    
    return float(temperature)
