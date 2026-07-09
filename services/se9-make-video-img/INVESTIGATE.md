# INVESTIGATE.md — Viabilidade: make-video.json → Vídeo

**Data**: 2026-07-08 (atualizado)
**Objetivo**: Investigar se é possível gerar um vídeo a partir do `make-video.json` usando o service SE9 (make-video-img).
**Versão**: v2 — análise aprofundada com gap analysis e mapeamento campo-a-campo.

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

### 2.2 Campos de `output` — Mapeamento Completo

| Campo | Valor | Tipo | SE9 Usa? | Observação |
|---|---|---|---|---|
| `job_type` | `"create_short_video"` | string | ❌ Ignorado | Metadado do upstream |
| `payload_version` | `"video_render_payload_v1"` | string | ❌ Ignorado | Versão do schema |
| `post_id` | `"1ra5656"` | string | ✅ Usado | Mapeado para CreateVideoRequest.post_id |
| `title` | `"Fiz meu pai vender o sítio..."` | string | ✅ Usado | Mapeado para CreateVideoRequest.hook |
| `platform` | `"tiktok_reels_shorts"` | string | ❌ Ignorado | Metadado — útil para presets futuros |
| `aspect_ratio` | `"9:16"` | string | ✅ Usado | Mapeado para CreateVideoRequest.aspect_ratio |
| `language` | `"pt-BR"` | string | ✅ Usado | Mapeado para CreateVideoRequest.language |
| `total_duration_seconds` | `30` | int | ✅ Usado | Mapeado para CreateVideoRequest.estimated_seconds |
| `render_settings.width` | `1080` | int | ❌ Ignorado | SE9 usa config default (1080) — OK |
| `render_settings.height` | `1920` | int | ❌ Ignorado | SE9 usa config default (1920) — OK |
| `render_settings.fps` | `30` | int | ❌ Ignorado | SE9 usa config default (30) — OK |
| `render_settings.format` | `"mp4"` | string | ❌ Ignorado | SE9 sempre gera MP4 |
| `full_narration_text` | 510 chars | string | ❌ Ignorado | SE9 concatena narration segments |
| `global_style` | { ... } | object | ❌ Ignorado | Limites criativos — ver seção 2.4 |
| `scenes` | [ ... ] | array | ✅ Parcial | Ver seção 2.3 |

### 2.3 Cenas — Análise Campo-a-Campo (6 cenas)

#### 2.3.1 Visão Geral das Cenas

| Cena | scene_id | Start | End | Duration | camera_movement | transition |
|---|---|---|---|---|---|---|
| S01 | VS01 | 0s | 5s | 5s | `static` | `corte seco` |
| S02 | VS02 | 5s | 10s | 5s | `slow_push_in` | `corte seco` |
| S03 | VS03 | 10s | 15s | 5s | `slow_push_in` | `fade curto` |
| S04 | VS04 | 15s | 20s | 5s | `static` | `corte seco` |
| S05 | VS05 | 20s | 25s | 5s | `static` | `corte seco` |
| S06 | VS06 | 25s | 30s | 5s | `static` | `corte seco` |

#### 2.3.2 Campo `image` por Cena

**S01** — Paisagem rural
```
prompt: "Estabelecing shot vertical, câmera estática, paisagem rural genérica
         com vegetação rasteira e céu levemente nublado sob luz natural discreta.
         foco no ambiente."
negative_prompt: "pessoas, casas, carros, cercas, animais, objetos específicos,
                  elementos urbanos, estruturas construídas, detalhes chamativos."
shot_type: "establishing_shot"
framing: "vertical 9:16 framing, fact-safe"
camera_movement: "static"
composition: "Composição vertical simples com foco no ambiente rural genérico
              e espaço negativo no céu."
subject: "paisagem rural genérica"
environment: "ambiente rural genérico"
lighting: "natural discreet"
color_mood: "soft dark"
visual_action: "nenhuma ação encenada"
broll_direction: "B-roll atmosférico de campo aberto com vegetação e céu
                  levemente nublado."
allowed_visual_elements: ["ambiente rural genérico", "vegetação", "céu", "luz natural discreta"]
forbidden_visual_elements: ["casa específica", "pessoas", "veículos", "objetos específicos",
                            "marcas de presença humana"]
```

