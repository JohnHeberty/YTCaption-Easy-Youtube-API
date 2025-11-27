"""
LOW VRAM Mode - Gerenciamento automático de VRAM

Quando LOW_VRAM=true, este módulo:
1. Carrega modelo apenas quando necessário
2. Processa áudio
3. Descarrega modelo da VRAM imediatamente
4. Repete para próximo modelo (RVC, etc)

Benefícios:
- Permite rodar em GPUs com pouca VRAM (4GB-6GB)
- Evita OOM (Out of Memory) errors
- Aumenta latência (carregamento de modelo a cada uso)
"""

import gc
import torch
from typing import Optional, Callable, Any
from contextlib import contextmanager
from functools import wraps
import logging

from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VRAMManager:
    """
    Gerenciador de VRAM para modo LOW_VRAM.
    
    Controla carregamento/descarregamento automático de modelos.
    """
    
    def __init__(self):
        self.low_vram_mode = settings.get('low_vram_mode', False)
        self._model_cache = {}  # Cache de modelos (quando LOW_VRAM=false)
        
        if self.low_vram_mode:
            logger.info("🔋 LOW VRAM MODE: ATIVADO - Modelos serão carregados/descarregados automaticamente")
        else:
            logger.info("⚡ NORMAL MODE: Modelos permanecerão na VRAM")
    
    @contextmanager
    def load_model(self, model_key: str, load_fn: Callable, *args, **kwargs):
        """
        Context manager para carregar modelo temporariamente.
        
        Uso:
            with vram_manager.load_model('xtts', load_xtts_model, config):
                output = model.process(input)
            # Modelo é descarregado automaticamente aqui
        
        Args:
            model_key: Identificador único do modelo
            load_fn: Função que carrega o modelo
            *args, **kwargs: Argumentos para load_fn
        
        Yields:
            Modelo carregado
        """
        model = None
        
        try:
            # Em modo LOW_VRAM, sempre carrega fresh
            # Em modo NORMAL, usa cache
            if self.low_vram_mode:
                logger.debug(f"🔋 Carregando modelo '{model_key}' (LOW VRAM)")
                model = load_fn(*args, **kwargs)
            else:
                # Usar cache
                if model_key not in self._model_cache:
                    logger.debug(f"⚡ Carregando modelo '{model_key}' (primeira vez)")
                    self._model_cache[model_key] = load_fn(*args, **kwargs)
                else:
                    logger.debug(f"⚡ Usando modelo '{model_key}' do cache")
                model = self._model_cache[model_key]
            
            yield model
        
        finally:
            # Descarregar apenas em modo LOW_VRAM
            if self.low_vram_mode and model is not None:
                logger.debug(f"🔋 Descarregando modelo '{model_key}' da VRAM")
                self._unload_model(model)
                del model
    
    def _unload_model(self, model):
        """
        Descarrega modelo da VRAM.
        
        Args:
            model: Modelo a ser descarregado
        """
        try:
            # Mover modelo para CPU
            if hasattr(model, 'to'):
                model.to('cpu')
            elif hasattr(model, 'cpu'):
                model.cpu()
            
            # Liberar referências
            if hasattr(model, 'eval'):
                model.eval()
            
            # Limpar cache CUDA
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
            
            # Garbage collection
            gc.collect()
            
            logger.debug("✅ Modelo descarregado com sucesso")
        
        except Exception as e:
            logger.warning(f"⚠️ Erro ao descarregar modelo: {e}")
    
    def clear_all_cache(self):
        """Limpa todo o cache de modelos (forçar reload)."""
        logger.info("🗑️ Limpando cache de modelos")
        self._model_cache.clear()
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        
        gc.collect()
    
    def get_vram_stats(self) -> dict:
        """
        Retorna estatísticas de uso de VRAM.
        
        Returns:
            Dict com estatísticas de VRAM (GB)
        """
        if not torch.cuda.is_available():
            return {
                "available": False,
                "low_vram_mode": self.low_vram_mode
            }
        
        allocated = torch.cuda.memory_allocated() / 1024**3  # GB
        reserved = torch.cuda.memory_reserved() / 1024**3
        free, total = torch.cuda.mem_get_info()
        free_gb = free / 1024**3
        total_gb = total / 1024**3
        
        return {
            "available": True,
            "low_vram_mode": self.low_vram_mode,
            "allocated_gb": round(allocated, 2),
            "reserved_gb": round(reserved, 2),
            "free_gb": round(free_gb, 2),
            "total_gb": round(total_gb, 2),
            "cached_models": len(self._model_cache) if not self.low_vram_mode else 0
        }


# Singleton global
_vram_manager = None


def get_vram_manager() -> VRAMManager:
    """Retorna o gerenciador global de VRAM (singleton)."""
    global _vram_manager
    if _vram_manager is None:
        _vram_manager = VRAMManager()
    return _vram_manager


def with_vram_management(model_key: str):
    """
    Decorator para gerenciar VRAM automaticamente.
    
    Uso:
        @with_vram_management('xtts')
        def synthesize(self, text, voice):
            # self.model já está carregado
            return self.model.process(text, voice)
        # Modelo descarregado automaticamente após retorno
    
    Args:
        model_key: Identificador único do modelo
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            vram_mgr = get_vram_manager()
            
            # Se não estiver em LOW_VRAM mode, executar normalmente
            if not vram_mgr.low_vram_mode:
                return func(self, *args, **kwargs)
            
            # Em LOW_VRAM mode, carregar e descarregar
            # Assume que a classe tem um método _load_model()
            if not hasattr(self, '_load_model'):
                logger.warning(f"Classe {self.__class__.__name__} não tem método _load_model()")
                return func(self, *args, **kwargs)
            
            with vram_mgr.load_model(model_key, self._load_model):
                result = func(self, *args, **kwargs)
            
            return result
        
        return wrapper
    return decorator


def clear_vram_cache():
    """Helper para limpar cache de VRAM manualmente."""
    vram_mgr = get_vram_manager()
    vram_mgr.clear_all_cache()
    logger.info("✅ Cache de VRAM limpo")


def get_vram_usage() -> dict:
    """Helper para obter estatísticas de VRAM."""
    vram_mgr = get_vram_manager()
    return vram_mgr.get_vram_stats()


# Singleton global instance
vram_manager = get_vram_manager()
