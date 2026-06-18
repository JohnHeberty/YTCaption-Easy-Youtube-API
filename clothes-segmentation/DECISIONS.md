# DECISIONS.md - Decisões do Projeto

## 27/05/2026 - Testes de Modelos de Segmentação

### Segformer (TF.js) — ❌ REPROVADO
- **Testado**: Docker + Puppeteer, CPU, ~5s por imagem
- **Resultado**: Detectou APENAS Face (rosto) e Hair (cabelo). ZERO classes de roupa detectadas em ambas as imagens de teste.
- **Classes esperadas**: Background, Hat, Hair, Sunglasses, Upper-clothes, Skirt, Pants, Dress, Belt, Left-shoe, Right-shoe, Face, Left-leg, Right-leg, Left-arm, Right-arm, Bag, Scarf (17 classes)
- **Classes detectadas**: Apenas Face e Hair
- **Conclusão**: Modelo foi treinado em dataset com poses/frontais diferentes. Não serve para imagens reais de pessoas. **DESCARTADO**.

### Grounded-SAM-2 — ✅ APROVADO
- **Testado**: CPU, SAM2 tiny (150MB) + GroundingDINO SwinT (694MB)
- **1-TEST.jpg** (homem, polo preta, jeans azul, cinto amarelo):
  - 67 detections iniciais → 67 after area filter → 28 after remove inside
  - Classes detectadas: pants, shoes, shirt, dress, hat, skirt, boots, handbag, blouse, sunglasses
  - 14 arquivos de output (máscaras individuais + comparison + detected_boxes)
- **2-TEST.jpg** (mulher, óculos, jaqueta):
  - 9 detections iniciais → 6 after remove inside
  - Classes detectadas: blouse, sunglasses, jacket, hat
  - 9 arquivos de output
- **Conclusão**: Detecta classes relevantes de roupa com boa precisão. Funciona em CPU. **CANDIDATO PRINCIPAL**.

### Virtual_Try_on_FashionGenAi (U2NET) — ❌ REPROVADO
- **Testado**: 27/05, CPU, checkpoint baixado do HuggingFace (177MB)
- **Resultado**: Detectou **100% background** — ZERO classes de roupa em ambas as imagens
- **Classes esperadas**: background, upper_clothes, lower_clothes, pants (4 classes apenas)
- **Conclusão**: Modelo treinado em dataset com poses/frontais diferentes. Mesmo problema do Segformer. **DESCARTADO**.
- **Nota**: Projeto faz virtual try-on (trocar roupa), não segmentação pura — propósito diferente do objetivo.

## Decisões Técnicas

| Decisão | Data | Motivo |
|---------|------|--------|
| NUNCA rodar servidor direto no terminal | 27/05 | `npm run start` travou o terminal 2 vezes. Usar Docker sempre. |
| Outputs salvos em C:\Temp, não OneDrive | 17/05 | OneDrive sync deleta arquivos em tempo real durante sync |
| Structura imgs/input (imutável) + imgs/output por projeto | 27/05 | Organização consistente entre projetos |
| Segformer descartado | 27/05 | Performance inaceitável — não detecta roupas |
| Virtual_Try_on descartado | 27/05 | U2NET detectou 100% background, propósito diferente (try-on, não segmentação) |
| **Grounded-SAM-2 como modelo PADRÃO** | 28/05 | Único modelo que detecta classes de roupa corretamente em ambas as imagens. Aprovado oficialmente pelo usuário. API construída em torno dele. |

## Modelo Oficial: Grounded-SAM-2

- **Status**: ✅ APROVADO E EM USO
- **Arquitetura**: GroundingDINO (detection) + SAM2 tiny (segmentation)
- **API**: `api/server.py` — FastAPI em `http://localhost:8001/segment`
- **Endpoint principal**: `POST /segment` (multipart/form-data com arquivo de imagem)
- **Response**: JSON com array de objetos (`class`, `confidence`, `bbox`) + base64 mask image
- **Performance CPU**: ~36s loading, inference por imagem em segundos
- **Classes detectadas no teste**: pants, shoes, shirt, dress, hat, skirt, boots, handbag, blouse, sunglasses, jacket
