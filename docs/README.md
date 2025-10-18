# 📚 YTCaption - Documentação Completa

## � Arquivos da Documentação

- **[README.md](README.md)** - Documentação completa (este arquivo)
- **[EXAMPLES.md](EXAMPLES.md)** - Exemplos práticos (Python, JS, cURL, batch)
- **[CHANGELOG.md](CHANGELOG.md)** - Histórico de versões e melhorias
- **[STARTUP_SCRIPTS.md](STARTUP_SCRIPTS.md)** - Scripts de inicialização

---

## �🚀 Início Rápido

### Instalação Local

```bash
# 1. Clone e configure
cp .env.example .env

# 2. Instale dependências
pip install -r requirements.txt

# 3. Execute
uvicorn src.main:app --reload
```

### Docker (Recomendado)

```bash
# 1. Configure
cp .env.example .env

# 2. Suba o container
docker-compose up -d

# 3. Aguarde inicialização (~30s)
docker-compose logs -f

# 4. Teste
curl http://localhost:8000/health
```

---

## 📖 API Endpoints

### 1. Health Check
```bash
GET /health
```

### 2. Informações do Vídeo
```bash
POST /api/v1/video/info
{
  "youtube_url": "https://youtube.com/watch?v=..."
}
```

**Resposta:**
- Duração, título, uploader
- **Idioma detectado** com confiança
- **Legendas disponíveis** (manuais e automáticas)
- Recomendações de modelo Whisper
- Avisos e estimativas de tempo

### 3. Transcrição

#### Usando Whisper (mais preciso)
```bash
POST /api/v1/transcribe
{
  "youtube_url": "https://youtube.com/watch?v=...",
  "language": "auto",
  "use_youtube_transcript": false
}
```

#### Usando Legendas do YouTube (mais rápido)
```bash
POST /api/v1/transcribe
{
  "youtube_url": "https://youtube.com/watch?v=...",
  "language": "pt",
  "use_youtube_transcript": true,
  "prefer_manual_subtitles": true
}
```

**Resposta:**
```json
{
  "transcription_id": "uuid",
  "video_id": "dQw4w9WgXcQ",
  "language": "en",
  "full_text": "Texto completo...",
  "segments": [
    {
      "text": "Texto do segmento",
      "start": 0.0,
      "end": 2.5,
      "duration": 2.5
    }
  ],
  "total_segments": 150,
  "duration": 210.5,
  "processing_time": 45.2,
  "source": "whisper",
  "transcript_type": null
}
```

---

## ⚙️ Configuração (.env)

```bash
# Whisper
WHISPER_MODEL=base          # tiny/base/small/medium/large
WHISPER_DEVICE=cpu          # cpu ou cuda
WHISPER_LANGUAGE=auto       # auto ou código do idioma

# Limites
MAX_VIDEO_SIZE_MB=2500      # Tamanho máximo
MAX_VIDEO_DURATION_SECONDS=10800  # 3 horas
DOWNLOAD_TIMEOUT=900        # 15 minutos
REQUEST_TIMEOUT=3600        # 1 hora

# Performance
MAX_CONCURRENT_REQUESTS=3
WORKERS=1
```

### Modelos Whisper

| Modelo | VRAM | Velocidade | Qualidade | Uso Recomendado |
|--------|------|------------|-----------|-----------------|
| **tiny** | ~1GB | ~32x | Baixa | Testes rápidos |
| **base** | ~1GB | ~16x | Boa | **Recomendado para produção** |
| **small** | ~2GB | ~6x | Muito boa | Vídeos importantes |
| **medium** | ~5GB | ~2x | Excelente | GPU disponível |
| **large** | ~10GB | ~1x | Melhor | GPU potente + precisão crítica |

---

## 🐳 Docker

### Comandos Úteis

```bash
# Subir
docker-compose up -d

# Logs
docker-compose logs -f

# Parar
docker-compose down

# Rebuild
docker-compose build --no-cache

# Status
docker-compose ps

# Entrar no container
docker-compose exec api bash
```

### Recursos Docker

```yaml
# docker-compose.yml
resources:
  limits:
    cpus: '4'
    memory: 8G
  reservations:
    cpus: '2'
    memory: 4G
```

---

## 🏗️ Arquitetura

### Clean Architecture - 4 Camadas

```
src/
├── domain/              # Regras de negócio
│   ├── entities/       # Transcription, VideoFile
│   ├── value_objects/  # YouTubeURL
│   ├── interfaces/     # Contratos
│   └── exceptions/     # Erros de domínio
│
├── application/         # Casos de uso
│   ├── use_cases/      # TranscribeYouTubeVideoUseCase
│   └── dtos/           # DTOs de entrada/saída
│
├── infrastructure/      # Implementações técnicas
│   ├── youtube/        # YouTubeDownloader, TranscriptService
│   ├── whisper/        # WhisperTranscriptionService
│   └── storage/        # LocalStorageService
│
└── presentation/        # API/Interface
    └── api/
        ├── routes/     # Endpoints
        ├── middlewares/# CORS, logging
        └── dependencies/# DI container
```

### Princípios SOLID

- **S**ingle Responsibility: Cada classe tem uma única responsabilidade
- **O**pen/Closed: Aberto para extensão, fechado para modificação
- **L**iskov Substitution: Interfaces implementadas corretamente
- **I**nterface Segregation: Interfaces específicas e focadas
- **D**ependency Inversion: Depende de abstrações, não implementações

---

## 📊 Performance

### Vídeo de 3 minutos

