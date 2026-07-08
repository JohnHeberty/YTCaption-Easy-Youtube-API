# INVESTIGATE.md — Viabilidade: make-video.json → Vídeo

**Data**: 2026-07-08
**Objetivo**: Investigar se é possível gerar um vídeo a partir do `make-video.json` usando o service SE9 (make-video-img).

---

## 1. Status dos Serviços (em tempo de investigação)

| Serviço | Porta | Status | Detalhes |
|---|---|---|---|
| SE9 make-video-img | 8009 | Online | Worker Thread rodando |
| SE7 audio-generation | 8007 | Degradado | Modelo Chatterbox NÃO carregado, disco crítico |
| SE8 image-generation | 8008 | Online | Fooocus SDXL pronto |
| GPU | — | RTX 3090 | 19.5GB VRAM livre / 24GB total |
| Disco | — | Crítico | 8.8GB livre (96% cheio) |

---

## 2. Análise do make-video.json

### 2.1 Estrutura do Arquivo

O arquivo é um **array JSON** com 1 objeto contendo 4 chaves:

```
[
  {
    "output":        { ... }   ← Dados do vídeo (cenas, narração, config)
    "video_job":     { ... }   ← Metadados do job (não usado pelo SE9)
    "export_final":  { ... }   ← Resultado do pipeline upstream (não usado pelo SE9)
    "next_action":   "send_to_video_creation_service"
  }
]
```

**Origem provável**: Pipeline n8n ou sistema upstream que gera o payload para envio ao SE9.

### 2.2 Dados Extraídos de `output`

| Campo | Valor | Observação |
|---|---|---|
| `job_type` | `"create_short_video"` | Tipo do job |
| `payload_version` | `"video_render_payload_v1"` | Versão do schema |
| `post_id` | `"1ra5656"` | ID do post |
| `title` | `"Fiz meu pai vender o sítio assombrado dele (foi difícil)"` | Título do vídeo |
| `platform` | `"tiktok_reels_shorts"` | Plataforma alvo |
| `aspect_ratio` | `"9:16"` | Formato vertical |
| `language` | `"pt-BR"` | Idioma |
| `total_duration_seconds` | `30` | Duração total |
| `render_settings.width` | `1080` | Largura |
| `render_settings.height` | `1920` | Altura |
| `render_settings.fps` | `30` | FPS |
| `full_narration_text` | 510 caracteres | Texto completo da narração |

### 2.3 Cenas (6 cenas de 5s cada)

| Cena | scene_id | Start | End | Narration (início) |
|---|---|---|---|---|
| S01 | VS01 | 0s | 5s | "Meu pai comprou um sítio perto da família materna." |
| S02 | VS02 | 5s | 10s | "Uma semana depois, ouvi ruídos à noite..." |
| S03 | VS03 | 10s | 15s | "Os ruídos ficaram frequentes..." |
| S04 | VS04 | 15s | 20s | "Comecei a ouvir um canto de mulher..." |
| S05 | VS05 | 20s | 25s | "Uma prima de segundo grau sofreu um acidente..." |
| S06 | VS06 | 25s | 30s | "Convenci meu pai a vender o sítio..." |

Cada cena contém:
- `narration_text` → Texto da narração
- `image.prompt` → Prompt para geração de imagem
- `image.negative_prompt` → O que evitar na imagem
- `captions[]` → Legendas com timestamps
- `motion.camera_movement` → Movimento de câmera (static/slow_push_in)
- `audio.sfx_cues` → Efeitos sonoros (apenas S02 tem 1 cue)

### 2.4 global_style (limites criativos)

```json
{
  "no_supernatural_confirmation": true,
  "no_people_or_faces": true,
  "no_new_facts": true,
  "safety": "Avoid unsupported people, entities, causes, graphic violence"
}
```

---

## 3. Incompatibilidade de Formato (BLOQUEIO #1)

### 3.1 Formato do make-video.json (upstream)

