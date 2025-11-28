# 🚀 Guia de Aplicação - Otimização de Disco

Este guia mostra **passo a passo** como aplicar as otimizações do Dockerfile e evitar o estouro de disco que corrompeu sua VM.

---

## 📋 PRÉ-REQUISITOS

Antes de começar:

- [ ] Acesso root ao servidor Ubuntu
- [ ] Docker instalado
- [ ] Backup ou snapshot da VM atual
- [ ] Pelo menos 30 GB livres no disco antes do build

---

## 🔧 ETAPA 1: PREPARAÇÃO DA INFRAESTRUTURA

### 1.1 Verificar Espaço Disponível

```bash
# Verifica espaço atual
df -h

# Verifica uso do Docker
du -sh /var/lib/docker
docker system df
```

### 1.2 Limpar Docker Atual (RECOMENDADO)

```bash
# Parar containers
docker-compose down

# Remover imagens antigas
docker system prune -af --volumes

# Verificar novamente
df -h
```

### 1.3 Configurar Partição Separada para Docker (OPCIONAL, MAS RECOMENDADO)

⚠️ **ATENÇÃO:** Só faça isso se tiver espaço LVM disponível!

```bash
# Verifica espaço LVM disponível
sudo vgs
sudo lvs

# Cria partição de 100 GB para Docker (ajuste conforme necessário)
sudo lvcreate -L 100G -n docker_lv ubuntu-vg
sudo mkfs.ext4 /dev/ubuntu-vg/docker_lv

# Backup do Docker atual
sudo systemctl stop docker
sudo mv /var/lib/docker /var/lib/docker.backup

# Monta nova partição
sudo mkdir -p /var/lib/docker
sudo mount /dev/ubuntu-vg/docker_lv /var/lib/docker

# Adiciona ao fstab
echo '/dev/ubuntu-vg/docker_lv /var/lib/docker ext4 defaults 0 2' | sudo tee -a /etc/fstab

# Restaura dados (se necessário)
sudo rsync -avh /var/lib/docker.backup/ /var/lib/docker/

# Reinicia Docker
sudo systemctl start docker
```

### 1.4 Configurar Monitoramento Automático

```bash
# Copia script de monitoramento
sudo cp scripts/check-disk.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/check-disk.sh

# Configura email de alerta (opcional)
export ALERT_EMAIL="seu-email@example.com"

# Testa o script
sudo /usr/local/bin/check-disk.sh 80

# Adiciona ao crontab (verifica a cada 15 minutos)
(crontab -l 2>/dev/null; echo "*/15 * * * * /usr/local/bin/check-disk.sh 80") | crontab -
```

### 1.5 Configurar Limpeza Automática do Docker

```bash
# Adiciona prune diário às 3h da manhã
(crontab -l 2>/dev/null; echo "0 3 * * * docker system prune -af --volumes --filter 'until=48h'") | crontab -
```

---

## 📦 ETAPA 2: APLICAR OTIMIZAÇÕES DO DOCKERFILE

### 2.1 Backup do Dockerfile Atual

```bash
cd services/audio-voice

# Backup
cp Dockerfile Dockerfile.backup.$(date +%Y%m%d)
cp .dockerignore .dockerignore.backup.$(date +%Y%m%d)
```

### 2.2 Aplicar Novos Arquivos

```bash
# Aplica Dockerfile otimizado
cp Dockerfile.optimized Dockerfile

# Aplica .dockerignore otimizado
cp .dockerignore.optimized .dockerignore
```

### 2.3 Verificar Mudanças

```bash
# Compara arquivos
diff Dockerfile.backup.* Dockerfile
diff .dockerignore.backup.* .dockerignore
```

---

## 🏗️ ETAPA 3: BUILD DA NOVA IMAGEM

### 3.1 Ativar BuildKit (Mais Eficiente)

```bash
export DOCKER_BUILDKIT=1
```

### 3.2 Build com Monitoramento

Abra **dois terminais**:

**Terminal 1 (Build):**
```bash
cd services/audio-voice

# Build da nova imagem
docker build \
  --target runtime \
  --tag audio-voice:3.0.0 \
  --tag audio-voice:latest \
  .
```

**Terminal 2 (Monitoramento):**
```bash
# Monitora uso de disco em tempo real
watch -n 5 'df -h | grep -E "Filesystem|/dev/mapper"; echo ""; docker system df'
```

### 3.3 Verificar Tamanho da Imagem

```bash
# Compara tamanho das imagens
docker images | grep audio-voice

# Detalhes da nova imagem
docker history audio-voice:3.0.0
```

---

## 🎯 ETAPA 4: CONFIGURAR VOLUMES PERSISTENTES

### 4.1 Criar docker-compose.yml Atualizado

