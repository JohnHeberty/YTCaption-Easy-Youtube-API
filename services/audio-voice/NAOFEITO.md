# ❌ NÃO FEITO - Audio Voice Service (F5-TTS pt-BR)

Este arquivo rastreia tarefas pendentes do plano de produção baseado em **SPRINTS-PRODUCAO.md**.

---

## 📊 **Visão Geral**

- **Total de Sprints:** 5 (Sprint 0 completo ✅)
- **Tempo estimado restante:** ~3.5 semanas
- **Prioridade:** ALTA (sistema precisa ser resiliente em produção)
- **Última atualização:** 2025-11-26

---

## **Sprint 1: Validações Avançadas** (1 semana)

**Status:** ⏳ Não iniciado  
**Prioridade:** ALTA  
**Bloqueadores:** Nenhum (Sprint 0 completo)

### 1.1 num2words Integration ⏳ PENDENTE
- **Descrição:** Integrar num2words para conversão de números em pt-BR
- **Arquivos:** `requirements.txt`, `app/validators.py`
- **Tempo estimado:** 2h
- **Passos:**
  1. Adicionar `num2words>=0.5.13` ao `requirements.txt`
  2. Implementar `_convert_numbers_to_words()` em `validators.py`
  3. Integrar em `normalize_text_ptbr()`
  4. Testar com exemplos: "123" → "cento e vinte e três"
  5. Rebuild containers e validar logs

**Critérios de sucesso:**
- [ ] num2words instalado sem erros
- [ ] Conversão funciona: "O ano é 2025" → "o ano é dois mil e vinte e cinco"
- [ ] Warning `num2words not installed` removido dos logs

---

### 1.2 Audio Preprocessing Validation ⏳ PENDENTE
- **Descrição:** Validação robusta de arquivos de áudio
- **Arquivos:** `app/validators.py`
- **Tempo estimado:** 3h
- **Features:**
  - Sample rate: Apenas 16kHz, 22.05kHz, 24kHz
  - Formato: WAV, MP3, FLAC
  - Canais: Mono (converter stereo automaticamente)
  - Ruído de fundo: Detectar e avisar
  - Normalização automática de volume

**Critérios de sucesso:**
- [ ] Rejeita áudios fora dos sample rates aceitos
- [ ] Converte stereo para mono automaticamente
- [ ] Detecta ruído > -30dB e emite warning
- [ ] Normaliza áudio para target_rms

---

### 1.3 Portuguese Vocabulary Validation ⏳ PENDENTE
- **Descrição:** Validar caracteres suportados pelo modelo pt-BR
- **Arquivos:** `app/validators.py`
- **Tempo estimado:** 2h
- **Features:**
  - Carregar vocab do modelo (2545 tokens)
  - Detectar caracteres não suportados
  - Sugerir substituições (ex: "ç" → "c")
  - Modo strict vs lenient

**Critérios de sucesso:**
- [ ] Detecta caracteres fora do vocab pt-BR
- [ ] Sugere substituições válidas
- [ ] Modo lenient remove caracteres desconhecidos
- [ ] Modo strict rejeita texto inválido

---

### 1.4 Text Length Validation ⏳ PENDENTE
- **Descrição:** Validar comprimento de texto para evitar OOM
- **Arquivos:** `app/validators.py`, `app/f5tts_client.py`
- **Tempo estimado:** 1h
- **Features:**
  - Comprimento mínimo: 10 caracteres
  - Comprimento máximo: 500 caracteres (ajustável)
  - Batch splitting automático para textos longos
  - Avisos de qualidade para textos > 300 chars

**Critérios de sucesso:**
- [ ] Rejeita textos < 10 caracteres
- [ ] Divide textos > 500 chars em batches
- [ ] Emite warning para textos > 300 chars
- [ ] Testes com textos 1, 50, 300, 600 caracteres

---

## **Sprint 2: Error Handling Resiliente** (1 semana)

**Status:** ⏳ Não iniciado  
**Prioridade:** ALTA  
**Dependências:** Sprint 1 concluído

### 2.1 Retry Logic com Exponential Backoff ⏳ PENDENTE
- **Descrição:** Implementar retry automático para falhas temporárias
- **Arquivos:** `app/f5tts_client.py`
- **Tempo estimado:** 4h
- **Features:**
  - Max retries: 3
  - Backoff: 1s, 2s, 4s
  - CUDA cache clear em OOM
  - Logging detalhado de tentativas
  - Métricas de retry rate

**Implementação:**
```python
def _infer_with_retry(self, max_retries=3):
    for attempt in range(max_retries):
        try:
            return infer_process(...)
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            time.sleep(2 ** attempt)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
```

