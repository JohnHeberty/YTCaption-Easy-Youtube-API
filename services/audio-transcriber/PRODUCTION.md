# Audio-Transcriber Service - Guia de Produção

## 📋 Índice
- [Visão Geral](#visão-geral)
- [Requisitos](#requisitos)
- [Deploy Rápido](#deploy-rápido)
- [Configuração](#configuração)
- [Monitoramento](#monitoramento)
- [Manutenção](#manutenção)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Visão Geral

Serviço de transcrição de áudio usando **Faster-Whisper** com suporte a CPU e GPU.

### Melhorias vs OpenAI-Whisper
- ✅ **4x mais rápido** que openai-whisper
- ✅ **Word-level timestamps nativos** (sincronização perfeita)
- ✅ **Menos uso de memória** (~40% redução)
- ✅ **Build limpo** (sem problemas de pkg_resources)
- ✅ **CPU otimizado** com compute_type=int8

### Stack
- **API**: FastAPI + Uvicorn
- **Transcrição**: Faster-Whisper (CTranslate2)
- **Queue**: Celery + Redis
- **Containers**: Docker + Docker Compose

---

## 📦 Requisitos

### Mínimos (CPU)
- **CPU**: 4 cores
- **RAM**: 6 GB
- **Disco**: 20 GB (10 GB para modelo large)
- **OS**: Linux (Ubuntu 20.04+, Debian 11+)

### Recomendados (GPU)
- **GPU**: NVIDIA com 4+ GB VRAM
- **CUDA**: 11.8+
- **Driver**: 550+
- **RAM**: 8 GB

### Software
```bash
# Docker
docker --version  # >= 24.0
docker compose version  # >= 2.20

# Python (apenas para dev local)
python3 --version  # >= 3.11
```

---

## 🚀 Deploy Rápido

### 1. Clone e Configure
```bash
cd services/audio-transcriber

# Copiar .env de exemplo
cp .env.example .env

# Editar configurações
nano .env
```

### 2. Configurações Essenciais (.env)
```bash
# Redis (OBRIGATÓRIO)
REDIS_URL=redis://localhost:6379/0

# Modelo Whisper
WHISPER_MODEL=base  # tiny|base|small|medium|large
WHISPER_DEVICE=cpu  # cpu|cuda

# Porta
PORT=8003
```

### 3. Deploy
```bash
# Usando Makefile (recomendado)
make prod-up

# OU usando script
./scripts/deploy-prod.sh

# OU manualmente
docker compose -f docker-compose.prod.yml up -d
```

### 4. Verificar
```bash
# Health check
make api-health

# OU
curl http://localhost:8003/health

# Logs
make prod-logs
```

---

## ⚙️ Configuração

### Modelos Disponíveis

| Modelo  | VRAM  | Velocidade | Qualidade | Recomendado Para |
|---------|-------|------------|-----------|------------------|
| tiny    | ~1GB  | ~32x       | ⭐⭐      | Testes rápidos   |
| base    | ~1GB  | ~16x       | ⭐⭐⭐    | **Produção CPU** |
| small   | ~2GB  | ~6x        | ⭐⭐⭐⭐  | GPU pequena      |
| medium  | ~5GB  | ~2x        | ⭐⭐⭐⭐⭐ | GPU média        |
| large   | ~10GB | ~1x        | ⭐⭐⭐⭐⭐⭐| GPU grande       |

### Variáveis Importantes

```bash
# === PERFORMANCE ===
CELERY_CONCURRENCY=2          # Workers paralelos
CELERY_REPLICAS=1             # Containers do Celery
WHISPER_PRELOAD_MODEL=true    # Carregar modelo no startup

# === LIMITES ===
MAX_FILE_SIZE_MB=500          # Tamanho máximo de áudio
CELERY_TASK_TIME_LIMIT=3600   # Timeout de transcrição (segundos)

# === CACHE ===
JOB_CACHE_TTL=24              # Cache de resultados (horas)
TRANSCRIPTION_RETENTION_DAYS=30  # Retenção de arquivos

# === SEGURANÇA ===
API_KEY=your-secret-key       # Autenticação (opcional)
CORS_ORIGINS=*                # CORS permitidos
```

### Otimizações CPU

```bash
# .env para produção CPU
WHISPER_DEVICE=cpu
WHISPER_MODEL=base
CELERY_CONCURRENCY=2
WORKERS=2

# Compute type (int8 = mais rápido, menos memória)
# Faster-Whisper automaticamente usa int8 em CPU
```

### Otimizações GPU

```bash
# .env para produção GPU
WHISPER_DEVICE=cuda
WHISPER_MODEL=medium
CELERY_CONCURRENCY=1  # GPU não precisa muita concorrência
NVIDIA_VISIBLE_DEVICES=all

# Usar docker-compose.yml original (não .prod.yml)
```

---

## 📊 Monitoramento

### Health Checks

```bash
# Health check completo
./scripts/health-check.sh

# OU usando Makefile
make diagnose

# Check individual
curl http://localhost:8003/health | jq
```

### Logs

```bash
# Todos os logs
make prod-logs

# Logs específicos
docker compose -f docker-compose.prod.yml logs -f audio-transcriber-service
docker compose -f docker-compose.prod.yml logs -f celery-worker

# Últimas 500 linhas
docker compose -f docker-compose.prod.yml logs --tail=500
```

### Métricas

```bash
# Status dos containers
make ps

# Uso de recursos
docker stats

# Jobs recentes
curl http://localhost:8003/jobs | jq
```

---

## 🔧 Manutenção

### Limpeza Regular

```bash
# Limpar uploads antigos (>7 dias)
make clean-uploads

# Limpar transcrições antigas (>30 dias)
make clean-transcriptions

# Limpar cache Docker
docker system prune -f
```

### Backup

```bash
# Backup de configurações
tar -czf backup-$(date +%Y%m%d).tar.gz \
    .env \
    models/ \
    transcriptions/ \
    logs/

# Backup de modelos (grande!)
tar -czf backup-models-$(date +%Y%m%d).tar.gz models/
```

### Atualização

```bash
# 1. Backup atual
docker tag audio-transcriber:production audio-transcriber:backup

# 2. Pull novo código
git pull origin main

# 3. Build nova versão
make prod-build

# 4. Deploy
make prod-up

# 5. Se der problema, rollback:
./scripts/rollback.sh
```

### Restart

```bash
# Restart completo
make restart

# Restart apenas Celery
docker compose -f docker-compose.prod.yml restart celery-worker

# Restart sem downtime (scale)
docker compose -f docker-compose.prod.yml up -d --scale celery-worker=2
sleep 30
docker compose -f docker-compose.prod.yml up -d --scale celery-worker=1
```

---

## 🔍 Troubleshooting

### Problema: API não responde

```bash
# 1. Verificar logs
docker compose -f docker-compose.prod.yml logs audio-transcriber-service

# 2. Verificar porta
netstat -tulpn | grep 8003

# 3. Verificar healthcheck
docker inspect audio-transcriber-api | grep -A 10 Health

# 4. Restart
docker compose -f docker-compose.prod.yml restart audio-transcriber-service
```

### Problema: Celery não processa jobs

```bash
# 1. Verificar worker
docker exec audio-transcriber-celery python -c \
    "from app.celery_config import celery_app; \
     i = celery_app.control.inspect(); \
     print(i.stats())"

# 2. Verificar Redis
docker exec audio-transcriber-celery python -c \
    "import redis; r = redis.from_url('redis://localhost:6379/0'); r.ping()"

# 3. Limpar fila
docker exec audio-transcriber-celery python -c \
    "from app.celery_config import celery_app; \
     celery_app.control.purge()"

# 4. Restart Celery
docker compose -f docker-compose.prod.yml restart celery-worker
```

### Problema: Modelo não carrega

```bash
# 1. Verificar espaço em disco
df -h

# 2. Baixar modelo manualmente
make model-download WHISPER_MODEL=base

# 3. Verificar permissões
ls -la models/

# 4. Logs de carregamento
docker compose -f docker-compose.prod.yml logs | grep "Carregando modelo"
```

### Problema: Transcrição muito lenta

```bash
# 1. Verificar CPU/RAM
docker stats audio-transcriber-celery

# 2. Reduzir concorrência
# Em .env: CELERY_CONCURRENCY=1

# 3. Usar modelo menor
# Em .env: WHISPER_MODEL=tiny

# 4. Habilitar chunking para áudios longos
# Em .env: ENABLE_CHUNKING=true
```

### Problema: Out of Memory

```bash
# 1. Verificar uso de memória
docker stats

# 2. Aumentar limite no docker-compose.prod.yml
# deploy.resources.limits.memory: 8G

# 3. Reduzir concorrência
# CELERY_CONCURRENCY=1

# 4. Usar modelo menor
# WHISPER_MODEL=base (ao invés de medium/large)

# 5. Restart com limpeza
docker compose -f docker-compose.prod.yml down
docker system prune -f
make prod-up
```

---

## 📚 Comandos Úteis (Makefile)

```bash
# Deploy
make prod-up          # Deploy em produção
make prod-build       # Build otimizado
make prod-status      # Status de produção
make prod-logs        # Logs de produção

# Desenvolvimento
make install          # Instalar dependências locais
make dev              # Rodar localmente (sem Docker)
make test-prod        # Testar com TEST-.ogg

# Modelos
make model-download   # Baixar modelo Whisper
make model-test       # Testar modelo
make model-info       # Info dos modelos

# API
make api-health       # Health check
make api-transcribe   # Transcrever áudio de teste
make api-jobs         # Listar jobs

# Manutenção
make clean            # Limpar cache
make clean-all        # Limpeza completa
make validate         # Validar configurações
make diagnose         # Diagnóstico completo

# Docker
make build            # Build imagens
make up               # Subir serviços
make down             # Parar serviços
make restart          # Reiniciar
make logs             # Ver logs
make ps               # Status containers
```

---

## 🆘 Suporte

- **Issues**: [GitHub Issues](https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/issues)
- **Docs**: [services/audio-transcriber/docs/](./docs/)
- **Logs**: `docker compose -f docker-compose.prod.yml logs`

---

## 📝 Checklist de Deploy

- [ ] Configurar `.env` com valores corretos
- [ ] Redis rodando e acessível
- [ ] Portas disponíveis (8003)
- [ ] Espaço em disco suficiente (20+ GB)
- [ ] Rede Docker criada (`ytcaption_network`)
- [ ] Build sem erros
- [ ] Health check passa
- [ ] Celery worker ativo
- [ ] Teste de transcrição funciona
- [ ] Logs sem erros críticos
- [ ] Backup configurado

---

**Versão**: 2.0.0 (Faster-Whisper)  
**Última atualização**: 2026-02-21