**S02** — Interior noturno
```
prompt: "Medium shot of a generic interior at night. Soft low light, minimal detail.
         Focus on atmosphere and creating a sense of anticipation. Vertical 9:16
         aspect ratio. Slow push-in."
negative_prompt: "people, faces, specific objects, entities, shadows suggesting
                  figures, gore, violence, exterior scenes."
shot_type: "medium_shot"
framing: "vertical 9:16 framing, fact-safe"
camera_movement: "slow_push_in"
composition: "Composição vertical simples com espaço negativo na parte superior
              e inferior do quadro."
subject: "ambiente interno genérico"
environment: "ambiente interno generico"
lighting: "soft low light"
color_mood: "low contrast"
visual_action: "Nenhuma ação encenada, apenas uma atmosfera de espera e expectativa."
broll_direction: "b-roll cinematográfico e fact-locked, focado em detalhes ambientais discretos."
allowed_visual_elements: ["ambiente interno genérico", "luz baixa", "espaço vazio"]
forbidden_visual_elements: ["pessoas", "objetos específicos não sustentados", "entidades",
                            "causas visíveis"]
```

**S03** — Textura em luz baixa
```
prompt: "Cinematic vertical medium shot of a subtly textured surface in low light.
         Slow, gentle push-in to create tension. Focus on atmosphere and subtle movement."
negative_prompt: "people, faces, objects, rooms, entities, ghosts, shadows,
                  sharp details, bright colors, explicit causes."
shot_type: "medium_shot"
framing: "vertical 9:16 framing, fact-safe"
camera_movement: "slow_push_in"
composition: "Simple vertical composition with neutral space and subtle depth.
              Focus on a central area without identifiable objects."
subject: "b-roll atmospheric compatible with the scene"
environment: "ambiente interno generico"
lighting: "soft low light"
color_mood: "contained tension"
visual_action: "No staged action. Subtle visual texture to represent sound waves
                or vibrations."
broll_direction: "Cinematic b-roll of a textured surface with minimal detail.
                  Focus on atmosphere and subtle movement."
allowed_visual_elements: ["ambiente interno generico", "textura neutra", "luz baixa",
                          "espaço vazio"]
forbidden_visual_elements: ["personagem", "objeto específico", "localização específica",
                            "causa do ruído", "entidade sobrenatural"]
```

**S04** — Exterior ao entardecer
```
prompt: "Cinematic vertical b-roll of a natural outdoor environment at dusk,
         soft low light, focus on atmospheric textures like trees and clouds. No people."
negative_prompt: "people, houses, specific objects, ghosts, entities, bright lights,
                  clear sky, obvious causes."
shot_type: "neutral_broll"
framing: "vertical 9:16 framing, fact-safe"
camera_movement: "static"
composition: "Composição vertical simples com foco em espaço negativo e luz baixa
              para criar uma sensação de isolamento."
subject: "ambiente externo genérico"
environment: "ambiente externo generico"
lighting: "soft low light"
color_mood: "soft dark"
visual_action: "sem ação encenada"
broll_direction: "B-roll atmosférico de ambiente natural com pouca luz e foco
                  em elementos neutros como árvores ou céu nublado."
allowed_visual_elements: ["ambiente externo generico", "luz baixa", "espaço negativo",
                          "textura neutra"]
forbidden_visual_elements: ["pessoa", "casa", "objeto específico", "causa confirmada",
                            "entidade"]
```

