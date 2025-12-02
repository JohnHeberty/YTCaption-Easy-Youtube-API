# 🔋 Gerenciamento de Modelo Whisper - Economia de Recursos

## 📋 Visão Geral

O serviço **audio-transcriber** agora possui endpoints para **gerenciar o carregamento/descarregamento do modelo Whisper** na memória RAM e GPU/VRAM, permitindo **economia de recursos energéticos** e **redução da pegada de carbono** quando o serviço está idle.

---

## 🆕 Novos Endpoints

### 1. **POST /model/unload** - Descarregar Modelo

Descarrega o modelo Whisper da memória/GPU para economia de recursos.

**Quando usar:**
- ✅ Após processar batch de transcrições
- ✅ Durante períodos de inatividade (sem tasks)
- ✅ Para reduzir consumo energético quando idle
- ✅ Sustentabilidade: reduzir pegada de carbono

**Request:**
```bash
curl -X POST http://localhost:8002/model/unload
```

**Response (Sucesso):**
```json
{
  "success": true,
  "message": "✅ Modelo 'base' descarregado com sucesso do CUDA. Recursos liberados...",
  "memory_freed": {
    "ram_mb": 150.0,
    "vram_mb": 142.5
  },
  "device_was": "cuda",
  "model_name": "base"
}
```

**Benefícios:**
- 🔋 **Economia de energia**: Libera GPU/CPU quando não há tasks
- ♻️ **Sustentabilidade**: Reduz emissões de CO₂
- 💾 **Memória**: Libera ~150MB a 3GB de RAM + VRAM
- ⚡ **Seguro**: Modelo é recarregado automaticamente na próxima task

---

### 2. **POST /model/load** - Carregar Modelo

Carrega o modelo Whisper explicitamente na memória/GPU.

**Quando usar:**
- ✅ Antes de processar múltiplas transcrições (batch)
- ✅ Após descarregar com `/model/unload`
- ✅ Para garantir primeira transcrição sem delay de carregamento
- ✅ Preparar sistema para período de alta demanda

**Request:**
```bash
curl -X POST http://localhost:8002/model/load
```

**Response (Sucesso):**
```json
{
  "success": true,
  "message": "✅ Modelo 'base' carregado com sucesso no CUDA. Sistema pronto...",
  "memory_used": {
    "ram_mb": 150.0,
    "vram_mb": 145.8
  },
  "device": "cuda",
  "model_name": "base"
}
```

**Benefícios:**
- 🚀 **Performance**: Primeira transcrição mais rápida
- ⏱️ **Latência**: Elimina delay de carregamento
- 📊 **Previsibilidade**: Sistema sempre pronto

---

### 3. **GET /model/status** - Status do Modelo

Consulta status atual do modelo Whisper.

**Request:**
```bash
curl http://localhost:8002/model/status
```

**Response (Modelo Carregado na GPU):**
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

**Response (Modelo Descarregado):**
```json
{
  "loaded": false,
  "model_name": "base",
  "device": null,
  "memory": {
    "vram_mb": 0.0,
    "cuda_available": true
  }
}
```

**Benefícios:**
- 📊 **Monitoramento**: Verificar estado atual do modelo
- 🔍 **Debugging**: Diagnosticar problemas de memória
- 📈 **Observabilidade**: Integrar com dashboards

---

## 🎯 Casos de Uso

### 1. **Economia de Recursos em Idle**

Cenário: Serviço rodando 24/7 mas com transcrições apenas durante horário comercial.

```bash
# Durante a noite/final de semana (sem transcrições)
curl -X POST http://localhost:8002/model/unload
# ✅ Libera ~150MB RAM + VRAM
# ✅ Reduz consumo de energia
# ✅ Menor pegada de carbono

# Antes de iniciar expediente
curl -X POST http://localhost:8002/model/load
# ✅ Sistema pronto para trabalhar
```

### 2. **Processamento de Batch**

Cenário: Processar 100 transcrições de uma vez.

```bash
# 1. Carrega modelo explicitamente
curl -X POST http://localhost:8002/model/load

# 2. Submete todas as 100 transcrições
for i in {1..100}; do
  curl -X POST http://localhost:8002/jobs \
    -F "file=@audio_${i}.mp3" \
    -F "language_in=auto"
done

# 3. Após concluir todas, libera recursos
curl -X POST http://localhost:8002/model/unload
```

### 3. **Monitoramento Contínuo**

```bash
# Verificar status a cada 5 minutos
watch -n 300 'curl -s http://localhost:8002/model/status | jq'
```

---

## ⚙️ Configuração

### Variável de Ambiente: `WHISPER_PRELOAD_MODEL`

Controla se o modelo é carregado automaticamente no startup do serviço.

**Valores:**
- `true` (padrão): Carrega modelo no startup
- `false`: Modelo só é carregado quando necessário (primeira task)

**Configurar no `.env`:**
```bash
# Carregar modelo no startup (comportamento padrão)
WHISPER_PRELOAD_MODEL=true

# OU desabilitar pré-carregamento (economia máxima)
WHISPER_PRELOAD_MODEL=false
```