**Critérios de sucesso:**
- [ ] OOM recovery com cache clear
- [ ] Retry automático em falhas temporárias
- [ ] Logs mostram tentativas e backoff
- [ ] Taxa de sucesso > 95% em 100 testes

---

### 2.2 Circuit Breaker Pattern ⏳ PENDENTE
- **Descrição:** Proteger sistema de falhas em cascata
- **Arquivos:** `app/circuit_breaker.py` (novo)
- **Tempo estimado:** 5h
- **Features:**
  - Estados: CLOSED, OPEN, HALF_OPEN
  - Threshold: 5 falhas em 60s → OPEN
  - Recovery timeout: 30s
  - Métricas: failure_rate, success_rate

**Critérios de sucesso:**
- [ ] Abre circuito após 5 falhas
- [ ] Entra em HALF_OPEN após 30s
- [ ] Fecha circuito após 1 sucesso
- [ ] Logs mostram transições de estado

---

### 2.3 Graceful Degradation ⏳ PENDENTE
- **Descrição:** Fallbacks quando serviços dependentes falham
- **Arquivos:** `app/f5tts_client.py`
- **Tempo estimado:** 3h
- **Features:**
  - F5-TTS indisponível → Whisper CPU fallback
  - Vocos indisponível → Griffin-Lim fallback
  - Reference text missing → Transcrição automática
  - Múltiplos níveis de qualidade

**Critérios de sucesso:**
- [ ] Degrada de GPU → CPU quando OOM
- [ ] Usa fallback de vocoder se necessário
- [ ] Logs indicam nível de degradação
- [ ] Qualidade reduzida mas funcional

---

### 2.4 Dead Letter Queue (DLQ) ⏳ PENDENTE
- **Descrição:** Capturar jobs que falharam múltiplas vezes
- **Arquivos:** `app/celery_tasks.py`
- **Tempo estimado:** 2h
- **Features:**
  - Redis DLQ separada: `audio_voice_dlq`
  - Max retries antes de DLQ: 3
  - TTL da DLQ: 7 dias
  - Dashboard de monitoramento

**Critérios de sucesso:**
- [ ] Jobs com 3+ falhas vão para DLQ
- [ ] DLQ pode ser reprocessada manualmente
- [ ] Logs mostram job_id, erro, timestamp
- [ ] Métricas de DLQ rate < 1%

---

## **Sprint 3: Logging Estruturado** (3 dias)

**Status:** ⏳ Não iniciado  
**Prioridade:** MÉDIA  
**Dependências:** Sprint 2 concluído

### 3.1 JSON Structured Logging ⏳ PENDENTE
- **Descrição:** Logs em formato JSON para análise automatizada
- **Arquivos:** `app/logger.py`
- **Tempo estimado:** 4h
- **Features:**
  - Formato: JSON com timestamp, level, message, context
  - Campos customizados: job_id, user_id, duration_ms
  - Integração com ELK Stack
  - Log rotation: 100MB/file, 7 dias

**Exemplo:**
```json
{
  "timestamp": "2025-11-26T04:04:52.558Z",
  "level": "INFO",
  "message": "F5-TTS generating",
  "job_id": "job_469763e77a66",
  "text_length": 63,
  "voice_id": "voice_07b851ab0a61",
  "nfe_step": 16,
  "speed": 1.0
}
```

**Critérios de sucesso:**
- [ ] Todos os logs em formato JSON
- [ ] Campos customizados presentes
- [ ] Log rotation funcional
- [ ] Queries funcionam no ELK

---

### 3.2 Performance Metrics Logging ⏳ PENDENTE
- **Descrição:** Métricas de latência e VRAM
- **Arquivos:** `app/f5tts_client.py`, `app/celery_tasks.py`
- **Tempo estimado:** 3h
- **Métricas:**
  - `model_load_time_ms`: Tempo de carregamento
  - `inference_time_ms`: Tempo de inferência
  - `vram_allocated_mb`: VRAM alocada
  - `vram_reserved_mb`: VRAM reservada
  - `audio_duration_s`: Duração do áudio gerado
  - `characters_per_second`: Taxa de processamento

**Critérios de sucesso:**
- [ ] Métricas logadas em cada job
- [ ] Dashboard Grafana com gráficos
- [ ] Alertas se latência > 10s
- [ ] P95 latency < 5s

---

### 3.3 Error Categorization ⏳ PENDENTE
- **Descrição:** Categorizar erros para análise
- **Arquivos:** `app/exceptions.py`
- **Tempo estimado:** 2h
- **Categorias:**
  - `VALIDATION_ERROR`: Input inválido
  - `RESOURCE_ERROR`: OOM, GPU indisponível
  - `MODEL_ERROR`: Erro interno do F5-TTS
  - `TIMEOUT_ERROR`: Operação excedeu timeout
  - `UNKNOWN_ERROR`: Erro não categorizado

