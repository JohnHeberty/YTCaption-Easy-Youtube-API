# Guia de Processamento de Vídeos Longos (1h+)

## 📊 Análise de Vídeos Longos

### Características e Desafios

| Duração | Tamanho Áudio | Tempo Download | Tempo Transcrição (base) | Tempo Transcrição (medium) | Memória RAM |
|---------|---------------|----------------|--------------------------|----------------------------|-------------|
| 10 min  | ~10-20 MB     | 5-15s          | ~2-3 min                 | ~8-12 min                  | ~2 GB       |
| 30 min  | ~30-60 MB     | 15-45s         | ~6-9 min                 | ~25-35 min                 | ~3 GB       |
| 1 hora  | ~60-120 MB    | 30-90s         | ~12-18 min               | ~50-70 min                 | ~4 GB       |
| 2 horas | ~120-240 MB   | 1-3 min        | ~25-35 min               | ~100-140 min               | ~5 GB       |
| 3 horas | ~180-360 MB   | 2-5 min        | ~35-50 min               | ~150-210 min               | ~6 GB       |

### Fatores que Impactam Performance

1. **Modelo Whisper Utilizado**
   - `tiny`: Mais rápido, menos preciso (5-10x mais rápido que base)
   - `base`: Balanceado (tempo de referência)
   - `small`: 2-3x mais lento que base, mais preciso
   - `medium`: 5-7x mais lento que base, muito preciso
   - `large`: 10-15x mais lento que base, máxima precisão

2. **Hardware Disponível**
   - **CPU**: Processamento mais lento
   - **GPU CUDA**: 10-20x mais rápido que CPU
   - **RAM**: Mínimo 4GB, recomendado 8GB+ para vídeos longos

3. **Qualidade do Áudio**
   - Áudio claro: Transcrição mais rápida
   - Áudio com ruído: Processamento mais lento
   - Múltiplos falantes: Pode aumentar o tempo

## 🚀 Configurações Recomendadas por Cenário

### Cenário 1: Velocidade Máxima (Qualidade Aceitável)
**Ideal para**: Legendas rápidas, rascunhos, análise preliminar

```env
WHISPER_MODEL=tiny
WHISPER_DEVICE=cpu
MAX_VIDEO_SIZE_MB=1000
DOWNLOAD_TIMEOUT=600
REQUEST_TIMEOUT=1800  # 30 minutos
```

**Performance esperada (1h de vídeo)**:
- Download: ~60s
- Transcrição: ~5-8 minutos
- Total: ~10 minutos

### Cenário 2: Balanceado (Recomendado)
**Ideal para**: Uso geral, boa relação qualidade/velocidade

```env
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
MAX_VIDEO_SIZE_MB=1000
DOWNLOAD_TIMEOUT=600
REQUEST_TIMEOUT=3600  # 1 hora
```

**Performance esperada (1h de vídeo)**:
- Download: ~60s
- Transcrição: ~12-18 minutos
- Total: ~20 minutos

### Cenário 3: Alta Precisão
**Ideal para**: Transcrições profissionais, documentação oficial

```env
WHISPER_MODEL=medium
WHISPER_DEVICE=cpu
MAX_VIDEO_SIZE_MB=1500
DOWNLOAD_TIMEOUT=900
REQUEST_TIMEOUT=7200  # 2 horas
```

**Performance esperada (1h de vídeo)**:
- Download: ~90s
- Transcrição: ~50-70 minutos
- Total: ~1h15min

### Cenário 4: Máxima Qualidade (Com GPU)
**Ideal para**: Produção, transcrições críticas

```env
WHISPER_MODEL=large
WHISPER_DEVICE=cuda
MAX_VIDEO_SIZE_MB=2000
DOWNLOAD_TIMEOUT=900
REQUEST_TIMEOUT=3600  # 1 hora
```

**Performance esperada (1h de vídeo)**:
- Download: ~90s
- Transcrição: ~5-8 minutos (GPU)
- Total: ~10 minutos

## ⚙️ Configurações Atualizadas para Vídeos Longos

### Arquivo `.env` Otimizado

```env
# ==========================================
# CONFIGURAÇÕES PARA VÍDEOS LONGOS
# ==========================================

# Application
APP_NAME="Whisper Transcription API"
APP_VERSION="1.0.0"
APP_ENVIRONMENT="production"

# Whisper - Escolha baseada no cenário acima
WHISPER_MODEL=base                    # tiny|base|small|medium|large|turbo
WHISPER_DEVICE=cpu                    # cpu|cuda
WHISPER_LANGUAGE=auto

# YouTube - Limites aumentados para vídeos longos
YOUTUBE_FORMAT=worstaudio
MAX_VIDEO_SIZE_MB=1500                # Aumentado de 500 para 1500 MB
DOWNLOAD_TIMEOUT=900                  # 15 minutos (aumentado de 5)

# Storage
TEMP_DIR=/app/temp
CLEANUP_ON_STARTUP=true
CLEANUP_AFTER_PROCESSING=true
MAX_TEMP_AGE_HOURS=24

# API - Timeouts estendidos
MAX_CONCURRENT_REQUESTS=3             # Reduzido para evitar sobrecarga
REQUEST_TIMEOUT=3600                  # 1 hora (aumentado de 10 min)
ENABLE_CORS=true
CORS_ORIGINS=*

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=/app/logs/app.log

# Performance
WORKERS=1
```