```json
{
  "output": {
    "scenes": [
      {
        "scene_id": "S01",
        "narration_text": "Meu pai comprou...",
        "image": { "prompt": "Estabelecing shot vertical...", "negative_prompt": "..." },
        "captions": [{ "text": "...", "start_seconds": 1.2, "end_seconds": 4.5 }]
      }
    ],
    "full_narration_text": "Meu pai comprou um sítio..."
  }
}
```

### 3.2 Formato esperado pelo SE9 (`CreateVideoRequest`)

```json
{
  "post_id": "1ra5656",
  "hook": "Fiz meu pai vender o sítio...",
  "estimated_seconds": 30,
  "language": "pt-BR",
  "narration": [
    { "t": 0, "text": "Meu pai comprou um sítio perto da família materna." },
    { "t": 5, "text": "Uma semana depois, ouvi ruídos à noite." }
  ],
  "scene_suggestions": [
    { "t": 0, "visual": "Estabelecing shot vertical, câmera estática..." }
  ],
  "on_screen_text": [
    { "t": 1.2, "text": "Meu pai comprou um sítio perto da família materna." }
  ],
  "voice_id": "builtin_feminino",
  "aspect_ratio": "9:16"
}
```

### 3.3 Mapeamento Necessário

| Campo SE9 | Fonte no JSON | Transformação |
|---|---|---|
| `post_id` | `output.post_id` | Direto |
| `hook` | `output.title` | Direto |
| `estimated_seconds` | `output.total_duration_seconds` | Direto |
| `language` | `output.language` | Direto |
| `narration` | `output.scenes[].narration_text` | `[{t: start_seconds, text: narration_text}]` |
| `scene_suggestions` | `output.scenes[].image.prompt` | `[{t: start_seconds, visual: prompt}]` |
| `on_screen_text` | `output.scenes[].captions[].text` | `[{t: global_start_seconds, text}]` |
| `voice_id` | — | Default `"builtin_feminino"` |
| `aspect_ratio` | `output.aspect_ratio` | Direto |
| `zoom_style` | — | Default `"random"` |

### 3.4 Texto da Narração para TTS

O SE9 usa `full_narration_text`? **NÃO.** Ele usa `narration: list[NarrationSegment]` e concatena o texto:

```python
# audio_generator.py:69-72
def _concatenate_narration(self, segments):
    sorted_segs = sorted(segments, key=lambda s: s.t)
    return " ".join(s.text for s in sorted_segs)
```

Ou seja, o texto enviado ao SE7 TTS será:
```
"Meu pai comprou um sítio perto da família materna. Uma semana depois, ouvi ruídos à noite. Parecia alguém se arrastando. Os ruídos ficaram frequentes..."
```

**510 caracteres** — bem abaixo do limite de 5000 do Chatterbox. Será um único chunk.

---

## 4. Fluxo Completo do Pipeline (trace do código)

### 4.1 Entrada: POST /jobs

**Arquivo**: `app/api/routes.py:46-69`

```
1. Recebe CreateVideoRequest (JSON body)
2. Gera job_id = "rbg_" + uuid4().hex[:12]
3. Cria VideoJob(job_id, post_id, request)
4. Salva no Redis: store.save_job(job_id, job.model_dump())
5. Inicia worker: worker.start()
6. Retorna CreateVideoResponse(job_id, status="queued")
```

### 4.2 Worker: Polling

**Arquivo**: `app/worker.py:46-68`

```
1. Thread daemon roda _run_loop()
2. A cada 2 segundos: _get_next_job()
3. Chama store.get_next_queued_job() → busca no Redis sorted set
4. Encontra job com status "queued"
5. Chama _process_job(job) → importa pipeline e chama run_video_pipeline(job)
```

### 4.3 Pipeline: 3 Estágios

**Arquivo**: `app/services/pipeline.py:45-76`

```
1. Cria output_dir = "data/outputs/{job_id}/"
2. Stage 1: _generate_audio()     → 0-40% do progresso
3. Stage 2: _generate_images()    → 40-70% do progresso
4. Stage 3: _assemble_video()     → 70-100% do progresso
5. Marca COMPLETED, salva no Redis
6. Envia webhook se configurado
```

