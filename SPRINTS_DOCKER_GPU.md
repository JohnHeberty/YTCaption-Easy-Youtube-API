# SPRINTS_DOCKER_GPU – Plano de Implementação QA

**Baseado em:** `QA_DOCKER_GPU.md`  
**Data:** 28 de Novembro de 2025  
**Metodologia:** Test-Driven QA (Testes → Implementação → Validação)  
**Estimativa Total:** 4-6 horas (dividido em 4 sprints)

---

## 📋 Objetivo Geral

Corrigir os problemas críticos identificados na auditoria:

1. ✅ Ativar `LOW_VRAM` mode corretamente
2. ✅ Fazer F5-TTS usar GPU (remover hardcode CPU)
3. ✅ Padronizar ciclo de vida dos containers (cleanup + rebuild limpo)
4. ✅ Atualizar base image CUDA (deprecated → current)
5. ✅ Garantir observabilidade (logs, healthchecks, monitoramento VRAM)

---

## 🏃 Sprint 1 – Padronizar Ciclo de Vida dos Containers

**Duração:** 45-60 minutos  
**Prioridade:** 🔴 Crítica  
**Objetivo:** Garantir que não existam múltiplos containers órfãos e que o ciclo de subir/derrubar seja claro e reproduzível.

### Tarefas

#### 1.1. Criar Script de Cleanup Sistemático

**Teste:**
```bash
# scripts/docker-cleanup-audio-voice.sh
#!/bin/bash
set -e

echo "🧹 Iniciando cleanup do serviço audio-voice..."

# Validação: script deve falhar se houver containers rodando que não sejam do compose
if docker ps --filter "name=audio-voice" --format '{{.Names}}' | grep -v -E "(audio-voice-api|audio-voice-celery)"; then
    echo "❌ ERRO: Containers desconhecidos detectados!"
    exit 1
fi

echo "✅ Validação de containers passou"
exit 0
```

**Implementação:**
```bash
# scripts/docker-cleanup-audio-voice.sh
#!/bin/bash
set -e

cd "$(dirname "$0")/../services/audio-voice"

echo "🧹 Parando serviços audio-voice..."
docker compose down --volumes --remove-orphans

echo "🗑️ Removendo imagens antigas do audio-voice..."
docker images | grep "audio-voice" | awk '{print $3}' | xargs -r docker rmi -f || true

echo "🧽 Limpando sistema Docker (prune seletivo)..."
docker system prune -f --filter "label=com.example.service=audio-voice"

echo "✅ Cleanup concluído!"
```

**Validação:**
```bash
bash scripts/docker-cleanup-audio-voice.sh
docker ps --filter "name=audio-voice"  # Deve retornar vazio
docker images | grep "audio-voice"      # Deve retornar vazio
```

- [ ] Script criado em `scripts/docker-cleanup-audio-voice.sh`
- [ ] Executável: `chmod +x scripts/docker-cleanup-audio-voice.sh`
- [ ] Teste: Executar e validar que não há containers/imagens restantes

#### 1.2. Criar Script de Rebuild Limpo

**Teste:**
```bash
# scripts/rebuild-audio-voice.sh (validation only)
#!/bin/bash
set -e

# Verificar se .env existe
if [ ! -f "services/audio-voice/.env" ]; then
    echo "❌ .env não encontrado!"
    exit 1
fi

# Verificar se LOW_VRAM está definido
if ! grep -q "^LOW_VRAM=" "services/audio-voice/.env"; then
    echo "❌ LOW_VRAM não definido no .env!"
    exit 1
fi

echo "✅ Pré-condições para rebuild OK"
```

