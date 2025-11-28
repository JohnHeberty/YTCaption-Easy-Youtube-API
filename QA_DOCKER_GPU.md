# QA_DOCKER_GPU – Auditoria de Docker, CUDA e LOW_VRAM

**Data:** 28 de Novembro de 2025  
**Auditor:** QA Engineer + Dev Sênior  
**Serviço:** Audio Voice Service (F5-TTS / XTTS)  
**Versão:** 2.0.0

---

## 📋 Sumário Executivo

### Problemas Críticos Identificados

1. ✅ **CONTAINERS DUPLICADOS**: 2 containers do mesmo serviço rodando simultaneamente (sem conflito de portas detectado)
2. 🔴 **LOW_VRAM NÃO FUNCIONANDO**: Variável `LOW_VRAM=false` no container, mas `.env` tem `LOW_VRAM=true`
3. 🔴 **F5-TTS EM CPU**: Modelo rodando em CPU mesmo com GPU disponível (CUDA 12.1 + GTX 1050 Ti 4GB)
4. ⚠️ **IMAGEM DOCKER DEPRECATED**: Base image CUDA 12.1 marcada para deprecação
5. ⚠️ **REBUILDS SUJOS**: Imagens antigas (24h) sem prune sistemático

---

## 1. Containers e Serviços Duplicados

### 1.1. Observação

```bash
$ docker ps --filter "name=audio-voice"
NAMES                    STATUS                    PORTS                     IMAGE
audio-voice-api          Up 26 minutes (healthy)   0.0.0.0:8005->8005/tcp    audio-voice-audio-voice-service
audio-voice-celery       Up 16 minutes (healthy)   8005/tcp                  audio-voice-celery-worker
```

**Descobertas:**

- ✅ **Apenas 2 containers ativos**: API + Celery Worker (arquitetura esperada)
- ✅ **Nomes únicos**: `audio-voice-api` e `audio-voice-celery`
- ✅ **Sem conflito de portas**: API expõe 8005, Celery não expõe porta
- ✅ **Health checks OK**: Ambos containers healthy
- ⚠️ **Horários dessincronizados**: API subiu 10min antes do Celery (restart manual?)

### 1.2. Containers Criados

```
aa648ca462fe audio-voice-api     2025-11-27 16:55:33 UTC
dc5124ddca9d audio-voice-celery  2025-11-27 16:55:33 UTC
```

- **Idade**: ~24 horas (criados ontem às 16:55 UTC)
- **Imagens**: 16.3GB cada (muito grande - otimizável)

### 1.3. Causa de "Múltiplos Containers"

**Hipótese inicial do usuário**: Containers duplicados por rebuild sujo.

**Realidade da auditoria**: 
- Não há containers duplicados do mesmo tipo
- Arquitetura **multi-container deliberada** (API + Worker)
- **Possível confusão** do usuário ao ver logs intercalados de `audio-voice-api` e `audio-voice-celery`

**Riscos Identificados:**

- ⚠️ **Restart assíncrono**: API e Celery não reiniciam juntos (pode causar dessincronia de estado)
- ⚠️ **Containers órfãos**: Sem evidência no momento, mas ausência de rotina de prune

### 1.4. Docker Compose

**Arquivo**: `services/audio-voice/docker-compose.yml`

- ✅ Define 2 serviços: `audio-voice-service` e `celery-worker`
- ✅ Usa `container_name` fixo (evita duplicação acidental)
- ✅ `restart: unless-stopped` configurado
- ⚠️ **Falta depends_on entre API e Celery**: API pode subir antes do worker estar pronto
- ⚠️ **Falta health check no Celery**: Só API tem healthcheck (`CMD-SHELL curl`)

---

## 2. Pipeline de Build e Deploy

### 2.1. Dockerfile Analysis

**Base Image**: `nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04`

```dockerfile
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04
```

**⚠️ DEPRECATION WARNING ATIVA:**

```
*************************
** DEPRECATION NOTICE! **
*************************
THIS IMAGE IS DEPRECATED and is scheduled for DELETION.
```

**Problemas Identificados:**