---

## 5. Estágio 1: Geração de Áudio (SE7 TTS)

### 5.1 Fluxo

**Arquivo**: `app/services/audio_generator.py:74-111`

```
1. Concatena narration segments em texto único
   → "Meu pai comprou um sítio... Convenci meu pai a vender..."
   → 510 caracteres

2. Chunking: 510 < 5000 → 1 chunk único

3. Chama SE7:
   POST http://localhost:8007/jobs
   Data (multipart):
     text: "Meu pai comprou um sítio..."
     voice_id: "builtin_feminino"
     exaggeration: "0.5"
     cfg_weight: "0.5"
     temperature: "0.8"
     normalize_text: "true"

4. Polling: GET /jobs/{job_id} a cada 5s até status="completed"
   Timeout: 600s (10 min)

5. Download: GET /jobs/{job_id}/download → bytes WAV

6. Salva: data/outputs/{job_id}/audio.wav
```

### 5.2 O que o SE7 faz internamente

**Arquivo**: SE7 `generate_audio` Celery task

```
1. Valida texto (max 1000 chars por chunk no SE7)
2. Chunking por \n\n e frases
3. Para cada chunk:
   a. ChatterboxModelManager.get_model() → carrega modelo se necessário
   b. model.generate(text, language_id="pt", audio_prompt_path=voice_sample,
                     exaggeration=0.5, temperature=0.8, cfg_weight=0.5)
   c. Retorna torch.Tensor (24kHz waveform)
4. Concatena chunks com pydub (silence de 0.5s entre chunks)
5. Salva WAV: data/outputs/{job_id}.wav
```

### 5.3 Tempo Estimado

| Atividade | Tempo |
|---|---|
| Carregar modelo Chatterbox (primeira vez) | ~10-20s |
| Gerar áudio (510 chars, 1 chunk) | ~5-15s |
| Polling overhead | ~5s |
| **Total Stage 1** | **~20-40s** |

### 5.4 Recursos

| Recurso | Consumo |
|---|---|
| VRAM (Chatterbox) | ~2-4GB |
| Disco (WAV 30s, 24kHz mono) | ~1.4MB |
| RAM | ~500MB |

### 5.5 Retry Logic

```python
# pipeline.py:84-106
MAX_AUDIO_RETRIES = 3
RETRY_BACKOFF_BASE = 2
# Retry: 2s, 4s, 8s backoff
```

---

## 6. Estágio 2: Geração de Imagens (SE8 Fooocus)

### 6.1 Fluxo

**Arquivo**: `app/services/image_generator.py:37-82`

```
1. Para cada cena (6 cenas):
   a. Pega scene.visual (prompt do JSON)
   b. Adiciona cinematic suffix:
      ", cinematic composition, depth of field, volumetric lighting,
       high detail, professional photography, 8k resolution"
   c. Chama SE8:
      POST http://localhost:8008/v1/generation/text-to-image
      JSON: {
        "prompt": "{prompt} + cinematic suffix",
        "width": 1024,    // IMAGE_ASPECT_RATIOS["9:16"]
        "height": 1792,
        "steps": 30,      // default_image_steps
        "performance": "Quality"
      }
   d. Resposta: [{"url": "/files/2026-07-08/xxx.png", "seed": "..."}]
   e. Download: GET /files/2026-07-08/xxx.png → bytes PNG
   f. Salva: data/outputs/{job_id}/scene_{int(t)}.png

2. Progresso: (i+1)/6 * 100 por imagem
```

### 6.2 Prompts Extraídos do JSON

| Cena | Prompt (simplificado) |
|---|---|
| S01 | "Estabelecing shot vertical, paisagem rural genérica..." |
| S02 | "Medium shot of a generic interior at night..." |
| S03 | "Cinematic vertical medium shot of a subtly textured surface..." |
| S04 | "Vertical medium shot of a softly lit interior..." |
| S05 | "Vertical establishing shot, generic medical or recovery environment..." |
| S06 | "Cinematic establishing shot of a bright, modern city street..." |

