"""
TESTES MÓDULO 4: Core (config, constants, models)
Testa componentes fundamentais do sistema
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestConfig:
    """Testes para app.core.config"""
    
    def test_get_settings(self):
        """Test 4.1: Carregar settings"""
        print("\n🧪 TEST 4.1: Carregando settings...")
        
        from app.core.config import get_settings
        
        settings = get_settings()
        
        assert settings is not None, "Settings não pode ser None"
        assert isinstance(settings, dict), f"Settings deve ser dict, é {type(settings)}"
        
        # Verificar keys essenciais
        essential_keys = ['redis_url', 'temp_dir', 'output_dir']
        for key in essential_keys:
            assert key in settings, f"Key essencial '{key}' não encontrada"
            assert settings[key] is not None, f"Key '{key}' não pode ser None"
        
        print(f"✅ Settings carregadas com {len(settings)} configurações")
        print(f"   redis_url: {settings['redis_url'][:30]}...")
        print(f"   temp_dir: {settings['temp_dir']}")


class TestConstants:
    """Testes para app.core.constants"""
    
    def test_processing_limits(self):
        """Test 4.2: Constants - ProcessingLimits"""
        print("\n🧪 TEST 4.2: ProcessingLimits...")
        
        from app.core.constants import ProcessingLimits
        
        # Verificar que constantes existem e são razoáveis
        assert hasattr(ProcessingLimits, 'MAX_SHORTS'), "MAX_SHORTS não definido"
        assert ProcessingLimits.MAX_SHORTS > 0, "MAX_SHORTS deve ser positivo"
        
        print(f"✅ ProcessingLimits OK")
        print(f"   MAX_SHORTS: {ProcessingLimits.MAX_SHORTS}")
    
    def test_aspect_ratios(self):
        """Test 4.3: Constants - AspectRatios"""
        print("\n🧪 TEST 4.3: AspectRatios...")
        
        from app.core.constants import AspectRatios
        
        # Verificar ratios comuns
        assert hasattr(AspectRatios, 'VERTICAL'), "VERTICAL não definido"
        assert hasattr(AspectRatios, 'HORIZONTAL'), "HORIZONTAL não definido"
        
        print(f"✅ AspectRatios OK")
        print(f"   VERTICAL: {AspectRatios.VERTICAL}")
        print(f"   HORIZONTAL: {AspectRatios.HORIZONTAL}")


class TestModels:
    """Testes para app.core.models"""
    
    def test_job_status_enum(self):
        """Test 4.4: JobStatus enum"""
        print("\n🧪 TEST 4.4: JobStatus enum...")
        
        from app.core.models import JobStatus
        
        # Verificar status principais
        essential_statuses = ['QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED']
        for status in essential_statuses:
            assert hasattr(JobStatus, status), f"Status '{status}' não definido"
        
        print(f"✅ JobStatus enum OK")
        print(f"   Statuses disponíveis: {[s.name for s in JobStatus]}")
    
    def test_job_model_creation(self):
        """Test 4.5: Criar modelo Job"""
        print("\n🧪 TEST 4.5: Criando modelo Job...")
        
        from app.core.models import Job, JobStatus
        from datetime import datetime
        
        job = Job(
            job_id="test_job_123",
            status=JobStatus.QUEUED,
            query="test query",
            max_shorts=5,
            aspect_ratio="9:16",
            created_at=datetime.utcnow()
        )
        
        assert job.job_id == "test_job_123"
        assert job.status == JobStatus.QUEUED
        assert job.query == "test query"
        
        print(f"✅ Job criado com sucesso")
        print(f"   job_id: {job.job_id}")
        print(f"   status: {job.status}")
    
    def test_stage_info_model(self):
        """Test 4.6: Modelo StageInfo"""
        print("\n🧪 TEST 4.6: StageInfo model...")
        
        from app.core.models import StageInfo, JobStatus
        from datetime import datetime
        
        stage = StageInfo(
            name="test_stage",
            status=JobStatus.PROCESSING,
            started_at=datetime.utcnow()
        )
        
        assert stage.name == "test_stage"
        assert stage.status == JobStatus.PROCESSING
        assert stage.started_at is not None
        
        print(f"✅ StageInfo criado")
        print(f"   name: {stage.name}")
        print(f"   status: {stage.status}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
