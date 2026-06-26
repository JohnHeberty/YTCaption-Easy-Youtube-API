# INVESTIGATE.md — Estado Actual

**Data:** 2026-06-24
**Pipeline:** `_run_nsfw_test()` (v17 PRODUCTION)

> **Lições aprendidas:** Ver `LIÇÕES.md`

---

## Estado Actual do Pipeline (v17)

```
body_mask → dilate 3.5% → morphOpen 3px → GaussianBlur 3px → threshold > 127
→ morphClose 5px → morphClose vertical 1x7 → inpaint_mask (binary)
→ SE8 (erode=-3, strength=0.65, field=0.85)
→ paste binário → GaussianBlur 7px blend → head_adjusted force
```

## GPU Memory
- Quando SE8 falha 3x com CUDA assertion → `nvidia-smi` verificar memória
- `docker exec image-engine pkill -f python` limpa GPU
- RTX 3090: 24GB VRAM, padrão 97% cheio após uso
