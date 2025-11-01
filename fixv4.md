# 🔧 PLANO DE CORREÇÕES v4 - EXECUÇÃO DETALHADA

**Data:** 2025-11-01  
**Base:** analisev4.md  
**Status:** Pronto para Implementação  

---

## 📋 VALIDAÇÃO DA ANÁLISE

### ✅ Problemas Confirmados:

1. **✓ Isolamento Vocal com IA**: Confirmado - 100+ referências encontradas
2. **✓ Referências GPU**: Confirmado - torch/cuda em múltiplos métodos
3. **✓ Requisições Duplicadas**: Confirmado - job_id usa timestamp (não idempotente)
4. **✓ Progresso em Chunks**: Confirmado - flag `is_chunk=True` desabilita updates

### ✅ Soluções Validadas:

1. **✓ Remoção Completa**: Solução viável - remover imports, métodos, parâmetros
2. **✓ 100% CPU**: Solução viável - remover torch mantém pydub/scipy/numpy
3. **✓ Idempotência**: Solução viável - hash sem timestamp + verificação Redis
4. **✓ Progresso Real-Time**: Solução viável - updates dentro do loop de chunks

---

## 🎯 PLANO DE EXECUÇÃO

---

## FASE 1: REMOVER ISOLAMENTO VOCAL + GPU (audio-normalization)

### ✅ ARQUIVO 1: `services/audio-normalization/requirements.txt`

**Ação:** Remover dependências ML/GPU

**Código Atual:**
```txt
# === ML-BASED VOCAL ISOLATION ===
openunmix==1.3.0
torch==2.9.0
torchaudio==2.9.0
```

**Código Novo:**
```txt
# (remover seção completa)
```

**Validação:**
- requirements.txt não deve conter: openunmix, torch, torchaudio

---

### ✅ ARQUIVO 2: `services/audio-normalization/app/config.py`

**Ação:** Remover configuração OpenUnmix

**Localização:** Linhas 81-87

**Código Atual:**
```python
# ===== OPENUNMIX =====
'openunmix': {
    'model_name': os.getenv('OPENUNMIX_MODEL_NAME', 'umx'),
    'target': os.getenv('OPENUNMIX_TARGET', 'vocals'),
    'device': os.getenv('OPENUNMIX_DEVICE', 'cpu'),
    'pretrained': os.getenv('OPENUNMIX_PRETRAINED', 'true').lower() == 'true',
},
```

**Código Novo:**
```python
# (remover seção completa)
```

**Validação:**
- Dicionário `settings` não deve ter chave `'openunmix'`

---

### ✅ ARQUIVO 3: `services/audio-normalization/app/processor.py`

**MODIFICAÇÃO 1: Remover Imports**

**Localização:** Linhas 19-29

**Código Atual:**
```python
# Para isolamento vocal com openunmix
try:
    import torch
    import openunmix
    OPENUNMIX_AVAILABLE = True
    TORCH_AVAILABLE = True
    logger.info("✅ PyTorch e OpenUnmix disponíveis para isolamento vocal")
except ImportError:
    OPENUNMIX_AVAILABLE = False
    TORCH_AVAILABLE = False
    logger.warning("⚠️ OpenUnmix não disponível. Isolamento vocal será desabilitado")
```

**Código Novo:**
```python
# (remover bloco completo - sem imports torch/openunmix)
```

---

**MODIFICAÇÃO 2: Remover Atributos de GPU no __init__**

**Localização:** Linhas 35-38

**Código Atual:**
```python
self._openunmix_model = None
self.device = None  # Will be set when loading model

self._detect_device()
```

**Código Novo:**
```python
# (remover linhas completas - sem atributos de GPU)
```

---

**MODIFICAÇÃO 3: Remover Método `_detect_device()`**

**Localização:** Linhas 40-64

**Ação:** Deletar método completo (25 linhas)

---

