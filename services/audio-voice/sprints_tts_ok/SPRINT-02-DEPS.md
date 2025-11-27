# SPRINT 2 - Instalação e Validação de Dependências RVC

**Duração Estimada:** 2-3 dias  
**Responsável:** Backend Engineer  
**Dependências:** Sprint 1 (Docker GPU funcional)

---

## 1. OBJETIVO

Instalar e validar todas as dependências necessárias para RVC, garantindo que:
- ✅ `tts-with-rvc` e dependências instalam sem conflitos
- ✅ Todos os imports funcionam corretamente
- ✅ Modelos auxiliares (Hubert, RMVPE) são baixáveis
- ✅ Não há regressões no XTTS existente

---

## 2. PRÉ-REQUISITOS

### Sprint 1 Completa

- [x] Docker GPU funcional
- [x] GPU detectada (`torch.cuda.is_available() == True`)
- [x] Health check passando

### Validação

```bash
# Container deve estar rodando
docker ps | grep audio-voice-api-gpu

# GPU detectada
docker exec -it audio-voice-api-gpu python -c "import torch; assert torch.cuda.is_available()"
```

---

## 3. TAREFAS

### 3.1 TESTES (Red Phase)

#### 3.1.1 Criar `tests/test_rvc_dependencies.py`

```python
"""
Testes de dependências RVC
Sprint 2: Dependências
"""
import pytest


class TestRvcDependenciesImport:
    """
    Testes que validam imports de todas as dependências RVC
    """
    
    def test_import_tts_with_rvc(self):
        """tts-with-rvc deve importar sem erros"""
        try:
            import tts_with_rvc
            assert hasattr(tts_with_rvc, '__version__'), "tts-with-rvc missing __version__"
        except ImportError as e:
            pytest.fail(f"Failed to import tts-with-rvc: {e}")
    
    def test_import_tts_rvc_class(self):
        """TTS_RVC class deve estar acessível"""
        try:
            from tts_with_rvc import TTS_RVC
            assert TTS_RVC is not None, "TTS_RVC class not found"
        except ImportError as e:
            pytest.fail(f"Failed to import TTS_RVC: {e}")
    
    def test_import_fairseq(self):
        """fairseq deve importar (Hubert model)"""
        try:
            import fairseq
            assert hasattr(fairseq, '__version__'), "fairseq missing __version__"
        except ImportError as e:
            pytest.fail(f"Failed to import fairseq: {e}")
    
    def test_import_faiss(self):
        """faiss deve importar (index retrieval)"""
        try:
            import faiss
            # Verifica se é versão GPU ou CPU
            assert hasattr(faiss, 'IndexFlatL2'), "faiss missing IndexFlatL2"
        except ImportError as e:
            pytest.fail(f"Failed to import faiss: {e}")
    
    def test_import_librosa(self):
        """librosa deve importar (audio processing)"""
        try:
            import librosa
            assert hasattr(librosa, '__version__'), "librosa missing __version__"
        except ImportError as e:
            pytest.fail(f"Failed to import librosa: {e}")
    
    def test_import_parselmouth(self):
        """praat-parselmouth deve importar (PM pitch method)"""
        try:
            import parselmouth
            assert hasattr(parselmouth, 'Sound'), "parselmouth missing Sound class"
        except ImportError as e:
            pytest.fail(f"Failed to import parselmouth: {e}")
    
    def test_import_torchcrepe(self):
        """torchcrepe deve importar (CREPE pitch method)"""
        try:
            import torchcrepe
            assert hasattr(torchcrepe, 'predict'), "torchcrepe missing predict function"
        except ImportError as e:
            pytest.fail(f"Failed to import torchcrepe: {e}")
    
    def test_import_soundfile(self):
        """soundfile deve importar (I/O de áudio)"""
        try:
            import soundfile as sf
            assert hasattr(sf, 'read'), "soundfile missing read function"
        except ImportError as e:
            pytest.fail(f"Failed to import soundfile: {e}")


class TestRvcModulesStructure:
    """
    Testes que validam estrutura interna do tts-with-rvc
    """
    
    def test_import_vc_modules(self):
        """Módulo VC deve importar"""
        try:
            from tts_with_rvc.infer.vc.modules import VC
            assert VC is not None, "VC class not found"
        except ImportError as e:
            pytest.fail(f"Failed to import VC: {e}")
    
    def test_import_pipeline(self):
        """Pipeline class deve importar"""
        try:
            from tts_with_rvc.infer.vc.pipeline import Pipeline
            assert Pipeline is not None, "Pipeline class not found"
        except ImportError as e:
            pytest.fail(f"Failed to import Pipeline: {e}")
    
    def test_import_rvc_convert(self):
        """rvc_convert function deve importar"""
        try:
            from tts_with_rvc.vc_infer import rvc_convert
            assert callable(rvc_convert), "rvc_convert is not callable"
        except ImportError as e:
            pytest.fail(f"Failed to import rvc_convert: {e}")
    
    def test_import_rmvpe(self):
        """RMVPE pitch extractor deve importar"""
        try:
            from tts_with_rvc.infer.lib.rmvpe import RMVPE
            assert RMVPE is not None, "RMVPE class not found"
        except ImportError as e:
            pytest.fail(f"Failed to import RMVPE: {e}")


class TestRvcCompatibilityXTTS:
    """
    Testes que validam compatibilidade RVC + XTTS (sem regressões)
    """
    
    def test_xtts_still_imports(self):
        """XTTS deve continuar importando após adicionar RVC deps"""
        try:
            from TTS.api import TTS
            assert TTS is not None, "TTS class not found"
        except ImportError as e:
            pytest.fail(f"Failed to import TTS (regression): {e}")
    
    def test_torch_versions_compatible(self):
        """torch, torchaudio devem ser versões compatíveis"""
        import torch
        import torchaudio
        
        torch_version = torch.__version__.split('+')[0]  # Remove +cu121
        torchaudio_version = torchaudio.__version__.split('+')[0]
        
        # Ambos devem ser 2.4.0
        assert torch_version.startswith('2.4'), f"torch version {torch_version} incompatible"
        assert torchaudio_version.startswith('2.4'), f"torchaudio version {torchaudio_version} incompatible"
    
    def test_no_dependency_conflicts(self):
        """Não deve haver conflitos de versão entre deps XTTS e RVC"""
        import pkg_resources
        
        # Packages críticos
        critical = ['torch', 'torchaudio', 'soundfile', 'librosa', 'numpy']
        
        for package in critical:
            try:
                dist = pkg_resources.get_distribution(package)
                assert dist is not None, f"{package} not installed"
            except pkg_resources.DistributionNotFound:
                pytest.fail(f"{package} not found in environment")


@pytest.mark.slow
class TestRvcModelDownloads:
    """
    Testes que validam download de modelos auxiliares RVC
    """
    
    def test_hubert_model_downloadable(self):
        """Modelo Hubert deve ser baixável"""
        from huggingface_hub import hf_hub_download
        
        try:
            model_path = hf_hub_download(
                repo_id="lj1995/VoiceConversionWebUI",
                filename="hubert_base.pt",
                cache_dir="/app/models"
            )
            assert model_path is not None, "Hubert model path is None"
        except Exception as e:
            pytest.fail(f"Failed to download Hubert model: {e}")
    
    def test_rmvpe_model_downloadable(self):
        """Modelo RMVPE deve ser baixável"""
        from huggingface_hub import hf_hub_download
        
        try:
            model_path = hf_hub_download(
                repo_id="lj1995/VoiceConversionWebUI",
                filename="rmvpe.pt",
                cache_dir="/app/models"
            )
            assert model_path is not None, "RMVPE model path is None"
        except Exception as e:
            pytest.fail(f"Failed to download RMVPE model: {e}")
```

