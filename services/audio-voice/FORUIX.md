# FORUIX – Mapa de Endpoints de Áudio

**Versão:** 2.0.0  
**Data:** 29 de novembro de 2025  
**Engine Principal:** F5-TTS PT-BR (firstpixel/F5-TTS-pt-br)  
**Propósito:** Documentação completa da API de áudio para designers UI/UX

---

## 1. Visão Geral do Serviço de Áudio

Este micro-serviço oferece **clonagem de voz** e **síntese de fala** (TTS) em português brasileiro com altíssima fidelidade de timbre usando o modelo **F5-TTS PT-BR**.

### Características Principais:
- **Clonagem de voz**: A partir de 3-30 segundos de áudio de referência
- **Fala natural**: Respeita vírgulas, pontos e pausas naturais (chunking inteligente)
- **Multi-idioma**: Suporte a 100+ idiomas via zero-shot learning
- **Engines disponíveis**: 
  - F5-TTS (recomendado para PT-BR, alta qualidade)
  - XTTS (alternativa rápida, multilíngue)
- **RVC (Voice Conversion)**: Conversão de voz opcional para maior controle de timbre
- **GPU-accelerated**: Requer NVIDIA GPU (GTX 1050 Ti mínimo, RTX 3090 recomendado)

### Fluxo Típico:
1. **Clonar voz** → `POST /voices/clone` → Recebe `voice_id`
2. **Gerar áudio** → `POST /jobs` com `voice_id` → Recebe `job_id`
3. **Consultar status** → `GET /jobs/{job_id}` → Aguardar `status=completed`
4. **Baixar áudio** → `GET /jobs/{job_id}/download` → Recebe arquivo de áudio

---

## 2. Endpoints Principais

### 2.1. Health Check

#### `GET /`

**Objetivo:** Verificar se o serviço está online e saudável.

**Resposta:**
```json
{
  "service": "audio-voice",
  "status": "running",
  "version": "2.0.0"
}
```

**Status Codes:**
- `200 OK`: Serviço operacional

---

### 2.2. Geração de Áudio (TTS)

#### `POST /jobs`

**Objetivo:** Criar um job de síntese de fala (dubbing/TTS) a partir de texto.

**Headers:**
```
Content-Type: application/json
```

**Body (JSON):**
```json
{
  "text": "Olá, tudo bem? Eu estou testando a velocidade da fala, para ver se as pausas funcionam bem.",
  "language": "pt-BR",
  "voice_id": "voice_12345abc",
  "engine": "f5tts",
  "quality_profile": "balanced",
  "speed": 0.80,
  "enable_rvc": false
}
```

**Parâmetros:**

| Parâmetro | Tipo | Obrigatório | Descrição | Valores Aceitos |
|-----------|------|-------------|-----------|-----------------|
| `text` | string | ✅ | Texto a sintetizar (até 10.000 caracteres) | Qualquer texto UTF-8 |
| `language` | string | ✅ | Código do idioma | `pt-BR`, `pt-PT`, `en-US`, `es`, etc. |
| `voice_id` | string | ❌ | ID da voz clonada (se omitido, usa voz padrão) | UUID ou nome da voz |
| `engine` | string | ❌ | Engine TTS (padrão: `f5tts`) | `f5tts`, `xtts` |
| `quality_profile` | string | ❌ | Perfil de qualidade (padrão: `balanced`) | `stable`, `balanced`, `expressive` |
| `speed` | float | ❌ | Multiplicador de velocidade (padrão: 0.80) | `0.5` a `2.0` |
| `enable_rvc` | boolean | ❌ | Ativar conversão de voz RVC (padrão: false) | `true`, `false` |
| `rvc_model` | string | ❌ | Modelo RVC a usar (se `enable_rvc=true`) | Nome do modelo RVC |