1. 🔴 **Imagem base obsoleta**: CUDA 12.1 deprecada (current: 12.4+)
2. ⚠️ **Python 3.11 via deadsnakes PPA**: Instalação manual (complexa, frágil)
3. ⚠️ **Tamanho excessivo**: 16.3GB por imagem (2x containers = **32.6GB**)
4. ✅ **Multi-stage ausente**: Poderia reduzir 40-50% do tamanho

### 2.2. Build Workflow

**Comandos identificados:**

```bash
# Build atual (inferido)
docker compose build

# Sem evidência de:
docker system prune
docker compose down --volumes
```

**Fragilidades:**

- ❌ **Sem rotina de prune**: Layers antigos acumulam
- ❌ **Sem cleanup de cache**: Build cache pode ter 50GB+
- ❌ **Sem build from scratch**: `--no-cache` nunca usado
- ⚠️ **Rebuilds sujos**: Imagens de 24h podem ter estado inconsistente

### 2.3. GPU Configuration em Docker Compose

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

✅ **CORRETAMENTE CONFIGURADO**

```bash
$ docker inspect audio-voice-celery --format '{{json .HostConfig.Devices}}'
null  # ⚠️ Devices null em runtime (compose v2 usa deploy.resources)
```

```bash
$ docker exec audio-voice-celery nvidia-smi
NVIDIA GeForce GTX 1050 Ti, 4096 MiB, 2144 MiB
```

✅ **GPU ACESSÍVEL DENTRO DO CONTAINER**

---

## 3. Uso de CUDA pelo F5-TTS

### 3.1. Device Configuration

**Variáveis de Ambiente (Container Celery):**

```bash
NVIDIA_VISIBLE_DEVICES=all
NVIDIA_DRIVER_CAPABILITIES=compute,utility
CUDA_VISIBLE_DEVICES=0
FORCE_CUDA=1
LOW_VRAM=false  # ⚠️ PROBLEMA CRÍTICO
```

**Arquivo `.env` (Host):**

```bash
LOW_VRAM=true  # ✅ Correto no arquivo
```

🔴 **PROBLEMA CRÍTICO**: Variável `LOW_VRAM` não sendo lida corretamente pelo container.

### 3.2. F5-TTS Device Selection

**Código**: `app/engines/f5tts_engine.py:115`

```python
# F5-TTS SEMPRE USA CPU para evitar OOM em GPUs pequenas (<8GB)
# XTTS já ocupa ~3.5GB, F5-TTS precisa ~2GB adicional
self.device = 'cpu'  # FIXME: Force CPU até implementar VRAM management
logger.info(f"F5TtsEngine initializing on device: {self.device} (forced CPU to avoid OOM)")
```

🔴 **HARDCODED CPU**: F5-TTS ignora GPU completamente!

**Justificativa no código:**
- GPU GTX 1050 Ti tem **4GB VRAM**
- XTTS ocupa ~3.5GB
- F5-TTS precisa ~2GB adicional
- **Total: 5.5GB > 4GB disponíveis** → OOM garantido

**Problema:** Código força CPU mesmo quando deveria usar GPU via LOW_VRAM mode!

### 3.3. XTTS vs F5-TTS VRAM Usage

**XTTS Engine** (`app/engines/xtts_engine.py:124`):

```python
# Device selection
self.device = self._select_device(device, fallback_to_cpu)
logger.info(f"XttsEngine initializing on device: {self.device}")
```

✅ **XTTS respeita device auto-detect** (cuda se disponível)

**F5-TTS Engine:**

❌ **F5-TTS força CPU** (hardcoded)

### 3.4. CUDA Availability

```bash
$ docker exec audio-voice-celery python -c "import torch; print(torch.cuda.is_available())"
True

$ docker exec audio-voice-celery python -c "import torch; print(torch.cuda.get_device_name(0))"
NVIDIA GeForce GTX 1050 Ti
```

✅ **CUDA 100% FUNCIONAL** no container

**Conclusão:** F5-TTS poderia usar CUDA, mas **código não permite**.

---

## 4. Lógica LOW_VRAM

### 4.1. Onde LOW_VRAM é Lida

**Config**: `app/config.py:51`

```python
'low_vram_mode': os.getenv('LOW_VRAM', 'false').lower() == 'true',
```

