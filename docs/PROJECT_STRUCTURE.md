# 📁 Estrutura de Organização - Padrão Enterprise

**YTCaption-Easy-Youtube-API**  
**Última atualização**: 2026-02-28

---

## 🎯 Objetivo

Este documento define o **padrão de organização enterprise** aplicado em todo o projeto para garantir:
- ✅ Consistência entre microserviços
- ✅ Manutenibilidade e escalabilidade
- ✅ Facilidade de navegação
- ✅ Conformidade com DevOps best practices

---

## 📦 Estrutura Raiz do Projeto

```
YTCaption-Easy-Youtube-API/
├── README.md                    # ✅ Único .md na raiz
├── LICENSE
├── .gitignore
├── .pre-commit-config.yaml
├── docker-compose.yml
├── Makefile
├── pytest.ini
│
├── docs/                        # 📚 Toda documentação centralizada
│   ├── CHECK.md
│   ├── VALIDATION.md
│   ├── IMPLEMENTATION_COMPLETE.md
│   ├── EXECUTIVE_SUMMARY.md
│   ├── PRACTICAL_VALIDATION_CHECKLIST.md
│   ├── FINAL_VALIDATION_REPORT.md
│   ├── TIMEZONE_PADRONIZATION_REPORT.md
│   ├── MAKEFILES-SUMMARY.md
│   ├── PRE_COMMIT_HOOKS.md
│   ├── DEVELOPMENT.md
│   └── README.md
│
├── scripts/                     # 🔧 Todos os scripts
│   ├── deploy.sh
│   ├── auto-resize-root.sh
│   ├── distribute_common.sh
│   ├── docker-cleanup-*.sh
│   ├── migrate_redis_jobs.py
│   └── ...
│
├── common/                      # 📦 Biblioteca compartilhada
│   ├── datetime_utils/
│   ├── config_utils/
│   ├── log_utils/
│   └── ...
│
├── services/                    # 🐳 Microserviços
│   ├── make-video/
│   ├── audio-transcriber/
│   ├── video-downloader/
│   ├── youtube-search/
│   └── audio-normalization/
│
└── orchestrator/               # 🎭 Orchestrator service
```

---

## 🐳 Estrutura Padrão de Microserviço

Cada serviço segue a mesma estrutura:

```
services/{service-name}/
├── README.md                    # ✅ Único .md na raiz
├── run.py                       # 🚀 Entry point principal
│
├── requirements.txt
├── requirements-docker.txt
├── constraints.txt
├── Dockerfile
├── docker-compose.yml
├── pytest.ini
├── Makefile
│
├── app/                         # 📱 Código da aplicação
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   ├── core/
│   ├── models/
│   ├── services/
│   └── infrastructure/
│
├── tests/                       # 🧪 Todos os testes
│   ├── __init__.py
│   ├── conftest.py             # Moved from root
│   ├── test_*.py               # Moved from root
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docs/                        # 📚 Documentação do serviço
│   ├── README.md
│   ├── API.md
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   └── ...                     # All .md files (except root README)
│
├── scripts/                     # 🔧 Scripts do serviço
│   ├── run_*.py                # Moved from root
│   ├── test_*.sh               # Moved from root
│   ├── validate_*.py           # Moved from root
│   └── ...                     # All .sh files
│
├── common/                      # 📦 Common library (copied)
│   ├── datetime_utils/
│   ├── config_utils/
│   └── ...
│
├── data/                        # 💾 Data directory
├── logs/                        # 📝 Logs directory
├── temp/                        # 🗃️ Temporary files
└── uploads/                     # 📤 Upload directory
```

---

## 📋 Regras de Organização

### ✅ Arquivos Permitidos na Raiz

#### Raiz do Projeto
- ✅ `README.md` (único .md permitido)
- ✅ `LICENSE`
- ✅ `.gitignore`, `.pre-commit-config.yaml`, `.bandit.yml`
- ✅ `docker-compose.yml`, `Makefile`, `pytest.ini`
- ✅ `package.json`, `pyproject.toml` (se aplicável)

