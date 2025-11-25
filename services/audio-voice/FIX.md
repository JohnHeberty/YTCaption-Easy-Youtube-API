# 🔧 PLANO DE CORREÇÃO - Audio Voice Service
**Problema:** PermissionError ao tentar criar arquivo de log no Docker

---

## 📋 ANÁLISE DO ERRO

### Erro Identificado
```
PermissionError: [Errno 13] Permission denied: '/app/logs/audio-voice.log'
```

### Stack Trace Crítico
```python
File "/app/app/main.py", line 30, in <module>
    setup_logging("audio-voice", settings['log_level'])
File "/app/app/logging_config.py", line 41, in setup_logging
    file_handler = logging.FileHandler(
        log_dir / f"{service_name}.log",
```

### Causa Raiz Identificada

**PROBLEMA PRINCIPAL:** O diretório `/app/logs` existe no container Docker mas pertence ao usuário `root`, e a aplicação está rodando como `appuser` (UID 1000).

**ANÁLISE DA SEQUÊNCIA DE EXECUÇÃO:**

1. **Dockerfile (Build Time):**
   ```dockerfile
   RUN useradd -m -u 1000 appuser && \
       mkdir -p /app/logs && \
       chown -R appuser:appuser /app
   ```
   - ✅ Diretório `/app/logs` é criado
   - ✅ Ownership é dado para `appuser`

2. **Docker Compose (Runtime):**
   ```yaml
   volumes:
     - ./logs:/app/logs
   ```
   - ❌ **PROBLEMA:** Volume bind mount SOBRESCREVE o diretório criado no build
   - ❌ O diretório `./logs` do host é montado sobre `/app/logs` do container
   - ❌ Permissões do host são aplicadas (geralmente root:root)
   - ❌ `appuser` perde acesso de escrita

3. **Código Python (Runtime):**
   ```python
   log_dir = Path("./logs")
   log_dir.mkdir(exist_ok=True, parents=True)  # Falha se já existe sem permissão
   file_handler = logging.FileHandler(log_dir / "audio-voice.log")  # ❌ ERRO AQUI
   ```

**POR QUE O PROBLEMA PERSISTE:**

- O `chmod 777` no Dockerfile é aplicado ANTES do volume mount
- O volume mount SUBSTITUI o diretório inteiro
- As permissões do diretório do host (provavelmente root ou UID diferente) são preservadas
- `appuser` não tem permissão para criar arquivos no diretório montado

---

## 🎯 ESTRATÉGIAS DE CORREÇÃO

### ✅ Estratégia Escolhida: **Logging Condicional + Criação Segura de Diretório**

**Justificativa:**
1. Evita falhas críticas na inicialização
2. Permite logging mesmo sem volume
3. Compatível com agregadores de logs (Docker, K8s)
4. Segue best practices para containers

---

## 🚀 SPRINT DE CORREÇÃO

### **Sprint 1: Correção do logging_config.py**

**Objetivo:** Tornar o file logging opcional e não-bloqueante

**Arquivos Afetados:**
- `services/audio-voice/app/logging_config.py`

**Mudanças Necessárias:**

1. **Criar diretório de logs com tratamento de erro:**
   ```python
   # ANTES (linha 36-37)
   log_dir = Path("./logs")
   log_dir.mkdir(exist_ok=True, parents=True)
   
   # DEPOIS
   log_dir = Path("./logs")
   try:
       log_dir.mkdir(exist_ok=True, parents=True)
   except (PermissionError, OSError) as e:
       logger.warning(f"Cannot create log directory: {e}. File logging disabled.")
       log_dir = None
   ```

2. **Tornar file handler condicional:**
   ```python
   # ANTES (linhas 40-50)
   file_handler = logging.FileHandler(...)
   root_logger.addHandler(file_handler)
   
   # DEPOIS
   if log_dir and log_dir.exists() and os.access(log_dir, os.W_OK):
       try:
           file_handler = logging.FileHandler(...)
           root_logger.addHandler(file_handler)
           logger.info(f"File logging enabled: {log_dir / service_name}.log")
       except (PermissionError, OSError) as e:
           logger.warning(f"File logging disabled: {e}")
   else:
       logger.info("File logging disabled (directory not writable)")
   ```

**Benefícios:**
- ✅ Aplicação inicia mesmo sem permissão de escrita
- ✅ Logs continuam no stdout (Docker/K8s podem capturar)
- ✅ File logging é bonus, não requisito
- ✅ Mensagens claras sobre estado do logging

---

### **Sprint 2: Correção do Dockerfile**

**Objetivo:** Garantir que diretórios criados no build tenham permissões corretas

**Arquivos Afetados:**
- `services/audio-voice/Dockerfile`

**Mudanças Necessárias:**

1. **Remover `chmod 777` (inseguro):**
   ```dockerfile
   # ANTES
   RUN chmod -R 777 /app/uploads /app/processed /app/temp /app/logs /app/voice_profiles /app/models
   
   # DEPOIS
   # (remover linha - permissões já corretas com chown)
   ```

2. **Manter estrutura limpa:**
   ```dockerfile
   # User não-root (criar ANTES de copiar código)
   RUN useradd -m -u 1000 appuser && \
       mkdir -p /app/uploads /app/processed /app/temp /app/logs /app/voice_profiles /app/models && \
       chown -R appuser:appuser /app
   
   # Código (copiar DEPOIS de criar user)
   COPY --chown=appuser:appuser app/ ./app/
   COPY --chown=appuser:appuser run.py .
   
   USER appuser
   ```

