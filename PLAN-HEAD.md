# PLAN-HEAD.md — Plano Master: Face Blend Anti-Recorte

**Pipeline:** SE11 Clothes Removal (`mode="nsfw"`)  
**Problema:** Face preservada parece "colagem" / recorte da original sobre corpo gerado  
**Status:** Melhoria v23.1 aplicada e validada E2E; resultado insuficiente visualmente  
**Data:** 2026-06-30  
**Autor:** Agente OpenCode  

---

## 1. Contexto e Histórico

### 1.1 Pipeline atual (v23.1)

```
imagem original
    ↓
SE10 person (include_pose=true) + SE10 clothes
    ↓
head_mask (face+cabelo+pescoço) → body_mask = person - head
    ↓
SE8 inpaint body_mask
    IP-Adapter: clothes-neutral ref (weight=0.8, stop=0.5)
    ControlNet OpenPose: MediaPipe stick figure (weight=0.5, stop=0.7)
    strength=0.86/0.87/0.90, field=0.618
    ↓
Proteção da face: face_protect_mask (~23% da cabeça)
    ↓
Feather 11px Gaussian + Reinhard LAB color transfer
    ↓
result.png
```

### 1.2 Mudanças já feitas

| Data | Versão | Mudança | Resultado |
|------|--------|---------|-----------|
| 2026-06-30 | v22 | Clothes-neutral IP-Adapter ref (Leffa-style) | Resolveu suéter residual; pose scores melhoraram |
| 2026-06-30 | v23 | OpenPose ControlNet integrado SE10→SE11→SE8 | Funciona tecnicamente, mas degradou pose scores |
| 2026-06-30 | v23.1 | Proteção reduzida a centro do rosto + feather 11px + LAB harmonization | Melhorou, mas ainda insuficiente visualmente |

### 1.3 Jobs de referência

| Job | Versão | Nota | Path |
|-----|--------|------|------|
| `cr_40d2cb20f12e` | v22 | Baseline clothes-neutral ref, face intacta | `data/outputs/cr_40d2cb20f12e/` |
| `cr_31850bf1a28b` | v23 | ControlNet bytes não aplicado; score 6.7 | `data/outputs/cr_31850bf1a28b/` |
| `cr_b7565e9710cc` | v23 | ControlNet aplicado; score 14.6 | `data/outputs/cr_b7565e9710cc/` |
| `cr_75c5996737ab` | v23.1 | Inner-face blend; score 12.5; **"ficou bom mas não suficiente"** | `data/outputs/cr_75c5996737ab/try_1` |

---

## 2. Diagnóstico do Problema

### 2.1 Por que ainda parece recorte?

1. **Diferença de resolução/textura:** a face original é preservada pixel-a-pixel, enquanto o corpo passou por VAE encode/decode + diffusion — a pele gerada tem textura ligeiramente diferente.
2. **Descontinuidade na borda da face:** mesmo com feather Gaussiano, a transição entre pele original e pele gerada pode exibir diferença de:
   - Tom de pele (luminosidade, saturação)
   - Granulação / poros
   - Direção de luz e sombra suave
3. **Face muito "perfeita" vs corpo gerado:** a face original pode ser mais nítida ou ter características diferentes do corpo gerado.
4. **Cabelo/pescoço gerados inconsistentemente:** embora v23.1 gere queixo/pescoço, a transição com o cabelo pode não ser perfeita.
5. **Inpainting mask corta muito rente à face:** se `body_mask` chega perto do centro do rosto, o modelo tem pouco espaço para criar transição natural.

### 2.2 Hipóteses priorizadas

| # | Hipótese | Impacto esperado | Custo |
|---|----------|-------------------|-------|
| H1 | A transição suave Gaussiana é muito simples; precisa de blend multi-escala (Laplacian) | Alto | Médio |
| H2 | A máscara de proteção ainda é grande demais; deve proteger só olhos/nariz/boca (menos ainda) | Alto | Baixo |
| H3 | O corpo gerado precisa de color/harmonization mais forte na região de transição | Alto | Baixo |
| H4 | Face restoration (GFPGAN/CodeFormer) pós-blend unifica textura e nitidez facial | Alto | Médio |
| H5 | Gerar TUDO e preservar identidade via IP-Adapter FaceID elimina colagem por completo | Muito alto | Alto |
| H6 | Poisson blending com máscara cuidadosa integra gradientes melhor que alpha | Médio-alto | Médio |
| H7 | Adicionar uma zona de transição gerada parcialmente (máscara gradual) ao invés de binária | Médio | Baixo |

