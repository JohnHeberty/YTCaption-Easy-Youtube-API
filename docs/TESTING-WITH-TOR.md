# Guia de Testes com Rede Tor

## 🧅 O que é Tor?

Tor (The Onion Router) é uma rede de anonimato que roteia seu tráfego através de múltiplos servidores, mudando seu IP e ajudando a contornar bloqueios.

## Por que testar com Tor?

- ✅ Contornar bloqueios baseados em IP
- ✅ Evitar rate limiting do YouTube
- ✅ Mudar de IP automaticamente
- ✅ Bypass de restrições geográficas
- ✅ Gratuito e open-source

## 🚀 Como Iniciar o Tor

### Opção 1: Usando Docker Compose (RECOMENDADO)

```bash
# Iniciar apenas o serviço Tor
docker compose up -d tor-proxy

# Verificar status
docker ps | grep tor

# Ver logs
docker logs whisper-tor-proxy

# Testar conexão
curl --socks5 localhost:9050 https://check.torproject.org/api/ip
```

### Opção 2: Instalar Tor no Windows

```powershell
# Usando Chocolatey
choco install tor

# Ou baixar manualmente
# https://www.torproject.org/download/

# Iniciar serviço
tor
```

### Opção 3: Tor Browser Bundle (Mais fácil)

1. Baixe: https://www.torproject.org/download/
2. Instale e abra o Tor Browser
3. O proxy SOCKS5 estará disponível em `localhost:9150`

## 🧪 Executar Testes

### 1. Verificar se Tor está rodando

```bash
python -m pytest tests/integration/test_youtube_strategies_tor.py::TestTorConnectivity::test_tor_service_available -v -s
```

### 2. Verificar mudança de IP

```bash
python -m pytest tests/integration/test_youtube_strategies_tor.py::TestTorConnectivity::test_tor_ip_different -v -s
```

### 3. Testar estratégia específica com Tor

```bash
# Testar android_client com Tor
python -m pytest tests/integration/test_youtube_strategies_tor.py::TestYouTubeDownloadStrategiesWithTor::test_android_client_with_tor -v -s

# Testar android_music com Tor
python -m pytest tests/integration/test_youtube_strategies_tor.py::TestYouTubeDownloadStrategiesWithTor::test_android_music_with_tor -v -s
```

### 4. Teste Comparativo Completo (COM vs SEM Tor)

```bash
python -m pytest tests/integration/test_youtube_strategies_tor.py::TestYouTubeDownloadStrategiesWithTor::test_all_strategies_with_tor_summary -v -s
```

Este teste irá:
- ✅ Testar todas as 7 estratégias COM Tor
- ✅ Testar todas as 7 estratégias SEM Tor
- ✅ Comparar resultados
- ✅ Identificar quais melhoram com Tor
- ✅ Gerar relatórios JSON e TXT
- ✅ Recomendar melhor configuração

## 📊 Interpretar Resultados

### Cenário 1: Tor melhora resultados
```
SEM TOR: 2/7 funcionando
COM TOR: 6/7 funcionando

🎯 RECOMENDAÇÃO: Usar TOR
   Configure ENABLE_TOR_PROXY=true no .env
```

### Cenário 2: Tor piora resultados
```
SEM TOR: 5/7 funcionando
COM TOR: 2/7 funcionando

🎯 RECOMENDAÇÃO: NÃO usar TOR
   YouTube pode estar bloqueando exit nodes do Tor
```

### Cenário 3: Mesmos resultados
```
SEM TOR: 5/7 funcionando
COM TOR: 5/7 funcionando

🎯 RECOMENDAÇÃO: Indiferente
   Use Tor apenas se precisar de anonimato
```

## 🔧 Configurar Aplicação para Usar Tor

### 1. Editar `.env` ou `docker-compose.yml`

```bash
# Habilitar Tor
ENABLE_TOR_PROXY=true
TOR_PROXY_URL=socks5://tor-proxy:9050

# Se Tor estiver local (fora do Docker)
TOR_PROXY_URL=socks5://host.docker.internal:9050
```

### 2. Reiniciar aplicação

```bash
docker compose down
docker compose up -d
```

### 3. Verificar logs

```bash
docker logs whisper-transcription-api --follow

# Deve ver:
# INFO: Tor proxy enabled: socks5://tor-proxy:9050
# INFO: Using Tor for YouTube requests
```

## 🐛 Troubleshooting

### Erro: "Connection refused" (9050)

```bash
# Verificar se Tor está rodando
docker ps | grep tor
netstat -an | grep 9050  # Windows PowerShell

# Iniciar Tor
docker compose up -d tor-proxy
```

### Erro: "Timeout" com Tor

Tor pode ser lento. Aumentar timeouts:

```yaml
environment:
  - DOWNLOAD_TIMEOUT=1800  # 30 minutos
  - REQUEST_TIMEOUT=7200   # 2 horas
```