**MODIFICAÇÃO 4: Remover Método `_test_gpu()`**

**Localização:** Linhas 66-91

**Ação:** Deletar método completo (26 linhas)

---

**MODIFICAÇÃO 5: Remover Método `_load_openunmix_model()`**

**Localização:** Linhas 253-300

**Ação:** Deletar método completo (~47 linhas)

---

**MODIFICAÇÃO 6: Remover Método `_isolate_vocals()`**

**Localização:** Buscar método (não visualizado, mas existe)

**Ação:** Deletar método completo

**Buscar por:**
```python
async def _isolate_vocals(self, audio: AudioSegment)
```

---

**MODIFICAÇÃO 7: Remover Bloco de Isolamento Vocal em `_apply_processing_operations()`**

**Localização:** Linhas 523-534

**Código Atual:**
```python
# 1. Isolamento vocal (primeiro, pois pode afetar outras operações)
if job.isolate_vocals:
    try:
        logger.info("Aplicando isolamento vocal...")
        audio = await self._isolate_vocals(audio)
        if not is_chunk:
            current_progress += progress_step
            job.progress = current_progress
            if self.job_store:
                self.job_store.update_job(job)
    except Exception as e:
        logger.error(f"Erro no isolamento vocal: {e}")
        raise AudioNormalizationException(f"Falha no isolamento vocal: {str(e)}")
```

**Código Novo:**
```python
# (remover bloco completo - sem processamento de isolamento vocal)
```

**NOTA:** Ajustar comentários e numeração dos outros passos (2, 3, 4, 5 → 1, 2, 3, 4)

---

**MODIFICAÇÃO 8: Ajustar Contagem de Operações**

**Localização:** Linha 513

**Código Atual:**
```python
operations_count = sum([
    job.remove_noise, job.convert_to_mono, job.apply_highpass_filter,
    job.set_sample_rate_16k, job.isolate_vocals
])
```

**Código Novo:**
```python
operations_count = sum([
    job.remove_noise, job.convert_to_mono, job.apply_highpass_filter,
    job.set_sample_rate_16k
])
```

---

**MODIFICAÇÃO 9: Adicionar Progresso em Chunks no `_process_audio_with_streaming()`**

**Localização:** Loop de chunks (aproximadamente linha 530-560)

**Código Atual:**
```python
for i, chunk_file in enumerate(chunk_files):
    chunk_num = i + 1
    logger.info(f"📦 Processando chunk {chunk_num}/{total_chunks}...")
    
    # Carrega chunk
    chunk_audio = AudioSegment.from_file(str(chunk_file))
    
    # Processa chunk
    processed_chunk = await self._apply_processing_operations(
        chunk_audio, job, is_chunk=True
    )
    
    # Salva chunk processado
    processed_chunks.append(processed_chunk)
    
    # ❌ SEM atualização de progresso aqui

# Merge (após o loop)
job.progress = 90.0
if self.job_store: self.job_store.update_job(job)
```

**Código Novo:**
```python
for i, chunk_file in enumerate(chunk_files):
    chunk_num = i + 1
    logger.info(f"📦 Processando chunk {chunk_num}/{total_chunks}...")
    
    # ✅ ATUALIZA PROGRESSO ANTES DE PROCESSAR
    # Progresso: 10% (prep) + 70% (chunks) + 10% (merge) + 10% (save)
    chunk_progress_before = 10.0 + ((chunk_num - 1) / total_chunks) * 70.0
    job.progress = chunk_progress_before
    if self.job_store:
        self.job_store.update_job(job)
        logger.info(f"📊 Progresso: {chunk_progress_before:.1f}% (iniciando chunk {chunk_num}/{total_chunks})")
    
    # Carrega chunk
    chunk_audio = AudioSegment.from_file(str(chunk_file))
    
    # Processa chunk
    processed_chunk = await self._apply_processing_operations(
        chunk_audio, job, is_chunk=True
    )
    
    # Salva chunk processado
    processed_chunks.append(processed_chunk)
    
    # ✅ ATUALIZA PROGRESSO APÓS PROCESSAR
    chunk_progress_after = 10.0 + (chunk_num / total_chunks) * 70.0
    job.progress = chunk_progress_after
    if self.job_store:
        self.job_store.update_job(job)
        logger.info(f"✅ Chunk {chunk_num}/{total_chunks} concluído ({chunk_progress_after:.1f}%)")

# Merge (após o loop)
logger.info("🔗 Mesclando chunks processados...")
job.progress = 85.0
if self.job_store: self.job_store.update_job(job)

# ... código de merge ...

job.progress = 90.0
if self.job_store: self.job_store.update_job(job)
logger.info("✅ Merge de chunks concluído (90%)")
```