**S05** — Interior melancólico
```
prompt: "Plano médio estático de um ambiente interno genérico, com iluminação suave
         e baixa. Foco na atmosfera tranquila e levemente melancólica. Texturas sutis
         e cores dessaturadas."
negative_prompt: "pessoas, objetos específicos, imagens de acidente, detalhes gráficos,
                  rostos, expressões faciais, ações específicas."
shot_type: "medium_shot"
framing: "vertical 9:16 framing, fact-safe"
camera_movement: "static"
composition: "Simples, com foco no espaço e atmosfera. Profundidade de campo rasa."
subject: "ambiente interno genérico, levemente iluminado"
environment: "ambiente interno generico"
lighting: "soft low light"
color_mood: "low contrast"
visual_action: "Nenhuma ação encenada. Apenas a sugestão de um espaço tranquilo."
broll_direction: "foco em texturas e detalhes neutros do ambiente"
allowed_visual_elements: ["ambiente interno genérico", "luz baixa", "espaço vazio",
                          "textura neutra"]
forbidden_visual_elements: ["pessoas", "objetos específicos", "imagens de acidente",
                            "imagens de locomoção arrastando", "expressão facial específica",
                            "cozinhas", "salas"]
```

**S06** — Cidade diurna
```
prompt: "cinematic establishing shot of a bright, modern city street during daylight.
         Focus on the open sky and the flow of traffic. Neutral colors. Vertical
         aspect ratio."
negative_prompt: "people, specific buildings, abandoned structures, emotional expressions,
                  farms, countryside, sadness, regret, old photographs."
shot_type: "establishing_shot"
framing: "vertical 9:16 framing, fact-safe"
camera_movement: "static"
composition: "simple vertical composition emphasizing open space and a sense
              of new beginnings."
subject: "generic city street scene"
environment: "city generica"
lighting: "natural discreet"
color_mood: "neutral cold"
visual_action: "no staged action; subtle movement of clouds or distant traffic"
broll_direction: "cinematic b-roll of a generic city environment with focus
                  on natural light and open space."
allowed_visual_elements: ["generic city buildings", "open sky", "distant traffic",
                          "neutral lighting"]
forbidden_visual_elements: ["specific faces", "specific landmarks", "emotional expressions",
                            "any indication of past life at the farm"]
```

#### 2.3.3 Campo `motion` por Cena

| Cena | camera_movement | motion_rhythm | edit_pacing | transition | transition_audio |
|---|---|---|---|---|---|
| S01 | `static` | cena estática com ritmo contido | ritmo contido | corte seco | corte seco com respiro curto |
| S02 | `slow_push_in` | aproximação perceptual suave | ritmo contido | corte seco | corte seco com respiro curto |
| S03 | `slow_push_in` | aproximação perceptual suave | ritmo contido | fade curto | corte seco com respiro curto |
| S04 | `static` | cena estática com ritmo contido | ritmo contido | corte seco | corte seco com respiro curto |
| S05 | `static` | cena estática com ritmo contido | ritmo contido | corte seco | corte seco com respiro curto |
| S06 | `static` | cena estática com ritmo contido | ritmo contido | corte seco | corte seco com respiro curto |

**Mapeamento motion → SE9:**
- `camera_movement` → Ken Burns zoom direction (zoom_in/zoom_out/static)
- `transition` → FFmpeg xfade transition name
- `motion_rhythm` → ❌ Não usado (metadado)
- `edit_pacing` → ❌ Não usado (metadado)
- `transition_audio` → ❌ Não usado (metadado)

#### 2.3.4 Campo `audio` por Cena

| Cena | ambient_bed | music_bed | sfx_cues (qty) | silence_cues (qty) |
|---|---|---|---|---|
| S01 | ambiente rural de baixa presença | sem cama musical | 0 | 1 (0.5-1.0s) |
| S02 | ambiente interno discreto | sem cama musical | 1 (6.5-7.0s) | 1 (9.0-9.5s) |
| S03 | ambiente interno discreto | sem cama musical | 2 (10.5-11.2s, 12.8-13.5s) | 1 (14.2-15.0s) |
| S04 | ambiente neutro de baixa presença | sem cama musical | 1 (16.2-17.8s) | 1 (19.1-20.0s) |
| S05 | ambiente interno discreto | sem cama musical | 1 (22.5-23.0s) | 1 (21.0-21.5s) |
| S06 | ambiente neutro de baixa presença | sem cama musical | 0 | 1 (28.0-29.0s) |

**Total de sfx_cues**: 5 em 6 cenas
**Total de silence_cues**: 6 (1 por cena)

