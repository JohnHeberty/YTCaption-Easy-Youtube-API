# YouTubeDownloader

**Path**: `src/infrastructure/youtube/downloader.py`

---

## 📋 Visão Geral

**Responsabilidade**: Orquestrador principal do download de vídeos do YouTube (Facade Pattern)

**Camada**: Infrastructure Layer

**Versão**: v3.0 (YouTube Resilience System)

**Dependências**:
- `DownloadConfig` - Configurações centralizadas
- `StrategyManager` - Gerencia 7 estratégias de download
- `RateLimiter` - Rate limiting + Circuit Breaker
- `UserAgentRotator` - Rotaciona 17 User-Agents
- `ProxyManager` - Gerencia Tor proxy (SOCKS5)
- `YouTubeMetrics` - Registra 26 métricas Prometheus

---

## 🎯 Propósito

Coordenar todas as **5 camadas de resiliência** para garantir taxa de sucesso de 95% em downloads do YouTube:

1. **DNS Resilience** - Google DNS + Cloudflare
2. **Multi-Strategy Download** - 7 estratégias sequenciais
3. **Rate Limiting** - Controle de requests/min + Circuit Breaker
4. **User-Agent Rotation** - 17 UAs diferentes
5. **Tor Proxy** - Anonimização de IP

---

## 🏗️ Arquitetura

### Padrões Aplicados

| Padrão | Aplicação |
|--------|-----------|
| **Facade** | Simplifica acesso aos 5 subsistemas de resiliência |
| **Dependency Injection** | Recebe `DownloadConfig` via constructor |
| **Retry with Exponential Backoff** | `delay = min(min_delay * 2^attempt, max_delay)` |
| **Circuit Breaker** | Para após N falhas, aguarda timeout |

---

## 📚 Interface Pública

### `download(youtube_url: str) -> str`

**Descrição**: Faz download do áudio de um vídeo do YouTube

**Parâmetros**:
- `youtube_url` (str): URL do vídeo (`https://youtube.com/watch?v=VIDEO_ID`)

**Retorna**:
- `str`: Path absoluto do arquivo de áudio baixado (`.m4a` ou `.webm`)

**Exceções**:
| Exceção | Quando | Solução |
|---------|--------|---------|
| `AllStrategiesFailedError` | Todas as 7 estratégias falharam | Habilitar Tor, reduzir rate limit |
| `CircuitBreakerOpenError` | Circuit breaker aberto (muitas falhas) | Aguardar timeout (60s padrão) |
| `RateLimitExceededError` | Limite de requests/min atingido | Aguardar cooldown |
| `NetworkUnreachableError` | Tor offline ou DNS falhou | Verificar Tor, testar DNS |

---

## 🔄 Fluxo de Execução

```
┌─────────────────────────────────────────┐
│  download(youtube_url)                  │
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│ 1. RateLimiter.check()                  │
│    • Verifica requests/min              │
│    • Verifica circuit breaker status    │
│    • Se OPEN: raise CircuitBreakerOpen  │
└────────────┬────────────────────────────┘
             │ OK
             ↓
┌─────────────────────────────────────────┐
│ 2. UserAgentRotator.get_random()        │
│    • Seleciona 1 de 17 UAs              │
│    • Chrome/Firefox/Safari/Edge         │
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│ 3. ProxyManager.configure()             │
│    • Se ENABLE_TOR_PROXY=true           │
│    • Configura SOCKS5: tor-proxy:9050   │
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│ 4. StrategyManager.try_all()            │
│    • Tenta estratégias 1-7 sequencial   │
│    • Strategy 1: Direct (sem cookies)   │
│    • Strategy 2: Cookies (navegador)    │
│    • Strategy 3: Mobile UA              │
│    • Strategy 4: Referer header         │
│    • Strategy 5: Extract format         │
│    • Strategy 6: Embedded player        │
│    • Strategy 7: OAuth2 fallback        │
└────────┬────────────┬───────────────────┘
         │            │
      SUCCESS      FAILURE
         │            │
         ↓            ↓
┌─────────────┐  ┌─────────────────────────┐
│ Metrics     │  │ 5. Exponential Backoff  │
│ .record_    │  │    delay = min * 2^att  │
│  success()  │  │    time.sleep(delay)    │
│             │  └─────────┬───────────────┘
│ Return      │            │
│ audio_path  │            ↓
└─────────────┘  ┌─────────────────────────┐
                 │ 6. Retry (até MAX)      │
                 │    attempt += 1         │
                 │    if attempt < MAX:    │
                 │        goto step 4      │
                 └─────────┬───────────────┘
                           │ ALL FAILED
                           ↓
                 ┌─────────────────────────┐
                 │ Metrics.record_failure()│
                 │ Circuit Breaker opens   │
                 │ raise AllStrategiesFail │
                 └─────────────────────────┘
```

