# 🚀 Deploy Manual - Guia Passo a Passo

## 📋 Pré-requisitos

1. ✅ Código commitado e pushed para `origin/main`
2. ✅ Acesso SSH ao servidor (192.168.18.104)
3. ✅ Docker e Docker Compose instalados no servidor

---

## 🔧 Opção 1: Deploy via SSH (Recomendado)

### Passo 1: Conectar ao Servidor

```bash
ssh root@192.168.18.104
```

### Passo 2: Navegar até o Projeto

```bash
cd /root/YTCaption-Easy-Youtube-API  # Ajuste o caminho se necessário
```

### Passo 3: Parar Containers

```bash
docker-compose down
```

### Passo 4: Atualizar Código

```bash
git pull origin main
```

**Verificar se atualizou:**
```bash
git log -1 --oneline
# Deve mostrar: "fix: correções singleton e parallel mode" ou similar
```

### Passo 5: Rebuild (OBRIGATÓRIO!)

```bash
docker-compose build --no-cache
```

⚠️ **IMPORTANTE:** O `--no-cache` é necessário para garantir que o código novo seja usado!

### Passo 6: Iniciar Containers

```bash
docker-compose up -d
```

### Passo 7: Verificar Logs

```bash
docker-compose logs -f
```

**Procure por estas mensagens:**
```
[INFO] Parallel Transcription: True
[INFO] PARALLEL MODE ENABLED - Initializing persistent worker pool...
[INFO] [WORKER POOL] Starting 2 persistent workers...
[INFO] [WORKER 0] Process started (PID: ...)
[INFO] [WORKER 0] Loading Whisper model 'base' on cpu...
[INFO] [WORKER 0] Model loaded successfully
[INFO] [WORKER 1] Process started (PID: ...)
[INFO] [WORKER 1] Loading Whisper model 'base' on cpu...
[INFO] [WORKER 1] Model loaded successfully
[INFO] Worker pool started successfully
```

✅ Se viu essas mensagens: **DEPLOY OK!**  
❌ Se NÃO viu: Algo deu errado, veja troubleshooting abaixo

---

## 🔧 Opção 2: Deploy via Script PowerShell

No Windows:

```powershell
.\deploy-server.ps1
```

---

## 🐛 Troubleshooting

### Problema: Logs não mostram "PARALLEL MODE ENABLED"

**Causa:** `.env` desatualizado no servidor

**Solução:**
```bash
# No servidor
cd /root/YTCaption-Easy-Youtube-API

# Verificar .env
cat .env | grep PARALLEL

# Deve ter:
# ENABLE_PARALLEL_TRANSCRIPTION=true
# PARALLEL_WORKERS=2
# PARALLEL_CHUNK_DURATION=120
# AUDIO_LIMIT_SINGLE_CORE=300

# Se não tiver, edite:
nano .env

# Adicione as linhas acima e salve (Ctrl+X, Y, Enter)

# Reinicie containers
docker-compose down
docker-compose up -d
```

---

### Problema: "Git pull" falha com "conflito"

**Causa:** Mudanças locais no servidor conflitam com remote

**Solução:**
```bash
# Backup das mudanças locais
git stash

# Atualizar
git pull origin main

# Se quiser restaurar mudanças locais (cuidado!)
# git stash pop
```

---

### Problema: "docker-compose: command not found"

**Causa:** Docker Compose não instalado ou nome diferente

**Solução:**
```bash
# Tentar versão v2 (plugin)
docker compose down  # Sem hífen

# Se não funcionar, instalar:
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Ou versão standalone
sudo curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

---

### Problema: Containers não iniciam após rebuild

**Causa:** Erro no código ou dependências

**Solução:**
```bash
# Ver logs completos
docker-compose logs

# Ver logs de um serviço específico
docker-compose logs app

# Ver status dos containers
docker-compose ps
```

---

## 📊 Validação Pós-Deploy

### 1. Verificar Logs de Startup

```bash
docker-compose logs | grep -E "PARALLEL|Worker|Model loaded"
```

**Esperado:**
- ✅ "PARALLEL MODE ENABLED"
- ✅ "Starting 2 persistent workers"
- ✅ "Worker 0 Model loaded"
- ✅ "Worker 1 Model loaded"

### 2. Verificar Containers Rodando

```bash
docker-compose ps
```

**Esperado:**
```
NAME                    STATE    PORTS
ytcaption_app           Up       0.0.0.0:8000->8000/tcp
```

### 3. Testar Endpoint

```bash
curl http://192.168.18.104:8000/api/v1/health
```

**Esperado:**
```json
{"status": "healthy", "parallel_mode": true, "workers": 2}
```

### 4. Fazer Transcrição de Teste

```bash
curl -X POST http://192.168.18.104:8000/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=s1-XF-FDvjc",
    "language": "pt",
    "use_youtube_transcript": false
  }'
```

**Esperado:**
- ✅ Status 200 (não 500!)
- ✅ Logs mostram processamento paralelo
- ✅ Tempo: ~24s (vs ~70s single-core)

---

## 🎯 Checklist Completo

### Antes do Deploy:
- [ ] Código commitado localmente
- [ ] `git push origin main` executado
- [ ] Backup dos logs atuais do servidor (opcional)

### Durante o Deploy:
- [ ] `docker-compose down` - Parar containers
- [ ] `git pull origin main` - Atualizar código
- [ ] `docker-compose build --no-cache` - Rebuild
- [ ] `docker-compose up -d` - Iniciar
- [ ] Aguardar ~60s (workers carregarem modelo)

### Após o Deploy:
- [ ] Logs mostram "PARALLEL MODE ENABLED"
- [ ] 2 workers iniciados
- [ ] Modelo carregado 2x
- [ ] Health check retorna OK
- [ ] Transcrição de teste funciona (200, não 500)
- [ ] Tempo reduzido (24s vs 70s)

---

## 🚀 Comandos de Atalho

### Deploy Completo (One-liner):
```bash
ssh root@192.168.18.104 'cd /root/YTCaption-Easy-Youtube-API && docker-compose down && git pull origin main && docker-compose build --no-cache && docker-compose up -d && docker-compose logs -f'
```

### Ver Logs em Tempo Real:
```bash
ssh root@192.168.18.104 'cd /root/YTCaption-Easy-Youtube-API && docker-compose logs -f'
```

### Restart Rápido:
```bash
ssh root@192.168.18.104 'cd /root/YTCaption-Easy-Youtube-API && docker-compose restart'
```

---

## ❓ Dúvidas?

Se algo não funcionar:

1. Capture os logs:
   ```bash
   docker-compose logs > deploy-error.log
   ```

2. Verifique o .env:
   ```bash
   cat .env
   ```

3. Verifique a versão do código:
   ```bash
   git log -3 --oneline
   ```

4. Compartilhe essas informações para análise!

---

**Boa sorte com o deploy! 🚀**