---

**Validação do processor.py:**
```bash
# Deve retornar 0 resultados:
grep -i "torch\|cuda\|gpu\|openunmix\|isolate_vocals" services/audio-normalization/app/processor.py
```

---

### ✅ ARQUIVO 4: `services/audio-normalization/app/models.py`

**MODIFICAÇÃO 1: Remover Campo de AudioProcessingRequest**

**Localização:** Linha ~20

**Código Atual:**
```python
class AudioProcessingRequest(BaseModel):
    """Request para processamento de áudio com parâmetros booleanos"""
    remove_noise: bool = False
    convert_to_mono: bool = False
    apply_highpass_filter: bool = False
    set_sample_rate_16k: bool = False
    isolate_vocals: bool = False
```

**Código Novo:**
```python
class AudioProcessingRequest(BaseModel):
    """Request para processamento de áudio com parâmetros booleanos"""
    remove_noise: bool = False
    convert_to_mono: bool = False
    apply_highpass_filter: bool = False
    set_sample_rate_16k: bool = False
```

---

**MODIFICAÇÃO 2: Remover Campo de Job**

**Localização:** Linha ~40

**Código Atual:**
```python
# Parâmetros de processamento
remove_noise: bool = False
convert_to_mono: bool = False
apply_highpass_filter: bool = False
set_sample_rate_16k: bool = False
isolate_vocals: bool = False
```

**Código Novo:**
```python
# Parâmetros de processamento
remove_noise: bool = False
convert_to_mono: bool = False
apply_highpass_filter: bool = False
set_sample_rate_16k: bool = False
```

---

**MODIFICAÇÃO 3: Remover "v" de processing_operations**

**Localização:** Linhas ~55-59

**Código Atual:**
```python
if self.apply_highpass_filter:
    operations.append("h")
if self.set_sample_rate_16k:
    operations.append("s")
if self.isolate_vocals:
    operations.append("v")
return "".join(operations) if operations else "none"
```

**Código Novo:**
```python
if self.apply_highpass_filter:
    operations.append("h")
if self.set_sample_rate_16k:
    operations.append("s")
return "".join(operations) if operations else "none"
```

---

**MODIFICAÇÃO 4: Remover Parâmetro de create_new()**

**Localização:** Linhas ~62-66, ~80-81, ~96

**Código Atual:**
```python
@classmethod
def create_new(
    cls, 
    filename: str, 
    remove_noise: bool = False,
    convert_to_mono: bool = False,
    apply_highpass_filter: bool = False,
    set_sample_rate_16k: bool = False,
    isolate_vocals: bool = False
) -> "Job":
    ...
    logger.info(f"🔍 DEBUG Job.create_new - isolate_vocals: {isolate_vocals}")
    ...
    operations = [
        "n" if remove_noise else "",
        "m" if convert_to_mono else "",
        "h" if apply_highpass_filter else "",
        "s" if set_sample_rate_16k else "",
        "v" if isolate_vocals else ""
    ]
    ...
    return cls(
        ...
        isolate_vocals=isolate_vocals,
        ...
    )
```

