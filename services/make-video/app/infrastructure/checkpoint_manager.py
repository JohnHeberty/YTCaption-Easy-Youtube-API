"""
Granular Checkpoint System - Sprint-02

Sistema de checkpoints granulares dentro de cada etapa do processamento.
Permite recuperação precisa de jobs interrompidos.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)

from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class CheckpointStage(str, Enum):
    """Estágios de processamento com checkpoints"""
    ANALYZING_AUDIO = "analyzing_audio"
    FETCHING_SHORTS = "fetching_shorts"
    DOWNLOADING_SHORTS = "downloading_shorts"
    VALIDATING_SHORTS = "validating_shorts"
    SELECTING_SHORTS = "selecting_shorts"
    BUILDING_VIDEO = "building_video"
    COMPLETED = "completed"


@dataclass
class CheckpointData:
    """Dados de um checkpoint granular"""
    stage: str  # CheckpointStage
    progress: float  # 0.0 - 1.0
    completed_items: int  # Items processados
    total_items: int  # Total de items
    item_ids: List[str]  # IDs dos items completados (ex: video_ids)
    metadata: Dict[str, Any]  # Dados adicionais específicos do estágio
    timestamp: str  # ISO timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CheckpointData":
        """Cria instância a partir de dicionário"""
        return cls(**data)


class GranularCheckpointManager:
    """
    Gerenciador de checkpoints granulares.
    
    Permite salvar progresso incremental dentro de cada etapa,
    não apenas entre etapas (como o checkpoint básico atual).
    
    Exemplo:
        Baixando 50 shorts:
        - Checkpoint básico: Só salva DEPOIS de baixar todos os 50
        - Checkpoint granular: Salva a cada 10 shorts (10/50, 20/50, etc)
        
        Se crashar no short 45, checkpoint granular recupera de 40.
        Checkpoint básico teria que refazer todos os 50.
    """
    
    def __init__(self, redis_store):
        """
        Args:
            redis_store: Instância do RedisJobStore
        """
        self.redis_store = redis_store
        self.checkpoint_interval = 10  # Salvar a cada N items
        logger.info("✅ GranularCheckpointManager initialized")
    
    async def save_checkpoint(
        self,
        job_id: str,
        stage: CheckpointStage,
        completed_items: int,
        total_items: int,
        item_ids: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Salva checkpoint granular.
        
        Args:
            job_id: ID do job
            stage: Estágio atual
            completed_items: Número de items completados
            total_items: Total de items
            item_ids: Lista de IDs dos items completados
            metadata: Dados adicionais (opcional)
        """
        progress = completed_items / total_items if total_items > 0 else 0.0
        
        checkpoint = CheckpointData(
            stage=stage.value,
            progress=progress,
            completed_items=completed_items,
            total_items=total_items,
            item_ids=item_ids,
            metadata=metadata or {},
            timestamp=now_brazil().isoformat()
        )
        
        # Salvar no Redis
        key = f"checkpoint:granular:{job_id}"
        await self.redis_store.redis.set(
            key,
            json.dumps(checkpoint.to_dict()),
            ex=86400  # 24 horas TTL
        )
        
        logger.info(
            f"📍 Granular checkpoint saved: {job_id} - {stage.value} "
            f"({completed_items}/{total_items} = {progress:.1%})"
        )
    
    async def load_checkpoint(self, job_id: str) -> Optional[CheckpointData]:
        """
        Carrega checkpoint granular.
        
        Args:
            job_id: ID do job
        
        Returns:
            CheckpointData se existe, None caso contrário
        """
        key = f"checkpoint:granular:{job_id}"
        data = await self.redis_store.redis.get(key)
        
        if data is None:
            logger.debug(f"No granular checkpoint found for {job_id}")
            return None
        
        try:
            checkpoint_dict = json.loads(data)
            checkpoint = CheckpointData.from_dict(checkpoint_dict)
            
            logger.info(
                f"📍 Granular checkpoint loaded: {job_id} - {checkpoint.stage} "
                f"({checkpoint.completed_items}/{checkpoint.total_items})"
            )
            
            return checkpoint
        
        except Exception as e:
            logger.error(f"Failed to parse checkpoint for {job_id}: {e}")
            return None
    
    async def should_save_checkpoint(
        self,
        completed_items: int,
        total_items: int
    ) -> bool:
        """
        Determina se deve salvar checkpoint baseado no intervalo.
        
        Args:
            completed_items: Número de items completados
            total_items: Total de items
        
        Returns:
            True se deve salvar checkpoint
        """
        # Salvar a cada checkpoint_interval items
        if completed_items % self.checkpoint_interval == 0:
            return True
        
        # Salvar no final
        if completed_items == total_items:
            return True
        
        return False
    
    async def get_remaining_items(
        self,
        job_id: str,
        all_items: List[Any],
        item_id_extractor: callable
    ) -> List[Any]:
        """
        Retorna items restantes baseado no checkpoint.
        
        Args:
            job_id: ID do job
            all_items: Lista completa de items a processar
            item_id_extractor: Função que extrai ID de um item
        
        Returns:
            Lista de items ainda não processados
        
        Example:
            remaining = await manager.get_remaining_items(
                job_id="abc123",
                all_items=shorts,
                item_id_extractor=lambda s: s.video_id
            )
        """
        checkpoint = await self.load_checkpoint(job_id)
        
        # Se não há checkpoint, processar tudo
        if checkpoint is None:
            return all_items
        
        # Filtrar items já processados
        completed_ids = set(checkpoint.item_ids)
        remaining = [
            item for item in all_items
            if item_id_extractor(item) not in completed_ids
        ]
        
        logger.info(
            f"📍 Recovery: {len(remaining)}/{len(all_items)} items remaining "
            f"({len(completed_ids)} already completed)"
        )
        
        return remaining
    
    async def clear_checkpoint(self, job_id: str):
        """
        Remove checkpoint após job completar com sucesso.
        
        Args:
            job_id: ID do job
        """
        key = f"checkpoint:granular:{job_id}"
        await self.redis_store.redis.delete(key)
        logger.debug(f"Granular checkpoint cleared for {job_id}")
    
    def set_checkpoint_interval(self, interval: int):
        """
        Configura intervalo de checkpoint.
        
        Args:
            interval: Número de items entre checkpoints
        """
        self.checkpoint_interval = max(1, interval)
        logger.info(f"Checkpoint interval set to {self.checkpoint_interval}")


