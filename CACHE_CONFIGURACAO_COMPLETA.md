# ⚙️ Sistema de Cache Configurável - Ambos os Microserviços

## 📋 Resumo das Mudanças

Implementado sistema de cache **totalmente configurável** via variáveis de ambiente em **AMBOS** os microserviços:

✅ **video-download-service** (porta 8000)  
✅ **audio-normalization-service** (porta 8001)

## 🔧 Variáveis de Ambiente Adicionadas

### CACHE_TTL_HOURS
- **Descrição**: Tempo de vida (TTL) dos jobs no Redis
- **Padrão**: `24` (24 horas)
- **Onde afeta**:
  - Redis: TTL das chaves (auto-expiração)
  - Job.expires_at: Timestamp de expiração
  - Celery: result_expires (apenas video-download)

### CLEANUP_INTERVAL_MINUTES
- **Descrição**: Intervalo entre execuções da limpeza automática
- **Padrão**: `30` (30 minutos)
- **Onde afeta**:
  - Loop de cleanup: Frequência de verificação e remoção de jobs expirados

## 📁 Arquivos Modificados

### 🎬 video-download-service

#### 1. `app/redis_store.py`
```python
# Inicialização
self.cache_ttl_hours = int(os.getenv('CACHE_TTL_HOURS', '24'))
self.cleanup_interval_minutes = int(os.getenv('CLEANUP_INTERVAL_MINUTES', '30'))

# save_job()
ttl_seconds = self.cache_ttl_hours * 3600
self.redis.setex(key, ttl_seconds, data)

# _cleanup_loop()
cleanup_interval_seconds = self.cleanup_interval_minutes * 60
await asyncio.sleep(cleanup_interval_seconds)
```

#### 2. `app/celery_config.py`
```python
# TTL do cache em segundos (converte de horas)
CACHE_TTL_HOURS = int(os.getenv('CACHE_TTL_HOURS', '24'))
RESULT_EXPIRES_SECONDS = CACHE_TTL_HOURS * 3600

celery_app.conf.update(
    result_expires=RESULT_EXPIRES_SECONDS,  # Configurável
)
```

#### 3. `docker-compose.yml`
```yaml
video-download-service:
  environment:
    - CACHE_TTL_HOURS=24
    - CLEANUP_INTERVAL_MINUTES=30

celery-worker:
  environment:
    - CACHE_TTL_HOURS=24
    - CLEANUP_INTERVAL_MINUTES=30
```

#### 4. `.env.example`
```bash
CACHE_TTL_HOURS=24
CLEANUP_INTERVAL_MINUTES=30
```

### 🎵 audio-normalization-service

#### 1. `app/redis_store.py`
```python
# Inicialização (idêntico ao video-download)
self.cache_ttl_hours = int(os.getenv('CACHE_TTL_HOURS', '24'))
self.cleanup_interval_minutes = int(os.getenv('CLEANUP_INTERVAL_MINUTES', '30'))

# save_job() (idêntico)
ttl_seconds = self.cache_ttl_hours * 3600
self.redis.setex(key, ttl_seconds, data)

# _cleanup_loop() (idêntico)
cleanup_interval_seconds = self.cleanup_interval_minutes * 60
await asyncio.sleep(cleanup_interval_seconds)
```

#### 2. `app/models.py`
```python
# create_new() - calcula expires_at
cache_ttl_hours = int(os.getenv('CACHE_TTL_HOURS', '24'))
expires_at = datetime.now() + timedelta(hours=cache_ttl_hours)
```

#### 3. `docker-compose.yml`
```yaml
audio-normalization-service:
  environment:
    - CACHE_TTL_HOURS=24
    - CLEANUP_INTERVAL_MINUTES=30

celery-worker:
  environment:
    - CACHE_TTL_HOURS=24
    - CLEANUP_INTERVAL_MINUTES=30
```

#### 4. `.env.example`
```bash
CACHE_TTL_HOURS=24
CLEANUP_INTERVAL_MINUTES=30
```