**Validação:** Rodar `pytest tests/test_rvc_dependencies.py -v`

**Resultado Esperado:** ❌ MUITOS TESTES DEVEM FALHAR (deps RVC não instaladas ainda)

---

### 3.2 IMPLEMENTAÇÃO (Green Phase)

#### 3.2.1 Criar `docker/requirements-rvc.txt`

```txt
# RVC Dependencies
# Sprint 2: Dependências RVC

# Core RVC
tts-with-rvc==0.1.9

# Fairseq (Hubert model)
# Use fairseq-fixed em Windows, fairseq em Linux
fairseq==0.12.2; sys_platform != 'win32'
# fairseq-fixed==0.12.2; sys_platform == 'win32'  # Uncomment if Windows

# FAISS (Index retrieval)
# Use GPU version se disponível
faiss-gpu==1.7.2; sys_platform != 'win32'
faiss-cpu==1.7.2; sys_platform == 'win32'

# Audio Processing
librosa==0.10.1
soundfile==0.12.1  # Já instalado, mas pinning version
praat-parselmouth==0.4.3
audioread==3.0.1
pyloudnorm==0.1.1

# Pitch Extraction
torchcrepe==0.0.23
pyworld==0.3.4

# Utilities
resampy==0.4.2
pydub==0.25.1
nest-asyncio==1.6.0
scipy>=1.12.0
numpy>=1.23.5,<2.0.0  # Compatibilidade com fairseq

# HuggingFace (download models)
huggingface-hub>=0.20.0
```

