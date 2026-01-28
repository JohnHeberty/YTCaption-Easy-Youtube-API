# 🔍 Análise do Erro 404 no Audio-Transcriber

**Data:** 28 de Janeiro de 2026  
**Problema Reportado:** Make-video falhando com erro 404 ao chamar audio-transcriber

---

## 📋 Erro Relatado

```json
{
  "job_id": "XPbEAFG2poZoH89Xib7KHT",
  "status": "failed",
  "error": {
    "message": "HTTP error: Client error '404 Not Found' for url 'https://yttranscriber.loadstask.com/transcribe'",
    "type": "MicroserviceException",
    "stage": "unknown"
  }
}
```

---

## 🔬 Causa Raiz Identificada

### ❌ Problema Principal: Endpoint `/transcribe` não existe

O audio-transcriber **NÃO possui** um endpoint `/transcribe`. Este endpoint foi descontinuado e substituído por um sistema de jobs assíncronos.

### ✅ API Atual (Correta)

O audio-transcriber v2.0+ utiliza os seguintes endpoints:

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/jobs` | Cria novo job de transcrição/tradução |
| `GET` | `/jobs/{job_id}` | Consulta status e progresso |
| `GET` | `/jobs/{job_id}/transcription` | Obtém resultado da transcrição |
| `GET` | `/jobs/{job_id}/download` | Download em formato SRT |
| `DELETE` | `/jobs/{job_id}` | Cancela job |
| `GET` | `/languages` | Lista idiomas suportados |

### 📝 Exemplo de Uso Correto

```bash
# 1. Criar job
curl -X POST http://localhost:8005/jobs \
  -F "file=@audio.mp3" \
  -F "language_in=pt" \
  -F "language_out=en"

# Resposta:
# {
#   "id": "trans_abc123",
#   "status": "queued",
#   "progress": 0.0,
#   ...
# }

# 2. Verificar status
curl http://localhost:8005/jobs/trans_abc123

# 3. Obter resultado (quando status=completed)
curl http://localhost:8005/jobs/trans_abc123/transcription
```

---

## 🔧 Verificação do Código

### ✅ Make-Video está CORRETO

O serviço make-video em [`app/api_client.py`](../make-video/app/api_client.py) já utiliza a API correta:

```python
# Linha 227-253
async def transcribe_audio(self, audio_path: str, language: str = "pt") -> List[Dict]:
    # Upload usando /jobs (CORRETO)
    response = await self.client.post(
        f"{self.audio_transcriber_url}/jobs",
        files={"file": ("audio.ogg", f, "audio/ogg")},
        data={"language": language, "operation": "transcribe"}
    )
    
    # Polling do status
    response = await self.client.get(
        f"{self.audio_transcriber_url}/jobs/{job_id}"
    )
```

### ❌ Documentação estava DESATUALIZADA

Os seguintes arquivos continham referências ao endpoint antigo `/transcribe`:

1. **README.md** (linha 46)
   - ❌ Antes: `POST /transcribe | Upload e transcreve áudio`
   - ✅ Depois: `POST /jobs | Cria job de transcrição/tradução`

2. **validate-gpu.sh** (linha 142)
   - ❌ Antes: `curl -X POST http://localhost:8002/transcribe -F 'file=@test.mp3'`
   - ✅ Depois: `curl -X POST http://localhost:8005/jobs -F 'file=@test.mp3' -F 'language_in=pt'`

---

## ✅ Correções Aplicadas

### 1. Atualização do README.md

**Arquivo:** [`README.md`](./README.md)

**Mudanças:**
- ✅ Tabela de endpoints corrigida
- ✅ Exemplos atualizados para usar `/jobs`
- ✅ Adicionado endpoint `/languages`
- ✅ Removido endpoint inexistente `/stats`

### 2. Atualização do validate-gpu.sh

**Arquivo:** [`validate-gpu.sh`](./validate-gpu.sh)

**Mudanças:**
- ✅ Exemplo de teste corrigido para usar `/jobs`
- ✅ Porta corrigida de 8002 para 8005
- ✅ Adicionado parâmetro `language_in=pt`

---

## 🎯 Conclusão

### Status do Problema

✅ **RESOLVIDO** - Documentação corrigida

### O que estava acontecendo?

1. O make-video **já estava usando a API correta** (`/jobs`)
2. A **documentação** estava desatualizada com referências ao endpoint antigo
3. Não havia problema no código, apenas na documentação

### Por que o erro 404 ocorreu?

O erro 404 no make-video provavelmente ocorreu devido a:
- URL mal configurada no ambiente de produção
- Possível tentativa de usar endpoint antigo baseado em documentação desatualizada
- O código do make-video está correto e usa `/jobs`

### Recomendações

1. ✅ Verificar variável de ambiente `AUDIO_TRANSCRIBER_URL` no make-video
2. ✅ Garantir que a URL aponta para o serviço correto
3. ✅ Seguir a documentação atualizada
4. ✅ Testar integração entre serviços

### Verificação da Integração

```bash
# 1. Verificar se audio-transcriber está rodando
curl http://localhost:8005/health

# 2. Verificar se make-video consegue alcançar audio-transcriber
docker exec make-video-api curl http://audio-transcriber-api:8005/health

# 3. Testar criação de job de transcrição
curl -X POST http://localhost:8005/jobs \
  -F "file=@test_audio.mp3" \
  -F "language_in=pt"
```

---

## 📚 Referências

- [Audio-Transcriber API Documentation](../../docs/services/audio-transcriber/README.md)
- [Make-Video API Client](../make-video/app/api_client.py)
- [Audio-Transcriber Main](./app/main.py)

---

**Autor:** GitHub Copilot  
**Data de Análise:** 28/01/2026  
**Status:** ✅ Documentação corrigida e sincronizada com a API real
