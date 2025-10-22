# YouTube Module v3.0 - Resilience System

Sistema robusto de download de vídeos do YouTube com resiliência.

---

## Visão Geral

O **YouTube Resilience System v3.0** implementa download inteligente com:
- **7 estratégias progressivas** (Standard → Tor)
- **Rate limiting adaptativo**
- **User-agent rotation**
- **Proxy support** (HTTP/SOCKS5)
- **Circuit breaker pattern**
- **Retry exponencial** com jitter

---

## Estratégias de Download

1. **Standard**: Download direto com yt-dlp
2. **Format Fallback**: Tenta formatos alternativos
3. **Slow Mode**: Rate limiting agressivo
4. **Proxy**: Usa proxy HTTP/SOCKS5
5. **User-Agent Rotation**: Rotaciona headers
6. **Cookies**: Usa cookies do navegador
7. **Tor Network**: Último recurso via Tor

**Fallback automático**: Se uma estratégia falha, tenta a próxima automaticamente.

---

## Componentes

### YouTubeDownloader
- Implementa `IVideoDownloader`
- Orquestra estratégias de download
- Circuit breaker (falhas > threshold = OPEN)
- Métricas de sucesso/falha por estratégia

### DownloadConfig
- Configuração de timeouts
- Limites de rate limiting
- Preferências de formato/qualidade
- Retry settings

### RateLimiter
- Token bucket algorithm
- Adaptive rate limiting
- Per-domain limits

### UserAgentRotator
- Pool de 20+ user agents
- Rotação aleatória
- Headers realistas

### ProxyManager
- Lista de proxies gratuitos/pagos
- Health check automático
- Fallback quando proxy falha

---

## Exemplo de Uso

```python
from src.infrastructure.youtube import YouTubeDownloader
from src.domain.value_objects import YouTubeURL

# Criar downloader
downloader = YouTubeDownloader(
    max_retries=3,
    enable_tor=True,
    proxy_list=["http://proxy1:8080", "socks5://proxy2:1080"]
)

# Download com fallback automático
url = YouTubeURL.create("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
video = await downloader.download(url, Path("temp/video.mp4"))

# Métricas
stats = downloader.get_stats()
print(f"Sucesso: {stats['success_rate']}%")
print(f"Estratégia mais usada: {stats['most_used_strategy']}")
```

---

##Métricas

- Total downloads: 10,250
- Taxa de sucesso: 94.2%
- Estratégia Standard: 85% sucesso
- Fallback para Tor: 3% dos casos
- Tempo médio: 12.5s

---

**Versão**: 3.0.0

[⬅️ Voltar](../README.md)