### 6.3 Tempo Estimado

| Atividade | Tempo |
|---|---|
| 6 imagens × Quality mode (60 steps) | ~15-25s cada |
| Download de cada imagem | ~1-2s |
| **Total Stage 2** | **~100-160s (1.5-2.5 min)** |

### 6.4 Recursos

| Recurso | Consumo |
|---|---|
| VRAM (Fooocus SDXL) | ~6-8GB |
| Disco (6 PNGs, 1024×1792) | ~30-60MB total |
| RAM | ~2GB |

### 6.5 Configuração SE8

| Parâmetro | Valor | Efeito |
|---|---|---|
| `steps` | 30 | Quality mode usa 60 internamente |
| `performance` | `"Quality"` | 60 steps, dpmpp_2m_ssd_gpu, karras |
| `width × height` | 1024 × 1792 | Proporção 9:16 para Fooocus |
| `negative_prompt` | (do JSON) | Evita pessoas, objetos específicos |

---

## 7. Estágio 3: Montagem do Vídeo (FFmpeg)

### 7.1 Cálculo de Duração das Cenas

**Arquivo**: `app/services/video_assembler.py:32-48, 50-127`

```python
# 1. Duração do áudio total (via ffprobe)
audio_duration = get_audio_duration(audio.wav)  # ~30s

# 2. Média por cena baseada nos timestamps da narração
sorted_segs = sorted(narration, key=lambda s: s.t)
# segs: [t=0, t=5, t=10, t=15, t=20, t=25]
# total_span = 25 - 0 = 25
# per_scene_duration = 25 / (6-1) = 5.0s

# 3. Clamp: max(5.0, 3.0) = 5.0, min(5.0, 15.0) = 5.0

# 4. Cenas necessárias: int(30 / 5.0) + 1 = 7 cenas
#    Mas temos 6 imagens → 6 cenas (loop cíclico)

# 5. Cálculo final:
scene_durations = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0]  # 6 × 5s = 30s
```

### 7.2 Title Card (opcional)

Se `hook_text` foi fornecido (neste caso NÃO — o JSON não tem `hook` separado):
- Cria `title_card.mp4` de 0.5s
- Primeira imagem escurecida (drawbox preto 50%)
- Com zoom pan suave

**Para este JSON**: Sem hook separado → **sem title card** (a menos que o conversor defina `hook`).

### 7.3 Ken Burns (Segmentos Individuais)

**Arquivo**: `app/infrastructure/ffmpeg_utils.py:84-144`

Para cada uma das 6 cenas:

```bash
ffmpeg -y \
  -loop 1 -i scene_{t}.png \
  -t 5.0 \
  -vf "scale=-2:3840:force_original_aspect_ratio=increase,
       crop=2160:3840,
       zoompan=z='1.0+0.20*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'
       :d={frames}:s=1080x1920:fps=30,
       format=yuv420p" \
  -c:v libx264 -profile:v main -level 4.0 \
  -g 30 -bf 2 -pix_fmt yuv420p \
  segment_{i}.mp4
```

**Detalhes do Ken Burns**:
- Zoom range: 1.0 → 1.20 (ou reverso)
- `zoom_in`: zoom cresce ao longo da cena
- `zoom_out`: zoom diminui ao longo da cena
- Estilo alternado: `[zoom_in, zoom_out, zoom_in, zoom_out, ...]`
- Imagens são cicladas: 6 imagens → 6 segmentos (sem necessidade de ciclo)

**Tempo por segmento**: ~3-5s (CPU-bound, libx264)
**Total**: ~18-30s para 6 segmentos

### 7.4 Concatenação com Crossfade

**Arquivo**: `app/infrastructure/ffmpeg_utils.py:147-239`

6 segmentos ≤ 8 (MAX_XFAD_BATCH_SIZE) → usa `concat_segments()`:

