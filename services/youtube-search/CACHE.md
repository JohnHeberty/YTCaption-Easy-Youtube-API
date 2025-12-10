# Cache Distribuído com Redis

## Arquitetura de Cache

O serviço YouTube Search utiliza Redis como **cache distribuído** para otimizar performance e reduzir chamadas repetidas à API do YouTube.

### Como Funciona

1. **ID Único por Operação**
   - Cada combinação de parâmetros gera um ID único (SHA256)
   - Exemplo: `video_info:dQw4w9WgXcQ` → `abc123def456`

2. **Cache Hit**
   - Quando uma requisição chega, o sistema verifica se já existe um job com os mesmos parâmetros
   - Se encontrar e estiver completo, retorna imediatamente do cache
   - **Não há nova chamada ao YouTube**

3. **Cache Miss**
   - Se não encontrar, cria novo job e processa
   - Resultado fica armazenado no Redis por 24h (configurável)

4. **TTL (Time To Live)**
   - Cache expira após 24h por padrão
   - Configurável via `CACHE_TTL_HOURS`
   - Limpeza automática remove jobs expirados

## Vantagens do Redis como Cache Distribuído

### 1. Performance
- **Leitura rápida**: Redis é in-memory (microsegundos)
- **Redução de latência**: ~5ms vs ~500ms+ de API externa
- **Hit rate alto**: ~90%+ em produção

### 2. Escalabilidade
- **Múltiplos workers**: Todos compartilham mesmo cache
- **Horizontal scaling**: Adicione mais workers sem duplicar cache
- **Load balancing**: Cache centralizado = consistência

### 3. Persistência
- **Sobrevive a restarts**: Jobs não se perdem ao reiniciar serviço
- **Backup/restore**: Redis pode ser backupeado
- **AOF/RDB**: Persistência configurável

### 4. Recursos Avançados
- **Expiração automática**: TTL nativo do Redis
- **Atomic operations**: Thread-safe por design
- **Pub/Sub**: Potencial para notificações em tempo real

## Configuração do Cache

### Variáveis de Ambiente

```env
# Cache TTL
CACHE_TTL_HOURS=24

# Limpeza automática
CACHE_CLEANUP_INTERVAL_MINUTES=30

# Redis URL
REDIS_URL=redis://redis:6379/0
```

### Estrutura de Chaves no Redis

```
youtube_search:job:abc123def456
youtube_search:job:def456ghi789
youtube_search:job:ghi789jkl012
...
```

Cada chave contém o job completo serializado em JSON:
```json
{
  "id": "abc123def456",
  "search_type": "video_info",
  "video_id": "dQw4w9WgXcQ",
  "status": "completed",
  "result": { ... },
  "created_at": "2025-12-10T10:00:00",
  "expires_at": "2025-12-11T10:00:00"
}
```

## Padrões de Cache

### Cache-Aside (Lazy Loading)
```python
# 1. Check cache
job = cache.get(job_id)

# 2. Cache miss - fetch from source
if not job:
    job = fetch_from_youtube(params)
    cache.set(job_id, job, ttl=24h)

# 3. Return result
return job.result
```

### Write-Through
- Quando job completa, escreve no Redis automaticamente
- Garantia de consistência
- Implementado no `job_store.update_job()`

## Monitoramento do Cache

### Estatísticas via `/admin/stats`

```json
{
  "total_jobs": 1000,
  "completed": 950,  // Cache hits potenciais
  "queued": 10,
  "processing": 20,
  "failed": 20
}
```

### Hit Rate Calculation

```
Hit Rate = (completed / total_jobs) * 100
```

Se 950 de 1000 jobs estão completos, qualquer requisição repetida será cache hit.

## Limpeza de Cache

### Automática
- **Intervalo**: A cada 30 minutos (configurável)
- **Critério**: Jobs com `expires_at < now()`
- **Task Celery Beat**: `cleanup_expired_jobs`

### Manual via API

```bash
# Limpeza básica (apenas expirados)
curl -X POST "http://localhost:8003/admin/cleanup?deep=false"

# Limpeza total (TUDO)
curl -X POST "http://localhost:8003/admin/cleanup?deep=true"
```

## Estratégias de Invalidação

### Por Tempo (TTL)
- **Padrão**: 24 horas
- **Vantagem**: Automático, simples
- **Desvantagem**: Dados podem ficar stale

### Manual
- **DELETE /jobs/{job_id}**
- **Útil para**: Dados incorretos, testes

### Cache Busting
- **Mudar parâmetros**: Força cache miss
- **Exemplo**: `max_results=10` → `max_results=11`

## Melhor Uso do Cache

### ✅ Cache-Friendly Operations
- Video info (raramente muda)
- Channel info (muda pouco)
- Search results (ok por 24h)

### ⚠️ Use com Cuidado
- Stats em tempo real (views, likes)
- Live streams (status muda frequente)
- Trending videos (mudam constantemente)

### 🔧 Configurações Recomendadas

```env
# Para dados relativamente estáticos
CACHE_TTL_HOURS=48

# Para dados mais dinâmicos
CACHE_TTL_HOURS=6

# Para desenvolvimento (teste rápido)
CACHE_TTL_HOURS=1
```

## Redis Cluster (Produção)

Para alta disponibilidade em produção:

```yaml
# docker-compose.yml
services:
  redis-master:
    image: redis:6.2-alpine
    command: redis-server --appendonly yes
    
  redis-replica:
    image: redis:6.2-alpine
    command: redis-server --replicaof redis-master 6379
    depends_on:
      - redis-master
```

Atualizar `.env`:
```env
REDIS_URL=redis://redis-master:6379/0
```

## Troubleshooting

### Cache não está funcionando
```bash
# Verificar conexão Redis
curl http://localhost:8003/health

# Ver estatísticas
curl http://localhost:8003/admin/stats

# Verificar logs
docker-compose logs youtube-search-service | grep cache
```

### Cache muito grande
```bash
# Ver quantidade de jobs
curl http://localhost:8003/admin/stats

# Limpar expirados
curl -X POST "http://localhost:8003/admin/cleanup?deep=false"

# Ver uso de memória Redis
docker exec redis redis-cli INFO memory
```

### Performance ruim
```bash
# Verificar hit rate no /admin/stats
# Ajustar TTL se necessário
# Considerar pre-warming para queries populares
```