**Implementação:**
```bash
# scripts/rebuild-audio-voice.sh
#!/bin/bash
set -e

cd "$(dirname "$0")/../services/audio-voice"

echo "🔨 Rebuild limpo do audio-voice..."

# 1. Cleanup completo
bash ../../scripts/docker-cleanup-audio-voice.sh

# 2. Rebuild sem cache
echo "📦 Building imagens (sem cache)..."
docker compose build --no-cache

# 3. Subir serviços
echo "🚀 Iniciando serviços..."
docker compose up -d

# 4. Aguardar health checks
echo "⏳ Aguardando health checks..."
sleep 30

# 5. Validar
echo "🔍 Validando containers..."
if docker ps --filter "name=audio-voice-api" --filter "health=healthy" | grep -q "audio-voice-api"; then
    echo "✅ API healthy"
else
    echo "❌ API não está healthy!"
    docker logs audio-voice-api --tail 50
    exit 1
fi

if docker ps --filter "name=audio-voice-celery" --filter "health=healthy" | grep -q "audio-voice-celery"; then
    echo "✅ Celery healthy"
else
    echo "⚠️ Celery sem healthcheck (OK se esperado)"
fi

echo "✅ Rebuild concluído com sucesso!"
```

**Validação:**
```bash
bash scripts/rebuild-audio-voice.sh
docker ps --filter "name=audio-voice"  # Deve mostrar 2 containers healthy
```

- [ ] Script criado em `scripts/rebuild-audio-voice.sh`
- [ ] Executável: `chmod +x scripts/rebuild-audio-voice.sh`
- [ ] Teste: Rebuild completo e verificar health

#### 1.3. Adicionar Target Makefile (Opcional)

**Implementação:**
```makefile
# services/audio-voice/Makefile
.PHONY: cleanup rebuild restart logs

cleanup:
	@echo "🧹 Cleanup audio-voice..."
	@bash ../../scripts/docker-cleanup-audio-voice.sh

rebuild:
	@echo "🔨 Rebuild audio-voice..."
	@bash ../../scripts/rebuild-audio-voice.sh

restart:
	@echo "🔄 Restart audio-voice..."
	docker compose restart

logs:
	@echo "📋 Logs audio-voice..."
	docker compose logs -f --tail=100

logs-celery:
	@echo "📋 Logs Celery..."
	docker logs audio-voice-celery -f --tail=100
```

**Validação:**
```bash
cd services/audio-voice
make cleanup
make rebuild
make logs-celery  # Verificar logs
```

- [ ] Makefile criado
- [ ] Testar todos os targets

#### 1.4. Verificação de Container Único por Serviço

**Teste:**
```bash
# test-single-container.sh
#!/bin/bash

API_COUNT=$(docker ps --filter "name=audio-voice-api" --format '{{.Names}}' | wc -l)
CELERY_COUNT=$(docker ps --filter "name=audio-voice-celery" --format '{{.Names}}' | wc -l)

if [ "$API_COUNT" -ne 1 ]; then
    echo "❌ ERRO: $API_COUNT containers API (esperado: 1)"
    exit 1
fi

if [ "$CELERY_COUNT" -ne 1 ]; then
    echo "❌ ERRO: $CELERY_COUNT containers Celery (esperado: 1)"
    exit 1
fi

echo "✅ Apenas 1 container de cada tipo rodando"
```

**Validação:**
```bash
bash test-single-container.sh
```

- [ ] Teste criado
- [ ] Executar após rebuild e confirmar sucesso

---

## 🏃 Sprint 2 – Garantir F5-TTS em CUDA

**Duração:** 60-90 minutos  
**Prioridade:** 🔴 Crítica  
**Objetivo:** Ajustar Dockerfile/compose + código para que F5-TTS rode em GPU (não CPU hardcoded).

### Tarefas

#### 2.1. Atualizar Base Image CUDA

**Teste:**
```bash
# Verificar se imagem está deprecated
docker pull nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04 2>&1 | grep -i "deprec" && echo "❌ DEPRECATED" || echo "✅ OK"
```

**Implementação:**
```dockerfile
# services/audio-voice/Dockerfile
# ANTES
# FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# DEPOIS
FROM nvidia/cuda:12.4.1-cudnn9-runtime-ubuntu22.04
```

**Validação:**
```bash
cd services/audio-voice
docker build -t test-cuda-image . 2>&1 | grep -i "deprec"  # Não deve retornar nada
docker run --rm test-cuda-image nvidia-smi  # Deve funcionar
```

- [ ] Dockerfile atualizado
- [ ] Build de teste sem warnings de deprecation

#### 2.2. Garantir `--gpus` no Compose