### Docker Compose Otimizado

```yaml
version: '3.8'

services:
  whisper-api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: whisper-transcription-api
    ports:
      - "8000:8000"
    environment:
      - WHISPER_MODEL=base
      - WHISPER_DEVICE=cpu
      - TEMP_DIR=/app/temp
      - MAX_VIDEO_SIZE_MB=1500          # Aumentado
      - DOWNLOAD_TIMEOUT=900            # 15 minutos
      - REQUEST_TIMEOUT=3600            # 1 hora
      - MAX_CONCURRENT_REQUESTS=3
      - CLEANUP_ON_STARTUP=true
      - LOG_LEVEL=INFO
    volumes:
      - whisper-cache:/home/appuser/.cache/whisper
      - ./logs:/app/logs
      - ./temp:/app/temp                # Persistir temp se necessário
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '4'                      # Aumentado de 2
          memory: 8G                     # Aumentado de 4G
        reservations:
          cpus: '2'                      # Aumentado de 1
          memory: 4G                     # Aumentado de 2G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 60s                      # Aumentado de 30s
      timeout: 20s                       # Aumentado de 10s
      retries: 3
      start_period: 60s                  # Aumentado de 40s
    networks:
      - whisper-network

volumes:
  whisper-cache:
    driver: local

networks:
  whisper-network:
    driver: bridge
```

## 🔧 Melhorias Implementadas

### 1. Validação de Duração Antes do Download

A API agora verifica a duração do vídeo antes de processar:

```python
# Obter informações do vídeo primeiro
video_info = await downloader.get_video_info(youtube_url)

# Validar duração
max_duration = 10800  # 3 horas em segundos
if video_info['duration'] > max_duration:
    raise VideoDownloadError(
        f"Video too long: {video_info['duration']}s "
        f"(max: {max_duration}s)"
    )
```

### 2. Progress Logging para Vídeos Longos

Logs detalhados mostram o progresso:

```python
logger.info(f"Video duration: {duration}s (~{duration//60} minutes)")
logger.info(f"Estimated processing time: {estimated_time}s")
logger.info(f"Download progress: {progress}%")
```

### 3. Timeouts Configuráveis

Todos os timeouts são configuráveis via variáveis de ambiente:

- `DOWNLOAD_TIMEOUT`: Timeout do download
- `REQUEST_TIMEOUT`: Timeout da requisição HTTP
- `TRANSCRIPTION_TIMEOUT`: Timeout específico da transcrição

### 4. Limite de Requisições Concorrentes

Para evitar sobrecarga com múltiplos vídeos longos:

```python
MAX_CONCURRENT_REQUESTS=3  # Máximo de 3 transcrições simultâneas
```

## 📈 Monitoramento e Logs

### Logs Importantes para Vídeos Longos

```log
2025-10-18 22:30:00 | INFO | Video duration: 3600s (~60 minutes)
2025-10-18 22:30:00 | INFO | Estimated processing time: 1200s (~20 minutes)
2025-10-18 22:30:15 | INFO | Download progress: 25%
2025-10-18 22:30:30 | INFO | Download progress: 50%
2025-10-18 22:30:45 | INFO | Download completed: 125.5 MB
2025-10-18 22:30:46 | INFO | Loading Whisper model: base
2025-10-18 22:31:00 | INFO | Model loaded successfully
2025-10-18 22:31:00 | INFO | Starting transcription
2025-10-18 22:35:00 | INFO | Transcription progress: 25%
2025-10-18 22:39:00 | INFO | Transcription progress: 50%
2025-10-18 22:43:00 | INFO | Transcription progress: 75%
2025-10-18 22:47:00 | INFO | Transcription completed: 150 segments
2025-10-18 22:47:01 | INFO | Cleanup completed
```

### Endpoint de Status (Planejado)

```http
GET /api/v1/transcribe/{transcription_id}/status

Response:
{
  "transcription_id": "uuid",
  "status": "processing",
  "progress": 45,
  "stage": "transcription",
  "estimated_time_remaining": 600,
  "started_at": "2025-10-18T22:30:00Z"
}
```

## ⚠️ Limitações e Considerações

### Limitações Atuais

1. **Processamento Síncrono**: 
   - A requisição fica bloqueada até terminar
   - Para vídeos muito longos (2h+), considere implementar processamento assíncrono

2. **Sem Cancelamento**:
   - Não é possível cancelar uma transcrição em andamento
   - Planejado para versões futuras

