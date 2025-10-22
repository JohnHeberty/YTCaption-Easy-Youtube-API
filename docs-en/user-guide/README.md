# 📘 User Guide

**Complete guide for YTCaption end users**

---

## 📚 Table of Contents

1. **[Quick Start](./01-quick-start.md)** ⚡  
   Get started in 5 minutes - installation + first transcription

2. **[Installation](./02-installation.md)** 🐳  
   Complete installation - Docker, Proxmox, bare metal

3. **[Configuration](./03-configuration.md)** ⚙️  
   All environment variables (.env) explained

4. **[API Usage](./04-api-usage.md)** 🌐  
   How to use the API - endpoints, parameters, examples

5. **[Troubleshooting](./05-troubleshooting.md)** 🔧  
   Common problems and solutions - 403 errors, network, OOM

6. **[Deployment](./06-deployment.md)** 🚀  
   Production deployment - Nginx, SSL, Docker Compose

7. **[Monitoring](./07-monitoring.md)** 📊  
   Monitoring - Grafana dashboards, Prometheus queries

---

## 🎯 Who is this guide for?

This guide is for **end users** who want to:
- ✅ Install and configure YTCaption
- ✅ Use the API to transcribe videos
- ✅ Solve common problems
- ✅ Deploy to production
- ✅ Monitor the application

**Not a developer?** This guide is perfect for you! 😊

---

## 🚀 Quick Links

| I want to... | Go to... |
|-------------|-----------|
| Get started now (5min) | [Quick Start](./01-quick-start.md) |
| Install with Docker | [Installation - Docker](./02-installation.md#docker) |
| Configure YouTube Resilience v3.0 | [Configuration - YouTube](./03-configuration.md#youtube-resilience-v30) |
| Make a transcription | [API Usage - Transcribe](./04-api-usage.md#post-transcribe) |
| Fix 403 error | [Troubleshooting - 403](./05-troubleshooting.md#http-403-forbidden) |
| Deploy with Nginx | [Deployment - Nginx](./06-deployment.md#nginx-reverse-proxy) |
| View metrics | [Monitoring - Grafana](./07-monitoring.md#grafana-dashboards) |

---

## 💡 Tip: Reading Order

**First time using YTCaption?**

1. Read [Quick Start](./01-quick-start.md) (5min)
2. Make your first transcription
3. Read [Configuration](./03-configuration.md) to adjust
4. If you have problems: [Troubleshooting](./05-troubleshooting.md)

**Preparing for production?**

1. Read complete [Configuration](./03-configuration.md)
2. Configure YouTube Resilience v3.0
3. Read [Deployment](./06-deployment.md)
4. Configure [Monitoring](./07-monitoring.md)

---

## 🆕 What's New in v3.0

### YouTube Resilience System

System with 5 layers of protection against blocking:
- DNS Resilience
- Multi-Strategy Download (7 strategies)
- Rate Limiting + Circuit Breaker
- User-Agent Rotation (17 UAs)
- Tor Proxy Integration

**Result**: Success rate 60% → 95%

📖 [Complete configuration](./03-configuration.md#youtube-resilience-v30)

---

## 📞 Need Help?

- **Technical problem?** → [Troubleshooting](./05-troubleshooting.md)
- **Want to contribute?** → [Developer Guide](../developer-guide/)
- **GitHub issue**: [Open issue](https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/issues)

---

**[← Back to main documentation](../README.md)**