**Validação Atual:**
```yaml
# services/audio-voice/docker-compose.yml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

✅ **JÁ ESTÁ CORRETO** (Docker Compose v2 usa `deploy.resources`)

**Teste Adicional:**
```bash
# Verificar se GPU está acessível
docker exec audio-voice-celery nvidia-smi --query-gpu=name --format=csv,noheader
```

- [ ] Validar que GPU está acessível
- [ ] Confirmar que CUDA 12.4 funciona

#### 2.3. Adicionar Verificação CUDA no Startup

**Implementação:**
```python
# services/audio-voice/app/cuda_check.py
"""
CUDA Availability Check
Executa no startup para validar GPU
"""
import logging
import torch

logger = logging.getLogger(__name__)

def check_cuda():
    """Verifica disponibilidade de CUDA e loga informações"""
    if not torch.cuda.is_available():
        logger.warning("⚠️ CUDA não disponível! Modelos rodarão em CPU.")
        return False
    
    gpu_name = torch.cuda.get_device_name(0)
    vram_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
    
    logger.info(f"✅ CUDA disponível: {gpu_name}")
    logger.info(f"📊 VRAM Total: {vram_total:.2f} GB")
    
    # Verificar se é GPU pequena (<6GB)
    if vram_total < 6.0:
        logger.warning(f"⚠️ GPU pequena detectada ({vram_total:.2f}GB). Recomenda-se LOW_VRAM=true")
    
    return True

if __name__ == "__main__":
    check_cuda()
```

**Integração no startup:**
```python
# services/audio-voice/run.py (adicionar no início)
from app.cuda_check import check_cuda

# Logo após imports
logger.info("🚀 Starting Audio Voice Service")
check_cuda()  # ← ADICIONAR AQUI
```

**Validação:**
```bash
docker logs audio-voice-api --tail 10 | grep "CUDA"
# Deve mostrar:
# ✅ CUDA disponível: NVIDIA GeForce GTX 1050 Ti
# 📊 VRAM Total: 4.00 GB
# ⚠️ GPU pequena detectada (4.00GB). Recomenda-se LOW_VRAM=true
```

- [ ] `cuda_check.py` criado
- [ ] Integrado em `run.py`
- [ ] Logs confirmam GPU detectada

#### 2.4. Remover Hardcode CPU do F5-TTS

**Teste (antes da mudança):**
```bash
docker exec audio-voice-celery grep -n "self.device = 'cpu'" /app/app/engines/f5tts_engine.py
# Deve retornar linha 115
```

**Implementação:**
```python
# services/audio-voice/app/engines/f5tts_engine.py

# ANTES (linha 115)
# self.device = 'cpu'  # FIXME: Force CPU até implementar VRAM management
# logger.info(f"F5TtsEngine initializing on device: {self.device} (forced CPU to avoid OOM)")

# DEPOIS
self.device = self._select_device(device, fallback_to_cpu)
logger.info(f"F5TtsEngine initializing on device: {self.device}")

# Se LOW_VRAM desativado e GPU pequena, avisar
settings = get_settings()
if self.device == 'cuda' and not settings.get('low_vram_mode'):
    if torch.cuda.is_available():
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        if vram_gb < 6.0:
            logger.warning(
                f"⚠️ GPU pequena ({vram_gb:.2f}GB) sem LOW_VRAM! "
                f"Recomenda-se LOW_VRAM=true para evitar OOM."
            )
```

**Validação:**
```bash
# Rebuild
make rebuild

# Verificar logs
docker logs audio-voice-celery 2>&1 | grep "F5TtsEngine initializing"
# Deve mostrar: F5TtsEngine initializing on device: cuda
```

- [ ] Código atualizado
- [ ] Rebuild executado
- [ ] Logs confirmam F5-TTS usando CUDA

#### 2.5. Criar Teste de Uso de GPU

**Teste:**
```python
# services/audio-voice/tests/test_gpu_usage.py
"""
Testa se F5-TTS está realmente usando GPU
"""
import pytest
import torch
from app.engines.f5tts_engine import F5TtsEngine

