# PLAN.md — SE9 Phase 1: Quick Wins para Máximo Realismo

**Data:** 2026-07-08
**Objetivo:** Usar o máximo de informação do `make-video.json` para gerar vídeos com mais realismo.
**Foco:** Fase 1 — Quick Wins (impacto alto, esforço baixo)

---

## Contexto

O `make-video.json` contém dados cinematográficos ricos que o SE9 **ignora hoje**:

| Dado | Impacto | Status |
|---|---|---|
| `negative_prompt` | ALTO | ❌ Não enviado ao SE8 |
| `camera_movement` | ALTO | ❌ Ken Burns é aleatório |
| `transition` | MÉDIO | ❌ Transições aleatórias |
| `captions[].global_start/end_seconds` | ALTO | ❌ Timing ignorado |
| `forbidden_visual_elements` | ALTO | ❌ Não usado |
| `composition/lighting/color_mood` | MÉDIO | ❌ Prompt não enriquecido |

---

## Quick Win 1: negative_prompt no SE8

### Problema
O SE8 aceita `negative_prompt` mas o SE9 nunca envia. Resultado: imagens podem conter pessoas, objetos específicos, etc. que deveriam ser evitados.

### Solução
Adicionar parâmetro `negative_prompt` ao `SE8Client.generate_image()` e ao `ImageGenerator.generate_all()`.

### Arquivos a alterar

**`app/infrastructure/http_client.py` — SE8Client.generate_image():**
```python
# Atual:
async def generate_image(self, prompt, width, height, steps, performance):
    payload = {"prompt": prompt, ...}

# Novo:
async def generate_image(self, prompt, width, height, steps, performance, negative_prompt=None):
    payload = {"prompt": prompt, ...}
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
```

**`app/core/models.py` — SceneSuggestion:**
```python
# Atual:
class SceneSuggestion(BaseModel):
    t: float
    visual: str

# Novo:
class SceneSuggestion(BaseModel):
    t: float
    visual: str
    negative_prompt: str = ""  # O que evitar na imagem
```

**`app/services/image_generator.py` — generate_all():**
```python
# Atual:
enhanced_prompt = scene.visual + self.cinematic_suffix

# Novo:
enhanced_prompt = scene.visual + self.cinematic_suffix
negative = scene.negative_prompt or None
images = await self.client.generate_image(
    prompt=enhanced_prompt,
    negative_prompt=negative,
    ...
)
```

### Validação
- Testar com o `make-video.json` — as imagens NÃO devem conter pessoas, casas específicas, etc.
- Comparar visualmente: com vs sem negative_prompt

---

## Quick Win 2: camera_movement → Ken Burns

### Problema
O Ken Burns hoje é aleatório (`zoom_in` ou `zoom_out`). O JSON especifica `camera_movement`:
- `"static"` → deveria ter zoom mínimo ou nenhum
- `"slow_push_in"` → deveria ser `zoom_in` suave

### Solução
Mapear `camera_movement` do JSON para estilo Ken Burns.

### Mapeamento

| JSON `camera_movement` | Ken Burns Style | Zoom Range |
|---|---|---|
| `"static"` | `zoom_in` com range mínimo (1.0→1.05) | 5% |
| `"slow_push_in"` | `zoom_in` (1.0→1.15) | 15% |
| `"slow_pan"` | `zoom_out` (1.15→1.0) | 15% |
| (default) | `zoom_in` (1.0→1.20) | 20% |

### Arquivos a alterar

**`app/core/models.py` — SceneSuggestion:**
```python
class SceneSuggestion(BaseModel):
    t: float
    visual: str
    negative_prompt: str = ""
    camera_movement: str = "slow_push_in"  # static, slow_push_in, slow_pan
```

