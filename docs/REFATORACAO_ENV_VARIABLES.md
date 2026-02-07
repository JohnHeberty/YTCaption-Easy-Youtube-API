# 🔧 REFATORAÇÃO: Centralização de Variáveis de Ambiente

**Data:** 2026-02-07  
**Serviço:** Todos os microserviços  
**Status:** ✅ make-video concluído | 🔄 Outros microserviços pendentes

---

## 📋 Problema Identificado

As variáveis de ambiente estavam **duplicadas** entre:
- `.env` (arquivo de configuração)
- `docker-compose.yml` (valores hardcoded)

**Exemplo do problema:**
```yaml
# docker-compose.yml (ANTES)
environment:
  - YOUTUBE_SEARCH_URL=https://ytsearch.loadstask.com/  # ❌ Hardcoded
  - VIDEO_DOWNLOADER_URL=https://ytdownloader.loadstask.com/
  - REDIS_URL=redis://192.168.1.110:6379/0
  - PORT=8004
```

**Consequências:**
- ❌ Necessário alterar **2 arquivos** para mudar uma configuração
- ❌ Risco de inconsistências (`.env` diferente de `docker-compose.yml`)
- ❌ Manutenção duplicada
- ❌ Erro humano mais provável

---

## ✅ Solução Implementada

**Princípio:** Single Source of Truth (SSOT)
- `.env` contém **todos os valores**
- `docker-compose.yml` referencia variáveis com sintaxe `${VARIAVEL}`

**Exemplo da solução:**
```yaml
# docker-compose.yml (DEPOIS)
services:
  make-video:
    env_file:
      - .env  # ✅ Carrega .env automaticamente
    environment:
      - YOUTUBE_SEARCH_URL=${YOUTUBE_SEARCH_URL}  # ✅ Referência
      - VIDEO_DOWNLOADER_URL=${VIDEO_DOWNLOADER_URL}
      - REDIS_URL=${REDIS_URL}
      - PORT=${PORT}
```

**Benefícios:**
- ✅ **1 arquivo** para configurar (`.env`)
- ✅ Consistência garantida
- ✅ Fácil manutenção
- ✅ Suporte a múltiplos ambientes (`.env.dev`, `.env.prod`)

---

## 🎯 Status de Implementação

### ✅ Concluído: make-video

**Arquivos modificados:**
- [docker-compose.yml](../services/make-video/docker-compose.yml)
- [.env](../services/make-video/.env)
- [.env.example](../services/make-video/.env.example)

**Mudanças aplicadas:**
1. ✅ Adicionado `env_file: - .env` em todos os services
2. ✅ Substituído valores hardcoded por `${VARIAVEL}` em:
   - `make-video` (API)
   - `make-video-celery` (worker)
   - `make-video-celery-beat` (scheduler)
3. ✅ Ajustado caminhos no `.env` para absolutos (`/app/storage/...`)
4. ✅ Validado funcionamento (teste com `docker exec`)

**Resultado do teste:**
```bash
$ docker exec ytcaption-make-video python -c "from app.config import get_settings; s = get_settings(); print(s.get('youtube_search_url'))"
https://ytsearch.loadstask.com/  ✅
```

---

### 🔄 Pendente: Outros Microserviços

Os seguintes serviços **JÁ USAM** `env_file: .env`, mas precisam revisar se há valores hardcoded no `environment:`:

#### 1. audio-normalization
**Arquivo:** `services/audio-normalization/docker-compose.yml`
**Status:** ☑️ Já usa `env_file`, verificar `environment`

#### 2. audio-transcriber
**Arquivo:** `services/audio-transcriber/docker-compose.yml`
**Status:** ☑️ Já usa `env_file`, verificar `environment`

#### 3. video-downloader
**Arquivo:** `services/video-downloader/docker-compose.yml`
**Status:** ☑️ Já usa `env_file`, verificar `environment`

#### 4. youtube-search
**Arquivo:** `services/youtube-search/docker-compose.yml`
**Status:** ⏳ Verificar se precisa ajustes

---

## 📝 Guia de Refatoração (Para Outros Serviços)

### Passo 1: Verificar docker-compose.yml

Identificar valores hardcoded:
```bash
cd services/<SERVICO>
grep -E "- [A-Z_]+=.+" docker-compose.yml
```

### Passo 2: Adicionar env_file (se não existir)

```yaml
services:
  <servico>:
    build: .
    env_file:
      - .env  # ← Adicionar esta linha
    environment:
      # ... variáveis
```

### Passo 3: Substituir valores hardcoded