**Código Novo:**
```python
@classmethod
def create_new(
    cls, 
    filename: str, 
    remove_noise: bool = False,
    convert_to_mono: bool = False,
    apply_highpass_filter: bool = False,
    set_sample_rate_16k: bool = False
) -> "Job":
    ...
    # (remover log de isolate_vocals)
    ...
    operations = [
        "n" if remove_noise else "",
        "m" if convert_to_mono else "",
        "h" if apply_highpass_filter else "",
        "s" if set_sample_rate_16k else ""
    ]
    ...
    return cls(
        ...
        # (remover isolate_vocals=isolate_vocals)
        ...
    )
```

---

### ✅ ARQUIVO 5: `services/audio-normalization/app/main.py`

**MODIFICAÇÃO 1: Remover Form Parameter**

**Localização:** Linha ~135

**Código Atual:**
```python
isolate_vocals: str = Form("false")
```

**Código Novo:**
```python
# (remover linha completa)
```

---

**MODIFICAÇÃO 2: Remover Docstring**

**Localização:** Linha ~147

**Código Atual:**
```python
- **isolate_vocals**: Isola vocais usando OpenUnmix (padrão: False)
```

**Código Novo:**
```python
# (remover linha completa)
```

---

**MODIFICAÇÃO 3: Remover Conversão**

**Localização:** Linha ~172

**Código Atual:**
```python
isolate_vocals_bool = str_to_bool(isolate_vocals)
```

**Código Novo:**
```python
# (remover linha completa)
```

---

**MODIFICAÇÃO 4: Remover Log**

**Localização:** Linha ~177

**Código Atual:**
```python
logger.info(f"  isolate_vocals: '{isolate_vocals}' -> {isolate_vocals_bool}")
```

**Código Novo:**
```python
# (remover linha completa)
```

---

**MODIFICAÇÃO 5: Remover Passagem para Job**

**Localização:** Linha ~192

**Código Atual:**
```python
job = Job.create_new(
    filename=file.filename,
    remove_noise=remove_noise_bool,
    convert_to_mono=convert_to_mono_bool,
    apply_highpass_filter=apply_highpass_filter_bool,
    set_sample_rate_16k=set_sample_rate_16k_bool,
    isolate_vocals=isolate_vocals_bool
)
```

**Código Novo:**
```python
job = Job.create_new(
    filename=file.filename,
    remove_noise=remove_noise_bool,
    convert_to_mono=convert_to_mono_bool,
    apply_highpass_filter=apply_highpass_filter_bool,
    set_sample_rate_16k=set_sample_rate_16k_bool
)
```

---

### ✅ ARQUIVO 6: `services/audio-normalization/app/celery_tasks.py`

**MODIFICAÇÃO: Remover `vocals=` do Log**

**Localização:** Linha ~186

**Código Atual:**
```python
logger.info(f"📋 Processing params: noise={job.remove_noise}, highpass={job.apply_highpass_filter}, vocals={job.isolate_vocals}")
```

**Código Novo:**
```python
logger.info(f"📋 Processing params: noise={job.remove_noise}, highpass={job.apply_highpass_filter}")
```

---

## FASE 2: REMOVER ISOLAMENTO VOCAL (orchestrator)

### ✅ ARQUIVO 7: `orchestrator/modules/config.py`

**MODIFICAÇÃO 1: Remover default_isolate_vocals**

**Localização:** Linha ~67

**Código Atual:**
```python
"default_isolate_vocals": os.getenv("DEFAULT_ISOLATE_VOCALS", "true").lower() == "true",
```

**Código Novo:**
```python
# (remover linha completa)
```

---

**MODIFICAÇÃO 2: Remover isolate_vocals de default_params**

**Localização:** Linha ~104

