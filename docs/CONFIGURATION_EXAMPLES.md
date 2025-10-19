# Exemplos de Configuração - Diferentes Cenários

## 🔧 Cenários de Configuração

Copie a configuração apropriada para seu `.env`:

---

## 📦 Servidor Básico (4-8GB RAM, 4 cores)

**Melhor para**: Pequeno volume de requisições, servidor compartilhado

```bash
# Whisper Settings
WHISPER_MODEL=base
WHISPER_DEVICE=cpu

# Parallel Transcription Settings
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=2               # Apenas 2 workers (economiza RAM)
PARALLEL_CHUNK_DURATION=120

# API Settings
MAX_CONCURRENT_REQUESTS=2        # Limita concorrência
REQUEST_TIMEOUT=3600
```

**RAM esperada**: ~2GB para transcription + ~1GB sistema = **~3GB total**

---

## 🚀 Servidor Performance (16GB+ RAM, 8+ cores)

**Melhor para**: Alto volume, produção dedicada

```bash
# Whisper Settings
WHISPER_MODEL=base               # Ou 'small' se tiver 24GB+ RAM
WHISPER_DEVICE=cpu

# Parallel Transcription Settings
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=4               # 4 workers agressivo
PARALLEL_CHUNK_DURATION=120

# API Settings
MAX_CONCURRENT_REQUESTS=3
REQUEST_TIMEOUT=3600
```

**RAM esperada**: ~3.2GB para transcription + ~1GB sistema = **~4-5GB total**

---

## 💾 Servidor Memória Limitada (2-4GB RAM, 2-4 cores)

**Melhor para**: VPS básico, teste, desenvolvimento

```bash
# Whisper Settings
WHISPER_MODEL=tiny               # Modelo mais leve
WHISPER_DEVICE=cpu

# Parallel Transcription Settings
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=2               # Apenas 2 workers
PARALLEL_CHUNK_DURATION=180      # Chunks maiores (menos overhead)

# API Settings
MAX_CONCURRENT_REQUESTS=1        # Uma requisição por vez
REQUEST_TIMEOUT=3600
```

**RAM esperada**: ~800MB para transcription + ~1GB sistema = **~2GB total**

---

## 🎯 Máxima Qualidade (32GB+ RAM, 16+ cores)

**Melhor para**: Transcrição profissional, alta precisão

```bash
# Whisper Settings
WHISPER_MODEL=medium             # Ou 'large' se 64GB+ RAM
WHISPER_DEVICE=cpu               # Ou 'cuda' se GPU disponível

# Parallel Transcription Settings
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=0               # Auto-detect (usa todos os cores)
PARALLEL_CHUNK_DURATION=120

# API Settings
MAX_CONCURRENT_REQUESTS=2        # Limita para não sobrecarregar
REQUEST_TIMEOUT=7200             # 2 horas (modelos grandes são lentos)
```

**RAM esperada**: ~12GB para transcription + ~2GB sistema = **~14GB total**

---

## 🏃 Desenvolvimento Local (Windows/Mac)

**Melhor para**: Testes locais, desenvolvimento

```bash
# Whisper Settings
WHISPER_MODEL=tiny               # Mais rápido para testes
WHISPER_DEVICE=cpu

# Parallel Transcription Settings
ENABLE_PARALLEL_TRANSCRIPTION=false   # Desabilitado (mais simples)
PARALLEL_WORKERS=0
PARALLEL_CHUNK_DURATION=120

# API Settings
MAX_CONCURRENT_REQUESTS=1
REQUEST_TIMEOUT=1800
```

**RAM esperada**: ~800MB para transcription + ~500MB sistema = **~1.5GB total**

---

## 🎮 Servidor com GPU (NVIDIA CUDA)

**Melhor para**: Máxima performance com GPU dedicada

```bash
# Whisper Settings
WHISPER_MODEL=medium             # GPU aguenta modelos maiores
WHISPER_DEVICE=cuda              # Usa GPU

# Parallel Transcription Settings
ENABLE_PARALLEL_TRANSCRIPTION=false   # GPU já é rápida, não precisa paralelo
PARALLEL_WORKERS=0
PARALLEL_CHUNK_DURATION=120

# API Settings
MAX_CONCURRENT_REQUESTS=3
REQUEST_TIMEOUT=3600
```

**Notas**: 
- GPU é muito mais rápida que CPU paralelo
- Não use paralelo com GPU (não há ganho, pode até ser mais lento)
- Requer CUDA instalado no sistema

---

## 📊 Comparação de Performance

| Cenário              | Modelo  | Workers | RAM    | Tempo (30min áudio) | Qualidade |
|----------------------|---------|---------|--------|---------------------|-----------|
| Básico               | base    | 2       | ~3GB   | ~7 min              | ⭐⭐⭐     |
| Performance          | base    | 4       | ~5GB   | ~4 min              | ⭐⭐⭐     |
| Memória Limitada     | tiny    | 2       | ~2GB   | ~10 min             | ⭐⭐       |
| Máxima Qualidade     | medium  | auto    | ~14GB  | ~5 min              | ⭐⭐⭐⭐⭐   |
| Desenvolvimento      | tiny    | -       | ~1.5GB | ~15 min             | ⭐⭐       |
| GPU                  | medium  | -       | ~4GB   | ~2 min              | ⭐⭐⭐⭐⭐   |

---

## 🔄 Como Trocar de Configuração

1. Edite `.env`:
```bash
nano .env
```

2. Copie a configuração desejada

3. Reinicie o container:
```bash
docker-compose restart
```

4. Verifique os logs:
```bash
docker-compose logs -f | grep "transcription service"
```

---

## 🧪 Teste Sua Configuração

Após trocar, teste com um vídeo curto primeiro:

```bash
curl -X POST http://localhost:8000/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "language": "auto"
  }'
```

Monitore RAM durante o teste:

```bash
# No servidor
docker stats

# Ou
docker-compose exec api top
```

---

## ⚠️ Sinais de Problema

### Falta de RAM
**Sintomas**: 
- Erro "process pool terminated abruptly"
- Container reinicia
- Sistema fica lento

**Solução**: Reduza `PARALLEL_WORKERS` ou use modelo menor

### CPU Sobrecarregado
**Sintomas**:
- Transcrição muito lenta
- Sistema irresponsivo

**Solução**: Reduza `PARALLEL_WORKERS` ou `MAX_CONCURRENT_REQUESTS`

### Disco Cheio
**Sintomas**:
- Erro ao salvar arquivos
- Conversão de áudio falha

**Solução**: 
- Limpe `./temp` manualmente
- Configure `CLEANUP_AFTER_PROCESSING=true`

---

**Dica Final**: Comece com configuração conservadora e aumente gradualmente enquanto monitora recursos! 🎯