**ANTES:**
```yaml
environment:
  - PORT=8001
  - DEBUG=false
  - REDIS_URL=redis://192.168.1.110:6379/0
```

**DEPOIS:**
```yaml
environment:
  - PORT=${PORT}
  - DEBUG=${DEBUG}
  - REDIS_URL=${REDIS_URL}
```

### Passo 4: Garantir que .env tem todos os valores

```bash
# Verificar quais variáveis estão no docker-compose
grep -oP '(?<=- )[A-Z_]+(?==)' docker-compose.yml | sort -u > vars_compose.txt

# Verificar quais estão no .env
grep -oP '^[A-Z_]+(?==)' .env | sort -u > vars_env.txt

# Comparar
comm -23 vars_compose.txt vars_env.txt  # Variáveis faltando no .env
```

### Passo 5: Validar mudanças

```bash
# Reconstruir e subir
docker compose down
docker compose up -d

# Testar que variáveis foram carregadas
docker exec <container-name> env | grep REDIS_URL
```

---

## 🔍 Checklist de Validação

Para cada microserviço, validar:

```yaml
✅ docker-compose.yml tem `env_file: - .env`
✅ Valores hardcoded substituídos por ${VARIAVEL}
✅ Arquivo .env contém TODAS as variáveis usadas
✅ Arquivo .env.example atualizado
✅ Teste de rebuild bem-sucedido
✅ Teste de runtime (verificar valores carregados)
✅ Healthcheck passa
✅ Serviço funcional após mudanças
```

---

## 📚 Referências Técnicas

### Sintaxe de Variáveis no Docker Compose

```yaml
# Variável simples
- VAR=${VAR}

# Variável com valor padrão
- VAR=${VAR:-default_value}

# Variável obrigatória (falha se não definida)
- VAR=${VAR?Variable VAR is required}
```

### Ordem de Precedência (Docker Compose)

1. **Shell environment** (mais alta)
2. **env_file** (`.env`)
3. **environment** (no docker-compose.yml)
4. **Dockerfile ENV** (mais baixa)

**Importante:** Se usar `${VAR}` no `environment:`, o valor vem do **shell** ou **env_file**, não do valor hardcoded.

---

## 🚨 Notas Importantes

### 1. Caminhos Relativos vs Absolutos

**Dentro do container:**
```bash
AUDIO_UPLOAD_DIR=/app/storage/audio_uploads  # ✅ Absoluto (dentro do container)
```

**No docker-compose (volumes):**
```yaml
volumes:
  - ./storage/audio_uploads:/app/storage/audio_uploads  # ✅ Relativo no host, absoluto no container
```

### 2. Variáveis com Espaços

Se variável contém espaços, usar aspas no `.env`:
```bash
SUBTITLE_FONT_NAME="Arial Black"  # ✅ Com aspas
```

No `docker-compose.yml`:
```yaml
- SUBTITLE_FONT_NAME=${SUBTITLE_FONT_NAME}  # Docker Compose preserva aspas
```

### 3. Valores Especiais

**Caracteres especiais (ex: `&H00FFFF&`):**
```bash
# .env
SUBTITLE_COLOR="&H00FFFF&"  # Use aspas se tiver caracteres especiais
```

### 4. Debug de Variáveis

Testar se variável foi carregada:
```bash
# Dentro do container
docker exec <container> env | grep YOUTUBE_SEARCH_URL

# Ou no Python
docker exec <container> python -c "import os; print(os.getenv('YOUTUBE_SEARCH_URL'))"
```

---

## 📊 Exemplo Completo: make-video

### .env
```bash
# URLs de Microserviços
YOUTUBE_SEARCH_URL=https://ytsearch.loadstask.com/
VIDEO_DOWNLOADER_URL=https://ytdownloader.loadstask.com/
AUDIO_TRANSCRIBER_URL=https://yttranscriber.loadstask.com/

# Redis
REDIS_URL=redis://192.168.1.110:6379/0

# Servidor
PORT=8004
DEBUG=False
LOG_LEVEL=INFO

# Diretórios (caminhos absolutos dentro do container)
AUDIO_UPLOAD_DIR=/app/storage/audio_uploads
SHORTS_CACHE_DIR=/app/storage/shorts_cache
TEMP_DIR=/app/storage/temp
OUTPUT_DIR=/app/storage/output_videos
LOG_DIR=/app/logs

# Processamento
VIDEO_TRIM_PADDING_MS=1000
TRSD_ENABLED=true
```

