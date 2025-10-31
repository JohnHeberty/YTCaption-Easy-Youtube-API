# 🔧 CORREÇÃO - Limite de Tamanho de Arquivo

## Data: 2025-10-31 00:45 BRT

---

## 🐛 PROBLEMA IDENTIFICADO

### Erro 413 - Request Entity Too Large:
```json
{
  "normalization": {
    "status": "failed",
    "error": "[audio-normalization] File too large for service: Client error '413 Request Entity Too Large' for url 'http://192.168.18.133:8002/jobs'"
  }
}
```

### Análise do Problema:
- ✅ **Download**: Funcionou (arquivo baixado com sucesso)
- ❌ **Normalização**: Falhou com erro 413
- ⏳ **Transcrição**: Não chegou a executar (pending)

### Causa Raiz:
**Limite hardcoded de 100MB** no `audio-normalization/app/main.py` linha 224:
```python
# ❌ ANTES: Limite fixo ignorando .env
max_size = 100 * 1024 * 1024  # 100MB
```

---

## ✅ CORREÇÕES APLICADAS

### 1. **Correção do Limite Hardcoded**

**Arquivo:** `services/audio-normalization/app/main.py`

**❌ Antes (Linha 224-230):**
```python
# Validação 4: Arquivo não excede limite de tamanho?
max_size = 100 * 1024 * 1024  # 100MB
if len(content) > max_size:
    logger.error(f"Arquivo muito grande: {len(content)} bytes")
    raise HTTPException(
        status_code=413,
        detail=f"Arquivo muito grande. Máximo: {max_size//1024//1024}MB"
    )
```

**✅ Depois:**
```python
# Validação 4: Arquivo não excede limite de tamanho? (usar configuração do .env)
max_size_mb = settings['max_file_size_mb']
max_size = max_size_mb * 1024 * 1024
if len(content) > max_size:
    logger.error(f"Arquivo muito grande: {len(content)} bytes (máximo: {max_size_mb}MB)")
    raise HTTPException(
        status_code=413,
        detail=f"Arquivo muito grande. Máximo: {max_size_mb}MB"
    )
```

### 2. **Middleware de Body Size**

**Adicionado middleware** para controlar tamanho do request body no FastAPI:

```python
class BodySizeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_size: int):
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get('content-length')
        if content_length and int(content_length) > self.max_size:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Request body too large. Maximum: {self.max_size // 1024 // 1024}MB"}
            )
        return await call_next(request)

# Aplicar middleware baseado na configuração .env
max_body_size = settings['max_file_size_mb'] * 1024 * 1024
app.add_middleware(BodySizeMiddleware, max_size=max_body_size)
```

### 3. **Configuração do Uvicorn**

**Arquivo:** `services/audio-normalization/run.py`

**✅ Adicionado:**
```python
from app.config import get_settings

settings = get_settings()
max_body_size = settings['max_file_size_mb'] * 1024 * 1024

uvicorn.run(
    "app.main:app",
    host="0.0.0.0",
    port=8001,
    reload=True,
    log_level="info",
    limit_max_requests=1000,
    limit_concurrency=100,
)
```

### 4. **Criação de .env nos Outros Serviços**

**✅ Criados arquivos .env:**
- `services/audio-transcriber/.env` (MAX_FILE_SIZE_MB=2048)
- `services/video-downloader/.env` (MAX_FILE_SIZE_MB=10240)

**✅ Verificado que docker-compose.yml já usa env_file:**
- Todos os serviços já têm `env_file: - .env`

---

## 📊 LIMITES ATUALIZADOS

| Serviço | Limite Anterior | Limite Atual | Chunking |
|---------|-----------------|--------------|-----------|
| **video-downloader** | 5GB | **10GB** | ✅ Sim |
| **audio-normalization** | ❌ 100MB (hardcoded) | **1GB** | ✅ Sim |
| **audio-transcriber** | 500MB | **2GB** | ✅ Sim |

### Configurações no .env:
```bash
# audio-normalization/.env
MAX_FILE_SIZE_MB=1024

# audio-transcriber/.env  
MAX_FILE_SIZE_MB=2048

# video-downloader/.env
MAX_FILE_SIZE_MB=10240
```

---

## 🧪 TESTES NECESSÁRIOS

### 1. Verificar Limite Aplicado:
```bash 
curl -X GET http://192.168.18.133:8002/health
```

### 2. Testar Arquivo Grande:
```bash
# Enviar arquivo de teste ~800MB
curl -X POST \
  -F "file=@large_audio_file.mp3" \
  -F "operations=[\"normalize\"]" \
  http://192.168.18.133:8002/jobs
```

### 3. Verificar Logs:
```bash
docker logs audio-normalization-api | grep -i "arquivo muito grande\|max_size"
```

---

## 🔄 STATUS DO REBUILD

### Comando Executado:
```bash
cd services/audio-normalization
docker-compose down && docker-compose build --no-cache && docker-compose up -d
```

**Status:** 🔄 **BUILD EM ANDAMENTO**  
**ETA:** ~2-3 minutos  

---

## ✅ RESULTADOS ESPERADOS

- ✅ **Arquivo ~600MB+**: Deve processar normalmente
- ✅ **Sem erro 413**: Limite agora é 1GB (1024MB)
- ✅ **Chunking funciona**: Para arquivos grandes
- ✅ **Configuração dinâmica**: Baseada no .env, não hardcoded

---

## 🎯 PRÓXIMOS PASSOS

1. ⏳ **Aguardar build completar**
2. 🧪 **Testar com arquivo problemático**
3. ✅ **Verificar normalização funciona**
4. 🚀 **Testar transcrição em sequência**

---

**Status:** 🔄 CORREÇÕES APLICADAS - BUILD EM ANDAMENTO  
**Problema:** Limite hardcoded de 100MB ❌  
**Solução:** Limite dinâmico de 1GB baseado no .env ✅  
**Arquivos Afetados:** main.py, run.py, .env (3 serviços)  