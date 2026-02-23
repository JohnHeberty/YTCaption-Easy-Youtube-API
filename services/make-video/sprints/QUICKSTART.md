# 🚀 GUIA DE INÍCIO RÁPIDO

**Como começar a executar as sprints em 5 minutos**

---

## ⚡ INÍCIO RÁPIDO

### 1. Requisitos

```bash
# Verificar Python
python --version  # >= 3.9

# Verificar FFmpeg
ffmpeg -version

# Verificar Redis
redis-cli ping
```

### 2. Setup Inicial (5 minutos)

```bash
# Navegar para o diretório
cd /root/YTCaption-Easy-Youtube-API/services/make-video

# Criar ambiente virtual
python3 -m venv .venv_test
source .venv_test/bin/activate

# Instalar dependências
pip install -r requirements.txt
pip install pytest pytest-cov pytest-asyncio pytest-timeout

# Criar estrutura de testes
mkdir -p tests/{unit,integration,e2e,fixtures/{real_videos,real_audio,real_subtitles}}
touch tests/__init__.py
```

### 3. Executar Sprint 0 (Setup)

```bash
# Abrir o guia da Sprint 0
cat sprints/SPRINT-00-SETUP.md | less

# Seguir o passo a passo
# Criar conftest.py, pytest.ini, .env.test

# Validar
pytest --collect-only
pytest tests/test_setup_validation.py -v
```

### 4. Aplicar Fix Crítico (Sprint 1)

```bash
# Abrir o guia da Sprint 1
cat sprints/SPRINT-01-CORE.md | less

# Editar app/core/config.py
nano app/core/config.py

# Adicionar no get_settings():
#   "transform_dir": "./data/transform/videos",
#   "validate_dir": "./data/validate",
#   "approved_dir": "./data/approved/videos",

# Validar fix
python -c "
from app.core.config import get_settings
s = get_settings()
print('transform_dir' in s)
print('validate_dir' in s)
"
```

### 5. Executar Teste Crítico

```bash
# Criar teste (ver SPRINT-01-CORE.md)
pytest tests/unit/core/test_config.py::TestGetSettings::test_get_settings_has_pipeline_directory_keys -v

# Deve passar: ✅ PASSED
```

---

## 📚 ESTRUTURA DOS ARQUIVOS

```
/root/YTCaption-Easy-Youtube-API/services/make-video/
│
├── sprints/                          # 📁 GUIAS DAS SPRINTS
│   ├── README.md                    # Índice e visão geral
│   ├── CHECKLIST.md                 # ✅ Checklist de progresso
│   ├── QUICKSTART.md                # 🚀 Este arquivo
│   ├── SPRINT-00-SETUP.md           # Sprint 0: Setup
│   ├── SPRINT-01-CORE.md            # Sprint 1: Core (BUG FIX)
│   ├── SPRINT-02-SHARED.md          # Sprint 2: Shared
│   ├── SPRINT-03-UTILS.md           # Sprint 3: Utils
│   ├── SPRINT-04-INFRASTRUCTURE.md  # Sprint 4: Infrastructure
│   ├── SPRINT-05-VIDEO-PROCESSING.md # Sprint 5: Video Processing
│   ├── SPRINT-06-SUBTITLE-PROCESSING.md # Sprint 6: Subtitle
│   ├── SPRINT-07-SERVICES.md        # Sprint 7: Services
│   ├── SPRINT-08-PIPELINE.md        # Sprint 8: Pipeline (CRÍTICO)
│   ├── SPRINT-09-DOMAIN.md          # Sprint 9: Domain
│   └── SPRINT-10-MAIN-API.md        # Sprint 10: Main & API
│
├── tests/                           # 🧪 TESTES
│   ├── conftest.py                  # Fixtures globais
│   ├── pytest.ini                   # Config do pytest
│   ├── .env.test                    # Env vars de teste
│   ├── unit/                        # Testes unitários
│   ├── integration/                 # Testes de integração
│   ├── e2e/                         # Testes end-to-end
│   └── fixtures/                    # Arquivos de teste reais
│
└── app/                             # 📦 CÓDIGO FONTE
    ├── core/                        # Configuração
    ├── pipeline/                    # Pipeline (bug está aqui)
    └── ...
```

---

## 🎯 ORDEM DE EXECUÇÃO

### Fase 1: Setup e Fix Crítico (4-7h)

```bash
# 1. Sprint 0 (2-3h)
# Preparar ambiente, fixtures, configuração

# 2. Sprint 1 (3-4h) ⚠️ CRÍTICO
# Corrigir bug KeyError, testar config
```

### Fase 2: Base e Utilitários (7-10h)

```bash
# 3. Sprint 2 (2-3h)
# Testar shared modules

# 4. Sprint 3 (3-4h)
# Testar audio, VAD, timeout

# 5. Sprint 4 (4-5h)
# Testar infrastructure (Redis, checkpoints)
```

### Fase 3: Processamento (10-13h)

```bash
# 6. Sprint 5 (6-8h)
# Testar video processing (detector, OCR)

# 7. Sprint 6 (4-5h)
# Testar subtitle processing (.ass generator)
```

### Fase 4: Integração (14-17h)