**Resposta (202 Accepted):**
```json
{
  "job_id": "job_abc123def456",
  "status": "processing",
  "created_at": "2025-11-29T18:30:00Z",
  "engine": "f5tts",
  "voice_id": "voice_12345abc"
}
```

**Status Codes:**
- `202 Accepted`: Job criado com sucesso, processamento iniciado
- `400 Bad Request`: Parâmetros inválidos (ex: texto muito longo)
- `404 Not Found`: `voice_id` não existe
- `500 Internal Server Error`: Erro no servidor

**Tempo Típico de Resposta:**
- Criação do job: < 100ms
- Processamento completo: 5s - 60s (depende do tamanho do texto e qualidade)

---

### 2.3. Consultar Status de Job

#### `GET /jobs/{job_id}`

**Objetivo:** Verificar o status de processamento de um job.

**Path Parameters:**
- `job_id`: ID do job retornado na criação

**Resposta (200 OK):**

**Job em processamento:**
```json
{
  "job_id": "job_abc123def456",
  "status": "processing",
  "progress": 45.5,
  "created_at": "2025-11-29T18:30:00Z",
  "engine": "f5tts"
}
```

**Job concluído:**
```json
{
  "job_id": "job_abc123def456",
  "status": "completed",
  "progress": 100.0,
  "created_at": "2025-11-29T18:30:00Z",
  "completed_at": "2025-11-29T18:30:25Z",
  "engine": "f5tts",
  "duration": 12.5,
  "file_size": 301234
}
```

**Job com erro:**
```json
{
  "job_id": "job_abc123def456",
  "status": "failed",
  "created_at": "2025-11-29T18:30:00Z",
  "error": "CUDA out of memory"
}
```

**Possíveis Status:**
- `pending`: Aguardando processamento
- `processing`: Em processamento
- `completed`: Concluído com sucesso
- `failed`: Falhou (verificar campo `error`)

**Status Codes:**
- `200 OK`: Job encontrado
- `404 Not Found`: Job não existe

**Polling Recomendado:**
- Intervalo: 1-2 segundos
- Timeout: 5 minutos (jobs grandes podem demorar)

---

### 2.4. Download de Áudio

#### `GET /jobs/{job_id}/download`

**Objetivo:** Baixar o arquivo de áudio gerado por um job concluído.

**Path Parameters:**
- `job_id`: ID do job

**Query Parameters:**
- `format` (opcional): Formato do áudio (`wav`, `mp3`, `flac`, `ogg`)
  - Padrão: `wav`

**Exemplo:**
```
GET /jobs/job_abc123def456/download?format=mp3
```

**Resposta (200 OK):**
- Content-Type: `audio/wav`, `audio/mpeg`, `audio/flac`, `audio/ogg`
- Body: Binário do arquivo de áudio

**Headers de Resposta:**
```
Content-Type: audio/mpeg
Content-Disposition: attachment; filename="job_abc123def456.mp3"
Content-Length: 301234
```

**Status Codes:**
- `200 OK`: Download iniciado
- `404 Not Found`: Job não existe ou ainda não concluído
- `400 Bad Request`: Formato não suportado

**Formatos Suportados:**

| Formato | MIME Type | Codec | Taxa de Bits (MP3) |
|---------|-----------|-------|--------------------|
| WAV | `audio/wav` | PCM 16-bit | N/A |
| MP3 | `audio/mpeg` | MP3 | 128 kbps |
| FLAC | `audio/flac` | FLAC lossless | N/A |
| OGG | `audio/ogg` | Opus | 96 kbps |

---

### 2.5. Listar Jobs

#### `GET /jobs`

**Objetivo:** Listar todos os jobs criados.

**Query Parameters:**
- `limit` (opcional): Número máximo de jobs a retornar (padrão: 50, máximo: 100)
- `offset` (opcional): Offset para paginação (padrão: 0)
- `status` (opcional): Filtrar por status (`pending`, `processing`, `completed`, `failed`)

