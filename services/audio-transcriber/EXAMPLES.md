# 🔋 Exemplos de Uso - Gerenciamento de Modelo Whisper

## Quick Start

### 1. Verificar Status do Modelo

```bash
curl http://localhost:8002/model/status
```

**Resposta (Modelo Carregado):**
```json
{
  "loaded": true,
  "model_name": "base",
  "device": "cuda",
  "memory": {
    "vram_mb": 145.8,
    "vram_reserved_mb": 256.0,
    "cuda_available": true
  },
  "gpu_info": {
    "name": "NVIDIA GeForce RTX 3060",
    "device_count": 1,
    "cuda_version": "12.1"
  }
}
```

---

### 2. Descarregar Modelo (Economia de Recursos)

```bash
curl -X POST http://localhost:8002/model/unload
```

**Resposta:**
```json
{
  "success": true,
  "message": "✅ Modelo 'base' descarregado com sucesso do CUDA...",
  "memory_freed": {
    "ram_mb": 150.0,
    "vram_mb": 142.5
  },
  "device_was": "cuda",
  "model_name": "base"
}
```

---

### 3. Carregar Modelo Explicitamente

```bash
curl -X POST http://localhost:8002/model/load
```

**Resposta:**
```json
{
  "success": true,
  "message": "✅ Modelo 'base' carregado com sucesso no CUDA...",
  "memory_used": {
    "ram_mb": 150.0,
    "vram_mb": 145.8
  },
  "device": "cuda",
  "model_name": "base"
}
```

---

## Casos de Uso Práticos

### Caso 1: Processamento Batch com Economia

```bash
#!/bin/bash
# batch_transcribe.sh

echo "📥 Carregando modelo Whisper..."
curl -X POST http://localhost:8002/model/load

echo ""
echo "🎬 Processando arquivos de áudio..."

# Processa todos os arquivos MP3
for file in ./audios/*.mp3; do
  echo "Processando: $file"
  
  response=$(curl -s -X POST http://localhost:8002/jobs \
    -F "file=@$file" \
    -F "language_in=auto" \
    -F "language_out=pt")
  
  job_id=$(echo $response | jq -r '.id')
  echo "  Job criado: $job_id"
  
  # Aguarda conclusão
  while true; do
    status=$(curl -s http://localhost:8002/jobs/$job_id | jq -r '.status')
    progress=$(curl -s http://localhost:8002/jobs/$job_id | jq -r '.progress')
    
    echo "  Status: $status ($progress%)"
    
    if [ "$status" == "completed" ]; then
      echo "  ✅ Concluído!"
      break
    elif [ "$status" == "failed" ]; then
      echo "  ❌ Falhou!"
      break
    fi
    
    sleep 5
  done
done

echo ""
echo "🔋 Descarregando modelo para economizar recursos..."
curl -X POST http://localhost:8002/model/unload

echo ""
echo "✅ Processamento batch concluído!"
```

**Executar:**
```bash
chmod +x batch_transcribe.sh
./batch_transcribe.sh
```

---

### Caso 2: Agendamento com Cron (Economia Noturna)

**Crontab:**
```bash
# Editar crontab
crontab -e

# Adicionar linhas:

# Descarrega modelo às 20h (fim do expediente)
0 20 * * * curl -X POST http://localhost:8002/model/unload

# Carrega modelo às 7h (início do expediente)
0 7 * * * curl -X POST http://localhost:8002/model/load
```

**Economia estimada:**
- Horas ociosas: 13h por dia (20h às 7h + 2h almoço)
- Consumo GPU idle: ~25W
- Economia diária: 25W × 13h = 325Wh/dia
- Economia mensal: ~9.75 kWh/mês
- Economia anual: ~120 kWh/ano (~60 kg CO₂)

---

### Caso 3: Monitoramento com Python