**Mapeamento audio → SE9:**
- `ambient_bed` → ❌ Não usado (descrição textual — precisa de mapeamento para áudio real)
- `music_bed` → ❌ Não usado (sempre "sem cama musical")
- `sfx_cues` → ❌ Não usado (contém timing + descrição — precisa de biblioteca de SFX)
- `silence_cues` → ❌ Não usado (timing de silêncio — pode ser usado para pausar narração)
- `mix_notes` → ❌ Não usado (metadado de mixagem)
- `sound_goal` → ❌ Não usado (metadado)

#### 2.3.5 Campo `captions` por Cena

| Cena | caption_id | text | start | end | global_start | global_end | source |
|---|---|---|---|---|---|---|---|
| S01 | VS01-CAP01 | "Meu pai comprou um sítio perto da família materna." | 1.2s | 4.5s | 1.2s | 4.5s | narration_text |
| S02 | VS02-CAP01 | "Parecia alguém se arrastando." | 2.0s | 3.5s | 7.0s | 8.5s | narration_text |
| S03 | VS03-CAP01 | "Os ruídos se tornaram frequentes." | 1.5s | 3.0s | 11.5s | 13.0s | narration_text |
| S04 | VS04-CAP01 | "Comecei a ouvir um canto de mulher." | 1.5s | 3.0s | 16.5s | 18.0s | narration_text |
| S05 | VS05-CAP01 | "Perdeu os movimentos." | 2.0s | 3.5s | 22.0s | 23.5s | narration_text |
| S06 | VS06-CAP01 | "Convenci meu pai a vender o sítio." | 0.5s | 2.5s | 25.5s | 27.5s | narration_text |
| S06 | VS06-CAP02 | "A família voltou para a cidade." | 2.7s | 4.7s | 27.7s | 29.7s | narration_text |

**Total de captions**: 7 (S06 tem 2)

**Mapeamento captions → SE9:**
- `global_start_seconds` → ❌ SE9 usa `on_screen_text.t` (start_seconds local) — **BUG: ignora timing global**
- `global_end_seconds` → ❌ SE9 não tem campo end_seconds em OnScreenText — **BUG: captions ficam visíveis indefinidamente**
- `start_seconds` (local) → ✅ SE9 usa como `t` no OnScreenText
- `text` → ✅ SE9 usa como `text` no OnScreenText
- `caption_id` → ❌ Ignorado (metadado)
- `source` → ❌ Ignorado (sempre "narration_text")

### 2.4 global_style — Limites Criativos

```json
{
  "visual_style": "neutral, cinematic, fact-locked, restrained tension",
  "tone": "medo, tensão, estranhamento, alívio",
  "pacing": "Use a clear first frame, simple vertical composition, progressive tension,
             and short readable overlays without adding facts.",
  "continuity": "Preserve scene order, beat order, visual consistency, simple transitions,
                 and restrained palette.",
  "safety": "Avoid unsupported people, entities, causes, graphic violence,
             and any visual that turns ambiguity into certainty.",
  "no_supernatural_confirmation": true,
  "no_people_or_faces": true,
  "no_new_facts": true
}
```

