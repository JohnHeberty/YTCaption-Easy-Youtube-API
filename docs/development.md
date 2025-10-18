# Guia de Desenvolvimento

## 🛠️ Setup de Desenvolvimento

### Pré-requisitos

- Python 3.9 - 3.11
- Git
- ffmpeg
- (Opcional) CUDA para GPU support

### Instalação

```bash
# 1. Clonar repositório
git clone <repository-url>
cd whisper-transcription-api

# 2. Criar ambiente virtual
python -m venv venv

# Ativar (Linux/Mac)
source venv/bin/activate

# Ativar (Windows)
.\\venv\\Scripts\\activate

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Instalar dependências de desenvolvimento
pip install pytest pytest-asyncio pytest-cov black flake8 mypy

# 5. Configurar ambiente
cp .env.example .env
```

### Configuração do IDE

#### VS Code

Criar `.vscode/settings.json`:

```json
{
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false,
  "editor.formatOnSave": true
}
```

#### PyCharm

- Configurar interpretador Python do venv
- Habilitar Black como formatador
- Configurar pytest como test runner

## 📁 Estrutura do Projeto

```
whisper-transcription-api/
├── src/                          # Código fonte
│   ├── domain/                   # Camada de domínio
│   │   ├── entities/             # Entidades
│   │   ├── value_objects/        # Objetos de valor
│   │   ├── interfaces/           # Interfaces (contratos)
│   │   └── exceptions.py         # Exceções
│   ├── application/              # Camada de aplicação
│   │   ├── use_cases/            # Casos de uso
│   │   └── dtos/                 # DTOs
│   ├── infrastructure/           # Camada de infraestrutura
│   │   ├── youtube/              # Implementação YouTube
│   │   ├── whisper/              # Implementação Whisper
│   │   └── storage/              # Implementação Storage
│   ├── presentation/             # Camada de apresentação
│   │   └── api/                  # FastAPI
│   │       ├── routes/           # Rotas
│   │       └── middlewares/      # Middlewares
│   └── config/                   # Configurações
├── tests/                        # Testes
│   ├── unit/                     # Testes unitários
│   └── integration/              # Testes de integração
├── docs/                         # Documentação
├── Dockerfile                    # Container Docker
├── docker-compose.yml            # Orquestração
├── requirements.txt              # Dependências
├── pyproject.toml               # Configuração do projeto
└── README.md                    # Documentação principal
```

## 🧪 Testes

### Executar Testes

```bash
# Todos os testes
pytest

# Com verbose
pytest -v

# Com coverage
pytest --cov=src --cov-report=html

# Apenas unit tests
pytest tests/unit/

# Apenas integration tests
pytest tests/integration/

# Teste específico
pytest tests/unit/test_youtube_url.py
```

### Escrever Testes

#### Exemplo: Teste Unitário

```python
# tests/unit/test_youtube_url.py
import pytest
from src.domain.value_objects import YouTubeURL

def test_valid_youtube_url():
    url = YouTubeURL.create("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert url.video_id == "dQw4w9WgXcQ"

def test_invalid_youtube_url():
    with pytest.raises(ValueError):
        YouTubeURL.create("https://invalid-url.com")
```

#### Exemplo: Teste de Integração

```python
# tests/integration/test_transcribe_use_case.py
import pytest
from src.application.use_cases import TranscribeYouTubeVideoUseCase
from src.application.dtos import TranscribeRequestDTO

@pytest.mark.asyncio
async def test_transcribe_video(
    transcribe_use_case: TranscribeYouTubeVideoUseCase
):
    request = TranscribeRequestDTO(
        youtube_url="https://www.youtube.com/watch?v=test",
        language="auto"
    )
    
    response = await transcribe_use_case.execute(request)
    
    assert response.transcription_id is not None
    assert response.language is not None
    assert len(response.segments) > 0
```

### Mocks e Fixtures

```python
# tests/conftest.py
import pytest
from unittest.mock import Mock
from src.domain.interfaces import IVideoDownloader

@pytest.fixture
def mock_video_downloader():
    mock = Mock(spec=IVideoDownloader)
    # Configurar comportamento do mock
    return mock
```

## 🎨 Code Style

### Black (Formatação)

```bash
# Formatar todo o código
black src/ tests/

# Verificar sem modificar
black --check src/ tests/

# Formatar arquivo específico
black src/domain/entities/transcription.py
```

### Flake8 (Linting)

```bash
# Verificar todo o código
flake8 src/ tests/

# Verificar arquivo específico
flake8 src/domain/entities/transcription.py
```

### MyPy (Type Checking)

```bash
# Verificar tipos
mypy src/

# Ignorar cache
mypy --no-incremental src/
```

### Configuração

```toml
# pyproject.toml
[tool.black]
line-length = 100
target-version = ['py311']

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
```

## 🔄 Workflow de Desenvolvimento

### 1. Criar Nova Feature

```bash
# Criar branch
git checkout -b feature/nova-funcionalidade

# Desenvolver...

# Rodar testes
pytest

# Formatar código
black src/ tests/

# Lint
flake8 src/ tests/

# Commit
git add .
git commit -m "feat: adiciona nova funcionalidade"
```

### 2. Adicionar Nova Entidade (Domain)

```python
# src/domain/entities/nova_entidade.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class NovaEntidade:
    """Nova entidade de domínio."""
    
    id: str
    nome: str
    criado_em: datetime
    
    def metodo_de_dominio(self) -> bool:
        """Lógica de negócio."""
        return True
```