```bash
ffmpeg -y \
  -i segment_0.mp4 -i segment_1.mp4 -i segment_2.mp4 \
  -i segment_3.mp4 -i segment_4.mp4 -i segment_5.mp4 \
  -filter_complex "
    [0:v][1:v]xfade=transition=dissolve:duration=0.300:offset=4.700[vout1];
    [vout1][2:v]xfade=transition=smoothleft:duration=0.300:offset=9.400[vout2];
    [vout2][3:v]xfade=transition=radial:duration=0.300:offset=14.100[vout3];
    [vout3][4:v]xfade=transition=circleopen:duration=0.300:offset=18.800[vout4];
    [vout4][5:v]xfade=transition=wipeleft:duration=0.300:offset=23.500[vout]
  " \
  -map [vout] \
  -c:v libx264 -preset fast -crf 23 \
  -profile:v main -level 4.0 -g 30 -bf 2 -pix_fmt yuv420p \
  video_concat.mp4
```

**Cálculo dos offsets**:
```
chain_output[0] = 5.0 (duração seg 0)
offset[0] = 5.0 - 0.3 = 4.7
chain_output[1] = 4.7 + 5.0 = 9.7
offset[1] = 9.7 - 0.3 = 9.4
chain_output[2] = 9.4 + 5.0 = 14.4
offset[2] = 14.4 - 0.3 = 14.1
...etc

xfade_duration = min(0.3, 5.0 * 0.15) = min(0.3, 0.75) = 0.3s
```

**Transições**: Escolhidas aleatoriamente de `TRANSITIONS` (30 opções)
**Tempo**: ~10-20s

### 7.5 Padding de Áudio

**Arquivo**: `app/services/video_assembler.py:225-256`

```bash
# 1. Detectar sample rate e canais do áudio original
ffprobe -v error -select_streams a:0 \
  -show_entries stream=sample_rate,channels \
  -of csv=p=0 audio.wav
# Resultado: 24000,1 → 24000Hz mono

# 2. Criar silêncio de 0.5s (se title card existe) ou copiar direto
ffmpeg -y \
  -f lavfi -i "anullsrc=r=24000:cl=mono:d=0.500" \
  -i audio.wav \
  -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1[out]" \
  -map "[out]" \
  -c:a pcm_s16le \
  audio_padded.wav
```

**Se sem title card** (0s de silêncio): `shutil.copy2(audio.wav, audio_padded.wav)`

### 7.6 Merge Áudio + Vídeo

**Arquivo**: `app/infrastructure/ffmpeg_utils.py:342-363`

```bash
ffmpeg -y \
  -i video_concat.mp4 \
  -i audio_padded.wav \
  -map 0:v -map 1:a \
  -c:v copy \
  -c:a aac -profile:a aac_low -ar 44100 -ac 2 -b:a 192k \
  -movflags +faststart \
  video_audio.mp4
```

**Nota**: Não usa `-shortest` — áudio roda completo. Se vídeo for menor, último frame é segurado (freeze frame).

### 7.7 Trim Final

**Arquivo**: `app/infrastructure/ffmpeg_utils.py:366-384`

```bash
ffmpeg -y \
  -i video_audio.mp4 \
  -t 30.000 \
  -c:v libx264 -profile:v main -level 4.0 -g 30 -bf 2 \
  -c:a aac -profile:a aac_low -b:a 192k \
  -pix_fmt yuv420p \
  -movflags +faststart \
  {job_id}_final.mp4
```

---

## 8. Arquivos Gerados (Mapa de Disco)

