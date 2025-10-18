# Whisper Transcription API

🎙️ **API REST para transcrição de vídeos do YouTube usando OpenAI Whisper**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-green)](https://fastapi.tiangolo.com/)
[![Whisper](https://img.shields.io/badge/OpenAI-Whisper-orange)](https://github.com/openai/whisper)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📋 Descrição

API profissional para transcrição automática de vídeos do YouTube, construída com **Clean Architecture**, princípios **SOLID** e **FastAPI**. A API baixa vídeos na menor qualidade possível (focando no áudio), transcreve usando Whisper e retorna captions com timestamps precisos.

## ✨ Características

- 🎥 **Download automático** de vídeos do YouTube (menor qualidade para otimização)
- 🎙️ **Transcrição de alta qualidade** usando OpenAI Whisper
- ⏱️ **Segmentos timestampados** com precisão
- 🌍 **Suporte multilíngue** com detecção automática de idioma
- 🧹 **Limpeza automática** de arquivos temporários
- 🏗️ **Clean Architecture** com separação clara de responsabilidades
- 🔧 **SOLID principles** aplicados em toda a base de código
- 📊 **Health checks** e monitoramento
- 🐳 **Docker pronto** para deploy em containers Linux
- 📚 **Documentação automática** com Swagger/OpenAPI

## 🏗️ Arquitetura

O projeto segue **Clean Architecture** com as seguintes camadas:

```
src/
├── domain/              # Regras de negócio e entidades
│   ├── entities/        # Entidades do domínio
│   ├── value_objects/   # Objetos de valor
│   ├── interfaces/      # Interfaces (contratos)
│   └── exceptions.py    # Exceções customizadas
├── application/         # Casos de uso
│   ├── use_cases/       # Lógica de aplicação
│   └── dtos/            # Data Transfer Objects
├── infrastructure/      # Implementações concretas
│   ├── youtube/         # Download de vídeos
│   ├── whisper/         # Serviço de transcrição
│   └── storage/         # Gerenciamento de storage
├── presentation/        # Camada de apresentação
│   └── api/             # FastAPI routes e middlewares
└── config/              # Configurações
```

## 🚀 Quick Start

### Usando Docker (Recomendado)

```bash
# 1. Clone o repositório
git clone <repository-url>
cd whisper-transcription-api

# 2. Configure as variáveis de ambiente
cp .env.example .env

# 3. Build e execute com Docker Compose
docker-compose up -d

# 4. Acesse a API
curl http://localhost:8000/health
```

### Desenvolvimento Local

```bash
# 1. Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
.\\venv\\Scripts\\activate  # Windows

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Configurar variáveis de ambiente
cp .env.example .env

# 4. Executar a API
python -m uvicorn src.presentation.api.main:app --reload
```

## 📖 Documentação da API

Após iniciar a API, acesse:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Endpoint Principal

**POST** `/api/v1/transcribe`

Transcreve um vídeo do YouTube.

**Request:**
```json
{
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "language": "auto"
}
```

**Response:**
```json
{
  "transcription_id": "123e4567-e89b-12d3-a456-426614174000",
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "video_id": "dQw4w9WgXcQ",
  "language": "en",
  "full_text": "Never gonna give you up...",
  "segments": [
    {
      "text": "Never gonna give you up",
      "start": 0.0,
      "end": 2.5,
      "duration": 2.5
    }
  ],
  "total_segments": 42,
  "duration": 213.5,
  "processing_time": 15.3
}
```

### Exemplo com cURL

```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \\
  -H "Content-Type: application/json" \\
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "language": "auto"
  }'
```

### Exemplo com Python

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/transcribe",
    json={
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "language": "auto"
    }
)

data = response.json()
print(f"Idioma: {data['language']}")
print(f"Texto: {data['full_text']}")
```

## ⚙️ Configuração

Principais variáveis de ambiente (`.env`):

```env
# Whisper Settings
WHISPER_MODEL=base          # tiny, base, small, medium, large, turbo
WHISPER_DEVICE=cpu          # cpu ou cuda
WHISPER_LANGUAGE=auto       # auto ou código do idioma

# Download Settings
MAX_VIDEO_SIZE_MB=500       # Tamanho máximo do vídeo
DOWNLOAD_TIMEOUT=300        # Timeout em segundos

# Storage Settings
TEMP_DIR=./temp             # Diretório temporário
CLEANUP_ON_STARTUP=true     # Limpar ao iniciar
CLEANUP_AFTER_PROCESSING=true  # Limpar após processar
MAX_TEMP_AGE_HOURS=24       # Idade máxima dos arquivos

# API Settings
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

## 🐳 Deploy com Docker no Proxmox

### 1. Preparar o Container LXC no Proxmox

```bash
# No Proxmox, criar container Linux
pct create 100 local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.gz \\
  --hostname whisper-api \\
  --memory 4096 \\
  --cores 2 \\
  --net0 name=eth0,bridge=vmbr0,ip=dhcp

# Instalar Docker no container
apt update && apt install -y docker.io docker-compose
```

### 2. Deploy da Aplicação

```bash
# Copiar arquivos para o container
scp -r . root@<container-ip>:/opt/whisper-api/

# No container
cd /opt/whisper-api
docker-compose up -d

# Verificar logs
docker-compose logs -f
```

### 3. Configurar como Serviço

```bash
# Criar systemd service
cat > /etc/systemd/system/whisper-api.service <<EOF
[Unit]
Description=Whisper Transcription API
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/whisper-api
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

systemctl enable whisper-api
systemctl start whisper-api
```

## 📚 Documentação Adicional

Documentação detalhada disponível em `/docs`:

- [Arquitetura do Sistema](docs/architecture.md)
- [Guia do Whisper](docs/whisper-guide.md)
- [Deploy e Operação](docs/deployment.md)
- [Desenvolvimento](docs/development.md)

## 🧪 Testes

```bash
# Executar todos os testes
pytest

# Com coverage
pytest --cov=src --cov-report=html

# Testes específicos
pytest tests/unit/
pytest tests/integration/
```

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor:

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📝 Licença

Este projeto está licenciado sob a MIT License - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 🙏 Agradecimentos

- [OpenAI Whisper](https://github.com/openai/whisper) - Modelo de transcrição
- [FastAPI](https://fastapi.tiangolo.com/) - Framework web
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Download de vídeos

## 📞 Suporte

Para questões e suporte:
- Abra uma [issue](../../issues)
- Consulte a [documentação](docs/)

---

**Desenvolvido com ❤️ seguindo as melhores práticas de engenharia de software**