3. **Sem Fila**:
   - Múltiplas requisições concorrentes competem por recursos
   - Recomendado: máximo 2-3 transcrições simultâneas

### Soluções Recomendadas para Produção

#### Para Vídeos Muito Longos (2h+)

**Opção 1: Processamento Assíncrono com Celery**
```python
# Adicionar à aplicação:
# - Celery + Redis para fila de tarefas
# - Endpoint para submeter job
# - Endpoint para verificar status
# - Webhook/notificação quando concluir
```

**Opção 2: Processamento em Chunks**
```python
# Dividir vídeo em partes de 15-30 minutos
# Processar cada parte independentemente
# Combinar resultados no final
```

**Opção 3: Stream/Websocket para Progresso**
```python
# Usar WebSocket para enviar atualizações em tempo real
# Cliente recebe progresso enquanto processa
```

## 🎯 Exemplos de Uso

### Exemplo 1: Transcrever Vídeo de 1 Hora

```bash
curl -X POST http://localhost:8000/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "language": "auto",
    "model": "base"
  }'
```

**Resposta esperada**:
```json
{
  "transcription_id": "uuid",
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "video_id": "VIDEO_ID",
  "language": "en",
  "full_text": "...",
  "segments": [...],
  "total_segments": 240,
  "duration": 3600.0,
  "processing_time": 1200.5
}
```

### Exemplo 2: Verificar Duração Antes

```bash
# Primeiro, obter informações do vídeo
curl -X POST http://localhost:8000/api/v1/video/info \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID"
  }'
```

**Resposta**:
```json
{
  "video_id": "VIDEO_ID",
  "title": "Video Title",
  "duration": 3600,
  "duration_formatted": "1:00:00",
  "estimated_processing_time": 1200,
  "estimated_processing_formatted": "20:00"
}
```

## 📊 Tabela de Decisão

Use esta tabela para escolher a melhor configuração:

| Duração do Vídeo | Modelo Recomendado | Device | Timeout Mínimo | Memória Mínima | Tempo Estimado |
|------------------|-------------------|--------|----------------|----------------|----------------|
| < 10 min         | base              | CPU    | 600s           | 2 GB           | 2-3 min        |
| 10-30 min        | base              | CPU    | 1200s          | 3 GB           | 6-9 min        |
| 30-60 min        | base              | CPU    | 2400s          | 4 GB           | 12-18 min      |
| 1-2 horas        | base              | CPU    | 3600s          | 5 GB           | 25-35 min      |
| 2-3 horas        | tiny/base         | CPU    | 5400s          | 6 GB           | 35-50 min      |
| > 3 horas        | tiny              | CPU    | 7200s          | 8 GB           | 60-90 min      |
| Qualquer (GPU)   | medium/large      | CUDA   | 1800s          | 8 GB           | 5-15 min       |

## 🚀 Próximas Melhorias Planejadas

1. **✅ Validação de duração pré-download** (Implementado)
2. **✅ Timeouts configuráveis** (Implementado)
3. **✅ Logs de progresso** (Implementado)
4. **🔄 Processamento assíncrono com Celery** (Planejado)
5. **🔄 Endpoint de status/progresso** (Planejado)
6. **🔄 Processamento em chunks** (Planejado)
7. **🔄 Cancelamento de transcrições** (Planejado)
8. **🔄 Fila de prioridade** (Planejado)
9. **🔄 Cache de transcrições** (Planejado)
10. **🔄 Suporte a GPU** (Documentado, requer hardware)

## 💡 Dicas de Otimização

### Para CPU
1. Use modelo `tiny` ou `base` para vídeos longos
2. Limite requisições concorrentes a 2-3
3. Aumente a RAM disponível para o container
4. Use SSD para armazenamento temporário

### Para GPU (NVIDIA)
1. Instale drivers CUDA no host
2. Configure Docker para usar GPU:
   ```yaml
   deploy:
     resources:
       reservations:
         devices:
           - driver: nvidia
             count: 1
             capabilities: [gpu]
   ```
3. Use modelos maiores (medium/large)
4. Processe múltiplos vídeos em paralelo

### Geral
1. Monitore uso de recursos (CPU, RAM, disco)
2. Configure cleanup automático
3. Use cache do Whisper (volume persistente)
4. Implemente logs estruturados
5. Configure alertas para falhas

## 🎬 Conclusão

A API está preparada para processar vídeos de até **3 horas** com as configurações adequadas. Para vídeos mais longos ou processamento em larga escala, considere implementar:

- ✅ Processamento assíncrono (Celery + Redis)
- ✅ Fila de tarefas
- ✅ Cache de resultados
- ✅ Distribuição de carga
- ✅ GPU para aceleração

**Configuração Recomendada para Produção** (vídeos até 2h):
- Modelo: `base`
- Device: `cpu` (ou `cuda` se disponível)
- Timeout: 3600s (1 hora)
- Max Size: 1500 MB
- Memória: 8 GB
- CPU: 4 cores