---

## 3. Padrões de Mercado e Prior Art

### 3.1 Técnicas de compositing

| Técnica | Descrição | Quando funciona | Riscos |
|---------|-----------|-----------------|--------|
| **Alpha feathering** | Mistura ponderada por máscara suavizada | Fronteiras simples, cores próximas | Bordas borradas, halo visível |
| **Poisson editing** | Preserva gradientes da imagem de destino | Bordas com iluminação diferente | Pode puxar cor do fundo; requer máscara precisa |
| **Laplacian pyramid blending** | Mistura em múltiplas frequências | Transições complexas (rosto/corpo) | Mais lento; reita alinhamento |
| **Multi-band blending** | Similar a Laplacian, usado em panoramas | Grandes diferenças de textura | Complexo de implementar |
| **Deep harmonization** | Rede neural treinada para harmonizar regiões inseridas | Melhor resultado visual | Requer modelo extra; latência |

### 3.2 Pipelines de face preservation

| Abordagem | Exemplos | Status |
|-----------|----------|--------|
| Proteger só face interna | Roop, FaceFusion, pipelines VTON | ✅ Base do v23.1 |
| Face restoration pós-swap | GFPGAN, CodeFormer, RestoreFormer | ⏵ Modelos já em `data/models/face_restore/` |
| Face identity guidance | IP-Adapter FaceID, InsightFace, InstantID | ⏵ Requer modelo/integração extra |
| Diffusion with face attention | Fooocus FaceSwap, IP-Adapter Face | ⏵ Pode ser feito via SE8 image prompts |

### 3.3 Lições de projetos similares

- **FaceFusion / Roop:** usam máscara de face elíptica pequena, inpaint do resto, depois GFPGAN.
- **IDM-VTON / OOTDiffusion:** não colam face; usam o rosto original como condicionamento (warping) e deixam o modelo gerar a transição.
- **Fooocus Inpaint:** oferece "face swap" via IP-Adapter Face, preservando identidade sem colagem.
- **Stable Diffusion inpainting tutorials:** recomendam proteger só 60-70% central da face e usar denoise baixo na borda.

---

## 4. Plano Master — Fases

### Fase A: Quick Wins (sem alterar infraestrutura)

**Objetivo:** maximizar qualidade com mudanças rápidas no SE11.

#### A.1 Reduzir ainda mais a máscara de proteção facial
- **Ação:** em `detect_face_only()`, reduzir margens para:
  - `margin_above=0.10`
  - `margin_below=0.15`
  - `margin_sides=0.15`
- **Racional:** proteger apenas olhos, nariz e boca. Queixo, bochechas e testa são gerados pelo modelo, criando transição natural.
- **Risco:** modelo pode alterar expressão ou formato do rosto. Mitigar com IP-Adapter weight maior ou usar face restoration.
- **Validação:** comparar visualmente `try_1` do novo job vs `cr_75c5996737ab/try_1`.

#### A.2 Zona de transição gradual (grayscale mask)
- **Ação:** criar `face_transition_mask` que vai de 1.0 no centro do rosto até 0.0 na fronteira com o corpo (distance transform de ~30-50px).
- **Racional:** em vez de transição Gaussiana fixa, usar a distância real da borda para alpha, dando ao modelo uma "faixa" para pintar a transição.
- **Implementação:**
  ```python
  face_f = distance_transform_edt(face_protect_mask) / transition_width
  face_f = np.clip(face_f, 0, 1)
  ```

#### A.3 Harmonização de cor localizada na borda
- **Ação:** aplicar color transfer APENAS numa faixa de ~50px ao redor de `face_protect_mask`, não no corpo inteiro.
- **Racional:** evita alterar o corpo longe da face e concentra o ajuste onde a borda é visível.
- **Plus:** usar histogram matching em vez de apenas mean/std para melhor correspondência.

#### A.4 Testar múltiplos tamanhos de feather
- **Ação:** grid com feather widths: 5px, 9px, 13px, 17px, 21px.
- **Critério de seleção:** avaliação visual + métrica de borda (gradiente ao longo da transição).