#### Raiz de Cada Serviço
- ✅ `README.md` (único .md permitido)
- ✅ `run.py` (único entry point)
- ✅ `requirements*.txt`, `constraints.txt`
- ✅ `Dockerfile`, `docker-compose.yml`
- ✅ `Makefile`, `pytest.ini`

### ❌ Arquivos NÃO Permitidos na Raiz

- ❌ Qualquer `.md` adicional → **mover para `docs/`**
- ❌ Scripts `.sh` → **mover para `scripts/`**
- ❌ Arquivos `test_*.py` → **mover para `tests/`**
- ❌ Arquivos `run_*.py` (exceto `run.py`) → **mover para `scripts/`**
- ❌ `conftest.py` → **mover para `tests/`**
- ❌ Scripts `validate_*.py` → **mover para `scripts/`**

---

## 🔍 Mapeamento de Arquivos Reorganizados

### Raiz do Projeto

| Origem (antes) | Destino (depois) | Tipo |
|----------------|------------------|------|
| `CHECK.md` | `docs/CHECK.md` | Documentação |
| `VALIDATION.md` | `docs/VALIDATION.md` | Documentação |
| `IMPLEMENTATION_COMPLETE.md` | `docs/IMPLEMENTATION_COMPLETE.md` | Documentação |
| `EXECUTIVE_SUMMARY.md` | `docs/EXECUTIVE_SUMMARY.md` | Documentação |
| `deploy.sh` | `scripts/deploy.sh` | Script |
| `auto-resize-root.sh` | `scripts/auto-resize-root.sh` | Script |

### services/audio-transcriber/

| Origem | Destino | Tipo |
|--------|---------|------|
| `GUIA_DE_USO.md` | `docs/GUIA_DE_USO.md` | Documentação |
| `conftest.py` | `tests/conftest.py` | Config de testes |

### services/make-video/

| Origem | Destino | Tipo |
|--------|---------|------|
| `AUDIO_LEGEND_SYNC.md` | `docs/AUDIO_LEGEND_SYNC.md` | Documentação |
| `MELHORIAS_SINCRONIZACAO.md` | `docs/MELHORIAS_SINCRONIZACAO.md` | Documentação |
| `NEXT_STEPS.md` | `docs/NEXT_STEPS.md` | Documentação |

### services/video-downloader/

| Origem | Destino | Tipo |
|--------|---------|------|
| `conftest.py` | `tests/conftest.py` | Config de testes |
| `run_celery.py` | `scripts/run_celery.py` | Script runner |
| `run_tests.py` | `scripts/run_tests.py` | Script de teste |
| `validate_user_agents.py` | `scripts/validate_user_agents.py` | Validador |

### services/youtube-search/

| Origem | Destino | Tipo |
|--------|---------|------|
| `CHANGELOG.md` | `docs/CHANGELOG.md` | Documentação |
| `conftest.py` | `tests/conftest.py` | Config de testes |
| `test_all_endpoints.sh` | `scripts/test_all_endpoints.sh` | Script de teste |
| `test_shorts_feature.sh` | `scripts/test_shorts_feature.sh` | Script de teste |

### services/audio-normalization/

| Origem | Destino | Tipo |
|--------|---------|------|
| `test_gpu.py` | `tests/test_gpu.py` | Teste |

---

## 🎨 Convenções de Nomenclatura

### Arquivos de Documentação (`.md`)
- `README.md` - Overview principal
- `API.md` - Documentação de API
- `ARCHITECTURE.md` - Arquitetura do sistema
- `DEPLOYMENT.md` - Guia de deploy
- `CHANGELOG.md` - Histórico de mudanças
- `CONTRIBUTING.md` - Guia de contribuição