**Código Atual:**
```python
"default_params": {
    "remove_noise": settings["default_remove_noise"],
    "convert_to_mono": settings["default_convert_mono"],
    "set_sample_rate_16k": settings["default_sample_rate_16k"],
    "apply_highpass_filter": False,
    "isolate_vocals": False
}
```

**Código Novo:**
```python
"default_params": {
    "remove_noise": settings["default_remove_noise"],
    "convert_to_mono": settings["default_convert_mono"],
    "set_sample_rate_16k": settings["default_sample_rate_16k"],
    "apply_highpass_filter": False
}
```

---

### ✅ ARQUIVO 8: `orchestrator/modules/models.py`

**MODIFICAÇÃO 1: Remover Campo de PipelineJob**

**Localização:** Linha ~88

**Código Atual:**
```python
class PipelineJob(BaseModel):
    ...
    isolate_vocals: bool = False
```

**Código Novo:**
```python
class PipelineJob(BaseModel):
    ...
    # (remover isolate_vocals)
```

---

**MODIFICAÇÃO 2: Remover Campo de PipelineRequest**

**Localização:** Linha ~185

**Código Atual:**
```python
isolate_vocals: Optional[bool] = Field(settings["default_isolate_vocals"], description="Isolar vocais (separa voz de música)")
```

**Código Novo:**
```python
# (remover linha completa)
```

---

**MODIFICAÇÃO 3: Adicionar Método `generate_id()` Estático**

**Localização:** Adicionar ANTES de `create_new()`

**Código Novo:**
```python
@staticmethod
def generate_id(
    youtube_url: str,
    language: str,
    language_out: Optional[str],
    remove_noise: bool,
    convert_to_mono: bool,
    apply_highpass_filter: bool,
    set_sample_rate_16k: bool
) -> str:
    """
    Gera ID determinístico baseado em parâmetros (idempotente)
    
    IMPORTANTE: NÃO usa timestamp para permitir deduplicação
    Mesmos parâmetros = mesmo job_id
    """
    # Normaliza URL (remove query params desnecessários)
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(youtube_url)
    video_id = parse_qs(parsed.query).get('v', [''])[0] if parsed.query else youtube_url
    
    # Cria string de operações
    operation_string = f"{video_id}"
    operation_string += f"_lang{language}_out{language_out or 'none'}"
    operation_string += f"_n{int(remove_noise)}_m{int(convert_to_mono)}"
    operation_string += f"_h{int(apply_highpass_filter)}_s{int(set_sample_rate_16k)}"
    
    # Gera hash determinístico
    job_id = hashlib.md5(operation_string.encode()).hexdigest()[:16]
    return job_id
```

---

**MODIFICAÇÃO 4: Modificar `create_new()` para Usar `generate_id()`**

**Localização:** Método `create_new()`

**Código Atual:**
```python
@classmethod
def create_new(cls, youtube_url: str, ...) -> "PipelineJob":
    job_id = hashlib.md5(f"{youtube_url}{datetime.now().isoformat()}".encode()).hexdigest()[:16]
    ...
```

**Código Novo:**
```python
@classmethod
def create_new(
    cls,
    youtube_url: str,
    language: str,
    language_out: Optional[str] = None,
    remove_noise: bool = False,
    convert_to_mono: bool = False,
    apply_highpass_filter: bool = False,
    set_sample_rate_16k: bool = False
) -> "PipelineJob":
    """Cria novo job de pipeline com ID determinístico (idempotente)"""
    
    # Gera ID determinístico (sem timestamp)
    job_id = cls.generate_id(
        youtube_url=youtube_url,
        language=language,
        language_out=language_out,
        remove_noise=remove_noise,
        convert_to_mono=convert_to_mono,
        apply_highpass_filter=apply_highpass_filter,
        set_sample_rate_16k=set_sample_rate_16k
    )
    
    now = datetime.now()
    
    return cls(
        id=job_id,
        youtube_url=youtube_url,
        language=language,
        language_out=language_out,
        remove_noise=remove_noise,
        convert_to_mono=convert_to_mono,
        apply_highpass_filter=apply_highpass_filter,
        set_sample_rate_16k=set_sample_rate_16k,
        # (remover isolate_vocals)
        status=PipelineStatus.QUEUED,
        created_at=now,
        expires_at=now + timedelta(hours=24)
    )
```