### 3. Adicionar Novo Use Case (Application)

```python
# src/application/use_cases/novo_use_case.py
from src.domain.interfaces import IAlgumServico

class NovoUseCase:
    """Use case para nova funcionalidade."""
    
    def __init__(self, servico: IAlgumServico):
        self.servico = servico
    
    async def execute(self, request: RequestDTO) -> ResponseDTO:
        """Executa o use case."""
        # Lógica...
        return ResponseDTO(...)
```

### 4. Adicionar Nova Implementação (Infrastructure)

```python
# src/infrastructure/novo_servico/implementacao.py
from src.domain.interfaces import INovoServico

class NovaImplementacao(INovoServico):
    """Implementação concreta."""
    
    async def metodo(self, parametro: str) -> str:
        """Implementa método da interface."""
        # Código...
        return resultado
```

### 5. Adicionar Nova Rota (Presentation)

```python
# src/presentation/api/routes/nova_rota.py
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/v1/nova", tags=["Nova"])

@router.post("")
async def endpoint(
    request: RequestDTO,
    use_case: NovoUseCase = Depends(get_use_case)
):
    """Novo endpoint."""
    return await use_case.execute(request)
```

## 🐛 Debug

### Logging

```python
from loguru import logger

# Em qualquer arquivo
logger.debug("Mensagem de debug")
logger.info("Informação")
logger.warning("Aviso")
logger.error("Erro")
logger.exception("Erro com stacktrace")
```

### Configurar Nível de Log

```env
# .env
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

### Debug no VS Code

```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "src.presentation.api.main:app",
        "--reload"
      ],
      "jinja": true,
      "justMyCode": false
    }
  ]
}
```

## 📦 Gerenciamento de Dependências

### Adicionar Nova Dependência

```bash
# Instalar
pip install nova-biblioteca

# Adicionar ao requirements.txt
pip freeze | grep nova-biblioteca >> requirements.txt

# Ou manualmente em requirements.txt
echo "nova-biblioteca==1.0.0" >> requirements.txt
```

### Atualizar Dependências

```bash
# Atualizar tudo
pip install -U -r requirements.txt

# Atualizar específica
pip install -U nome-da-biblioteca
```

## 🔐 Variáveis de Ambiente

### Desenvolvimento

```env
# .env (local)
APP_ENVIRONMENT=development
LOG_LEVEL=DEBUG
WHISPER_MODEL=tiny  # Modelo menor para testes
```

### Produção

```env
# .env (produção)
APP_ENVIRONMENT=production
LOG_LEVEL=INFO
WHISPER_MODEL=base
```

## 📚 Documentação

### Docstrings

Seguir Google Style:

```python
def funcao(parametro: str) -> bool:
    """
    Breve descrição da função.
    
    Descrição mais detalhada se necessário.
    
    Args:
        parametro: Descrição do parâmetro
        
    Returns:
        bool: Descrição do retorno
        
    Raises:
        ValueError: Quando parametro é inválido
        
    Example:
        >>> funcao("teste")
        True
    """
    return True
```

### Atualizar Documentação

```bash
# Documentação na pasta docs/
# Usar Markdown para clareza
```

## 🚀 Deploy Local

### Rodar com Uvicorn

```bash
# Desenvolvimento (com reload)
uvicorn src.presentation.api.main:app --reload --port 8000

# Produção (múltiplos workers)
uvicorn src.presentation.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Rodar com Docker

```bash
# Build
docker build -t whisper-api .

# Run
docker run -p 8000:8000 --env-file .env whisper-api
```

## 🤝 Contribuição

### Padrões de Commit

Seguir [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: adiciona nova funcionalidade
fix: corrige bug
docs: atualiza documentação
style: formatação de código
refactor: refatoração sem mudança de comportamento
test: adiciona ou corrige testes
chore: tarefas de build/CI
```

### Pull Request

1. Fork o projeto
2. Criar branch: `git checkout -b feature/nova-feature`
3. Commit: `git commit -m 'feat: adiciona nova feature'`
4. Push: `git push origin feature/nova-feature`
5. Abrir Pull Request

### Code Review

Checklist:
- [ ] Código segue style guide
- [ ] Testes passam
- [ ] Coverage mantido/aumentado
- [ ] Documentação atualizada
- [ ] Sem warnings do linter
- [ ] Types corretos (mypy)

## 🎯 Melhores Práticas

### ✅ Faça

- ✅ Escreva testes para código novo
- ✅ Use type hints
- ✅ Documente funções complexas
- ✅ Siga Clean Architecture
- ✅ Aplique SOLID principles
- ✅ Use async/await corretamente
- ✅ Trate exceções apropriadamente
- ✅ Valide inputs

### ❌ Evite

- ❌ Lógica de negócio na camada de apresentação
- ❌ Acoplamento entre camadas
- ❌ Dependências circulares
- ❌ Código duplicado
- ❌ Magic numbers
- ❌ Variáveis globais mutáveis
- ❌ Exceções genéricas (`except Exception`)
- ❌ Commits diretos na main

## 📖 Recursos

### Documentação de Dependências

- [FastAPI](https://fastapi.tiangolo.com/)
- [Pydantic](https://pydantic-docs.helpmanual.io/)
- [Whisper](https://github.com/openai/whisper)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

### Artigos e Tutoriais

- Clean Architecture em Python
- SOLID Principles
- FastAPI Best Practices
- Async/Await em Python

---

**Happy coding! 🚀**
