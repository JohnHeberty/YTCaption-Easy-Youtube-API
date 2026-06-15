# MASTER-PLAN — `se7-audio-generation`

## 1. Arquitetura Geral

### 1.1 Conceito
Serviço **standalone** de TTS em português brasileiro com **gerenciamento de perfis de voz**. O usuário pode:

1. **Criar perfis de voz** enviando um áudio de referência (5-15s) → recebe um `voice_id` permanente
2. **Gerar áudio** referenciando um `voice_id` (clonagem) ou sem (voz sintética padrão do modelo)

### 1.2 Stack Tecnológica

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Web framework | FastAPI | Padrão do projeto |
| Async tasks | Celery + Redis | Modelo ML pesado roda em background |
| Modelo TTS | `ResembleAI/Chatterbox-Multilingual-pt-br` | Fine-tuned PT-BR, suporta clonagem |
| Áudio | torchaudio + pydub | Geração + pós-processamento (concatenação) |
| Job/Profile store | Redis (via `common.redis_utils`) | Padrão do projeto |
| Health check | `common.health_utils.ServiceHealthChecker` | Padrão do projeto |
| DI | `common.di.Dep` + `@lru_cache` | Padrão do projeto |
| FastAPI factory | `common.fastapi_utils.create_service_app` | Padrão do projeto |

### 1.3 Porta: `8007`

---

## 2. API Completa

### 2.1 Endpoints de Voz (Voice Profiles)

| Método | Rota | Body | Resposta | Descrição |
|---|---|---|---|---|
| `POST` | `/voices` | Multipart: `name`, `description` (opcional), `file` (.wav) | `VoiceProfile` | Cria perfil de voz clonada |
| `GET` | `/voices` | — | `List[VoiceProfile]` | Lista todos os perfis |
| `GET` | `/voices/{voice_id}` | — | `VoiceProfile` | Detalhes de um perfil |
| `DELETE` | `/voices/{voice_id}` | — | `{message, voice_id}` | Remove perfil e áudio |
| `GET` | `/voices/{voice_id}/sample` | — | `FileResponse (.wav)` | Download do sample original |

### 2.2 Endpoints de Geração (Jobs)

| Método | Rota | Body | Resposta | Descrição |
|---|---|---|---|---|
| `POST` | `/jobs` | Multipart/JSON: `text`, `voice_id` (opcional), `exaggeration`, `cfg_weight`, `temperature` | `JobResponse` | Cria job de geração |
| `GET` | `/jobs` | Query: `limit` | `List[AudioGenerationJob]` | Lista jobs |
| `GET` | `/jobs/{job_id}` | — | `AudioGenerationJob` | Status do job |
| `GET` | `/jobs/{job_id}/download` | — | `FileResponse (.wav)` | Download do áudio |
| `DELETE` | `/jobs/{job_id}` | — | `DeleteJobResponse` | Remove job + áudio |

### 2.3 Endpoints de Saúde

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/health` | Health check (Redis, modelo, GPU, disco) |
| `GET` | `/metrics` | Prometheus metrics |

---

## 3. Fluxo de Criação de Perfil de Voz

```
POST /voices (multipart: name="Maria", file=@sample.wav)
  ├── Valida: formato WAV, 5s ≤ duração ≤ 15s, mono
  ├── Gera voice_id = "vc_{sha256(file)[:16]}"
  ├── Salva áudio em data/voices/{voice_id}.wav
  ├── Cria VoiceProfile no Redis (sem TTL)
  ├── Adiciona índice: voice_profiles:all → set(voice_ids)
  └── Retorna VoiceProfile
```

---

## 4. Fluxo de Geração de Áudio

```
POST /jobs
  Body: { text: "...", voice_id: "vc_abc123", params }

  1. Valida entrada
  2. Cria AudioGenerationJob (QUEUED, prefix "ag_")
  3. Envia Celery task: generate_audio_task(job_dict)

  --- CELERY WORKER ---

  4. Carrega ChatterboxModel (lazy load, GPU/CPU fallback)
  5. Divide texto em chunks de ~250 chars
  6. Para cada chunk: model.generate(text, language_id="pt",
       audio_prompt_path=voice_sample, exaggeration, temperature, cfg_weight)
  7. Concatena chunks com pydub (silêncio entre parágrafos)
  8. Salva: data/outputs/{job_id}.wav
  9. Atualiza job: COMPLETED

  10. GET /jobs/{job_id}/download → .wav
```

---

## 5. Estrutura de Diretórios

```
services/se7-audio-generation/
├── .env
├── .env.example
├── MASTER-PLAN.md
├── run.py
├── requirements.txt
├── constraints.txt
├── Dockerfile
├── docker-compose.yml
├── Makefile
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── jobs_routes.py
│   │   ├── voices_routes.py
│   │   ├── health_routes.py
│   │   └── schemas.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── constants.py
│   │
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── interfaces.py
│   │   └── exceptions.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── generator.py
│   │   ├── model_manager.py
│   │   ├── voice_manager.py
│   │   └── audio_utils.py
│   │
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── dependencies.py
│   │   ├── celery_config.py
│   │   ├── celery_tasks.py
│   │   └── redis_store.py
│   │
│   └── middleware/
│       └── __init__.py
│
├── data/
│   ├── models/
│   ├── voices/
│   ├── outputs/
│   └── temp/
│
└── tests/
    └── test_generator.py
```

---

## 6. Modelos de Domínio

```python
class VoiceProfile(BaseModel):
    id: str
    name: str
    description: str = ""
    created_at: datetime
    updated_at: datetime
    audio_path: str
    duration_seconds: float
    sample_rate: int
    status: str = "active"  # active | failed

class AudioGenerationJob(StandardJob):
    input_text: str
    text_hash: str
    voice_id: Optional[str] = None
    has_voice_cloning: bool = False
    exaggeration: float = 0.75
    cfg_weight: float = 0.35
    temperature: float = 0.8
    output_file: Optional[str] = None
    output_duration_seconds: Optional[float] = None
```

---

## 7. Ordens de Implementação

| Fase | O que | Arquivos |
|---|---|---|
| 1 | Setup base | `requirements.txt`, `constraints.txt`, `.env.example` |
| 2 | Config + constantes | `core/config.py`, `core/constants.py` |
| 3 | Domínio | `domain/models.py`, `domain/interfaces.py`, `domain/exceptions.py` |
| 4 | Voice Manager + Redis | `services/voice_manager.py`, `infrastructure/redis_store.py` |
| 5 | Model Manager | `services/model_manager.py` |
| 6 | Gerador + Audio Utils | `services/generator.py`, `services/audio_utils.py` |
| 7 | DI dependencies | `infrastructure/dependencies.py` |
| 8 | Celery | `infrastructure/celery_config.py`, `infrastructure/celery_tasks.py` |
| 9 | API routes + main | `api/*`, `main.py`, `run.py` |
| 10 | Docker | `Dockerfile`, `docker-compose.yml`, `Makefile` |
| 11 | Testes | `tests/` |