```yaml
# docker-compose.yml
version: '3.8'

services:
  audio-voice:
    image: audio-voice:3.0.0
    container_name: audio-voice-service
    restart: unless-stopped
    
    # Runtime NVIDIA
    runtime: nvidia
    
    environment:
      # Cache de modelos em volumes persistentes
      - TRANSFORMERS_CACHE=/app/models/transformers
      - HF_HOME=/app/models/huggingface
      - COQUI_TTS_CACHE=/app/models/coqui
      - TORCH_HOME=/app/models/torch
    
    volumes:
      # Volume PERSISTENTE para modelos (não no build!)
      - models_cache:/app/models
      
      # Volumes de trabalho
      - ./uploads:/app/uploads
      - ./processed:/app/processed
      - ./temp:/app/temp
      - ./logs:/app/logs
    
    ports:
      - "8005:8005"
    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8005/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 90s

volumes:
  models_cache:
    driver: local
```

### 4.2 Primeiro Deploy com Download de Modelos

```bash
# Sobe container
docker-compose up -d

# Aguarda container iniciar
docker-compose logs -f

# Baixa modelos (primeira vez)
docker-compose exec audio-voice python scripts/download_models.py

# Verifica se modelos foram baixados
docker-compose exec audio-voice ls -lh /app/models/
```

---

## ✅ ETAPA 5: VALIDAÇÃO E TESTES

### 5.1 Testes Básicos

```bash
# Verifica status
docker-compose ps

# Testa healthcheck
curl http://localhost:8005/health

# Verifica logs
docker-compose logs --tail=50
```

### 5.2 Teste de Geração de Áudio (Smoke Test)

```bash
# Teste XTTS básico
curl -X POST http://localhost:8005/api/v1/tts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Olá, este é um teste.",
    "language": "pt",
    "speaker": "default"
  }' \
  -o test_output.wav
```

### 5.3 Monitoramento Pós-Deploy

```bash
# Uso de recursos
docker stats audio-voice-service

# Uso de disco
du -sh /var/lib/docker
docker system df

# Verifica se não está lotando
df -h
```

---

## 🔄 ROLLBACK (Se Necessário)

Se algo der errado:

```bash
cd services/audio-voice

# Para container
docker-compose down

# Restaura Dockerfile antigo
cp Dockerfile.backup.$(ls -t Dockerfile.backup.* | head -1) Dockerfile
cp .dockerignore.backup.$(ls -t .dockerignore.backup.* | head -1) .dockerignore

# Rebuild com versão antiga
docker build -t audio-voice:rollback .

# Atualiza docker-compose.yml
sed -i 's/audio-voice:3.0.0/audio-voice:rollback/' docker-compose.yml

# Sobe novamente
docker-compose up -d
```

---

## 📊 CHECKLIST DE VALIDAÇÃO

Depois de aplicar todas as mudanças:

- [ ] Imagem build com sucesso
- [ ] Tamanho da imagem reduzido (comparar com `docker images`)
- [ ] Container inicia corretamente
- [ ] Healthcheck OK (`curl http://localhost:8005/health`)
- [ ] Modelos baixados com sucesso
- [ ] Geração de áudio funciona (smoke test)
- [ ] Monitoramento de disco ativo (`crontab -l`)
- [ ] Limpeza automática configurada
- [ ] Uso de disco estável após 24h
- [ ] Logs sem erros críticos

---

## 🆘 TROUBLESHOOTING

### Problema: Build ainda lotando disco

```bash
# Verifica espaço ANTES de buildar
df -h

# Limpa TUDO do Docker
docker system prune -af --volumes

# Build com log detalhado
DOCKER_BUILDKIT=1 docker build --progress=plain -t audio-voice:3.0.0 . 2>&1 | tee build.log
```

### Problema: Modelos não baixam

```bash
# Entra no container
docker-compose exec audio-voice bash

# Baixa manualmente
python scripts/download_models.py

# Verifica permissões
ls -lha /app/models/
```

### Problema: Container não inicia

```bash
# Logs completos
docker-compose logs --tail=200

# Verifica variáveis de ambiente
docker-compose exec audio-voice env | grep -E "CACHE|HOME|TORCH"

# Verifica volumes
docker volume inspect audio-voice_models_cache
```

---

## 📞 SUPORTE

Para problemas não cobertos neste guia:

1. Verifique logs: `docker-compose logs`
2. Consulte `DISK_OPTIMIZATION_REPORT.md`
3. Rode `scripts/check-disk.sh` para diagnóstico
4. Abra issue no repositório com output dos comandos acima

---

**Última atualização:** 28/11/2025  
**Autor:** Guia de Aplicação - Audio Voice Service