def test_f5tts_uses_gpu():
    """Verifica se F5-TTS inicializa em CUDA quando disponível"""
    if not torch.cuda.is_available():
        pytest.skip("CUDA não disponível")
    
    engine = F5TtsEngine(device='cuda', fallback_to_cpu=False)
    
    assert engine.device == 'cuda', f"F5-TTS não está em CUDA! Device: {engine.device}"
    
    # Verificar se modelo está em GPU (se já carregado)
    if engine.tts is not None:
        # F5-TTS API não expõe device diretamente, mas podemos checar VRAM
        allocated_before = torch.cuda.memory_allocated()
        # Load model se lazy
        if hasattr(engine, '_load_model'):
            engine._load_model()
        allocated_after = torch.cuda.memory_allocated()
        
        assert allocated_after > allocated_before, "Nenhuma VRAM alocada (modelo não em GPU?)"

def test_f5tts_fallback_cpu():
    """Verifica fallback para CPU quando GPU não disponível"""
    # Simular CUDA indisponível
    engine = F5TtsEngine(device='cpu', fallback_to_cpu=True)
    assert engine.device == 'cpu'
```

**Validação:**
```bash
cd services/audio-voice
docker exec audio-voice-celery pytest tests/test_gpu_usage.py -v
```

- [ ] Teste criado
- [ ] Executado com sucesso

---

## 🏃 Sprint 3 – Corrigir Comportamento LOW_VRAM

**Duração:** 60-90 minutos  
**Prioridade:** 🔴 Crítica  
**Objetivo:** Fazer com que LOW_VRAM=true seja lido corretamente e modelos sejam carregados/descarregados dinamicamente.

### Tarefas

#### 3.1. Validar `.env` Atual

**Teste:**
```bash
# Verificar se .env tem LOW_VRAM correto
grep "^LOW_VRAM=" services/audio-voice/.env
# Deve retornar: LOW_VRAM=true
```

**Implementação (se necessário):**
```bash
# Garantir que .env tem valor correto
cd services/audio-voice
if ! grep -q "^LOW_VRAM=true" .env; then
    echo "Corrigindo LOW_VRAM no .env..."
    sed -i 's/^LOW_VRAM=.*/LOW_VRAM=true/' .env
fi
```

- [ ] `.env` verificado e corrigido se necessário

#### 3.2. Forçar Recriação de Containers (não restart)

**Problema:** `docker compose restart` NÃO recarrega `env_file`

**Solução:**
```bash
cd services/audio-voice
docker compose down
docker compose up -d
```

**Validação:**
```bash
docker inspect audio-voice-celery --format '{{.Config.Env}}' | grep LOW_VRAM
# Deve retornar: LOW_VRAM=true
```

- [ ] Containers recriados (down + up)
- [ ] Variável LOW_VRAM=true confirmada no container

#### 3.3. Implementar Logs de Debug para LOW_VRAM

**Implementação:**
```python
# services/audio-voice/app/vram_manager.py (início do __init__)

def __init__(self):
    settings = get_settings()
    self.low_vram_mode = settings.get('low_vram_mode', False)
    
    # Debug: Logar valor lido
    import os
    env_value = os.getenv('LOW_VRAM', 'NOT_SET')
    logger.info(f"🔍 DEBUG: LOW_VRAM env={env_value}, parsed={self.low_vram_mode}")
    
    self._model_cache = {}
    
    if self.low_vram_mode:
        logger.info("🔋 LOW VRAM MODE: ATIVADO - Modelos serão carregados/descarregados automaticamente")
    else:
        logger.info("⚡ NORMAL MODE: Modelos permanecerão na VRAM")
```

**Validação:**
```bash
docker logs audio-voice-celery 2>&1 | grep "DEBUG: LOW_VRAM"
# Deve mostrar:
# 🔍 DEBUG: LOW_VRAM env=true, parsed=True
# 🔋 LOW VRAM MODE: ATIVADO
```

- [ ] Logs de debug adicionados
- [ ] Rebuild executado
- [ ] Logs confirmam LOW_VRAM=true sendo lido

#### 3.4. Adicionar Logs Durante Load/Unload

**Implementação:**
```python
# services/audio-voice/app/vram_manager.py (método load_model)

