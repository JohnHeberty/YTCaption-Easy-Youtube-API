"""
Utilitários para manipulação de datetime com timezone.

Todos os microsserviços devem usar estas funções para garantir
consistência nos timestamps, usando o horário de Brasília (America/Sao_Paulo).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback para Python < 3.9
    from backports.zoneinfo import ZoneInfo

# Timezone de Brasília (UTC-3 ou UTC-2 no horário de verão)
BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")


def now_brazil() -> datetime:
    """
    Retorna datetime atual com timezone de Brasília.
    
    Returns:
        datetime: Datetime atual timezone-aware (America/Sao_Paulo)
    
    Example:
        >>> from common.datetime_utils import now_brazil
        >>> timestamp = now_brazil()
        >>> print(timestamp)
        2026-02-28 20:24:00-03:00
    """
    return datetime.now(BRAZIL_TZ)


def utcnow_aware() -> datetime:
    """
    Retorna datetime UTC timezone-aware.
    
    Útil para armazenar em bancos de dados ou APIs internacionais.
    
    Returns:
        datetime: Datetime UTC timezone-aware
    """
    return datetime.now(timezone.utc)


def to_brazil_tz(dt: datetime) -> datetime:
    """
    Converte um datetime para o timezone de Brasília.
    
    Args:
        dt: Datetime a ser convertido (pode ser naive ou aware)
        
    Returns:
        datetime: Datetime convertido para America/Sao_Paulo
        
    Example:
        >>> from datetime import datetime
        >>> from common.datetime_utils import to_brazil_tz
        >>> utc_time = datetime(2026, 2, 28, 23, 24, tzinfo=timezone.utc)
        >>> brazil_time = to_brazil_tz(utc_time)
        >>> print(brazil_time)
        2026-02-28 20:24:00-03:00
    """
    if dt.tzinfo is None:
        # Se é naive, assume como UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BRAZIL_TZ)


def brazil_timestamp_str(dt: Optional[datetime] = None) -> str:
    """
    Retorna string formatada com timestamp de Brasília.
    
    Args:
        dt: Datetime a formatar (usa now_brazil() se None)
        
    Returns:
        str: String formatada ISO 8601 com timezone
        
    Example:
        >>> from common.datetime_utils import brazil_timestamp_str
        >>> print(brazil_timestamp_str())
        2026-02-28T20:24:00-03:00
    """
    if dt is None:
        dt = now_brazil()
    elif dt.tzinfo is None:
        dt = to_brazil_tz(dt)
    return dt.isoformat()


__all__ = [
    'BRAZIL_TZ',
    'now_brazil',
    'utcnow_aware',
    'to_brazil_tz',
    'brazil_timestamp_str',
]
