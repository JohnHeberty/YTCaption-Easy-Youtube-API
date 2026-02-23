# 🏗️ SPRINT 8 - PIPELINE (ORQUESTRAÇÃO PRINCIPAL)

**Status**: ⏳ Pendente  
**Prioridade**: 🔴 CRÍTICA  
**Duração Estimada**: 5-6 horas  
**Pré-requisitos**: Sprints 1-7 completas

---

## 🎯 OBJETIVOS

**SPRINT MAIS CRÍTICA** - Testa o arquivo onde ocorre o bug de produção:

1. 🔧 **VALIDAR**: Bug `KeyError: 'transform_dir'` foi corrigido
2. ✅ Testar método `cleanup_orphaned_files()` sem erros
3. ✅ Validar pipeline completo end-to-end
4. ✅ Testar todas as transições de estado (download → transform → validate → approve/reject)
5. ✅ Garantir integração com detector de legendas
6. ✅ Validar blacklist/approved system

---

## 📁 ARQUIVOS NO ESCOPO

```
app/pipeline/
├── __init__.py
└── video_pipeline.py    # 1040 linhas - ⚠️ CONTÉM O BUG NA LINHA 282
```

### Métodos Críticos em video_pipeline.py

- `__init__()` - Inicialização  
- `_ensure_directories()` - Cria diretórios  
- **`cleanup_orphaned_files()`** - ⚠️ **LINHA 282 - BUG AQUI**
- `transform_video()` - H264 conversion
- `move_to_validation()` - Move para validação
- `validate_video()` - Detecta legendas
- `approve_video()` - Aprova vídeo
- `reject_video()` - Rejeita vídeo

---

## 🧪 TESTES - `tests/integration/pipeline/test_video_pipeline.py`

