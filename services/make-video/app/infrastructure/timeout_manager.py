"""
Smart Timeout Management - Sprint-03

Calcula timeouts dinâmicos baseados em complexidade do job.
"""

from typing import Dict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class JobTimeouts:
    """Timeouts calculados para um job"""
    download: int  # Timeout para download de shorts (segundos)
    validation: int  # Timeout para validação de shorts (segundos)
    build: int  # Timeout para construção do vídeo (segundos)
    total: int  # Timeout total do job (segundos)
    
    def to_dict(self) -> Dict[str, int]:
        """Converte para dicionário"""
        return {
            "download": self.download,
            "validation": self.validation,
            "build": self.build,
            "total": self.total
        }


class TimeoutManager:
    """
    Gerenciador de timeouts inteligentes.
    
    Calcula timeouts baseados em:
    - Número de shorts a processar
    - Duração do áudio
    - Aspect ratio (portrait é mais lento)
    - Fatores de complexidade adicionais
    """
    
    # Constantes de tempo (segundos)
    BASE_TIMEOUT = 60  # 1 minuto base
    
    # Fatores por operação
    DOWNLOAD_PER_SHORT = 4  # 4s por short (download + save)
    VALIDATION_PER_SHORT = 2  # 2s por short (OCR + checks)
    BUILD_PER_AUDIO_SECOND = 1.5  # 1.5s por segundo de áudio
    
    # Multiplicadores
    PORTRAIT_MULTIPLIER = 1.5  # Portrait (9:16) é 50% mais lento
    LANDSCAPE_MULTIPLIER = 1.0  # Landscape (16:9) é baseline
    
    # Limites
    MIN_TIMEOUT = 30  # Mínimo 30 segundos
    MAX_TIMEOUT = 3600  # Máximo 1 hora
    
    def __init__(self):
        logger.info("✅ TimeoutManager initialized")
    
    def calculate_timeouts(
        self,
        shorts_count: int,
        audio_duration: float,
        aspect_ratio: str = "16:9"
    ) -> JobTimeouts:
        """
        Calcula timeouts para um job.
        
        Args:
            shorts_count: Número de shorts a processar
            audio_duration: Duração do áudio em segundos
            aspect_ratio: "16:9" ou "9:16"
        
        Returns:
            JobTimeouts com timeouts calculados
        """
        # Determinar multiplicador de aspect ratio
        aspect_multiplier = (
            self.PORTRAIT_MULTIPLIER if aspect_ratio == "9:16"
            else self.LANDSCAPE_MULTIPLIER
        )
        
        # Calcular timeout de download (aspect_multiplier afeta tudo)
        download_timeout = (
            self.BASE_TIMEOUT + (shorts_count * self.DOWNLOAD_PER_SHORT)
        ) * aspect_multiplier
        
        # Calcular timeout de validação
        validation_timeout = shorts_count * self.VALIDATION_PER_SHORT
        
        # Calcular timeout de build (aspect_multiplier afeta tudo)
        build_timeout = (
            self.BASE_TIMEOUT + (audio_duration * self.BUILD_PER_AUDIO_SECOND)
        ) * aspect_multiplier
        
        # Calcular timeout total
        total_timeout = download_timeout + validation_timeout + build_timeout
        
        # Aplicar limites
        download_timeout = self._apply_limits(download_timeout)
        validation_timeout = self._apply_limits(validation_timeout)
        build_timeout = self._apply_limits(build_timeout)
        total_timeout = self._apply_limits(total_timeout)
        
        timeouts = JobTimeouts(
            download=int(download_timeout),
            validation=int(validation_timeout),
            build=int(build_timeout),
            total=int(total_timeout)
        )
        
        logger.debug(
            f"⏱️  Calculated timeouts: download={timeouts.download}s, "
            f"validation={timeouts.validation}s, build={timeouts.build}s, "
            f"total={timeouts.total}s (shorts={shorts_count}, "
            f"audio={audio_duration}s, aspect={aspect_ratio})"
        )
        
        return timeouts
    
    def _apply_limits(self, timeout: float) -> float:
        """Aplica limites mínimo e máximo"""
        return max(self.MIN_TIMEOUT, min(timeout, self.MAX_TIMEOUT))
    
    def get_download_timeout_per_short(self, aspect_ratio: str = "16:9") -> int:
        """
        Retorna timeout recomendado para download de um único short.
        
        Args:
            aspect_ratio: "16:9" ou "9:16"
        
        Returns:
            Timeout em segundos
        """
        multiplier = (
            self.PORTRAIT_MULTIPLIER if aspect_ratio == "9:16"
            else self.LANDSCAPE_MULTIPLIER
        )
        return int(self.DOWNLOAD_PER_SHORT * multiplier)


# Singleton global
_timeout_manager = None


def get_timeout_manager() -> TimeoutManager:
    """Retorna instância singleton do TimeoutManager"""
    global _timeout_manager
    if _timeout_manager is None:
        _timeout_manager = TimeoutManager()
    return _timeout_manager