**Exemplo:**
```
GET /jobs?limit=10&status=completed
```

**Resposta (200 OK):**
```json
{
  "jobs": [
    {
      "job_id": "job_abc123",
      "status": "completed",
      "created_at": "2025-11-29T18:30:00Z",
      "engine": "f5tts"
    },
    {
      "job_id": "job_def456",
      "status": "processing",
      "created_at": "2025-11-29T18:31:00Z",
      "engine": "xtts"
    }
  ],
  "total": 42,
  "limit": 10,
  "offset": 0
}
```

---

### 2.6. Deletar Job

#### `DELETE /jobs/{job_id}`

**Objetivo:** Deletar um job e liberar espaço em disco.

**Path Parameters:**
- `job_id`: ID do job a deletar

**Resposta (200 OK):**
```json
{
  "message": "Job deleted successfully",
  "job_id": "job_abc123"
}
```

**Status Codes:**
- `200 OK`: Job deletado
- `404 Not Found`: Job não existe

---

### 2.7. Clonagem de Voz

#### `POST /voices/clone`

**Objetivo:** Criar um perfil de voz clonada a partir de um áudio de referência.

**Headers:**
```
Content-Type: multipart/form-data
```

**Body (Multipart Form):**

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `audio` | File | ✅ | Arquivo de áudio de referência (3-30s, WAV/MP3/OGG) |
| `name` | string | ✅ | Nome da voz (ex: "João Silva") |
| `language` | string | ✅ | Idioma da voz (`pt-BR`, etc.) |
| `description` | string | ❌ | Descrição opcional da voz |
| `ref_text` | string | ❌ | Transcrição do áudio (RECOMENDADO para melhor qualidade) |

**Exemplo (cURL):**
```bash
curl -X POST http://localhost:8005/voices/clone \
  -F "audio=@referencia.wav" \
  -F "name=João Silva" \
  -F "language=pt-BR" \
  -F "ref_text=Olá, boa tarde, esse daqui é um teste para clonagem de voz."
```

**Resposta (202 Accepted):**
```json
{
  "job_id": "clone_xyz789",
  "status": "processing",
  "voice_name": "João Silva"
}
```

**Após Conclusão (consultar via `GET /jobs/clone_xyz789`):**
```json
{
  "job_id": "clone_xyz789",
  "status": "completed",
  "voice_id": "voice_joao_silva_12345",
  "voice_name": "João Silva",
  "language": "pt-BR",
  "duration": 12.5
}
```

**Requisitos do Áudio de Referência:**
- **Duração**: 3-30 segundos (ideal: 10-15s)
- **Qualidade**: Sem ruído de fundo, voz clara
- **Conteúdo**: Fala natural, variada (não monocórdica)
- **Formato**: WAV (preferível), MP3, OGG, FLAC
- **Sample Rate**: Qualquer (será resampleado para 24kHz)

**Status Codes:**
- `202 Accepted`: Clonagem iniciada
- `400 Bad Request`: Arquivo inválido ou parâmetros incorretos
- `413 Payload Too Large`: Arquivo muito grande (> 100MB)

**Tempo de Processamento:**
- Típico: 5-15 segundos
- Com auto-transcrição (sem `ref_text`): +10-30 segundos

---

### 2.8. Listar Vozes

#### `GET /voices`

**Objetivo:** Listar todas as vozes clonadas disponíveis.

**Query Parameters:**
- `limit` (opcional): Número máximo de vozes (padrão: 100)

**Resposta (200 OK):**
```json
{
  "voices": [
    {
      "voice_id": "voice_joao_silva_12345",
      "name": "João Silva",
      "language": "pt-BR",
      "created_at": "2025-11-29T18:00:00Z",
      "source_audio_duration": 12.5,
      "description": "Voz masculina, tom grave, sotaque paulista"
    },
    {
      "voice_id": "voice_maria_santos_67890",
      "name": "Maria Santos",
      "language": "pt-BR",
      "created_at": "2025-11-29T17:30:00Z",
      "source_audio_duration": 8.3
    }
  ],
  "total": 2
}
```