**Impacto no SE9:**
- `visual_style` → ❌ Não usado — poderia enriquecer prompts do SE8
- `tone` → ❌ Não usado — poderia influenciar escolha de transições/cores
- `pacing` → ❌ Não usado — metadado
- `continuity` → ❌ Não usado — metadado
- `safety` → ❌ Não usado — poderia ser adicionado como safety_notes
- `no_people_or_faces` → ❌ Não usado — **importante**: deve ser adicionado como negative_prompt global
- `no_supernatural_confirmation` → ❌ Não usado — metadado
- `no_new_facts` → ❌ Não usado — metadado

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
        "image": {
          "prompt": "Estabelecing shot vertical...",
          "negative_prompt": "...",
          "camera_movement": "static",
          "shot_type": "establishing_shot",
          "composition": "...",
          "lighting": "natural discreet",
          "color_mood": "soft dark"
        },
        "motion": {
          "camera_movement": "static",
          "transition": "corte seco"
        },
        "audio": {
          "sfx_cues": [...],
          "silence_cues": [...],
          "ambient_bed": "..."
        },
        "captions": [
          {
            "text": "...",
            "start_seconds": 1.2,
            "end_seconds": 4.5,
            "global_start_seconds": 1.2,
            "global_end_seconds": 4.5
          }
        ]
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
    {
      "t": 0,
      "visual": "Estabelecing shot vertical, câmera estática...",
      "negative_prompt": "pessoas, casas, carros...",
      "camera_movement": "static",
      "transition": "dissolve"
    }
  ],
  "on_screen_text": [
    { "t": 1.2, "text": "Meu pai comprou um sítio perto da família materna.", "end_seconds": 4.5 }
  ],
  "voice_id": "builtin_feminino",
  "aspect_ratio": "9:16"
}
```

### 3.3 Mapeamento Necessário (Completo)

| Campo SE9 | Fonte no JSON | Transformação | Status |
|---|---|---|---|
| `post_id` | `output.post_id` | Direto | ✅ Implementado |
| `hook` | `output.title` | Direto | ✅ Implementado |
| `estimated_seconds` | `output.total_duration_seconds` | Direto | ✅ Implementado |
| `language` | `output.language` | Direto | ✅ Implementado |
| `narration` | `output.scenes[].narration_text` | `[{t: start_seconds, text: narration_text}]` | ✅ Implementado |
| `scene_suggestions[].visual` | `output.scenes[].image.prompt` | Direto | ✅ Implementado |
| `scene_suggestions[].negative_prompt` | `output.scenes[].image.negative_prompt` | Direto | ❌ **NÃO implementado** |
| `scene_suggestions[].camera_movement` | `output.scenes[].motion.camera_movement` | Mapear: "static"→"static", "slow_push_in"→"slow_push_in" | ❌ **NÃO implementado** |
| `scene_suggestions[].transition` | `output.scenes[].motion.transition` | Mapear: "corte seco"→null, "fade curto"→"fadeblack" | ❌ **NÃO implementado** |
| `on_screen_text[].t` | `output.scenes[].captions[].global_start_seconds` | Usar global (não local) | ❌ **BUG: usa local** |
| `on_screen_text[].text` | `output.scenes[].captions[].text` | Direto | ✅ Implementado |
| `on_screen_text[].end_seconds` | `output.scenes[].captions[].global_end_seconds` | Usar global (não local) | ❌ **NÃO implementado** |
| `voice_id` | — | Default `"builtin_feminino"` | ✅ Implementado |
| `aspect_ratio` | `output.aspect_ratio` | Direto | ✅ Implementado |
| `zoom_style` | — | Default `"random"` | ✅ Implementado |
| `global_style` | `output.global_style` | Direto | ❌ **NÃO implementado** |

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

| Cena | Prompt (simplificado) | negative_prompt (NO JSON, SE9 ignora) |
|---|---|---|
| S01 | "Estabelecing shot vertical, paisagem rural genérica..." | "pessoas, casas, carros, cercas, animais..." |
| S02 | "Medium shot of a generic interior at night..." | "people, faces, specific objects, entities..." |
| S03 | "Cinematic vertical medium shot of a subtly textured surface..." | "people, faces, objects, rooms, entities..." |
| S04 | "Cinematic vertical b-roll of a natural outdoor environment at dusk..." | "people, houses, specific objects, ghosts..." |
| S05 | "Plano médio estático de um ambiente interno genérico..." | "pessoas, objetos específicos, imagens de acidente..." |
| S06 | "cinematic establishing shot of a bright, modern city street..." | "people, specific buildings, abandoned structures..." |

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
| `negative_prompt` | **NÃO ENVIADO** | SE9 não passa negative_prompt ao SE8 |

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

## 11. Gap Analysis Detalhado (JSON vs SE9)

### 11.1 Resumo de Gaps por Impacto

| # | Gap | Impacto | Prioridade | Estágio |
|---|---|---|---|---|
| G1 | `negative_prompt` não enviado ao SE8 | 🔴 Alto | P1 | Imagens |
| G2 | `camera_movement` ignorado (SE9 usa random) | 🔴 Alto | P1 | Assembly |
| G3 | `transition` ignorada (SE9 usa random) | 🟡 Médio | P1 | Assembly |
| G4 | `global_start_seconds` ignorado (usa local) | 🔴 Alto | P1 | Captions |
| G5 | `end_seconds` não suportado em OnScreenText | 🔴 Alto | P1 | Captions |
| G6 | `global_style` ignorado | 🟡 Médio | P2 | Metadata |
| G7 | `sfx_cues` ignorados | 🟡 Médio | P3 | Audio |
| G8 | `silence_cues` ignorados | 🟡 Médio | P3 | Audio |
| G9 | `ambient_bed` ignorado | 🟢 Baixo | P3 | Audio |
| G10 | `shot_type/composition/lighting` ignorados | 🟢 Baixo | P2 | Prompts |
| G11 | `platform` ignorado (sem presets) | 🟢 Baixo | P4 | Metadata |
| G12 | `allowed/forbidden_visual_elements` ignorados | 🟢 Baixo | P2 | Prompts |

### 11.2 Impacto por Gap

**G1 — negative_prompt (ALTO)**
- **Situação atual**: SE9 envia prompt + cinematic_suffix ao SE8, sem negative_prompt
- **JSON提供**: Cada cena tem negative_prompt específico (ex: "pessoas, casas, carros...")
- **Impacto**: Imagens podem conter elementos indesejados (pessoas, objetos urbanos)
- **Correção**: Adicionar campo `negative_prompt` em SceneSuggestion, passar ao SE8Client

**G2 — camera_movement (ALTO)**
- **Situação atual**: SE9 usa `zoom_style=random` → alterna zoom_in/zoom_out aleatoriamente
- **JSON提供**: `motion.camera_movement` = "static" ou "slow_push_in" por cena
- **Impacto**: Cenas que deveriam ser estáticas (S01, S04-S06) recebem zoom desnecessário
- **Correção**: Mapear `camera_movement` → `zoom_style` por cena

**G3 — transition (MÉDIO)**
- **Situação atual**: SE9 escolhe transição aleatória de `TRANSITIONS` (30 opções)
- **JSON提供**: `motion.transition` = "corte seco" (5 cenas) ou "fade curto" (1 cena)
- **Impacto**: Transições podem ser incompatíveis com o tom da cena
- **Correção**: Mapear `transition` do JSON → FFmpeg xfade name

**G4 — global_start_seconds (ALTO)**
- **Situação atual**: SE9 usa `on_screen_text.t` = `start_seconds` local da cena
- **JSON提供**: `captions[].global_start_seconds` = timestamp global correto
- **Impacto**: Legendas aparecem no timing errado (ex: S02 caption aparece em 2s em vez de 7s)
- **Correção**: Usar `global_start_seconds` como `t` na conversão

**G5 — end_seconds (ALTO)**
- **Situação atual**: `OnScreenText` não tem campo `end_seconds`
- **JSON提供**: `captions[].global_end_seconds` define quando a legenda some
- **Impacto**: Legendas ficam visíveis até a próxima legenda ou fim do vídeo
- **Correção**: Adicionar `end_seconds` ao modelo OnScreenText

### 11.3 Prioridade de Implementação

**Fase 1 — Quick Wins (1-2h):**
1. G1: negative_prompt → SE8Client.generate_image() + models.py
2. G2: camera_movement → SceneSuggestion + assembler
3. G3: transition → SceneSuggestion + assembler
4. G4+G5: global_start_seconds + end_seconds → OnScreenText

**Fase 2 — Prompt Enrichment (2-4h):**
5. G6: global_style → negative_prompt global
6. G10: shot_type/composition → enriquecer prompts
7. G12: allowed/forbidden → validação de prompts

**Fase 3 — Audio (4-8h):**
8. G7: sfx_cues → biblioteca de SFX + mixagem
9. G8: silence_cues → pausas na narração
10. G9: ambient_bed → camada de ambiente

---

## 12. Conversão Necessária (Script)

### 12.1 Script de Exemplo (Atualizado com Gaps Corrigidos)

```python
#!/usr/bin/env python3
"""Convert make-video.json (upstream format) → CreateVideoRequest (SE9 format).

v2: Includes negative_prompt, camera_movement, transition, global caption timing.
"""
import json
import sys

