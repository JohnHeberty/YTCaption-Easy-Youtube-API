# INVESTIGATE.md — Lições e Estado Actual

**Data:** 2026-06-24
**Pipeline:** `_run_nsfw_test()`

---

## Lições Aprendidas

### ❌ O que NÃO funciona
1. **5% dilation** — máscara demasiado grande → SE8 gera blobs cinza
2. **erode_or_dilate=-2** — demasiado agressivo nas áreas finas
3. **Máscara suave (0-255) para SE8** — SE8 espera binário (0 ou 255), suave confunde o modelo
4. **Reinhard LAB** — escurece a pele (canal L deslocado)
5. **inpaint_strength=0.55** — pouco criatividade → blobs
6. **inpaint_strength=0.80** — muita criatividade → muda pose
7. **GaussianBlur 15px na máscara** — expandia demais, comia área do rosto

### ✅ O que FUNCIONA (config actual)
1. **1% dilation** — cobertura suficiente, máscara apertada
2. **erode_or_dilate=-1** — mínimo de erosão, bordas limpas
3. **Máscara binária para SE8** — binário puro funciona
4. **Sem Reinhard LAB** — pele com tom correcto do SE8
5. **inpaint_strength=0.65** — pose preservada + boa qualidade
6. **morphOpen 3px + GaussianBlur 3px + morphClose 5px + vertical 1x7** — bordas suaves + sem gaps
7. **Prompts optimizados** — pose reforçada (positive + negative com weights)

### Parâmetros óptimos
| Parâmetro | Valor |
|-----------|-------|
| Dilation | 1% |
| erode_or_dilate | -1 |
| strength | 0.65 |
| field | 0.85 |
| morphOpen | 3px |
| GaussianBlur | 3px |
| morphClose | 5px ellipse + vertical 1x7 |
| Reinhard LAB | DESLIGADO |
| Bilateral filter | DESLIGADO |
| NsfwPov | 0.3 |
| add-detail-xl | 1.0 |

---

## Estado Actual do Pipeline

```
body_mask → dilate 1% → morphOpen 3px → GaussianBlur 3px → threshold
→ morphClose 5px → morphClose vertical 1x7 → inpaint_mask (binary)
→ SE8 (erode=-1, strength=0.65, field=0.85)
→ head_adjusted force → compositing direct paste
```

## GPU Memory
- Quando SE8 falha 3x com CUDA assertion → `nvidia-smi` verificar memória
- `docker exec image-engine pkill -f python` limpa GPU
- RTX 3090: 24GB VRAM, padrão 97% cheio após uso