---

### 2.9. Obter Detalhes de Voz

#### `GET /voices/{voice_id}`

**Objetivo:** Obter detalhes completos de uma voz clonada.

**Path Parameters:**
- `voice_id`: ID da voz

**Resposta (200 OK):**
```json
{
  "voice_id": "voice_joao_silva_12345",
  "name": "João Silva",
  "language": "pt-BR",
  "created_at": "2025-11-29T18:00:00Z",
  "source_audio_path": "/app/voice_profiles/voice_joao_silva_12345.wav",
  "source_audio_duration": 12.5,
  "ref_text": "Olá, boa tarde, esse daqui é um teste para clonagem de voz.",
  "description": "Voz masculina, tom grave, sotaque paulista",
  "metadata": {
    "sample_rate": 24000,
    "channels": 1,
    "engine": "f5tts"
  }
}
```

**Status Codes:**
- `200 OK`: Voz encontrada
- `404 Not Found`: Voz não existe

---

### 2.10. Deletar Voz

#### `DELETE /voices/{voice_id}`

**Objetivo:** Deletar uma voz clonada.

**Path Parameters:**
- `voice_id`: ID da voz

**Resposta (200 OK):**
```json
{
  "message": "Voice deleted successfully",
  "voice_id": "voice_joao_silva_12345"
}
```

**Status Codes:**
- `200 OK`: Voz deletada
- `404 Not Found`: Voz não existe

---

### 2.11. Quality Profiles (Perfis de Qualidade)

#### `GET /quality-profiles-legacy`

**Objetivo:** Listar perfis de qualidade disponíveis para síntese.

**Resposta (200 OK):**
```json
{
  "profiles": [
    {
      "name": "stable",
      "description": "Rápido e estável, qualidade razoável",
      "nfe_step": 16,
      "processing_time": "~1 minuto"
    },
    {
      "name": "balanced",
      "description": "Equilíbrio entre qualidade e velocidade (RECOMENDADO)",
      "nfe_step": 40,
      "processing_time": "~2 minutos"
    },
    {
      "name": "expressive",
      "description": "Máxima qualidade e expressividade",
      "nfe_step": 64,
      "processing_time": "~3 minutos"
    }
  ]
}
```

---

### 2.12. Formatos de Áudio Suportados

#### `GET /jobs/{job_id}/formats`

**Objetivo:** Listar formatos de áudio disponíveis para um job.

**Resposta (200 OK):**
```json
{
  "formats": [
    {
      "format": "wav",
      "mime_type": "audio/wav",
      "description": "PCM WAV sem compressão (melhor qualidade)"
    },
    {
      "format": "mp3",
      "mime_type": "audio/mpeg",
      "description": "MP3 128kbps (comprimido, compatível)"
    },
    {
      "format": "flac",
      "mime_type": "audio/flac",
      "description": "FLAC lossless (alta qualidade comprimida)"
    },
    {
      "format": "ogg",
      "mime_type": "audio/ogg",
      "description": "OGG Opus 96kbps (web-friendly)"
    }
  ]
}
```

---

### 2.13. Idiomas Suportados

#### `GET /languages`

**Objetivo:** Listar idiomas suportados pelo F5-TTS.

**Resposta (200 OK):**
```json
{
  "languages": [
    {"code": "pt-BR", "name": "Português Brasileiro"},
    {"code": "pt-PT", "name": "Português Europeu"},
    {"code": "en-US", "name": "English (US)"},
    {"code": "en-GB", "name": "English (UK)"},
    {"code": "es", "name": "Español"},
    {"code": "fr", "name": "Français"},
    {"code": "de", "name": "Deutsch"},
    {"code": "it", "name": "Italiano"},
    {"code": "zh", "name": "中文"},
    {"code": "ja", "name": "日本語"},
    {"code": "ko", "name": "한국어"}
  ]
}
```

