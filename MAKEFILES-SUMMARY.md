# 📘 Resumo de Makefiles - YTCaption API

## 🎯 Visão Geral

Todos os microserviços agora possuem Makefiles padronizados com comandos consistentes.

## 📦 Serviços com Makefiles

### 1. **audio-normalization** (Porta 8003)
```bash
cd services/audio-normalization
make help              # Ver todos os comandos
make build             # Build Docker
make up                # Iniciar serviço
make down              # Parar serviço
make logs              # Ver logs
make health            # Testar health endpoint
make fix-permissions   # Corrigir permissões (uid 1000)
```

**Comandos Específicos:**
- `make logs-api` - Logs do container API
- `make logs-celery` - Logs do Celery worker
- `make shell-api` - Shell no container API
- `make shell-celery` - Shell no Celery worker

---

### 2. **youtube-search** (Porta 8001)
```bash
cd services/youtube-search
make help              # Ver todos os comandos
make build             # Build Docker
make up                # Iniciar serviço
make down              # Parar serviço
make logs              # Ver logs
make health            # Testar health endpoint
```

**Comandos Específicos:**
- `make search QUERY="python tutorial"` - Testar busca
- `make shorts` - Testar busca de shorts
- `make test-endpoints` - Rodar test_all_endpoints.sh
- `make test-shorts` - Rodar test_shorts_feature.sh

---

### 3. **audio-transcriber** (Porta 8002)
```bash
cd services/audio-transcriber
make help              # Ver todos os comandos
make build             # Build Docker
make up                # Iniciar serviço
make down              # Parar serviço
make logs              # Ver logs
make health            # Testar health endpoint
```

**Comandos Específicos:**
- `make model-download` - Baixar modelo Whisper
- `make model-test` - Testar modelo
- `make test-prod` - Teste de produção

---

### 4. **make-video** (Porta 8004)
```bash
cd services/make-video
make help              # Ver todos os comandos
make build             # Build Docker
make up                # Iniciar serviço
make down              # Parar serviço
make logs              # Ver logs
make health            # Testar health endpoint
```

**Comandos Específicos:**
- `make calibrate-start` - Iniciar calibração
- `make calibrate-watch` - Acompanhar calibração
- `make calibrate-status` - Status da calibração
- `make test-validate` - Validação completa

---

### 5. **video-downloader** (Porta 8005)
```bash
cd services/video-downloader
make help              # Ver todos os comandos
make build             # Build Docker
make up                # Iniciar serviço
make down              # Parar serviço
make logs              # Ver logs
make health            # Testar health endpoint
```

**Comandos Específicos:**
- `make download URL="https://youtube.com/watch?v=..."` - Testar download

---

### 6. **orchestrator** (Porta 8000)
```bash
cd orchestrator
make help              # Ver todos os comandos
make build             # Build Docker
make up                # Iniciar serviço
make down              # Parar serviço
make logs              # Ver logs
make health            # Testar health endpoint
make jobs              # Listar jobs ativos
```

**Comandos Específicos:**
- `make notebook` - Abrir Jupyter notebook
- `make test-sse` - Testar Server-Sent Events

---

## 🚀 Makefile Raiz (Gerenciamento Global)

O Makefile na raiz do projeto permite gerenciar TODOS os serviços:

```bash
cd /root/YTCaption-Easy-Youtube-API
make help                          # Ver todos comandos
make validate                      # Validar todos os serviços
make build-audio-normalization     # Build de um serviço específico
make up-audio-normalization        # Iniciar um serviço específico
make down-audio-normalization      # Parar um serviço específico
make logs-audio-normalization      # Ver logs de um serviço
make restart-audio-normalization   # Reiniciar um serviço
make status-audio-normalization    # Ver status de um serviço
```

### Comandos por Padrão

Substitua `{SERVICE}` por:
- `audio-normalization`
- `youtube-search`
- `audio-transcriber`
- `make-video`
- `video-downloader`
- `orchestrator`

