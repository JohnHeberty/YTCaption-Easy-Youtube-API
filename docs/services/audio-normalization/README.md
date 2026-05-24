# 🔊 Audio Normalization - Processamento de Áudio

O **Audio Normalization** é responsável por processar e normalizar arquivos de áudio para otimizar a qualidade da transcrição posterior.

## 🎯 Função

- Normalização de volume e qualidade de áudio
- Remoção de ruído de fundo
- Conversão para formato mono
- Aplicação de filtros high-pass
- Isolamento de vocais (separação voz/música)
- Sample rate adjustment para 16kHz (otimizado para speech-to-text)

## 🔧 Configuração

### Variáveis de Ambiente Principais

```bash
# Servidor
HOST=0.0.0.0
PORT=8002

# Redis
REDIS_URL=redis://localhost:6379/1

# Processamento
MAX_FILE_SIZE_MB=200
PROCESSING_TIMEOUT_SECONDS=300
TEMP_DIR=./temp
OUTPUT_DIR=./processed

# Cache
CACHE_TTL_HOURS=24
```

### Inicialização

```bash
cd services/se3-audio-normalization

# Instalar dependências (FFmpeg necessário)
pip install -r requirements.txt

# Verificar FFmpeg
ffmpeg -version

# Iniciar serviço
python run.py
```

## 📡 API Endpoints

### Jobs Principais

#### `POST /jobs`
Cria job de normalização de áudio.

**Request** (multipart/form-data):
```
file: [arquivo_audio.webm]          # Arquivo de áudio
remove_noise: "true"                # Remover ruído
convert_to_mono: "true"             # Converter para mono
apply_highpass_filter: "false"      # Filtro high-pass
set_sample_rate_16k: "true"         # Sample rate 16kHz
isolate_vocals: "false"             # Isolar vocais
```

**Response:**
```json
{
  "id": "norm_abc123def456",
  "status": "queued",
  "progress": 0.0,
  "created_at": "2025-10-29T10:05:00Z",
  "original_filename": "audio_FtnKP8fSSdc.webm",
  "file_size": 15720450,
  "processing_params": {
    "remove_noise": true,
    "convert_to_mono": true,
    "apply_highpass_filter": false,
    "set_sample_rate_16k": true,
    "isolate_vocals": false
  }
}
```

#### `GET /jobs/{job_id}`
Consulta status do job de normalização.

**Response:**
```json
{
  "id": "norm_abc123def456",
  "status": "completed",
  "progress": 100.0,
  "created_at": "2025-10-29T10:05:00Z",
  "updated_at": "2025-10-29T10:06:45Z",
  "completed_at": "2025-10-29T10:06:45Z",
  "original_filename": "audio_FtnKP8fSSdc.webm",
  "processed_filename": "normalized_abc123def456.wav",
  "file_size": 15720450,
  "processed_file_size": 16234567,
  "duration": 180.5,
  "processing_time": 105.2,
  "audio_info": {
    "original": {
      "format": "webm",
      "codec": "opus",
      "sample_rate": 48000,
      "channels": 2,
      "bitrate": "128k"
    },
    "processed": {
      "format": "wav",
      "codec": "pcm_s16le", 
      "sample_rate": 16000,
      "channels": 1,
      "bitrate": "256k"
    }
  },
  "processing_params": {
    "remove_noise": true,
    "convert_to_mono": true,
    "apply_highpass_filter": false,
    "set_sample_rate_16k": true,
    "isolate_vocals": false
  },
  "quality_metrics": {
    "noise_reduction_db": -12.5,
    "volume_normalized": true,
    "peak_amplitude": -3.0,
    "rms_level": -18.2
  }
}
```

#### `GET /jobs/{job_id}/download`
Download do arquivo normalizado.

**Response**: Arquivo binário (WAV) com headers:
```
Content-Type: audio/wav
Content-Disposition: attachment; filename="normalized_abc123def456.wav"
Content-Length: 16234567
```

