"""
Error Handling Patterns for Audio Voice Service

Best practices para tratamento de exceções específicas.
"""
from typing import TypeVar, Callable, Any
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

T = TypeVar('T')


def safe_file_delete(file_path: str | Path) -> bool:
    """
    Deleta arquivo de forma segura com error handling apropriado.
    
    Args:
        file_path: Caminho do arquivo
        
    Returns:
        True se deletado com sucesso, False caso contrário
    """
    try:
        Path(file_path).unlink()
        logger.debug(f"Deleted file: {file_path}")
        return True
    except FileNotFoundError:
        logger.debug(f"File already deleted: {file_path}")
        return True  # Idempotente
    except PermissionError as e:
        logger.warning(f"Cannot delete file (locked?): {file_path} - {e}")
        return False
    except OSError as e:
        logger.error(f"Filesystem error deleting {file_path}: {e}")
        return False


def safe_file_operation(
    operation: Callable[[], T],
    file_path: str | Path,
    operation_name: str = "file operation"
) -> T | None:
    """
    Executa operação de arquivo com error handling robusto.
    
    Args:
        operation: Função a executar
        file_path: Caminho do arquivo
        operation_name: Nome da operação (para logs)
        
    Returns:
        Resultado da operação ou None se falhou
    """
    try:
        return operation()
    except FileNotFoundError as e:
        logger.error(f"{operation_name} failed - file not found: {file_path}")
        raise
    except PermissionError as e:
        logger.error(f"{operation_name} failed - permission denied: {file_path}")
        raise
    except OSError as e:
        logger.error(f"{operation_name} failed - OS error: {e}")
        raise
    except Exception as e:
        logger.error(f"{operation_name} failed - unexpected error: {e}", exc_info=True)
        raise


# Pattern: Audio file loading
def load_audio_safe(file_path: str | Path):
    """Pattern para carregar áudio com error handling específico."""
    import torchaudio
    from .exceptions import InvalidAudioException
    
    try:
        return torchaudio.load(str(file_path))
    except FileNotFoundError as e:
        raise InvalidAudioException(f"Audio file not found: {file_path}") from e
    except RuntimeError as e:
        # torchaudio levanta RuntimeError para formato inválido
        if "format" in str(e).lower() or "codec" in str(e).lower():
            raise InvalidAudioException(f"Invalid audio format: {e}") from e
        raise
    except OSError as e:
        raise InvalidAudioException(f"Cannot read audio file: {e}") from e