**Nota:** F5-TTS suporta 100+ idiomas via zero-shot, mas os listados acima têm melhor qualidade.

---

## 3. Fluxos Recomendados para UI/UX

### 3.1. Fluxo Completo: Clonar Voz e Testar

**Caso de uso:** Usuário quer clonar sua voz e testar imediatamente.

**Passos:**
1. **Upload de áudio de referência**
   - UI: Input de arquivo + textarea para transcrição (opcional, mas recomendado)
   - Backend: `POST /voices/clone`
   - Recebe: `job_id` da clonagem

2. **Polling do status da clonagem**
   - UI: Loading spinner
   - Backend: `GET /jobs/{job_id}` a cada 2 segundos
   - Aguardar: `status=completed`
   - Recebe: `voice_id`

3. **Gerar áudio de teste**
   - UI: Input de texto de teste
   - Backend: `POST /jobs` com `voice_id`
   - Recebe: `job_id` da síntese

4. **Polling do status da síntese**
   - UI: Loading com progresso
   - Backend: `GET /jobs/{job_id}` a cada 1 segundo
   - Aguardar: `status=completed`

5. **Reproduzir áudio**
   - UI: Player HTML5 `<audio>`
   - Backend: `GET /jobs/{job_id}/download?format=mp3`
   - Exibir: Player com controles

**Tempo total esperado:** 20-60 segundos (depende do tamanho do texto)

---

### 3.2. Fluxo Rápido: Gerar com Voz Existente

**Caso de uso:** Usuário já tem voz clonada e quer gerar novo áudio.

**Passos:**
1. **Listar vozes disponíveis**
   - Backend: `GET /voices`
   - UI: Dropdown de seleção

2. **Input de texto e parâmetros**
   - UI: Textarea + sliders (speed, quality)
   - Valores recomendados:
     - Speed: 0.70 - 1.00 (default: 0.80)
     - Quality: balanced

3. **Criar job**
   - Backend: `POST /jobs`
   - Recebe: `job_id`

4. **Polling + Download** (mesmo que fluxo anterior)

**Tempo esperado:** 5-30 segundos

---

### 3.3. Fluxo de Teste de Parâmetros

**Caso de uso:** Designer quer ajustar parâmetros para encontrar melhor naturalidade.

**UI Sugerida:**
- Sliders com preview em tempo real:
  - **Speed**: 0.5 - 2.0 (steps de 0.05)
    - Label: "Velocidade da fala"
    - Default: 0.80
  - **CFG Strength**: 1.0 - 3.0 (steps de 0.1)
    - Label: "Fidelidade ao texto" 
    - Default: 2.2
  - **Sway Coefficient**: -1.0 - 1.0 (steps de 0.1)
    - Label: "Variações naturais"
    - Default: 0.3
    - Info: "-1.0 = desabilitado, 0.3 = sutil, 1.0 = pronunciado"

- Botão "Gerar Preview" que cria job com texto curto fixo (ex: "Olá, como vai?")
- Comparação A/B entre diferentes configurações

---

## 4. Considerações de Performance e Limites

### 4.1. Limites de Tamanho

| Recurso | Limite | Comportamento ao Exceder |
|---------|--------|--------------------------|
| Tamanho de texto | 10.000 caracteres | HTTP 400 Bad Request |
| Arquivo de upload | 100 MB | HTTP 413 Payload Too Large |
| Duração de referência | 3-30 segundos | HTTP 400 (fora do range) |
| Jobs simultâneos | 3 | Fila (FIFO) |
| Jobs por hora | Ilimitado | - |

### 4.2. Tempo de Processamento

**F5-TTS (Engine Recomendado):**