## 🔄 Sincronização entre Camadas

### video-download-service
```
CACHE_TTL_HOURS=24
    ↓
┌───────────────────────────────────────┐
│ 1. redis_store.py                     │
│    - Redis TTL: 24h (auto-expira)     │
│    - Job.expires_at: now + 24h        │
├───────────────────────────────────────┤
│ 2. celery_config.py                   │
│    - result_expires: 86400s           │
├───────────────────────────────────────┤
│ 3. cleanup_expired()                  │
│    - Remove se expires_at < now       │
│    - Deleta arquivos físicos          │
└───────────────────────────────────────┘
```

### audio-normalization-service
```
CACHE_TTL_HOURS=24
    ↓
┌───────────────────────────────────────┐
│ 1. models.py                          │
│    - Job.expires_at = now + 24h       │
├───────────────────────────────────────┤
│ 2. redis_store.py                     │
│    - Redis TTL: 24h (auto-expira)     │
│    - Sincroniza com Job.expires_at    │
├───────────────────────────────────────┤
│ 3. cleanup_expired()                  │
│    - Remove se expires_at < now       │
│    - Deleta arquivos processados      │
└───────────────────────────────────────┘
```

## 🎯 Cenários de Configuração

### 🔧 Desenvolvimento
```bash
# Cache curto, limpeza frequente (teste rápido)
CACHE_TTL_HOURS=1
CLEANUP_INTERVAL_MINUTES=5
```

### 🚀 Produção Padrão
```bash
# Cache de 1 dia, limpeza a cada 30min (balanceado)
CACHE_TTL_HOURS=24
CLEANUP_INTERVAL_MINUTES=30
```

### ⚡ Produção Alta Performance
```bash
# Cache de 2 dias, limpeza a cada hora (menos overhead)
CACHE_TTL_HOURS=48
CLEANUP_INTERVAL_MINUTES=60
```

### 💾 Produção Economia de Espaço
```bash
# Cache de 12h, limpeza frequente (libera espaço rápido)
CACHE_TTL_HOURS=12
CLEANUP_INTERVAL_MINUTES=15
```

### 🧪 Testes Automatizados
```bash
# Cache muito curto para testar comportamento
CACHE_TTL_HOURS=0.5  # 30 minutos
CLEANUP_INTERVAL_MINUTES=1
```

## 📊 Impacto das Configurações

| Cenário | TTL | Cleanup | Uso Disco | Cache Hit | Overhead | Recomendado para |
|---------|-----|---------|-----------|-----------|----------|------------------|
| Dev | 1h | 5min | Baixo | Médio | Alto | Desenvolvimento local |
| Produção Econômica | 12h | 15min | Médio | Alto | Médio | Espaço limitado |
| Produção Padrão | 24h | 30min | Médio-Alto | Muito Alto | Baixo | Uso geral |
| Alta Performance | 48h | 60min | Alto | Máximo | Mínimo | Alta demanda |

## ✅ Como Aplicar as Mudanças

### 1️⃣ Criar arquivos .env (se não existirem)

**video-download-service**:
```bash
cd services/video-download
cp .env.example .env
```

**audio-normalization-service**:
```bash
cd services/audio-normalization
cp .env.example .env
```

### 2️⃣ Editar valores (opcional)
```bash
# Editar conforme necessidade
notepad .env
```

### 3️⃣ Restartar serviços

**video-download-service**:
```bash
cd services/video-download
docker-compose down
docker-compose up -d
```

**audio-normalization-service**:
```bash
cd services/audio-normalization
docker-compose down
docker-compose up -d
```

### 4️⃣ Verificar logs

**video-download**:
```bash
docker logs video-download-api | grep "Cache TTL"
# Deve mostrar: ⏰ Cache TTL: 24h, Cleanup: 30min
```

**audio-normalization**:
```bash
docker logs audio-normalization-api | grep "Cache TTL"
# Deve mostrar: ⏰ Cache TTL: 24h, Cleanup: 30min
```