### Erro: "All circuits are down"

Tor ainda está estabelecendo conexões. Aguarde 30-60 segundos:

```bash
docker logs whisper-tor-proxy --follow
# Aguarde ver: "Bootstrapped 100%: Done"
```

### Tor muito lento

Configurar Tor para renovar circuito mais rápido:

```yaml
tor-proxy:
  environment:
    - TOR_MaxCircuitDirtiness=30  # Renovar a cada 30s
    - TOR_NewCircuitPeriod=15     # Tentar novo circuito a cada 15s
```

### YouTube detectando Tor

YouTube pode bloquear exit nodes conhecidos do Tor. Soluções:

1. **Usar bridges (obfs4)**:
   ```bash
   docker exec -it whisper-tor-proxy sh
   # Editar /etc/tor/torrc
   # Adicionar: UseBridges 1
   ```

2. **Rotacionar circuitos**:
   ```bash
   # Forçar novo circuito
   docker restart whisper-tor-proxy
   ```

3. **Combinar com User-Agent rotation**:
   ```bash
   ENABLE_USER_AGENT_ROTATION=true
   ENABLE_TOR_PROXY=true
   ```

## 📈 Métricas com Tor

Acessar métricas Prometheus:
- http://localhost:9090

Verificar:
- `youtube_tor_requests_total` - Total de requests via Tor
- `youtube_tor_success_rate` - Taxa de sucesso com Tor
- `youtube_proxy_latency_seconds` - Latência do Tor

## 🔒 Segurança e Privacidade

### Tor esconde:
✅ Seu IP real do YouTube
✅ Sua localização geográfica
✅ Padrões de uso

### Tor NÃO esconde:
❌ Conteúdo das requisições (use HTTPS)
❌ Identificação por cookies (limpe cache)
❌ Fingerprinting do navegador (use User-Agent rotation)

### Melhores práticas:
```bash
# Combinar Tor + User-Agent rotation + Rate limiting
ENABLE_TOR_PROXY=true
ENABLE_USER_AGENT_ROTATION=true
YOUTUBE_REQUESTS_PER_MINUTE=5  # Menos agressivo
```

## 🌍 Verificar País do Exit Node

```bash
# Via API
curl --socks5 localhost:9050 https://ipapi.co/json/

# Resultado exemplo:
{
  "ip": "185.220.101.34",
  "country": "DE",  # Alemanha
  "city": "Frankfurt",
  ...
}
```

## 📝 Relatórios Gerados

Após executar o teste comparativo completo:

1. **test_strategies_tor_report.json** - Dados estruturados
2. **test_strategies_tor_report.txt** - Relatório legível

### Exemplo de relatório:

```
RELATÓRIO DE TESTE: TOR vs DIRETO
================================================================================

Vídeo testado: https://www.youtube.com/watch?v=jNQXAC9IVRw
Data: 2024-01-23 14:30:00

COM TOR: 6/7 funcionando
  ✅ android_client (priority 1)
  ✅ android_music (priority 2)
  ✅ web_embed (priority 4)
  ✅ tv_embedded (priority 5)  # Melhorou com Tor!
  ✅ mweb (priority 6)
  ✅ default (priority 7)

SEM TOR: 5/7 funcionando
  ✅ android_client (priority 1)
  ✅ android_music (priority 2)
  ✅ web_embed (priority 4)
  ✅ mweb (priority 6)
  ✅ default (priority 7)

SÓ COM TOR: 1
  🧅 tv_embedded  # Esta estratégia SÓ funciona com Tor!

RECOMENDAÇÃO: Usar TOR
```

## 🎯 Exemplo Completo

```bash
# 1. Iniciar Tor
docker compose up -d tor-proxy

# 2. Aguardar 30 segundos para Tor conectar
sleep 30

# 3. Verificar conectividade
python -m pytest tests/integration/test_youtube_strategies_tor.py::TestTorConnectivity -v -s

# 4. Executar teste comparativo
python -m pytest tests/integration/test_youtube_strategies_tor.py::TestYouTubeDownloadStrategiesWithTor::test_all_strategies_with_tor_summary -v -s

# 5. Analisar relatórios
cat test_strategies_tor_report.txt

# 6. Se Tor melhorar, habilitar na aplicação
# Editar .env: ENABLE_TOR_PROXY=true

# 7. Reiniciar e testar
docker compose restart whisper-api
docker logs whisper-transcription-api --follow
```

## 🔗 Referências

- [Tor Project](https://www.torproject.org/)
- [Tor Docker Image](https://hub.docker.com/r/dperson/torproxy)
- [yt-dlp Proxy Support](https://github.com/yt-dlp/yt-dlp#network-options)
- [YouTube API Limits](https://developers.google.com/youtube/v3/getting-started#quota)
