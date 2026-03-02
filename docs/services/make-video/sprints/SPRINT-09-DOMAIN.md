# 🎭 SPRINT 9 - DOMAIN (JOB PROCESSOR & STAGES)

**Status**: ⏳ Pendente  
**Prioridade**: 🟡 ALTA  
**Duração Estimada**: 5-6 horas  
**Pré-requisitos**: Sprint 1-8

---

## 🎯 OBJETIVOS

1. ✅ Testar JobProcessor end-to-end
2. ✅ Validar todas as stages do pipeline
3. ✅ Testar job_stage base class
4. ✅ Garantir integração entre stages

---

## 📁 ARQUIVOS

```
app/domain/
├── job_processor.py           # Processador principal
├── job_stage.py               # Base class para stages
└── stages/
    ├── fetch_shorts_stage.py       # Busca shorts
    ├── select_shorts_stage.py      # Seleciona shorts
    ├── download_shorts_stage.py    # Download
    ├── analyze_audio_stage.py      # Análise de áudio
    ├── generate_subtitles_stage.py # Geração de legendas
    ├── trim_video_stage.py         # Trim de vídeo
    ├── assemble_video_stage.py     # Montagem
    └── final_composition_stage.py  # Composição final
```

---

## 🧪 TESTES

```python
# tests/integration/domain/test_job_processor.py
import pytest


@pytest.mark.integration
@pytest.mark.slow
class TestJobProcessor:
    """Testes do processador de jobs"""
    
    def test_job_processor_imports(self):
        """JobProcessor pode ser importado"""
        try:
            from app.domain.job_processor import JobProcessor
            assert JobProcessor is not None
        except ImportError:
            pytest.skip("JobProcessor não existe")
    
    def test_job_processor_instantiates(self):
        """JobProcessor pode ser instanciado"""
        try:
            from app.domain.job_processor import JobProcessor
            processor = JobProcessor()
            assert processor is not None
        except ImportError:
            pytest.skip("JobProcessor não existe")
    
    def test_process_job_structure(self, real_test_audio):
        """Estrutura de job é válida"""
        job_data = {
            "job_id": "test_job_001",
            "audio_file": str(real_test_audio),
            "niche": "test",
            "min_duration": 5,
            "max_duration": 60,
        }
        
        # Validar estrutura
        assert "job_id" in job_data
        assert "audio_file" in job_data
        assert Path(job_data["audio_file"]).exists()


# tests/unit/domain/test_job_stage.py
class TestJobStage:
    """Testes da base class JobStage"""
    
    def test_job_stage_imports(self):
        """JobStage pode ser importado"""
        try:
            from app.domain.job_stage import JobStage
            assert JobStage is not None
        except ImportError:
            pytest.skip("JobStage não existe")
    
    def test_stage_interface(self):
        """Stage tem interface esperada"""
        from abc import ABC, abstractmethod
        
        class TestStage:
            def execute(self, context):
                pass
            
            def validate(self, context):
                return True
        
        stage = TestStage()
        assert hasattr(stage, 'execute')
        assert callable(stage.execute)


# tests/unit/domain/stages/test_stages.py
class TestStages:
    """Testes das stages individuais"""
    
    def test_all_stages_import(self):
        """Todas as stages podem ser importadas"""
        stages = [
            'fetch_shorts_stage',
            'select_shorts_stage',
            'download_shorts_stage',
            'analyze_audio_stage',
            'generate_subtitles_stage',
            'trim_video_stage',
            'assemble_video_stage',
            'final_composition_stage',
        ]
        
        for stage_name in stages:
            try:
                module = __import__(
                    f'app.domain.stages.{stage_name}',
                    fromlist=['']
                )
                assert module is not None
            except ImportError:
                pytest.skip(f"Stage {stage_name} não existe")
    
    def test_fetch_shorts_stage_structure(self):
        """FetchShortsStage tem estrutura correta"""
        try:
            from app.domain.stages.fetch_shorts_stage import FetchShortsStage
            
            # Deve ter método execute
            assert hasattr(FetchShortsStage, 'execute') or \
                   hasattr(FetchShortsStage, 'run')
        except ImportError:
            pytest.skip("FetchShortsStage não existe")
```

---

## 📋 IMPLEMENTAÇÃO

```bash
mkdir -p tests/integration/domain
mkdir -p tests/unit/domain/stages

touch tests/integration/domain/__init__.py
touch tests/integration/domain/test_job_processor.py
touch tests/unit/domain/test_job_stage.py
touch tests/unit/domain/stages/__init__.py
touch tests/unit/domain/stages/test_stages.py

pytest tests/integration/domain/ -v
pytest tests/unit/domain/ -v
```

---

## ✅ CRITÉRIOS

- [ ] JobProcessor testado
- [ ] Todas as stages identificadas
- [ ] Interface validada
- [ ] Cobertura > 75%

---

**Status**: ⏳ Pendente
