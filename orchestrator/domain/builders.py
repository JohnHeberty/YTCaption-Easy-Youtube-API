"""Builders para respostas do orchestrator."""
from typing import Dict, Any, Optional

# Try to import from common.job_utils, fall back to None if not available
try:
    from common.job_utils.models import StageInfo as PipelineStage, StandardJob as PipelineJobBase
    PipelineJob = type('PipelineJob', (PipelineJobBase,), {})
except ImportError:
    PipelineJob = None
    PipelineStage = None


class StageResponseBuilder:
    """Builder para respostas de stages do pipeline.
    
    Centraliza a construção de respostas para evitar duplicação de código
    nos endpoints da API.
    """
    
    @staticmethod
    def build_stage_response(stage) -> Dict[str, Any]:
        """Constroi resposta para um stage.
        
        Args:
            stage: Stage do pipeline
            
        Returns:
            Dicionario com dados do stage formatados
        """
        if stage is None:
            return {"status": "unknown", "message": "Stage not available"}
            
        status_value = (
            stage.status.value 
            if hasattr(stage.status, 'value') 
            else str(stage.status)
        )
        
        return {
            "name": stage.name,
            "status": status_value,
            "progress": stage.progress,
            "message": stage.progress_message,
        }

    @staticmethod
    def build_all_stages(job) -> Dict[str, Any]:
        """Constroi respostas para todos os stages de um job.
        
        Args:
            job: Job do pipeline
            
        Returns:
            Dicionario com todos os stages
        """
        if not job or not hasattr(job, 'stages') or not job.stages:
            return {}
            
        return {
            stage.name: StageResponseBuilder.build_stage_response(stage)
            for stage in job.stages
        }