#### 3.2.2 Atualizar `requirements.txt` (merge com RVC)

```txt
# ========================================
# CORE DEPENDENCIES (Existentes)
# ========================================

# FastAPI
fastapi==0.120.0
uvicorn[standard]==0.32.1
python-multipart==0.0.18
pydantic==2.10.3
pydantic-settings==2.7.0

# Celery
celery==5.3.4
redis==5.0.1

# XTTS (TTS Engine)
TTS==0.22.0

# Audio Processing
soundfile==0.12.1
pydub==0.25.1

# Utils
requests==2.32.3
python-dotenv==1.0.1

# ========================================
# RVC DEPENDENCIES (Novos - Sprint 2)
# ========================================

# Core RVC
tts-with-rvc==0.1.9

# Fairseq (Hubert model)
fairseq==0.12.2; sys_platform != 'win32'

# FAISS (Index retrieval)
faiss-gpu==1.7.2; sys_platform != 'win32'
faiss-cpu==1.7.2; sys_platform == 'win32'

# Audio Processing (RVC specific)
librosa==0.10.1
praat-parselmouth==0.4.3
audioread==3.0.1
pyloudnorm==0.1.1

# Pitch Extraction
torchcrepe==0.0.23
pyworld==0.3.4

# Utilities
resampy==0.4.2
nest-asyncio==1.6.0
scipy>=1.12.0
numpy>=1.23.5,<2.0.0

# HuggingFace
huggingface-hub>=0.20.0

# ========================================
# TESTING (Existentes)
# ========================================

pytest==8.3.4
pytest-asyncio==0.24.0
pytest-cov==6.0.0
httpx==0.28.1
```

#### 3.2.3 Atualizar `docker/Dockerfile-gpu` (instalar RVC deps)

Modificar seção de instalação de dependências:

```dockerfile
# ... (código existente até WORKDIR /app)

# Copiar requirements
COPY requirements.txt .

# Instalar PyTorch com CUDA (antes de outras deps)
RUN pip install torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0 \
    --index-url https://download.pytorch.org/whl/cu121

# ★ NOVO: Instalar fairseq separadamente (pode dar timeout)
RUN pip install fairseq==0.12.2 --no-deps && \
    pip install omegaconf hydra-core

# Instalar dependências Python (incluindo RVC)
RUN pip install -r requirements.txt

# ★ NOVO: Pré-baixar modelos auxiliares RVC
RUN python -c "from huggingface_hub import hf_hub_download; \
               hf_hub_download('lj1995/VoiceConversionWebUI', 'hubert_base.pt', cache_dir='/app/models'); \
               hf_hub_download('lj1995/VoiceConversionWebUI', 'rmvpe.pt', cache_dir='/app/models')"

# ... (resto do Dockerfile)
```

