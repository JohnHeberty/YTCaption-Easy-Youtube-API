# 🔧 Installation

**Guia completo de instalação - Docker, Local e Proxmox.**

---

## 🐳 Instalação com Docker (Recomendado)

### Pré-requisitos
- Docker 20.10+
- Docker Compose 2.0+
- 2GB RAM mínimo
- 10GB espaço em disco

### Passos

#### 1. Clone o repositório
```bash
git clone https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API
```

#### 2. Configure variáveis de ambiente
```bash
cp .env.example .env
nano .env  # Ou seu editor preferido
```

#### 3. Construa e inicie
```bash
docker-compose up -d
```

#### 4. Verifique logs
```bash
docker-compose logs -f
```

#### 5. 🆕 Aguarde Tor inicializar (v3.0)
```bash
# Aguarde Tor estabelecer circuito (30-60s)
docker-compose logs torproxy | grep "Bootstrapped 100%"

# Esperado: "Bootstrapped 100% (done): Done"
```

#### 6. Teste a API
```bash
curl http://localhost:8000/health
```

**🆕 Teste download com Tor (v3.0)**:
```bash
# Dentro do container
docker-compose exec app curl --socks5-hostname torproxy:9050 https://check.torproject.org

# Esperado: "Congratulations. This browser is configured to use Tor."
```

---

## 💻 Instalação Local (Desenvolvimento)

### Pré-requisitos
- Python 3.11+
- FFmpeg (para Whisper)
- Git
- 4GB RAM mínimo

### Passos

#### 1. Clone o repositório
```bash
git clone https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API
```

#### 2. Crie ambiente virtual
```bash
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Windows (CMD)
.\venv\Scripts\activate.bat
```

#### 3. Instale dependências
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. Instale FFmpeg

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Linux (CentOS/RHEL):**
```bash
sudo yum install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
```powershell
# Usando Chocolatey
choco install ffmpeg

# Ou baixe de: https://ffmpeg.org/download.html
```

**Verifique instalação:**
```bash
ffmpeg -version
```

#### 5. Configure ambiente
```bash
cp .env.example .env
```

#### 6. Inicie o servidor
```bash
python -m uvicorn src.presentation.api.main:app --reload --host 0.0.0.0 --port 8000
```

#### 7. Acesse
```
http://localhost:8000/docs
```

---

## 🖥️ Instalação no Proxmox/Linux Server

### Método 1: Script Automático (Recomendado)

```bash
# 1. Clone o repositório
git clone https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API

# 2. Dê permissão de execução
chmod +x start.sh

# 3. Execute o script
./start.sh
```

**O script irá:**
- ✅ Detectar hardware (CPU, RAM, GPU)
- ✅ Instalar Docker se necessário
- ✅ Configurar `.env` automaticamente
- ✅ Recomendar modelo Whisper
- ✅ Iniciar serviço

**Opções do script:**
```bash
./start.sh --help                  # Ver todas as opções
./start.sh --model base            # Escolher modelo
./start.sh --workers 2             # Definir workers API
./start.sh --parallel-workers 4    # Definir workers transcrição
./start.sh --no-gpu                # Forçar CPU
./start.sh --force-rebuild         # Rebuild imagens
```

### Método 2: Manual

#### 1. Instale Docker
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

#### 2. Instale Docker Compose
```bash
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### 3. Clone e configure
```bash
git clone https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API
cp .env.example .env
```

#### 4. Ajuste recursos no docker-compose.yml
```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '4'        # Ajuste para seus cores
          memory: 8G       # Ajuste para sua RAM
```

#### 5. Inicie
```bash
docker-compose up -d
```

---

## 🎮 Instalação com GPU (NVIDIA CUDA)

### Pré-requisitos
- GPU NVIDIA compatível
- Drivers NVIDIA instalados
- NVIDIA Container Toolkit

### Instalar NVIDIA Container Toolkit

```bash
# 1. Setup repositório
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# 2. Instale
sudo apt-get update
sudo apt-get install -y nvidia-docker2

# 3. Reinicie Docker
sudo systemctl restart docker

# 4. Teste
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### Configure para usar GPU

**docker-compose.yml:**
```yaml
services:
  api:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

**.env:**
```bash
WHISPER_DEVICE=cuda
WHISPER_MODEL=medium  # GPU aguenta modelos maiores
```

---

## 🔄 Atualização

### Docker
```bash
cd YTCaption-Easy-Youtube-API
git pull
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Local
```bash
cd YTCaption-Easy-Youtube-API
git pull
source venv/bin/activate  # Ative o venv
pip install -r requirements.txt --upgrade
```

---

## 🗑️ Desinstalação

### Docker
```bash
cd YTCaption-Easy-Youtube-API
docker-compose down -v  # Remove containers e volumes
cd ..
rm -rf YTCaption-Easy-Youtube-API
```

### Local
```bash
cd YTCaption-Easy-Youtube-API
deactivate  # Desative venv
cd ..
rm -rf YTCaption-Easy-Youtube-API
```

---

## ✅ Verificação de Instalação

### 1. Health Check
```bash
curl http://localhost:8000/health
```

**Esperado:**
```json
{"status": "healthy"}
```

### 2. Versão da API
```bash
curl http://localhost:8000/api/v1/
```

### 3. Teste de transcrição
```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "use_youtube_transcript": true
  }'
```

---

## 🆘 Problemas na Instalação?

Veja **[Troubleshooting](./08-TROUBLESHOOTING.md)** para soluções.

---

**Próximo**: [Configuração Completa](./03-CONFIGURATION.md)

**Versão**: 1.3.3+  
**Última atualização**: 19/10/2025