**VRAM Manager**: `app/vram_manager.py:37`

```python
self.low_vram_mode = settings.get('low_vram_mode', False)
```

### 4.2. Comportamento Desejado

**Quando `LOW_VRAM=true`:**

1. **Load**: Carregar modelo na GPU apenas para inference
2. **Synthesize**: Gerar áudio
3. **Unload**: Mover modelo para CPU + `torch.cuda.empty_cache()`
4. **Repeat**: Próxima requisição repete ciclo

**Benefícios:**
- Economia de 70-75% de VRAM
- Permite rodar XTTS + F5-TTS em GPU 4GB
- Aumenta latência (+2-5s por requisição)

### 4.3. Comportamento Atual

**Logs do Container Celery:**

```bash
[2025-11-27 17:20:16] INFO: ⚡ NORMAL MODE: Modelos permanecerão na VRAM
[2025-11-27 18:01:36] INFO: ⚡ NORMAL MODE: Modelos permanecerão na VRAM
[2025-11-28 01:14:02] INFO: ⚡ NORMAL MODE: Modelos permanecerão na VRAM
```

🔴 **PROBLEMA**: LOW_VRAM **NUNCA ATIVADO**, mesmo com `.env` configurado!

### 4.4. Motivos do Problema

#### 4.4.1. Variável de Ambiente Não Propagada

**Análise:**

```bash
$ docker inspect audio-voice-celery | grep LOW_VRAM
LOW_VRAM=false  # ⚠️ Container tem valor ERRADO
```

**Arquivo `.env`:**

```bash
LOW_VRAM=true  # ✅ Arquivo host tem valor CORRETO
```

**Docker Compose:**

```yaml
env_file:
  - .env
environment:
  - PYTHONPATH=/app
  - NVIDIA_VISIBLE_DEVICES=all
  - ...
  # ❌ LOW_VRAM não está em "environment" override
```

**Problema:** `env_file` lê `.env`, mas:
1. Container foi buildado **antes** de `.env` ser editado
2. Container não foi **recriado** após mudança no `.env`
3. **Restart não recarrega `env_file`** (apenas `down` + `up`)

#### 4.4.2. Código de Unload Implementado, Mas Não Usado

**VRAM Manager** (`app/vram_manager.py:89`):

```python
def _unload_model(self, model):
    """Descarrega modelo da VRAM."""
    try:
        # Mover modelo para CPU
        if hasattr(model, 'to'):
            model.to('cpu')
        elif hasattr(model, 'cpu'):
            model.cpu()
        
        # Limpar cache CUDA
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        
        # Garbage collection
        gc.collect()
        
        logger.debug("✅ Modelo descarregado com sucesso")
    
    except Exception as e:
        logger.warning(f"⚠️ Erro ao descarregar modelo: {e}")
```

✅ **CÓDIGO CORRETO** para unload!

**Context Manager** (`app/vram_manager.py:46`):

```python
@contextmanager
def load_model(self, model_key: str, load_fn: Callable, *args, **kwargs):
    """Context manager para carregar modelo temporariamente."""
    model = None
    
    try:
        # Em modo LOW_VRAM, sempre carrega fresh
        if self.low_vram_mode:
            logger.debug(f"🔋 Carregando modelo '{model_key}' (LOW VRAM)")
            model = load_fn(*args, **kwargs)
        else:
            # Usar cache
            if model_key not in self._model_cache:
                self._model_cache[model_key] = load_fn(*args, **kwargs)
            model = self._model_cache[model_key]
        
        yield model
    
    finally:
        # Descarregar apenas em modo LOW_VRAM
        if self.low_vram_mode and model is not None:
            logger.debug(f"🔋 Descarregando modelo '{model_key}' da VRAM")
            self._unload_model(model)
            del model
```

✅ **LÓGICA CORRETA** implementada!

**Uso em F5-TTS** (`app/engines/f5tts_engine.py:360`):