#### 3.2.4 Criar script de validação `scripts/validate-deps.sh`

```bash
#!/bin/bash
# Validação de dependências RVC
# Sprint 2

set -e

echo "==================================="
echo "RVC Dependencies Validation"
echo "==================================="
echo ""

CONTAINER="audio-voice-api-gpu"

# Check 1: Container running
echo "✓ Checking container..."
if ! docker ps | grep -q "$CONTAINER"; then
    echo "❌ Container $CONTAINER not running"
    exit 1
fi
echo "Container is running ✓"
echo ""

# Check 2: Python imports
echo "✓ Testing Python imports..."

imports=(
    "import tts_with_rvc"
    "from tts_with_rvc import TTS_RVC"
    "import fairseq"
    "import faiss"
    "import librosa"
    "import parselmouth"
    "import torchcrepe"
    "from TTS.api import TTS"
)

for import_stmt in "${imports[@]}"; do
    echo "  - Testing: $import_stmt"
    if ! docker exec -it "$CONTAINER" python -c "$import_stmt" &> /dev/null; then
        echo "  ❌ Failed: $import_stmt"
        exit 1
    fi
    echo "    ✓ OK"
done
echo ""

# Check 3: Hubert model
echo "✓ Checking Hubert model..."
docker exec -it "$CONTAINER" bash -c "
if [ ! -f /app/models/models--lj1995--VoiceConversionWebUI/snapshots/*/hubert_base.pt ]; then
    echo '❌ Hubert model not found'
    exit 1
fi
echo 'Hubert model exists ✓'
"
echo ""

# Check 4: RMVPE model
echo "✓ Checking RMVPE model..."
docker exec -it "$CONTAINER" bash -c "
if [ ! -f /app/models/models--lj1995--VoiceConversionWebUI/snapshots/*/rmvpe.pt ]; then
    echo '❌ RMVPE model not found'
    exit 1
fi
echo 'RMVPE model exists ✓'
"
echo ""

# Check 5: Run tests
echo "✓ Running dependency tests..."
docker exec -it "$CONTAINER" pytest tests/test_rvc_dependencies.py -v
echo ""

echo "==================================="
echo "✅ All dependency checks passed!"
echo "==================================="
```

#### 3.2.5 Criar `app/rvc_dependencies.py` (helper para lazy imports)

