# 🧪 Test Suite - Make Video Service

## 📋 Estrutura dos Testes

Suite completa de testes para todos os módulos do serviço make-video.

### Arquivos de Teste

| Arquivo | Descrição | Testes |
|---------|-----------|--------|
| **test_01_celery_config.py** | Configuração Celery | 8 testes |
| **test_02_task_sending.py** | Envio de tasks (BUG PROOF) | 5 testes |
| **test_03_workaround.py** | Workaround Kombu | 2 testes |
| **test_04_core.py** | Core modules (config, models) | 6 testes |
| **test_05_infrastructure.py** | Infrastructure (Redis, Circuit Breaker) | 8 classes |
| **test_06_services.py** | Services (shorts, video, subtitle) | 10 testes |
| **test_07_domain_stages.py** | Domain stages (pipeline) | 12 testes |
| **test_08_video_processing.py** | Video processing (detectors, validators) | 14 testes |
| **test_09_utils_subtitles.py** | Utils e subtitle processing | 10 testes |
| **test_10_api_pipeline.py** | API endpoints e integração | 13 testes |

---

## 🎯 Objetivo dos Testes

1. **test_01-03**: Prova bug Celery 5.3.4 + Kombu e valida workaround
2. **test_04-05**: Valida módulos core e infraestrutura
3. **test_06-09**: Testa todos os serviços, stages, processamento de vídeo
4. **test_10**: Testa API, pipeline e integração end-to-end

---

## ⚙️ Como Rodar

### Todos os Testes
```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video
pytest tests/ -v -s
```

### Teste Específico
```bash
pytest tests/test_01_celery_config.py -v -s
```

### Por Módulo
```bash
pytest tests/test_06_services.py -v -s
pytest tests/test_07_domain_stages.py -v -s
```

### Apenas Testes Rápidos (Skip Integration)
```bash
pytest tests/ -v -s -m "not integration"
```

---

## 📊 Resultados Esperados

### ✅ PASS Obrigatórios
- **test_01**: 8/8 - Celery config OK
- **test_03**: 2/2 - Workaround funciona
- **test_04**: 6/6 - Core modules OK

### ⚠️ FAIL Conhecidos (PROVA DO BUG)
- **test_02**: 
  - ✅ test_send_task_kombu_direct (PASS - Kombu funciona)
  - ❌ test_send_task_delay (FAIL - Celery bug)
  - ❌ test_send_task_apply_async (FAIL - Celery bug)
  - ❌ test_send_task_send_task (FAIL - Celery bug)

### 🔄 SKIP Esperados
- Testes de integração marcados com `@pytest.mark.integration`
- Módulos ainda não implementados

---

## 🐛 Bug Documentado

**Celery 5.3.4 + Kombu 5.6.2 + Redis**

❌ **Falham silenciosamente**:
- `task.delay()`
- `task.apply_async()`
- `celery_app.send_task()`

✅ **Funciona**:
- Kombu direct publish: `Producer.publish()`
- Implementado em: `app/infrastructure/celery_workaround.py`

---

## 🔧 Workaround Aplicado

**Arquivo**: `app/main.py` linha ~670

**Antes**:
```python
task_result = process_make_video.delay(job_id)
```

**Depois**:
```python
from .infrastructure.celery_workaround import send_make_video_task_workaround
task_id = send_make_video_task_workaround(job_id, settings['redis_url'])
```

---

## 📝 Notas Importantes

### Workers Rodando
Se workers (Docker ou local) estiverem rodando:
- Tasks serão consumidos INSTANTANEAMENTE
- Queue length = 0 é NORMAL (workers consumiram)
- `test_03_workaround.py` pode mostrar queue=0 (OK!)

### Workers Parados
Para testar que mensagens chegam à fila:
```bash
# Parar workers Docker
docker stop ytcaption-make-video-celery
docker stop ytcaption-make-video-celery-beat

# Rodar teste
pytest tests/test_03_workaround.py -v -s

# Queue length > 0 = mensagens na fila ✅
```

### Redis Monitor
Para debug visual:
```bash
redis-cli -h 192.168.1.110 -p 6379
> MONITOR
```

---

## 🎓 Lições Aprendidas

1. **Celery 5.3.4 tem bug crítico** com Redis transport
2. **Queue length = 0** não significa falha (workers podem ter consumido)
3. **Redis MONITOR** é essencial para debug de mensagens
4. **Kombu direct** é solução confiável para bugs do Celery
5. **Tests provam o bug** antes de implementar workaround

---

## 📦 Dependências

```bash
pip install pytest pytest-asyncio redis kombu celery fastapi
```

---

## ✅ Checklist Validação

- [ ] test_01: 8/8 PASS
- [ ] test_02: Kombu PASS, Celery FAIL (esperado)
- [ ] test_03: 2/2 PASS
- [ ] test_04-09: Módulos importam sem erro
- [ ] test_10: API responde health check
- [ ] Workaround aplicado em main.py
- [ ] Workers consomem tasks via workaround

---

## 🚀 Próximos Passos

1. ✅ Suite de testes completa (DONE)
2. ⏳ Rodar todos os testes
3. ⏳ Testar end-to-end com workers
4. ⏳ Validar geração de vídeo real
5. ⏳ Docker compose testing

---

**Última atualização**: Após reestruturação completa da pasta tests  
**Status**: Suite criada, aguardando execução  
**Cobertura**: ~88 testes cobrindo todos os 73 módulos de app/
