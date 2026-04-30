# Exemplos de Uso

## Criar transcricao
```bash
curl -X POST "http://localhost:8004/jobs" \
  -F "file=@audio.mp3" \
  -F "language_in=pt" \
  -F "engine=faster-whisper"
```

## Consultar status
```bash
curl "http://localhost:8004/jobs/at_123"
```

## Obter texto
```bash
curl "http://localhost:8004/jobs/at_123/text"
```

## Obter transcricao completa
```bash
curl "http://localhost:8004/jobs/at_123/transcription"
```

## Download de SRT
```bash
curl -L "http://localhost:8004/jobs/at_123/download" -o out.srt
```

## Diagnosticar jobs orfaos
```bash
curl "http://localhost:8004/jobs/orphaned?max_age_minutes=30"
```

## Limpar jobs orfaos
```bash
curl -X POST "http://localhost:8004/jobs/orphaned/cleanup?max_age_minutes=30&mark_as_failed=true"
```

## Verificar engines
```bash
curl "http://localhost:8004/engines"
```

## Health
```bash
curl "http://localhost:8004/health"
curl "http://localhost:8004/health/detailed"
```