@contextmanager
def load_model(self, model_key: str, load_fn: Callable, *args, **kwargs):
    model = None
    
    try:
        if self.low_vram_mode:
            logger.info(f"🔋 LOW_VRAM: Carregando modelo '{model_key}' na GPU...")
            model = load_fn(*args, **kwargs)
            
            # Log VRAM usage após load
            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated() / 1024**3
                logger.info(f"📊 VRAM alocada após load: {allocated:.2f} GB")
        else:
            # Usar cache
            if model_key not in self._model_cache:
                logger.info(f"⚡ Carregando modelo '{model_key}' (primeira vez)")
                self._model_cache[model_key] = load_fn(*args, **kwargs)
            else:
                logger.debug(f"⚡ Usando modelo '{model_key}' do cache")
            model = self._model_cache[model_key]
        
        yield model
    
    finally:
        # Descarregar apenas em modo LOW_VRAM
        if self.low_vram_mode and model is not None:
            logger.info(f"🔋 LOW_VRAM: Descarregando modelo '{model_key}' da VRAM...")
            
            # Log VRAM antes
            if torch.cuda.is_available():
                before = torch.cuda.memory_allocated() / 1024**3
                
            self._unload_model(model)
            del model
            
            # Log VRAM depois
            if torch.cuda.is_available():
                after = torch.cuda.memory_allocated() / 1024**3
                freed = before - after
                logger.info(f"📊 VRAM liberada: {freed:.2f} GB (antes={before:.2f}, depois={after:.2f})")
```

**Validação:**
```bash
# Fazer uma requisição de síntese
curl -X POST http://localhost:8005/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "dubbing_with_clone",
    "text": "Teste de VRAM",
    "language": "pt-BR",
    "voice_id": "82f8f815-ac80-4415-8091-7ebf833912ca"
  }'

# Monitorar logs
docker logs audio-voice-celery -f

# Deve mostrar:
# 🔋 LOW_VRAM: Carregando modelo 'f5tts' na GPU...
# 📊 VRAM alocada após load: 2.34 GB
# (processamento)
# 🔋 LOW_VRAM: Descarregando modelo 'f5tts' da VRAM...
# 📊 VRAM liberada: 2.10 GB (antes=2.34, depois=0.24)
```

- [ ] Logs detalhados implementados
- [ ] Rebuild executado
- [ ] Teste de síntese mostra load/unload correto

#### 3.5. Criar Teste de VRAM Management

**Teste:**
```python
# services/audio-voice/tests/test_vram_management.py
"""
Testa comportamento de LOW_VRAM mode
"""
import pytest
import torch
from app.vram_manager import get_vram_manager
from app.config import get_settings

@pytest.fixture
def vram_manager():
    return get_vram_manager()

def test_low_vram_mode_enabled(vram_manager):
    """Verifica se LOW_VRAM mode está ativado quando configurado"""
    settings = get_settings()
    
    # Se LOW_VRAM=true no .env
    if settings.get('low_vram_mode'):
        assert vram_manager.low_vram_mode is True
    else:
        pytest.skip("LOW_VRAM não configurado")

def test_vram_freed_after_inference(vram_manager):
    """Verifica se VRAM é liberada após inference em modo LOW_VRAM"""
    if not torch.cuda.is_available():
        pytest.skip("CUDA não disponível")
    
    if not vram_manager.low_vram_mode:
        pytest.skip("LOW_VRAM não ativado")
    
    # Baseline VRAM
    torch.cuda.empty_cache()
    baseline = torch.cuda.memory_allocated()
    
    # Simular carregamento de modelo
    def dummy_load():
        # Alocar tensor grande
        return torch.randn(1000, 1000, 1000, device='cuda')
    
    with vram_manager.load_model('test', dummy_load):
        during = torch.cuda.memory_allocated()
        assert during > baseline, "VRAM não aumentou durante load"
    
    # Após context manager, VRAM deve voltar ao baseline
    torch.cuda.synchronize()
    after = torch.cuda.memory_allocated()
    
    # Tolerância de 100MB
    assert abs(after - baseline) < 100 * 1024**2, \
        f"VRAM não foi liberada! Baseline={baseline/1024**2:.0f}MB, After={after/1024**2:.0f}MB"