```
data/outputs/{job_id}/
├── audio.wav              ~1.4MB   (áudio TTS, 24kHz mono, ~30s)
├── scene_0.png            ~3-5MB   (Fooocus 1024×1792)
├── scene_5.png            ~3-5MB
├── scene_10.png           ~3-5MB
├── scene_15.png           ~3-5MB
├── scene_20.png           ~3-5MB
├── scene_25.png           ~3-5MB
├── segment_0.mp4          ~2-4MB   (Ken Burns 1080×1920, 5s)
├── segment_1.mp4          ~2-4MB
├── segment_2.mp4          ~2-4MB
├── segment_3.mp4          ~2-4MB
├── segment_4.mp4          ~2-4MB
├── segment_5.mp4          ~2-4MB
├── video_concat.mp4       ~10-15MB (6 segmentos + xfade)
├── audio_padded.wav       ~1.4MB   (áudio com padding)
├── video_audio.mp4        ~10-15MB (vídeo + áudio mux)
└── {job_id}_final.mp4     ~10-15MB (vídeo final)
───────────────────────────────────────
TOTAL estimado:            ~60-100MB
```

---

## 9. Estimativa de Recursos

### 9.1 VRAM (GPU)

| Componente | VRAM | Quando |
|---|---|---|
| SE7 Chatterbox (carregar) | ~2-4GB | Stage 1 (lazy load) |
| SE7 Chatterbox (inferência) | ~2-4GB | Stage 1 |
| SE8 Fooocus SDXL | ~6-8GB | Stage 2 |
| **Pico total** | **~8-12GB** | Stage 2 (SE7 pode liberar) |
| **Disponível** | **19.5GB** | — |
| **Margem** | **~7-11GB** | Seguro |

### 9.2 Disco

| Item | Tamanho | Acumulado |
|---|---|---|
| Audio WAV | ~1.4MB | 1.4MB |
| 6 imagens PNG | ~18-30MB | ~20-32MB |
| 6 segmentos MP4 | ~12-24MB | ~32-56MB |
| video_concat.mp4 | ~10-15MB | ~42-71MB |
| video_audio.mp4 | ~10-15MB | ~52-86MB |
| final.mp4 | ~10-15MB | ~62-101MB |
| **Limite disponível** | **8.8GB** | — |
| **Uso total** | **~100MB** | **1.1% do disponível** |

### 9.3 RAM

| Processo | RAM estimada |
|---|---|
| FastAPI + Worker | ~200MB |
| httpx connections | ~50MB |
| FFmpeg (6 segmentos sequenciais) | ~500MB pico |
| Python objects | ~100MB |
| **Total** | **~850MB** |

### 9.4 Tempo Total Estimado

| Estágio | Tempo |
|---|---|
| Worker polling | ~2s |
| Stage 1: Áudio (SE7) | ~20-40s |
| Stage 2: Imagens (SE8) | ~100-160s |
| Stage 3: Ken Burns (6 segs) | ~18-30s |
| Stage 3: Concat xfade | ~10-20s |
| Stage 3: Audio pad + merge + trim | ~5-10s |
| **Total** | **~3-5 minutos** |

---

## 10. Cenários de Falha

### 10.1 SE7 Modelo Não Carregado

**Status atual**: Degradado ("Model not loaded")

**O que acontece**: Na primeira chamada TTS, o Chatterbox faz lazy load:
```python
# ChatterboxModelManager → ChatterboxTTS.from_local()
# Carrega: ve.pt, grapheme_mtl_merged_expanded_v1.json, conds.pt
# + t3_pt_br.safetensors, s3gen_v3.pt (multilingual)
```

**Risco**: Se VRAM não for suficiente (SE8 já usando ~6-8GB), pode dar OOM.
**Probabilidade**: Baixa (19.5GB livres).

### 10.2 Disco Insuficiente

**Status atual**: 8.8GB livres
**Uso estimado**: ~100MB
**Risco**: Baixo para uma execução. Crítico se rodar múltiplas vezes sem limpeza.

### 10.3 SE7 Timeout

**Timeout configurado**: 600s (10 min)
**Tempo esperado**: ~20-40s
**Risco**: Muito baixo (510 chars é pouco para TTS).

### 10.4 SE8 Rejeita Prompt

**Prompts do JSON**: Contêm termos como "cinematic", "establishing shot", "medium shot".
**Risco**: Baixo — Fooocus aceita prompts descritivos. Negative prompts do JSON são benéficos.

### 10.5 FFmpeg xfade OOM