```python
"""
RVC Dependencies Helper
Sprint 2: Lazy imports e validação de dependências
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RvcDependencies:
    """
    Helper para gerenciar imports RVC (lazy loading)
    """
    
    # Cache de módulos importados
    _tts_rvc = None
    _vc_class = None
    _pipeline_class = None
    _rmvpe_class = None
    
    @classmethod
    def get_tts_rvc_class(cls):
        """
        Importa TTS_RVC class (lazy)
        
        Returns:
            TTS_RVC class
        
        Raises:
            ImportError: Se tts-with-rvc não estiver instalado
        """
        if cls._tts_rvc is None:
            try:
                from tts_with_rvc import TTS_RVC
                cls._tts_rvc = TTS_RVC
                logger.info("TTS_RVC class imported successfully")
            except ImportError as e:
                logger.error(f"Failed to import TTS_RVC: {e}")
                raise ImportError(
                    "tts-with-rvc not installed. Run: pip install tts-with-rvc"
                ) from e
        
        return cls._tts_rvc
    
    @classmethod
    def get_vc_class(cls):
        """
        Importa VC class (lazy)
        
        Returns:
            VC class
        """
        if cls._vc_class is None:
            try:
                from tts_with_rvc.infer.vc.modules import VC
                cls._vc_class = VC
                logger.info("VC class imported successfully")
            except ImportError as e:
                logger.error(f"Failed to import VC: {e}")
                raise ImportError("Failed to import RVC VC module") from e
        
        return cls._vc_class
    
    @classmethod
    def get_pipeline_class(cls):
        """
        Importa Pipeline class (lazy)
        
        Returns:
            Pipeline class
        """
        if cls._pipeline_class is None:
            try:
                from tts_with_rvc.infer.vc.pipeline import Pipeline
                cls._pipeline_class = Pipeline
                logger.info("Pipeline class imported successfully")
            except ImportError as e:
                logger.error(f"Failed to import Pipeline: {e}")
                raise ImportError("Failed to import RVC Pipeline module") from e
        
        return cls._pipeline_class
    
    @classmethod
    def get_rmvpe_class(cls):
        """
        Importa RMVPE class (lazy)
        
        Returns:
            RMVPE class
        """
        if cls._rmvpe_class is None:
            try:
                from tts_with_rvc.infer.lib.rmvpe import RMVPE
                cls._rmvpe_class = RMVPE
                logger.info("RMVPE class imported successfully")
            except ImportError as e:
                logger.error(f"Failed to import RMVPE: {e}")
                raise ImportError("Failed to import RMVPE module") from e
        
        return cls._rmvpe_class
    
    @classmethod
    def validate_all_dependencies(cls) -> bool:
        """
        Valida que todas as dependências RVC estão instaladas
        
        Returns:
            bool: True se todas as deps estão OK
        """
        try:
            # Testa imports críticos
            import tts_with_rvc
            import fairseq
            import faiss
            import librosa
            import parselmouth
            import torchcrepe
            
            # Testa classes específicas
            cls.get_tts_rvc_class()
            cls.get_vc_class()
            cls.get_pipeline_class()
            cls.get_rmvpe_class()
            
            logger.info("All RVC dependencies validated successfully")
            return True
            
        except ImportError as e:
            logger.error(f"RVC dependency validation failed: {e}")
            return False


def check_rvc_dependencies() -> dict:
    """
    Verifica status de todas as dependências RVC
    
    Returns:
        dict: Status de cada dependência
    """
    status = {}
    
    # Lista de deps
    dependencies = {
        'tts-with-rvc': 'tts_with_rvc',
        'fairseq': 'fairseq',
        'faiss': 'faiss',
        'librosa': 'librosa',
        'parselmouth': 'parselmouth',
        'torchcrepe': 'torchcrepe',
        'soundfile': 'soundfile',
        'numpy': 'numpy',
        'scipy': 'scipy'
    }
    
    for name, module_name in dependencies.items():
        try:
            __import__(module_name)
            status[name] = 'installed'
        except ImportError:
            status[name] = 'missing'
    
    return status
```

#### 3.2.6 Atualizar health check com info de dependências

```python
# Adicionar em app/main.py

@app.get("/health/dependencies", tags=["Health"])
async def health_dependencies():
    """
    Health check de dependências RVC
    
    Returns:
        dict: Status de cada dependência
    """
    from app.rvc_dependencies import check_rvc_dependencies, RvcDependencies
    
    deps_status = check_rvc_dependencies()
    
    # Valida todas as deps
    all_ok = RvcDependencies.validate_all_dependencies()
    
    return {
        "status": "healthy" if all_ok else "degraded",
        "dependencies": deps_status,
        "all_validated": all_ok
    }
```

---

### 3.3 REFATORAÇÃO

#### 3.3.1 Organizar requirements.txt

- Separar em seções claras (Core, XTTS, RVC, Testing)
- Adicionar comentários explicativos
- Pin todas as versões (evitar surpresas)

#### 3.3.2 Otimizar build do Docker

- Usar layer caching (deps mudam menos que código)
- Separar instalação de fairseq (pode falhar)
- Pré-baixar modelos Hubert/RMVPE

#### 3.3.3 Criar script de instalação local

`scripts/install-rvc-deps-local.sh`:

