"""
Checkpoint Manager for Audio Transcription

Sistema de checkpoints granulares para recuperação de transcrições interrompidas.
Salva progresso incremental durante transcrições longas.

Adaptado do padrão make-video para transcrições de áudio.
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from common.log_utils import get_logger

logger = get_logger(__name__)

class TranscriptionStage(str, Enum):
    """Estágios de processamento de transcrição"""
    PREPROCESSING = "preprocessing"  # Normalização, conversão de formato
    MODEL_LOADING = "model_loading"  # Carregando modelo Whisper
    TRANSCRIBING = "transcribing"  # Transcrição em progresso
    POSTPROCESSING = "postprocessing"  # Formatação, timestamps
    COMPLETED = "completed"  # Finalizado

@dataclass
class CheckpointData:
    """Dados de um checkpoint granular"""
    stage: str  # TranscriptionStage
    progress: float  # 0.0 - 1.0
    processed_seconds: float  # Segundos de áudio processados
    total_seconds: float  # Total de segundos de áudio
    segments_completed: int  # Número de segmentos transcritos
    metadata: Dict[str, Any]  # Dados adicionais (texto parcial, timestamps, etc)
    timestamp: str  # ISO timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CheckpointData":
        """Cria instância a partir de dicionário"""
        return cls(**data)

class CheckpointManager:
    """
    Gerenciador de checkpoints para transcrições de áudio.
    
    Permite recuperar transcrições interrompidas salvando progresso incremental.
    
    Exemplo:
        Transcrição de 1 hora de áudio:
        - Checkpoint a cada 5 minutos
        - Se crashar aos 47 minutos, recupera de 45 minutos
        - Sem checkpoint: teria que refazer 1 hora completa
    
    Use cases:
    - Transcrições longas (>30 minutos)
    - Modelos grandes (large-v3) com risco de GPU OOM
    - Network instável (download de models)
    - Processamento distribuído (Celery worker crashes)
    """
    
    def __init__(self, redis_store):
        """
        Args:
            redis_store: Instância do RedisJobStore
        """
        self.redis_store = redis_store
        self.checkpoint_interval_seconds = 300  # Salvar a cada 5 minutos
        logger.info("✅ CheckpointManager initialized (interval=5min)")
    
    def _checkpoint_key(self, job_id: str) -> str:
        """Gera chave Redis para checkpoint"""
        return f"checkpoint:{job_id}"
    
    async def save_checkpoint(
        self,
        job_id: str,
        stage: TranscriptionStage,
        processed_seconds: float,
        total_seconds: float,
        segments_completed: int,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Salva checkpoint granular.
        
        Args:
            job_id: ID do job
            stage: Estágio atual
            processed_seconds: Segundos de áudio processados
            total_seconds: Total de segundos
            segments_completed: Número de segmentos transcritos
            metadata: Dados adicionais (texto parcial, timestamps, etc)
        """
        progress = processed_seconds / total_seconds if total_seconds > 0 else 0.0
        
        checkpoint = CheckpointData(
            stage=stage.value,
            progress=progress,
            processed_seconds=processed_seconds,
            total_seconds=total_seconds,
            segments_completed=segments_completed,
            metadata=metadata or {},
            timestamp=now_brazil().isoformat()
        )
        
        # Salva no Redis
        key = self._checkpoint_key(job_id)
        data = json.dumps(checkpoint.to_dict())
        
        # TTL de 24 horas (mesma do job)
        self.redis_store.redis.setex(key, 86400, data)
        
        logger.info(
            f"💾 Checkpoint saved for job {job_id}: "
            f"{stage.value} ({progress*100:.1f}%, {processed_seconds:.1f}s/{total_seconds:.1f}s)"
        )
    
    def get_checkpoint(self, job_id: str) -> Optional[CheckpointData]:
        """
        Recupera checkpoint do Redis.
        
        Args:
            job_id: ID do job
        
        Returns:
            CheckpointData se existe, None caso contrário
        """
        key = self._checkpoint_key(job_id)
        data = self.redis_store.redis.get(key)
        
        if not data:
            return None
        
        try:
            checkpoint_dict = json.loads(data)
            checkpoint = CheckpointData.from_dict(checkpoint_dict)
            logger.info(
                f"📂 Checkpoint loaded for job {job_id}: "
                f"{checkpoint.stage} ({checkpoint.progress*100:.1f}%)"
            )
            return checkpoint
        except Exception as e:
            logger.error(f"❌ Error deserializing checkpoint {job_id}: {e}")
            return None
    
    def should_save_checkpoint(
        self,
        job_id: str,
        processed_seconds: float,
        last_checkpoint_seconds: float
    ) -> bool:
        """
        Verifica se deve salvar checkpoint baseado no intervalo.
        
        Args:
            job_id: ID do job
            processed_seconds: Segundos processados atualmente
            last_checkpoint_seconds: Segundos do último checkpoint
        
        Returns:
            True se deve salvar checkpoint
        """
        elapsed = processed_seconds - last_checkpoint_seconds
        return elapsed >= self.checkpoint_interval_seconds
    
    def delete_checkpoint(self, job_id: str):
        """
        Remove checkpoint do Redis (quando job completa ou falha).
        
        Args:
            job_id: ID do job
        """
        key = self._checkpoint_key(job_id)
        self.redis_store.redis.delete(key)
        logger.info(f"🗑️  Checkpoint deleted for job {job_id}")
    
    def list_checkpoints(self) -> List[str]:
        """
        Lista todos os job_ids com checkpoints ativos.
        
        Returns:
            Lista de job_ids
        """
        pattern = "checkpoint:*"
        keys = self.redis_store.redis.keys(pattern)
        job_ids = [key.decode('utf-8').replace('checkpoint:', '') for key in keys]
        return job_ids
    
    async def resume_from_checkpoint(
        self,
        job_id: str
    ) -> Optional[CheckpointData]:
        """
        Recupera checkpoint para resumir transcrição.
        
        IMPORTANTE: Esta função apenas retorna o checkpoint.
        A lógica de resumo (re-iniciar transcrição do ponto correto)
        deve ser implementada no TranscriptionProcessor.
        
        Args:
            job_id: ID do job
        
        Returns:
            CheckpointData se existe, None caso contrário
        """
        checkpoint = self.get_checkpoint(job_id)
        
        if checkpoint:
            logger.info(
                f"♻️  Resuming job {job_id} from checkpoint: "
                f"{checkpoint.stage} ({checkpoint.progress*100:.1f}%)"
            )
        
        return checkpoint