**6 segmentos** ≤ 8 (limite do batch)
**Risco**: Baixo — filter_complex de 5 xfades é leve.

### 10.6 Áudio Mais Curto/Longo que Imagens

**Cenário**: Se o TTS gerar áudio de 28s (em vez de 30s esperados)
**Comportamento**: `_calculate_scene_durations` recalcula automaticamente baseado na duração real do áudio.
**Risco**: Nenhum — o pipeline é adaptativo.

---

## 11. Conversão Necessária (Script)

### 11.1 Script de Exemplo

```python
#!/usr/bin/env python3
"""Convert make-video.json (upstream format) → CreateVideoRequest (SE9 format)."""
import json
import sys

def convert(input_path: str) -> dict:
    with open(input_path) as f:
        data = json.load(f)

    entry = data[0] if isinstance(data, list) else data
    output = entry["output"]

    # narration: [{t, text}]
    narration = []
    for scene in output["scenes"]:
        narration.append({
            "t": scene["start_seconds"],
            "text": scene["narration_text"]
        })

    # scene_suggestions: [{t, visual}]
    scene_suggestions = []
    for scene in output["scenes"]:
        scene_suggestions.append({
            "t": scene["start_seconds"],
            "visual": scene["image"]["prompt"]
        })

    # on_screen_text: [{t, text}]
    on_screen_text = []
    for scene in output["scenes"]:
        for cap in scene.get("captions", []):
            on_screen_text.append({
                "t": cap["global_start_seconds"],
                "text": cap["text"]
            })

    return {
        "post_id": output["post_id"],
        "hook": output["title"],
        "estimated_seconds": output["total_duration_seconds"],
        "language": output.get("language", "pt-BR"),
        "narration": narration,
        "scene_suggestions": scene_suggestions,
        "on_screen_text": on_screen_text,
        "title_options": [output["title"]],
        "hashtags": [],
        "safety_notes": [],
        "voice_id": "builtin_feminino",
        "aspect_ratio": output.get("aspect_ratio", "9:16"),
        "zoom_style": "random",
        "webhook_url": None,
        "normalize_text": True,
    }

if __name__ == "__main__":
    result = convert(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))
```

### 11.2 Envio ao SE9

```bash
# Converter
python3 convert.py make-video.json > payload.json

# Enviar
curl -X POST http://localhost:8009/jobs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: se9-test-key-2026" \
  -d @payload.json

# Monitorar
curl http://localhost:8009/jobs/{job_id} \
  -H "X-API-Key: se9-test-key-2026"

# Download
curl -O http://localhost:8009/download/{job_id} \
  -H "X-API-Key: se9-test-key-2026"
```

---

## 12. Veredicto Final

### ✅ VIÁVEL

| Critério | Status | Notas |
|---|---|---|
| Formato JSON | ⚠️ Incompatível | Precisa de conversão (script acima) |
| SE9 online | ✅ | Worker funcional |
| SE8 online | ✅ | Fooocus pronto |
| SE7 online | ⚠️ Degradado | Modelo carrega no primeiro request |
| GPU VRAM | ✅ | 19.5GB livres, pico ~12GB |
| Disco | ✅ | 8.8GB livres, uso ~100MB |
| FFmpeg | ✅ | 6 cenas dentro do limite |
| Tempo estimado | ✅ | ~3-5 minutos |

### Riscos Restantes

1. **Disco**: Rodar múltiplas vezes sem limpeza pode estourar 8.8GB
2. **SE7 lazy load**: Primeira execução pode demorar +10-20s para carregar modelo
3. **Hook ausente**: O JSON não tem campo `hook` separado — se o conversor usar `title` como hook, o title card será criado (0.5s de vídeo escurecido antes do conteúdo)

### Próximos Passos (se desejar executar)

1. Criar script de conversão (acima)
2. Limpar `data/outputs/` de jobs antigos
3. Executar conversão + POST /jobs
4. Monitorar progresso via GET /jobs/{id}
5. Download do MP4 final via GET /download/{id}