**Configurar no docker-compose.yml:**
```yaml
services:
  audio-transcriber:
    environment:
      - WHISPER_PRELOAD_MODEL=false  # Economia de recursos no startup
```

---

## 🔄 Comportamento Automático

### ✅ Carregamento Sob Demanda (Lazy Loading)

O modelo **sempre será carregado automaticamente** quando necessário, mesmo que:
- Serviço inicie com `WHISPER_PRELOAD_MODEL=false`
- Modelo seja descarregado com `/model/unload`
- Houver falha no carregamento inicial

**Exemplo:**
```bash
# 1. Descarrega modelo
curl -X POST http://localhost:8002/model/unload
# ✅ Modelo descarregado, memória liberada

# 2. Nova transcrição é criada
curl -X POST http://localhost:8002/jobs -F "file=@audio.mp3"
# ✅ Modelo é carregado AUTOMATICAMENTE antes de processar
# ✅ Transcrição funciona normalmente
```

**Não há risco de falha!** O carregamento sob demanda garante que o serviço sempre funcionará.

---

## 📊 Uso de Memória por Modelo

| Modelo | RAM (estimado) | VRAM (GPU) | Qualidade | Velocidade |
|--------|----------------|------------|-----------|------------|
| `tiny` | ~75 MB | ~70 MB | ⭐ | ⚡⚡⚡ |
| `base` | ~150 MB | ~140 MB | ⭐⭐ | ⚡⚡⚡ |
| `small` | ~500 MB | ~460 MB | ⭐⭐⭐ | ⚡⚡ |
| `medium` | ~1.5 GB | ~1.4 GB | ⭐⭐⭐⭐ | ⚡ |
| `large` | ~3 GB | ~2.9 GB | ⭐⭐⭐⭐⭐ | 🐌 |

**Recomendações:**
- **Produção geral**: `base` (bom equilíbrio)
- **Alta qualidade**: `small` ou `medium`
- **Recursos limitados**: `tiny`
- **Máxima precisão**: `large` (requer GPU potente)

---

## 🌍 Impacto Ambiental

### Por que gerenciar o modelo importa?

**Consumo de GPU em idle:**
- GPU ociosa com modelo carregado: ~20-50W
- GPU sem modelo (idle real): ~5-10W
- **Economia**: ~15-40W por hora

**Cálculo anual (servidor 24/7):**
```
Economia por hora: 25W (média)
Horas ociosas por dia: 16h (67%)
Dias por ano: 365

Economia anual: 25W × 16h × 365 = 146 kWh/ano
Redução CO₂: ~73 kg/ano (média grid elétrico)
```

**Escalando para 10 servidores:**
- Economia: 1.460 kWh/ano
- Redução CO₂: 730 kg/ano (equivalente a ~350 árvores plantadas)

---

## 🚀 Guia Rápido

### Cenário 1: Uso Normal (24/7 com tasks esporádicas)
```bash
# Deixar WHISPER_PRELOAD_MODEL=true (padrão)
# Modelo sempre carregado, pronto para uso imediato
```

### Cenário 2: Economia Máxima (períodos idle longos)
```bash
# Configurar WHISPER_PRELOAD_MODEL=false
# Usar cron job para descarregar à noite:

# Crontab: descarregar às 20h (após expediente)
0 20 * * * curl -X POST http://localhost:8002/model/unload

# Crontab: carregar às 7h (antes do expediente)
0 7 * * * curl -X POST http://localhost:8002/model/load
```

### Cenário 3: Processamento Batch
```bash
# Script de processamento:
#!/bin/bash

# 1. Carrega modelo
curl -X POST http://localhost:8002/model/load

# 2. Processa arquivos
for file in *.mp3; do
  curl -X POST http://localhost:8002/jobs -F "file=@$file"
done

# 3. Aguarda conclusão (polling)
# ... (seu código de aguardar jobs)

# 4. Descarrega modelo
curl -X POST http://localhost:8002/model/unload
```

---

## 📝 Notas Importantes

### ✅ Segurança
- Descarregar modelo **NÃO afeta** tasks em execução
- Tasks em fila serão processadas normalmente (modelo recarrega automaticamente)
- Operação é **idempotente** (pode chamar múltiplas vezes sem erro)

### ⚠️ Performance
- Primeira transcrição após `unload` terá **+3-10s de delay** (carregamento)
- Transcrições subsequentes: latência normal
- GPU demora mais para carregar que CPU (~5-10s vs ~2-3s)

### 🔧 Troubleshooting
- Se `/model/unload` falhar: Verificar se há tasks em processamento
- Se `/model/load` falhar: Verificar logs de GPU/CUDA
- Se modelo não carregar automaticamente: Verificar espaço em disco/memória

---

## 📞 Suporte

Para dúvidas ou problemas:
1. Verificar logs do container: `docker logs audio-transcriber`
2. Consultar status: `GET /model/status`
3. Health check: `GET /health`

**Data de criação**: 04/11/2025  
**Versão do serviço**: 2.0.0