```python
#!/usr/bin/env python3
# monitor_model.py

import requests
import time
from datetime import datetime

API_URL = "http://localhost:8002"

def get_model_status():
    """Consulta status atual do modelo"""
    try:
        response = requests.get(f"{API_URL}/model/status")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Erro ao consultar status: {e}")
        return None

def unload_model():
    """Descarrega modelo"""
    try:
        response = requests.post(f"{API_URL}/model/unload")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Erro ao descarregar: {e}")
        return None

def load_model():
    """Carrega modelo"""
    try:
        response = requests.post(f"{API_URL}/model/load")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Erro ao carregar: {e}")
        return None

def main():
    """Monitor de economia de recursos"""
    print("🔋 Monitor de Economia de Recursos - Whisper")
    print("=" * 60)
    
    while True:
        now = datetime.now()
        hour = now.hour
        
        # Horário de trabalho: 7h às 20h
        is_work_hours = 7 <= hour < 20
        
        status = get_model_status()
        
        if not status:
            print(f"[{now}] ⚠️ Não foi possível consultar status")
            time.sleep(60)
            continue
        
        is_loaded = status.get("loaded", False)
        device = status.get("device", "unknown")
        vram = status.get("memory", {}).get("vram_mb", 0)
        
        print(f"\n[{now}] Status:")
        print(f"  Modelo carregado: {'✅ Sim' if is_loaded else '❌ Não'}")
        print(f"  Dispositivo: {device or 'N/A'}")
        print(f"  VRAM: {vram:.1f} MB")
        print(f"  Horário de trabalho: {'✅ Sim' if is_work_hours else '❌ Não'}")
        
        # Lógica de economia
        if is_work_hours and not is_loaded:
            print("  🚀 Carregando modelo (horário de trabalho)...")
            result = load_model()
            if result and result.get("success"):
                print(f"  ✅ {result['message']}")
            
        elif not is_work_hours and is_loaded:
            print("  🔋 Descarregando modelo (fora do horário)...")
            result = unload_model()
            if result and result.get("success"):
                freed = result.get("memory_freed", {})
                print(f"  ✅ RAM liberada: {freed.get('ram_mb', 0):.1f} MB")
                print(f"  ✅ VRAM liberada: {freed.get('vram_mb', 0):.1f} MB")
        
        # Verifica a cada 5 minutos
        time.sleep(300)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Monitor encerrado")
```

**Executar:**
```bash
python3 monitor_model.py
```

---

### Caso 4: Webhook para Economia Inteligente

```python
#!/usr/bin/env python3
# smart_unload.py

import requests
import time
from datetime import datetime, timedelta

API_URL = "http://localhost:8002"
IDLE_THRESHOLD_MINUTES = 15  # Descarrega após 15min sem tasks

def get_active_jobs():
    """Consulta jobs ativos"""
    try:
        response = requests.get(f"{API_URL}/jobs?limit=100")
        response.raise_for_status()
        jobs = response.json()
        
        # Filtra jobs em processamento ou em fila
        active = [j for j in jobs if j.get('status') in ['queued', 'processing']]
        return active
    except Exception as e:
        print(f"❌ Erro ao consultar jobs: {e}")
        return []

def get_last_completed_job():
    """Encontra último job completado"""
    try:
        response = requests.get(f"{API_URL}/jobs?limit=100")
        response.raise_for_status()
        jobs = response.json()
        
        completed = [j for j in jobs if j.get('status') == 'completed']
        if not completed:
            return None
        
        # Ordena por data de conclusão
        completed.sort(key=lambda x: x.get('completed_at', ''), reverse=True)
        return completed[0]
    except Exception as e:
        print(f"❌ Erro: {e}")
        return None

def smart_unload():
    """Descarrega modelo inteligentemente"""
    print("🧠 Smart Unload - Economia Inteligente")
    print("=" * 60)
    print(f"Threshold: {IDLE_THRESHOLD_MINUTES} minutos sem atividade\n")
    
    while True:
        active_jobs = get_active_jobs()
        
        if active_jobs:
            print(f"[{datetime.now()}] ⚙️ {len(active_jobs)} jobs ativos - modelo MANTIDO")
            time.sleep(60)
            continue
        
        # Sem jobs ativos - verifica último job
        last_job = get_last_completed_job()
        
        if not last_job:
            print(f"[{datetime.now()}] ℹ️ Nenhum job encontrado - aguardando...")
            time.sleep(60)
            continue
        
        # Calcula tempo desde último job
        completed_at = datetime.fromisoformat(last_job['completed_at'].replace('Z', '+00:00'))
        idle_time = datetime.now(completed_at.tzinfo) - completed_at
        idle_minutes = idle_time.total_seconds() / 60
        
        print(f"[{datetime.now()}] 💤 Idle há {idle_minutes:.1f} minutos")
        
        if idle_minutes >= IDLE_THRESHOLD_MINUTES:
            print(f"  🔋 Threshold atingido! Descarregando modelo...")
            
            result = requests.post(f"{API_URL}/model/unload").json()
            
            if result.get("success"):
                freed = result.get("memory_freed", {})
                print(f"  ✅ Modelo descarregado!")
                print(f"     RAM liberada: {freed.get('ram_mb', 0):.1f} MB")
                print(f"     VRAM liberada: {freed.get('vram_mb', 0):.1f} MB")
                
                # Aguarda 30 minutos antes de verificar novamente
                print(f"  😴 Aguardando 30 minutos...")
                time.sleep(1800)
            else:
                print(f"  ⚠️ Falha ao descarregar: {result.get('message')}")
        
        time.sleep(60)

if __name__ == "__main__":
    try:
        smart_unload()
    except KeyboardInterrupt:
        print("\n\n👋 Smart Unload encerrado")
```