## 🔍 Validação de Funcionamento

### Verificar Redis TTL
```bash
# video-download
docker exec video-download-redis redis-cli TTL "job:VIDEO_ID_quality"

# audio-normalization
docker exec audio-normalization-redis redis-cli TTL "audio_job:HASH_ops"

# Deve retornar tempo em segundos (ex: 86400 para 24h)
```

### Monitorar Cleanup
```bash
# video-download
docker logs video-download-celery | grep "Limpeza: removidos"

# audio-normalization
docker logs audio-normalization-celery | grep "Removidos"
```

### Testar Cache Hit
```bash
# video-download - requisição duplicada deve retornar mesmo job_id
curl -X POST http://localhost:8000/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=dQw4w9WgXcQ", "quality": "720p"}'

# audio-normalization - mesmo arquivo deve retornar cached
curl -X POST http://localhost:8001/normalize \
  -F "file=@test.mp3" \
  -F "operations[]=normalize_volume"
```

## 📈 Monitoramento de Cache

### Estatísticas do Redis
```bash
# video-download
docker exec video-download-redis redis-cli INFO stats | grep keyspace

# audio-normalization
docker exec audio-normalization-redis redis-cli INFO stats | grep keyspace
```

### Admin Stats Endpoint
```bash
# video-download
curl http://localhost:8000/admin/stats

# audio-normalization
curl http://localhost:8001/admin/stats
```

## ⚠️ Considerações Importantes

### ✅ Boas Práticas
1. **Sincronização**: Sempre use o mesmo valor de `CACHE_TTL_HOURS` em todos os serviços do mesmo microserviço
2. **Mínimos recomendados**:
   - `CACHE_TTL_HOURS >= 1` (cache < 1h é ineficiente)
   - `CLEANUP_INTERVAL_MINUTES >= 5` (evita overhead)
3. **Hot Reload**: Mudanças nas env vars requerem restart dos containers
4. **Monitoramento**: Acompanhe uso de disco com cache longo

### ❌ Evitar
1. Valores muito baixos em produção (causa overhead de I/O)
2. Cleanup mais frequente que TTL (ex: TTL=24h, Cleanup=1min)
3. TTL muito alto sem monitoramento de disco
4. Valores diferentes entre API e Celery Worker do mesmo serviço

## 🆘 Troubleshooting

### Cache não está expirando
```bash
# Verificar se env var foi aplicada
docker exec video-download-api env | grep CACHE_TTL

# Verificar logs de inicialização
docker logs video-download-api | head -20
```

### Cleanup não está rodando
```bash
# Verificar loop de cleanup
docker logs video-download-celery | grep "Cleanup"

# Deve aparecer mensagens a cada CLEANUP_INTERVAL_MINUTES
```

### Jobs expiram muito rápido
```bash
# Verificar TTL no Redis
docker exec video-download-redis redis-cli TTL "job:VIDEO_ID_720p"

# Se < esperado, verificar CACHE_TTL_HOURS
```

## 📚 Documentos Relacionados

- `services/audio-normalization/CACHE_SYSTEM.md` - Arquitetura do cache por hash
- `services/audio-normalization/CONFIGURACAO_CACHE.md` - Detalhes do audio-normalization
- `services/video-download/.env.example` - Configurações do video-download
- `services/audio-normalization/.env.example` - Configurações do audio-normalization

## 🎉 Benefícios Implementados

✅ **Flexibilidade**: Ajuste de cache sem redeployar código  
✅ **Consistência**: Mesma arquitetura em ambos os microserviços  
✅ **Monitoramento**: Logs informativos sobre configuração  
✅ **Segurança**: Valores padrão sensatos (24h/30min)  
✅ **Desenvolvimento**: Cache curto para testes rápidos  
✅ **Produção**: Cache longo para máxima performance  

---

**Última atualização**: Sistema totalmente configurável implementado em ambos os microserviços  
**Status**: ✅ Pronto para uso em desenvolvimento e produção
