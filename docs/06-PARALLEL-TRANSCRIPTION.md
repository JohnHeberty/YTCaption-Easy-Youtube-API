# ⚡ Parallel Transcription

**Guia completo de transcrição paralela - como funciona, configuração e otimização.**

> **📢 NOTA IMPORTANTE - v2.0.0:**  
> A partir da versão 2.0.0, a transcrição paralela foi completamente redesenhada com **Persistent Worker Pool**.  
> Este documento cobre conceitos gerais. Para detalhes da nova arquitetura, veja [10-PARALLEL-ARCHITECTURE.md](./10-PARALLEL-ARCHITECTURE.md).

---

## 📋 Índice

1. [O que é Transcrição Paralela](#o-que-é-transcrição-paralela)
2. [Como Funciona](#como-funciona)
3. [Benefícios](#benefícios)
4. [Configuração](#configuração)
5. [Cálculo de Recursos](#cálculo-de-recursos)
6. [Otimização](#otimização)
7. [Troubleshooting](#troubleshooting)

---

## O que é Transcrição Paralela

**Transcrição paralela** divide o áudio em **chunks** (pedaços) e processa cada um em **paralelo** usando múltiplos workers (processos).

### Modo Traditional (Single-Core)

```
Áudio (30 min)
    ↓
[Worker 1] → 30 minutos de processamento
    ↓
Resultado
```

⏱️ **Tempo**: 30 minutos

---

### Modo Paralelo (Multi-Core)

```
Áudio (30 min)
    ↓
[Split em 15 chunks de 2 min]
    ↓
[Worker 1] → Chunk 1-4   (8 min)
[Worker 2] → Chunk 5-8   (8 min)
[Worker 3] → Chunk 9-12  (8 min)
[Worker 4] → Chunk 13-15 (6 min)
    ↓
[Merge] → Resultado
```

⏱️ **Tempo**: ~8-10 minutos (3-4x mais rápido!)

---

## Como Funciona

### 1. Detecção Automática de Duração

```python
if audio_duration < AUDIO_LIMIT_SINGLE_CORE:
    # Usa single-core (mais eficiente para áudios curtos)
    return transcribe_single_core()
else:
    # Usa paralelo (mais rápido para áudios longos)
    return transcribe_parallel()
```

**Padrão**: `AUDIO_LIMIT_SINGLE_CORE=300` (5 minutos)

---

### 2. Divisão em Chunks

```python
chunk_duration = PARALLEL_CHUNK_DURATION  # Padrão: 120 segundos

# Exemplo: áudio de 30 min (1800s)
num_chunks = 1800 / 120 = 15 chunks
```

---

### 3. Processamento Paralelo

```python
# Cria pool de workers
with multiprocessing.Pool(processes=PARALLEL_WORKERS) as pool:
    # Processa todos os chunks em paralelo
    results = pool.map(transcribe_chunk, chunks)
```

---

### 4. Merge de Resultados

```python
# Une todos os chunks em ordem
final_transcription = merge_segments(results)
```

---

## Benefícios

### ✅ Velocidade

**Ganho de Performance**:

| CPU Cores | PARALLEL_WORKERS | Speedup Real |
|-----------|------------------|--------------|
| 2 cores | Desabilitado | 1x (baseline) |
| 4 cores | 2 workers | 1.8-2.2x |
| 8 cores | 4 workers | 3.2-3.8x |
| 16 cores | 8 workers | 5-6x |

**Exemplo Prático**:
- Áudio: 1 hora
- Single-core: ~60 minutos
- Paralelo (4 workers): ~15-18 minutos

---

### ✅ Eficiência

- Aproveita **todos os cores** da CPU
- Melhor utilização de recursos
- Reduz tempo de espera

---

### ✅ Escalabilidade

- Adicione mais CPU cores → Ganhe mais velocidade
- Configuração flexível por hardware

---

### ⚠️ Trade-offs

**Desvantagens**:
- **Consome mais RAM** (cada worker = 1 modelo Whisper)
- **Overhead de merge** (pequeno, ~1-2%)
- **Não funciona com GPU** (GPU já é rápido o suficiente)

---

## Configuração

### Variáveis de Ambiente (.env)

```bash
# Habilitar/Desabilitar
ENABLE_PARALLEL_TRANSCRIPTION=true

# Número de workers (0 = auto-detect)
PARALLEL_WORKERS=2

# Duração de cada chunk (segundos)
PARALLEL_CHUNK_DURATION=120

# Limite para usar single-core (segundos)
AUDIO_LIMIT_SINGLE_CORE=300
```

---

### ENABLE_PARALLEL_TRANSCRIPTION

**Habilita ou desabilita completamente o modo paralelo.**

```bash
ENABLE_PARALLEL_TRANSCRIPTION=true
```

| Valor | Comportamento |
|-------|---------------|
| `true` | Usa paralelo para áudios longos |
| `false` | Sempre usa single-core |

**Quando desabilitar**:
- ❌ CPU com 2 cores ou menos
- ❌ RAM limitada (< 4GB)
- ❌ Você usa GPU (CUDA)

---

### PARALLEL_WORKERS

**Número de processos paralelos.**

```bash
PARALLEL_WORKERS=2
```

| Valor | Comportamento | RAM Usada (base model) |
|-------|---------------|------------------------|
| `0` | Auto-detect (usa todos os cores) | Variável |
| `1` | Single-core (sem paralelismo) | ~800 MB |
| `2` | 2 workers ✅ | ~1.6 GB |
| `4` | 4 workers | ~3.2 GB |
| `8` | 8 workers | ~6.4 GB |

**Cálculo**:
```
RAM necessária = PARALLEL_WORKERS × RAM_por_modelo
```

**Recomendações por Hardware**:

| CPU Cores | RAM Total | PARALLEL_WORKERS |
|-----------|-----------|------------------|
| 2 cores | 4 GB | `0` (desabilitar) |
| 4 cores | 8 GB | `2` ✅ |
| 8 cores | 16 GB | `4` |
| 16 cores | 32 GB+ | `0` (auto) |

---

### PARALLEL_CHUNK_DURATION

**Duração de cada chunk processado.**

```bash
PARALLEL_CHUNK_DURATION=120
```

| Valor | Chunks (30min) | Overhead | Uso |
|-------|----------------|----------|-----|
| `60` | 30 chunks | Alto | Muitos cores (8+) |
| `90` | 20 chunks | Médio | Equilibrado |
| `120` ✅ | 15 chunks | Baixo | **Padrão** |
| `180` | 10 chunks | Muito baixo | Poucos cores (2-4) |
| `240` | 7 chunks | Mínimo | RAM limitada |

**Como escolher**:

**Chunks menores** (60s):
- ✅ Melhor paralelismo (mais chunks)
- ⚠️ Mais overhead de merge
- 🎯 Use se: CPU com 8+ cores

**Chunks maiores** (240s):
- ✅ Menos overhead
- ⚠️ Menos paralelismo
- 🎯 Use se: CPU com 2-4 cores

---

### AUDIO_LIMIT_SINGLE_CORE

**Limite para decidir entre single-core vs paralelo.**

```bash
AUDIO_LIMIT_SINGLE_CORE=300
```

**Como funciona**:
```python
if audio_duration < 300:  # < 5 minutos
    use_single_core()  # Mais eficiente
else:
    use_parallel()  # Mais rápido
```

| Valor | Comportamento |
|-------|---------------|
| `60` | Paralelo para áudios > 1 min |
| `180` | Paralelo para áudios > 3 min |
| `300` ✅ | Paralelo para áudios > 5 min (padrão) |
| `600` | Paralelo para áudios > 10 min |
| `9999` | Sempre single-core |

**Por que existe esse limite?**
- Áudios curtos (< 5min) processam rápido mesmo em single-core
- Overhead de split/merge não compensa
- Single-core usa menos RAM

---

## Cálculo de Recursos

### RAM Necessária

**Fórmula Base**:
```
RAM_total = PARALLEL_WORKERS × RAM_por_modelo
```

**Tabela por Modelo**:

| Modelo | RAM/Worker | 2 Workers | 4 Workers | 8 Workers |
|--------|------------|-----------|-----------|-----------|
| `tiny` | 400 MB | 800 MB | 1.6 GB | 3.2 GB |
| `base` | 800 MB | 1.6 GB | 3.2 GB | 6.4 GB |
| `small` | 1.5 GB | 3 GB | 6 GB | 12 GB |
| `medium` | 3 GB | 6 GB | 12 GB | 24 GB |

**Exemplo**:
```bash
WHISPER_MODEL=base
PARALLEL_WORKERS=4

# RAM necessária = 4 × 800MB = 3.2 GB
```

---

### CPU Cores Recomendados

**Regra Geral**:
```
PARALLEL_WORKERS = CPU_CORES / 2
```

**Exemplos**:

| CPU Cores | PARALLEL_WORKERS | Uso CPU |
|-----------|------------------|---------|
| 4 cores | 2 workers | ~80-90% |
| 8 cores | 4 workers | ~85-95% |
| 16 cores | 8 workers | ~90-100% |

---

### Tempo de Processamento

**Estimativa**:
```
tempo = (audio_duration / PARALLEL_WORKERS) × overhead_factor
```

**Overhead Factor**: ~1.1-1.2 (10-20% de overhead para merge)

**Exemplo**:
```
Áudio: 30 minutos (1800s)
PARALLEL_WORKERS: 4
Overhead: 1.15

Tempo = (1800 / 4) × 1.15 = 518 segundos ≈ 8.6 minutos
```

---

## Otimização

### 1. Configure Workers pelo Hardware

**Servidor com 4 cores, 8GB RAM**:
```bash
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=2
WHISPER_MODEL=base
```

**Servidor com 8 cores, 16GB RAM**:
```bash
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=4
WHISPER_MODEL=base
```

**Servidor com 16+ cores, 32GB+ RAM**:
```bash
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=0  # Auto-detect
WHISPER_MODEL=small
```

---

### 2. Ajuste Chunk Duration

**Muitos cores (8+)**:
```bash
PARALLEL_CHUNK_DURATION=60  # Chunks menores
```

**Poucos cores (2-4)**:
```bash
PARALLEL_CHUNK_DURATION=180  # Chunks maiores
```

---

### 3. Combine com MAX_CONCURRENT_REQUESTS

```bash
# 8GB RAM, base model (800MB/worker)
PARALLEL_WORKERS=2
MAX_CONCURRENT_REQUESTS=2

# RAM total = (2 workers × 800MB) × 2 requests = 3.2GB
```

**Regra**:
```
RAM_necessária = PARALLEL_WORKERS × RAM_modelo × MAX_CONCURRENT_REQUESTS
```

---

### 4. Use GPU para Modelos Grandes

**Ao invés de**:
```bash
WHISPER_MODEL=medium
WHISPER_DEVICE=cpu
ENABLE_PARALLEL_TRANSCRIPTION=true  # Lento mesmo assim
```

**Use**:
```bash
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda
ENABLE_PARALLEL_TRANSCRIPTION=false  # GPU já é rápido
```

---

## Troubleshooting

### ❌ Erro: Out of Memory (OOM)

**Sintomas**:
```
RuntimeError: Out of memory
Process killed (OOM)
```

**Causas**:
- Muitos workers para a RAM disponível
- Modelo muito grande

**Soluções**:

1. **Reduza workers**:
```bash
PARALLEL_WORKERS=2  # Era 4
```

2. **Use modelo menor**:
```bash
WHISPER_MODEL=tiny  # Era base
```

3. **Desabilite paralelo**:
```bash
ENABLE_PARALLEL_TRANSCRIPTION=false
```

---

### ❌ Erro: CPU Throttling

**Sintomas**:
- Processamento muito lento
- CPU em 100% por muito tempo
- Sistema trava/lag

**Causas**:
- Muitos workers para os cores disponíveis

**Soluções**:

1. **Reduza workers**:
```bash
PARALLEL_WORKERS=2  # Era 8
```

2. **Aumente chunk duration**:
```bash
PARALLEL_CHUNK_DURATION=240  # Era 60
```

---

### ❌ Erro: Transcrição Dessincronizada

**Sintomas**:
- Timestamps errados
- Texto fora de ordem

**Causas**:
- Bug no merge (muito raro)

**Soluções**:

1. **Use single-core temporariamente**:
```bash
ENABLE_PARALLEL_TRANSCRIPTION=false
```

2. **Reporte o bug** (com logs)

---

### ⚠️ Performance Não Melhorou

**Sintomas**:
- Paralelo não é mais rápido que single-core

**Causas**:
- Áudio muito curto (< 5 min)
- Chunks muito pequenos (overhead alto)
- Disco lento (bottleneck I/O)

**Soluções**:

1. **Aumente limite single-core**:
```bash
AUDIO_LIMIT_SINGLE_CORE=600  # Era 300
```

2. **Aumente chunk duration**:
```bash
PARALLEL_CHUNK_DURATION=180  # Era 60
```

---

## Comparação: Single-Core vs Paralelo

### Teste Real: Áudio de 30 minutos

**Hardware**: 8 cores CPU, 16GB RAM, modelo `base`

| Modo | Configuração | Tempo | RAM Usada | CPU Uso |
|------|--------------|-------|-----------|---------|
| Single-core | Padrão | 28 min | 900 MB | 12% (1 core) |
| Paralelo (2w) | PARALLEL_WORKERS=2 | 15 min | 1.8 GB | 45% |
| Paralelo (4w) | PARALLEL_WORKERS=4 | 9 min | 3.5 GB | 85% |
| Paralelo (8w) | PARALLEL_WORKERS=8 | 8 min | 7 GB | 98% |

**Conclusão**: 4 workers = melhor custo-benefício (3.1x speedup)

---

## Configurações Recomendadas

### Desenvolvimento/Testes

```bash
ENABLE_PARALLEL_TRANSCRIPTION=false
WHISPER_MODEL=tiny
```

**Por quê**: Velocidade já é boa, economiza RAM.

---

### Produção (4 cores, 8GB RAM)

```bash
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=2
PARALLEL_CHUNK_DURATION=120
AUDIO_LIMIT_SINGLE_CORE=300
WHISPER_MODEL=base
```

**Resultado**: 2x speedup, uso moderado de recursos.

---

### Produção (8+ cores, 16GB+ RAM)

```bash
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=4
PARALLEL_CHUNK_DURATION=90
AUDIO_LIMIT_SINGLE_CORE=180
WHISPER_MODEL=base
```

**Resultado**: 3-4x speedup, alto uso de recursos.

---

### Servidor Dedicado (16+ cores, 32GB+ RAM)

```bash
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=0  # Auto-detect
PARALLEL_CHUNK_DURATION=60
AUDIO_LIMIT_SINGLE_CORE=60
WHISPER_MODEL=small
```

**Resultado**: 5-6x speedup, máxima performance.

---

### GPU NVIDIA

```bash
ENABLE_PARALLEL_TRANSCRIPTION=false  # Desnecessário
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda
```

**Por quê**: GPU já é 10-20x mais rápido que CPU paralelo.

---

## Comandos Úteis

### Verificar Uso de CPU Durante Transcrição

**Linux/WSL**:
```bash
htop
```

**Windows (PowerShell)**:
```powershell
Get-Process | Where-Object {$_.ProcessName -like "*python*"} | Select-Object CPU, WorkingSet64
```

---

### Verificar Uso de RAM

**Linux/WSL**:
```bash
free -h
```

**Docker**:
```bash
docker stats ytcaption
```

---

### Testar Performance

```bash
# 1. Single-core
curl -X POST http://localhost:8000/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -d '{"video_url": "URL_TESTE"}' \
  | jq '.processing_time, .mode'

# 2. Habilitar paralelo e testar novamente
# Edite .env: ENABLE_PARALLEL_TRANSCRIPTION=true
docker-compose restart

# 3. Comparar tempos
```

---

## Recursos Adicionais

- **Persistent Worker Pool Architecture**: Ver [10-PARALLEL-ARCHITECTURE.md](./10-PARALLEL-ARCHITECTURE.md)
- **Changelog**: Ver [CHANGELOG.md](./CHANGELOG.md) para histórico de versões
- **Configuração Completa**: Ver [Configuration](./03-CONFIGURATION.md)

---

**Próximo**: [Deployment](./07-DEPLOYMENT.md)

**Versão**: 2.0.0  
**Última atualização**: 19/10/2025