```bash
#!/bin/bash
# Instalação local de deps RVC (desenvolvimento)

set -e

echo "Installing RVC dependencies locally..."

# PyTorch com CUDA
pip install torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0 \
    --index-url https://download.pytorch.org/whl/cu121

# Fairseq separado
pip install fairseq==0.12.2 --no-deps
pip install omegaconf hydra-core

# Resto das deps
pip install -r requirements.txt

# Download modelos
python -c "
from huggingface_hub import hf_hub_download
hf_hub_download('lj1995/VoiceConversionWebUI', 'hubert_base.pt', cache_dir='./models')
hf_hub_download('lj1995/VoiceConversionWebUI', 'rmvpe.pt', cache_dir='./models')
"

echo "✅ RVC dependencies installed!"
```

---

## 4. CRITÉRIOS DE ACEITAÇÃO

### ✅ Checklist

- [ ] **requirements.txt** atualizado com deps RVC
- [ ] **Dockerfile-gpu** atualizado (instala RVC deps)
- [ ] **Container builda** sem erros
- [ ] **Todos os imports** funcionam (`test_rvc_dependencies.py` ✅)
- [ ] **Modelos auxiliares** baixados (Hubert, RMVPE)
- [ ] **Sem regressões** XTTS (`test_xtts_still_imports` ✅)
- [ ] **Health check dependencies** retorna status OK
- [ ] **Script validate-deps.sh** passa ✅
- [ ] **Coverage** ≥85%

### Comando de Validação Final

```bash
# Rebuild com deps RVC
docker-compose -f docker-compose-gpu.yml build --no-cache

# Start
docker-compose -f docker-compose-gpu.yml up -d

# Aguardar startup
sleep 60

# Validar deps
./scripts/validate-deps.sh

# Rodar testes
docker exec -it audio-voice-api-gpu pytest tests/test_rvc_dependencies.py -v --cov=app

# Testar health de deps
curl http://localhost:8000/health/dependencies | jq

# Limpar
docker-compose -f docker-compose-gpu.yml down
```

**Resultado Esperado:** ✅ TODOS OS COMANDOS EXECUTAM SEM ERROS

---

## 5. ENTREGÁVEIS

### Arquivos Criados/Modificados

```
docker/
└── requirements-rvc.txt         ✅ NOVO

requirements.txt                 🔄 MODIFICADO (merge RVC deps)

docker/
└── Dockerfile-gpu               🔄 MODIFICADO (install RVC deps)

app/
├── main.py                      🔄 MODIFICADO (health dependencies endpoint)
└── rvc_dependencies.py          ✅ NOVO

tests/
└── test_rvc_dependencies.py     ✅ NOVO

scripts/
├── validate-deps.sh             ✅ NOVO
└── install-rvc-deps-local.sh    ✅ NOVO
```

---

## 6. PRÓXIMOS PASSOS

Após completar esta sprint:

1. ✅ Marcar Sprint 2 como completa
2. ✅ Commit: `git commit -m "feat(rvc): Sprint 2 - RVC dependencies installation"`
3. ✅ Push: `git push origin feature/f5tts-ptbr-migration`
4. ▶️ Iniciar **Sprint 3** (ler `sprints/SPRINT-03-RVC-CLIENT.md`)

---

## 7. TROUBLESHOOTING

### Problema: fairseq falha ao instalar

**Solução:**
```bash
# Instalar fairseq-fixed (Windows)
pip install fairseq-fixed==0.12.2

# OU instalar sem deps e adicionar manualmente
pip install fairseq==0.12.2 --no-deps
pip install omegaconf hydra-core
```

### Problema: faiss-gpu não disponível

**Solução:**
```bash
# Fallback para CPU
pip install faiss-cpu==1.7.2
```

### Problema: Hugging Face download timeout

**Solução:**
```bash
# Aumentar timeout
export HF_HUB_DOWNLOAD_TIMEOUT=600

# OU baixar manualmente
wget https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/hubert_base.pt
mv hubert_base.pt /app/models/
```

---

**Sprint 2 Completa!** 🎉

Próxima: **Sprint 3 - RVC Client Implementation** →