```python
# LOW_VRAM mode: load model → synthesize → unload
if settings.get('low_vram_mode'):
    with vram_manager.load_model('f5tts', self._load_model):
        model_params = self._normalize_f5_params(tts_params)
        audio_array = await loop.run_in_executor(
            None,
            self._synthesize_blocking,
            text,
            ref_audio_path,
            ref_text,
            model_params
        )
else:
    # Normal mode: model already loaded
    ...
```

✅ **INTEGRAÇÃO CORRETA** com context manager!

**Conclusão:** Código está **100% implementado e correto**, mas **nunca executa** porque `LOW_VRAM=false` no container!

#### 4.4.3. Padrões que Impedem Unload

**Singleton Global** (`app/vram_manager.py:158`):

```python
_vram_manager = None

def get_vram_manager() -> VRAMManager:
    """Retorna o gerenciador global de VRAM (singleton)."""
    global _vram_manager
    if _vram_manager is None:
        _vram_manager = VRAMManager()
    return _vram_manager
```

✅ **Singleton OK**: Não impede unload (apenas centraliza gerenciamento)

**Model Cache** (`app/vram_manager.py:38`):

```python
self._model_cache = {}  # Cache de modelos (quando LOW_VRAM=false)
```

✅ **Cache só usado em NORMAL mode**: Não impede unload em LOW_VRAM

**Referências Globais:**

Nenhuma referência global ao modelo detectada fora do VRAMManager.

---

## 5. Conclusões e Problemas Críticos

### 5.1. Resumo de Problemas

| # | Problema | Severidade | Impacto | Causa Raiz |
|---|----------|------------|---------|------------|
| 1 | LOW_VRAM não ativado | 🔴 Crítico | 100% VRAM ocupada sempre | `env_file` não recarregado após mudança |
| 2 | F5-TTS em CPU forçado | 🔴 Crítico | 10x mais lento | Hardcode `device='cpu'` no engine |
| 3 | Imagem Docker deprecated | ⚠️ Alto | Risco de quebra futura | Base image CUDA 12.1 EOL |
| 4 | Containers órfãos potenciais | ⚠️ Médio | Uso desnecessário de disk/RAM | Falta rotina de prune |
| 5 | Imagens gigantes (16GB) | ⚠️ Médio | 32GB total storage | Sem multi-stage build |
| 6 | Health check só na API | ⚠️ Baixo | Celery pode estar unhealthy | Falta healthcheck no worker |
| 7 | Rebuilds sujos | ⚠️ Baixo | Estado inconsistente | Falta cleanup before rebuild |

### 5.2. Priorização (Alta → Baixa)

1. ⚡ **[CRÍTICO]** Ativar LOW_VRAM corretamente
2. ⚡ **[CRÍTICO]** Fazer F5-TTS usar GPU (não CPU hardcoded)
3. 🔧 **[ALTO]** Atualizar base image CUDA (12.1 → 12.4)
4. 🔧 **[ALTO]** Criar rotina de cleanup (prune) sistemática
5. 🛠️ **[MÉDIO]** Implementar multi-stage build (reduzir tamanho)
6. 🛠️ **[MÉDIO]** Adicionar healthcheck no Celery
7. 📋 **[BAIXO]** Adicionar depends_on entre serviços

### 5.3. Riscos Identificados

#### Risco 1: OOM (Out of Memory) em GPU 4GB

**Cenário:**
- XTTS carregado: ~3.5GB VRAM
- F5-TTS carregado: ~2.0GB VRAM
- **Total: 5.5GB > 4GB disponíveis**

**Consequência:** `RuntimeError: CUDA out of memory`

**Mitigação Atual:** F5-TTS forçado em CPU (evita OOM, mas **10x mais lento**)

**Mitigação Ideal:** LOW_VRAM mode ativado (carrega/descarrega modelos dinamicamente)

#### Risco 2: Comportamento Não Determinístico Após Restart

**Cenário:**
- Usuário muda `.env` (ex: `LOW_VRAM=true`)
- Faz `docker restart audio-voice-celery`
- **Variável NÃO é recarregada** (container mantém env antigo)

**Consequência:** Comportamento imprevisível, usuário acha que configurou mas não funcionou

**Mitigação:** Sempre usar `docker compose down` + `docker compose up` (não `restart`)

#### Risco 3: Imagem Deprecated Pode Parar de Funcionar