```python
"""
Testes CRÍTICOS do VideoPipeline
Valida que o BUG de produção foi corrigido
"""
import pytest
import shutil
import subprocess
from pathlib import Path
from app.pipeline.video_pipeline import VideoPipeline


class TestVideoPipelineInit:
    """Testes de inicialização"""
    
    def test_pipeline_instantiates(self):
        """Pipeline pode ser instanciado"""
        pipeline = VideoPipeline()
        assert pipeline is not None
    
    def test_pipeline_has_settings(self):
        """Pipeline tem settings carregadas"""
        pipeline = VideoPipeline()
        assert pipeline.settings is not None
        assert isinstance(pipeline.settings, dict)
    
    def test_pipeline_settings_has_all_keys(self):
        """
        🔴 TESTE CRÍTICO: Valida que settings tem TODAS as chaves
        Este teste GARANTEQUE o bug foi corrigido
        """
        pipeline = VideoPipeline()
        
        required_keys = [
            'shorts_cache_dir',
            'transform_dir',      # ⚠️ Era isso que faltava!
            'validate_dir',       # ⚠️ Era isso que faltava!
            'audio_upload_dir',
            'output_dir',
            'log_dir',
        ]
        
        missing_keys = [k for k in required_keys if k not in pipeline.settings]
        
        assert missing_keys == [], f"❌ BUG AINDA PRESENTE! Missing: {missing_keys}"
    
    def test_pipeline_has_detector(self):
        """Pipeline tem detector de legendas"""
        pipeline = VideoPipeline()
        assert pipeline.detector is not None
    
    def test_pipeline_has_status_store(self):
        """Pipeline tem video status store"""
        pipeline = VideoPipeline()
        assert pipeline.status_store is not None


class TestEnsureDirectories:
    """Testes de criação de diretórios"""
    
    def test_ensure_directories_creates_all(self, monkeypatch, tmp_path):
        """_ensure_directories() cria todos os diretórios"""
        base = tmp_path / "pipeline_test"
        
        # Configurar ambiente temporário
        monkeypatch.setenv("AUDIO_UPLOAD_DIR", str(base / "raw/audio"))
        monkeypatch.setenv("SHORTS_CACHE_DIR", str(base / "raw/shorts"))
        monkeypatch.setenv("OUTPUT_DIR", str(base / "approved/output"))
        monkeypatch.setenv("LOG_DIR", str(base / "logs"))
        
        # Reset settings
        from app.core import config
        config._settings = None
        
        # Criar pipeline
        pipeline = VideoPipeline()
        
        # Verificar que diretórios foram criados
        expected_dirs = [
            'data/raw/shorts',
            'data/raw/audio',
            'data/transform/videos',
            'data/validate/in_progress',
            'data/approved/videos',
            'data/approved/output',
        ]
        
        for dir_path in expected_dirs:
            full_path = Path(dir_path)
            assert full_path.exists(), f"Directory not created: {dir_path}"


class TestCleanupOrphanedFiles:
    """
    🔴 TESTES CRÍTICOS - Método que causava o bug em produção
    """
    
    def test_cleanup_method_exists(self):
        """Método cleanup_orphaned_files() existe"""
        pipeline = VideoPipeline()
        assert hasattr(pipeline, 'cleanup_orphaned_files')
        assert callable(pipeline.cleanup_orphaned_files)
    
    @pytest.mark.requires_video
    def test_cleanup_orphaned_files_no_keyerror(self, temp_data_dirs):
        """
        🔴 TESTE MAIS CRÍTICO: cleanup_orphaned_files() NÃO deve dar KeyError
        Este é o teste que valida o fix do bug de produção
        """
        pipeline = VideoPipeline()
        
        # Criar arquivos órfãos reais
        orphan1 = temp_data_dirs['transform'] / "orphan_video_1.mp4"
        orphan2 = temp_data_dirs['validate'] / "orphan_video_2.mp4"
        
        orphan1.write_bytes(b"fake video data 1")
        orphan2.write_bytes(b"fake video data 2")
        
        # Executar cleanup - NÃO deve dar KeyError
        try:
            pipeline.cleanup_orphaned_files(max_age_minutes=0)
            success = True
        except KeyError as e:
            pytest.fail(f"❌ BUG AINDA PRESENTE! KeyError: {e}")
            success = False
        
        assert success, "cleanup_orphaned_files() deve executar sem KeyError"
    
    @pytest.mark.requires_video
    def test_cleanup_removes_old_files(self, temp_data_dirs):
        """Cleanup remove arquivos antigos"""
        pipeline = VideoPipeline()
        
        # Criar arquivo órfão
        orphan = temp_data_dirs['transform'] / "old_video.mp4"
        orphan.write_bytes(b"old video")
        
        # Aguardar 1 segundo
        import time
        time.sleep(1)
        
        # Limpar arquivos com idade > 0 minutos
        pipeline.cleanup_orphaned_files(max_age_minutes=0)
        
        # Arquivo deve ter sido removido
        assert not orphan.exists(), "Old file should be removed"
    
    @pytest.mark.requires_video
    def test_cleanup_preserves_recent_files(self, temp_data_dirs):
        """Cleanup preserva arquivos recentes"""
        pipeline = VideoPipeline()
        
        # Criar arquivo recente
        recent = temp_data_dirs['transform'] / "recent_video.mp4"
        recent.write_bytes(b"recent video")
        
        # Limpar arquivos com idade > 60 minutos
        pipeline.cleanup_orphaned_files(max_age_minutes=60)
        
        # Arquivo recente deve permanecer
        assert recent.exists(), "Recent file should be preserved"


class TestPipelineFlow:
    """Teste do fluxo completo do pipeline"""
    
    @pytest.mark.requires_video
    @pytest.mark.requires_ffmpeg
    @pytest.mark.slow
    def test_full_pipeline_flow_video_without_subtitles(
        self, 
        pipeline, 
        real_test_video, 
        temp_data_dirs
    ):
        """
        Teste end-to-end completo: vídeo SEM legendas
        1. Download (simulado)
        2. Transform
        3. Validate
        4. Approve
        """
        video_id = "test_video_001"
        
        # 1. DOWNLOAD (simular copiando vídeo)
        raw_path = temp_data_dirs['raw'] / f"{video_id}.mp4"
        shutil.copy(real_test_video, raw_path)
        assert raw_path.exists()
        
        # 2. TRANSFORM
        transform_path = pipeline.transform_video(video_id, str(raw_path))
        assert Path(transform_path).exists()
        
        # 3. MOVE TO VALIDATION
        job_id = "job_001"
        validate_path = pipeline.move_to_validation(video_id, transform_path, job_id)
        assert Path(validate_path).exists()
        assert "_PROCESSING_" in str(validate_path)
        
        # 4. VALIDATE
        result = pipeline.validate_video(video_id, validate_path)
        assert 'has_subtitles' in result
        assert isinstance(result['has_subtitles'], bool)
        
        # 5. APPROVE (se não tem legendas)
        if not result['has_subtitles']:
            approved_path = pipeline.approve_video(video_id, validate_path)
            assert Path(approved_path).exists()
            
            # Vídeo deve estar no database de aprovados
            assert pipeline.status_store.is_approved(video_id)
        else:
            # 5. REJECT (se tem legendas)
            pipeline.reject_video(video_id, validate_path, "has_subtitles")
            assert pipeline.status_store.is_rejected(video_id)
    
    @pytest.mark.requires_video
    @pytest.mark.slow
    def test_pipeline_reject_video_with_subtitles(
        self, 
        pipeline, 
        video_with_subtitles, 
        temp_data_dirs
    ):
        """Pipeline rejeita vídeo COM legendas"""
        video_id = "test_video_with_subs"
        
        # Simular download
        raw_path = temp_data_dirs['raw'] / f"{video_id}.mp4"
        shutil.copy(video_with_subtitles, raw_path)
        
        # Transform
        transform_path = pipeline.transform_video(video_id, str(raw_path))
        
        # Validate
        job_id = "job_002"
        validate_path = pipeline.move_to_validation(video_id, transform_path, job_id)
        result = pipeline.validate_video(video_id, validate_path)
        
        # Deve detectar legendas
        assert result['has_subtitles'] is True
        
        # Rejeitar
        pipeline.reject_video(video_id, validate_path, "has_subtitles")
        
        # Validar rejeição
        assert pipeline.status_store.is_rejected(video_id)
        assert not Path(validate_path).exists()  # Arquivo removido


class TestPipelineErrorHandling:
    """Testes de tratamento de erros"""
    
    def test_transform_with_invalid_video(self, pipeline, tmp_path):
        """Transform com vídeo inválido deve falhar graciosamente"""
        invalid_video = tmp_path / "invalid.mp4"
        invalid_video.write_bytes(b"not a real video")
        
        video_id = "invalid_video"
        
        with pytest.raises(Exception):  # Deve lançar erro
            pipeline.transform_video(video_id, str(invalid_video))
    
    def test_validate_with_nonexistent_video(self, pipeline):
        """Validar vídeo inexistente deve falhar"""
        video_id = "nonexistent"
        fake_path = "/tmp/nonexistent.mp4"
        
        with pytest.raises(FileNotFoundError):
            pipeline.validate_video(video_id, fake_path)


@pytest.fixture
def pipeline():
    """Fixture de pipeline real"""
    return VideoPipeline()
```

