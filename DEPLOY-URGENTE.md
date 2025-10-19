# 🚨 AÇÃO URGENTE - Deploy do Servidor

## ❌ PROBLEMA ATUAL

**O servidor está rodando código ANTIGO sem as correções!**

```
Servidor (192.168.18.104) → Código DESATUALIZADO
   ├─ ❌ Sem singleton pattern
   ├─ ❌ Sem worker pool
   ├─ ❌ Erro 500: "Unexpected error: "
   └─ ❌ Modo paralelo não funciona

Código Local → CORRIGIDO e pushed ✅
   ├─ ✅ Singleton pattern OK
   ├─ ✅ Worker pool OK
   ├─ ✅ Validações OK
   └─ ✅ Git pushed: commit d8c31de
```

---

## 🚀 SOLUÇÃO: Deploy em 3 Opções

### ⚡ OPÇÃO 1: Script Automático (Mais Rápido)

No PowerShell do Windows:

```powershell
cd "C:\Users\johnfreitas\Desktop\Nova pasta"
.\deploy-server.ps1
```

✅ O script faz tudo automaticamente!

---

### 🔧 OPÇÃO 2: Manual via SSH (Recomendado)

```bash
# 1. Conectar
ssh root@192.168.18.104

# 2. Ir para projeto
cd /root/YTCaption-Easy-Youtube-API  # AJUSTE SE NECESSÁRIO!

# 3. Deploy completo
docker-compose down && \
git pull origin main && \
docker-compose build --no-cache && \
docker-compose up -d

# 4. Ver logs (aguardar ~60s para workers carregarem)
docker-compose logs -f
```

**Aguarde até ver:**
```
[INFO] PARALLEL MODE ENABLED ← PROCURE POR ISSO!
[INFO] Worker 0 Model loaded
[INFO] Worker 1 Model loaded
```

---

### 📝 OPÇÃO 3: Seguir Guia Passo a Passo

Abra o arquivo: `deploy-server-manual.md`

---

## ✅ VALIDAÇÃO: Como Saber se Funcionou?

### 1. Logs de Startup DEVEM mostrar:

```log
✅ [INFO] Parallel Transcription: True
✅ [INFO] PARALLEL MODE ENABLED - Initializing persistent worker pool...
✅ [INFO] [WORKER POOL] Starting 2 persistent workers...
✅ [INFO] [WORKER 0] Model loaded successfully
✅ [INFO] [WORKER 1] Model loaded successfully
```

❌ Se **NÃO** aparecer isso: Problema no deploy!

### 2. Teste de Transcrição:

Faça uma nova requisição. Deve:
- ✅ Retornar 200 (não 500!)
- ✅ Processar em ~24s
- ✅ Logs mostram singleton: `service instance id=...`

---

## 🐛 TROUBLESHOOTING Rápido

### "Logs não mostram PARALLEL MODE ENABLED"

**Problema:** .env desatualizado

**Solução:**
```bash
ssh root@192.168.18.104
cd /root/YTCaption-Easy-Youtube-API
nano .env  # Adicione as linhas abaixo

# Adicionar:
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=2
PARALLEL_CHUNK_DURATION=120
AUDIO_LIMIT_SINGLE_CORE=300

# Salvar: Ctrl+X, Y, Enter
docker-compose restart
```

---

### "git pull" dá conflito

```bash
git stash  # Guarda mudanças locais
git pull origin main  # Atualiza
```

---

### "docker-compose não encontrado"

Tente sem hífen:
```bash
docker compose down
docker compose up -d
```

---

## 📊 STATUS DO CÓDIGO

| Item | Local | Servidor |
|------|-------|----------|
| Singleton fix | ✅ OK | ❌ Desatualizado |
| Worker pool | ✅ OK | ❌ Desatualizado |
| Validações | ✅ OK | ❌ Desatualizado |
| .env corrigido | ✅ OK | ❓ Verificar |
| Git commit | ✅ d8c31de pushed | ⏳ Precisa pull |

---

## 🎯 PRÓXIMOS PASSOS

1. **AGORA:** Deploy do servidor (escolha uma opção acima)
2. **Após deploy:** Validar logs (procurar "PARALLEL MODE ENABLED")
3. **Testar:** Fazer requisição e verificar erro 500 sumiu
4. **Monitorar:** Acompanhar logs por 5-10min

---

## ❓ DÚVIDAS?

Se algo não funcionar:

1. Capture os logs: `docker-compose logs > error.log`
2. Verifique: `cat .env | grep PARALLEL`
3. Verifique código: `git log -1`
4. Compartilhe essas informações!

---

**⏰ Tempo estimado do deploy: 3-5 minutos**

---

## 📚 Documentos Criados

1. ✅ `CODE-REVIEW-SOLID-CRITICAL.md` - Análise completa de código
2. ✅ `deploy-server.ps1` - Script automático PowerShell
3. ✅ `deploy-server-manual.md` - Guia detalhado passo a passo
4. ✅ `DEPLOY-URGENTE.md` - Este guia rápido

**Tudo commitado e pushed! Só falta atualizar o servidor! 🚀**
