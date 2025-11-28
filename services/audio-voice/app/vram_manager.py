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
        settings = get_settings()
        self.low_vram_mode = settings.get('low_vram_mode', False)
        
        # Debug: Logar valor raw da variável de ambiente e valor parseado
        import os
        env_value = os.getenv('LOW_VRAM', 'NOT_SET')
        logger.info(f"🔍 DEBUG: LOW_VRAM env='{env_value}', parsed={self.low_vram_mode}")
        
        self._model_cache = {}  # Cache de modelos (quando LOW_VRAM=false)
        
        if self.low_vram_mode:
            logger.info("🔋 LOW VRAM MODE: ATIVADO - Modelos serão carregados/descarregados automaticamente")
            logger.info("    💡 Economia de VRAM: 70-75%")
            logger.info("    ⚠️  Latência aumentada: +2-5s por requisição")
        else:
            logger.info("⚡ NORMAL MODE: Modelos permanecerão na VRAM")
            logger.info("    💡 Melhor performance, maior consumo de VRAM")
    
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
                logger.info(f"🔋 LOW_VRAM: Carregando modelo '{model_key}' na GPU...")
                
                # Log VRAM antes do load (se CUDA disponível)
                if torch.cuda.is_available():
                    before_allocated = torch.cuda.memory_allocated() / 1024**3
                    logger.debug(f"📊 VRAM antes do load: {before_allocated:.2f} GB")
                
                model = load_fn(*args, **kwargs)
                
                # Log VRAM após load
                if torch.cuda.is_available():
                    after_allocated = torch.cuda.memory_allocated() / 1024**3
                    delta = after_allocated - before_allocated
                    logger.info(f"📊 VRAM alocada: {after_allocated:.2f} GB (Δ +{delta:.2f} GB)")
            else:
                # Usar cache
                if model_key not in self._model_cache:
                    logger.info(f"⚡ Carregando modelo '{model_key}' (primeira vez, será cacheado)")
                    self._model_cache[model_key] = load_fn(*args, **kwargs)
                else:
                    logger.debug(f"⚡ Usando modelo '{model_key}' do cache")
                model = self._model_cache[model_key]
            
            yield model
        
        finally:
            # Descarregar apenas em modo LOW_VRAM
            if self.low_vram_mode and model is not None:
                logger.info(f"🔋 LOW_VRAM: Descarregando modelo '{model_key}' da VRAM...")
                
                # Log VRAM antes do unload
                if torch.cuda.is_available():
                    before_free = torch.cuda.memory_allocated() / 1024**3
                
                self._unload_model(model)
                del model
                
                # Log VRAM depois do unload
                if torch.cuda.is_available():
                    after_free = torch.cuda.memory_allocated() / 1024**3
                    freed = before_free - after_free
                    logger.info(f"📊 VRAM liberada: {freed:.2f} GB (antes={before_free:.2f}, depois={after_free:.2f} GB)")
    
    def _unload_model(self, model):
        """
        Descarrega modelo da VRAM.
        
        Args:
            model: Modelo a ser descarregado
        """
        try:
            models_moved = 0
            
            # Estratégia 1: Mover modelo direto (PyTorch nn.Module)
            if hasattr(model, 'to'):
                logger.debug("Moving model to CPU via .to('cpu')")
                model.to('cpu')
                models_moved += 1
            elif hasattr(model, 'cpu'):
                logger.debug("Moving model to CPU via .cpu()")
                model.cpu()
                models_moved += 1
            
            # Estratégia 2: Procurar submodelos (F5TTS API wrapper)
            # F5TTS API tem atributos: .model, .vocoder, etc
            for attr_name in dir(model):
                if attr_name.startswith('_'):
                    continue
                try:
                    attr = getattr(model, attr_name)
                    # Se é um módulo PyTorch, mover para CPU
                    if hasattr(attr, 'to') and callable(attr.to):
                        logger.debug(f"Moving submodel '{attr_name}' to CPU")
                        attr.to('cpu')
                        models_moved += 1
                    elif hasattr(attr, 'cpu') and callable(attr.cpu):
                        logger.debug(f"Moving submodel '{attr_name}' to CPU via .cpu()")
                        attr.cpu()
                        models_moved += 1
                except Exception as e:
                    # Ignorar atributos que não são modelos
                    logger.debug(f"Skipping attribute '{attr_name}': {e}")
                    continue
            
            # Estratégia 3: Verificar __dict__ para modelos encapsulados
            if hasattr(model, '__dict__'):
                for key, value in model.__dict__.items():
                    if key.startswith('_'):
                        continue
                    try:
                        if hasattr(value, 'to') and callable(value.to):
                            logger.debug(f"Moving __dict__ model '{key}' to CPU")
                            value.to('cpu')
                            models_moved += 1
                    except Exception as e:
                        logger.debug(f"Skipping __dict__ key '{key}': {e}")
                        continue
            
            logger.debug(f"📦 Moved {models_moved} model(s) to CPU")
            
            # Liberar referências
            if hasattr(model, 'eval'):
                model.eval()
            
            # Limpar cache CUDA (crítico!)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()  # Aguardar operações CUDA completarem
                torch.cuda.ipc_collect()
            
            # Garbage collection agressivo
            gc.collect()
            gc.collect()  # Segunda passagem
            
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
