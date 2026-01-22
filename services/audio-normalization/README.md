# Audio Normalization Service

Microserviço para normalização de áudio com Celery + Redis.

## 🎯 Funcionalidades

- ✅ **Remoção de ruído** - Remove ruído de fundo usando noisereduce
- ✅ **Normalização de volume** - Ajusta volume para nível consistente
- ✅ **Conversão para mono** - Reduz canais de áudio para 1 (economia de espaço)
- ✅ **Processamento assíncrono** - Celery + Redis para jobs em background
- ✅ **Cache inteligente por hash** - Evita reprocessamento de arquivos idênticos
- ✅ **Cache de 24h** - Arquivos processados disponíveis por 24 horas
- 🆕 **Suporte a vídeos** - Aceita MP4, AVI, MOV, etc. (extrai áudio automaticamente)

## 🚀 Iniciar Serviços

### Docker Compose (RECOMENDADO)
```powershell
cd services/audio-normalization-service
docker-compose up -d
```

### Ver logs
```powershell
docker-compose logs -f
```

## 📊 Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/normalize` | Upload e processa áudio |
| GET | `/jobs/{job_id}` | Consulta status do job |
| GET | `/jobs/{job_id}/download` | Download do áudio processado |
| DELETE | `/jobs/{job_id}` | Cancela/deleta job |
| GET | `/jobs` | Lista jobs recentes |
| GET | `/health` | Health check |
| GET | `/admin/stats` | Estatísticas do sistema |

## 🧪 Testar

### Upload de áudio para normalização
```powershell
# PowerShell
$file = Get-Item "C:\path\to\audio.mp3"
$form = @{
    file = $file
    remove_noise = "true"
    normalize_volume = "true"
    convert_to_mono = "true"
}

$response = Invoke-RestMethod -Method Post -Uri "http://localhost:8002/normalize" -Form $form
$jobId = $response.id

# Ver progresso
Invoke-RestMethod -Uri "http://localhost:8002/jobs/$jobId"

# Download do resultado
Invoke-WebRequest -Uri "http://localhost:8002/jobs/$jobId/download" -OutFile "audio_normalized.mp3"
```

### Testar Sistema de Cache
```powershell
# Executa script de teste automatizado
.\test_cache.ps1

# Resultado esperado:
# - Upload 1: Cria job novo
# - Upload 2 (mesmo arquivo): CACHE HIT (retorna job existente)
# - Upload 3 (operações diferentes): Cria job novo
```

## 🔑 Sistema de Cache

O serviço implementa cache inteligente baseado no **hash do arquivo + operações**:

### Como Funciona
1. **Upload** → Calcula SHA256 do arquivo
2. **Job ID** = `hash_operações` (ex: `a1b2c3_nvm`)
3. **Verifica Cache** → Se já existe, retorna job existente
4. **Economia** → Não reprocessa arquivos idênticos

### Códigos de Operação
- `n` = Noise reduction
- `v` = Volume normalize
- `m` = Mono conversion

**Exemplos de Job IDs:**
- `abc123_nvm` - Todas operações
- `abc123_n` - Apenas ruído
- `abc123_vm` - Volume + Mono

📖 **Documentação completa**: Ver [CACHE_SYSTEM.md](./CACHE_SYSTEM.md)

## 🔧 Configuração

### Variáveis de Ambiente
```env
REDIS_URL=redis://localhost:6379/0
```

## 📦 Dependências

- **FastAPI** - API REST
- **Celery + Redis** - Fila de jobs
- **pydub** - Manipulação de áudio
- **noisereduce** - Remoção de ruído
- **librosa** - Processamento de áudio
- **soundfile** - I/O de arquivos de áudio

## 🏗️ Arquitetura

```
┌─────────────┐
│   FastAPI   │ ─── Submete jobs ───┐
│   (8002)    │                      │
└─────────────┘                      ▼
                              ┌─────────────┐
                              │    Redis    │
                              │   (6380)    │
                              └─────────────┘
                                     ▲
┌─────────────┐                     │
│   Celery    │ ─── Processa audio ─┘
│   Worker    │
└─────────────┘
```

## 🎵 Processo de Normalização

1. **Upload** - Cliente envia arquivo de áudio
2. **Job Creation** - Cria job no Redis
3. **Queue** - Celery worker pega o job
4. **Processing**:
   - Remove ruído (noisereduce)
   - Normaliza volume (pydub)
   - Converte para mono
5. **Complete** - Arquivo disponível para download
6. **Expire** - Arquivo removido após 24h

## 📈 Performance

| Operação | Tempo Médio | Redução |
|----------|-------------|---------|
| Remove Ruído | 5-10s | N/A |
| Normaliza Volume | 1-2s | N/A |
| Converte Mono | 1s | ~50% tamanho |
| **Total (5min áudio)** | **7-13s** | **~50%** |

## 🔐 Portas

- **8002** - API REST
- **6380** - Redis (mapeado do 6379 interno)