**`app/infrastructure/ffmpeg_utils.py` — create_segment():**
```python
# Atual:
ZOOM_MAX = 1.20
ZOOM_MIN = 1.0

# Novo (adicionar parâmetro zoom_range):
async def create_segment(..., zoom_style="random", zoom_range=None):
    ZOOM_MIN = 1.0
    ZOOM_MAX = zoom_range or 1.20  # Default 20%
    ...
```

**`app/services/video_assembler.py` — _create_segments():**
```python
# Atual:
scene_style = chosen_seq[i % len(chosen_seq)]

# Novo (usar camera_movement da cena):
camera_movement = "slow_push_in"  # Default
if hasattr(scenes[i], 'camera_movement'):
    camera_movement = scenes[i].camera_movement

if camera_movement == "static":
    scene_style = "zoom_in"
    zoom_range = 1.05  # 5% apenas
elif camera_movement == "slow_push_in":
    scene_style = "zoom_in"
    zoom_range = 1.15  # 15%
elif camera_movement == "slow_pan":
    scene_style = "zoom_out"
    zoom_range = 1.15
else:
    scene_style = "zoom_in"
    zoom_range = 1.20  # Default 20%
```

### Validação
- Cena S01 (`camera_movement: "static"`) → zoom quase imperceptível (5%)
- Cena S02 (`camera_movement: "slow_push_in"`) → zoom_in suave (15%)
- Comparar visualmente com resultado aleatório atual

---

## Quick Win 3: transition do JSON

### Problema
O SE9 escolhe transições aleatórias de uma lista de 30. O JSON especifica transições intencionais:
- `"corte seco"` → hard cut (sem xfade)
- `"fade curto"` → dissolve rápido (0.15s)
- `"corte seco com respiro curto"` → hard cut

### Solução
Mapear `motion.transition` do JSON para parâmetros FFmpeg.

### Mapeamento

| JSON `transition` | FFmpeg | Duração |
|---|---|---|
| `"corte seco"` | hard cut (concat demuxer) | 0s |
| `"fade curto"` | xfade dissolve | 0.15s |
| `"corte seco com respiro"` | hard cut | 0s |
| (default) | xfade aleatório | 0.3s |

### Arquivos a alterar

**`app/core/models.py` — SceneSuggestion:**
```python
class SceneSuggestion(BaseModel):
    t: float
    visual: str
    negative_prompt: str = ""
    camera_movement: str = "slow_push_in"
    transition: str = "corte seco"  # corte_seco, fade_curto, default
```

**`app/services/video_assembler.py` — _concatenate():**
```python
# Atual:
first_xfade = random.choice([...])
transition_list = [first_xfade] + [random.choice(TRANSITIONS) ...]

# Novo (usar transições do JSON):
# Se todas as transições forem "corte seco" → usar concat_simple (sem xfade)
# Se mistura → usar xfade apenas onde necessário
```

### Validação
- Se todas as cenas tiverem `"corte seco"` → vídeo final deve ter hard cuts
- Se uma cena tiver `"fade curto"` → deve ter dissolve naquela transição

---

## Quick Win 4: Caption Timing Preciso

### Problema
O JSON fornece `global_start_seconds` e `global_end_seconds` para cada legenda. O SE9 hoje ignora esse timing — as legendas são posicionadas apenas pelo texto.

### Solução
Usar o timing do JSON para posicionar legendas precisamente no vídeo.

### Arquivos a alterar

**`app/services/video_assembler.py` — assemble():**
```python
# Atual: on_screen_text é lista de dicts com {t, text}
# Novo: usar {t, text, start, end} para timing preciso

# No método de overlay de texto:
if on_screen_text:
    for caption in on_screen_text:
        start = caption.get("t", 0)
        end = caption.get("end", start + 3)
        text = caption["text"]
        # Gerar filtro drawtext com enable='between(t,{start},{end})'
```

