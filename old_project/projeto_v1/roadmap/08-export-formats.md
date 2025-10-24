# Phase 8: Multiple Export Formats

**Status**: ⏳ PENDENTE  
**Prioridade**: 🟢 LOW  
**Esforço Estimado**: 4 horas  
**Impacto**: Médio  
**ROI**: ⭐⭐⭐

---

## 📋 Objetivo

Suportar múltiplos formatos de exportação de transcrições além do JSON padrão, aumentando compatibilidade com ferramentas de edição de vídeo e legendas.

---

## 🎯 Formatos Suportados

### 1. SRT (SubRip)
```srt
1
00:00:00,000 --> 00:00:05,000
Primeira legenda do vídeo

2
00:00:05,000 --> 00:00:10,000
Segunda legenda do vídeo
```

### 2. VTT (WebVTT)
```vtt
WEBVTT

00:00:00.000 --> 00:00:05.000
Primeira legenda do vídeo

00:00:05.000 --> 00:00:10.000
Segunda legenda do vídeo
```

### 3. TXT (Plain Text)
```txt
Primeira legenda do vídeo Segunda legenda do vídeo...
```

### 4. PDF
Transcrição formatada com timestamps e metadados.

### 5. DOCX
Documento Word editável com formatação.

---

## 🛠️ Implementação

```python
# src/application/use_cases/export_transcription.py
class ExportTranscriptionUseCase:
    def execute(self, transcription_id: str, format: str) -> bytes:
        transcription = self.repo.get_by_id(transcription_id)
        
        if format == 'srt':
            return self._export_srt(transcription)
        elif format == 'vtt':
            return self._export_vtt(transcription)
        elif format == 'txt':
            return self._export_txt(transcription)
        elif format == 'pdf':
            return self._export_pdf(transcription)
        elif format == 'docx':
            return self._export_docx(transcription)
        else:
            raise ValueError(f"Unsupported format: {format}")

# Endpoint
@router.get("/api/v1/transcription/{id}/export")
async def export_transcription(
    id: str,
    format: str = Query(..., enum=['json', 'srt', 'vtt', 'txt', 'pdf', 'docx'])
):
    content = export_use_case.execute(id, format)
    
    media_types = {
        'json': 'application/json',
        'srt': 'text/plain',
        'vtt': 'text/vtt',
        'txt': 'text/plain',
        'pdf': 'application/pdf',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    }
    
    return Response(
        content=content,
        media_type=media_types[format],
        headers={
            'Content-Disposition': f'attachment; filename="transcription.{format}"'
        }
    )
```

---

**Próxima Phase**: [Phase 9: Search API for Transcriptions](./09-search-api.md)