| Método | Tempo | Qualidade | CPU |
|--------|-------|-----------|-----|
| YouTube Transcript | 1-2s | Profissional* | ~0% |
| Whisper tiny | ~42s | Baixa | 100% |
| Whisper base | ~106s | Boa | 100% |
| Whisper small | ~213s | Muito boa | 100% |

*Se legendas manuais disponíveis

### Vídeo de 1 hora

| Método | Tempo | Recomendação |
|--------|-------|--------------|
| YouTube Transcript | 2-5s | ✅ **Use se disponível** |
| Whisper base (CPU) | 30-60min | ⚠️ Lento |
| Whisper base (GPU) | 5-10min | ✅ Recomendado |

---

## 🔍 Recursos Avançados

### 1. Detecção de Idioma

Analisa título e descrição para detectar idioma:
- 10 idiomas suportados (pt, en, es, fr, de, it, ja, ko, ru, zh)
- Nível de confiança de 0 a 1
- Recomendação automática de parâmetros Whisper

### 2. Legendas do YouTube

Três métodos de fallback:
1. `youtube-transcript-api` (principal)
2. Método alternativo com retry
3. **yt-dlp** (mais robusto - JSON3 format)

Vantagens:
- ~100x mais rápido que Whisper
- Sem uso de CPU/GPU
- Legendas profissionais quando disponíveis

### 3. Validação de Duração

Antes de baixar:
- Verifica duração do vídeo
- Valida contra `MAX_VIDEO_DURATION_SECONDS`
- Fornece estimativas de processamento
- Alertas para vídeos longos

---

## 🚨 Troubleshooting

### Erro: "Downloaded file is empty"

**Solução**: Atualizar yt-dlp
```bash
pip install --upgrade yt-dlp
# Versão atual: 2025.10.14
```

### Whisper muito lento

**Soluções**:
1. Usar modelo menor (`tiny` ou `base`)
2. Usar GPU se disponível (`WHISPER_DEVICE=cuda`)
3. Usar YouTube Transcript se disponível

### Timeout em vídeos longos

**Ajustar limites**:
```bash
REQUEST_TIMEOUT=7200         # 2 horas
DOWNLOAD_TIMEOUT=1800        # 30 minutos
MAX_VIDEO_DURATION_SECONDS=14400  # 4 horas
```

### Container reiniciando

**Verificar**:
```bash
docker-compose logs api
docker stats

# Aumentar memória
memory: 8G  # no docker-compose.yml
```

---

## 🔐 Segurança

### Boas Práticas

1. **Nunca** exponha `.env` no Git
2. Use **reverse proxy** (nginx) em produção
3. Configure **rate limiting**
4. Monitore **uso de disco** (arquivos temp)
5. Configure **CORS** adequadamente

### Exemplo nginx

```nginx
server {
    listen 80;
    server_name api.ytcaption.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # Timeout para vídeos longos
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

---

## 📈 Monitoramento

### Logs

```bash
# Tempo real
docker-compose logs -f

# Últimas 100 linhas
docker-compose logs --tail=100

# Filtrar por erro
docker-compose logs | grep ERROR
```

### Health Check

```bash
# Manual
curl http://localhost:8000/health

# Monitoramento contínuo
watch -n 5 'curl -s http://localhost:8000/health | jq'
```

### Métricas

Health endpoint retorna:
- Status da API
- Modelo Whisper em uso
- Uso de armazenamento
- Uptime
- Versão

---

## 🚀 Deploy

### Proxmox/LXC

```bash
# 1. Criar container LXC
# CPU: 4-6 cores
# RAM: 6-8GB
# Disco: 50GB+

# 2. Instalar Docker
curl -fsSL https://get.docker.com | sh

# 3. Clonar projeto
git clone <repo>
cd ytcaption

# 4. Configurar
cp .env.example .env
nano .env

# 5. Usar scripts fornecidos
chmod +x start.sh stop.sh status.sh
./start.sh

# 6. Habilitar auto-start
# Adicionar ao crontab:
@reboot /path/to/start.sh
```

### Scripts Utilitários

**start.sh**: Detecta hardware e inicia container
**stop.sh**: Para container de forma segura
**status.sh**: Mostra status e logs

---

## 🆕 Changelog

### Versão 1.1.0 (Outubro 2025)

**Adicionado**:
- ✅ Detecção automática de idioma no `/video/info`
- ✅ Suporte a transcrição do YouTube (YouTube Transcript API)
- ✅ Parâmetro `use_youtube_transcript` no `/transcribe`
- ✅ Legendas disponíveis listadas no `/video/info`
- ✅ Recomendações inteligentes de modelo Whisper
- ✅ Sistema de 3 fallbacks para legendas (yt-dlp como backup)

**Atualizado**:
- ✅ yt-dlp de 2024.10.7 → 2025.10.14
- ✅ Corrigido bug "downloaded file is empty"

**Performance**:
- ✅ YouTube Transcript ~100x mais rápido que Whisper
- ✅ Sem uso de CPU/GPU ao usar legendas

---

## 📞 Suporte

### Documentação
- `/docs` - Swagger UI interativa
- `/redoc` - ReDoc alternativa

### Repositório
- Issues: Reporte bugs
- Discussions: Dúvidas e ideias
- Wiki: Guias avançados

### Comunidade
- GitHub: @JohnHeberty
- Projeto: YTCaption-Easy-Youtube-API

---

**💡 Dica**: Comece com `base` model e YouTube Transcript habilitado para melhor balanço entre velocidade e qualidade!
