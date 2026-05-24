# API Reference - Audio Transcriber

Versao: 2.0.0  
Base URL: http://localhost:8004

## Fluxo principal
1. Criar job: POST /jobs
2. Consultar status: GET /jobs/{job_id}
3. Baixar resultado: GET /jobs/{job_id}/download

## Jobs

### POST /jobs
Cria um job de transcricao de audio.

Request (multipart/form-data):
- file: arquivo de audio/video (obrigatorio)
- language_in: codigo ISO 639-1 ou auto (default: auto)
- language_out: codigo ISO 639-1 (opcional; traducao real suportada para en)
- engine: faster-whisper | openai-whisper | whisperx (default: faster-whisper)

Response 200:
- Retorna o objeto Job completo (id, status, progresso, timestamps, idiomas, etc.).

Exemplo curl:
```bash
curl -X POST "http://localhost:8004/jobs" \
  -F "file=@audio.mp3" \
  -F "language_in=pt" \
  -F "engine=faster-whisper"
```

### GET /jobs
Lista jobs recentes.

Query:
- limit (opcional, default 20)

### GET /jobs/{job_id}
Retorna status detalhado do job.

Status:
- 200: job encontrado
- 404: job nao encontrado
- 410: job expirado

### GET /jobs/{job_id}/text
Retorna somente o texto consolidado da transcricao.

Response:
```json
{
  "text": "..."
}
```

### GET /jobs/{job_id}/transcription
Retorna transcricao completa tipada (texto, segmentos, idioma detectado, duracao, tempo de processamento).

### GET /jobs/{job_id}/download
Baixa arquivo final (SRT) do job concluido.

Status:
- 200: arquivo entregue
- 404: job/arquivo nao encontrado
- 410: job expirado
- 425: transcricao ainda nao finalizada

### DELETE /jobs/{job_id}
Remove job e arquivos relacionados.

Response:
```json
{
  "message": "Job removido com sucesso",
  "job_id": "at_xxx",
  "files_deleted": 2
}
```

## Recuperacao de jobs orfaos

### GET /jobs/orphaned
Lista jobs em estado processando/fila acima do tempo limite.

Query:
- max_age_minutes (default 30)

### POST /jobs/orphaned/cleanup
Executa cleanup dos jobs orfaos.

Query:
- max_age_minutes (default 30)
- mark_as_failed (default true)

## Health e metadata

### GET /health
Health check rapido do servico (redis, disco, ffmpeg, modelo).

### GET /health/detailed
Health check detalhado e agregado (com status HTTP 503 se unhealthy).

### GET /metrics
Metricas em formato Prometheus.

### GET /languages
Lista linguagens suportadas para transcricao/traducao e exemplos de uso.

### GET /engines
Lista engines disponiveis com capacidades.

## Admin

### GET /admin/stats
Metricas de jobs e cache local.

### GET /admin/queue
Informacoes da fila Celery.

### POST /admin/cleanup
Limpeza manual.

Query:
- deep (default false)
- purge_celery_queue (default false)

### POST /admin/cleanup-orphans
Executa limpeza de orfaos via OrphanJobCleaner.

## Modelo

### POST /model/load
Carrega modelo explicitamente.

### POST /model/unload
Descarrega modelo explicitamente.

### GET /model/status
Retorna status do modelo carregado e memoria associada.

## Erros comuns
- 400: linguagem invalida, arquivo vazio ou request invalido.
- 404: job ou recurso nao encontrado.
- 410: job expirado.
- 425: job ainda nao finalizado.
- 500: erro interno.

Consulte também:
- TIPOS.md
- ERROS.md
- EXEMPLOS.md
