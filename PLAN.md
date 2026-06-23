# PLAN.md — Pipeline NSFW 3-Camadas: Roupas → Pele Preservando Pessoa

**Data:** 2026-06-23  
**Status:** Planejamento — Pronto para implementar  
**Objetivo:** Remoção 100% de roupa com preservação ABSOLUTA de rosto, cabeça, cabelo e fundo

---

## Problema Atual

O `pipe_nsfw_subtract` atual (Face=1.000, Bot=72.4%) funciona bem mas:
- Não detecta roupa separadamente — usa pessoa-rosto como máscara
- O SE8 pode alucinar em áreas que não são roupa (pescoço, queixo)
- Não separa fundo do corpo — pode editar onde não deve

## Solução: Pipeline 3-Camadas

### Diagrama

```
IMAGEM ORIGINAL
    │
    ▼
┌───────────────────────────────────┐
│  CAMADA 1: PRESERVADA            │
│  (NUNCA tocada pelo SE8)         │
│  • Rosto + cabeça + cabelo       │
│  • Fundo/background              │
│  • Braços, mãos, pernas (pele)  │
└───────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────┐
│  CAMADA 2: CORPO ISOLADO         │
│  Pessoa - rosto - fundo = corpo  │
│  Máscara binária do corpo        │
└───────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────┐
│  CAMADA 3: DETECÇÃO + INPAINT    │
│  1. Florence-2 detecta ROUPA     │
│     dentro do corpo isolado      │
│  2. Máscara = roupa AND corpo    │
│  3. SE8 LUSTIFY NSFW inpaint    │
│  4. Gera pele SÓ onde tem roupa  │
└───────────────────────────────────┘
    │
    ▼
COMPOSIÇÃO FINAL:
  Camada 1 (original: rosto+cabeça+fundo)
  + Camada 3 (corpo com pele onde tinha roupa)
  = Imagem final NSFW
```

### Etapas Detalhadas

#### Etapa 1: Detectar pessoa
```
SE10 person mode → person_mask (máscara de corpo inteiro)
```
- Input: imagem original
- Output: máscara binária (0/255) da pessoa

#### Etapa 2: Detectar rosto + cabeça
```
face_mask = person_mask[top 50% da bbox da pessoa]
```
- Cortar top 50% da bounding box da pessoa (incluir cabelo e cabeça)
- Output: máscara do rosto+cabeça

#### Etapa 3: Calcular corpo isolado
```
body_mask = person_mask AND NOT face_mask
```
- O que SOBRA = corpo (torso, pescoço, braços, ombros)
- Output: máscara binária do corpo

#### Etapa 4: Detectar roupa dentro do corpo
```
SE10 clothes mode → clothes_mask
effective_mask = clothes_mask AND body_mask
```
- Florence-2 detecta roupa na imagem inteira
- Interseção com body_mask = SÓ roupa dentro do corpo
- Output: máscara EXATA da roupa

#### Etapa 5: Inpainting NSFW
```
SE8 LUSTIFY NSFW inpaint com effective_mask
denoise_pass1 = 0.75 (remoção principal)
denoise_pass2 = 0.45 (refinamento)
```
- LoRA: NsfwPovAllInOne 0.5
- Prompt: "natural skin texture matching surrounding skin"
- Output: imagem com pele onde tinha roupa

#### Etapa 6: Composição final
```
result = original
result[effective_mask] = inpainted[effective_mask]
```
- Máscara dura (sem Gaussian blur) no rosto+cabeça+fundo
- Gaussian blur (5px) apenas nas bordas da effective_mask
- Forçar face region = exatamente original
- Output: imagem final

#### Etapa 7: Pós-processamento
```
1. HSV color transfer → cor da pele consistente
2. Morfologia abertura → remove artefatos pequenos
3. Morfologia fechamento → preenche buracos na máscara
4. Bilateral filter nas bordas → suaviza transição
```

---

## Diferenças vs pipe_nsfw_subtract atual

| Aspecto | pipe_nsfw_subtract (atual) | **Pipe 3-Camadas (novo)** |
|---------|--------------------------|--------------------------|
| Máscara de roupa | pessoa - rosto | **(roupa AND corpo) = roupa EXATA** |
| Detecção de roupa | NÃO usa Florence-2 | **USA Florence-2 dentro do corpo** |
| Rosto tocado pelo SE8 | ❌ Pode acontecer | **✅ NUNCA (camada 1 isolada)** |
| Fundo tocado | ❌ Pode acontecer | **✅ NUNCA (camada 1 isolada)** |
| Precisão da máscara | Média | **ALTA (roupa + corpo intersecção)** |
| Alucinação do modelo | Possível | **Mínima (corpo isolado)** |

---

## Métricas Esperadas

| Métrica | Atual (v3) | **Meta 3-Camadas** |
|---------|-----------|-------------------|
| Face SSIM | 1.000 | **1.000** |
| Face diff | 0.0 | **0.0** |
| BG diff | 0.0 | **0.0** |
| Torso | 34.2% | **> 40%** |
| Bot | 72.4% | **> 75%** |
| Neck/chin artifacts | ⚠️ Possível | **0.0 (isolado)** |

---

## Arquivos a modificar

| Arquivo | Mudança |
|---------|---------|
| `pipeline.py` | Nova função `_run_pipe_nsfw_3layers()` |
| `models.py` | Adicionar `mode="pipe_3layers"` |
| `http_client.py` | Sem mudança (SE10+SE8 já suportam) |

---

## Ordem de implementação

1. Criar `_run_pipe_nsfw_3layers()` no pipeline.py
2. Registrar mode `pipe_3layers` no models.py
3. Testar com Test.png
4. Comparar com pipe_nsfw_subtract v3
5. Ajustar parâmetros (thresholds, denoise, face cutoff)
6. Commit + push

---

## Risco

- **BAIXO** — usa componentes existentes (SE10, SE8, Florence-2)
- **MÉDIO** — pode detectar roupa fora do corpo (filtrar com body_mask resolve)
- **MÉDIO** — 3 chamadas ao SE10 (person + clothes + possibly face) — pode bater CUDA assertion