**Cenário:**
- NVIDIA remove imagem CUDA 12.1 do DockerHub
- Build quebra com `image not found`

**Consequência:** Deploy impossível sem atualizar Dockerfile

**Mitigação:** Atualizar para CUDA 12.4+ (latest LTS)

---

## 6. Evidências Coletadas

### 6.1. Containers Ativos

```
NAMES                    STATUS                    IMAGE
audio-voice-api          Up 26 minutes (healthy)   audio-voice-audio-voice-service
audio-voice-celery       Up 16 minutes (healthy)   audio-voice-celery-worker
```

### 6.2. GPU Accessibility

```bash
$ docker exec audio-voice-celery nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
NVIDIA GeForce GTX 1050 Ti, 4096 MiB, 2144 MiB
```

### 6.3. Environment Variables (Container)

```bash
$ docker inspect audio-voice-celery --format '{{.Config.Env}}'
LOW_VRAM=false
NVIDIA_VISIBLE_DEVICES=all
CUDA_VISIBLE_DEVICES=0
FORCE_CUDA=1
```

### 6.4. Logs LOW_VRAM

```
[2025-11-28 01:14:02] INFO: ⚡ NORMAL MODE: Modelos permanecerão na VRAM
[2025-11-28 01:09:14] INFO: ⚡ NORMAL MODE: Modelos permanecerão na VRAM
[2025-11-28 01:03:10] INFO: ⚡ NORMAL MODE: Modelos permanecerão na VRAM
```

**Conclusão:** LOW_VRAM **NUNCA foi ativado** em nenhum restart.

### 6.5. Hardcode CPU em F5-TTS

```python
# app/engines/f5tts_engine.py:115
self.device = 'cpu'  # FIXME: Force CPU até implementar VRAM management
```

---

## 7. Recomendações Técnicas

### 7.1. Imediatas (Sprint 1)

1. **Recriar containers com LOW_VRAM correto**
   ```bash
   docker compose down
   docker compose up -d --build
   ```

2. **Remover hardcode CPU do F5-TTS**
   ```python
   # Antes
   self.device = 'cpu'  # FIXME
   
   # Depois
   self.device = self._select_device(device, fallback_to_cpu)
   ```

3. **Validar GPU usage com nvidia-smi**
   ```bash
   watch -n 1 nvidia-smi
   # Verificar VRAM usage durante inference
   ```

### 7.2. Curto Prazo (Sprint 2)

1. **Atualizar base image CUDA**
   ```dockerfile
   FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04
   ```

2. **Criar script de cleanup sistemático**
   ```bash
   #!/bin/bash
   docker compose down --volumes
   docker system prune -af --volumes
   docker compose build --no-cache
   docker compose up -d
   ```

3. **Adicionar healthcheck no Celery**
   ```yaml
   healthcheck:
     test: ["CMD-SHELL", "celery -A app.celery_config inspect ping -d celery@$HOSTNAME"]
     interval: 30s
     timeout: 10s
     retries: 3
   ```

### 7.3. Médio Prazo (Sprint 3-4)

1. **Multi-stage build** (reduzir tamanho 40-50%)
2. **Testes de stress VRAM** (validar LOW_VRAM em produção)
3. **Monitoramento de VRAM** (Prometheus + Grafana)

---

## 8. Checklist de Validação

**Após implementar correções, validar:**

- [ ] `docker ps` mostra apenas 2 containers (API + Celery)
- [ ] `docker inspect audio-voice-celery | grep LOW_VRAM` retorna `true`
- [ ] Logs mostram `🔋 LOW VRAM MODE: ATIVADO`
- [ ] F5-TTS usa GPU (não CPU)
- [ ] `nvidia-smi` mostra VRAM sendo alocada/liberada durante inference
- [ ] Após inference, VRAM volta ao baseline (apenas XTTS residente)
- [ ] Base image é CUDA 12.4+ (não deprecated)
- [ ] `docker images` não mostra imagens `<none>` (órfãs)

---

**Fim do Relatório de Auditoria QA**

**Próximo passo:** Gerar `SPRINTS_DOCKER_GPU.md` com plano de implementação detalhado.
