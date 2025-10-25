# YTCaption - Easy YouTube API

Sistema de microserviços para download de vídeos, normalização de áudio e transcrição automática.

## 🚀 Serviços

### 📹 Video Downloader (porta 8000)
- Download de vídeos do YouTube
- Cache inteligente de 24h
- Gerenciamento de User-Agents
- Rate limiting e validação de URLs

### 🎵 Audio Normalization (porta 8001)
- Normalização de áudio com FFmpeg
- Redução de ruído
- Processamento assíncrono com Celery
- Cache de resultados

### 📝 Audio Transcriber (porta 8002)
- Transcrição de áudio usando Whisper
- Suporte a múltiplos idiomas
- Formatos de saída: SRT, VTT, TXT
- Processamento em batch

## 🛠️ Tecnologias

- **FastAPI** - API REST moderna e rápida
- **Celery** - Processamento assíncrono de tarefas
- **Redis** - Cache e message broker (192.168.18.110:6379)
- **Docker** - Containerização dos serviços
- **FFmpeg** - Processamento de áudio/vídeo
- **Whisper** - Transcrição de áudio
- **yt-dlp** - Download de vídeos

## 🔧 Setup e Execução

### Pré-requisitos
- Docker e Docker Compose
- Redis rodando em 192.168.18.110:6379
- 8GB+ RAM (recomendado para Whisper)
- 10GB+ espaço livre

### Execução Rápida

```bash
# Clone o repositório
git clone <repository-url>
cd YTCaption-Easy-Youtube-API

# Crie a rede Docker
docker network create ytcaption-network

# Inicie todos os serviços
docker-compose up -d

# Verifique os logs
docker-compose logs -f
```

### Execução Individual dos Serviços

```bash
# Video Downloader
cd services/video-downloader
docker-compose up -d

# Audio Normalization
cd services/audio-normalization
docker-compose up -d

# Audio Transcriber
cd services/audio-transcriber
docker-compose up -d
```

## 📊 Endpoints Administrativos

Todos os serviços possuem os seguintes endpoints administrativos:

### Health Checks
- `GET /health` - Status básico do serviço
- `GET /health/detailed` - Status detalhado com dependências

### Administração
- `POST /admin/cleanup` - Limpeza manual de arquivos expirados
- `DELETE /admin/cache` - Limpa todo o cache (⚠️ CUIDADO)
- `GET /admin/stats` - Estatísticas do sistema
- `GET /admin/queue` - Status da fila Celery

### Monitoramento
- `GET /metrics` - Métricas Prometheus
- `GET /jobs` - Lista todos os jobs
- `GET /jobs/{id}` - Detalhes de um job específico

## 🔒 Configurações de Segurança

### Rate Limiting
- Video Downloader: 100 req/min
- Audio Normalization: 100 req/min
- Audio Transcriber: 50 req/min

### Validações
- Tamanho máximo de arquivo: 200MB (transcriber), 100MB (normalization)
- Extensões permitidas: .mp4, .mp3, .wav, .flac, .ogg, .m4a
- Timeout de processamento: 30-60 minutos por job
- Validação de URLs e domínios bloqueados

## 🏗️ Arquitetura

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Video Downloader│    │Audio Normalization│   │Audio Transcriber│
│     :8000       │    │     :8001        │    │     :8002       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Redis Cache   │
                    │ 192.168.18.110  │
                    │     :6379       │
                    └─────────────────┘
```

## 🔄 Resiliência e Recuperação

### Circuit Breakers
- Threshold: 5 falhas consecutivas
- Timeout: 60 segundos
- Recovery: 3 sucessos para fechar

### Retry Policies
- Máximo 3 tentativas
- Backoff exponencial (2x)
- Delay inicial: 1s, máximo: 60s

### Resource Management
- Semáforos para controle de concorrência
- Monitoramento de CPU/memória
- Cleanup automático de recursos

## 📝 Exemplos de Uso

### Download de Vídeo
```bash
curl -X POST "http://localhost:8000/download" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=VIDEO_ID"}'
```

### Normalização de Áudio
```bash
curl -X POST "http://localhost:8001/normalize" \
  -F "file=@audio.mp3"
```

### Transcrição de Áudio
```bash
curl -X POST "http://localhost:8002/transcribe" \
  -F "file=@audio.wav" \
  -F "language=pt" \
  -F "output_format=srt"
```

## 🐛 Troubleshooting

### Problemas Comuns

1. **Redis Connection Failed**
   ```bash
   # Verifique se o Redis está rodando
   redis-cli -h 192.168.18.110 ping
   ```

2. **Port Already in Use**
   ```bash
   # Mude as portas no docker-compose.yml
   ports:
     - "8001:8001"  # altere a primeira porta
   ```

3. **Out of Memory (Whisper)**
   ```bash
   # Use modelo menor no .env
   WHISPER_MODEL=tiny  # ou base, small
   ```

4. **File Not Found Errors**
   ```bash
   # Crie os diretórios necessários
   mkdir -p uploads processed temp logs cache transcriptions models
   ```

### Logs Úteis
```bash
# Logs de todos os serviços
docker-compose logs -f

# Logs de um serviço específico
docker-compose logs -f video-downloader

# Logs do Celery
docker-compose logs -f audio-normalization-celery
```

## 🔧 Desenvolvimento

### Variáveis de Ambiente

Cada serviço tem um arquivo `.env` com configurações. Principais variáveis:

```env
# Redis
REDIS_URL=redis://192.168.18.110:6379/0

# Cache
CACHE_TTL_HOURS=24
CLEANUP_INTERVAL_MINUTES=30

# Processing
MAX_CONCURRENT_JOBS=3
JOB_TIMEOUT_MINUTES=30

# Security
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Hot Reload

Durante desenvolvimento, os volumes estão configurados para hot reload:

```yaml
volumes:
  - ./app:/app/app  # Código da aplicação
  - ./logs:/app/logs  # Logs persistentes
```

## 📊 Monitoramento

### Métricas Disponíveis
- Requests por segundo
- Latência P95/P99
- Taxa de erro
- Jobs processados
- Uso de recursos

### Endpoints de Status
- `/health` - Status básico
- `/metrics` - Métricas Prometheus
- `/admin/stats` - Estatísticas detalhadas

## 🤝 Contribuição

1. Fork o repositório
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## 🆘 Suporte

Para suporte, abra uma issue no GitHub ou entre em contato:

- 📧 Email: [seu-email@exemplo.com](mailto:seu-email@exemplo.com)
- 💬 Discord: [Link do Discord](https://discord.gg/seu-servidor)
- 📖 Wiki: [Link da Wiki](https://github.com/seu-usuario/ytcaption/wiki)