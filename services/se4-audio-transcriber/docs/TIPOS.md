# Tipos e Contratos

## Base model de Job
O objeto principal retornado em POST /jobs e GET /jobs/{job_id}.

Campos relevantes:
- id: identificador unico (prefixo at_)
- status: pending | queued | processing | completed | failed | cancelled
- progress: progresso de 0 a 100
- created_at, started_at, completed_at, updated_at
- input_file, output_file, filename
- language_in, language_out, language_detected
- engine: faster-whisper | openai-whisper | whisperx
- error_message
- transcription_text
- transcription_segments

## Segmentos de transcricao
Cada segmento segue:
- text: texto do trecho
- start: inicio em segundos
- end: fim em segundos
- duration: duracao em segundos
- words (opcional): lista com word/start/end/probability

## Response de transcricao completa
GET /jobs/{job_id}/transcription retorna:
- transcription_id
- filename
- language
- language_detected
- language_out
- was_translated
- full_text
- segments
- total_segments
- duration
- processing_time

## Responses auxiliares tipadas
- GET /jobs/{job_id}/text -> { text }
- DELETE /jobs/{job_id} -> { message, job_id, files_deleted }
- GET /jobs/orphaned -> lista de jobs orfaos
- POST /jobs/orphaned/cleanup -> relatorio de acoes
- GET /health -> status/checks
- GET /languages -> transcription/translation/models/usage_examples
- GET /engines -> engines/default_engine/recommendation
- GET /admin/stats -> total_jobs/by_status/cache
- GET /admin/queue -> status/queue
- POST /model/load|unload -> success/message
- GET /model/status -> loaded/model_name/device/memory

## Compatibilidade
- Campo legado language continua funcional como alias de language_in.
- Campos extras podem existir para manter compatibilidade progressiva.