---

## 📋 PASSO A PASSO

```bash
# 1. Verificar que Sprint 1 foi concluída (fix aplicado)
python -c "
from app.core.config import get_settings
settings = get_settings()
assert 'transform_dir' in settings, 'Sprint 1 não concluída!'
print('✅ Sprint 1 OK')
"

# 2. Criar estrutura
mkdir -p tests/integration/pipeline
touch tests/integration/pipeline/__init__.py
touch tests/integration/pipeline/test_video_pipeline.py

# 3. Implementar testes (copiar código acima)

# 4. Executar teste crítico primeiro
pytest tests/integration/pipeline/test_video_pipeline.py::TestCleanupOrphanedFiles::test_cleanup_orphaned_files_no_keyerror -v -s

# 5. Se passou, executar todos
pytest tests/integration/pipeline/ -v

# 6. Com cobertura
pytest tests/integration/pipeline/ --cov=app.pipeline --cov-report=term
```

---

## ✅ CRITÉRIOS DE ACEITAÇÃO

- [ ] **TESTE CRÍTICO PASSA**: `test_cleanup_orphaned_files_no_keyerror`
- [ ] `test_pipeline_settings_has_all_keys` passa
- [ ] Pipeline completo end-to-end funciona
- [ ] Cleanup funciona sem KeyError
- [ ] Approve/Reject flow testado
- [ ] Cobertura > 80%
- [ ] Todos os testes passando

---

## 🎉 VALIDAÇÃO DO BUG

```bash
# Teste final de validação
pytest tests/integration/pipeline/test_video_pipeline.py::TestCleanupOrphanedFiles -v

# Output esperado:
# PASSED test_cleanup_orphaned_files_no_keyerror ✅
# PASSED test_cleanup_removes_old_files ✅
# PASSED test_cleanup_preserves_recent_files ✅

# Se todos passaram:
echo "🎉 BUG DE PRODUÇÃO RESOLVIDO!"
```

---

**Status**: ⏳ Pendente  
**Data de Conclusão**: ___________  
**Bug Validado**: ⬜ Sim ⬜ Não