# Mapeamento de transições do JSON para FFmpeg xfade
TRANSITION_MAP = {
    "corte seco": None,           # No transition (hard cut)
    "fade curto": "fadeblack",    # Short fade to black
    "fade": "fadefast",           # Fast fade
    "dissolve": "dissolve",       # Cross dissolve
    "corte": None,                # Hard cut
}

# Mapeamento de camera_movement para Ken Burns zoom
CAMERA_MOVEMENT_MAP = {
    "static": "static",
    "slow_push_in": "slow_push_in",
    "slow_pull_out": "slow_pull_out",
}

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

    # scene_suggestions: [{t, visual, negative_prompt, camera_movement, transition}]
    scene_suggestions = []
    for scene in output["scenes"]:
        suggestion = {
            "t": scene["start_seconds"],
            "visual": scene["image"]["prompt"],
        }
        # G1: Include negative_prompt
        if scene["image"].get("negative_prompt"):
            suggestion["negative_prompt"] = scene["image"]["negative_prompt"]

        # G2: Include camera_movement
        motion = scene.get("motion", {})
        cam_move = motion.get("camera_movement")
        if cam_move and cam_move in CAMERA_MOVEMENT_MAP:
            suggestion["camera_movement"] = CAMERA_MOVEMENT_MAP[cam_move]

        # G3: Include transition
        transition_raw = motion.get("transition")
        if transition_raw and transition_raw in TRANSITION_MAP:
            mapped = TRANSITION_MAP[transition_raw]
            if mapped:  # None means hard cut (no transition)
                suggestion["transition"] = mapped

        scene_suggestions.append(suggestion)

    # on_screen_text: [{t, text, end_seconds}] — using GLOBAL timestamps
    on_screen_text = []
    for scene in output["scenes"]:
        for cap in scene.get("captions", []):
            entry = {
                "t": cap["global_start_seconds"],    # G4: Use global timing
                "text": cap["text"],
            }
            # G5: Include end_seconds
            if "global_end_seconds" in cap:
                entry["end_seconds"] = cap["global_end_seconds"]
            on_screen_text.append(entry)

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
        # G6: Preserve global_style metadata
        "global_style": output.get("global_style"),
    }

