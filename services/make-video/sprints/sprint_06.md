# Sprint Pack 06/12 - ShortsBlacklist JSON (File Locking & TTL)

**Escopo deste pack:** Implementar `ShortsBlacklist` com backend JSON + file locking (fcntl) para single-host, atomic write, TTL de 90 dias, mtime reload automático, retry com backoff exponencial, e limpeza automática de entradas expiradas.

## Índice

- [S-063: Criar classe ShortsBlacklist (estrutura)](#s-063)
- [S-064: Implementar file locking com fcntl](#s-064)
- [S-065: Implementar atomic write (temp + rename)](#s-065)
- [S-066: Implementar TTL de 90 dias](#s-066)
- [S-067: Implementar timestamps ISO 8601 UTC (MUST-FIX)](#s-067)
- [S-068: Implementar limpeza de entradas expiradas](#s-068)
- [S-069: Implementar mtime reload automático](#s-069)
- [S-070: Implementar retry com backoff exponencial](#s-070)
- [S-071: Implementar método is_blacklisted()](#s-071)
- [S-072: Implementar método add()](#s-072)
- [S-073: Implementar método remove()](#s-073)
- [S-074: Implementar método get_stats()](#s-074)
- [S-075: Criar testes de concurrent access](#s-075)
- [S-076: Criar testes de TTL expiration](#s-076)

---

<a name="s-063"></a>
## S-063: Criar classe ShortsBlacklist (estrutura)

**Objetivo:** Criar estrutura da classe `ShortsBlacklist` com docstring completa e atributos básicos.

**Escopo (IN/OUT):**
- **IN:** Classe, `__init__`, docstring, atributos
- **OUT:** Não implementar métodos ainda

**Arquivos tocados:**
- `services/make-video/app/shorts_blacklist.py`

**Mudanças exatas:**
- Adicionar imports: `import fcntl`, `import json`, `import os`, `import time`, `import logging`, `import tempfile`, `import shutil`, `from pathlib import Path`, `from datetime import datetime, timezone, timedelta`
- Criar `logger = logging.getLogger(__name__)`
- Criar classe:
  ```python
  class ShortsBlacklist:
      """
      Gerencia lista de vídeos bloqueados com suporte a concorrência
      
      IMPORTANTE: Usa file locking + atomic write para evitar race conditions
      em ambientes com múltiplos workers.
      
      Features:
      - TTL de 90 dias (limpeza automática)
      - Reload automático por mtime (evita stale reads)
      - Retry com backoff em caso de erro de leitura
      
      ⚠️ TODO (produção): Migrar para Redis/DB para escala.
      """
      
      def __init__(self, blacklist_path: str, ttl_days: int = 90):
          self.blacklist_path = Path(blacklist_path)
          self.lock_path = Path(str(blacklist_path) + ".lock")
          self.ttl_days = ttl_days
          self.blacklist = self._load()
          self.last_mtime = self._get_mtime()
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Classe criada com docstring completa
- [ ] 5 atributos definidos em `__init__`
- [ ] lock_path criado automaticamente (.lock)
- [ ] Import de `datetime.timezone` (MUST-FIX v1.6)

**Testes:**
- Unit: `tests/test_shorts_blacklist.py::test_blacklist_initialization()`

**Observabilidade:**
- N/A (estrutura)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-001, S-004

---

<a name="s-064"></a>
## S-064: Implementar file locking com fcntl

**Objetivo:** Criar helper que adquire lock exclusivo em arquivo usando fcntl para evitar race conditions.

**Escopo (IN/OUT):**
- **IN:** Context manager ou wrapper para lock
- **OUT:** Não implementar lock distribuído (Redis em pack 07)

**Arquivos tocados:**
- `services/make-video/app/shorts_blacklist.py`

**Mudanças exatas:**
- Criar método auxiliar (usado em add/remove):
  ```python
  def _acquire_lock(self):
      """Context manager para lock exclusivo"""
      lock_file = open(self.lock_path, 'w')
      fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
      return lock_file
  
  def _release_lock(self, lock_file):
      """Libera lock"""
      fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
      lock_file.close()
  ```
- Alternativa: Usar context manager:
  ```python
  from contextlib import contextmanager
  
  @contextmanager
  def _lock(self):
      lock_file = open(self.lock_path, 'w')
      try:
          fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
          yield
      finally:
          fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
          lock_file.close()
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Lock adquirido antes de write
- [ ] Lock liberado após write
- [ ] Múltiplos processos serializam acesso

**Testes:**
- Unit: `tests/test_shorts_blacklist.py::test_file_locking_prevents_race()`

**Observabilidade:**
- Log: `logger.debug("lock_acquired", path=self.lock_path)`

**Riscos/Rollback:**
- Risco: Deadlock se exceção ocorrer antes de release
- Rollback: Usar try/finally garantido

**Dependências:** S-063

---

<a name="s-065"></a>
## S-065: Implementar atomic write (temp + rename)

**Objetivo:** Implementar escrita atômica: escrever em arquivo temporário, depois renomear para destino final.

**Escopo (IN/OUT):**
- **IN:** Helper `_atomic_write(data)` que escreve atomicamente
- **OUT:** Não implementar backup de versões anteriores

**Arquivos tocados:**
- `services/make-video/app/shorts_blacklist.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def _atomic_write(self, data: dict):
      """Escrita atômica: temp file + rename"""
      # Criar temp file no mesmo diretório (necessário para atomic rename)
      temp_fd, temp_path = tempfile.mkstemp(
          dir=self.blacklist_path.parent,
          suffix='.tmp',
          prefix='.blacklist_'
      )
      
      try:
          # Escrever dados
          with os.fdopen(temp_fd, 'w') as f:
              json.dump(data, f, indent=2)
          
          # Rename atômico
          shutil.move(temp_path, self.blacklist_path)
          
          logger.debug("atomic_write_completed", path=self.blacklist_path)
      except Exception as e:
          # Cleanup temp file em caso de erro
          if os.path.exists(temp_path):
              os.remove(temp_path)
          raise
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Escreve em temp file primeiro
- [ ] Rename para destino final
- [ ] Cleanup de temp em caso de erro
- [ ] Operação atômica (não deixa arquivo corrompido)

**Testes:**
- Unit: `tests/test_shorts_blacklist.py::test_atomic_write_no_corruption()`

**Observabilidade:**
- Log: `logger.debug("atomic_write_completed")`

**Riscos/Rollback:**
- Risco: shutil.move pode falhar entre filesystems
- Rollback: Usar os.rename() (requer mesmo filesystem)

**Dependências:** S-064

---

<a name="s-066"></a>
## S-066: Implementar TTL de 90 dias

**Objetivo:** Adicionar cálculo de expiração (expires_at) baseado em TTL ao adicionar entrada.

**Escopo (IN/OUT):**
- **IN:** Calcular expires_at = now + ttl_days
- **OUT:** Não implementar limpeza ainda (próxima sprint)

**Arquivos tocados:**
- `services/make-video/app/shorts_blacklist.py`

**Mudanças exatas:**
- Em método `add()` (será implementado em S-072), adicionar:
  ```python
  # Calcular expiração (TTL) - aware UTC
  now = datetime.now(timezone.utc)
  expires_at = now + timedelta(days=self.ttl_days)
  ```
- Estrutura de entrada:
  ```python
  entry = {
      "video_id": video_id,
      "reason": reason,
      "detected_at": now.isoformat().replace('+00:00', 'Z'),  # MUST-FIX v1.6
      "expires_at": expires_at.isoformat().replace('+00:00', 'Z'),  # MUST-FIX v1.6
      "detection_info": detection_info or {},
      "confidence": confidence,
      "attempts": attempts
  }
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] expires_at calculado corretamente
- [ ] TTL padrão de 90 dias
- [ ] Timestamps em timezone aware UTC
- [ ] ISO format com 'Z' (MUST-FIX v1.6)

**Testes:**
- Unit: `tests/test_shorts_blacklist.py::test_ttl_calculation()`

**Observabilidade:**
- Log: `logger.debug("entry_ttl_set", expires_at=expires_at.isoformat())`

**Riscos/Rollback:**
- Risco: Entradas nunca expiram se limpeza não implementada
- Rollback: Implementar limpeza em S-068

**Dependências:** S-065

---

<a name="s-067"></a>
## S-067: Implementar timestamps ISO 8601 UTC (MUST-FIX)

**Objetivo:** Garantir que timestamps são formatados corretamente como ISO 8601 com 'Z' ao invés de '+00:00Z' (bug do plano v1.6).

**Escopo (IN/OUT):**
- **IN:** Aplicar `.replace('+00:00', 'Z')` em todos timestamps
- **OUT:** Não implementar parsing de timestamps antigos

**Arquivos tocados:**
- `services/make-video/app/shorts_blacklist.py`

**Mudanças exatas:**
- Garantir que em todos lugares onde `datetime.isoformat()` é chamado, aplicar:
  ```python
  timestamp_str = now.isoformat().replace('+00:00', 'Z')
  ```
- Adicionar comentário: `# MUST-FIX v1.6: .replace evita string inválida '2026-01-29T10:30:00+00:00Z'`

**Critérios de Aceite / Definition of Done:**
- [ ] Todos timestamps terminam com 'Z'
- [ ] Não têm '+00:00Z' (formato inválido)
- [ ] Formato: `2026-01-29T10:30:00Z`

**Testes:**
- Unit: `tests/test_shorts_blacklist.py::test_timestamp_format_correct()`
- Assert: `'Z' in timestamp and '+00:00Z' not in timestamp`

**Observabilidade:**
- N/A (formatação)

**Riscos/Rollback:**
- Risco: Timestamps antigos em formato errado
- Rollback: Adicionar migração para corrigir entradas antigas

**Dependências:** S-066

---

<a name="s-068"></a>
## S-068: Implementar limpeza de entradas expiradas

**Objetivo:** Criar método que remove entradas expiradas da blacklist (TTL).

**Escopo (IN/OUT):**
- **IN:** Método `_cleanup_expired(data) -> dict` que filtra expirados
- **OUT:** Não implementar limpeza agendada (será chamado no load)

**Arquivos tocados:**
- `services/make-video/app/shorts_blacklist.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def _cleanup_expired(self, data: dict) -> dict:
      """Remove entradas expiradas (TTL)"""
      now = datetime.now(timezone.utc)  # aware UTC (não naive)
      cleaned = {}
      
      for video_id, entry in data.items():
          expires_at = entry.get('expires_at')
          if expires_at:
              # Normalizar para aware UTC
              exp_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
              if exp_dt > now:
                  cleaned[video_id] = entry
              # else: expirado, não adiciona
          else:
              # Sem expiração: manter (legacy)
              cleaned[video_id] = entry
      
      removed_count = len(data) - len(cleaned)
      if removed_count > 0:
          logger.info("expired_entries_cleaned", count=removed_count)
      
      return cleaned
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Filtra entradas expiradas
- [ ] Mantém entradas sem expires_at (legacy)
- [ ] Loga quantidade removida
- [ ] Retorna dict limpo

**Testes:**
- Unit: `tests/test_shorts_blacklist.py::test_cleanup_removes_expired()`

**Observabilidade:**
- Log: `logger.info("expired_entries_cleaned", count=removed_count)`
- Métrica: `counter("blacklist_expired_cleaned_total", value=removed_count)`

**Riscos/Rollback:**
- Risco: Limpeza agressiva remove entradas válidas
- Rollback: Validar lógica de comparação de timezone

**Dependências:** S-067

---

<a name="s-069"></a>
## S-069: Implementar mtime reload automático

**Objetivo:** Implementar reload automático da blacklist quando arquivo é modificado (detectado via mtime).

**Escopo (IN/OUT):**
- **IN:** Verificar mtime em `is_blacklisted()`, reload se mudou
- **OUT:** Não implementar polling ativo

**Arquivos tocados:**
- `services/make-video/app/shorts_blacklist.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def _get_mtime(self) -> float:
      """Retorna timestamp de modificação do arquivo"""
      if self.blacklist_path.exists():
          return self.blacklist_path.stat().st_mtime
      return 0.0
  ```
- Em `is_blacklisted()`, adicionar:
  ```python
  def is_blacklisted(self, video_id: str) -> bool:
      """Verifica se vídeo está na blacklist (com reload automático)"""
      # Reload se arquivo mudou (evita stale reads em multiworker)
      current_mtime = self._get_mtime()
      if current_mtime > self.last_mtime:
          logger.debug("blacklist_reloading", reason="mtime_changed")
          self.blacklist = self._load()
          self.last_mtime = current_mtime
      
      return video_id in self.blacklist
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] mtime verificado em cada chamada
- [ ] Reload apenas se mtime mudou
- [ ] last_mtime atualizado após reload
- [ ] Log indica reload

**Testes:**
- Unit: `tests/test_shorts_blacklist.py::test_mtime_reload_triggers()`

**Observabilidade:**
- Log: `logger.debug("blacklist_reloading", reason="mtime_changed")`
- Métrica: `counter("blacklist_reloads_total")`

**Riscos/Rollback:**
- Risco: Muitos reloads causam lentidão
- Rollback: Adicionar debounce (reload máximo 1x por segundo)

**Dependências:** S-068

---

<a name="s-070"></a>
## S-070: Implementar retry com backoff exponencial

**Objetivo:** Implementar retry com backoff exponencial ao carregar blacklist (evita falhas por JSONDecodeError).

**Escopo (IN/OUT):**
- **IN:** Método `_load()` com retry de 3 tentativas
- **OUT:** Não implementar circuit breaker

**Arquivos tocados:**
- `services/make-video/app/shorts_blacklist.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def _load(self, max_retries: int = 3) -> dict:
      """Carrega blacklist do disco com retry"""
      if not self.blacklist_path.exists():
          return {}
      
      for attempt in range(max_retries):
          try:
              with open(self.blacklist_path) as f:
                  data = json.load(f)
              # Limpar entradas expiradas no load
              return self._cleanup_expired(data)
          except json.JSONDecodeError as e:
              if attempt < max_retries - 1:
                  sleep_time = 0.1 * (2 ** attempt)  # Backoff exponencial: 0.1s, 0.2s, 0.4s
                  logger.warning(
                      "blacklist_load_failed_retrying",
                      attempt=attempt + 1,
                      max_retries=max_retries,
                      sleep_sec=sleep_time,
                      error=str(e)
                  )
                  time.sleep(sleep_time)
                  continue
              # Último retry: retornar vazio e logar
              logger.error(f"⚠️ Blacklist corrompida após {max_retries} tentativas: {e}")
              return {}
          except Exception as e:
              logger.error(f"⚠️ Erro ao carregar blacklist: {e}")
              return {}
      
      return {}
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] 3 tentativas com backoff exponencial
- [ ] Retorna {} se todas falham
- [ ] Loga cada tentativa
- [ ] Cleanup de expirados chamado após load

**Testes:**
- Unit: `tests/test_shorts_blacklist.py::test_retry_on_json_error()`

**Observabilidade:**
- Log: `logger.warning("blacklist_load_failed_retrying", attempt=..., sleep_sec=...)`
- Métrica: `counter("blacklist_load_retries_total")`

**Riscos/Rollback:**
- Risco: Backoff muito longo trava worker
- Rollback: Reduzir max_retries para 2

**Dependências:** S-069

---

<a name="s-071"></a>
## S-071: Implementar método is_blacklisted()

**Objetivo:** Implementar método público que verifica se vídeo está na blacklist.

**Escopo (IN/OUT):**
- **IN:** Método simples de lookup
- **OUT:** Não implementar cache em memória

**Arquivos tocados:**
- `services/make-video/app/shorts_blacklist.py`

**Mudanças exatas:**
- Já implementado parcialmente em S-069, validar:
  ```python
  def is_blacklisted(self, video_id: str) -> bool:
      """Verifica se vídeo está na blacklist (com reload automático)"""
      # Reload se arquivo mudou (já implementado em S-069)
      current_mtime = self._get_mtime()
      if current_mtime > self.last_mtime:
          logger.debug("blacklist_reloading", reason="mtime_changed")
          self.blacklist = self._load()
          self.last_mtime = current_mtime
      
      # Lookup simples
      return video_id in self.blacklist
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Retorna True se video_id na blacklist
- [ ] Retorna False caso contrário
- [ ] Reload automático funciona
- [ ] Performance: O(1) lookup

**Testes:**
- Unit: `tests/test_shorts_blacklist.py::test_is_blacklisted_returns_true()`
- Unit: `tests/test_shorts_blacklist.py::test_is_blacklisted_returns_false()`

**Observabilidade:**
- N/A (método simples)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-069

---

<a name="s-072"></a>
## S-072: Implementar método add()

**Objetivo:** Implementar método que adiciona vídeo à blacklist com locking e atomic write.

**Escopo (IN/OUT):**
- **IN:** Método completo com TTL, locking, atomic write
- **OUT:** Não implementar validação de duplicatas avançada

**Arquivos tocados:**
- `services/make-video/app/shorts_blacklist.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def add(self, video_id: str, reason: str, detection_info: dict = None, confidence: float = 0.0):
      """Adiciona vídeo à blacklist (atomic write com file lock + TTL)"""
      with self._lock():  # Context manager de S-064
          # Recarregar para evitar perda de dados
          self.blacklist = self._load()
          
          # Calcular expiração (TTL) - aware UTC
          now = datetime.now(timezone.utc)
          expires_at = now + timedelta(days=self.ttl_days)
          
          # Incrementar attempts se já existe
          attempts = 1
          if video_id in self.blacklist:
              attempts = self.blacklist[video_id].get("attempts", 0) + 1
          
          # Adicionar entrada
          self.blacklist[video_id] = {
              "video_id": video_id,
              "reason": reason,
              "detected_at": now.isoformat().replace('+00:00', 'Z'),  # MUST-FIX v1.6
              "expires_at": expires_at.isoformat().replace('+00:00', 'Z'),  # MUST-FIX v1.6
              "detection_info": detection_info or {},
              "confidence": confidence,
              "attempts": attempts
          }
          
          # Atomic write
          self._atomic_write(self.blacklist)
          
          logger.info(
              "blacklist_entry_added",
              video_id=video_id,
              reason=reason,
              confidence=confidence,
              attempts=attempts,
              expires_at=expires_at.isoformat()
          )
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Adiciona entrada com todos campos
- [ ] TTL aplicado
- [ ] Lock adquirido antes de write
- [ ] Atomic write executado
- [ ] Attempts incrementado se já existe
- [ ] MUST-FIX v1.6: timestamps com .replace()

**Testes:**
- Unit: `tests/test_shorts_blacklist.py::test_add_creates_entry()`
- Unit: `tests/test_shorts_blacklist.py::test_add_increments_attempts()`

**Observabilidade:**
- Log: `logger.info("blacklist_entry_added", ...)`
- Métrica: `counter("blacklist_entries_added_total", tags={"reason": reason})`

**Riscos/Rollback:**
- Risco: Lock timeout se outro processo travou
- Rollback: Adicionar timeout no lock (10s)

**Dependências:** S-064, S-065, S-066, S-067, S-070

---

<a name="s-073"></a>
## S-073: Implementar método remove()

**Objetivo:** Implementar método que remove vídeo da blacklist (para corrigir falsos positivos).

**Escopo (IN/OUT):**
- **IN:** Método com locking e atomic write
- **OUT:** Não implementar soft-delete

**Arquivos tocados:**
- `services/make-video/app/shorts_blacklist.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def remove(self, video_id: str):
      """Remove vídeo da blacklist (caso seja falso positivo)"""
      with self._lock():
          self.blacklist = self._load()
          
          if video_id in self.blacklist:
              del self.blacklist[video_id]
              
              # Atomic write
              self._atomic_write(self.blacklist)
              
              logger.info("blacklist_entry_removed", video_id=video_id)
          else:
              logger.warning("blacklist_entry_not_found", video_id=video_id)
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Remove entrada se existe
- [ ] Loga warning se não existe
- [ ] Lock adquirido
- [ ] Atomic write executado

**Testes:**
- Unit: `tests/test_shorts_blacklist.py::test_remove_deletes_entry()`
- Unit: `tests/test_shorts_blacklist.py::test_remove_nonexistent_logs_warning()`

**Observabilidade:**
- Log: `logger.info("blacklist_entry_removed", video_id=...)`
- Métrica: `counter("blacklist_entries_removed_total")`

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-072

---

<a name="s-074"></a>
## S-074: Implementar método get_stats()

**Objetivo:** Implementar método que retorna estatísticas da blacklist (total, por reason, oldest, newest).

**Escopo (IN/OUT):**
- **IN:** Método que retorna dict com stats
- **OUT:** Não implementar stats avançadas (P50/P95)

**Arquivos tocados:**
- `services/make-video/app/shorts_blacklist.py`

**Mudanças exatas:**
- Criar método:
  ```python
  def get_stats(self) -> dict:
      """Retorna estatísticas da blacklist"""
      return {
          "total_blocked": len(self.blacklist),
          "by_reason": self._count_by_reason(),
          "oldest_entry": self._get_oldest(),
          "newest_entry": self._get_newest(),
          "backend": "json_file"
      }
  
  def _count_by_reason(self) -> dict:
      counts = {}
      for entry in self.blacklist.values():
          reason = entry.get("reason", "unknown")
          counts[reason] = counts.get(reason, 0) + 1
      return counts
  
  def _get_oldest(self) -> str:
      if not self.blacklist:
          return None
      oldest = min(self.blacklist.values(), key=lambda e: e.get("detected_at", ""))
      return oldest.get("detected_at")
  
  def _get_newest(self) -> str:
      if not self.blacklist:
          return None
      newest = max(self.blacklist.values(), key=lambda e: e.get("detected_at", ""))
      return newest.get("detected_at")
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Retorna total_blocked
- [ ] Retorna contagem por reason
- [ ] Retorna oldest e newest entries
- [ ] Não falha se blacklist vazia

**Testes:**
- Unit: `tests/test_shorts_blacklist.py::test_get_stats_structure()`

**Observabilidade:**
- N/A (método de leitura)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-072

---

<a name="s-075"></a>
## S-075: Criar testes de concurrent access

**Objetivo:** Criar testes que validam que file locking previne race conditions em acesso concorrente.

**Escopo (IN/OUT):**
- **IN:** Testes com multiprocessing
- **OUT:** Não testar com threads (fcntl não funciona bem com threads)

**Arquivos tocados:**
- `services/make-video/tests/test_shorts_blacklist.py`

**Mudanças exatas:**
- Criar teste:
  ```python
  import multiprocessing
  
  def _add_entry(blacklist_path, video_id):
      """Worker que adiciona entrada"""
      bl = ShortsBlacklist(blacklist_path)
      bl.add(video_id, reason="test", confidence=0.8)
  
  def test_concurrent_add_no_data_loss(tmp_path):
      blacklist_path = tmp_path / "blacklist.json"
      blacklist_path.write_text("{}")
      
      # Criar 10 processos adicionando simultaneamente
      processes = []
      for i in range(10):
          p = multiprocessing.Process(
              target=_add_entry,
              args=(str(blacklist_path), f"video_{i}")
          )
          processes.append(p)
          p.start()
      
      # Aguardar todos
      for p in processes:
          p.join()
      
      # Validar: todos os 10 vídeos devem estar na blacklist
      bl = ShortsBlacklist(str(blacklist_path))
      assert len(bl.blacklist) == 10
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Teste executa 10 processos concorrentes
- [ ] Nenhum dado perdido
- [ ] Arquivo final válido (não corrompido)
- [ ] Teste passa

**Testes:**
- Self-test: `pytest tests/test_shorts_blacklist.py::test_concurrent_add_no_data_loss -v`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: Teste flaky
- Rollback: Aumentar número de processos para aumentar probabilidade de race

**Dependências:** S-072, S-064

---

<a name="s-076"></a>
## S-076: Criar testes de TTL expiration

**Objetivo:** Criar testes que validam que entradas expiradas são removidas na limpeza.

**Escopo (IN/OUT):**
- **IN:** Testes que manipulam timestamps
- **OUT:** Não testar com tempo real (usar mock)

**Arquivos tocados:**
- `services/make-video/tests/test_shorts_blacklist.py`

**Mudanças exatas:**
- Criar teste:
  ```python
  from datetime import timezone, timedelta
  from unittest.mock import patch
  
  def test_expired_entries_removed_on_load(tmp_path):
      blacklist_path = tmp_path / "blacklist.json"
      
      # Criar entrada expirada (90 dias no passado)
      now = datetime.now(timezone.utc)
      expired_time = now - timedelta(days=91)
      
      data = {
          "video_old": {
              "video_id": "video_old",
              "detected_at": expired_time.isoformat().replace('+00:00', 'Z'),
              "expires_at": (expired_time + timedelta(days=90)).isoformat().replace('+00:00', 'Z'),
              "reason": "test"
          },
          "video_new": {
              "video_id": "video_new",
              "detected_at": now.isoformat().replace('+00:00', 'Z'),
              "expires_at": (now + timedelta(days=90)).isoformat().replace('+00:00', 'Z'),
              "reason": "test"
          }
      }
      
      blacklist_path.write_text(json.dumps(data))
      
      # Carregar blacklist
      bl = ShortsBlacklist(str(blacklist_path))
      
      # Validar: video_old removido, video_new mantido
      assert "video_old" not in bl.blacklist
      assert "video_new" in bl.blacklist
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Entradas expiradas são removidas
- [ ] Entradas válidas são mantidas
- [ ] Teste passa
- [ ] Usa timestamps mock

**Testes:**
- Self-test: `pytest tests/test_shorts_blacklist.py::test_expired_entries_removed_on_load -v`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-068, S-070

---

## Mapa de Dependências (Pack 06)

```
S-063 (estrutura) → S-064, S-069
S-064 (locking) → S-065, S-072, S-075
S-065 (atomic write) → S-066, S-072
S-066 (TTL) → S-067
S-067 (timestamps MUST-FIX) → S-068
S-068 (cleanup expirados) → S-070, S-076
S-069 (mtime reload) → S-070, S-071
S-070 (retry backoff) → S-071, S-072
S-071 (is_blacklisted) ← S-069, S-070
S-072 (add) ← S-064, S-065, S-066, S-067, S-070
S-073 (remove) ← S-072
S-074 (get_stats) ← S-072
S-075 (teste concurrent) ← S-072, S-064
S-076 (teste TTL) ← S-068, S-070
```

**Próximo pack:** Sprint 07 - RedisBlacklistBackend + stats HINCRBY + fallback manager
