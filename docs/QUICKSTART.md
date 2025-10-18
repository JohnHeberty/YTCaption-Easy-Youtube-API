# ⚡ Quick Start Guide

## 🚀 Início Rápido (5 minutos)

### 1️⃣ Configurar Ambiente

```bash
# Copiar arquivo de configuração
cp .env.example .env
```

### 2️⃣ Executar com Docker

```bash
# Subir a aplicação
docker-compose up -d

# Aguardar ~500 segundos para inicialização...

# Verificar se está rodando
curl http://localhost:8000/health
```

### 3️⃣ Testar Transcrição

```bash
# Teste simples (vídeo curto)
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"
  }'
```

### 4️⃣ Ver Documentação

Abra no navegador: **http://localhost:8000/docs**

---

## 📋 Comandos Mais Usados

### Docker
```bash
docker-compose up -d        # Iniciar
docker-compose down         # Parar
docker-compose logs -f      # Ver logs
docker-compose restart      # Reiniciar
docker-compose ps           # Status
```

### Health Check
```bash
curl http://localhost:8000/health
```

### Transcrever Vídeo
```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "SUA_URL_AQUI"}'
```

---

## 🔧 Troubleshooting Rápido

### Container não inicia?
```bash
docker-compose logs       # Ver erro
docker-compose down       # Parar tudo
docker-compose up -d      # Tentar novamente
```

### Porta 8000 ocupada?
```bash
# Editar docker-compose.yml
# Mudar: "8000:8000" para "8001:8000"
docker-compose up -d
```

### Disco cheio?
```bash
docker system prune -a --volumes  # Limpar Docker
rm -rf temp/*                     # Limpar temporários
```

---

## 📚 Próximos Passos

1. ✅ Ler **README.md** completo
2. ✅ Explorar **docs/examples.md**
3. ✅ Ver **docs/deployment.md** para produção
4. ✅ Consultar **docs/whisper-guide.md** para otimizações

---

**🎉 Você está pronto para usar a API!**
