# 🚀 Guia Rápido - Testes do Audio Normalization

## Início Rápido

### 1. Preparação

```bash
# Entre no diretório do serviço
cd services/audio-normalization

# Certifique-se de que há um arquivo de teste
# Coloque qualquer arquivo de áudio em ./uploads/
cp ~/Downloads/seu_audio.mp3 uploads/test.mp3
```

### 2. Inicie o Serviço

```bash
# Com Docker
docker-compose up -d

# Ou manualmente (se preferir)
# Terminal 1 - Redis
redis-server

# Terminal 2 - Celery Worker
celery -A app.celery_config worker --loglevel=info

# Terminal 3 - API FastAPI
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 3. Execute os Testes

```bash
# Execute o script de teste completo
python test_all_features.py
```

## O que o Script Testa

### Teste 1: Baseline ✅
- **Parâmetros:** Nenhum
- **Espera:** Conversão simples para .webm
- **Duração:** ~5s

### Teste 2: Remove Noise ✅
- **Parâmetros:** `remove_noise=True`
- **Espera:** Remoção de ruído de fundo
- **Duração:** ~30-60s

### Teste 3: Convert to Mono ✅
- **Parâmetros:** `convert_to_mono=True`
- **Espera:** Conversão para mono
- **Duração:** ~5s

### Teste 4: Apply Highpass Filter ✅
- **Parâmetros:** `apply_highpass_filter=True`
- **Espera:** Filtro high-pass @ 80Hz
- **Duração:** ~10-20s

### Teste 5: Set Sample Rate 16kHz ✅
- **Parâmetros:** `set_sample_rate_16k=True`
- **Espera:** Resample para 16kHz
- **Duração:** ~5s

### Teste 6: Isolate Vocals 🎤
- **Parâmetros:** `isolate_vocals=True`
- **Espera:** Separação de vocais com OpenUnmix
- **Duração:** ~60-120s
- **NOTA:** Pode falhar com OOM em áudios longos (é esperado)

## Output Esperado

### Sucesso Total ✅

```
================================================================================
🧪 TESTE: Remove Noise
   Parâmetros: {'remove_noise': True}
================================================================================
✅ Job criado: abc123
⏳ Aguardando conclusão do job abc123...
   [1] Status: processing, Progress: 0.0%
   [2] Status: processing, Progress: 10.0%
   [3] Status: processing, Progress: 50.0%
   [4] Status: completed, Progress: 100.0%
✅ Job abc123 COMPLETADO em 45.2s
✅ TESTE PASSOU: Remove Noise

================================================================================
📊 RESUMO DOS TESTES
================================================================================

Total de testes: 6
✅ Passou: 6
❌ Falhou: 0
Taxa de sucesso: 100.0%

🎉 TODOS OS TESTES PASSARAM!
```

### Falha Controlada (Resiliência) ✅

```
================================================================================
🧪 TESTE: Isolate Vocals
   Parâmetros: {'isolate_vocals': True}
================================================================================
✅ Job criado: def456
⏳ Aguardando conclusão do job def456...
   [1] Status: processing, Progress: 0.0%
   [2] Status: processing, Progress: 5.0%
   [3] Status: failed, Progress: 5.0%
❌ Job def456 FALHOU: Out of memory during vocal isolation
❌ TESTE FALHOU: Isolate Vocals - Out of memory

================================================================================
🛡️ TESTE DE RESILIÊNCIA DA API
================================================================================
   [1/10] ✅ API respondendo
   [2/10] ✅ API respondendo
   ...
   [10/10] ✅ API respondendo
✅ API PERMANECEU RESILIENTE durante todos os testes

⚠️ ALGUNS TESTES FALHARAM - mas a API permaneceu resiliente!
```

## Testes Manuais via cURL

### Criar Job com Noise Removal

```bash
curl -X POST http://localhost:8001/jobs \
  -F "file=@uploads/test.mp3" \
  -F "remove_noise=true"

# Response:
# {
#   "id": "abc123",
#   "status": "queued",
#   "filename": "test.mp3"
# }
```

### Consultar Status do Job

```bash
curl http://localhost:8001/jobs/abc123

# Response (processando):
# {
#   "id": "abc123",
#   "status": "processing",
#   "progress": 45.5
# }

# Response (completo):
# {
#   "id": "abc123",
#   "status": "completed",
#   "progress": 100.0,
#   "output_file": "/path/to/processed/abc123.webm"
# }

# Response (falhou - MAS API NÃO QUEBRA):
# {
#   "id": "abc123",
#   "status": "failed",
#   "error_message": "Out of memory during vocal isolation",
#   "progress": 0.0
# }
```

### Baixar Arquivo Processado

```bash
curl -O http://localhost:8001/jobs/abc123/download
```

## Verificação de Resiliência

### O que DEVE acontecer:

1. ✅ API continua respondendo mesmo com tasks falhando
2. ✅ Endpoint `/health` sempre retorna 200
3. ✅ Endpoint `/jobs/{job_id}` sempre retorna JSON válido
4. ✅ Jobs falhados têm `error_message` descritivo

### O que NÃO deve acontecer:

1. ❌ API quebrar ou parar de responder
2. ❌ Endpoint retornar 500 sem JSON
3. ❌ Jobs ficarem em estado indefinido
4. ❌ Workers crasharem

## Troubleshooting

### Script não encontra arquivo de áudio

```bash
# Certifique-se de que há arquivo em uploads/
ls -la uploads/

# Se vazio, adicione um:
cp ~/Downloads/test.mp3 uploads/
```

### API não está respondendo

```bash
# Verifique se serviços estão rodando
docker-compose ps

# Ou manualmente:
curl http://localhost:8001/health

# Logs:
docker-compose logs -f
```

### Job fica em "processing" para sempre

```bash
# Verifique se worker Celery está rodando
docker-compose ps celery

# Logs do worker:
docker-compose logs -f celery

# Reinicie worker se necessário:
docker-compose restart celery
```

### Teste falha com OOM (Out of Memory)

Isso é **esperado** para:
- `isolate_vocals` com áudios > 3 minutos
- `remove_noise` com áudios > 5 minutos

**Solução:** Use áudios menores ou aumente memória disponível

## Próximos Passos

1. ✅ Execute `python test_all_features.py`
2. ✅ Verifique resumo de testes
3. ✅ Confirme que API permaneceu resiliente
4. ✅ Teste manualmente com cURL se necessário
5. ✅ Leia `CORREÇÕES_V4.md` para detalhes técnicos

---

**Dúvidas?** Consulte os logs em `./logs/` ou o arquivo `CORREÇÕES_V4.md`
