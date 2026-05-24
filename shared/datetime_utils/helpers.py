"""
Timezone helpers para garantir operações seguras com datetime.

Funções auxiliares para lidar com timezone-aware e timezone-naive datetimes,
prevenindo erros comuns ao misturar os dois tipos.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Any

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# Timezone de Brasília (UTC-3 ou UTC-2 no horário de verão)
BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")


def ensure_timezone_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Garante que um datetime tem timezone (converte para Brasília se naive).
    
    Args:
        dt: Datetime a ser verificado e possivelmente convertido
        
    Returns:
        Datetime timezone-aware ou None se dt for None
        
    Example:
        >>> naive_dt = datetime(2026, 2, 28, 20, 30)  # Sem timezone
        >>> aware_dt = ensure_timezone_aware(naive_dt)
        >>> print(aware_dt)
        2026-02-28 20:30:00-03:00
    """
    if dt is None:
        return None
    
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        # DateTime é naive - assumir como se fosse Brasília
        # (Alternativa: assume UTC e converte)
        dt = dt.replace(tzinfo=BRAZIL_TZ)
    
    return dt


def ensure_timezone_aware_utc_base(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Garante timezone-aware assumindo que naive datetime está em UTC.
    
    Usa esta função quando você sabe que o datetime naive veio de um
    sistema que armazena em UTC (comum em APIs/bancos de dados).
    
    Args:
        dt: Datetime a ser verificado
        
    Returns:
        Datetime timezone-aware convertido para Brasília
        
    Example:
        >>> naive_utc = datetime(2026, 2, 28, 23, 30)  # UTC naive
        >>> aware_brazil = ensure_timezone_aware_utc_base(naive_utc)
        >>> print(aware_brazil)
        2026-02-28 20:30:00-03:00  # Convertido para Brasília
    """
    if dt is None:
        return None
    
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        # Assume que é UTC e converte para Brasília
        dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(BRAZIL_TZ)
    
    return dt


def safe_datetime_subtract(dt1: datetime, dt2: datetime) -> timedelta:
    """
    Subtração segura entre datetimes (normaliza ambos antes).
    
    Previne o erro: "can't subtract offset-naive and offset-aware datetimes"
    
    Args:
        dt1: Datetime minuendo (do qual subtraímos)
        dt2: Datetime subtraendo (o que será subtraído)
        
    Returns:
        Timedelta resultante da subtração
        
    Example:
        >>> from common.datetime_utils import now_brazil
        >>> now = now_brazil()  # Timezone-aware
        >>> old_dt = datetime(2026, 2, 28, 19, 0)  # Naive
        >>> duration = safe_datetime_subtract(now, old_dt)
        >>> print(duration.total_seconds())
        5400.0  # 1.5 horas
    """
    dt1 = ensure_timezone_aware(dt1)
    dt2 = ensure_timezone_aware(dt2)
    return dt1 - dt2


def safe_datetime_compare(dt1: datetime, dt2: datetime) -> int:
    """
    Comparação segura entre datetimes (normaliza ambos antes).
    
    Args:
        dt1: Primeiro datetime
        dt2: Segundo datetime
        
    Returns:
        -1 se dt1 < dt2, 0 se dt1 == dt2, 1 se dt1 > dt2
        
    Example:
        >>> dt1 = datetime(2026, 2, 28, 20, 0)  # Naive
        >>> dt2 = now_brazil()  # Aware
        >>> result = safe_datetime_compare(dt1, dt2)
        >>> print("dt1 é mais antigo" if result < 0 else "dt2 é mais antigo")
    """
    dt1 = ensure_timezone_aware(dt1)
    dt2 = ensure_timezone_aware(dt2)
    
    if dt1 < dt2:
        return -1
    elif dt1 > dt2:
        return 1
    else:
        return 0


def normalize_model_datetimes(obj: Any, fields: list = None) -> Any:
    """
    Normaliza todos os campos datetime de um objeto para timezone-aware.
    
    Útil para normalizar modelos Pydantic após deserialização do Redis/DB.
    
    Args:
        obj: Objeto a ser normalizado (geralmente um Pydantic model)
        fields: Lista de campos a normalizar (default: todos datetime fields)
        
    Returns:
        Objeto modificado com datetimes timezone-aware
        
    Example:
        >>> from app.models import Job
        >>> job = Job.from_redis(data)  # Pode ter datetimes naive
        >>> job = normalize_model_datetimes(job, ['created_at', 'updated_at'])
        >>> print(job.created_at.tzinfo)  # Garante timezone
        America/Sao_Paulo
    """
    if obj is None:
        return None
    
    # Se não especificou fields, tenta detectar automaticamente
    if fields is None:
        fields = []
        # Para Pydantic models
        if hasattr(obj, 'model_fields'):
            for field_name, field_info in obj.model_fields.items():
                # Verifica se o campo é datetime
                if hasattr(field_info, 'annotation'):
                    annotation = str(field_info.annotation)
                    if 'datetime' in annotation.lower():
                        fields.append(field_name)
        # Para objetos comuns
        else:
            for attr_name in dir(obj):
                if not attr_name.startswith('_'):
                    attr_value = getattr(obj, attr_name, None)
                    if isinstance(attr_value, datetime):
                        fields.append(attr_name)
    
    # Normaliza cada campo
    for field in fields:
        if hasattr(obj, field):
            value = getattr(obj, field)
            if isinstance(value, datetime):
                normalized = ensure_timezone_aware(value)
                setattr(obj, field, normalized)
    
    return obj


def format_duration_safe(start: datetime, end: Optional[datetime] = None) -> str:
    """
    Formata duração entre dois datetimes de forma segura.
    
    Args:
        start: Datetime inicial
        end: Datetime final (default: now_brazil())
        
    Returns:
        String formatada (ex: "1h 30m", "45s", "2d 3h")
        
    Example:
        >>> started = datetime(2026, 2, 28, 19, 0)
        >>> finished = datetime(2026, 2, 28, 20, 30)
        >>> print(format_duration_safe(started, finished))
        "1h 30m"
    """
    if end is None:
        from . import now_brazil
        end = now_brazil()
    
    duration = safe_datetime_subtract(end, start)
    seconds = int(duration.total_seconds())
    
    if seconds < 0:
        return "0s"
    
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    
    return " ".join(parts[:2])  # Mostrar no máximo 2 unidades


__all__ = [
    'BRAZIL_TZ',
    'ensure_timezone_aware',
    'ensure_timezone_aware_utc_base',
    'safe_datetime_subtract',
    'safe_datetime_compare',
    'normalize_model_datetimes',
    'format_duration_safe',
]
