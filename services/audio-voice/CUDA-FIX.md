# 🔧 CUDA Fix - PyTorch cu118 Configuration

## Problema Identificado

O serviço estava apresentando o warning:
```
CUDA requested but not available, falling back to CPU
```

### Causa Raiz

1. **Conflito de versões PyTorch**: 
   - Dockerfile instalava PyTorch cu118 (compatível com CUDA 11.8)
   - requirements.txt tinha `torch==2.4.0` sem especificar versão CUDA
   - Ao instalar requirements.txt, PyTorch era sobrescrito com versão cu121 (default)

2. **Biblioteca NVIDIA faltando nos containers**:
   - `/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1` não estava montada
   - nvidia-smi não funcionava nos containers
   - PyTorch não conseguia acessar GPU

## Solução Implementada

### 1. Correção do requirements.txt

**Removido torch e torchaudio** do requirements.txt, pois são instalados explicitamente no Dockerfile:

```diff
# === AUDIO PROCESSING CORE ===
- torch==2.4.0
- torchaudio==2.4.0
+ # torch e torchaudio são instalados no Dockerfile com versão específica cu118
numpy>=1.26.0,<1.27.0
soundfile==0.12.1
```

### 2. Correção do Dockerfile

Reorganizada ordem de instalação para **garantir PyTorch cu118**:

```dockerfile
# 🔥 Upgrade pip
RUN python -m pip install --no-cache-dir --upgrade pip

# 🔥 PyTorch CUDA 11.8 (DEVE ser instalado PRIMEIRO para evitar conflito)
RUN python -m pip install --no-cache-dir \
      torch==2.4.0 torchaudio==2.4.0 \
      --index-url https://download.pytorch.org/whl/cu118

# 🔥 Outras dependências (requirements.txt NÃO tem torch/torchaudio)
RUN python -m pip install --no-cache-dir --ignore-installed blinker \
      -r requirements.txt -c constraints.txt
```

### 3. Correção do docker-compose.yml

Adicionado bind mount de `libnvidia-ml.so.1` em **AMBOS** os serviços:

```yaml
services:
  audio-voice-service:
    volumes:
      # ... outros volumes ...
      - /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1:/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1:ro
  
  celery-worker:
    volumes:
      # ... outros volumes ...
      - /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1:/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1:ro
```

## Verificação

Após aplicar as correções, verificar:

```bash
# 1. Rebuild da imagem
docker compose build --no-cache

# 2. Restart dos containers
docker compose up -d

# 3. Verificar nvidia-smi
docker exec audio-voice-celery nvidia-smi

# 4. Verificar PyTorch CUDA
docker exec audio-voice-celery python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('CUDA version:', torch.version.cuda)"
```

**Resultado esperado:**
```
CUDA available: True
CUDA version: 11.8
```

## Ambiente

- **Driver NVIDIA**: 550.163.01
- **CUDA Runtime**: 11.8.0
- **PyTorch**: 2.4.0+cu118
- **Base Image**: nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

## Notas Importantes

⚠️ **Nunca adicione torch/torchaudio ao requirements.txt** - sempre instale via Dockerfile com index-url específico

⚠️ **Sempre monte libnvidia-ml.so.1** em containers que precisam acessar GPU

⚠️ **Use CUDA 11.8** - é mais compatível com drivers 550.x do que CUDA 12.x

## Status

- ✅ requirements.txt corrigido (torch removido)
- ✅ Dockerfile reorganizado (PyTorch cu118 primeiro)
- ✅ docker-compose.yml atualizado (bind mount libnvidia-ml.so.1)
- 🔄 Build em andamento...