| Texto | NFE Steps | GPU | Tempo Típico |
|-------|-----------|-----|--------------|
| 50 chars | 40 (balanced) | RTX 3090 | 2-5s |
| 200 chars | 40 (balanced) | RTX 3090 | 8-15s |
| 1000 chars | 40 (balanced) | RTX 3090 | 30-60s |
| 200 chars | 64 (expressive) | RTX 3090 | 15-25s |
| 200 chars | 40 (balanced) | GTX 1050 Ti | 25-40s |

**Fatores que aumentam tempo:**
- Texto longo (usa chunking, processa em partes)
- NFE steps alto (quality=expressive)
- GPU fraca ou modo CPU
- RVC habilitado (+20-40% tempo)

### 4.3. Uso de VRAM (GPU)

| Modo | VRAM Típica | VRAM Pico |
|------|-------------|-----------|
| F5-TTS + Vocos | 2-3 GB | 4 GB |
| F5-TTS + XTTS (ambos carregados) | 5-6 GB | 8 GB |
| F5-TTS + RVC | 4-5 GB | 6 GB |
| LOW_VRAM=true | 0.5-1 GB | 3 GB |

**Modo LOW_VRAM:**
- Carrega/descarrega modelo dinamicamente
- Economia de 70-75% de VRAM
- +2-5s de latência por job
- Ideal para GPUs com < 6GB VRAM

### 4.4. Taxas de Erro Comuns

| Erro | Causa | Solução UI |
|------|-------|------------|
| "Text too long" | Texto > 10k chars | Mostrar contador de caracteres |
| "Reference audio too short" | Áudio < 3s | Validar duração antes de upload |
| "CUDA out of memory" | VRAM insuficiente | Sugerir quality=stable ou modo CPU |
| "Voice not found" | voice_id inválido | Atualizar lista de vozes |
| "Job timeout" | Texto muito longo | Dividir texto ou usar quality=stable |

### 4.5. Latência de Rede

| Operação | Payload | Latência Típica (LAN) |
|----------|---------|----------------------|
| POST /jobs | ~1 KB | < 50ms |
| GET /jobs/{id} | ~500 B | < 20ms |
| POST /voices/clone | 1-10 MB | 100-500ms |
| GET /jobs/{id}/download | 100KB - 5MB | 200ms - 2s |

**Recomendações para UI:**
- Implementar timeout de 60s para `/jobs` (criação)
- Polling com backoff exponencial para status
- Streaming/chunked download para arquivos grandes
- Cache local de vozes listadas (`GET /voices`)

---

## 5. Parâmetros Avançados F5-TTS (Para Power Users)

### 5.1. Parâmetros de Síntese

Estes parâmetros podem ser passados no body de `POST /jobs` dentro de um objeto `advanced_params`:

```json
{
  "text": "...",
  "voice_id": "...",
  "advanced_params": {
    "nfe_step": 40,
    "cfg_strength": 2.2,
    "sway_sampling_coef": 0.3,
    "speed": 0.80,
    "denoise_strength": 0.85,
    "chunk_by_punctuation": true,
    "max_chunk_chars": 200,
    "cross_fade_duration": 0.05
  }
}
```

**Descrição dos Parâmetros:**

| Parâmetro | Range | Default | Efeito |
|-----------|-------|---------|--------|
| `nfe_step` | 16-128 | 40 | Número de iterações do flow matching. Maior = melhor qualidade, mais lento. |
| `cfg_strength` | 1.0-3.0 | 2.2 | Fidelidade ao texto/prosódia. Maior = mais preciso, menos variação. |
| `sway_sampling_coef` | -1.0 a 1.0 | 0.3 | Variações naturais. -1.0 = off, 0.3 = sutil, 1.0 = pronunciado. |
| `speed` | 0.5-2.0 | 0.80 | Velocidade de fala. < 1.0 = mais lento/natural PT-BR. |
| `denoise_strength` | 0.0-1.0 | 0.85 | Redução de ruído pós-processamento. |
| `chunk_by_punctuation` | boolean | true | Se true, divide texto por vírgulas/pontos para pausas naturais. |
| `max_chunk_chars` | 50-500 | 200 | Tamanho máximo de cada chunk de texto. |
| `cross_fade_duration` | 0.0-0.5 | 0.05 | Duração do cross-fade entre chunks (segundos). |

