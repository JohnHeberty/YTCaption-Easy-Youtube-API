# 📘 User Guide

**Guia completo para usuários finais do YTCaption**

---

## 📚 Índice

1. **[Quick Start](./01-quick-start.md)** ⚡  
   Comece em 5 minutos - instalação + primeira transcrição

2. **[Installation](./02-installation.md)** 🐳  
   Instalação completa - Docker, Proxmox, bare metal

3. **[Configuration](./03-configuration.md)** ⚙️  
   Todas as variáveis de ambiente (.env) explicadas

4. **[API Usage](./04-api-usage.md)** 🌐  
   Como usar a API - endpoints, parâmetros, exemplos

5. **[Troubleshooting](./05-troubleshooting.md)** 🔧  
   Problemas comuns e soluções - erros 403, network, OOM

6. **[Deployment](./06-deployment.md)** 🚀  
   Deploy em produção - Nginx, SSL, Docker Compose

7. **[Monitoring](./07-monitoring.md)** 📊  
   Monitoramento - Grafana dashboards, Prometheus queries

---

## 🎯 Para quem é este guia?

Este guia é para **usuários finais** que querem:
- ✅ Instalar e configurar o YTCaption
- ✅ Usar a API para transcrever vídeos
- ✅ Resolver problemas comuns
- ✅ Fazer deploy em produção
- ✅ Monitorar a aplicação

**Não é desenvolvedor?** Este guia é perfeito para você! 😊

---

## 🚀 Quick Links

| Eu quero... | Ir para... |
|-------------|-----------|
| Começar agora (5min) | [Quick Start](./01-quick-start.md) |
| Instalar com Docker | [Installation - Docker](./02-installation.md#docker) |
| Configurar YouTube Resilience v3.0 | [Configuration - YouTube](./03-configuration.md#youtube-resilience-v30) |
| Fazer uma transcrição | [API Usage - Transcribe](./04-api-usage.md#post-transcribe) |
| Resolver erro 403 | [Troubleshooting - 403](./05-troubleshooting.md#http-403-forbidden) |
| Deploy com Nginx | [Deployment - Nginx](./06-deployment.md#nginx-reverse-proxy) |
| Ver métricas | [Monitoring - Grafana](./07-monitoring.md#grafana-dashboards) |

---

## 💡 Dica: Ordem de Leitura

**Primeira vez usando YTCaption?**

1. Leia [Quick Start](./01-quick-start.md) (5min)
2. Faça sua primeira transcrição
3. Leia [Configuration](./03-configuration.md) para ajustar
4. Se tiver problemas: [Troubleshooting](./05-troubleshooting.md)

**Preparando para produção?**

1. Leia [Configuration](./03-configuration.md) completo
2. Configure YouTube Resilience v3.0
3. Leia [Deployment](./06-deployment.md)
4. Configure [Monitoring](./07-monitoring.md)

---

## 🆕 Novidades v3.0

### YouTube Resilience System

Sistema com 5 camadas de proteção contra bloqueios:
- DNS Resilience
- Multi-Strategy Download (7 estratégias)
- Rate Limiting + Circuit Breaker
- User-Agent Rotation (17 UAs)
- Tor Proxy Integration

**Resultado**: Taxa de sucesso 60% → 95%

📖 [Configuração completa](./03-configuration.md#youtube-resilience-v30)

---

## 📞 Precisa de Ajuda?

- **Problema técnico?** → [Troubleshooting](./05-troubleshooting.md)
- **Quer contribuir?** → [Developer Guide](../developer-guide/)
- **Issue no GitHub**: [Abrir issue](https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/issues)

---

**[← Voltar para documentação principal](../README.md)**
