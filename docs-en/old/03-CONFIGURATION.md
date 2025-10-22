# ⚙️ Configuration

**Guia completo de todas as variáveis de ambiente (.env) - uma por uma.**

---

## 📋 Índice

1. [Application Settings](#application-settings)
2. [Server Settings](#server-settings)
3. [Whisper Settings](#whisper-settings)
4. [Parallel Transcription Settings](#parallel-transcription-settings)
5. [YouTube Settings](#youtube-settings)
6. [Storage Settings](#storage-settings)
7. [API Settings](#api-settings)
8. [Logging Settings](#logging-settings)
9. [Performance Settings](#performance-settings)

---

## Application Settings

### `APP_NAME`
**Nome da aplicação exibido nos logs e documentação.**

```bash
APP_NAME=Whisper Transcription API
```

- **Tipo**: String
- **Padrão**: `Whisper Transcription API`
- **Quando mudar**: Customização de branding

---

### `APP_VERSION`
**Versão da aplicação para controle de releases.**

```bash
APP_VERSION=1.0.0
```

- **Tipo**: String (Semantic Versioning)
- **Padrão**: `1.0.0`
- **Quando mudar**: Após mudanças importantes

---

### `APP_ENVIRONMENT`
**Ambiente de execução (afeta logs e comportamento).**

```bash
APP_ENVIRONMENT=production
```

- **Tipo**: String
- **Valores**: `production`, `development`, `staging`
- **Padrão**: `production`
- **Impacto**:
  - `production`: Logs minimalistas, otimizações
  - `development`: Logs verbosos, hot-reload
  - `staging`: Híbrido para testes

---

## Server Settings

### `HOST`
**Endereço IP que o servidor escuta.**

```bash
HOST=0.0.0.0
```

- **Tipo**: IP Address
- **Valores comuns**:
  - `0.0.0.0`: Todas as interfaces (Docker/produção)
  - `127.0.0.1`: Apenas localhost (desenvolvimento)
- **Padrão**: `0.0.0.0`
- **Quando mudar**: Segurança restritiva (apenas localhost)

---

### `PORT`
**Porta TCP onde a API escuta.**

```bash
PORT=8000
```

- **Tipo**: Integer (1-65535)
- **Padrão**: `8000`
- **Quando mudar**: Conflito de porta, firewall específico
- **Nota**: Alterar requer mudança no `docker-compose.yml`

---

## Whisper Settings

### `WHISPER_MODEL`
**Modelo de IA usado para transcrição.**

```bash
WHISPER_MODEL=base
```

- **Tipo**: String
- **Valores**: `tiny`, `base`, `small`, `medium`, `large`, `turbo`
- **Padrão**: `base`

| Modelo | Tamanho | RAM/Worker | Precisão | Velocidade | Uso Recomendado |
|--------|---------|------------|----------|------------|-----------------|
| `tiny` | 39M | ~400MB | ⭐⭐ | ⚡⚡⚡⚡⚡ | Desenvolvimento, testes |
| `base` | 74M | ~800MB | ⭐⭐⭐ | ⚡⚡⚡⚡ | **Produção (padrão)** |
| `small` | 244M | ~1.5GB | ⭐⭐⭐⭐ | ⚡⚡⚡ | Alta qualidade, CPU potente |
| `medium` | 769M | ~3GB | ⭐⭐⭐⭐⭐ | ⚡⚡ | GPU ou servidor dedicado |
| `large` | 1550M | ~6GB | ⭐⭐⭐⭐⭐ | ⚡ | GPU potente, máxima qualidade |

**Quando usar cada um**:
- **tiny**: Testes, desenvolvimento, velocidade máxima
- **base**: ✅ **Recomendado** - equilíbrio ideal
- **small**: Podcasts, entrevistas (qualidade alta)
- **medium**: Transcrições profissionais com GPU
- **large**: Academia, legendas oficiais

---

### `WHISPER_DEVICE`
**Dispositivo de processamento.**

```bash
WHISPER_DEVICE=cpu
```

- **Tipo**: String
- **Valores**: `cpu`, `cuda`
- **Padrão**: `cpu`

**CPU**:
- ✅ Funciona em qualquer servidor
- ⚠️ Mais lento (30min para 1h de áudio)
- 💰 Econômico

**CUDA (GPU NVIDIA)**:
- ✅ 10-20x mais rápido
- ⚠️ Requer GPU NVIDIA + drivers
- 💰 Servidor com GPU

**Como verificar se tem GPU:**
```bash
nvidia-smi
```

---

### `WHISPER_LANGUAGE`
**Idioma padrão para transcrição.**

```bash
WHISPER_LANGUAGE=auto
```

- **Tipo**: String (ISO 639-1)
- **Padrão**: `auto` (detecção automática)
- **Valores**: `auto`, `pt`, `en`, `es`, `fr`, `de`, `it`, `ja`, `ko`, `zh`

**Quando especificar**:
- ✅ **auto**: Deixe o Whisper detectar (recomendado)
- ✅ **pt**: Se todos os vídeos são em português (leve melhoria)
- ✅ **en**: Se todos os vídeos são em inglês

**Nota**: Especificar o idioma pode melhorar precisão em ~5-10%

---

## Parallel Transcription Settings

### `ENABLE_PARALLEL_TRANSCRIPTION`
**Habilita/desabilita processamento paralelo.**

```bash
ENABLE_PARALLEL_TRANSCRIPTION=true
```

- **Tipo**: Boolean
- **Valores**: `true`, `false`
- **Padrão**: `true`

**Quando habilitar (`true`)**:
- ✅ CPU com 4+ cores
- ✅ RAM suficiente (8GB+)
- ✅ Vídeos longos (10+ minutos)
- ✅ Quer velocidade máxima

**Quando desabilitar (`false`)**:
- ✅ CPU com 2 cores ou menos
- ✅ RAM limitada (4GB ou menos)
- ✅ Vídeos curtos (<5 min)
- ✅ Estabilidade > velocidade

**Benefício**: 3-4x mais rápido em CPUs multi-core

---

### `PARALLEL_WORKERS`
**Número de workers para processamento paralelo.**

```bash
PARALLEL_WORKERS=2
```

- **Tipo**: Integer
- **Valores**: `0` (auto-detect), `1`, `2`, `3`, `4`, `6`, `8`
- **Padrão**: `2` (conservador)

**Configurações por cenário**:

| Cores CPU | RAM Total | PARALLEL_WORKERS | RAM Usada (base model) |
|-----------|-----------|------------------|------------------------|
| 2 cores | 4GB | `0` (desabilitar paralelo) | ~800MB |
| 4 cores | 8GB | `2` ✅ | ~1.6GB |
| 8 cores | 16GB | `4` | ~3.2GB |
| 16 cores | 32GB+ | `0` (auto = usa todos) | ~6-8GB |

**Cálculo de RAM**:
```
RAM necessária = PARALLEL_WORKERS × RAM_por_modelo
```

Exemplo:
- `base` model = 800MB
- 4 workers = 4 × 800MB = **3.2GB RAM**

**Recomendações**:
- **0**: Auto-detect (usa todos os cores) - ⚠️ Alto uso de RAM
- **2**: ✅ **Conservador** - funciona na maioria dos casos
- **4**: Agressivo - requer 16GB+ RAM
- **8+**: Apenas servidores dedicados

---

### `PARALLEL_CHUNK_DURATION`
**Duração de cada chunk de áudio processado em paralelo.**

```bash
PARALLEL_CHUNK_DURATION=120
```

- **Tipo**: Integer (segundos)
- **Valores**: `60`, `90`, `120`, `180`, `240`
- **Padrão**: `120` (2 minutos)

**Como escolher**:

| Valor | Chunks (30min) | Overhead | Uso Recomendado |
|-------|----------------|----------|-----------------|
| `60` | 30 chunks | Alto | Muitos cores (8+) |
| `90` | 20 chunks | Médio | Equilibrado |
| `120` ✅ | 15 chunks | Baixo | **Padrão (recomendado)** |
| `180` | 10 chunks | Muito baixo | Poucos cores (2-4) |
| `240` | 7 chunks | Mínimo | CPU limitado |

**Trade-off**:
- ⬇️ Chunks menores (60s) = Mais paralelismo, mais overhead
- ⬆️ Chunks maiores (240s) = Menos paralelismo, menos overhead

---
---

## YouTube Settings

### `YOUTUBE_FORMAT`
**Qualidade do áudio baixado do YouTube.**

```bash
YOUTUBE_FORMAT=worstaudio
```

- **Tipo**: String
- **Valores**: `worstaudio`, `bestaudio`
- **Padrão**: `worstaudio`

**Por quê "worstaudio"?**
- ✅ Download 10x mais rápido
- ✅ Menos uso de disco
- ✅ Whisper funciona bem com baixa qualidade
- ✅ Suficiente para transcrição

**Quando usar "bestaudio"**:
- Análise de áudio detalhada
- Música/sons complexos
- Você tem banda e disco sobrando

---

### `MAX_VIDEO_SIZE_MB`
**Tamanho máximo de vídeo permitido (em MB).**

```bash
MAX_VIDEO_SIZE_MB=2500
```

- **Tipo**: Integer (megabytes)
- **Padrão**: `2500` (2.5GB)
- **Limite recomendado**: 500MB - 5000MB

**Cálculo aproximado**:
```
1 hora de áudio (worstaudio) ≈ 30-50MB
```

**Quando ajustar**:
- `500`: Vídeos curtos apenas (<30min)
- `1500`: ✅ Até 1 hora
- `2500`: ✅ **Padrão** - até 3 horas
- `5000`: Vídeos muito longos (palestras, lives)

---

### `MAX_VIDEO_DURATION_SECONDS`
**Duração máxima de vídeo permitida (em segundos).**

```bash
MAX_VIDEO_DURATION_SECONDS=10800
```

- **Tipo**: Integer (segundos)
- **Padrão**: `10800` (3 horas)

**Conversões úteis**:
```
1800 = 30 minutos
3600 = 1 hora
7200 = 2 horas
10800 = 3 horas ✅ (padrão)
14400 = 4 horas
```

**Quando ajustar**:
- `1800`: Apenas vídeos curtos
- `3600`: Até 1 hora (aulas, tutoriais)
- `7200`: Até 2 horas (palestras)
- `10800`: ✅ **Padrão** - até 3 horas
- `21600`: Lives, podcasts longos (6 horas)

---

### `DOWNLOAD_TIMEOUT`
**Timeout para download do YouTube (em segundos).**

```bash
DOWNLOAD_TIMEOUT=900
```

- **Tipo**: Integer (segundos)
- **Padrão**: `900` (15 minutos)

**Quando ajustar**:
- `300`: Internet rápida (5 min)
- `600`: Padrão (10 min)
- `900`: ✅ **Recomendado** - 15 minutos
- `1800`: Internet lenta ou vídeos grandes (30 min)

---

## YouTube Resilience Settings (v3.0)

**Sistema de resiliência para resolver bloqueios do YouTube (HTTP 403, Network unreachable).**

### `YOUTUBE_MAX_RETRIES`
**Número máximo de tentativas de download.**

```bash
YOUTUBE_MAX_RETRIES=5
```

- **Tipo**: Integer
- **Valores**: `1`, `3`, `5`, `7`, `10`
- **Padrão**: `5` ✅

**Como funciona**:
- Sistema tenta até N vezes antes de desistir
- Cada tentativa usa uma estratégia diferente (se multi-strategy habilitado)
- Delay entre tentativas é exponencial (YOUTUBE_RETRY_DELAY)

**Quando aumentar** (`7` ou `10`):
- Rede muito instável
- YouTube bloqueando frequentemente
- Servidor em região com alta latência
- Quer máxima persistência

**Quando diminuir** (`1` ou `3`):
- Quer falhar rápido
- Tem fallback externo
- Download não é crítico

---

### `YOUTUBE_RETRY_DELAY_MIN` / `YOUTUBE_RETRY_DELAY_MAX`
**Delay mínimo/máximo entre retentativas (segundos).**

```bash
YOUTUBE_RETRY_DELAY_MIN=10
YOUTUBE_RETRY_DELAY_MAX=120
```

- **Tipo**: Integer (segundos)
- **Padrão**: `10` / `120` ✅

**Como funciona**:
- Delay é escolhido aleatoriamente entre MIN e MAX
- Aumenta exponencialmente a cada tentativa
- Exemplo com padrão (10-120):
  - 1ª tentativa: 10-30s
  - 2ª tentativa: 30-60s
  - 3ª tentativa: 60-120s
  - 4ª tentativa: 120s (max)

**Configurações por cenário**:

| Cenário | MIN | MAX | Comportamento | Quando Usar |
|---------|-----|-----|---------------|-------------|
| **Agressivo** | 5 | 30 | Falha rápido, menos espera | Testes, debugging |
| **Padrão** ✅ | 10 | 120 | Equilíbrio | Produção normal |
| **Conservador** | 30 | 300 | Mais chances, mais espera | YouTube bloqueando muito |

**Por quê delay aleatório?**
- ✅ Parece tráfego humano (não é bot)
- ✅ Evita sincronização (múltiplos workers)
- ✅ Distribui carga no YouTube

---

### `YOUTUBE_CIRCUIT_BREAKER_THRESHOLD`
**Número de falhas consecutivas para abrir circuit breaker.**

```bash
YOUTUBE_CIRCUIT_BREAKER_THRESHOLD=8
```

- **Tipo**: Integer
- **Valores**: `5`, `8`, `10`, `15`
- **Padrão**: `8` ✅

**Como funciona** (Circuit Breaker Pattern):
1. **Closed** (normal): Tentativas de download passam
2. **Open** (bloqueado): Após N falhas, para de tentar (retorna erro imediato)
3. **Half-Open** (teste): Após timeout, permite 1 tentativa de teste

**Quando aumentar** (`10` ou `15`):
- YouTube com bloqueios esporádicos
- Quer mais persistência antes de desistir

**Quando diminuir** (`5`):
- Quer falhar rápido após problemas
- Tem alertas automáticos

---

### `YOUTUBE_CIRCUIT_BREAKER_TIMEOUT`
**Tempo de espera antes de tentar novamente após circuit breaker abrir (segundos).**

```bash
YOUTUBE_CIRCUIT_BREAKER_TIMEOUT=180
```

- **Tipo**: Integer (segundos)
- **Padrão**: `180` (3 minutos) ✅

**Como funciona**:
- Circuit breaker abre após N falhas
- Aguarda TIMEOUT segundos
- Entra em estado "Half-Open" (permite 1 teste)
- Se teste passa: volta ao normal (Closed)
- Se teste falha: volta para Open (aguarda mais TIMEOUT)

**Valores sugeridos**:
- `60`: Recuperação rápida (1 min)
- `180`: ✅ **Padrão** - equilibrado (3 min)
- `300`: Conservador (5 min)
- `600`: Muito conservador (10 min)

---

### `YOUTUBE_REQUESTS_PER_MINUTE`
**Limite de requests por minuto (rate limiting).**

```bash
YOUTUBE_REQUESTS_PER_MINUTE=10
```

- **Tipo**: Integer
- **Valores**: `5`, `10`, `15`, `20`, `30`
- **Padrão**: `10` ✅

**Por quê rate limiting?**
- ✅ Evita ban automático do YouTube
- ✅ Parece tráfego humano (não bot)
- ✅ Distribui carga no servidor
- ✅ Previne abuse detection

**Configurações por cenário**:

| Cenário | Valor | Comportamento | Quando Usar |
|---------|-------|---------------|-------------|
| **Muito Conservador** | 5 | 5 downloads/min | YouTube bloqueando muito |
| **Conservador** | 8 | 8 downloads/min | Servidor público |
| **Padrão** ✅ | 10 | 10 downloads/min | Produção normal |
| **Agressivo** | 15 | 15 downloads/min | Servidor dedicado |
| **Muito Agressivo** | 20-30 | 20-30 downloads/min | ⚠️ Risco de ban |

**⚠️ Aviso**: YouTube pode banir se detectar >30 req/min consistentemente.

---

### `YOUTUBE_REQUESTS_PER_HOUR`
**Limite de requests por hora (rate limiting global).**

```bash
YOUTUBE_REQUESTS_PER_HOUR=200
```

- **Tipo**: Integer
- **Valores**: `100`, `200`, `300`, `500`, `1000`
- **Padrão**: `200` ✅

**Janela dupla**:
- Sistema usa 2 janelas: minuto + hora
- Bloqueia se QUALQUER uma atingir o limite
- Exemplo: 10/min E 200/hora

**Configurações por cenário**:

| Cenário | /hora | /dia estimado | Quando Usar |
|---------|-------|---------------|-------------|
| **Conservador** | 100 | ~2.4k | Servidor público |
| **Padrão** ✅ | 200 | ~4.8k | Produção normal |
| **Agressivo** | 500 | ~12k | Alto volume |
| **Muito Agressivo** | 1000 | ~24k | ⚠️ Apenas servidor dedicado |

**Nota**: YouTube pode ter limites próprios não documentados.

---

### `YOUTUBE_COOLDOWN_ON_ERROR`
**Tempo de cooldown após erros consecutivos (segundos).**

```bash
YOUTUBE_COOLDOWN_ON_ERROR=60
```

- **Tipo**: Integer (segundos)
- **Valores**: `30`, `60`, `120`, `300`
- **Padrão**: `60` ✅

**Como funciona** (Exponential Backoff):
- 1º erro: 60s de pausa
- 2º erro consecutivo: 120s de pausa (2x)
- 3º erro consecutivo: 240s de pausa (4x)
- 4º erro consecutivo: 480s de pausa (8x)
- Sucesso reseta o contador

**Quando aumentar** (`120` ou `300`):
- YouTube está bloqueando agressivamente
- Quer evitar ban definitivo
- Prefere esperar mais entre tentativas

**Quando diminuir** (`30`):
- Erros são raros
- Quer recuperação rápida

---

### `ENABLE_TOR_PROXY`
**Habilita proxy Tor (GRATUITO, anônimo, IP rotation).**

```bash
ENABLE_TOR_PROXY=false
```

- **Tipo**: Boolean
- **Valores**: `true`, `false`
- **Padrão**: `false` ✅ (desabilitado)

**O que é Tor?**
- Rede de proxies anônimos e gratuitos
- Troca de IP automática a cada 30-60 segundos
- YouTube vê IP do Tor, não o seu IP real
- **ZERO CUSTO** (alternativa a proxies pagos)

**Por quê usar Tor? (`true`)**
- ✅ **GRÁTIS** (sem mensalidades)
- ✅ Bypass de bloqueios de IP
- ✅ Anonimato (YouTube não vê seu IP)
- ✅ IP rotation automática
- ✅ Bypass de bloqueios regionais

**Por quê NÃO usar Tor? (`false`)** ✅
- ⚠️ Mais lento (latência +500ms~2s)
- ⚠️ IPs do Tor podem estar na blacklist do YouTube
- ⚠️ Alguns IPs Tor são bloqueados
- ⚠️ Download pode ser mais lento

**Quando habilitar** (`true`):
- ❌ YouTube está bloqueando seu IP
- ❌ Erro 403 Forbidden frequente
- ❌ "Network unreachable" persistente
- ❌ Não tem budget para proxies pagos ($50-200/mês)
- ✅ Quer anonimato

**Quando desabilitar** (`false`) ✅:
- ✅ Conexão direta funcionando bem
- ✅ Quer máxima velocidade
- ✅ Tor está com muitos erros

**Serviço Tor** (incluído no docker-compose.yml):
- Container: `tor-proxy` (dperson/torproxy)
- Porta SOCKS5: `9050` (para Python/yt-dlp)
- Porta HTTP: `8118` (para navegadores)
- Rotação de IP: 30-60 segundos automático
- Configuração otimizada: MaxCircuitDirtiness=60, NewCircuitPeriod=30

**Testar Tor**:
```bash
# Verificar se Tor está rodando
docker ps | grep tor-proxy

# Ver logs
docker logs whisper-tor-proxy

# Testar conexão
docker exec whisper-transcription-api curl --socks5 tor-proxy:9050 https://check.torproject.org
```

---

### `TOR_PROXY_URL`
**URL do proxy Tor (se habilitado).**

```bash
TOR_PROXY_URL=socks5://tor-proxy:9050
```

- **Tipo**: String (URL)
- **Formato**: `socks5://HOST:PORT` ou `http://HOST:PORT`
- **Padrão**: `socks5://tor-proxy:9050` ✅

**Quando mudar**:
- Usar Tor externo (fora do Docker): `socks5://localhost:9050`
- Usar proxy HTTP customizado: `http://meu-proxy:8080`
- Usar serviço Tor comercial: `socks5://tor-comercial.com:9050`

**Formatos válidos**:
- `socks5://tor-proxy:9050` (SOCKS5 - recomendado)
- `socks5://localhost:9050` (Tor local)
- `http://proxy.com:8080` (HTTP proxy)
- `https://proxy.com:443` (HTTPS proxy)

---

### `ENABLE_MULTI_STRATEGY`
**Habilita sistema de multi-estratégias de download (7 fallback strategies).**

```bash
ENABLE_MULTI_STRATEGY=true
```

- **Tipo**: Boolean
- **Valores**: `true`, `false`
- **Padrão**: `true` ✅ (recomendado)

**O que faz?**
- Tenta 7 estratégias diferentes de download
- Fallback automático se uma falhar
- Aumenta taxa de sucesso de 60% → 95% (+58%)
- Cada estratégia usa diferentes clients do YouTube (Android, iOS, Web, TV, etc.)

**Estratégias (em ordem de prioridade)**:
1. **android_client** (prioridade 1) - Mais confiável em 2025
2. **android_music** (prioridade 2) - YouTube Music específico
3. **ios_client** (prioridade 3) - Client iOS oficial
4. **web_embed** (prioridade 4) - Player embed web
5. **tv_embedded** (prioridade 5) - Smart TV player
6. **mweb** (prioridade 6) - Mobile web
7. **default** (prioridade 7) - Fallback final

**Quando habilitar** (`true`) ✅:
- ✅ Produção (sempre)
- ✅ Quer máxima taxa de sucesso
- ✅ YouTube está bloqueando
- ✅ Conexão instável

**Quando desabilitar** (`false`):
- Debugging (quer testar estratégia específica)
- Quer falha rápida (sem tentativas de fallback)
- Desenvolvimento/testes

**Logging**:
```
🎯 Trying strategy: android_client (priority 1)
✅ Download completed with strategy 'android_client'
```

Ou se falhar:
```
🎯 Trying strategy: android_client (priority 1)
⚠️  Strategy 'android_client' failed: HTTP Error 403
🔄 Trying next strategy...
🎯 Trying strategy: ios_client (priority 3)
✅ Download completed with strategy 'ios_client'
```

---

### `ENABLE_USER_AGENT_ROTATION`
**Habilita rotação de User-Agent a cada request.**

```bash
ENABLE_USER_AGENT_ROTATION=true
```

- **Tipo**: Boolean
- **Valores**: `true`, `false`
- **Padrão**: `true` ✅ (recomendado)

**O que faz?**
- Rotaciona User-Agent (browser/device) a cada request
- 17 UAs pré-configurados (atualizados para 2025)
- Integração com biblioteca fake-useragent (70% random, 30% custom)
- Parece tráfego humano variado (não bot com UA fixo)

**User-Agents incluídos**:

**Desktop**:
- Chrome 120.0.0.0 (Windows 10)
- Chrome 119.0.0.0 (macOS)
- Firefox 121.0 (Windows 10)
- Edge 120.0.0.0 (Windows 11)
- Safari 17.2 (macOS Sonoma)

**Mobile**:
- Chrome 120 Mobile (Android 13)
- Chrome 119 Mobile (Android 14)
- Safari iOS 17.1 (iPhone 15 Pro)
- Safari iOS 17.2 (iPhone 15 Pro Max)

**Tablet**:
- Samsung Galaxy Tab S8 (Android 13)

**Smart TV / Console**:
- PlayStation 5
- LG WebOS 6.0

**Por quê rotação de UA?**
- ✅ Evita detecção de bot (UA fixo é suspeito)
- ✅ Parece tráfego humano diversificado
- ✅ Bypass de fingerprinting
- ✅ Melhora taxa de sucesso

**Quando habilitar** (`true`) ✅:
- ✅ Produção (sempre)
- ✅ YouTube detectando bot
- ✅ Quer parecer tráfego humano
- ✅ Combinação com multi-strategy

**Quando desabilitar** (`false`):
- Debugging (quer UA específico)
- Testes reproduzíveis
- Desenvolvimento

**Mix de UAs**:
- 70%: fake-useragent library (UAs mais recentes e variados)
- 30%: Custom pool (17 UAs testados e funcionando)

---

## YouTube Resilience Summary (v3.0)

**Resumo rápido das configurações de resiliência**:

```bash
# === Rate Limiting (evitar ban) ===
YOUTUBE_REQUESTS_PER_MINUTE=10          # Limite por minuto
YOUTUBE_REQUESTS_PER_HOUR=200           # Limite por hora

# === Retry Logic (persistência) ===
YOUTUBE_MAX_RETRIES=5                   # Tentativas máximas
YOUTUBE_RETRY_DELAY_MIN=10              # Delay mínimo (s)
YOUTUBE_RETRY_DELAY_MAX=120             # Delay máximo (s)
YOUTUBE_COOLDOWN_ON_ERROR=60            # Cooldown após erros (s)

# === Circuit Breaker (proteção) ===
YOUTUBE_CIRCUIT_BREAKER_THRESHOLD=8     # Falhas para abrir
YOUTUBE_CIRCUIT_BREAKER_TIMEOUT=180     # Timeout para retry (s)

# === Advanced Features ===
ENABLE_TOR_PROXY=false                  # Habilitar se bloqueado ⚠️
TOR_PROXY_URL=socks5://tor-proxy:9050   # URL do Tor
ENABLE_MULTI_STRATEGY=true              # ✅ Manter habilitado
ENABLE_USER_AGENT_ROTATION=true         # ✅ Manter habilitado
```

**Cenários de uso**:

| Problema | Solução | Configuração |
|----------|---------|--------------|
| **YouTube bloqueando (403)** | Habilitar Tor + Multi-Strategy | `ENABLE_TOR_PROXY=true` |
| **Network unreachable** | Verificar DNS + Habilitar Tor | Checar `docker-compose.yml` dns |
| **Rate limit muito alto** | Reduzir limites | `YOUTUBE_REQUESTS_PER_MINUTE=5` |
| **Download lento** | Desabilitar Tor (se habilitado) | `ENABLE_TOR_PROXY=false` |
| **Falhas esporádicas** | Aumentar retries | `YOUTUBE_MAX_RETRIES=7` |
| **Ban persistente** | Cooldown maior + Tor | `YOUTUBE_COOLDOWN_ON_ERROR=300` |

**Documentação completa**: 
- `docs/YOUTUBE-RESILIENCE-v3.0.md` (guia detalhado)
- `docs/PROMETHEUS-GRAFANA-v3.0.md` (monitoramento)

**Monitoramento (Grafana)**:
- URL: http://localhost:3000
- Usuário: admin / Senha: whisper2024
- Dashboard: "YouTube Download Resilience v3.0"

---

## Storage Settings

### `TEMP_DIR`
**Diretório para arquivos temporários.**

```bash
TEMP_DIR=./temp
```

- **Tipo**: Path (relativo ou absoluto)
- **Padrão**: `./temp`
- **Quando mudar**: Trocar disco/volume

**Exemplo absoluto**:
```bash
TEMP_DIR=/mnt/storage/ytcaption-temp
```

---

### `CLEANUP_ON_STARTUP`
**Limpar arquivos temporários ao iniciar.**

```bash
CLEANUP_ON_STARTUP=true
```

- **Tipo**: Boolean
- **Valores**: `true`, `false`
- **Padrão**: `true`

**Recomendação**: Deixe `true` para evitar acúmulo de lixo

---

### `CLEANUP_AFTER_PROCESSING`
**Limpar arquivos temporários após cada transcrição.**

```bash
CLEANUP_AFTER_PROCESSING=true
```

- **Tipo**: Boolean
- **Valores**: `true`, `false`
- **Padrão**: `true`

**Quando desabilitar (`false`)**:
- Debug (analisar arquivos baixados)
- Cache de áudios
- ⚠️ Requer limpeza manual periódica

---

### `MAX_TEMP_AGE_HOURS`
**Idade máxima de arquivos temp antes da limpeza.**

```bash
MAX_TEMP_AGE_HOURS=24
```

- **Tipo**: Integer (horas)
- **Padrão**: `24` (1 dia)
- **Valores**: `1`, `6`, `12`, `24`, `48`, `72`

---

## API Settings

### `MAX_CONCURRENT_REQUESTS`
**Número máximo de transcrições simultâneas.**

```bash
MAX_CONCURRENT_REQUESTS=3
```

- **Tipo**: Integer
- **Padrão**: `3`

**Cálculo**:
```
RAM necessária = MAX_CONCURRENT_REQUESTS × RAM_por_modelo
```

Exemplo:
- 3 requests × 800MB (base) = **2.4GB RAM**

**Recomendações por RAM**:
- 4GB RAM: `MAX_CONCURRENT_REQUESTS=2`
- 8GB RAM: `MAX_CONCURRENT_REQUESTS=3` ✅
- 16GB RAM: `MAX_CONCURRENT_REQUESTS=6`
- 32GB+ RAM: `MAX_CONCURRENT_REQUESTS=10`

---

### `REQUEST_TIMEOUT`
**Timeout para cada requisição (em segundos).**

```bash
REQUEST_TIMEOUT=3600
```

- **Tipo**: Integer (segundos)
- **Padrão**: `3600` (1 hora)

**Quando ajustar**:
- `1800`: Vídeos até 30min
- `3600`: ✅ **Padrão** - até 1 hora
- `7200`: Vídeos até 2 horas
- `10800`: Vídeos até 3 horas

---

### `ENABLE_CORS`
**Habilitar CORS (para acesso de navegadores).**

```bash
ENABLE_CORS=true
```

- **Tipo**: Boolean
- **Valores**: `true`, `false`
- **Padrão**: `true`

**Quando desabilitar**: API backend-only (sem frontend web)

---

### `CORS_ORIGINS`
**Origens permitidas para CORS.**

```bash
CORS_ORIGINS=*
```

- **Tipo**: String (URLs separadas por vírgula)
- **Padrão**: `*` (todas as origens)

**Exemplos**:
```bash
# Permitir todas (desenvolvimento)
CORS_ORIGINS=*

# Apenas domínio específico (produção)
CORS_ORIGINS=https://meu-site.com

# Múltiplos domínios
CORS_ORIGINS=https://meu-site.com,https://app.meu-site.com
```

---

## Logging Settings

### `LOG_LEVEL`
**Nível de detalhamento dos logs.**

```bash
LOG_LEVEL=INFO
```

- **Tipo**: String
- **Valores**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Padrão**: `INFO`

| Nível | Detalhamento | Uso |
|-------|--------------|-----|
| `DEBUG` | Máximo | Desenvolvimento |
| `INFO` ✅ | Moderado | **Produção (padrão)** |
| `WARNING` | Apenas avisos | Produção silenciosa |
| `ERROR` | Apenas erros | Mínimo |

---

### `LOG_FORMAT`
**Formato de saída dos logs.**

```bash
LOG_FORMAT=json
```

- **Tipo**: String
- **Valores**: `json`, `text`
- **Padrão**: `json`

**JSON**: Ideal para parsing, ferramentas de logs (ELK, Grafana)  
**TEXT**: Mais legível para humanos

---

### `LOG_FILE`
**Caminho do arquivo de log.**

```bash
LOG_FILE=./logs/app.log
```

- **Tipo**: Path
- **Padrão**: `./logs/app.log`

---

## Performance Settings

### `WORKERS`
**Número de workers Uvicorn (processos API).**

```bash
WORKERS=1
```

- **Tipo**: Integer
- **Valores**: `1`, `2`, `4`
- **Padrão**: `1` ✅

**⚠️ IMPORTANTE**: Para esta aplicação, `WORKERS=1` é **ótimo**!

**Por quê?**
- Aplicação é I/O bound (espera download, FFmpeg)
- Múltiplos workers competem pelo modelo Whisper
- Async/await do FastAPI já gerencia concorrência

**Quando usar > 1**:
- Tráfego altíssimo (100+ req/s)
- RAM sobrando (8GB+ por worker)
- Você desabilitou transcrição paralela

---

### `WORKER_CLASS`
**Classe de worker do Uvicorn.**

```bash
WORKER_CLASS=uvicorn.workers.UvicornWorker
```

- **Tipo**: String
- **Padrão**: `uvicorn.workers.UvicornWorker`
- **Não alterar** (valor correto para async)

---

## 📊 Configurações Recomendadas por Cenário

### Servidor Pequeno (4GB RAM, 2 cores)
```bash
WHISPER_MODEL=tiny
WHISPER_DEVICE=cpu
ENABLE_PARALLEL_TRANSCRIPTION=false
MAX_CONCURRENT_REQUESTS=2
WORKERS=1
```

### Servidor Médio (8GB RAM, 4 cores) ✅ **Padrão**
```bash
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=2
MAX_CONCURRENT_REQUESTS=3
WORKERS=1
```

### Servidor Grande (16GB+ RAM, 8+ cores)
```bash
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=4
MAX_CONCURRENT_REQUESTS=6
WORKERS=1
```

### Servidor com GPU
```bash
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda
ENABLE_PARALLEL_TRANSCRIPTION=false  # GPU já é rápido
MAX_CONCURRENT_REQUESTS=4
WORKERS=1
```

---

**Próximo**: [Uso da API](./04-API-USAGE.md)

**Versão**: 1.3.3+  
**Última atualização**: 19/10/2025