---

### ✅ ARQUIVO 9: `orchestrator/modules/orchestrator.py`

**MODIFICAÇÃO: Remover isolate_vocals do Form Data**

**Localização:** Linha ~456

**Código Atual:**
```python
"isolate_vocals": _bool_to_str(job.isolate_vocals if job.isolate_vocals is not None else defaults.get("isolate_vocals", False)),
```

**Código Novo:**
```python
# (remover linha completa)
```

---

### ✅ ARQUIVO 10: `orchestrator/main.py`

**MODIFICAÇÃO 1: Remover isolate_vocals da Criação de Job**

**Localização:** Linha ~150

**Código Atual:**
```python
job = PipelineJob.create_new(
    youtube_url=request.youtube_url,
    language=request.language or settings["default_language"],
    language_out=request.language_out,
    remove_noise=request.remove_noise if request.remove_noise is not None else settings["default_remove_noise"],
    convert_to_mono=request.convert_to_mono if request.convert_to_mono is not None else settings["default_convert_mono"],
    apply_highpass_filter=request.apply_highpass_filter if request.apply_highpass_filter is not None else False,
    set_sample_rate_16k=request.set_sample_rate_16k if request.set_sample_rate_16k is not None else settings["default_sample_rate_16k"],
    isolate_vocals=request.isolate_vocals if request.isolate_vocals is not None else False
)
```

**Código Novo:**
```python
job = PipelineJob.create_new(
    youtube_url=request.youtube_url,
    language=request.language or settings["default_language"],
    language_out=request.language_out,
    remove_noise=request.remove_noise if request.remove_noise is not None else settings["default_remove_noise"],
    convert_to_mono=request.convert_to_mono if request.convert_to_mono is not None else settings["default_convert_mono"],
    apply_highpass_filter=request.apply_highpass_filter if request.apply_highpass_filter is not None else False,
    set_sample_rate_16k=request.set_sample_rate_16k if request.set_sample_rate_16k is not None else settings["default_sample_rate_16k"]
)
```

---

**MODIFICAÇÃO 2: Adicionar Verificação de Job Existente (Idempotência)**

**Localização:** Logo APÓS criação da variável `job` (antes de `redis_store.save_job(job)`)

**Código Atual:**
```python
# Cria job
job = PipelineJob.create_new(...)

# Salva no Redis
redis_store.save_job(job)
```

**Código Novo:**
```python
# Gera job_id determinístico e verifica se já existe
job_id = PipelineJob.generate_id(
    youtube_url=request.youtube_url,
    language=request.language or settings["default_language"],
    language_out=request.language_out,
    remove_noise=request.remove_noise if request.remove_noise is not None else settings["default_remove_noise"],
    convert_to_mono=request.convert_to_mono if request.convert_to_mono is not None else settings["default_convert_mono"],
    apply_highpass_filter=request.apply_highpass_filter if request.apply_highpass_filter is not None else False,
    set_sample_rate_16k=request.set_sample_rate_16k if request.set_sample_rate_16k is not None else settings["default_sample_rate_16k"]
)

# Verifica se job já existe (idempotência)
existing_job = redis_store.get_job(job_id)
if existing_job:
    # Job já existe
    if existing_job.status in [PipelineStatus.PROCESSING, PipelineStatus.COMPLETED]:
        logger.info(f"♻️ Job {job_id} já existe com status {existing_job.status.value} - retornando job existente")
        return PipelineResponse(
            job_id=job_id,
            status=existing_job.status.value,
            message=f"Job já existe e está {existing_job.status.value}",
            created_at=existing_job.created_at,
            stages=existing_job.stages
        )
    elif existing_job.status == PipelineStatus.FAILED:
        # Job falhou anteriormente, permite reprocessar
        logger.info(f"🔄 Job {job_id} falhou anteriormente - permitindo reprocessamento")
    # Se QUEUED, continua para recriar

# Cria novo job com ID pré-determinado
job = PipelineJob.create_new(...)

# Salva no Redis
redis_store.save_job(job)
```