### docker-compose.yml
```yaml
services:
  make-video:
    build: .
    container_name: ytcaption-make-video
    ports:
      - "${PORT}:${PORT}"
    volumes:
      - ./storage/audio_uploads:/app/storage/audio_uploads
      - ./storage/shorts_cache:/app/storage/shorts_cache
      - ./storage/temp:/app/storage/temp
      - ./storage/output_videos:/app/storage/output_videos
      - ./logs:/app/logs
    env_file:
      - .env  # ← Carrega .env
    environment:
      - PYTHONPATH=/app
      - PORT=${PORT}
      - DEBUG=${DEBUG}
      - REDIS_URL=${REDIS_URL}
      - YOUTUBE_SEARCH_URL=${YOUTUBE_SEARCH_URL}
      - VIDEO_DOWNLOADER_URL=${VIDEO_DOWNLOADER_URL}
      - AUDIO_TRANSCRIBER_URL=${AUDIO_TRANSCRIBER_URL}
      - AUDIO_UPLOAD_DIR=${AUDIO_UPLOAD_DIR}
      - SHORTS_CACHE_DIR=${SHORTS_CACHE_DIR}
      - TEMP_DIR=${TEMP_DIR}
      - OUTPUT_DIR=${OUTPUT_DIR}
      - LOG_DIR=${LOG_DIR}
      - LOG_LEVEL=${LOG_LEVEL}
      - VIDEO_TRIM_PADDING_MS=${VIDEO_TRIM_PADDING_MS}
      - TRSD_ENABLED=${TRSD_ENABLED}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${PORT}/health"]
    networks:
      - ytcaption-network

  make-video-celery:
    build: .
    container_name: ytcaption-make-video-celery
    command: python -m celery -A app.celery_config worker --loglevel=info
    volumes:
      - ./storage/audio_uploads:/app/storage/audio_uploads
      - ./storage/shorts_cache:/app/storage/shorts_cache
      - ./storage/temp:/app/storage/temp
      - ./storage/output_videos:/app/storage/output_videos
      - ./logs:/app/logs
    env_file:
      - .env  # ← Carrega .env
    environment:
      - PYTHONPATH=/app
      - PORT=${PORT}
      - DEBUG=${DEBUG}
      - REDIS_URL=${REDIS_URL}
      - YOUTUBE_SEARCH_URL=${YOUTUBE_SEARCH_URL}
      - VIDEO_DOWNLOADER_URL=${VIDEO_DOWNLOADER_URL}
      - AUDIO_TRANSCRIBER_URL=${AUDIO_TRANSCRIBER_URL}
      - AUDIO_UPLOAD_DIR=${AUDIO_UPLOAD_DIR}
      - SHORTS_CACHE_DIR=${SHORTS_CACHE_DIR}
      - TEMP_DIR=${TEMP_DIR}
      - OUTPUT_DIR=${OUTPUT_DIR}
      - LOG_DIR=${LOG_DIR}
      - VIDEO_TRIM_PADDING_MS=${VIDEO_TRIM_PADDING_MS}
    restart: unless-stopped

networks:
  ytcaption-network:
    external: true
```

---

## 🎯 Próximos Passos

1. **Aplicar refatoração nos outros microserviços:**
   - [ ] audio-normalization
   - [ ] audio-transcriber
   - [ ] video-downloader
   - [ ] youtube-search

2. **Validar cada serviço após mudanças:**
   - [ ] Rebuild bem-sucedido
   - [ ] Variáveis carregadas corretamente
   - [ ] Healthcheck passa
   - [ ] Funcionalidade preservada

3. **Documentar mudanças:**
   - [ ] Atualizar README de cada serviço
   - [ ] Atualizar documentação de deployment
   - [ ] Criar guia de troubleshooting

4. **Considerar melhorias futuras:**
   - [ ] Usar `.env.dev`, `.env.staging`, `.env.prod`
   - [ ] Implementar validação de variáveis obrigatórias
   - [ ] Criar script de setup automático
   - [ ] Adicionar CI/CD checks para .env

---

## ✅ Conclusão

**make-video:** ✅ Refatoração completa e validada

**Benefícios imediatos:**
- 🎯 Single source of truth (`.env`)
- 🛠️ Manutenção simplificada
- 🔒 Consistência garantida
- 📝 Melhor documentação

**Próxima ação:** Replicar para outros microserviços seguindo este guia.

---

*Documento criado em: 2026-02-07*  
*Autor: GitHub Copilot AI Assistant*  
*Referência: Sprint Post-09 - Task 1 (Audit Environment Variables)*