### Scripts (`.sh`, `.py`)
- `run_*.py` - Scripts runners
- `test_*.sh` - Scripts de teste
- `validate_*.py` - Scripts de validação
- `deploy*.sh` - Scripts de deploy
- `docker-*.sh` - Scripts Docker

### Testes (`test_*.py`)
- `test_unit_*.py` - Testes unitários
- `test_integration_*.py` - Testes de integração
- `test_e2e_*.py` - Testes end-to-end
- `conftest.py` - Configuração pytest

---

## 📊 Benefícios da Organização

### 1. **Navegação Intuitiva**
- Desenvolvedores sabem exatamente onde procurar
- Estrutura previsível em todos os serviços

### 2. **Separação de Responsabilidades**
- Código em `app/`
- Testes em `tests/`
- Documentação em `docs/`
- Scripts em `scripts/`

### 3. **CI/CD Otimizado**
- Paths previsíveis para automação
- Test discovery automático
- Build consistency

### 4. **Onboarding Rápido**
- Novos desenvolvedores entendem a estrutura imediatamente
- Documentação centralizada e acessível

### 5. **Manutenibilidade**
- Fácil localizar e modificar componentes
- Reduz duplicação acidental
- Facilita refactoring

---

## 🔄 Migrando para o Novo Padrão

Se você adicionar novos arquivos, siga estas diretrizes:

### Adicionando Documentação
```bash
# ❌ Errado
echo "# Novo Doc" > services/my-service/NEW_DOC.md

# ✅ Correto
echo "# Novo Doc" > services/my-service/docs/NEW_DOC.md
```

### Adicionando Scripts
```bash
# ❌ Errado
cp meu_script.sh services/my-service/

# ✅ Correto
cp meu_script.sh services/my-service/scripts/
chmod +x services/my-service/scripts/meu_script.sh
```

### Adicionando Testes
```bash
# ❌ Errado
echo "def test_foo(): pass" > services/my-service/test_foo.py

# ✅ Correto
echo "def test_foo(): pass" > services/my-service/tests/test_foo.py
```

---

## ✅ Checklist de Validação

Use este checklist ao criar/modificar um serviço:

- [ ] `README.md` é o único `.md` na raiz do serviço
- [ ] Todos os outros `.md` estão em `docs/`
- [ ] Todos os `.sh` estão em `scripts/`
- [ ] Todos os `test_*.py` estão em `tests/`
- [ ] `conftest.py` está em `tests/`
- [ ] Scripts auxiliares (`run_*.py`, `validate_*.py`) estão em `scripts/`
- [ ] Estrutura `app/`, `tests/`, `docs/`, `scripts/` existe
- [ ] `run.py` é o único entry point na raiz

---

## 🛠️ Ferramentas de Validação

### Script de Validação Automática

```bash
# Valida estrutura do projeto
./scripts/validate_structure.sh

# Valida estrutura de um serviço específico
./scripts/validate_structure.sh services/make-video
```

### Pre-commit Hook

O projeto usa pre-commit hooks que validam:
- Arquivos `.md` fora de `docs/`
- Arquivos `.sh` fora de `scripts/`
- Arquivos `test_*.py` fora de `tests/`

---

## 📚 Referências

Este padrão segue as melhores práticas de:
- [The Twelve-Factor App](https://12factor.net/)
- [Google Engineering Practices](https://google.github.io/eng-practices/)
- [Microsoft REST API Guidelines](https://github.com/microsoft/api-guidelines)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)

---

## 🤝 Contribuindo

Ao contribuir com o projeto:
1. Siga esta estrutura rigorosamente
2. Execute `./scripts/validate_structure.sh` antes de commit
3. Documente qualquer exceção necessária
4. Mantenha consistência entre serviços

---

**Mantido por**: YTCaption Engineering Team  
**Aplicado em**: 2026-02-28  
**Versão**: 1.0.0
