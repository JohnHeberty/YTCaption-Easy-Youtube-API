# PLAN-2.md — Detecção Adaptativa de Cabeça (Substituir 40% Fixo)

**Data:** 2026-06-23
**Status:** PENDENTE
**Objetivo:** Substituir cutoff fixo de 40% por detecção facial adaptativa

---

## Problema Actual

O pipeline usa **top 40% da bounding box da pessoa** para definir a região da cabeça que deve ser preservada. Isto é uma heurística que só funciona bem para pessoas em pé em close.

### Cenários onde o 40% fixo falha

| Cenário | % real da cabeça | 40% fixo | Resultado |
|---------|-----------------|----------|-----------|
| Close-up em pé | ~35-40% | ✅ | Funciona |
| Pessoa longe (full body) | ~15-20% | ❌ | 40% inclui torso → inpaint não chega ao peito |
| Pessoa sentada | ~45-50% | ❌ | 40% corta testa/cabelo |
| Pose inclinada | Variável | ❌ |_bbox não representa cabeça_ |
| Mais de 1 pessoa | Variável | ❌ | Só uma é protegida |

### Código actual (3 locais)

| Local | Linha | Cutoff |
|-------|-------|--------|
| `_get_torso_mask()` | ~309 | `top 35%` |
| `_run_progressive()` | ~832 | `top 30%` |
| `_run_pipe_nsfw_3layers_max()` | ~1955 | `top 40%` |

---

## Solução: Haarcascade + Florence-2 Fallback

### Abordagem 3 passos

#### Passo 1: OpenCV Haarcascade (~10ms, CPU, zero dependências novas)
```python
import cv2

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)
gray = cv2.cvtColor(orig_img, cv2.COLOR_BGR2GRAY)
faces = face_cascade.detectMultiScale(
    gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
)
# faces = [(x, y, w, h), ...]
```

**Vantagens:**
- Já está no container (bundled com OpenCV)
- ~10ms de latência
- Zero GPU necessária
- Funciona para rostos frontais

**Limitações:**
- Falha para rostos de perfil ou muito pequenos
- Não detecta cabelo

#### Passo 2: Head region adaptativa
```python
if len(faces) > 0:
    # Usar maior face detectada
    face = max(faces, key=lambda f: f[2] * f[3])
    fx, fy, fw, fh = face

    # Head = face + margem para cabelo (50% acima) + pescoço (30% abaixo)
    margin_above = int(fh * 0.5)
    margin_below = int(fh * 0.3)
    head_top = max(0, fy - margin_above)
    head_bottom = fy + fh + margin_below

    # Criar head_mask baseado na face detectada
    head_mask = _np.zeros_like(person_binary)
    head_mask[head_top:head_bottom, fx:fx+fw] = 255
    head_mask = _cv2.bitwise_and(head_mask, person_binary)  # limitar à pessoa
    head_mask = _cv2.dilate(head_mask, kernel_15px, iterations=2)
else:
    # Fallback: 35% (comportamento actual)
    h = person_bbox_h
    head_cutoff_y = person_bbox_y + int(0.35 * h)
    head_mask = person_binary.copy()
    head_mask[head_cutoff_y:, :] = 0
    head_mask = _cv2.dilate(head_mask, kernel_15px, iterations=2)
    head_mask = _cv2.bitwise_and(head_mask, person_binary)
```

#### Passo 3 (Opcional): Florence-2 fallback
Se haarcascade não detecta nenhuma face (perfil, oclusão, imagem pequena):
```python
if len(faces) == 0:
    # Chamar SE10 com classes de face
    face_result = await se10.segment(
        image_bytes=image_bytes,
        filename=f"{job.job_id}_face.jpg",
        classes="face, head, hair",
        mode="person",
        detector="florence2",
    )
    face_objects = face_result.get("objects", [])
    if face_objects:
        # Usar bounding box da face detectada por Florence-2
        ...
```

---

## Arquivos a Modificar

| Arquivo | Locais | Mudanças |
|---------|--------|----------|
| `pipeline.py` | `_run_pipe_nsfw_3layers_max()` ~1955 | Substituir cutoff 40% por haarcascade |
| `pipeline.py` | `_get_torso_mask()` ~309 | Substituir cutoff 35% por haarcascade |
| `pipeline.py` | `_run_progressive()` ~832 | Substituir cutoff 30% por haarcascade |

### Função auxiliar a criar
```python
def _detect_head_mask(
    orig_img: _np.ndarray,
    person_binary: _np.ndarray,
    person_bbox: tuple[int, int, int, int],
    fallback_pct: float = 0.35,
) -> _np.ndarray:
    """Detect face and create adaptive head mask.

    Uses OpenCV Haarcascade for fast face detection.
    Falls back to fixed percentage if no face found.
    """
    ...
```

---

## Vantagens

| Cenário | 40% fixo | Adaptativo |
|---------|----------|------------|
| Close-up em pé | ✅ | ✅ |
| Pessoa longe | ❌ 40% enorme | ✅ detecta rosto pequeno |
| Pessoa sentada | ❌ 40% corta testa | ✅ adapta à pose |
| Pose inclinada | ❌ bbox não representa | ✅ segue o rosto |
| Multi-face | ❌ só uma protegida | ✅ todas protegidas |

---

## Riscos

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Haarcascade falha para perfil | Rosto não detectado | Fallback 35% |
| Rosto muito pequeno (<30px) | Não detecta | minSize=(20, 20) + Florence-2 fallback |
| Múltiplas faces | Qual proteger? | Usar maior face |
| Margem incorreta | Cabelo/pescoço cortado | Margem generosa (50% acima, 30% abaixo) |

---

## Dependências

| Item | Necessário? | Status |
|------|------------|--------|
| OpenCV haarcascades | Sim | ✅ Já bundled com OpenCV |
| Novo pip install | Não | ✅ |
| Novo modelo ONNX | Não | ✅ (usa haarcascade, não DNN) |
| GPU extra | Não | ✅ CPU apenas |

---

## Teste

```bash
# Testar com diferentes imagens:
# 1. Close-up (Test.png) — deve detectar face grande
# 2. Full body — deve detectar face pequena
# 3. Pessoa sentada — deve adaptar cutoff
# Comparar debug masks 02_head_protected.png entre versões
```