**Comandos Disponíveis:**
- `make build-{SERVICE}` - Build
- `make up-{SERVICE}` - Iniciar
- `make down-{SERVICE}` - Parar
- `make restart-{SERVICE}` - Reiniciar
- `make logs-{SERVICE}` - Logs
- `make status-{SERVICE}` - Status
- `make validate-{SERVICE}` - Validar

**Comandos Globais:**
- `make check-ports` - Verificar portas em uso
- `make check-port-conflicts` - Detectar conflitos
- `make stop-port-8002` - Parar container em porta específica
- `make build-only-{SERVICE}` - Build sem iniciar

---

## 📊 Estrutura Padrão dos Makefiles

Todos os Makefiles seguem a mesma estrutura:

### 1. **Seção de Desenvolvimento**
- `venv` - Criar virtual environment
- `install` - Instalar dependências
- `dev` - Rodar em modo desenvolvimento (sem Docker)
- `shell` - Shell Python

### 2. **Seção de Testes**
- `test` - Todos os testes
- `test-unit` - Testes unitários
- `test-integration` - Testes de integração
- `test-coverage` - Testes com coverage

### 3. **Seção Docker**
- `build` - Build das imagens
- `up` - Subir containers
- `down` - Derrubar containers
- `restart` - Reiniciar
- `logs` - Ver logs
- `ps` - Listar containers

### 4. **Seção API**
- `health` - Verificar health
- `status` - Status completo
- Comandos específicos por serviço

### 5. **Seção Manutenção**
- `clean` - Limpar arquivos temporários
- `clean-all` - Limpar tudo
- `clean-docker` - Limpar imagens Docker
- `validate` - Validar configuração

### 6. **Utilitários**
- `shell-api` / `shell-container` - Shell no container
- `fix-permissions` - Corrigir permissões

---

## 🎯 Fluxo de Trabalho Recomendado

### Primeiro Setup
```bash
cd /root/YTCaption-Easy-Youtube-API
make validate                 # Validar tudo
make build-youtube-search     # Build do serviço
make up-youtube-search        # Iniciar
make logs-youtube-search      # Verificar logs
```

### Desenvolvimento Local
```bash
cd services/youtube-search
make install                  # Instalar dependências
make dev                      # Rodar localmente
```

### Deploy/Produção
```bash
cd /root/YTCaption-Easy-Youtube-API
make build-{SERVICE}
make up-{SERVICE}
make status-{SERVICE}
```

### Troubleshooting
```bash
make logs-{SERVICE}           # Ver logs
make restart-{SERVICE}        # Reiniciar
make down-{SERVICE}           # Parar
make clean-docker             # Limpar e rebuild
make build-{SERVICE}
make up-{SERVICE}
```

---

## 📋 Checklist de Validação

Após criar/modificar um serviço:

- [ ] Criar/Atualizar Makefile local
- [ ] Testar `make validate`
- [ ] Testar `make build`
- [ ] Testar `make up`
- [ ] Verificar health endpoint
- [ ] Atualizar Makefile raiz (se necessário)
- [ ] Commitar mudanças
- [ ] Documentar comandos específicos

---

## 🔧 Manutenção

### Limpar Tudo
```bash
cd /root/YTCaption-Easy-Youtube-API
make down-audio-normalization
make down-youtube-search
# ... outros serviços
docker system prune -af --volumes
```

### Rebuild Completo
```bash
make down-{SERVICE}
make clean-docker
make build-{SERVICE}
make up-{SERVICE}
```

---

## 📝 Notas

- **Portas Padrão:**
  - orchestrator: 8000
  - youtube-search: 8001
  - audio-transcriber: 8002
  - audio-normalization: 8003
  - make-video: 8004
  - video-downloader: 8005

- **Permissões:** Containers rodam como uid 1000 (appuser)
- **Redis:** Compartilhado em 192.168.1.110:6379
- **Logs:** Estruturados em JSON

---

## 🆘 Suporte

Ver ajuda de qualquer Makefile:
```bash
make help
```

Ver comandos do Makefile raiz:
```bash
cd /root/YTCaption-Easy-Youtube-API
make help
```