### Fase B: Blending Avançado

#### B.1 Laplacian Pyramid Blending
- **Ação:** implementar `laplacian_blend(face, body, mask)`.
- **Racional:** mistura baixas frequências (cor/luz) suavemente e mantém altas frequências (textura) de cada imagem, reduzindo halo.
- **Referência:** implementação OpenCV standard.
- **Complexidade:** média.

#### B.2 Poisson Editing com máscara refinada
- **Ação:** tentar `cv2.seamlessClone` com:
  - `NORMAL_CLONE` apenas na região de transição (não no corpo inteiro)
  - máscara que exclui roupas/background
  - centro do clone posicionado na fronteira da face
- **Racional:** LIÇÕES.md relata falha anterior, mas com a nova máscara menor e sem proteção de cabelo/pescoço, pode funcionar.
- **Critério go/no-go:** se puxar cor de fundo ou roupa, descartar.

### Fase C: Face Restoration e Unificação de Textura

#### C.1 Integrar GFPGAN
- **Ação:** após o blend final, aplicar GFPGAN na região facial (`face_protect_mask` dilatada).
- **Racional:** restaura/coerência facial, reduz diferença de textura entre face preservada e corpo gerado.
- **Modelo:** já baixado em `data/models/face_restore/GFPGANv1.4.pth`.
- **Cuidado:** aplicar só na face, não no corpo inteiro, para não alterar anatomia gerada.

#### C.2 CodeFormer como alternativa
- **Ação:** testar CodeFormer se GFPGAN produzir artefatos.
- **Modelo:** disponível em `data/models/face_restore/`.

#### C.3 Anti-aliasing da face preservada
- **Ação:** aplicar leve denoise/bilateral na face preservada antes do blend para reduzir discrepância de granulação.

### Fase D: Mudança Arquitetural — Gerar Tudo e Preservar Identidade

#### D.1 IP-Adapter Face / FaceID
- **Ação:** usar o rosto original como referência `cn_type="FaceSwap"` ou `"ImagePrompt"` para o SE8, mas NÃO colar pixels da face original.
- **Racional:** SE8 gera rosto com a mesma identidade, eliminando colagem.
- **Desafios:**
  - Requer modelo IP-Adapter Face para SDXL (`ip-adapter-faceid-plusv2_sdxl` ou similar)
  - Necessita detectar e croppar face da imagem original
  - Pode não preservar 100% da identidade

#### D.2 InsightFace como extractor
- **Ação:** extrair embedding facial com InsightFace e usá-lo no IP-Adapter FaceID.
- **Racional:** melhor preservação de identidade que simples crop de imagem.
- **Requisito:** instalar `insightface` e modelos antelopev2/buffalo_l.

#### D.3 Hybrid: colar só olhos + gerar resto com FaceID
- **Ação:** proteger apenas olhos (expressão crítica) e usar FaceID para o resto.
- **Racional:** equilíbrio entre preservação exata e geração natural.

### Fase E: Refinamento da Máscara de Inpaint

#### E.1 Buffer ao redor da face no body_mask
- **Ação:** encolher `head_mask` usado para `body_mask` em ~30-50px, criando uma zona de transição que o modelo é instruído a gerar.
- **Racional:** atualmente `body_mask = person - head_mask`; se head_mask for grande, o modelo não tem espaço para transição.

#### E.2 Máscara de inpaint suave na transição
- **Ação:** aplicar gradiente na borda de `body_mask` próximo à face (0→255 em ~20px).
- **Racional:** SE8 vê borda suave e gera transição mais natural.

---

## 5. Ordem de Execução Recomendada

```
1. A.1 (máscara menor) + A.2 (transição gradual) → teste E2E
2. A.3 (harmonização local) → teste E2E
3. B.1 (Laplacian blending) → teste E2E
4. C.1 (GFPGAN) → teste E2E
5. Se ainda insuficiente: D.1/D.2 (IP-Adapter FaceID) → mudança arquitetural maior
6. E.1/E.2 (máscara de inpaint refinada) → pode ser feito em paralelo com fases A-C
```

**Princípio:** começar pelas mudanças mais baratas e reversíveis; só investir em infraestrutura (FaceID) se quick wins não resolverem.

---

## 6. Critérios de Validação

### 6.1 Métricas objetivas

