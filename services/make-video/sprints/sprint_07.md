# Sprint Pack 07/12 - RedisBlacklistBackend + Multi-Host Support

**Escopo deste pack:** Implementar backend Redis para blacklist multi-host, stats agregados com HINCRBY, fallback automático para JSON local, BlacklistManager com ping de health, e testes de integração Redis.

## Índice

- [S-077: Criar interface BlacklistBackend (ABC)](#s-077)
- [S-078: Criar RedisBlacklistBackend (estrutura)](#s-078)
- [S-079: Implementar is_blacklisted() no Redis](#s-079)
- [S-080: Implementar add() no Redis com TTL nativo](#s-080)
- [S-081: Implementar remove() no Redis](#s-081)
- [S-082: Implementar stats com HINCRBY](#s-082)
- [S-083: Implementar get_stats() agregado](#s-083)
- [S-084: Implementar ping de health](#s-084)
- [S-085: Adaptar ShortsBlacklist para implementar interface](#s-085)
- [S-086: Criar BlacklistManager com fallback](#s-086)
- [S-087: Implementar detecção automática de Redis disponível](#s-087)
- [S-088: Criar testes com Redis mock (fakeredis)](#s-088)

---

<a name="s-077"></a>
## S-077: Criar interface BlacklistBackend (ABC)

**Objetivo:** Criar interface abstrata que define contrato para backends de blacklist (JSON e Redis).

**Escopo (IN/OUT):**
- **IN:** ABC com métodos abstratos: is_blacklisted, add, remove, get_stats
- **OUT:** Não implementar lógica ainda

**Arquivos tocados:**
- `services/make-video/app/blacklist_backend.py`

**Mudanças exatas:**
- Adicionar imports: `from abc import ABC, abstractmethod`, `from typing import Optional, Dict`
- Criar interface:
  ```python
  class BlacklistBackend(ABC):
      """Interface para backends de blacklist"""
      
      @abstractmethod
      def is_blacklisted(self, video_id: str) -> bool:
          """Verifica se vídeo está na blacklist"""
          pass
      
      @abstractmethod
      def add(self, video_id: str, reason: str, detection_info: dict, confidence: float):
          """Adiciona vídeo à blacklist"""
          pass
      
      @abstractmethod
      def remove(self, video_id: str):
          """Remove vídeo da blacklist"""
          pass
      
      @abstractmethod
      def get_stats(self) -> dict:
          """Retorna estatísticas da blacklist"""
          pass
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Interface ABC criada
- [ ] 4 métodos abstratos definidos
- [ ] Docstrings adicionadas
- [ ] Não pode ser instanciada diretamente

**Testes:**
- Unit: `tests/test_blacklist_backend.py::test_cannot_instantiate_abc()`

**Observabilidade:**
- N/A (interface)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-001

---

<a name="s-078"></a>
## S-078: Criar RedisBlacklistBackend (estrutura)

**Objetivo:** Criar classe `RedisBlacklistBackend` que implementa interface, com conexão Redis.

**Escopo (IN/OUT):**
- **IN:** Classe, `__init__`, conexão Redis
- **OUT:** Não implementar métodos ainda

**Arquivos tocados:**
- `services/make-video/app/blacklist_backend.py`

**Mudanças exatas:**
- Adicionar import: `import redis`, `import json`, `import logging`, `from datetime import datetime, timezone, timedelta`
- Criar `logger = logging.getLogger(__name__)`
- Criar classe:
  ```python
  class RedisBlacklistBackend(BlacklistBackend):
      """
      Backend Redis para multi-host
      
      Vantagens:
      - Consistência entre instâncias
      - TTL nativo (sem cleanup manual)
      - Performance (in-memory)
      """
      
      def __init__(self, redis_url: str, ttl_days: int = 90):
          self.redis = redis.from_url(redis_url, decode_responses=True)
          self.ttl_seconds = ttl_days * 86400
          self.key_prefix = 'ytcaption:blacklist:'
          
          logger.info("redis_backend_initialized", redis_url=redis_url, ttl_days=ttl_days)
      
      # Métodos abstratos serão implementados nas próximas sprints
      def is_blacklisted(self, video_id: str) -> bool:
          pass
      
      def add(self, video_id: str, reason: str, detection_info: dict, confidence: float):
          pass
      
      def remove(self, video_id: str):
          pass
      
      def get_stats(self) -> dict:
          pass
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Classe criada e herda de BlacklistBackend
- [ ] Conexão Redis estabelecida
- [ ] key_prefix definido ('ytcaption:blacklist:')
- [ ] TTL configurável em dias (default 90)

**Testes:**
- Unit: `tests/test_blacklist_backend.py::test_redis_backend_initialization()`

**Observabilidade:**
- Log: `logger.info("redis_backend_initialized", ...)`

**Riscos/Rollback:**
- Risco: Redis não disponível no init
- Rollback: Lazy connection (conectar apenas no primeiro uso)

**Dependências:** S-077, S-004 (redis instalado)

---

<a name="s-079"></a>
## S-079: Implementar is_blacklisted() no Redis

**Objetivo:** Implementar verificação de blacklist usando Redis EXISTS.

**Escopo (IN/OUT):**
- **IN:** Método simples com EXISTS
- **OUT:** Não implementar cache local

**Arquivos tocados:**
- `services/make-video/app/blacklist_backend.py`

**Mudanças exatas:**
- Implementar método:
  ```python
  def is_blacklisted(self, video_id: str) -> bool:
      key = f"{self.key_prefix}{video_id}"
      return self.redis.exists(key) > 0
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Retorna True se key existe
- [ ] Retorna False caso contrário
- [ ] Performance: O(1) no Redis
- [ ] Não falha se Redis indisponível (será tratado em S-086)

**Testes:**
- Unit: `tests/test_blacklist_backend.py::test_redis_is_blacklisted_true()`
- Unit: `tests/test_blacklist_backend.py::test_redis_is_blacklisted_false()`

**Observabilidade:**
- N/A (método simples)

**Riscos/Rollback:**
- Risco: Redis lento causa timeout
- Rollback: Adicionar timeout de 1s na operação

**Dependências:** S-078

---

<a name="s-080"></a>
## S-080: Implementar add() no Redis com TTL nativo

**Objetivo:** Implementar adição de entrada à blacklist usando Redis SETEX (set com expiração).

**Escopo (IN/OUT):**
- **IN:** Método com TTL nativo do Redis
- **OUT:** Não implementar pub/sub de notificações

**Arquivos tocados:**
- `services/make-video/app/blacklist_backend.py`

**Mudanças exatas:**
- Implementar método:
  ```python
  def add(self, video_id: str, reason: str, detection_info: dict, confidence: float):
      key = f"{self.key_prefix}{video_id}"
      
      # Incrementar attempts se já existe
      attempts = 1
      existing = self.redis.get(key)
      if existing:
          data = json.loads(existing)
          attempts = data.get('attempts', 0) + 1
      
      entry = {
          'video_id': video_id,
          'reason': reason,
          'detected_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),  # MUST-FIX v1.6
          'detection_info': detection_info,
          'confidence': confidence,
          'attempts': attempts
      }
      
      # Set com TTL nativo do Redis
      self.redis.setex(
          key,
          self.ttl_seconds,
          json.dumps(entry)
      )
      
      # Incrementar contador por reason (para stats otimizado)
      self.redis.hincrby('ytcaption:blacklist:stats', reason, 1)
      
      logger.info(f"📝 Blacklist (Redis): {video_id} (reason={reason}, conf={confidence:.2f})")
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Entrada adicionada com TTL
- [ ] HINCRBY incrementa stats
- [ ] Attempts incrementado se já existe
- [ ] Log gerado
- [ ] MUST-FIX v1.6: timestamp correto

**Testes:**
- Unit: `tests/test_blacklist_backend.py::test_redis_add_creates_entry()`
- Unit: `tests/test_blacklist_backend.py::test_redis_add_increments_attempts()`
- Unit: `tests/test_blacklist_backend.py::test_redis_add_sets_ttl()`

**Observabilidade:**
- Log: `logger.info("blacklist_entry_added_redis", ...)`
- Métrica: Já incrementada via HINCRBY no próprio Redis

**Riscos/Rollback:**
- Risco: JSON encoding falha
- Rollback: Try/except e logar erro

**Dependências:** S-079

---

<a name="s-081"></a>
## S-081: Implementar remove() no Redis

**Objetivo:** Implementar remoção de entrada usando Redis DEL.

**Escopo (IN/OUT):**
- **IN:** Método simples com DEL
- **OUT:** Não decrementar stats (contadores são append-only)

**Arquivos tocados:**
- `services/make-video/app/blacklist_backend.py`

**Mudanças exatas:**
- Implementar método:
  ```python
  def remove(self, video_id: str):
      key = f"{self.key_prefix}{video_id}"
      deleted = self.redis.delete(key)
      
      if deleted > 0:
          logger.info("blacklist_entry_removed_redis", video_id=video_id)
      else:
          logger.warning("blacklist_entry_not_found_redis", video_id=video_id)
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] DEL executa corretamente
- [ ] Log indica sucesso/falha
- [ ] Retorna número de keys deletadas

**Testes:**
- Unit: `tests/test_blacklist_backend.py::test_redis_remove_deletes()`
- Unit: `tests/test_blacklist_backend.py::test_redis_remove_nonexistent()`

**Observabilidade:**
- Log: `logger.info("blacklist_entry_removed_redis", ...)`
- Métrica: `counter("blacklist_entries_removed_total", tags={"backend": "redis"})`

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-080

---

<a name="s-082"></a>
## S-082: Implementar stats com HINCRBY

**Objetivo:** Validar que HINCRBY está sendo usado para incrementar contadores por reason.

**Escopo (IN/OUT):**
- **IN:** Validar que add() já usa HINCRBY (implementado em S-080)
- **OUT:** Não implementar outros tipos de stats ainda

**Arquivos tocados:**
- Nenhum (validação de S-080)

**Mudanças exatas:**
- Validar que em `add()`, existe linha: `self.redis.hincrby('ytcaption:blacklist:stats', reason, 1)`
- Adicionar comentário: `# HINCRBY é atômico e leve (não requer lock)`

**Critérios de Aceite / Definition of Done:**
- [ ] HINCRBY usado em add()
- [ ] Key de stats: 'ytcaption:blacklist:stats'
- [ ] Field: reason (embedded_subtitles, duplicado, etc)
- [ ] Incremento de 1

**Testes:**
- Unit: `tests/test_blacklist_backend.py::test_redis_stats_incremented_on_add()`

**Observabilidade:**
- Métrica: Dados no próprio Redis (lidos em S-083)

**Riscos/Rollback:**
- Risco: Hash stats cresce indefinidamente
- Rollback: Adicionar TTL no hash (ex: 30 dias)

**Dependências:** S-080

---

<a name="s-083"></a>
## S-083: Implementar get_stats() agregado

**Objetivo:** Implementar método que retorna stats agregados do Redis usando HGETALL.

**Escopo (IN/OUT):**
- **IN:** Usar HGETALL para ler contadores
- **OUT:** Não implementar stats em tempo real (usar contadores)

**Arquivos tocados:**
- `services/make-video/app/blacklist_backend.py`

**Mudanças exatas:**
- Implementar método:
  ```python
  def get_stats(self) -> dict:
      # Usar contadores agregados (leve)
      reasons = self.redis.hgetall('ytcaption:blacklist:stats')
      
      # Converter para int
      reasons = {k: int(v) for k, v in reasons.items()}
      
      total = sum(reasons.values())
      
      return {
          'total_blocked': total,
          'by_reason': reasons,
          'backend': 'redis',
          'note': 'Contadores agregados (não conta expirações)'
      }
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Retorna total_blocked (soma dos contadores)
- [ ] Retorna by_reason (dict de contadores)
- [ ] Indica backend='redis'
- [ ] Nota sobre expiração

**Testes:**
- Unit: `tests/test_blacklist_backend.py::test_redis_get_stats_structure()`

**Observabilidade:**
- N/A (método de leitura)

**Riscos/Rollback:**
- Risco: HGETALL lento se hash muito grande
- Rollback: Limitar size do hash

**Dependências:** S-082

---

<a name="s-084"></a>
## S-084: Implementar ping de health

**Objetivo:** Criar método que valida conexão Redis está funcional.

**Escopo (IN/OUT):**
- **IN:** Método `ping() -> bool` que testa Redis
- **OUT:** Não implementar reconnect automático

**Arquivos tocados:**
- `services/make-video/app/blacklist_backend.py`

**Mudanças exatas:**
- Adicionar método:
  ```python
  def ping(self) -> bool:
      """Testa conexão Redis"""
      try:
          return self.redis.ping()
      except Exception as e:
          logger.error(f"Redis ping failed: {e}")
          return False
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Retorna True se Redis responde
- [ ] Retorna False se falha
- [ ] Não levanta exceção

**Testes:**
- Unit: `tests/test_blacklist_backend.py::test_redis_ping_success()`
- Unit: `tests/test_blacklist_backend.py::test_redis_ping_failure()`

**Observabilidade:**
- Log: `logger.error("redis_ping_failed", error=...)`

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-078

---

<a name="s-085"></a>
## S-085: Adaptar ShortsBlacklist para implementar interface

**Objetivo:** Modificar `ShortsBlacklist` (JSON backend) para implementar interface `BlacklistBackend`.

**Escopo (IN/OUT):**
- **IN:** Adicionar herança de BlacklistBackend
- **OUT:** Não modificar lógica interna

**Arquivos tocados:**
- `services/make-video/app/shorts_blacklist.py`

**Mudanças exatas:**
- Adicionar import: `from app.blacklist_backend import BlacklistBackend`
- Modificar declaração de classe: `class ShortsBlacklist(BlacklistBackend):`
- Validar que métodos já existem: `is_blacklisted`, `add`, `remove`, `get_stats`
- Adicionar nota no docstring: `Implements BlacklistBackend interface`

**Critérios de Aceite / Definition of Done:**
- [ ] Herda de BlacklistBackend
- [ ] Todos métodos abstratos implementados
- [ ] Não quebra testes existentes

**Testes:**
- Unit: `tests/test_shorts_blacklist.py::test_implements_backend_interface()`

**Observabilidade:**
- N/A (refactoring)

**Riscos/Rollback:**
- Risco: Assinaturas incompatíveis
- Rollback: Ajustar assinaturas dos métodos

**Dependências:** S-077, S-074 (ShortsBlacklist completo)

---

<a name="s-086"></a>
## S-086: Criar BlacklistManager com fallback

**Objetivo:** Criar classe gerenciadora que tenta Redis, se falhar usa JSON local automaticamente.

**Escopo (IN/OUT):**
- **IN:** Manager com detecção e fallback automático
- **OUT:** Não implementar circuit breaker ainda

**Arquivos tocados:**
- `services/make-video/app/blacklist_backend.py`

**Mudanças exatas:**
- Criar classe:
  ```python
  class BlacklistManager:
      """
      Gerenciador com fallback automático
      
      Tenta Redis, se falhar usa JSON local (modo degradado)
      """
      
      def __init__(self):
          from app.config import MULTI_HOST_MODE, REDIS_URL, BLACKLIST_TTL_DAYS
          from app.shorts_blacklist import ShortsBlacklist
          import os
          
          redis_url = REDIS_URL
          multi_host = MULTI_HOST_MODE
          blacklist_path = os.getenv('BLACKLIST_PATH', 'storage/shorts_cache/blacklist.json')
          
          if multi_host and redis_url:
              try:
                  self.backend = RedisBlacklistBackend(redis_url, ttl_days=BLACKLIST_TTL_DAYS)
                  # Testar conexão
                  if self.backend.ping():
                      logger.info("✅ Blacklist: Redis (multi-host)")
                  else:
                      raise ConnectionError("Redis ping failed")
              except Exception as e:
                  logger.warning(f"⚠️ Redis falhou: {e}, usando JSON local")
                  self.backend = ShortsBlacklist(blacklist_path, ttl_days=BLACKLIST_TTL_DAYS)
          else:
              self.backend = ShortsBlacklist(blacklist_path, ttl_days=BLACKLIST_TTL_DAYS)
              logger.info("✅ Blacklist: JSON local (single-host)")
      
      def is_blacklisted(self, video_id: str) -> bool:
          return self.backend.is_blacklisted(video_id)
      
      def add(self, video_id: str, reason: str, detection_info: dict = None, confidence: float = 0.0):
          self.backend.add(video_id, reason, detection_info or {}, confidence)
      
      def remove(self, video_id: str):
          self.backend.remove(video_id)
      
      def get_stats(self) -> dict:
          return self.backend.get_stats()
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Tenta Redis se MULTI_HOST_MODE=true
- [ ] Fallback para JSON se Redis falha
- [ ] Ping valida conexão antes de usar Redis
- [ ] Todos métodos delegam para backend

**Testes:**
- Unit: `tests/test_blacklist_backend.py::test_manager_uses_redis_when_available()`
- Unit: `tests/test_blacklist_backend.py::test_manager_fallback_to_json()`

**Observabilidade:**
- Log: `logger.info("blacklist_backend_selected", backend="redis"|"json")`

**Riscos/Rollback:**
- Risco: Fallback silencioso pode ocultar problema de Redis
- Rollback: Adicionar alerta se Redis falha em produção

**Dependências:** S-078, S-084, S-085

---

<a name="s-087"></a>
## S-087: Implementar detecção automática de Redis disponível

**Objetivo:** Validar que BlacklistManager detecta corretamente se Redis está disponível e funciona.

**Escopo (IN/OUT):**
- **IN:** Testes de detecção automática
- **OUT:** Não implementar retry de conexão

**Arquivos tocados:**
- Nenhum (validação de S-086)

**Mudanças exatas:**
- Criar testes que validam cenários:
  1. Redis disponível e funcional → usa Redis
  2. Redis URL não configurado → usa JSON
  3. Redis configurado mas offline → fallback para JSON
  4. MULTI_HOST_MODE=false → usa JSON mesmo com Redis

**Critérios de Aceite / Definition of Done:**
- [ ] 4 cenários testados
- [ ] Detecção correta em cada caso
- [ ] Logs indicam backend escolhido

**Testes:**
- Unit: `tests/test_blacklist_backend.py::test_detection_scenarios()`

**Observabilidade:**
- Log: Backend selecionado em cada cenário

**Riscos/Rollback:**
- Risco: Detecção incorreta causa uso de backend errado
- Rollback: Adicionar flag explícita FORCE_BACKEND=redis|json

**Dependências:** S-086

---

<a name="s-088"></a>
## S-088: Criar testes com Redis mock (fakeredis)

**Objetivo:** Criar testes que usam fakeredis para simular Redis sem dependência externa.

**Escopo (IN/OUT):**
- **IN:** Testes com fakeredis
- **OUT:** Não testar com Redis real (CI)

**Arquivos tocados:**
- `services/make-video/conftest.py`
- `services/make-video/tests/test_blacklist_backend.py`

**Mudanças exatas:**
- Em `conftest.py`, criar fixture:
  ```python
  import fakeredis
  
  @pytest.fixture
  def mock_redis():
      """Fake Redis para testes"""
      return fakeredis.FakeRedis(decode_responses=True)
  
  @pytest.fixture
  def redis_backend(mock_redis, monkeypatch):
      """RedisBlacklistBackend com fake Redis"""
      from app.blacklist_backend import RedisBlacklistBackend
      
      # Monkeypatch redis.from_url para retornar fake
      monkeypatch.setattr('redis.from_url', lambda *args, **kwargs: mock_redis)
      
      backend = RedisBlacklistBackend('redis://fake', ttl_days=90)
      return backend
  ```
- Criar testes:
  ```python
  def test_redis_backend_add_and_get(redis_backend):
      redis_backend.add('video1', 'test', {}, 0.8)
      assert redis_backend.is_blacklisted('video1') == True
  
  def test_redis_backend_ttl_set(redis_backend, mock_redis):
      redis_backend.add('video1', 'test', {}, 0.8)
      ttl = mock_redis.ttl('ytcaption:blacklist:video1')
      assert ttl > 0  # TTL está setado
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] fakeredis fixture criada
- [ ] 5+ testes com Redis mock
- [ ] Testes passam sem Redis real
- [ ] Cobertura: 80%+ dos métodos Redis

**Testes:**
- Self-test: `pytest tests/test_blacklist_backend.py -v`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: fakeredis não replica comportamento real 100%
- Rollback: Adicionar testes de integração com Redis real (opcional)

**Dependências:** S-080, S-081, S-083, S-010 (fixtures)

---

## Mapa de Dependências (Pack 07)

```
S-077 (interface ABC) → S-078, S-085
S-078 (Redis estrutura) → S-079, S-084
S-079 (is_blacklisted) → S-080
S-080 (add) → S-081, S-082, S-088
S-081 (remove) ← S-080
S-082 (HINCRBY) → S-083
S-083 (get_stats) ← S-082
S-084 (ping) → S-086
S-085 (ShortsBlacklist interface) ← S-077, S-074
S-086 (BlacklistManager) ← S-078, S-084, S-085
S-087 (detecção auto) ← S-086
S-088 (testes mock) ← S-080, S-081, S-083
```

**Próximo pack:** Sprint 08 - Integração no pipeline (download_short, fetch_shorts, overfetch+dedupe, remover return duplicado)