```bash
# 8. Sprint 7 (4-5h)
# Testar services (video builder, status)

# 9. Sprint 8 (5-6h) ⚠️ CRÍTICO
# Testar pipeline (validar fix do bug)

# 10. Sprint 9 (5-6h)
# Testar domain (job processor, stages)
```

### Fase 5: Finalização (3-4h)

```bash
# 11. Sprint 10 (3-4h) ⚠️ CRÍTICO
# Testar main & API (validar CRON job)
```

**Total**: 42-53 horas (~5-7 dias de trabalho)

---

## 🔥 COMANDOS MAIS ÚTEIS

### Executar Testes

```bash
# Todos os testes
pytest tests/ -v

# Sprint específica
pytest tests/unit/core/ -v

# Com cobertura
pytest tests/ --cov=app --cov-report=html

# Apenas testes que falharam
pytest --lf -v

# Parar no primeiro erro
pytest -x -v

# Testes lentos
pytest -v -m slow

# Testes que requeremvídeo
pytest -v -m requires_video

# Verbose com output
pytest -v -s
```

### Validações Rápidas

```bash
# Verificar se bug foi corrigido
python -c "from app.core.config import get_settings; assert 'transform_dir' in get_settings()"

# Testar CRON job
python -c "from app.main import cleanup_orphaned_videos_cron; cleanup_orphaned_videos_cron()"

# Ver cobertura
pytest tests/ --cov=app --cov-report=term | grep TOTAL
```

### Troubleshooting

```bash
# Redis não conecta?
redis-server --daemonize yes
redis-cli ping

# FFmpeg não encontrado?
which ffmpeg
sudo apt install ffmpeg

# Módulo app não encontrado?
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Limpar cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type d -name .pytest_cache -exec rm -rf {} +
```

---

## 📊 ACOMPANHAMENTO

### Atualizar Status

Após cada sprint, atualize:

```bash
# Editar CHECKLIST.md
nano sprints/CHECKLIST.md

# Marcar sprint como completa: ⏳ → ✅
# Adicionar data de conclusão
# Adicionar cobertura alcançada
```

### Gerar Relatório

```bash
# Após cada sprint
cp sprints/CHECKLIST.md sprints/SPRINT-0X-REPORT.md

# Preencher template de relatório
# Ver exemplo em CHECKLIST.md
```

---

## 🎯 TESTES CRÍTICOS

Estes 3 testes são os mais importantes e validam que o bug foi corrigido:

### 1. Sprint 1 - Config

```bash
pytest tests/unit/core/test_config.py::TestGetSettings::test_get_settings_has_pipeline_directory_keys -v
```

**Deve passar**: ✅

### 2. Sprint 8 - Pipeline

```bash
pytest tests/integration/pipeline/test_video_pipeline.py::TestCleanupOrphanedFiles::test_cleanup_orphaned_files_no_keyerror -v
```

**Deve passar**: ✅

### 3. Sprint 10 - CRON Job

```bash
pytest tests/e2e/test_main_application.py::TestCronJobs::test_cleanup_cron_does_not_crash -v
```

**Deve passar**: ✅

---

## ✅ VALIDAÇÃO FINAL

Quando todas as sprints estiverem completas:

```bash
# 1. Todos os testes
pytest tests/ -v

# 2. Cobertura
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html

# 3. Testes críticos
pytest tests/unit/core/test_config.py::TestGetSettings::test_get_settings_has_pipeline_directory_keys -v
pytest tests/integration/pipeline/test_video_pipeline.py::TestCleanupOrphanedFiles::test_cleanup_orphaned_files_no_keyerror -v
pytest tests/e2e/test_main_application.py::TestCronJobs::test_cleanup_cron_does_not_crash -v

# 4. Smoke test
python -c "
from app.main import cleanup_orphaned_videos_cron
from app.core.config import get_settings

settings = get_settings()
assert 'transform_dir' in settings
assert 'validate_dir' in settings

cleanup_orphaned_videos_cron()

print('🎉 BUG RESOLVIDO! PRONTO PARA PRODUÇÃO!')
"

# 5. Se tudo passou:
echo "✅ Testes completos"
echo "✅ Bug corrigido"
echo "✅ Pronto para deployment"
```

---

## 📞 AJUDA

### Documentação

- [README.md](README.md) - Visão geral
- [CHECKLIST.md](CHECKLIST.md) - Acompanhamento
- [SPRINT-XX-*.md](.) - Guias detalhados

### Comandos de Ajuda

```bash
# Ver markers disponíveis
pytest --markers

# Ver fixtures disponíveis
pytest --fixtures

# Ajuda do pytest
pytest --help
```

---

## 🎉 PRÓXIMOS PASSOS

Após completar todos os testes:

1 ✅ Code review
2. ✅ Merge para main
3. ✅ Build Docker
4. ✅ Deploy staging
5. ✅ Deploy produção
6. ✅ Monitoramento

---

**BOA SORTE! 🚀**

**Lembre-se**: O objetivo é resolver o bug de produção e garantir que ele não volte. Foque nas sprints críticas (1, 8, 10) primeiro se tiver pouco tempo.

---

**Versão**: 1.0.0  
**Criado**: 2026-02-19
