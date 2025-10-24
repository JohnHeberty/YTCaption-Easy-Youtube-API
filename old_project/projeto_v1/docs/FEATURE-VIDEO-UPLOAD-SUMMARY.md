# 📊 Video Upload Feature - Executive Summary

## 🎯 Objetivo
Adicionar endpoint `/api/v1/transcribe/upload` para permitir upload direto de arquivos de vídeo/áudio.

---

## ✨ Benefícios

| Benefício | Descrição |
|-----------|-----------|
| 🌍 **Flexibilidade** | Vídeos de qualquer plataforma (não só YouTube) |
| 🔒 **Privacidade** | Vídeos privados/locais podem ser transcritos |
| 🏢 **Corporativo** | Vídeos internos de empresas |
| 🚀 **Bypass** | Reduz dependência do YouTube (evita rate limits) |

---

## 🏗️ Arquitetura - Clean Architecture

```
📁 PRESENTATION LAYER
  └── POST /api/v1/transcribe/upload
      ├── Rate Limit: 2 uploads/min (vs 5 YouTube/min)
      ├── Max Size: 2.5GB
      └── Formatos: MP4, AVI, MOV, MKV, WebM, MP3, WAV, AAC, etc.

📁 APPLICATION LAYER  
  └── TranscribeUploadedVideoUseCase
      ├── 1. Salvar upload (streaming)
      ├── 2. Validar (formato, tamanho, duração)
      ├── 3. Extrair áudio (FFmpeg)
      ├── 4. Transcrever (Whisper)
      └── 5. Cleanup (arquivos temporários)

📁 DOMAIN LAYER
  ├── UploadedVideoFile (Value Object)
  ├── IVideoUploadValidator (Interface)
  └── VideoUploadError (Exception)

📁 INFRASTRUCTURE LAYER
  ├── VideoUploadValidator (FFprobe validation)
  ├── VideoUploadService (file streaming)
  └── UploadMetricsCollector (Prometheus)
```

---

## 📝 Fases de Implementação

### FASE 1: Domain Layer (2h)
- [x] UploadedVideoFile value object
- [x] IVideoUploadValidator interface
- [x] VideoUploadError exceptions

### FASE 2: Infrastructure Layer (4h)
- [x] VideoUploadValidator (FFprobe)
- [x] VideoUploadService (streaming save)
- [x] Prometheus metrics

### FASE 3: Application Layer (2h)
- [x] TranscribeUploadedVideoUseCase
- [x] UploadVideoRequestDTO
- [x] FFmpeg integration

### FASE 4: Presentation Layer (2h)
- [x] Upload route endpoint
- [x] Error handling
- [x] Rate limiting

### FASE 5: Testes e Config (2-3h)
- [x] Unit tests
- [x] Integration tests
- [x] Settings configuration

### FASE 6: Documentação (1-2h)
- [x] API docs (Swagger)
- [x] README update
- [x] CHANGELOG update

---

## 🚀 Exemplo de Uso

### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/transcribe/upload" \
  -F "file=@video.mp4" \
  -F "language=auto"
```

### Python
```python
with open("video.mp4", "rb") as f:
    files = {"file": f}
    data = {"language": "auto"}
    response = requests.post(
        "http://localhost:8000/api/v1/transcribe/upload",
        files=files, data=data
    )
```

### JavaScript
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('language', 'auto');

fetch('/api/v1/transcribe/upload', {
    method: 'POST',
    body: formData
});
```

---

## 📊 Formatos Suportados

### Vídeo
MP4, AVI, MOV, MKV, WebM, FLV, WMV, M4V, MPG, MPEG, 3GP

### Áudio
MP3, WAV, AAC, M4A, FLAC, OGG, WMA, Opus

**Total**: 23 formatos

---

## ⚡ Performance

| Métrica | Valor |
|---------|-------|
| Upload 100MB | <30s |
| Upload 1GB | <5min |
| Rate Limit | 2/min |
| Max File Size | 2.5GB |
| Max Duration | 3h (10,800s) |

---

## 🔒 Segurança

✅ **Validação dupla**: MIME type + FFprobe  
✅ **Sanitização**: Nomes de arquivo sanitizados  
✅ **Rate limiting**: 2 uploads/min por IP  
✅ **Tamanho máximo**: 2.5GB enforced  
✅ **Cleanup automático**: Arquivos temporários removidos  
✅ **Timeout**: Upload timeout 5min  

---

## 📈 Métricas Prometheus

```
video_upload_requests_total{status, format}
video_upload_duration_seconds
video_upload_file_size_bytes
video_uploads_in_progress
video_upload_validation_errors_total{error_type}
```

---

## ⏱️ Timeline

| Fase | Tempo |
|------|-------|
| 1. Domain | 2h |
| 2. Infrastructure | 4h |
| 3. Application | 2h |
| 4. Presentation | 2h |
| 5. Testes | 2-3h |
| 6. Docs | 1-2h |
| **TOTAL** | **13-15h** |

**Sprint**: 2-3 dias

---

## ✅ Critérios de Sucesso

### Funcionais
- ✅ Upload MP4, AVI, MOV, MKV funciona
- ✅ Upload MP3, WAV, AAC funciona
- ✅ Transcrição igual formato YouTube
- ✅ Validação rejeita formatos inválidos
- ✅ Validação rejeita >2.5GB
- ✅ Validação rejeita >3h duração

### Performance
- ✅ 100MB em <30s
- ✅ 1GB em <5min
- ✅ Rate limit funciona
- ✅ Métricas registradas
- ✅ Cleanup automático

---

## 🎯 Próximos Passos

1. ✅ Planejamento completo criado
2. ⏳ Revisão com time técnico
3. ⏳ Aprovação de escopo
4. ⏳ Criar branch `feature/video-upload-endpoint`
5. ⏳ Implementação (13-15h)
6. ⏳ Code review
7. ⏳ Deploy staging
8. ⏳ Deploy production

---

## 📚 Documentação Completa

Ver: `docs/FEATURE-VIDEO-UPLOAD.md`

- Arquitetura detalhada
- Código de exemplo completo
- Todos os arquivos a criar
- Testes unitários e integração
- Troubleshooting
- Melhorias futuras (v2.0)

---

**Status**: 📋 PLANEJAMENTO COMPLETO  
**Prioridade**: P1 - HIGH  
**Estimativa**: 13-15 horas  
**Complexidade**: Média-Alta  
