# 🚀 GUIA RÁPIDO DE DEPLOY - YTCaption Easy Youtube API

## 📋 Pré-requisitos

- Docker e Docker Compose instalados
- Redis disponível (local ou remoto)
- Portas 8000, 8001, 8002 disponíveis
- Python 3.11+ (para testes locais)

---

## ⚡ Deploy Rápido (5 minutos)

### 1. Configure os arquivos .env

```bash
# Audio Normalization
cd services/audio-normalization
cp .env.example .env
# Edite REDIS_URL com seu IP Redis

# Audio Transcriber
cd ../audio-transcriber
cp .env.example .env
# Edite REDIS_URL com seu IP Redis

# Video Downloader
cd ../video-downloader
cp .env.example .env
# Edite REDIS_URL com seu IP Redis
```

### 2. Inicie os serviços

```bash
# Audio Normalization (Porta 8001)
cd services/audio-normalization
docker compose up -d

# Audio Transcriber (Porta 8002)
cd ../audio-transcriber
docker compose up -d

# Video Downloader (Porta 8000)
cd ../video-downloader
docker compose up -d
```

### 3. Verifique a saúde

```bash
curl http://localhost:8000/health  # Video Downloader
curl http://localhost:8001/health  # Audio Normalization
curl http://localhost:8002/health  # Audio Transcriber
```

**✅ Se todos retornarem `{"status":"healthy"}`, o sistema está pronto!**

---

## 🧪 Testando os Endpoints

### Video Downloader (8000)

```bash
# Criar job de download
curl -X POST "http://localhost:8000/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "quality": "720p"
  }'

# Verificar status
curl "http://localhost:8000/jobs/{job_id}"

# Download do arquivo
curl "http://localhost:8000/jobs/{job_id}/download" -o video.mp4
```

### Audio Normalization (8001)

```bash
# Upload e normalizar áudio
curl -X POST "http://localhost:8001/normalize" \
  -F "file=@audio.mp3" \
  -F "normalize_volume=true" \
  -F "remove_noise=true"

# Verificar status
curl "http://localhost:8001/jobs/{job_id}"

# Download do áudio processado
curl "http://localhost:8001/jobs/{job_id}/download" -o normalized.opus
```

### Audio Transcriber (8002)

```bash
# Upload e transcrever
curl -X POST "http://localhost:8002/transcribe" \
  -F "file=@audio.mp3"

# Verificar status
curl "http://localhost:8002/jobs/{job_id}"

# Obter transcrição
curl "http://localhost:8002/jobs/{job_id}/result"
```

---

## 📊 Monitoramento

### Logs em Tempo Real

```bash
# Ver logs de um serviço
docker logs -f audio-normalization-api
docker logs -f audio-normalization-celery

# Ver todos os containers
docker ps

# Ver uso de recursos
docker stats
```

### Métricas Prometheus

```bash
# Audio Normalization
curl http://localhost:9090/metrics

# Audio Transcriber
curl http://localhost:9091/metrics

# Video Downloader
curl http://localhost:9092/metrics
```

---

## 🛠️ Comandos Úteis

### Reiniciar Serviço

```bash
cd services/audio-normalization
docker compose restart
```

### Rebuild Completo

```bash
cd services/audio-normalization
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Ver Logs de Erro

```bash
docker logs audio-normalization-api 2>&1 | grep ERROR
```

### Limpar Cache

```bash
# Limpar cache Redis
redis-cli -h 192.168.18.110 FLUSHDB

# OU via API
curl -X DELETE "http://localhost:8001/admin/cache"
```

---

## 🔧 Troubleshooting

### Serviço não inicia

```bash
# Verificar logs
docker logs audio-normalization-api

# Verificar configuração
docker compose config

# Verificar portas em uso
netstat -an | grep 8001
```

### Redis não conecta

```bash
# Testar conexão Redis
redis-cli -h 192.168.18.110 ping

# Verificar .env
cat .env | grep REDIS_URL
```

### Worker Celery não processa

```bash
# Verificar se worker está rodando
docker ps | grep celery

# Ver logs do worker
docker logs audio-normalization-celery

# Reiniciar worker
docker restart audio-normalization-celery
```

---

## 📁 Estrutura de Diretórios

```
services/
├── audio-normalization/
│   ├── uploads/      # Arquivos enviados
│   ├── processed/    # Arquivos processados
│   ├── temp/         # Arquivos temporários
│   └── logs/         # Logs da aplicação
│
├── audio-transcriber/
│   ├── uploads/      # Arquivos de áudio
│   ├── transcriptions/  # Transcrições geradas
│   ├── models/       # Modelos Whisper
│   └── logs/         # Logs da aplicação
│
└── video-downloader/
    ├── cache/        # Vídeos baixados
    └── logs/         # Logs da aplicação
```

---

## 🔐 Segurança

### Alterar Permissões (se necessário)

```bash
# Dar permissão para diretórios
chmod 755 services/audio-normalization/uploads
chmod 755 services/audio-normalization/processed

# Ou todos de uma vez
find services -type d -name "uploads" -exec chmod 755 {} \;
find services -type d -name "processed" -exec chmod 755 {} \;
```

### Configurar Firewall (Proxmox)

```bash
# Permitir portas dos serviços
ufw allow 8000/tcp
ufw allow 8001/tcp
ufw allow 8002/tcp
```

---

## 📈 Otimizações de Performance

### Ajustar Workers

Edite `.env` de cada serviço:

```bash
# Para servidores mais potentes
WORKERS=4
PROCESSING__MAX_CONCURRENT_JOBS=5

# Para limitar recursos
WORKERS=1
PROCESSING__MAX_CONCURRENT_JOBS=2
```

### Ajustar Cache

```bash
# Cache maior (mais espaço, menos processamento)
CACHE__TTL_HOURS=168  # 7 dias
CACHE__MAX_CACHE_SIZE_GB=50

# Cache menor (menos espaço, mais processamento)
CACHE__TTL_HOURS=12
CACHE__MAX_CACHE_SIZE_GB=5
```

---

## 🆘 Suporte e Documentação

### Documentação Completa

- `CORRECOES_REALIZADAS.md` - Todas as correções implementadas
- `services/*/README.md` - Documentação específica de cada serviço
- `.env.example` - Todas as variáveis de ambiente disponíveis

### Comandos de Diagnóstico

```bash
# Status geral do sistema
docker ps
docker stats

# Informações detalhadas de um serviço
docker inspect audio-normalization-api

# Estatísticas da API
curl http://localhost:8001/admin/stats
curl http://localhost:8001/admin/queue
```

---

## ✅ Checklist de Deploy

- [ ] Redis configurado e acessível
- [ ] Arquivos `.env` criados e configurados
- [ ] Portas 8000-8002 disponíveis
- [ ] Diretórios com permissões corretas
- [ ] Docker e Docker Compose instalados
- [ ] Serviços iniciados com `docker compose up -d`
- [ ] Health checks retornando OK
- [ ] Testes básicos realizados
- [ ] Logs sendo gerados corretamente
- [ ] Workers Celery processando jobs

---

**🎉 Pronto! Seu sistema está rodando!**

Para mais informações, consulte `CORRECOES_REALIZADAS.md`
