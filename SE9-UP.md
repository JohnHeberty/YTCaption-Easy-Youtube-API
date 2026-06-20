# SE9-UP — Melhorias de Animação e Transição

## Pesquisa: Técnicas Profissionais de Animação de Imagens Estáticas

### O que o FFmpeg zoompan oferece oficialmente

Do **próprio site do FFmpeg** (`11.293 zoompan`):

**Variáveis disponíveis:** `in` (frame do input), `on` (frame do output), `iw/ih` (input width/height), `ow/oh` (output width/height), `zoom/pzoom` (zoom atual/anterior), `x/px/y/py` (posição atual/anterior), `in_time/it` (tempo em segundos)

**Fato crítico:** zoompan **NÃO tem easing embutido**. Movimento é **linear por frame** — `z` é avaliado uma vez por input frame e aplicado uniformemente a `d` output frames. Para easing, precisa compor manualmente com `min()`, `max()`, `if()`, `between()` etc.

### O que profissionais de verdade fazem

| Técnica | Ferramenta | FFmpeg equivalente |
|---------|-----------|-------------------|
| **Easing (suavização)** | After Effects, DaVinci | Expressões quadráticas: `z='1+speed*(on/d)^2'` |
| **Multi-fase zoom** | Final Cut Pro | `if(between(in_time,0,3), zoom_in, zoom_out)` |
| **Zoom para ponto focal** | Premiere Pro | `x='if(gte(zoom,1.5), focal_x, ...)'` |
| **Parallax/2.5D** | After Effects + masks | Impossível só com FFmpeg (precisa AI) |
| **Vignette animado** | DaVinci | `vignette='PI/5+PI/30*sin(t*0.8)':eval=frame` |
| **Brilho pulsante** | Qualquer NLE | `eq=brightness='0.03*sin(2*PI*t/3)':eval=frame` |
| **Breathing (respiração)** | Motion | `z='1+0.01*sin(t*2)'` oscillation |
| **Zoom+Pan composto** | Todos | x e y variam com zoom para focal point |
| **Cor Dinâmica** | DaVinci curves | `curves=m='0/0 0.5/0.55 1/1':eval=frame` |

### O que nosso código faz HOJE (e por que é chato)

1. **Zoom linear constante** — `z='1+0.004*on'` — mesma velocidade do início ao fim, sem vida
2. **Pan linear** — `x='on*0.004*4'` — desliza como uma esteira
3. **Sem easing** — começo e fim são idênticos, sem transição suave
4. **Sem efeitos de profundidade** — imagem parece "colada" no tempo
5. **Sem variação de cor/brilho** — tudo estático e flat
6. **Sem vignette** — imagem sem profundidade visual
7. **Mesma velocidade para todas as cenas** — sem hierarquia visual

---

## Plano de Melhoria — 5 Camadas de Animação

### Camada 1: Ken Burns com Easing (substitui zoom linear)
**Arquivo:** `app/infrastructure/ffmpeg_utils.py` → `create_segment()`

Substituir zoom linear por **easing quadrático**:

```python
# ANTES (linear — chato):
zoom_expr = f"1+{zoom_speed}*on"

# DEPOIS (ease-in-out — profissional):
# Ease-in-out quadrático: desacelera no início e no fim
zoom_expr = f"min(1.15, 1+{zoom_speed}*d*if(lt(on,d/2), 2*(on/d)^2, 1-2*(1-on/d)^2))"
```

**8 estilos com easing:**
- `zoom_in_ease` — zoom in suave com ease-in-out
- `zoom_out_ease` — zoom out suave com ease-in-out
- `pan_left_ease` — pan esquerda com desaceleração
- `pan_right_ease` — pan direita com desaceleração
- `zoom_in_top` — zoom no terço superior (retrato)
- `zoom_in_bottom` — zoom no terço inferior (paisagem)
- `zoom_out_center` — reveal dramático do centro
- `diagonal_ease` — zoom + pan diagonal com easing

### Camada 2: Vignette Animado
**Arquivo:** `app/infrastructure/ffmpeg_utils.py` → `create_segment()`

Adicionar vignette que muda suavemente ao longo do segmento:
```python
# Vignette que oscila levemente — cria profundidade
vignette_expr = f"vignette='PI/6+PI/40*sin(on/{frames}*PI)':eval=frame"
```

### Camada 3: Brilho/Saturação Dinâmica
**Arquivo:** `app/infrastructure/ffmpeg_utils.py` → `create_segment()`

Filtro `eq` com variação temporal:
```python
# Sutil brilho que pulsa — imagem parece "viva"
eq_filter = f"eq=brightness='0.02*sin(2*PI*on/{frames})':saturation='1+0.05*sin(2*PI*on/{frames}*0.5)'"
```

### Camada 4: Focal Point Zoom (zoom para ponto específico)
**Arquivo:** `app/infrastructure/ffmpeg_utils.py` → `create_segment()`

Zoom não para o centro, mas para pontos de interesse:
```python
# Zoom begin showing top-right corner, end centered
x_expr = f"(1-on/{frames})*(iw*0.3)+{on}/{frames}*(iw/2-(iw/zoom/2))"
y_expr = f"(1-on/{frames})*(ih*0.1)+{on}/{frames}*(ih/2-(ih/zoom/2))"
```

### Camada 5: Variação de Velocidade por Cena
**Arquivo:** `app/infrastructure/ffmpeg_utils.py` → `create_segment()`

Cada cena recebe velocidade aleatória (não todas iguais):
```python
# Velocidade variada: 0.002 a 0.008
actual_speed = random.uniform(0.002, 0.008)
```

### Pipeline atualizado (filter chain por segmento):
```
scale 2x → zoompan (easing) → vignette animado → eq (brilho dinâmico) → format yuv420p
```

### Arquivos a modificar:
1. **`app/infrastructure/ffmpeg_utils.py`** — `create_segment()`: easing expressions, vignette, eq, focal points
2. **`app/core/constants.py`** — Novos estilos de zoom com easing
3. **`tests/unit/test_video_assembler_srt.py`** — Atualizar testes

### Validação:
1. Unit tests passam
2. Docker rebuild
3. Teste real via POST /jobs com script que tem 8+ cenas
4. Comparar visualmente com vídeo anterior
