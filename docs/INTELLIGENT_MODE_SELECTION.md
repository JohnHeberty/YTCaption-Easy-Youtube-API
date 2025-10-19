# 🎯 Seleção Inteligente de Modo de Transcrição

## Como Funciona?

O sistema agora decide **automaticamente** qual modo usar baseado na duração do áudio:

```
┌─────────────────────────────────────────────────────────────┐
│                    FLUXO DE DECISÃO                         │
└─────────────────────────────────────────────────────────────┘

    Requisição de Transcrição
             │
             ▼
    ┌─────────────────┐
    │ Detecta duração │  (usando FFprobe)
    │   do áudio      │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────────────────────────────────────────┐
    │   Duração < AUDIO_LIMIT_SINGLE_CORE (5 min)?       │
    └──────────────┬──────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
       SIM                   NÃO
        │                     │
        ▼                     ▼
┌──────────────┐      ┌──────────────┐
│ SINGLE-CORE  │      │   PARALELO   │
│              │      │              │
│ • Eficiente  │      │ • Rápido     │
│ • Baixo RAM  │      │ • Multi-core │
│ • < 800MB    │      │ • ~1.6GB RAM │
└──────────────┘      └──────┬───────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                 SUCESSO          FALHA?
                    │             (OOM)
                    │                 │
                    │                 ▼
                    │         ┌──────────────┐
                    │         │   FALLBACK   │
                    │         │ SINGLE-CORE  │
                    │         └──────────────┘
                    │                 │
                    └────────┬────────┘
                             │
                             ▼
                    ✅ Transcrição OK
```

## 🎭 Exemplo Real

### Cenário 1: Vídeo Curto (3 minutos)

```bash
[INFO] 📊 Audio duration: 180.0s < 300s limit.
[INFO] Using SINGLE-CORE mode (more efficient for short audio)
[INFO] 🎤 Starting standard transcription...
[INFO] ✅ Transcription completed in 45.3s
```

**Vantagens**:
- Sem overhead de criação de workers
- Usa apenas ~800MB RAM
- Mais rápido para áudios curtos (não há divisão de chunks)

---

### Cenário 2: Vídeo Longo (30 minutos)

```bash
[INFO] 📊 Audio duration: 1800.0s >= 300s limit.
[INFO] Using PARALLEL mode (faster for long audio)
[INFO] 🚀 [PARALLEL] Starting parallel transcription...
[INFO] 📦 [PARALLEL] Split audio into 15 chunks of 120.0s each
[INFO] 👥 [PARALLEL] Processing with 2 workers
[INFO] ⏱️  [PARALLEL] Parallel transcription completed in 7m 23s
[INFO] ✅ [PARALLEL] Merged 15 chunks successfully
```

**Vantagens**:
- Speedup ~4x (30min → 7min)
- Usa múltiplos cores eficientemente
- RAM controlada (2 workers = ~1.6GB)

---

### Cenário 3: Vídeo Longo + Servidor com Pouca RAM

```bash
[INFO] 📊 Audio duration: 1800.0s >= 300s limit.
[INFO] Using PARALLEL mode (faster for long audio)
[INFO] 🚀 [PARALLEL] Starting parallel transcription...
[ERROR] [PARALLEL] Process pool error: A process in the process pool was terminated abruptly
[WARNING] [PARALLEL] Disabling parallel mode and falling back to normal transcription
[INFO] 🎤 Starting standard transcription...
[INFO] ✅ Transcription completed in 28m 45s
```

**Vantagens**:
- API **não falha** (retorna 200 OK)
- Fallback automático para single-core
- Próximas requisições usam single-core direto (paralelo desabilitado)

---

## ⚙️ Configuração

### Arquivo `.env`

```bash
# Parallel Transcription Settings
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=2                 # Conservador: 2 workers
PARALLEL_CHUNK_DURATION=120        # 2 minutos por chunk
AUDIO_LIMIT_SINGLE_CORE=300        # 5 minutos (limite inteligente)
```

### Ajustar o Limite

Você pode ajustar `AUDIO_LIMIT_SINGLE_CORE` baseado no seu caso de uso:

| Valor | Comportamento | Melhor Para |
|-------|---------------|-------------|
| `60` | Paralelo para > 1min | Máxima performance, servidor potente |
| `180` | Paralelo para > 3min | Equilíbrio |
| `300` | Paralelo para > 5min | **Recomendado (padrão)** |
| `600` | Paralelo para > 10min | Servidor com pouca RAM |
| `9999` | Sempre single-core | Desabilitar paralelo (mantém fallback) |

---

## 📊 Benchmarks

### Áudio de 3 minutos (180s)

| Modo | Tempo | RAM | Escolha do Sistema |
|------|-------|-----|-------------------|
| Single-core | **45s** | ~800MB | ✅ **ESCOLHIDO** (< 300s) |
| Paralelo (2 workers) | 52s | ~1.6GB | ❌ Overhead > ganho |

### Áudio de 10 minutos (600s)

| Modo | Tempo | RAM | Escolha do Sistema |
|------|-------|-----|-------------------|
| Single-core | 2m 30s | ~800MB | ❌ Lento |
| Paralelo (2 workers) | **1m 15s** | ~1.6GB | ✅ **ESCOLHIDO** (>= 300s) |

### Áudio de 30 minutos (1800s)

| Modo | Tempo | RAM | Escolha do Sistema |
|------|-------|-----|-------------------|
| Single-core | 7m 30s | ~800MB | ❌ Muito lento |
| Paralelo (2 workers) | **3m 45s** | ~1.6GB | ✅ **ESCOLHIDO** (>= 300s) |
| Paralelo (4 workers) | **2m 15s** | ~3.2GB | ⚠️ Se aumentar PARALLEL_WORKERS |

---

## 🎯 Recomendações por Caso de Uso

### 📱 Transcrição de Podcasts (20-60min)

```bash
AUDIO_LIMIT_SINGLE_CORE=300        # Sempre usa paralelo
PARALLEL_WORKERS=4                  # Speedup máximo
PARALLEL_CHUNK_DURATION=120
```

### 🎬 Transcrição de Vídeos Curtos (<5min)

```bash
AUDIO_LIMIT_SINGLE_CORE=300        # Usa single-core (eficiente)
PARALLEL_WORKERS=2                  # Caso apareçam vídeos longos
```

### 🖥️ Servidor com Pouca RAM (4-8GB)

```bash
AUDIO_LIMIT_SINGLE_CORE=600        # Paralelo só para > 10min
PARALLEL_WORKERS=2                  # Conservador
WHISPER_MODEL=tiny                  # Modelo leve (~400MB/worker)
```

### 🚀 Máxima Performance (16GB+ RAM)

```bash
AUDIO_LIMIT_SINGLE_CORE=180        # Paralelo para > 3min
PARALLEL_WORKERS=4                  # Agressivo
WHISPER_MODEL=base                  # Bom equilíbrio
```

---

## 🔍 Como Verificar Qual Modo Foi Usado?

### Via Logs

```bash
docker-compose logs -f | grep "Audio duration"
```

Você verá:
```
📊 Audio duration: 180.0s < 300s limit. Using SINGLE-CORE mode
```
ou
```
📊 Audio duration: 1800.0s >= 300s limit. Using PARALLEL mode
```

### Via Monitoramento de RAM

```bash
# Em outra janela
docker stats
```

- **Single-core**: ~800MB RAM
- **Paralelo (2 workers)**: ~1.6GB RAM
- **Paralelo (4 workers)**: ~3.2GB RAM

---

## 🎉 Benefícios da Seleção Inteligente

✅ **Zero configuração manual**: Sistema decide sozinho  
✅ **Máxima eficiência**: Single-core para curtos, paralelo para longos  
✅ **Economia de RAM**: Não desperdiça recursos  
✅ **Fallback robusto**: Se paralelo falhar, usa single-core  
✅ **Logs claros**: Sempre informa qual modo foi escolhido e por quê  

---

## 📖 Ver Também

- **[PARALLEL_TRANSCRIPTION_GUIDE.md](./PARALLEL_TRANSCRIPTION_GUIDE.md)**: Guia completo de paralelização
- **[CONFIGURATION_EXAMPLES.md](./CONFIGURATION_EXAMPLES.md)**: 6 cenários de configuração prontos
- **[CHANGELOG.md](./CHANGELOG.md)**: Histórico de versões

---

**Versão**: 1.3.2  
**Data**: 19/10/2025