### 5.2. Combinações Recomendadas

**Narração natural (audiobook):**
```json
{
  "nfe_step": 40,
  "cfg_strength": 2.2,
  "sway_sampling_coef": 0.3,
  "speed": 0.75,
  "chunk_by_punctuation": true
}
```

**Fala rápida (notícias):**
```json
{
  "nfe_step": 32,
  "cfg_strength": 2.0,
  "sway_sampling_coef": 0.1,
  "speed": 1.1,
  "chunk_by_punctuation": false
}
```

**Máxima expressividade (personagem):**
```json
{
  "nfe_step": 64,
  "cfg_strength": 2.5,
  "sway_sampling_coef": 0.5,
  "speed": 0.85,
  "chunk_by_punctuation": true
}
```

---

## 6. Tratamento de Erros

### 6.1. Códigos de Status HTTP

| Status | Significado | Ação Recomendada |
|--------|-------------|------------------|
| 200 OK | Sucesso | Processar resposta |
| 202 Accepted | Job criado, processando | Fazer polling de status |
| 400 Bad Request | Parâmetros inválidos | Exibir mensagem de erro, corrigir input |
| 404 Not Found | Recurso não existe | Atualizar cache, sugerir criar novo |
| 413 Payload Too Large | Arquivo muito grande | Comprimir ou reduzir tamanho |
| 429 Too Many Requests | Rate limit excedido | Aguardar e retentar (backoff) |
| 500 Internal Server Error | Erro no servidor | Reportar erro, sugerir retry |
| 503 Service Unavailable | Serviço temporariamente indisponível | Exibir mensagem, retry automático |

### 6.2. Mensagens de Erro (Body)

Formato padrão de erro:
```json
{
  "detail": "Text exceeds maximum length of 10000 characters",
  "error_code": "TEXT_TOO_LONG",
  "suggestion": "Split text into smaller chunks or use text summarization"
}
```

**Códigos de Erro Comuns:**

| error_code | Descrição | Solução UI |
|------------|-----------|------------|
| `TEXT_TOO_LONG` | Texto > 10k chars | Contador de caracteres, split automático |
| `VOICE_NOT_FOUND` | voice_id inválido | Refresh lista de vozes |
| `INVALID_AUDIO_FORMAT` | Formato não suportado | Aceitar apenas WAV/MP3/OGG |
| `AUDIO_TOO_SHORT` | Duração < 3s | Validar duração do upload |
| `AUDIO_TOO_LONG` | Duração > 30s | Cortar áudio automaticamente |
| `CUDA_OOM` | Memória GPU insuficiente | Sugerir quality=stable |
| `JOB_TIMEOUT` | Job excedeu timeout | Sugerir texto menor |
| `INVALID_LANGUAGE` | Idioma não suportado | Mostrar lista de idiomas válidos |

---

## 7. Webhooks (Futuro)

**Status:** Planejado para v2.1.0

Permitirá notificações assíncronas de conclusão de jobs via HTTP callback.

**Endpoint proposto:**
```
POST /webhooks
```

**Body:**
```json
{
  "url": "https://seu-servidor.com/callback",
  "events": ["job.completed", "job.failed"]
}
```

**Callback recebido:**
```json
{
  "event": "job.completed",
  "job_id": "job_abc123",
  "timestamp": "2025-11-29T18:30:25Z",
  "data": {
    "duration": 12.5,
    "file_size": 301234
  }
}
```

---

## 8. Segurança e Autenticação

**Status Atual:** Sem autenticação (uso interno/LAN)

