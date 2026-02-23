"""Testes unitários para JobStage base class"""
import pytest
from abc import ABC, abstractmethod
from pathlib import Path


@pytest.mark.unit
class TestJobStageModule:
    """Testes de módulo job_stage"""
    
    def test_job_stage_module_imports(self):
        """Módulo job_stage pode ser importado"""
        from app.domain import job_stage
        assert job_stage is not None
    
    def test_job_stage_class_exists(self):
        """JobStage class existe"""
        from app.domain.job_stage import JobStage
        assert JobStage is not None
        assert issubclass(JobStage, ABC), "JobStage deve ser abstract"
    
    def test_stage_context_exists(self):
        """StageContext dataclass existe"""
        from app.domain.job_stage import StageContext
        assert StageContext is not None
    
    def test_stage_result_exists(self):
        """StageResult dataclass existe"""
        from app.domain.job_stage import StageResult
        assert StageResult is not None
    
    def test_stage_status_enum_exists(self):
        """StageStatus enum existe"""
        from app.domain.job_stage import StageStatus
        assert StageStatus is not None
        assert hasattr(StageStatus, 'NOT_STARTED')
        assert hasattr(StageStatus, 'IN_PROGRESS')
        assert hasattr(StageStatus, 'COMPLETED')
        assert hasattr(StageStatus, 'FAILED')


@pytest.mark.unit
class TestJobStageInterface:
    """Testes de interface JobStage"""
    
    def test_job_stage_has_abstract_methods(self):
        """JobStage tem métodos abstratos esperados"""
        from app.domain.job_stage import JobStage
        
        # Verificar que é abstract
        assert hasattr(JobStage, '__abstractmethods__')
        
        # Deve ter método execute
        assert 'execute' in JobStage.__abstractmethods__
    
    def test_job_stage_has_template_methods(self):
        """JobStage tem métodos template (não abstratos)"""
        from app.domain.job_stage import JobStage
        
        # Métodos que devem existir
        assert hasattr(JobStage, 'run'), "Deve ter método run()"
        assert hasattr(JobStage, 'validate'), "Deve ter método validate()"
    
    def test_real_stage_implements_interface(self):
        """Stage real implementa interface corretamente"""
        from app.domain.stages.fetch_shorts_stage import FetchShortsStage
        from app.domain.job_stage import JobStage
        
        # Deve herdar de JobStage
        assert issubclass(FetchShortsStage, JobStage)
        
        # Deve implementar execute
        assert hasattr(FetchShortsStage, 'execute')
        assert callable(FetchShortsStage.execute)


@pytest.mark.unit
class TestStageContext:
    """Testes de StageContext dataclass"""
    
    def test_stage_context_creation(self):
        """StageContext pode ser criado"""
        from app.domain.job_stage import StageContext
        
        context = StageContext(
            job_id="test_001",
            query="test query",
            max_shorts=10,
            aspect_ratio="9:16",
            crop_position="center",
            subtitle_language="en",
            subtitle_style={},
            settings={}
        )
        
        assert context.job_id == "test_001"
        assert context.query == "test query"
        assert context.max_shorts == 10
    
    def test_stage_context_has_required_fields(self):
        """StageContext tem campos obrigatórios"""
        from app.domain.job_stage import StageContext
        import inspect
        
        sig = inspect.signature(StageContext)
        params = sig.parameters
        
        # Campos obrigatórios
        assert 'job_id' in params
        assert 'query' in params
        assert 'max_shorts' in params
        assert 'settings' in params
    
    def test_stage_context_accumulates_results(self):
        """StageContext acumula resultados de stages"""
        from app.domain.job_stage import StageContext, StageResult, StageStatus
        
        context = StageContext(
            job_id="test_001",
            query="test",
            max_shorts=10,
            aspect_ratio="9:16",
            crop_position="center",
            subtitle_language="en",
            subtitle_style={},
            settings={}
        )
        
        # Deve ter dict de results
        assert hasattr(context, 'results')
        assert isinstance(context.results, dict)
        
        # Pode adicionar result
        result = StageResult(
            status=StageStatus.COMPLETED,
            data={'test': 'data'},
            duration_seconds=1.5
        )
        context.results['test_stage'] = result
        
        assert 'test_stage' in context.results
        assert context.results['test_stage'].status == StageStatus.COMPLETED


@pytest.mark.unit
class TestStageResult:
    """Testes de StageResult dataclass"""
    
    def test_stage_result_creation(self):
        """StageResult pode ser criado"""
        from app.domain.job_stage import StageResult, StageStatus
        
        result = StageResult(
            status=StageStatus.COMPLETED,
            data={'key': 'value'},
            duration_seconds=2.5
        )
        
        assert result.status == StageStatus.COMPLETED
        assert result.data['key'] == 'value'
        assert result.duration_seconds == 2.5
    
    def test_stage_result_success_property(self):
        """StageResult tem propriedade success"""
        from app.domain.job_stage import StageResult, StageStatus
        
        # Sucesso
        success_result = StageResult(
            status=StageStatus.COMPLETED,
            data={}
        )
        assert success_result.success is True
        
        # Falha
        failed_result = StageResult(
            status=StageStatus.FAILED,
            data={}
        )
        assert failed_result.success is False
    
    def test_stage_result_to_dict(self):
        """StageResult serializa para dict"""
        from app.domain.job_stage import StageResult, StageStatus
        
        result = StageResult(
            status=StageStatus.COMPLETED,
            data={'test': 123},
            duration_seconds=1.5
        )
        
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert 'status' in result_dict
        assert 'data' in result_dict
        assert 'duration_seconds' in result_dict
        assert result_dict['status'] == 'completed'


@pytest.mark.unit  
class TestStageStatus:
    """Testes de StageStatus enum"""
    
    def test_stage_status_values(self):
        """StageStatus tem todos os valores esperados"""
        from app.domain.job_stage import StageStatus
        
        assert StageStatus.NOT_STARTED.value == "not_started"
        assert StageStatus.IN_PROGRESS.value == "in_progress"
        assert StageStatus.COMPLETED.value == "completed"
        assert StageStatus.FAILED.value == "failed"
    
    def test_stage_status_comparison(self):
        """StageStatus pode ser comparado"""
        from app.domain.job_stage import StageStatus
        
        status1 = StageStatus.COMPLETED
        status2 = StageStatus.COMPLETED
        status3 = StageStatus.FAILED
        
        assert status1 == status2
        assert status1 != status3