**Executar:**
```bash
python3 smart_unload.py
```

**Como funciona:**
1. Monitora jobs a cada 1 minuto
2. Se houver jobs ativos: mantém modelo carregado
3. Se idle por >15 min: descarrega modelo automaticamente
4. Economia automática sem intervenção manual!

---

## PowerShell (Windows)

### Verificar Status
```powershell
Invoke-RestMethod -Uri "http://localhost:8002/model/status" | ConvertTo-Json
```

### Descarregar Modelo
```powershell
Invoke-RestMethod -Uri "http://localhost:8002/model/unload" -Method Post | ConvertTo-Json
```

### Carregar Modelo
```powershell
Invoke-RestMethod -Uri "http://localhost:8002/model/load" -Method Post | ConvertTo-Json
```

### Script de Monitoramento (PowerShell)
```powershell
# monitor.ps1

while ($true) {
    $status = Invoke-RestMethod -Uri "http://localhost:8002/model/status"
    
    Write-Host "`n[$(Get-Date)] Status do Modelo:" -ForegroundColor Cyan
    Write-Host "  Carregado: $($status.loaded)" -ForegroundColor $(if ($status.loaded) { "Green" } else { "Red" })
    Write-Host "  Modelo: $($status.model_name)"
    Write-Host "  Dispositivo: $($status.device)"
    
    if ($status.loaded -and $status.device -eq "cuda") {
        Write-Host "  VRAM: $($status.memory.vram_mb) MB" -ForegroundColor Yellow
    }
    
    Start-Sleep -Seconds 300  # 5 minutos
}
```

**Executar:**
```powershell
.\monitor.ps1
```

---

## Integração com Docker Compose

### Desabilitar Pré-carregamento

```yaml
# docker-compose.yml
services:
  audio-transcriber:
    environment:
      - WHISPER_PRELOAD_MODEL=false  # Modelo só carrega quando necessário
```

### Gerenciar com docker exec

```bash
# Status
docker exec audio-transcriber curl http://localhost:8002/model/status

# Descarregar
docker exec audio-transcriber curl -X POST http://localhost:8002/model/unload

# Carregar
docker exec audio-transcriber curl -X POST http://localhost:8002/model/load
```

---

## Troubleshooting

### Erro: "Modelo já estava descarregado"
```bash
# Normal! Significa que o modelo já foi descarregado anteriormente
# A operação é idempotente e segura
```

### Erro: "Falha ao carregar modelo"
```bash
# Verificar logs do container
docker logs audio-transcriber

# Possíveis causas:
# - Memória insuficiente (RAM/VRAM)
# - Modelo não encontrado no diretório
# - GPU não disponível (se WHISPER_DEVICE=cuda)

# Soluções:
# 1. Verificar espaço em disco/memória
# 2. Usar modelo menor (tiny/base ao invés de large)
# 3. Usar CPU se GPU não disponível (WHISPER_DEVICE=cpu)
```

### Modelo não recarrega automaticamente
```bash
# Verificar se há tasks esperando
curl http://localhost:8002/jobs

# Forçar carregamento manual
curl -X POST http://localhost:8002/model/load

# Se persistir, verificar logs
docker logs audio-transcriber --tail 100
```

---

## Métricas e Observabilidade

### Prometheus Metrics (Future)

```yaml
# Métricas que podem ser expostas:
whisper_model_loaded{device="cuda"} 1
whisper_model_vram_mb{device="cuda"} 145.8
whisper_model_load_duration_seconds 8.5
whisper_model_unload_duration_seconds 2.1
whisper_model_memory_freed_mb{type="vram"} 142.5
```

### Logs Estruturados

```json
{
  "timestamp": "2025-11-04T17:30:00Z",
  "level": "INFO",
  "message": "Modelo descarregado com sucesso",
  "context": {
    "model_name": "base",
    "device": "cuda",
    "memory_freed_mb": 142.5,
    "duration_seconds": 2.1
  }
}
```

---

## Links Úteis

- **Documentação Completa**: [MODEL-MANAGEMENT.md](./MODEL-MANAGEMENT.md)
- **API Documentation**: http://localhost:8002/docs
- **Health Check**: http://localhost:8002/health
- **Service README**: [README.md](./README.md)

**Última atualização**: 04/11/2025