# Helper functions para integração com celery_tasks.py

async def save_download_checkpoint(
    checkpoint_manager: GranularCheckpointManager,
    job_id: str,
    downloaded_shorts: List[Any],
    total_shorts: int,
    shorts_list: List[Any]
):
    """
    Salva checkpoint durante download de shorts.
    
    Args:
        checkpoint_manager: Instância do manager
        job_id: ID do job
        downloaded_shorts: Lista de shorts já baixados
        total_shorts: Total de shorts a baixar
        shorts_list: Lista completa de shorts
    """
    if await checkpoint_manager.should_save_checkpoint(
        len(downloaded_shorts),
        total_shorts
    ):
        await checkpoint_manager.save_checkpoint(
            job_id=job_id,
            stage=CheckpointStage.DOWNLOADING_SHORTS,
            completed_items=len(downloaded_shorts),
            total_items=total_shorts,
            item_ids=[s.video_id for s in downloaded_shorts],
            metadata={
                "download_method": "batch",
                "batch_size": 5
            }
        )


async def recover_download_progress(
    checkpoint_manager: GranularCheckpointManager,
    job_id: str,
    shorts_list: List[Any]
) -> List[Any]:
    """
    Recupera progresso de download.
    
    Args:
        checkpoint_manager: Instância do manager
        job_id: ID do job
        shorts_list: Lista completa de shorts
    
    Returns:
        Lista de shorts ainda não baixados
    """
    return await checkpoint_manager.get_remaining_items(
        job_id=job_id,
        all_items=shorts_list,
        item_id_extractor=lambda s: s.video_id
    )


# Singleton global (inicializado com redis_store no celery_tasks.py)
_checkpoint_manager = None


def get_checkpoint_manager(redis_store=None) -> Optional[GranularCheckpointManager]:
    """
    Retorna instância singleton do GranularCheckpointManager.
    
    Args:
        redis_store: RedisJobStore (necessário na primeira chamada)
    
    Returns:
        GranularCheckpointManager ou None se não inicializado
    """
    global _checkpoint_manager
    
    if _checkpoint_manager is None and redis_store is not None:
        _checkpoint_manager = GranularCheckpointManager(redis_store)
    
    return _checkpoint_manager
