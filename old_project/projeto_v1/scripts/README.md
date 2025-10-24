# Scripts de Gerenciamento - YTCaption

Este diretório contém todos os scripts de gerenciamento do projeto YTCaption.

## 📋 Scripts Disponíveis

### 🚀 Principais

#### `start.sh`
Script principal de inicialização do projeto.

**Uso:**
```bash
cd /caminho/do/projeto
./scripts/start.sh [options]
```

**Opções:**
- `--force-rebuild` - Força rebuild das imagens Docker
- `--no-gpu` - Desabilita GPU mesmo se disponível
- `--no-parallel` - Desabilita modo paralelo (single-core)
- `--model MODEL` - Define modelo Whisper (tiny|base|small|medium|large)
- `--workers NUM` - Define número de workers Uvicorn
- `--parallel-workers N` - Define workers de transcrição paralela
- `--memory MB` - Limita memória Docker (em MB)
- `--help` - Mostra ajuda

**Exemplos:**
```bash
./scripts/start.sh                              # Start normal
./scripts/start.sh --model base --memory 2048   # Base model com 2GB RAM
./scripts/start.sh --no-parallel                # Modo single-core
```

---

### 🔍 Diagnóstico GPU

#### `gpu-diagnostic.sh`
Script completo de diagnóstico de GPU/CUDA.

**Uso:**
```bash
cd /caminho/do/projeto
./scripts/gpu-diagnostic.sh
```

**Verifica:**
- ✅ Hardware NVIDIA (via lspci)
- ✅ Driver NVIDIA (nvidia-smi)
- ✅ Módulos do kernel (lsmod)
- ✅ Pacotes de driver instalados
- ✅ CUDA Toolkit
- ✅ Docker GPU support
- ✅ Teste de acesso GPU no container

**Output:**
- Diagnóstico completo com status de cada componente
- Recomendações específicas baseadas no que foi detectado
- Comandos para resolver problemas encontrados

---

#### `install-nvidia-docker.sh`
Instala e configura NVIDIA Container Toolkit.

**Uso:**
```bash
cd /caminho/do/projeto
sudo ./scripts/install-nvidia-docker.sh
```

**Faz:**
1. Verifica pré-requisitos (driver NVIDIA, Docker)
2. Adiciona repositório NVIDIA Container Toolkit
3. Instala nvidia-container-toolkit
4. Configura Docker runtime
5. Reinicia Docker
6. Testa acesso GPU no container

**Requer:**
- ⚠️ Executar como root (`sudo`)
- ✅ NVIDIA driver instalado e funcionando
- ✅ Docker instalado

---

### 🔧 Gerenciamento

#### `stop.sh`
Para os containers Docker.

**Uso:**
```bash
./scripts/stop.sh
```

---

#### `status.sh`
Mostra status dos containers e recursos.

**Uso:**
```bash
./scripts/status.sh
```

---

#### `deploy.sh`
Script de deploy/atualização do projeto.

**Uso:**
```bash
./scripts/deploy.sh
```

---

#### `docker-cleanup-total.sh`
Limpeza total do ambiente Docker (remove tudo).

**Uso:**
```bash
./scripts/docker-cleanup-total.sh
```

**⚠️ CUIDADO:** Remove TODOS os containers, imagens, volumes e redes Docker!

---

## 📂 Estrutura do Projeto

Os scripts nesta pasta acessam arquivos na raiz do projeto:

```
YTCaption-Easy-Youtube-API/
├── scripts/           # ← Você está aqui
│   ├── start.sh
│   ├── stop.sh
│   ├── status.sh
│   ├── deploy.sh
│   ├── gpu-diagnostic.sh
│   ├── install-nvidia-docker.sh
│   └── docker-cleanup-total.sh
├── .env              # Arquivo de configuração (gerado por start.sh)
├── .env.example      # Template de configuração
├── docker-compose.yml # Configuração Docker
├── Dockerfile
└── src/              # Código fonte

```

## 🔄 Fluxo de Trabalho Típico

### Primeira Instalação:
```bash
# 1. Clonar repositório
git clone https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API

# 2. Diagnosticar GPU (se tiver)
./scripts/gpu-diagnostic.sh

# 3. Instalar NVIDIA Docker (se necessário)
sudo ./scripts/install-nvidia-docker.sh

# 4. Iniciar aplicação
./scripts/start.sh --model base --memory 2048
```

### Uso Diário:
```bash
# Iniciar
./scripts/start.sh

# Ver status
./scripts/status.sh

# Parar
./scripts/stop.sh
```

### Solução de Problemas:
```bash
# GPU não funciona?
./scripts/gpu-diagnostic.sh

# Reinstalar tudo?
./scripts/docker-cleanup-total.sh
./scripts/start.sh --force-rebuild
```

---

## 💡 Notas Importantes

### Caminhos Relativos
Todos os scripts foram projetados para serem executados da **raiz do projeto**:

✅ **CORRETO:**
```bash
cd /caminho/do/projeto
./scripts/start.sh
```

✅ **TAMBÉM FUNCIONA:**
```bash
cd /caminho/do/projeto/scripts
./start.sh
```

❌ **INCORRETO:**
```bash
cd /algum/outro/lugar
/caminho/completo/scripts/start.sh  # Pode não funcionar
```

### Permissões
Torne os scripts executáveis:
```bash
chmod +x scripts/*.sh
```

### Sistema Operacional
Estes scripts são para **Linux** (Ubuntu, Debian, etc).

Para **Windows**, use WSL2 ou Docker Desktop.

---

## 📖 Documentação Adicional

- **Arquitetura**: `docs/ARCHITECTURE-CONFIG-FLOW.md`
- **GPU vs CPU**: `docs/GPU-VS-CPU-GUIDE.md`
- **Flag Memory**: `docs/FEATURE-MEMORY-FLAG.md`
- **README Principal**: `../README.md`

---

## 🐛 Problemas Comuns

### "Permission denied" ao executar script
```bash
chmod +x scripts/start.sh
```

### "docker-compose not found"
```bash
# Instalar Docker Compose
sudo apt install docker-compose
```

### "nvidia-smi: command not found"
```bash
# Instalar driver NVIDIA
sudo apt install nvidia-driver-535
sudo reboot
```

### "Docker cannot access GPU"
```bash
# Instalar NVIDIA Docker
sudo ./scripts/install-nvidia-docker.sh
```

---

## 📞 Suporte

- **Issues**: https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/issues
- **Documentação**: Pasta `docs/`
- **Logs**: `docker-compose logs -f`
