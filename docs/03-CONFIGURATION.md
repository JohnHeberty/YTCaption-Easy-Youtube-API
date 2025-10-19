# ⚙️ Configuration

**Guia completo de todas as variáveis de ambiente (.env) - uma por uma.**

---

## 📋 Índice

1. [Application Settings](#application-settings)
2. [Server Settings](#server-settings)
3. [Whisper Settings](#whisper-settings)
4. [Parallel Transcription Settings](#parallel-transcription-settings)
5. [YouTube Settings](#youtube-settings)
6. [Storage Settings](#storage-settings)
7. [API Settings](#api-settings)
8. [Logging Settings](#logging-settings)
9. [Performance Settings](#performance-settings)

---

## Application Settings

### `APP_NAME`
**Nome da aplicação exibido nos logs e documentação.**

```bash
APP_NAME=Whisper Transcription API
```

- **Tipo**: String
- **Padrão**: `Whisper Transcription API`
- **Quando mudar**: Customização de branding

---

### `APP_VERSION`
**Versão da aplicação para controle de releases.**

```bash
APP_VERSION=1.0.0
```

- **Tipo**: String (Semantic Versioning)
- **Padrão**: `1.0.0`
- **Quando mudar**: Após mudanças importantes

---

### `APP_ENVIRONMENT`
**Ambiente de execução (afeta logs e comportamento).**

```bash
APP_ENVIRONMENT=production
```

- **Tipo**: String
- **Valores**: `production`, `development`, `staging`
- **Padrão**: `production`
- **Impacto**:
  - `production`: Logs minimalistas, otimizações
  - `development`: Logs verbosos, hot-reload
  - `staging`: Híbrido para testes

---

## Server Settings

### `HOST`
**Endereço IP que o servidor escuta.**

```bash
HOST=0.0.0.0
```

- **Tipo**: IP Address
- **Valores comuns**:
  - `0.0.0.0`: Todas as interfaces (Docker/produção)
  - `127.0.0.1`: Apenas localhost (desenvolvimento)
- **Padrão**: `0.0.0.0`
- **Quando mudar**: Segurança restritiva (apenas localhost)

---

### `PORT`
**Porta TCP onde a API escuta.**

```bash
PORT=8000
```

- **Tipo**: Integer (1-65535)
- **Padrão**: `8000`
- **Quando mudar**: Conflito de porta, firewall específico
- **Nota**: Alterar requer mudança no `docker-compose.yml`

---

## Whisper Settings

### `WHISPER_MODEL`
**Modelo de IA usado para transcrição.**

```bash
WHISPER_MODEL=base
```

- **Tipo**: String
- **Valores**: `tiny`, `base`, `small`, `medium`, `large`, `turbo`
- **Padrão**: `base`

| Modelo | Tamanho | RAM/Worker | Precisão | Velocidade | Uso Recomendado |
|--------|---------|------------|----------|------------|-----------------|
| `tiny` | 39M | ~400MB | ⭐⭐ | ⚡⚡⚡⚡⚡ | Desenvolvimento, testes |
| `base` | 74M | ~800MB | ⭐⭐⭐ | ⚡⚡⚡⚡ | **Produção (padrão)** |
| `small` | 244M | ~1.5GB | ⭐⭐⭐⭐ | ⚡⚡⚡ | Alta qualidade, CPU potente |
| `medium` | 769M | ~3GB | ⭐⭐⭐⭐⭐ | ⚡⚡ | GPU ou servidor dedicado |
| `large` | 1550M | ~6GB | ⭐⭐⭐⭐⭐ | ⚡ | GPU potente, máxima qualidade |

**Quando usar cada um**:
- **tiny**: Testes, desenvolvimento, velocidade máxima
- **base**: ✅ **Recomendado** - equilíbrio ideal
- **small**: Podcasts, entrevistas (qualidade alta)
- **medium**: Transcrições profissionais com GPU
- **large**: Academia, legendas oficiais

---

### `WHISPER_DEVICE`
**Dispositivo de processamento.**

```bash
WHISPER_DEVICE=cpu
```

- **Tipo**: String
- **Valores**: `cpu`, `cuda`
- **Padrão**: `cpu`

**CPU**:
- ✅ Funciona em qualquer servidor
- ⚠️ Mais lento (30min para 1h de áudio)
- 💰 Econômico

**CUDA (GPU NVIDIA)**:
- ✅ 10-20x mais rápido
- ⚠️ Requer GPU NVIDIA + drivers
- 💰 Servidor com GPU

**Como verificar se tem GPU:**
```bash
nvidia-smi
```

---

### `WHISPER_LANGUAGE`
**Idioma padrão para transcrição.**

```bash
WHISPER_LANGUAGE=auto
```

- **Tipo**: String (ISO 639-1)
- **Padrão**: `auto` (detecção automática)
- **Valores**: `auto`, `pt`, `en`, `es`, `fr`, `de`, `it`, `ja`, `ko`, `zh`

**Quando especificar**:
- ✅ **auto**: Deixe o Whisper detectar (recomendado)
- ✅ **pt**: Se todos os vídeos são em português (leve melhoria)
- ✅ **en**: Se todos os vídeos são em inglês

**Nota**: Especificar o idioma pode melhorar precisão em ~5-10%

---

## Parallel Transcription Settings

### `ENABLE_PARALLEL_TRANSCRIPTION`
**Habilita/desabilita processamento paralelo.**

```bash
ENABLE_PARALLEL_TRANSCRIPTION=true
```

- **Tipo**: Boolean
- **Valores**: `true`, `false`
- **Padrão**: `true`

**Quando habilitar (`true`)**:
- ✅ CPU com 4+ cores
- ✅ RAM suficiente (8GB+)
- ✅ Vídeos longos (10+ minutos)
- ✅ Quer velocidade máxima

**Quando desabilitar (`false`)**:
- ✅ CPU com 2 cores ou menos
- ✅ RAM limitada (4GB ou menos)
- ✅ Vídeos curtos (<5 min)
- ✅ Estabilidade > velocidade

**Benefício**: 3-4x mais rápido em CPUs multi-core

---

### `PARALLEL_WORKERS`
**Número de workers para processamento paralelo.**

```bash
PARALLEL_WORKERS=2
```

- **Tipo**: Integer
- **Valores**: `0` (auto-detect), `1`, `2`, `3`, `4`, `6`, `8`
- **Padrão**: `2` (conservador)

**Configurações por cenário**:

| Cores CPU | RAM Total | PARALLEL_WORKERS | RAM Usada (base model) |
|-----------|-----------|------------------|------------------------|
| 2 cores | 4GB | `0` (desabilitar paralelo) | ~800MB |
| 4 cores | 8GB | `2` ✅ | ~1.6GB |
| 8 cores | 16GB | `4` | ~3.2GB |
| 16 cores | 32GB+ | `0` (auto = usa todos) | ~6-8GB |

**Cálculo de RAM**:
```
RAM necessária = PARALLEL_WORKERS × RAM_por_modelo
```

Exemplo:
- `base` model = 800MB
- 4 workers = 4 × 800MB = **3.2GB RAM**

**Recomendações**:
- **0**: Auto-detect (usa todos os cores) - ⚠️ Alto uso de RAM
- **2**: ✅ **Conservador** - funciona na maioria dos casos
- **4**: Agressivo - requer 16GB+ RAM
- **8+**: Apenas servidores dedicados

---

### `PARALLEL_CHUNK_DURATION`
**Duração de cada chunk de áudio processado em paralelo.**

```bash
PARALLEL_CHUNK_DURATION=120
```

- **Tipo**: Integer (segundos)
- **Valores**: `60`, `90`, `120`, `180`, `240`
- **Padrão**: `120` (2 minutos)

**Como escolher**:

| Valor | Chunks (30min) | Overhead | Uso Recomendado |
|-------|----------------|----------|-----------------|
| `60` | 30 chunks | Alto | Muitos cores (8+) |
| `90` | 20 chunks | Médio | Equilibrado |
| `120` ✅ | 15 chunks | Baixo | **Padrão (recomendado)** |
| `180` | 10 chunks | Muito baixo | Poucos cores (2-4) |
| `240` | 7 chunks | Mínimo | CPU limitado |

**Trade-off**:
- ⬇️ Chunks menores (60s) = Mais paralelismo, mais overhead
- ⬆️ Chunks maiores (240s) = Menos paralelismo, menos overhead

---

### `AUDIO_LIMIT_SINGLE_CORE`
**Duração limite para usar single-core ao invés de paralelo.**

```bash
AUDIO_LIMIT_SINGLE_CORE=300
```

- **Tipo**: Integer (segundos)
- **Padrão**: `300` (5 minutos)

**Como funciona**:
- Áudio **< 5min**: Usa **single-core** (mais eficiente, sem overhead)
- Áudio **≥ 5min**: Usa **paralelo** (mais rápido)

**Quando ajustar**:

| Valor | Comportamento | Uso Recomendado |
|-------|---------------|-----------------|
| `60` | Paralelo para >1min | Servidor potente, prioridade velocidade |
| `180` | Paralelo para >3min | Equilibrado |
| `300` ✅ | Paralelo para >5min | **Padrão (recomendado)** |
| `600` | Paralelo para >10min | RAM limitada |
| `9999` | Sempre single-core | Desabilitar paralelo (manter fallback) |

---

## YouTube Settings

### `YOUTUBE_FORMAT`
**Qualidade do áudio baixado do YouTube.**

```bash
YOUTUBE_FORMAT=worstaudio
```

- **Tipo**: String
- **Valores**: `worstaudio`, `bestaudio`
- **Padrão**: `worstaudio`

**Por quê "worstaudio"?**
- ✅ Download 10x mais rápido
- ✅ Menos uso de disco
- ✅ Whisper funciona bem com baixa qualidade
- ✅ Suficiente para transcrição

**Quando usar "bestaudio"**:
- Análise de áudio detalhada
- Música/sons complexos
- Você tem banda e disco sobrando

---

### `MAX_VIDEO_SIZE_MB`
**Tamanho máximo de vídeo permitido (em MB).**

```bash
MAX_VIDEO_SIZE_MB=2500
```

- **Tipo**: Integer (megabytes)
- **Padrão**: `2500` (2.5GB)
- **Limite recomendado**: 500MB - 5000MB

**Cálculo aproximado**:
```
1 hora de áudio (worstaudio) ≈ 30-50MB
```

**Quando ajustar**:
- `500`: Vídeos curtos apenas (<30min)
- `1500`: ✅ Até 1 hora
- `2500`: ✅ **Padrão** - até 3 horas
- `5000`: Vídeos muito longos (palestras, lives)

---

### `MAX_VIDEO_DURATION_SECONDS`
**Duração máxima de vídeo permitida (em segundos).**

```bash
MAX_VIDEO_DURATION_SECONDS=10800
```

- **Tipo**: Integer (segundos)
- **Padrão**: `10800` (3 horas)

**Conversões úteis**:
```
1800 = 30 minutos
3600 = 1 hora
7200 = 2 horas
10800 = 3 horas ✅ (padrão)
14400 = 4 horas
```

**Quando ajustar**:
- `1800`: Apenas vídeos curtos
- `3600`: Até 1 hora (aulas, tutoriais)
- `7200`: Até 2 horas (palestras)
- `10800`: ✅ **Padrão** - até 3 horas
- `21600`: Lives, podcasts longos (6 horas)

---

### `DOWNLOAD_TIMEOUT`
**Timeout para download do YouTube (em segundos).**

```bash
DOWNLOAD_TIMEOUT=900
```

- **Tipo**: Integer (segundos)
- **Padrão**: `900` (15 minutos)

**Quando ajustar**:
- `300`: Internet rápida (5 min)
- `600`: Padrão (10 min)
- `900`: ✅ **Recomendado** - 15 minutos
- `1800`: Internet lenta ou vídeos grandes (30 min)

---

## Storage Settings

### `TEMP_DIR`
**Diretório para arquivos temporários.**

```bash
TEMP_DIR=./temp
```

- **Tipo**: Path (relativo ou absoluto)
- **Padrão**: `./temp`
- **Quando mudar**: Trocar disco/volume

**Exemplo absoluto**:
```bash
TEMP_DIR=/mnt/storage/ytcaption-temp
```

---

### `CLEANUP_ON_STARTUP`
**Limpar arquivos temporários ao iniciar.**

```bash
CLEANUP_ON_STARTUP=true
```

- **Tipo**: Boolean
- **Valores**: `true`, `false`
- **Padrão**: `true`

**Recomendação**: Deixe `true` para evitar acúmulo de lixo

---

### `CLEANUP_AFTER_PROCESSING`
**Limpar arquivos temporários após cada transcrição.**

```bash
CLEANUP_AFTER_PROCESSING=true
```

- **Tipo**: Boolean
- **Valores**: `true`, `false`
- **Padrão**: `true`

**Quando desabilitar (`false`)**:
- Debug (analisar arquivos baixados)
- Cache de áudios
- ⚠️ Requer limpeza manual periódica

---

### `MAX_TEMP_AGE_HOURS`
**Idade máxima de arquivos temp antes da limpeza.**

```bash
MAX_TEMP_AGE_HOURS=24
```

- **Tipo**: Integer (horas)
- **Padrão**: `24` (1 dia)
- **Valores**: `1`, `6`, `12`, `24`, `48`, `72`

---

## API Settings

### `MAX_CONCURRENT_REQUESTS`
**Número máximo de transcrições simultâneas.**

```bash
MAX_CONCURRENT_REQUESTS=3
```

- **Tipo**: Integer
- **Padrão**: `3`

**Cálculo**:
```
RAM necessária = MAX_CONCURRENT_REQUESTS × RAM_por_modelo
```

Exemplo:
- 3 requests × 800MB (base) = **2.4GB RAM**

**Recomendações por RAM**:
- 4GB RAM: `MAX_CONCURRENT_REQUESTS=2`
- 8GB RAM: `MAX_CONCURRENT_REQUESTS=3` ✅
- 16GB RAM: `MAX_CONCURRENT_REQUESTS=6`
- 32GB+ RAM: `MAX_CONCURRENT_REQUESTS=10`

---

### `REQUEST_TIMEOUT`
**Timeout para cada requisição (em segundos).**

```bash
REQUEST_TIMEOUT=3600
```

- **Tipo**: Integer (segundos)
- **Padrão**: `3600` (1 hora)

**Quando ajustar**:
- `1800`: Vídeos até 30min
- `3600`: ✅ **Padrão** - até 1 hora
- `7200`: Vídeos até 2 horas
- `10800`: Vídeos até 3 horas

---

### `ENABLE_CORS`
**Habilitar CORS (para acesso de navegadores).**

```bash
ENABLE_CORS=true
```

- **Tipo**: Boolean
- **Valores**: `true`, `false`
- **Padrão**: `true`

**Quando desabilitar**: API backend-only (sem frontend web)

---

### `CORS_ORIGINS`
**Origens permitidas para CORS.**

```bash
CORS_ORIGINS=*
```

- **Tipo**: String (URLs separadas por vírgula)
- **Padrão**: `*` (todas as origens)

**Exemplos**:
```bash
# Permitir todas (desenvolvimento)
CORS_ORIGINS=*

# Apenas domínio específico (produção)
CORS_ORIGINS=https://meu-site.com

# Múltiplos domínios
CORS_ORIGINS=https://meu-site.com,https://app.meu-site.com
```

---

## Logging Settings

### `LOG_LEVEL`
**Nível de detalhamento dos logs.**

```bash
LOG_LEVEL=INFO
```

- **Tipo**: String
- **Valores**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Padrão**: `INFO`

| Nível | Detalhamento | Uso |
|-------|--------------|-----|
| `DEBUG` | Máximo | Desenvolvimento |
| `INFO` ✅ | Moderado | **Produção (padrão)** |
| `WARNING` | Apenas avisos | Produção silenciosa |
| `ERROR` | Apenas erros | Mínimo |

---

### `LOG_FORMAT`
**Formato de saída dos logs.**

```bash
LOG_FORMAT=json
```

- **Tipo**: String
- **Valores**: `json`, `text`
- **Padrão**: `json`

**JSON**: Ideal para parsing, ferramentas de logs (ELK, Grafana)  
**TEXT**: Mais legível para humanos

---

### `LOG_FILE`
**Caminho do arquivo de log.**

```bash
LOG_FILE=./logs/app.log
```

- **Tipo**: Path
- **Padrão**: `./logs/app.log`

---

## Performance Settings

### `WORKERS`
**Número de workers Uvicorn (processos API).**

```bash
WORKERS=1
```

- **Tipo**: Integer
- **Valores**: `1`, `2`, `4`
- **Padrão**: `1` ✅

**⚠️ IMPORTANTE**: Para esta aplicação, `WORKERS=1` é **ótimo**!

**Por quê?**
- Aplicação é I/O bound (espera download, FFmpeg)
- Múltiplos workers competem pelo modelo Whisper
- Async/await do FastAPI já gerencia concorrência

**Quando usar > 1**:
- Tráfego altíssimo (100+ req/s)
- RAM sobrando (8GB+ por worker)
- Você desabilitou transcrição paralela

---

### `WORKER_CLASS`
**Classe de worker do Uvicorn.**

```bash
WORKER_CLASS=uvicorn.workers.UvicornWorker
```

- **Tipo**: String
- **Padrão**: `uvicorn.workers.UvicornWorker`
- **Não alterar** (valor correto para async)

---

## 📊 Configurações Recomendadas por Cenário

### Servidor Pequeno (4GB RAM, 2 cores)
```bash
WHISPER_MODEL=tiny
WHISPER_DEVICE=cpu
ENABLE_PARALLEL_TRANSCRIPTION=false
MAX_CONCURRENT_REQUESTS=2
WORKERS=1
```

### Servidor Médio (8GB RAM, 4 cores) ✅ **Padrão**
```bash
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=2
AUDIO_LIMIT_SINGLE_CORE=300
MAX_CONCURRENT_REQUESTS=3
WORKERS=1
```

### Servidor Grande (16GB+ RAM, 8+ cores)
```bash
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=4
AUDIO_LIMIT_SINGLE_CORE=180
MAX_CONCURRENT_REQUESTS=6
WORKERS=1
```

### Servidor com GPU
```bash
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda
ENABLE_PARALLEL_TRANSCRIPTION=false  # GPU já é rápido
MAX_CONCURRENT_REQUESTS=4
WORKERS=1
```

---

**Próximo**: [Uso da API](./04-API-USAGE.md)

**Versão**: 1.3.3+  
**Última atualização**: 19/10/2025