if __name__ == "__main__":
    result = convert(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))
```

### 12.2 Envio ao SE9

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

## 13. Veredicto Final

### ✅ VIÁVEL (com ressalvas)

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
| **Dados aproveitados** | **~20%** | **12 campos ignorados** |

### Gaps Críticos (P1)

1. **negative_prompt** → Imagens podem conter elementos indesejados
2. **camera_movement** → Zoom aleatório em cenas que deveriam ser estáticas
3. **caption timing** → Legendas no timing errado (local vs global)
4. **end_seconds** → Legendas ficam visíveis indefinidamente

### Riscos Restantes

1. **Disco**: Rodar múltiplas vezes sem limpeza pode estourar 8.8GB
2. **SE7 lazy load**: Primeira execução pode demorar +10-20s para carregar modelo
3. **Hook ausente**: O JSON não tem campo `hook` separado — se o conversor usar `title` como hook, o title card será criado (0.5s de vídeo escurecido antes do conteúdo)

### Próximos Passos (se desejar executar)

1. **Fase 1**: Implementar gaps P1 (negative_prompt, camera_movement, transitions, captions)
2. Criar script de conversão v2 (acima)
3. Limpar `data/outputs/` de jobs antigos
4. Executar conversão + POST /jobs
5. Monitorar progresso via GET /jobs/{id}
6. Download do MP4 final via GET /download/{id}
7. **Fase 2**: Prompt enrichment (global_style, shot_type, composition)
8. **Fase 3**: Audio enrichment (sfx_cues, silence_cues, ambient_bed)
