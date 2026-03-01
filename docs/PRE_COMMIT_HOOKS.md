# Pre-commit Hooks - Best Practices Guide
# YTCaption-Easy-Youtube-API

## 🎯 Overview

Este projeto usa **pre-commit hooks** para garantir qualidade de código e segurança antes de cada commit. Seguimos as **melhores práticas enterprise** de Google, Meta, Netflix e Microsoft.

## 📦 Instalação

```bash
# 1. Instalar pre-commit
pip install pre-commit

# 2. Instalar hooks no repositório
pre-commit install

# 3. (Opcional) Install commit-msg hook
pre-commit install --hook-type commit-msg
```

## 🚀 Uso

### Automático (Recomendado)
Os hooks rodam **automaticamente** em cada commit:
```bash
git add meu_arquivo.py
git commit -m "feat: minha mudança"
# → Pre-commit hooks rodam automaticamente
```

### Manual
Rodar em todos os arquivos:
```bash
pre-commit run --all-files
```

Rodar em arquivos específicos:
```bash
pre-commit run --files services/make-video/app/main.py
```

Rodar hook específico:
```bash
pre-commit run black --all-files
pre-commit run flake8 --all-files
```

## 🛠️ Hooks Configurados

### 1️⃣ **Generic Checks** (Básicos mas Essenciais)
- ✅ `check-added-large-files` - Previne arquivos > 1MB
- ✅ `check-merge-conflict` - Detecta conflitos de merge
- ✅ `detect-private-key` - Detecta chaves privadas
- ✅ `trailing-whitespace` - Remove espaços em branco
- ✅ `end-of-file-fixer` - Fix newline no fim do arquivo
- ✅ `check-yaml/json/toml` - Valida sintaxe

### 2️⃣ **Python Code Quality**
- 🎨 **Black** - Formatação automática (100 chars/line)
- 📦 **isort** - Organiza imports automaticamente
- 🔍 **Flake8** - Linting PEP8, complexidade < 15
  - Plugins: bugbear, comprehensions, simplify

### 3️⃣ **Python Security**
- 🔐 **Bandit** - Detecta vulnerabilidades de segurança
  - SQL injection, pickle usage, weak crypto, etc.
- 🕵️ **detect-secrets** - Previne commit de secrets/keys

### 4️⃣ **Python Type Checking**
- 📝 **MyPy** - Type checking estático
  - Garante type hints corretos

### 5️⃣ **Python Documentation**
- 📚 **Pydocstyle** - Valida docstrings (Google style)

### 6️⃣ **Docker**
- 🐳 **Hadolint** - Lint Dockerfiles (best practices)

### 7️⃣ **Custom Hooks** (Project-Specific)
- ⏰ **no-datetime-now** - Bloqueia datetime.now()
  - Força uso de now_brazil() (timezone-aware)
- 🧪 **pytest-check** - Roda testes em arquivos modificados
- 🐳 **docker-compose-check** - Valida docker-compose.yml

## 🎨 Workflow Típico

```bash
# 1. Fazer mudanças
vim services/make-video/app/main.py

# 2. Adicionar ao staging
git add services/make-video/app/main.py

# 3. Commit (hooks rodam automaticamente)
git commit -m "feat: add new endpoint"

# → Black formata o código
# → isort organiza imports
# → Flake8 valida lint
# → Bandit checa segurança
# → MyPy valida types
# → Custom hooks checam datetime.now()
# → Pytest roda testes relevantes

# 4. Se algum hook falhar:
#    - Arquivos são auto-corrigidos (Black, isort)
#    - Erros são mostrados (Flake8, Bandit)
#    - Fix manualmente e re-commit

# 5. Push (se tudo passou)
git push
```

## ⚙️ Configuração

### Skip Hooks (quando necessário)
Skip todos os hooks (USE COM CUIDADO):
```bash
git commit --no-verify -m "emergency fix"
```

Skip hook especcífico:
```bash
SKIP=flake8 git commit -m "wip: work in progress"
```

### Atualizar Hooks
```bash
pre-commit autoupdate
```

### Desinstalar
```bash
pre-commit uninstall
```

## 📋 Checklist de Boas Práticas

Antes de fazer commit, garanta:

- ✅ **Code Quality**
  - [ ] Código formatado com Black
  - [ ] Imports organizados com isort
  - [ ] Sem erros Flake8 (PEP8)
  - [ ] Complexidade < 15
  
- ✅ **Security**
  - [ ] Sem secrets/keys no código
  - [ ] Sem vulnerabilidades Bandit
  - [ ] SSL/TLS habilitado
  
- ✅ **Type Safety**
  - [ ] Type hints em funções públicas
  - [ ] MyPy passing
  
- ✅ **Documentation**
  - [ ] Docstrings em funções públicas
  - [ ] README atualizado
  
- ✅ **Project-Specific**
  - [ ] Usar now_brazil() ao invés de datetime.now()
  - [ ] Redis store com ensure_timezone_aware()
  - [ ] Testes passando

## 🏢 Enterprise Best Practices

Estas configurações seguem padrões de:

1. **Google Python Style Guide**
   - Docstrings, line length, complexity

2. **Meta (Facebook) OSS**
   - Black formatter, consistent style

3. **Netflix**
   - Security-first (Bandit, detect-secrets)

4. **Microsoft**
   - Type safety (MyPy), comprehensive testing

## 🐛 Troubleshooting

### Hook falha mas arquivo parece correto
```bash
# Re-instalar hooks
pre-commit clean
pre-commit install

# Rodar manualmente para debug
pre-commit run <hook-name> --files <file> --verbose
```

### Conflito entre Black e Flake8
Configuração já resolve (E203, W503 ignorados)

### MyPy errors em imports
Adicione types em `additional_dependencies` no `.pre-commit-config.yaml`

## 📚 Referências

- [Pre-commit Documentation](https://pre-commit.com/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Black Code Style](https://black.readthedocs.io/)
- [Bandit Security](https://bandit.readthedocs.io/)
- [MyPy Type Checking](https://mypy.readthedocs.io/)

---

**Mantido por**: YTCaption Engineering Team  
**Última atualização**: 2026-02-28
