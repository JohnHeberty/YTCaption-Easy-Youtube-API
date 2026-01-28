# 🚀 Make-Video Service - Quick Start

## Iniciar em Produção

### Opção 1: Script Automático (Recomendado)
```bash
./start-production.sh
```

### Opção 2: Manual
```bash
# 1. Ativar ambiente
source venv/bin/activate

# 2. Iniciar API
python run.py &

# 3. Iniciar Worker
celery -A app.celery_config worker \
  --loglevel=info \
  --concurrency=1 \
  --queues=make_video_queue \
  --pool=solo &
```

## Testar API

```bash
# Health check
curl http://localhost:8004/health

# Criar vídeo
curl -X POST http://localhost:8004/make-video \
  -F "audio_file=@seu_audio.ogg" \
  -F "query=cats funny" \
  -F "max_shorts=10" \
  -F "subtitle_language=pt"

# Ver status (substitua JOB_ID)
curl http://localhost:8004/jobs/JOB_ID

# Baixar vídeo (quando status=completed)
curl -O http://localhost:8004/download/JOB_ID
```

## Configurações Importantes

Edite `.env`:

```bash
# Legendas palavra por palavra
WORDS_PER_CAPTION=2        # 2 palavras por legenda
SUBTITLE_FONT_SIZE=22      # Tamanho da fonte
SUBTITLE_OUTLINE=2         # Espessura do contorno

# Performance
API_TIMEOUT=120
TRANSCRIBE_MAX_POLLS=240
```

## Monitoramento

```bash
# Ver logs da API
tail -f /tmp/make-video-api.log

# Ver logs do Worker
tail -f /tmp/make-video-worker.log

# Verificar processos
ps aux | grep -E "uvicorn|celery" | grep make
```

## Parar Serviços

```bash
pkill -f "uvicorn.*make-video"
pkill -f "celery.*make_video_queue"
```

---

**Porta:** 8004  
**Redis:** redis://192.168.1.110:6379/0  
**Docs:** http://localhost:8004/docs