**Critérios de sucesso:**
- [ ] Todos os erros categorizados
- [ ] Logs incluem category
- [ ] Dashboard mostra distribuição por categoria
- [ ] Taxa de UNKNOWN_ERROR < 5%

---

## **Sprint 4: Testing** (1 semana)

**Status:** ⏳ Não iniciado  
**Prioridade:** ALTA  
**Dependências:** Sprints 1-3 concluídos

### 4.1 Unit Tests (80%+ Coverage) ⏳ PENDENTE
- **Descrição:** Testes unitários completos
- **Arquivos:** `tests/test_validators.py`, `tests/test_f5tts_client.py`
- **Tempo estimado:** 8h
- **Coverage alvo:** 80%+
- **Módulos:**
  - `validators.py`: 100% coverage
  - `f5tts_client.py`: 80% coverage
  - `celery_tasks.py`: 70% coverage

**Testes críticos:**
```python
def test_normalize_text_ptbr():
    assert normalize_text_ptbr("OLÁ MUNDO 123!") == "olá mundo cento e vinte e três!"

def test_validate_audio_path_invalid():
    with pytest.raises(InvalidAudioException):
        validate_audio_path("/invalid/path.wav")

def test_generate_dubbing_with_retry():
    # Simula OOM e verifica retry
    ...
```

**Critérios de sucesso:**
- [ ] Coverage > 80%
- [ ] Todos os testes passam
- [ ] CI/CD integrado (GitHub Actions)
- [ ] Tempo de execução < 2 min

---

### 4.2 Integration Tests ⏳ PENDENTE
- **Descrição:** Testes end-to-end do fluxo completo
- **Arquivos:** `tests/test_integration.py`
- **Tempo estimado:** 6h
- **Cenários:**
  - Clone de voz → Dubbing com voz clonada
  - Dubbing com preset existente
  - Dubbing com texto longo (>500 chars)
  - Falha e retry automático
  - OOM recovery

**Critérios de sucesso:**
- [ ] Fluxo completo funciona
- [ ] Áudio gerado não está silencioso
- [ ] VRAM não excede 4GB
- [ ] Latência < 10s para 100 chars

---

### 4.3 Load Testing ⏳ PENDENTE
- **Descrição:** Testar sob carga
- **Ferramentas:** Locust, K6
- **Tempo estimado:** 4h
- **Cenários:**
  - 10 req/s por 1 min
  - 50 req/s por 30s (spike test)
  - 100 concurrent users
  - Soak test: 5 req/s por 1h

**Métricas alvo:**
- P95 latency < 8s
- Error rate < 1%
- VRAM usage estável
- Sem memory leaks

**Critérios de sucesso:**
- [ ] Sistema aguenta 10 req/s
- [ ] Spike test não causa crashes
- [ ] Sem memory leaks em 1h
- [ ] Métricas dentro dos alvos

---

### 4.4 Chaos Engineering ⏳ PENDENTE
- **Descrição:** Testar resiliência a falhas
- **Ferramentas:** Chaos Mesh, manual simulation
- **Tempo estimado:** 3h
- **Cenários:**
  - Redis down durante job
  - GPU OOM simulado
  - Network latency +500ms
  - Celery worker restart

**Critérios de sucesso:**
- [ ] Graceful degradation funciona
- [ ] Circuit breaker abre corretamente
- [ ] DLQ captura jobs falhados
- [ ] Sistema se recupera automaticamente

---

## **Sprint 5: Otimizações** (3 dias)

**Status:** ⏳ Não iniciado  
**Prioridade:** MÉDIA  
**Dependências:** Sprint 4 concluído

### 5.1 LRU Cache para VoiceProfiles ⏳ PENDENTE
- **Descrição:** Cache de perfis de voz em memória
- **Arquivos:** `app/cache.py` (novo), `app/f5tts_client.py`
- **Tempo estimado:** 3h
- **Features:**
  - LRU cache com 100 perfis
  - TTL: 1 hora
  - Cache hit rate > 80%
  - Invalidação manual

**Implementação:**
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_voice_profile(voice_id: str) -> VoiceProfile:
    ...