### Gerenciamento

#### `GET /jobs`
Lista jobs recentes de normalização.

#### `DELETE /jobs/{job_id}`
Remove job e arquivos associados.

### Administração

#### `GET /admin/stats`
Estatísticas do serviço.

**Response:**
```json
{
  "jobs": {
    "total": 125,
    "completed": 120,
    "failed": 3,
    "processing": 2
  },
  "processing": {
    "avg_duration": 95.5,
    "total_processed_mb": 5420.8,
    "cache_hit_rate": 0.15
  },
  "audio_formats": {
    "input": {
      "webm": 80,
      "mp4": 25,
      "wav": 15,
      "m4a": 5
    },
    "output": {
      "wav": 125
    }
  },
  "disk_usage": {
    "temp_dir_mb": 450.2,
    "processed_dir_mb": 1250.8,
    "cache_dir_mb": 890.5
  }
}
```

#### `POST /admin/cleanup`
Limpeza de arquivos temporários e cache.

**Request:**
```json
{
  "deep": false,  // true para limpeza completa
  "max_age_hours": 24
}
```

### Health Check

#### `GET /health`
Verifica saúde do serviço.

**Response:**
```json
{
  "status": "healthy",
  "service": "audio-normalization-service",
  "version": "2.0.0",
  "dependencies": {
    "ffmpeg": "✅ 4.4.2 disponível",
    "redis": "✅ Conectado",
    "disk_space": "✅ 15.2GB livres"
  },
  "performance": {
    "avg_processing_time": 95.5,
    "concurrent_jobs": 2,
    "max_concurrent": 4
  }
}
```

## 🔄 Estados de Job

1. **queued** - Job criado, aguardando processamento
2. **processing** - Normalização em andamento
3. **completed** - Processamento concluído
4. **failed** - Falha no processamento

## 🎛️ Parâmetros de Processamento

### Remove Noise (`remove_noise`)
- **Função**: Remove ruído de fundo usando filtro spectral
- **Algoritmo**: Spectral subtraction + Wiener filter
- **Impacto**: Melhora clareza vocal, pode afetar qualidade se muito agressivo
- **Recomendado**: `true` para gravações com ruído

### Convert to Mono (`convert_to_mono`)
- **Função**: Converte áudio estéreo para mono
- **Algoritmo**: Mix down channels (L+R)/2
- **Impacto**: Reduz tamanho do arquivo pela metade
- **Recomendado**: `true` para speech-to-text

### High-pass Filter (`apply_highpass_filter`)
- **Função**: Remove frequências baixas (<80Hz)
- **Algoritmo**: Butterworth high-pass filter
- **Impacto**: Remove ruídos de baixa frequência (vento, motor)
- **Recomendado**: `true` para gravações ao ar livre

### Sample Rate 16kHz (`set_sample_rate_16k`)
- **Função**: Converte para 16kHz sample rate
- **Algoritmo**: Anti-aliasing + resampling
- **Impacto**: Otimizado para modelos de speech-to-text
- **Recomendado**: `true` para transcrição

### Isolate Vocals (`isolate_vocals`)
- **Função**: Separa voz de música/instrumentos
- **Algoritmo**: Center channel extraction + spectral analysis
- **Impacto**: Melhora transcrição de música com vocal
- **Recomendado**: `true` apenas para música com vocal

## 🎚️ Processamento FFmpeg

### Pipeline de Processamento
```bash
# Exemplo de comando FFmpeg gerado
ffmpeg -i input.webm \
  -af "anlmdn=s=0.002,            # Noise reduction
       pan=mono|c0=0.5*c0+0.5*c1, # Convert to mono
       highpass=f=80,              # High-pass filter
       dynaudnorm"                 # Volume normalization
  -ar 16000                        # Sample rate 16kHz
  -c:a pcm_s16le                   # WAV PCM codec
  output.wav
```

### Filtros Aplicados

1. **Noise Reduction** (`anlmdn`)
   - Adaptive noise reduction
   - Preserva qualidade vocal