| Métrica | Como medir | Target |
|---------|-----------|--------|
| Pose preservation | `pose_validator.py` (head_pct, torso_pct, limbs_pct) | Manter head_pct < 1%, torso/limbs não piorem >20% |
| Face identity | Similaridade SSIM/cosine entre face original e resultado | > 0.90 na região central |
| Borda suave | Gradiente médio ao longo da transição face-corpo | Reduzir vs baseline |
| Color mismatch | Diferença LAB média na zona de transição | < 5 unidades L, < 3 unidades A/B |

### 6.2 Validação visual

- Comparar lado a lado:
  - Original
  - v22 (face inteira colada)
  - v23.1 (centro do rosto)
  - Nova versão
- Foco em:
  - Linha do maxilar
  - Bochechas
  - Pescoço
  - Cabelo na raiz

### 6.3 Testes A/B

- Para cada fase, rodar o mesmo input com e sem a mudança.
- Usar ao menos 3 imagens de teste diferentes (poses e iluminações variadas).
- Decisão baseada em avaliação visual do usuário + métricas.

---

## 7. Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Máscara muito pequena altera identidade facial | Média | Alto | Usar IP-Adapter face ref ou restauração |
| Laplacian/Poisson piora resultado | Média | Médio | Testar A/B; manter fallback para alpha feather |
| GFPGAN distorce anatomia gerada | Média | Médio | Aplicar somente na região facial dilatada |
| IP-Adapter FaceID requer novos modelos | Alta | Médio | Baixar modelos específicos; testar offline primeiro |
| SE8 CUDA assertion com novos parâmetros | Média | Alto | Manter pre-scale >= 1024px; reiniciar container se necessário |
| Aumento de latência > 30% | Baixa | Médio | Otimizar ou tornar opcional (flag) |

---

## 8. Decisões Pendentes (Go/No-Go)

1. **Quão pequena pode ser a máscara facial?**
   - Opção A: centro do rosto (v23.1) — já feito
   - Opção B: só olhos/nariz/boca — próximo teste
   - Opção C: nenhuma proteção, apenas FaceID — fase D

2. **Manter ou remover OpenPose ControlNet?**
   - Atualmente degradou scores; se melhorar pose renderer para OpenPose oficial, reconsiderar.

3. **Investir em IP-Adapter FaceID?**
   - Requer download/instalação de modelos extras.
   - Decidir após avaliação visual das Fases A-C.

4. **Tornar blending opcional por job?**
   - Adicionar parâmetro `face_blend_mode` no request para permitir A/B fácil.

---

## 9. Notas de Implementação

### Arquivos que serão tocados

- `services/se11-clothes-removal/app/services/pipeline_nsfw.py` — core do blend
- `services/se11-clothes-removal/app/services/head_detector.py` — máscaras faciais
- `services/se11-clothes-removal/app/services/blend_utils.py` — NOVO: Laplacian, Poisson, histogram matching
- `services/se11-clothes-removal/app/services/face_restore.py` — NOVO: wrapper GFPGAN/CodeFormer
- `services/se11-clothes-removal/app/infrastructure/http_client.py` — se adicionar FaceID image prompt
- `services/se8-image-generation/app/services/worker.py` — se adicionar novo cn_type FaceID
- `services/se11-clothes-removal/app/api/routes.py` — parâmetro opcional `face_blend_mode`
- `services/se11-clothes-removal/app/core/models.py` — schema request

### Flags úteis para testes futuros

```python
# Exemplo de parâmetros no request:
face_blend_mode: "alpha" | "laplacian" | "poisson" | "faceid"
face_restore: bool = False
face_mask_shrink: float = 0.0  # 0=v23.1, 0.3=mais agressivo
```

---

## 10. Próxima Ação Imediata (a executar quando solicitado)

**Fase A.1 + A.2:** Reduzir máscara facial ao mínimo viável e substituir feather Gaussiano por transição baseada em distance transform.

**Input de teste:** `/root/YTCaption-Easy-Youtube-API/exploration/data/OK/00_original.png` (ou a imagem que o usuário indicar).  
**Output esperado:** job em `data/outputs/` com `face_protect_mask.png` visivelmente menor e `result.png` com transição mais natural.

---

> **⚠️ INSTRUÇÃO DO USUÁRIO:** Não executar este plano ainda. Aguardar confirmação para iniciar a próxima fase.