```

**Critérios de sucesso:**
- [ ] Cache hit rate > 80%
- [ ] Latência reduzida em 30%
- [ ] Memória adicional < 500MB
- [ ] Logs mostram cache hits/misses

---

### 5.2 Model Warm-up on Startup ⏳ PENDENTE
- **Descrição:** Pré-carregar modelo no startup
- **Arquivos:** `app/f5tts_client.py`
- **Tempo estimado:** 2h
- **Features:**
  - Carregar modelo no `__init__`
  - Dummy inference para warm-up CUDA
  - Health check aguarda warm-up
  - Logs de startup time

**Critérios de sucesso:**
- [ ] Modelo carregado antes de aceitar jobs
- [ ] Primeira inferência < 1s
- [ ] Health check retorna ready=true
- [ ] Startup time documentado

---

### 5.3 Batch Processing para Múltiplos Jobs ⏳ PENDENTE
- **Descrição:** Processar múltiplos jobs em um batch
- **Arquivos:** `app/celery_tasks.py`
- **Tempo estimado:** 5h
- **Features:**
  - Agrupar até 5 jobs
  - Batch inference do F5-TTS
  - Timeout: 30s para agrupar
  - Métricas de throughput

**Critérios de sucesso:**
- [ ] Throughput aumenta 2x
- [ ] VRAM usage otimizado
- [ ] Latência individual < 10s
- [ ] Batch size médio > 3

---

### 5.4 GPU Memory Optimization ⏳ PENDENTE
- **Descrição:** Reduzir footprint de VRAM
- **Arquivos:** `app/f5tts_client.py`, `app/custom_loader.py`
- **Tempo estimado:** 4h
- **Features:**
  - FP16 inference (já implementado)
  - Gradient checkpointing
  - Aggressive cache clearing
  - Monitoramento contínuo

**Métricas alvo:**
- VRAM idle: < 100MB
- VRAM peak: < 1.5GB
- Sem fragmentação após 1000 jobs

**Critérios de sucesso:**
- [ ] VRAM usage reduzido 15%
- [ ] Sem fragmentação
- [ ] Métricas dentro dos alvos
- [ ] Documentação de otimizações

---

## **Bugs Conhecidos** 🐛

### 🔴 **CRÍTICO - RESOLVIDO ✅**
- **Sprint 0 Fix:** Batches vazios no `chunk_text()` causando `TypeError: encoding without a string argument`
  - **Solução:** Pré-processamento remove espaços antes de pontuação
  - **Status:** ✅ Corrigido em 2025-11-26

### 🟡 **MÉDIO**
- **num2words não instalado:** Warning nos logs, conversão de números desabilitada
  - **Sprint:** 1.1
  - **Prioridade:** ALTA
  - **Estimativa:** 2h

### 🟢 **BAIXO**
- **Linting warnings:** Uso de f-strings em logs em vez de lazy formatting
  - **Sprint:** 3.1 (refatoração de logs)
  - **Prioridade:** BAIXA
  - **Estimativa:** 1h

---

## **Roadmap Timeline** 📅

```
Semana 1: Sprint 1 (Validações)
├── Dia 1-2: num2words + Audio preprocessing
├── Dia 3-4: Vocabulary validation
└── Dia 5: Text length validation + testes

Semana 2: Sprint 2 (Error Handling)
├── Dia 1: Retry logic
├── Dia 2-3: Circuit breaker
├── Dia 4: Graceful degradation
└── Dia 5: DLQ + integração

Semana 3: Sprint 3 + 4 (Logging + Tests)
├── Dia 1-2: JSON logging + métricas
├── Dia 3: Error categorization
├── Dia 4-5: Unit tests (80% coverage)

Semana 4: Sprint 4 + 5 (Tests + Optimizations)
├── Dia 1-2: Integration + Load tests
├── Dia 3: Chaos engineering
├── Dia 4-5: LRU cache + Model warm-up + Batch processing
```

**Total:** ~4 semanas (20 dias úteis)

---

## **Métricas de Sucesso** 📊

| Métrica | Alvo | Atual | Sprint |
|---------|------|-------|--------|
| Test Coverage | 80%+ | 0% | 4.1 |
| P95 Latency | < 5s | ~8s | 5.3 |
| Error Rate | < 1% | ~5% | 2.1-2.4 |
| VRAM Usage | < 1.5GB | 1.27GB ✅ | 5.4 |
| Cache Hit Rate | > 80% | N/A | 5.1 |
| Throughput | 10 req/s | ~2 req/s | 5.3 |
| DLQ Rate | < 1% | N/A | 2.4 |
| Uptime | 99.5%+ | N/A | 2.2 |

---

## **Dependências Externas** 📦

Pending installations:
- `num2words>=0.5.13` (Sprint 1.1)
- `prometheus-client>=0.19.0` (Sprint 3.2)
- `locust>=2.17.0` (Sprint 4.3)
- `pytest-cov>=4.1.0` (Sprint 4.1)

---

**Última revisão:** 2025-11-26 04:10 UTC  
**Autor:** GitHub Copilot  
**Referência:** SPRINTS-PRODUCAO.md, FEITO.md