---

## 📊 Métricas Emitidas

### Contadores

- `youtube_download_success_total` - Total de downloads bem-sucedidos
- `youtube_download_failure_total` - Total de falhas (todas estratégias)
- `youtube_403_forbidden_total` - Erros HTTP 403 Forbidden
- `youtube_network_error_total` - Erros de rede (Tor offline, DNS)
- `youtube_strategy_success_total{strategy="1-7"}` - Sucessos por estratégia

### Gauges

- `youtube_circuit_breaker_open` - 1 se aberto, 0 se fechado
- `youtube_cooldown_active` - 1 se em cooldown, 0 caso contrário
- `youtube_retries_before_success` - Número de retries até sucesso

### Histogramas

- `youtube_request_duration_seconds` - Tempo de download (p50, p95, p99)

---

## 🧪 Exemplo de Uso

```python
from src.infrastructure.youtube.downloader import YouTubeDownloader
from src.infrastructure.youtube.download_config import DownloadConfig

# Carregar configurações do .env
config = DownloadConfig.from_env()

# Instanciar downloader
downloader = YouTubeDownloader(config)

try:
    # Fazer download
    audio_path = downloader.download(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )
    
    print(f"✅ Download sucesso: {audio_path}")
    # Output: /app/temp/dQw4w9WgXcQ.m4a
    
except AllStrategiesFailedError as e:
    print(f"❌ Todas as 7 estratégias falharam: {e}")
    print("Solução: Habilite Tor ou reduza rate limit")
    
except CircuitBreakerOpenError:
    print("⚠️ Circuit breaker aberto (muitas falhas)")
    print("Aguarde 60s (CIRCUIT_BREAKER_TIMEOUT)")
    
except RateLimitExceededError as e:
    print(f"⏱️ Rate limit atingido: {e}")
    print("Aguarde cooldown ou aumente limites no .env")
```

---

## 🔗 Relacionamentos

### Usa (Composição)

| Módulo | Propósito |
|--------|-----------|
| [DownloadConfig](./download-config.md) | Configurações (retries, timeouts, rate limits) |
| [StrategyManager](./download-strategies.md) | Gerencia 7 estratégias de download |
| [RateLimiter](./rate-limiter.md) | Rate limiting + Circuit Breaker |
| [UserAgentRotator](./user-agent-rotator.md) | Rotaciona 17 User-Agents |
| [ProxyManager](./proxy-manager.md) | Gerencia Tor proxy (SOCKS5) |
| [YouTubeMetrics](./metrics.md) | Registra 26 métricas Prometheus |

### Usado Por

- `TranscribeVideoUseCase` ([Application Layer](../../application/use-cases.md))

### Implementa

- `IVideoDownloader` ([Domain Layer](../../domain/interfaces.md))

---

## 🐛 Debugging

### Habilitar logs detalhados

```bash
# .env
LOG_LEVEL=DEBUG

# Logs mostram:
# - Estratégia sendo tentada
# - User-Agent selecionado
# - Proxy configurado (Tor)
# - Tempo de cada tentativa
# - Razão de falha de cada estratégia
```

### Ver métricas em tempo real

```bash
# Grafana
http://localhost:3000
Dashboard: YouTube Resilience v3.0

# Prometheus
http://localhost:9090
Query: rate(youtube_download_success_total[5m])
```

---

## 📖 Referências

### Diagramas

- [YouTube Resilience Flow](../../../diagrams/youtube-resilience-flow.md)
- [Design Patterns - Facade](../../../diagrams/design-patterns.md#facade)
- [Design Patterns - Circuit Breaker](../../../diagrams/design-patterns.md#circuit-breaker)

### Módulos Relacionados

- [DownloadConfig](./download-config.md) - Configurações
- [DownloadStrategies](./download-strategies.md) - 7 estratégias
- [RateLimiter](./rate-limiter.md) - Rate limiting
- [Metrics](./metrics.md) - Prometheus

### User Guides

- [Configuration - YouTube Resilience](../../../user-guide/03-configuration.md#youtube-resilience-v30)
- [Troubleshooting - HTTP 403](../../../user-guide/05-troubleshooting.md#http-403-forbidden)
- [Monitoring - Grafana](../../../user-guide/07-monitoring.md)

---

**Versão**: 3.0.0  
**Última atualização**: 22/10/2025  
**Autor**: [@JohnHeberty](https://github.com/JohnHeberty)

---

**[← Voltar para YouTube Module](./README.md)** | **[Próximo: DownloadConfig →](./download-config.md)**
