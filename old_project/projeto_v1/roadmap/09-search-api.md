# Phase 9: Search API for Transcriptions

**Status**: ⏳ PENDENTE  
**Prioridade**: 🟢 LOW  
**Esforço Estimado**: 5 horas  
**Impacto**: Baixo  
**ROI**: ⭐⭐

---

## 📋 Objetivo

Permitir busca textual dentro de transcrições, facilitando localização de trechos específicos em vídeos longos.

---

## 🎯 Funcionalidades

### Full-Text Search
```http
GET /api/v1/transcriptions/search?q=machine+learning&user_id=123
```

### Filtros Avançados
- Por data de criação
- Por duração do vídeo
- Por idioma
- Por modelo Whisper usado

### Response
```json
{
  "total_results": 15,
  "results": [
    {
      "transcription_id": "trans_123",
      "video_title": "Introduction to ML",
      "matches": [
        {
          "segment_index": 5,
          "text": "...introduction to machine learning concepts...",
          "timestamp": "00:02:15",
          "relevance_score": 0.95
        }
      ],
      "created_at": "2025-10-20T10:30:00Z"
    }
  ]
}
```

---

## 🛠️ Implementação

### Opção 1: PostgreSQL Full-Text Search
```sql
ALTER TABLE transcriptions ADD COLUMN tsv tsvector;
CREATE INDEX idx_transcriptions_tsv ON transcriptions USING gin(tsv);
```

### Opção 2: Elasticsearch
```python
# Indexar transcrições no Elasticsearch
es.index(
    index="transcriptions",
    id=transcription_id,
    body={
        "text": full_text,
        "segments": segments,
        "metadata": metadata
    }
)

# Buscar
results = es.search(
    index="transcriptions",
    body={
        "query": {
            "match": {"text": search_query}
        },
        "highlight": {
            "fields": {"text": {}}
        }
    }
)
```

---

**Próxima Phase**: [Phase 10: API Key Rate Limiting](./10-api-key-limiting.md)