```

**Validação:**
```bash
docker exec audio-voice-celery pytest tests/test_vram_management.py -v -s
```

- [ ] Teste criado
- [ ] Executado com sucesso (VRAM liberada confirmada)

---

## 🏃 Sprint 4 – QA Final e Observabilidade

**Duração:** 45-60 minutos  
**Prioridade:** ⚠️ Alta  
**Objetivo:** Garantir que tudo está estável, observável e documentado.

### Tarefas

#### 4.1. Validar Ciclo Completo

**Teste End-to-End:**
```bash
#!/bin/bash
# tests/e2e-test-low-vram.sh

set -e

echo "🧪 Teste E2E: LOW_VRAM mode"

# 1. Cleanup
echo "1️⃣ Cleanup..."
bash scripts/docker-cleanup-audio-voice.sh

# 2. Rebuild
echo "2️⃣ Rebuild..."
bash scripts/rebuild-audio-voice.sh

# 3. Aguardar startup
echo "3️⃣ Aguardando startup completo (60s)..."
sleep 60

# 4. Verificar LOW_VRAM nos logs
echo "4️⃣ Verificando LOW_VRAM mode..."
if docker logs audio-voice-celery 2>&1 | grep -q "🔋 LOW VRAM MODE: ATIVADO"; then
    echo "✅ LOW_VRAM ativado"
else
    echo "❌ LOW_VRAM NÃO está ativado!"
    exit 1
fi

# 5. Fazer clone de voz
echo "5️⃣ Clonando voz de teste..."
CLONE_RESPONSE=$(curl -s -X POST http://localhost:8005/voices/clone \
  -F "audio=@services/audio-voice/tests/Teste.ogg" \
  -F "language=pt-BR" \
  -F "voice_name=TesteLowVRAM")

VOICE_ID=$(echo $CLONE_RESPONSE | jq -r '.voice_id')
echo "Voice ID: $VOICE_ID"

# 6. Aguardar job de clone
sleep 10

# 7. Fazer síntese com F5-TTS
echo "6️⃣ Sintetizando com F5-TTS..."
JOB_RESPONSE=$(curl -s -X POST http://localhost:8005/jobs \
  -H "Content-Type: application/json" \
  -d "{
    \"mode\": \"dubbing_with_clone\",
    \"text\": \"Este é um teste completo do modo LOW VRAM com F5-TTS em CUDA.\",
    \"language\": \"pt-BR\",
    \"voice_id\": \"$VOICE_ID\",
    \"quality_profile\": \"f5tts_balanced\"
  }")

JOB_ID=$(echo $JOB_RESPONSE | jq -r '.job_id')
echo "Job ID: $JOB_ID"