**`app/infrastructure/ffmpeg_utils.py` — criar nova função:**
```python
async def add_captions(
    video_path: str,
    output_path: str,
    captions: list[dict],  # [{start, end, text}]
    width: int = 1080,
    height: int = 1920,
) -> None:
    """Add timed captions to video using drawtext filter."""
    # Para cada legenda, gerar filtro drawtext com enable='between(t,start,end)'
    # Concatenar filtros com vírgula
    # Aplicar ao vídeo
```

### Validação
- Legenda "Meu pai comprou um sítio..." deve aparecer entre 1.2s e 4.5s
- Legenda "Parecia alguém se arrastando." deve aparecer entre 7.0s e 8.5s
- Legendas não devem sobrepor narração

---

## Ordem de Implementação

1. **Quick Win 1** (negative_prompt) — 30 min
   - Alterar `http_client.py`, `models.py`, `image_generator.py`
   - Testar com make-video.json

2. **Quick Win 2** (camera_movement) — 45 min
   - Alterar `models.py`, `ffmpeg_utils.py`, `video_assembler.py`
   - Testar com make-video.json

3. **Quick Win 3** (transitions) — 30 min
   - Alterar `models.py`, `video_assembler.py`
   - Testar com make-video.json

4. **Quick Win 4** (caption timing) — 1h
   - Criar `add_captions()` em `ffmpeg_utils.py`
   - Alterar `video_assembler.py`
   - Testar com make-video.json

**Tempo total estimado:** ~2.5h

---

## Validação Final

Após implementar todos os Quick Wins, rodar o pipeline completo com o `make-video.json`:

```bash
cd /root/YTCaption-Easy-Youtube-API/services/se9-make-video-img

# 1. Converter JSON para formato SE9
python3 -c "
import json
with open('make-video.json') as f:
    data = json.load(f)
entry = data[0]
output = entry['output']
scenes = output['scenes']
narration = [{'t': s['start_seconds'], 'text': s['narration_text']} for s in scenes]
scene_suggestions = [{'t': s['start_seconds'], 'visual': s['image']['prompt'], 'negative_prompt': s['image']['negative_prompt'], 'camera_movement': s['image']['camera_movement'], 'transition': s['motion']['transition']} for s in scenes]
on_screen_text = []
for s in scenes:
    for c in s.get('captions', []):
        on_screen_text.append({'t': c['global_start_seconds'], 'text': c['text'], 'end': c['global_end_seconds']})
payload = {
    'post_id': output['post_id'],
    'hook': output['title'],
    'estimated_seconds': output['total_duration_seconds'],
    'language': output.get('language', 'pt-BR'),
    'narration': narration,
    'scene_suggestions': scene_suggestions,
    'on_screen_text': on_screen_text,
    'voice_id': 'builtin_feminino',
    'aspect_ratio': output.get('aspect_ratio', '9:16'),
    'zoom_style': 'random',
    'normalize_text': True,
}
with open('payload_phase1.json', 'w') as f:
    json.dump(payload, f, indent=2, ensure_ascii=False)
print('payload_phase1.json criado')
"

# 2. Enviar ao SE9
curl -X POST http://localhost:8009/jobs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: se9-test-key-2026" \
  -d @payload_phase1.json

# 3. Monitorar
# GET http://localhost:8009/jobs/{job_id}

# 4. Download e comparar
# GET http://localhost:8009/download/{job_id}
```

### Critérios de Sucesso

- [ ] Imagens NÃO contêm pessoas (negative_prompt funciona)
- [ ] Cena S01 tem zoom quase imperceptível (camera_movement=static)
- [ ] Cena S02 tem zoom_in suave (camera_movement=slow_push_in)
- [ ] Transições são hard cuts (transition=corte seco)
- [ ] Legendas aparecem nos momentos corretos (timing preciso)
- [ ] Vídeo final é mais realista que versão anterior

---

## Referências

- JSON de entrada: `make-video.json`
- Análise completa: `INVESTIGATE.md`
- Código fonte: `app/services/`, `app/infrastructure/`, `app/core/`
