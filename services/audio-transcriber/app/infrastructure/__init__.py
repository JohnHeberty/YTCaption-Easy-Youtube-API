"""Infrastructure components for audio-transcriber service

Padrões de resiliência adaptados do make-video service para alta disponibilidade.

Components:
- CircuitBreaker: Protege contra falhas em cascata
- CheckpointManager: Recuperação de transcrições interrompidas
- DistributedRateLimiter: Rate limiting distribuído via Redis
"""

from .circuit_breaker import CircuitBreaker, CircuitBreakerState, CircuitBreakerException, get_circuit_breaker
from .checkpoint_manager import CheckpointManager, TranscriptionStage, CheckpointData
from .distributed_rate_limiter import DistributedRateLimiter

__all__ = [
    'CircuitBreaker',
    'CircuitBreakerState',
    'CircuitBreakerException',
    'get_circuit_breaker',
    'CheckpointManager',
    'TranscriptionStage',
    'CheckpointData',
    'DistributedRateLimiter',
]