---

## 📊 CHECKLIST DE VALIDAÇÃO PÓS-IMPLEMENTAÇÃO

### ✅ Validação 1: Remoção Completa de isolate_vocals

```bash
# Executar na raiz do projeto:
grep -r "isolate_vocals" services/audio-normalization/ orchestrator/
# Resultado esperado: 0 matches
```

### ✅ Validação 2: Remoção Completa de GPU/Torch

```bash
# Executar:
grep -ri "torch\|cuda\|gpu\|openunmix" services/audio-normalization/app/
# Resultado esperado: 0 matches (exceto em comentários históricos)
```

### ✅ Validação 3: Requirements.txt Limpo

```bash
# Verificar:
cat services/audio-normalization/requirements.txt | grep -i "torch\|openunmix"
# Resultado esperado: nenhuma linha
```

### ✅ Validação 4: Progresso em Chunks

**Teste Manual:**
1. Upload arquivo > 50MB para `/jobs`
2. Monitorar `GET /jobs/{job_id}` em loop
3. Verificar: progresso deve atualizar continuamente (10% → 25% → 40% → 55% → 70% → 85% → 100%)
4. NÃO deve ficar parado em 10% por minutos

### ✅ Validação 5: Idempotência

**Teste Manual:**
1. Enviar POST `/process` com mesma URL/params
2. Aguardar 1 segundo
3. Enviar POST `/process` com MESMA URL/params novamente
4. Verificar: AMBOS devem retornar o MESMO `job_id`
5. Verificar Redis: apenas 1 job deve existir

**Teste Automatizado:**
```bash
curl -X POST "http://localhost:8080/process" -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://youtube.com/watch?v=TEST123", "language": "pt"}' > resp1.json

curl -X POST "http://localhost:8080/process" -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://youtube.com/watch?v=TEST123", "language": "pt"}' > resp2.json

# Comparar job_id:
diff <(jq -r '.job_id' resp1.json) <(jq -r '.job_id' resp2.json)
# Resultado esperado: sem diferenças (mesmo job_id)
```

### ✅ Validação 6: Build e Startup

```bash
# Build:
time docker-compose build audio-normalization
# Tempo esperado: ~50% mais rápido que antes

# Startup:
docker-compose up audio-normalization
# Verificar logs: deve subir em poucos segundos, sem carregar modelos torch
```

---

## 🚀 ORDEM DE EXECUÇÃO

1. **Commit Estado Atual** (backup)
2. **Executar FASE 1** (arquivos 1-6)
3. **Testar audio-normalization isoladamente**
4. **Executar FASE 2** (arquivos 7-10)
5. **Testar sistema completo**
6. **Executar Validações 1-6**
7. **Commit Final**

---

## 📝 NOTAS IMPORTANTES

### Sobre Imports:
- Após remover torch/openunmix, NÃO adicionar substituições
- pydub/scipy/numpy/librosa são suficientes para noise reduction e filters

### Sobre Progresso:
- Cálculo: 10% (prep) + 70% (chunks) + 10% (merge) + 10% (save)
- Update ANTES e DEPOIS de cada chunk
- Logs detalhados para debugging

### Sobre Idempotência:
- Hash NÃO inclui timestamp
- URL é normalizada (extrai video_id)
- Jobs FAILED podem ser reprocessados
- Jobs PROCESSING/COMPLETED são retornados como-estão

---

**FIM DO PLANO DE CORREÇÕES v4**