2. **Mono Conversion** (`pan`)
   - Mix inteligente dos canais
   - Preserva informação espacial importante

3. **High-pass Filter** (`highpass`)
   - Corte em 80Hz
   - Remove subsônicos indesejados

4. **Dynamic Normalization** (`dynaudnorm`)
   - Normalização adaptativa de volume
   - Mantém dinâmica natural

5. **Vocal Isolation** (quando habilitado)
   - Extração de canal central
   - Atenuação de instrumentos laterais

## 📊 Métricas de Qualidade

### Indicadores Calculados
- **Noise Reduction (dB)**: Redução de ruído em decibéis
- **Peak Amplitude**: Pico máximo após normalização (-3dB target)
- **RMS Level**: Nível médio de energia do sinal
- **Dynamic Range**: Diferença entre pico e RMS
- **THD+N**: Distorção harmônica total + ruído

### Validação de Qualidade
```json
{
  "quality_metrics": {
    "noise_reduction_db": -12.5,     // Ruído removido
    "volume_normalized": true,        // Volume normalizado
    "peak_amplitude": -3.0,          // Pico em dB
    "rms_level": -18.2,              // Energia média
    "dynamic_range": 15.2,           // Faixa dinâmica
    "thd_n_percent": 0.05,           // Distorção total
    "spectral_centroid": 2150.5,     // Centro espectral
    "zero_crossing_rate": 0.12       // Taxa de cruzamento zero
  }
}
```

## 🚨 Troubleshooting

### Job Failed com "FFmpeg Error"
**Causa**: Arquivo corrompido ou formato não suportado
**Solução**: Verificar integridade do arquivo de entrada

### Processamento Muito Lento
**Causa**: Arquivo muito grande ou CPU limitada
**Solução**: Reduzir concorrência ou aumentar recursos

### Qualidade Ruim Após Processamento
**Causa**: Parâmetros muito agressivos
**Solução**: Desabilitar `remove_noise` ou `isolate_vocals`

### "Disk Full" Error  
**Causa**: Espaço insuficiente para arquivos temporários
**Solução**: Executar `POST /admin/cleanup` ou aumentar storage

### Timeout no Processamento
**Causa**: Arquivo muito longo ou processamento complexo
**Solução**: Aumentar `PROCESSING_TIMEOUT_SECONDS`

## 📁 Formatos Suportados

### Input (Entrada)
- **WebM** (Opus, Vorbis)
- **MP4** (AAC, MP3)
- **WAV** (PCM)
- **M4A** (AAC)
- **FLAC** (Lossless)
- **OGG** (Vorbis)

### Output (Saída)
- **WAV** (PCM 16-bit, mono/stereo, 16kHz/44.1kHz)

## 🔧 Configuração Avançada

### Otimizações de Performance
```python
# Concurrent jobs
MAX_CONCURRENT_JOBS = 4

# FFmpeg threads
FFMPEG_THREADS = 2

# Chunk size para streaming
CHUNK_SIZE = 8192
```

### Limites de Recursos
```python
# Tamanho máximo de arquivo
MAX_FILE_SIZE_MB = 200

# Timeout por job
PROCESSING_TIMEOUT_SECONDS = 300

# Memória máxima FFmpeg
FFMPEG_MAX_MEMORY = "512M"
```

## 📂 Estrutura de Arquivos

```
services/se3-audio-normalization/
├── app/
│   ├── main.py           # API endpoints
│   ├── processor.py      # Lógica de processamento
│   ├── models.py         # Modelos de dados
│   ├── redis_store.py    # Interface Redis
│   └── config.py         # Configurações
├── temp/                 # Arquivos temporários
├── processed/            # Arquivos processados
├── logs/                 # Logs do serviço
└── requirements.txt      # Dependências
```

---

**Porta**: 8002 | **Versão**: 2.0.0 | **Tech**: FastAPI + FFmpeg + Redis