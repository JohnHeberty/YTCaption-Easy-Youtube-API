# YTCaption API - Portas dos Serviços

## 📋 Relatório de Portas

| Serviço | Porta | Container | Status |
|---------|-------|-----------|--------|
| **youtube-search** | 8001 | youtube-search-api | ✅ Healthy |
| **video-downloader** | 8002 | ytcaption-video-downloader | ✅ Healthy |
| **audio-normalization** | 8003 | ytcaption-audio-normalization | ✅ Healthy |
| **audio-transcriber** | 8004 | ytcaption-audio-transcriber | ✅ Healthy |
| **make-video** | 8005 | ytcaption-make-video | ✅ Healthy |

---

## 🔗 Endpoints de Health Check

```
http://<host>:8001/health  → youtube-search
http://<host>:8002/health  → video-downloader
http://<host>:8003/health  → audio-normalization
http://<host>:8004/health  → audio-transcriber
http://<host>:8005/health  → make-video
```

---

## 🌐 Configuração DNS

Aponte seus domínios/subdomínios para as respectivas portas:

| Serviço | Porta | Descrição |
|---------|-------|-----------|
| youtube-search | 8001 | Busca de vídeos no YouTube |
| video-downloader | 8002 | Download de vídeos |
| audio-normalization | 8003 | Normalização de áudio |
| audio-transcriber | 8004 | Transcrição de áudio |
| make-video | 8005 | Composição de vídeos |

---

## 📊 Status dos Workers Celery

| Worker | Container | Status |
|--------|-----------|--------|
| youtube-search-celery | youtube-search-celery-worker | ✅ Healthy |
| youtube-search-celery-beat | youtube-search-celery-beat | ✅ Healthy |
| video-downloader-celery | ytcaption-video-downloader-celery | ✅ Healthy |
| audio-normalization-celery | ytcaption-audio-normalization-celery | 🔄 Restarting |
| audio-transcriber-celery | ytcaption-audio-transcriber-celery | ✅ Healthy |
| make-video-celery | ytcaption-make-video-celery | ✅ Healthy |
| make-video-celery-beat | ytcaption-make-video-celery-beat | ✅ Healthy |

---

## 🔧 Comandos Úteis

```bash
# Ver status de todos os containers
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Ver logs de um serviço específico
docker logs -f ytcaption-video-downloader
docker logs -f youtube-search-api
docker logs -f ytcaption-make-video

# Restart de um serviço
cd /root/YTCaption-Easy-Youtube-API/services/<service>
docker compose restart
```

---

**Data de geração:** 2025-04-29
**Versão:** 1.0
