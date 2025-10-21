# ⚙️ Configuração de Linting e Formatação

Este projeto utiliza múltiplas ferramentas para garantir qualidade de código, mas configuradas de forma **não intrusiva** para não sobrecarregar o VS Code.

---

## 🛠️ Ferramentas Configuradas

### 1. **Pylance** (Análise de Tipo - VS Code)
- **Arquivo**: `.vscode/settings.json`
- **Modo**: `basic` (menos rigoroso)
- **Comportamento**: 
  - ✅ Detecta erros críticos (variáveis não definidas)
  - ⚠️ Avisos para imports não usados
  - ❌ **Desabilitado**: Erros de tipo, missing imports, optional access

### 2. **Pylint** (Análise de Código)
- **Arquivo**: `.pylintrc`
- **Comportamento**:
  - ✅ Detecta erros lógicos
  - ❌ **Desabilitado**: Docstrings obrigatórias, limites rígidos, import-error

### 3. **Flake8** (Estilo de Código)
- **Arquivo**: `.flake8`
- **Comportamento**:
  - ✅ Verifica PEP8 básico
  - ❌ **Desabilitado**: Linha muito longa, imports não usados em `__init__.py`

### 4. **Black** (Formatador)
- **Arquivo**: `pyproject.toml`
- **Configuração**: Linha máxima de 120 caracteres
- **Uso**: Manual (`black .`) - não formata automaticamente

---

## 📝 Arquivos de Configuração

```
.
├── .vscode/
│   └── settings.json       # Configurações do VS Code (Pylance)
├── .pylintrc               # Configurações do Pylint
├── .flake8                 # Configurações do Flake8
└── pyproject.toml          # Configurações do Black, MyPy, Ruff, Pytest
```

---

## 🎨 Redução de "Poluição Visual"

### Antes (com todos os avisos):
```python
from loguru import logger  # ❌ Import "loguru" could not be resolved
from src.config import settings  # ❌ Import could not be resolved

def process_data(data, config, timeout, retries):  # ❌ Too many arguments
    # ❌ Missing docstring
    result = some_optional_value.data  # ❌ Optional member access
    ...
```

### Depois (apenas erros críticos):
```python
from loguru import logger  # ✅ OK
from src.config import settings  # ✅ OK

def process_data(data, config, timeout, retries):  # ✅ OK
    result = some_optional_value.data  # ✅ OK
    ...
```

---

## 🚀 Como Usar

### Verificar Erros Manualmente

```bash
# Pylint (análise completa)
pylint src/

# Flake8 (estilo PEP8)
flake8 src/

# MyPy (tipos - opcional)
mypy src/
```

### Formatar Código

```bash
# Black (formatador automático)
black src/

# Black (apenas verificar, sem modificar)
black --check src/
```

### Organizar Imports

```bash
# isort (ordenar imports)
isort src/

# isort (apenas verificar)
isort --check-only src/
```

---

## ⚙️ Personalização Adicional

### Desabilitar Pylance Completamente

Adicionar em `.vscode/settings.json`:
```json
{
  "python.analysis.typeCheckingMode": "off"
}
```

### Desabilitar Pylint

Adicionar em `.vscode/settings.json`:
```json
{
  "python.linting.pylintEnabled": false
}
```

### Desabilitar Avisos Específicos por Arquivo

Adicionar no topo do arquivo `.py`:
```python
# pylint: disable=import-error,no-member
# type: ignore

from loguru import logger  # Não mostrará aviso
```

### Desabilitar Avisos por Linha

```python
from loguru import logger  # pylint: disable=import-error
resultado = valor.propriedade  # type: ignore
```

---

## 🔧 Problemas Comuns

### Problema: "Import could not be resolved"

**Causa**: Pylance não encontra o módulo instalado.

**Solução 1** (Recomendada): Já configurado em `.vscode/settings.json`:
```json
{
  "python.analysis.diagnosticSeverityOverrides": {
    "reportMissingImports": "none"
  }
}
```

**Solução 2**: Configurar Python interpreter corretamente:
1. `Ctrl+Shift+P` → "Python: Select Interpreter"
2. Escolher o ambiente virtual correto

**Solução 3**: Adicionar em `settings.json`:
```json
{
  "python.analysis.extraPaths": [
    "${workspaceFolder}/src"
  ]
}
```

---

### Problema: Muitos avisos de tipo

**Solução**: Já configurado em `.vscode/settings.json`:
```json
{
  "python.analysis.typeCheckingMode": "basic",
  "python.analysis.diagnosticSeverityOverrides": {
    "reportGeneralTypeIssues": "none",
    "reportOptionalMemberAccess": "none"
  }
}
```

---

### Problema: "Too many arguments"

**Solução**: Já configurado em `.pylintrc`:
```ini
[DESIGN]
max-args=10  # Permite até 10 argumentos
```

---

## 📊 Níveis de Rigor

### 🟢 Modo Atual (Balanceado)
- ✅ Detecta erros críticos
- ⚠️ Avisos para código suspeito
- ❌ Ignora estilo e tipos

### 🟡 Modo Relaxado (Para Desenvolvimento Rápido)

Adicionar em `.vscode/settings.json`:
```json
{
  "python.analysis.typeCheckingMode": "off",
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": false
}
```

### 🔴 Modo Rigoroso (Para Produção)

Modificar `.vscode/settings.json`:
```json
{
  "python.analysis.typeCheckingMode": "strict",
  "python.linting.mypyEnabled": true,
  "python.analysis.diagnosticSeverityOverrides": {
    "reportMissingImports": "error",
    "reportGeneralTypeIssues": "error"
  }
}
```

---

## 🧪 Integração com CI/CD

### GitHub Actions

```yaml
name: Lint

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pylint flake8 black
      
      - name: Run Pylint
        run: pylint src/ --exit-zero
      
      - name: Run Flake8
        run: flake8 src/ --exit-zero
      
      - name: Check Black formatting
        run: black --check src/ --diff
```

---

## 📚 Referências

- [Pylance Documentation](https://github.com/microsoft/pylance-release)
- [Pylint Documentation](https://pylint.pycqa.org/)
- [Flake8 Documentation](https://flake8.pycqa.org/)
- [Black Documentation](https://black.readthedocs.io/)
- [PEP 8 – Style Guide](https://peps.python.org/pep-0008/)

---

## ✅ Checklist de Configuração

- [x] ✅ `.vscode/settings.json` criado
- [x] ✅ `.pylintrc` criado
- [x] ✅ `.flake8` criado
- [x] ✅ `pyproject.toml` atualizado
- [x] ✅ Erros visuais minimizados
- [ ] ⏳ Testar configurações
- [ ] ⏳ Ajustar conforme necessário

---

**Configuração**: v2.0  
**Data**: 2024-01-15  
**Status**: ✅ Configurado para mínima poluição visual