# 8. Aguardar processamento
echo "7️⃣ Aguardando processamento (até 5min)..."
for i in {1..60}; do
    STATUS=$(curl -s http://localhost:8005/jobs/$JOB_ID | jq -r '.status')
    echo "   Status: $STATUS (tentativa $i/60)"
    
    if [ "$STATUS" == "completed" ]; then
        echo "✅ Job completado!"
        break
    elif [ "$STATUS" == "failed" ]; then
        echo "❌ Job falhou!"
        docker logs audio-voice-celery --tail 100
        exit 1
    fi
    
    sleep 5
done

# 9. Verificar logs de VRAM
echo "8️⃣ Verificando logs de VRAM management..."
if docker logs audio-voice-celery 2>&1 | grep -q "📊 VRAM liberada:"; then
    echo "✅ VRAM foi liberada após síntese"
else
    echo "⚠️ Não encontrado log de VRAM liberada (pode ser normal se cache usado)"
fi

# 10. Verificar uso de GPU (não CPU)
echo "9️⃣ Verificando se F5-TTS usou GPU..."
if docker logs audio-voice-celery 2>&1 | grep -q "F5TtsEngine initializing on device: cuda"; then
    echo "✅ F5-TTS usando CUDA"
else
    echo "❌ F5-TTS NÃO está usando CUDA!"
    exit 1
fi

echo "🎉 Teste E2E PASSOU!"
```

**Validação:**
```bash
bash tests/e2e-test-low-vram.sh
```

- [ ] Script E2E criado
- [ ] Executado com sucesso

#### 4.2. Adicionar Health Check no Celery

**Implementação:**
```yaml
# services/audio-voice/docker-compose.yml

celery-worker:
  # ... (existente)
  healthcheck:
    test: ["CMD-SHELL", "python -c \"from celery import Celery; app = Celery(); app.broker_connection().ensure_connection(max_retries=3)\" || exit 1"]
    interval: 30s
    timeout: 10s
    retries: 5
    start_period: 60s
```

**Validação:**
```bash
docker compose up -d
sleep 60
docker ps --filter "name=audio-voice-celery" --filter "health=healthy"
# Deve mostrar container healthy
```

- [ ] Health check adicionado
- [ ] Containers recriados
- [ ] Health check passing

#### 4.3. Criar Endpoint de Monitoramento VRAM

**Implementação:**
```python
# services/audio-voice/app/main.py (adicionar endpoint)

from app.vram_manager import get_vram_manager

@app.get("/admin/vram", tags=["Admin"])
async def get_vram_stats():
    """
    Retorna estatísticas de uso de VRAM.
    
    Útil para monitoramento e debugging de LOW_VRAM mode.
    """
    vram_mgr = get_vram_manager()
    stats = vram_mgr.get_vram_stats()
    
    return {
        "vram": stats,
        "timestamp": datetime.now().isoformat()
    }
```

**Validação:**
```bash
curl -s http://localhost:8005/admin/vram | jq
# Deve retornar:
# {
#   "vram": {
#     "available": true,
#     "low_vram_mode": true,
#     "allocated_gb": 0.24,
#     "reserved_gb": 0.50,
#     "free_gb": 2.14,
#     "total_gb": 4.00,
#     "cached_models": 0
#   },
#   "timestamp": "2025-11-28T01:30:00"
# }
```

- [ ] Endpoint criado
- [ ] Testado e retornando dados corretos

#### 4.4. Ajustar Logs para Monitoramento

**Implementação:**
```python
# services/audio-voice/app/engines/f5tts_engine.py (no final de generate_dubbing)

# Após síntese bem-sucedida
logger.info(
    f"✅ F5-TTS synthesis complete: {duration:.2f}s, {len(audio_bytes)} bytes "
    f"[device={self.device}, low_vram={settings.get('low_vram_mode')}]"
)
```

**Validação:**
```bash
docker logs audio-voice-celery 2>&1 | grep "F5-TTS synthesis complete"
# Deve mostrar device e low_vram mode
```

- [ ] Logs aprimorados
- [ ] Informações de device/VRAM visíveis

#### 4.5. Documentar Uso e Troubleshooting

**Implementação:**
```markdown
# services/audio-voice/VRAM_TROUBLESHOOTING.md

# VRAM Troubleshooting Guide

## Como verificar se LOW_VRAM está ativado

```bash
# 1. Verificar .env
grep LOW_VRAM services/audio-voice/.env
# Deve retornar: LOW_VRAM=true

# 2. Verificar container
docker inspect audio-voice-celery --format '{{.Config.Env}}' | grep LOW_VRAM
# Deve retornar: LOW_VRAM=true

# 3. Verificar logs
docker logs audio-voice-celery 2>&1 | grep "LOW VRAM MODE"
# Deve mostrar: 🔋 LOW VRAM MODE: ATIVADO
```

## Se LOW_VRAM não estiver ativado

1. **Edite `.env`:**
   ```bash
   cd services/audio-voice
   sed -i 's/^LOW_VRAM=.*/LOW_VRAM=true/' .env
   ```

2. **IMPORTANTE: Não use `docker restart`! Use:**
   ```bash
   docker compose down
   docker compose up -d
   ```

3. **Verifique novamente:**
   ```bash
   docker logs audio-voice-celery 2>&1 | grep "LOW VRAM MODE"
   ```

## Como monitorar uso de VRAM

### Tempo real (nvidia-smi)
```bash
watch -n 1 nvidia-smi
```

### Endpoint HTTP
```bash
curl -s http://localhost:8005/admin/vram | jq
```

### Logs detalhados
```bash
docker logs audio-voice-celery -f | grep -E "(VRAM|carregando|descarregando)"
```

## Troubleshooting: OOM (Out of Memory)

Se você ver `RuntimeError: CUDA out of memory`:

1. ✅ **Certifique-se que LOW_VRAM está ativado** (veja acima)
2. ✅ **Reduza concorrência do Celery:**
   ```yaml
   # docker-compose.yml
   command: ... --concurrency=1  # ← Deve ser 1!
   ```
3. ✅ **Não rode XTTS e F5-TTS simultaneamente** (LOW_VRAM evita isso)
4. ⚠️ **Se ainda falhar:** GPU pode ser muito pequena (<4GB), use CPU:
   ```env
   F5TTS_DEVICE=cpu
   XTTS_DEVICE=cuda  # Apenas XTTS em GPU
   ```
```

- [ ] Documento criado
- [ ] Instruções validadas

---

## ✅ Checklist Final de Validação

Após completar todas as sprints, validar:

### Containers
- [ ] `docker ps` mostra apenas 2 containers (API + Celery)
- [ ] Ambos containers mostram `(healthy)`
- [ ] Não há containers órfãos (`docker ps -a` sem `<none>`)

### LOW_VRAM
- [ ] `docker inspect audio-voice-celery | grep LOW_VRAM` retorna `true`
- [ ] Logs mostram `🔋 LOW VRAM MODE: ATIVADO`
- [ ] Durante síntese, logs mostram:
  - `🔋 LOW_VRAM: Carregando modelo 'f5tts' na GPU...`
  - `📊 VRAM alocada após load: X.XX GB`
  - `🔋 LOW_VRAM: Descarregando modelo 'f5tts' da VRAM...`
  - `📊 VRAM liberada: X.XX GB`

### F5-TTS em CUDA
- [ ] Logs mostram `F5TtsEngine initializing on device: cuda`
- [ ] `nvidia-smi` mostra VRAM sendo alocada durante síntese
- [ ] Após síntese, VRAM volta ao baseline (XTTS apenas)

### Docker
- [ ] Base image é `nvidia/cuda:12.4.1` (não deprecated)
- [ ] Build não mostra warnings de deprecation
- [ ] `docker images | grep audio-voice` não mostra `<none>`

### Testes
- [ ] `pytest tests/test_gpu_usage.py` passa
- [ ] `pytest tests/test_vram_management.py` passa
- [ ] `bash tests/e2e-test-low-vram.sh` passa

### Observabilidade
- [ ] `curl http://localhost:8005/admin/vram` retorna stats corretos
- [ ] Health checks passando (API + Celery)
- [ ] Logs contêm informações de device e VRAM usage

---

## 📊 Estimativa de Tempo

| Sprint | Tarefas | Tempo Estimado | Complexidade |
|--------|---------|----------------|--------------|
| Sprint 1 | Padronizar ciclo de vida | 45-60 min | Baixa |
| Sprint 2 | F5-TTS em CUDA | 60-90 min | Média |
| Sprint 3 | Corrigir LOW_VRAM | 60-90 min | Alta |
| Sprint 4 | QA final | 45-60 min | Média |
| **TOTAL** | - | **3.5-5 horas** | - |

---

## 🎯 Próximos Passos

Após concluir TODAS as sprints:

1. ✅ Marcar todos os checkboxes acima
2. ✅ Commitar mudanças com mensagem descritiva:
   ```bash
   git add -A
   git commit -m "fix(audio-voice): Ativar LOW_VRAM + F5-TTS em CUDA

   - Corrigido LOW_VRAM não sendo lido (env_file reload)
   - Removido hardcode CPU do F5-TTS (agora usa CUDA)
   - Atualizado base image CUDA (12.1 → 12.4)
   - Implementado scripts de cleanup e rebuild sistemáticos
   - Adicionado health check no Celery
   - Criado endpoint /admin/vram para monitoramento
   - Adicionados testes de GPU usage e VRAM management
   
   Fixes #<issue_number>"
   ```
3. ✅ Testar em ambiente staging (se disponível)
4. ✅ Deploy em produção

---

**Fim do Plano de Implementação**

**Próximo passo:** Executar Sprint 1!