**Planejado para produção:**
- API Keys via header `X-API-Key`
- Rate limiting por IP
- HTTPS obrigatório

---

## 9. Versionamento da API

**Versão Atual:** v2.0.0

**Política de Versionamento:**
- Sem breaking changes em minor/patch versions
- Major versions (v3.0.0) podem ter mudanças incompatíveis
- Versão incluída em todas as respostas no header `X-API-Version`

---

## 10. Exemplos de Código

### 10.1. JavaScript (Fetch API)

**Criar Job e Aguardar Conclusão:**
```javascript
async function generateAudio(text, voiceId) {
  // 1. Criar job
  const createResponse = await fetch('http://localhost:8005/jobs', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      text: text,
      language: 'pt-BR',
      voice_id: voiceId,
      engine: 'f5tts',
      speed: 0.80
    })
  });
  const {job_id} = await createResponse.json();
  
  // 2. Polling de status
  while (true) {
    const statusResponse = await fetch(`http://localhost:8005/jobs/${job_id}`);
    const status = await statusResponse.json();
    
    if (status.status === 'completed') {
      // 3. Download
      const audioUrl = `http://localhost:8005/jobs/${job_id}/download?format=mp3`;
      return audioUrl;
    } else if (status.status === 'failed') {
      throw new Error(status.error);
    }
    
    // Aguardar 1 segundo
    await new Promise(r => setTimeout(r, 1000));
  }
}

// Uso:
const audioUrl = await generateAudio("Olá, tudo bem?", "voice_joao_123");
document.getElementById('player').src = audioUrl;
```

### 10.2. Python (requests)

**Clonar Voz:**
```python
import requests
import time

def clone_voice(audio_path, name, language, ref_text=None):
    # 1. Upload e criar job de clonagem
    with open(audio_path, 'rb') as f:
        files = {'audio': f}
        data = {
            'name': name,
            'language': language
        }
        if ref_text:
            data['ref_text'] = ref_text
        
        response = requests.post(
            'http://localhost:8005/voices/clone',
            files=files,
            data=data
        )
    
    job_id = response.json()['job_id']
    
    # 2. Aguardar conclusão
    while True:
        status_response = requests.get(f'http://localhost:8005/jobs/{job_id}')
        status = status_response.json()
        
        if status['status'] == 'completed':
            return status['voice_id']
        elif status['status'] == 'failed':
            raise Exception(status['error'])
        
        time.sleep(2)

# Uso:
voice_id = clone_voice(
    'referencia.wav',
    'João Silva',
    'pt-BR',
    ref_text='Olá, boa tarde, esse daqui é um teste.'
)
print(f"Voz clonada: {voice_id}")
```

---

## 11. Monitoramento e Logs

### 11.1. Healthcheck Endpoints

**Container Health:**
```bash
curl http://localhost:8005/
```

**GPU Status:**
Verificar logs do container:
```bash
docker logs audio-voice-api | grep CUDA
```

Deve mostrar:
```
✅ GPU grande detectada (>= 8GB)
   Pode rodar XTTS + F5-TTS simultaneamente
   LOW_VRAM=false é seguro
```

### 11.2. Métricas de Performance

**Jobs Concluídos:**
```bash
curl http://localhost:8005/jobs?status=completed
```

**VRAM Utilizada:**
Verificar logs:
```bash
docker logs audio-voice-celery | grep "VRAM"
```

---

## 12. Suporte e Contato

**Documentação Técnica Completa:**
- `/home/YTCaption-Easy-Youtube-API/services/audio-voice/README.md`
- `/home/YTCaption-Easy-Youtube-API/services/audio-voice/docs/`

**Repositório:**
- GitHub: `YTCaption-Easy-Youtube-API/services/audio-voice`

**Versão deste Documento:**
- Última Atualização: 29/11/2025 18:55 UTC
- Versão API: 2.0.0

---

**Fim do FORUIX.md**
