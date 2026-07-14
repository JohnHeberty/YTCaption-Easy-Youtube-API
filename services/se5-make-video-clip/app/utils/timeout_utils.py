"""
Timeout utilities

Wrappers para operações com timeout garantido
"""
from __future__ import annotations

import signal
from typing import Any
from collections.abc import Callable
from functools import wraps


class TimeoutError(Exception):
    """Exceção levantada quando operação excede timeout"""
    pass


def timeout_handler(signum: int, frame: Any) -> None:
    """Handler para sinal de timeout"""
    raise TimeoutError("Operation timed out")


def with_timeout(seconds: int) -> Callable[[Any], Any]:
    """
    Decorator para adicionar timeout a funções
    
    Exemplo:
        @with_timeout(5)
        def slow_function():
            time.sleep(10)
    
    Note: Apenas funciona em Unix/Linux (usa signal.SIGALRM)
    """
    def decorator(func: Any) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Setup alarm
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)
            
            try:
                result = func(*args, **kwargs)
            finally:
                # Cancel alarm
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            
            return result
        
        return wrapper
    return decorator


def run_with_timeout(func: Callable, timeout_seconds: int, *args, **kwargs) -> Any:
    """
    Executa função com timeout
    
    Args:
        func: Função a executar
        timeout_seconds: Timeout em segundos
        *args, **kwargs: Argumentos para a função
    
    Returns:
        Resultado da função
    
    Raises:
        TimeoutError: Se função exceder timeout
    """
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)
    
    try:
        result = func(*args, **kwargs)
        return result
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