**Benefícios:**
- ✅ Menos superfície de ataque (não usar 777)
- ✅ Ownership correto desde o build
- ✅ Compatível com volumes

---

### **Sprint 3: Atualização do docker-compose.yml**

**Objetivo:** Documentar comportamento de volumes

**Arquivos Afetados:**
- `services/audio-voice/docker-compose.yml`

**Mudanças Necessárias:**

1. **Adicionar comentário sobre permissões:**
   ```yaml
   volumes:
     - ./app:/app/app
     - ./uploads:/app/uploads
     - ./processed:/app/processed
     - ./temp:/app/temp
     - ./voice_profiles:/app/voice_profiles
     - ./models:/app/models
     # Nota: ./logs é criado pelo container se necessário
     # Se montar volume aqui, certifique-se que UID 1000 tem permissão de escrita
     - ./logs:/app/logs
   ```

2. **Alternativa: Criar diretórios no host com permissões corretas:**
   ```yaml
   # No compose, antes de services:
   # Execute no host: mkdir -p logs && chmod 777 logs
   ```

**Benefícios:**
- ✅ Documentação clara
- ✅ Usuários entendem comportamento
- ✅ Facilita troubleshooting

---

### **Sprint 4: Teste e Validação**

**Objetivo:** Garantir que serviço funciona em todos os cenários

**Cenários de Teste:**

1. **Teste 1: Container sem volume de logs**
   ```bash
   # Remover volume de logs do docker-compose.yml
   docker-compose down
   docker-compose build --no-cache
   docker-compose up
   # ✅ Esperado: Serviço inicia, logs apenas em stdout
   ```

2. **Teste 2: Container com volume de logs (permissão correta)**
   ```bash
   mkdir -p logs && chmod 777 logs
   docker-compose up
   # ✅ Esperado: Serviço inicia, logs em stdout E arquivo
   ```

3. **Teste 3: Container com volume de logs (permissão incorreta)**
   ```bash
   mkdir -p logs && chmod 000 logs
   docker-compose up
   # ✅ Esperado: Serviço inicia, logs apenas em stdout, warning sobre file logging
   ```

4. **Teste 4: Healthcheck funciona**
   ```bash
   docker-compose up -d
   docker-compose ps
   # ✅ Esperado: Container healthy
   curl http://localhost:8005/
   # ✅ Esperado: {"service": "audio-voice", "status": "running", "version": "1.0.0"}
   ```

---

## 📊 CHECKLIST DE IMPLEMENTAÇÃO

### Sprint 1: logging_config.py
- [ ] Adicionar import `os`
- [ ] Envolver `log_dir.mkdir()` em try/except
- [ ] Adicionar verificação `os.access(log_dir, os.W_OK)`
- [ ] Tornar criação de `file_handler` condicional
- [ ] Adicionar logs informativos sobre estado do file logging
- [ ] Testar localmente (sem Docker)

### Sprint 2: Dockerfile
- [ ] Remover linha `chmod -R 777`
- [ ] Verificar ordem: create user → mkdir → chown → COPY
- [ ] Validar que `USER appuser` está APÓS COPY
- [ ] Build e inspecionar permissões no container

### Sprint 3: docker-compose.yml
- [ ] Adicionar comentário sobre permissões de volumes
- [ ] (Opcional) Criar script init para criar diretórios no host

### Sprint 4: Testes
- [ ] Executar Teste 1 (sem volume)
- [ ] Executar Teste 2 (com permissão)
- [ ] Executar Teste 3 (sem permissão)
- [ ] Executar Teste 4 (healthcheck)
- [ ] Validar logs aparecem corretamente
- [ ] Validar API responde em todos os cenários

---

## 🎯 RESULTADO ESPERADO

Após implementação completa:

1. ✅ **Serviço inicia sempre**, independente de permissões de diretório
2. ✅ **Logs em stdout** funcionam em 100% dos casos (Docker/K8s podem capturar)
3. ✅ **Logs em arquivo** são bonus quando permissões estão corretas
4. ✅ **Mensagens claras** sobre estado do file logging
5. ✅ **Healthcheck passa** consistentemente
6. ✅ **Sem permissões 777** (segurança melhorada)
7. ✅ **Compatível com orchestrators** (K8s, Swarm, etc)

---

## 📝 NOTAS ADICIONAIS

### Por que não usar chmod 777?
- **Segurança:** Qualquer processo pode ler/escrever
- **Best Practice:** Containers devem usar least privilege
- **Auditoria:** Falha em compliance scans

### Por que logging em stdout é suficiente?
- **Docker:** `docker logs` captura stdout
- **Kubernetes:** Fluent, Fluentd, Loki capturam stdout
- **Cloud:** AWS CloudWatch, GCP Logging capturam stdout
- **Agregadores:** Elasticsearch, Splunk capturam stdout

### Alternativa: Sidecar de Logging
Para logs em arquivo obrigatórios:
```yaml
services:
  audio-voice-service:
    # ... configuração atual
  
  log-forwarder:
    image: fluent/fluentd
    volumes:
      - ./logs:/logs
    # Encaminha logs do container para arquivo
```

---

**Status:** 📋 PRONTO PARA IMPLEMENTAÇÃO
**Prioridade:** 🔴 CRÍTICA
**Impacto:** ⭐⭐⭐⭐⭐ (Bloqueador de inicialização)
**Complexidade:** ⚡ BAIXA (2-3 horas)
