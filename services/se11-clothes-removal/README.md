# SE11 — Clothes Removal API

Serviço profissional de remoção de vestimentas via IA, com detecção de objetos (SE10), inpainting (SE8) e validação de pose.

---

## ⚠️ Política de Uso

> **ANTES de usar este serviço, leia e aceite a [Política de Uso](./POLITICA-USO.md).**
>
> O SE11 é destinado **EXCLUSIVAMENTE** a imagens geradas por inteligência artificial (AI-generated images). O uso com fotos de pessoas reais é **ESTRITAMENTE PROIBIDO**.

---

## Visão Geral

```
Imagem → SE10 (detecção) → SE8 (inpainting) → Pose Validation → Resultado
```

| Componente | Função |
|------------|--------|
| SE10 (port 8010) | Detecção de objetos — GroundingDINO / Florence-2 |
| SE8 (port 8008) | Inpainting — Fooocus + JuggernautXL + LoRAs NSFW |
| SE11 (port 8011) | Orchestration — pipeline, retry, validação, debug grid |

## Quick Start

### Docker

```bash
docker restart se11-clothes-removal
```

### Criar Job

```bash
# Base64 da imagem
IMG_B64=$(base64 -w0 imagem.png)

curl -X POST http://localhost:8011/jobs \
  -H "X-API-Key: se11-test-key-2026" \
  -H "Content-Type: application/json" \
  -d "{\"image\": \"$IMG_B64\", \"mode\": \"nsfw\"}"
```

### Verificar Status

```bash
curl http://localhost:8011/jobs/{job_id} \
  -H "X-API-Key: se11-test-key-2026"
```

### Download Resultado

```bash
curl -O http://localhost:8011/jobs/{job_id}/download \
  -H "X-API-Key: se11-test-key-2026"
```

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/` | Informações do serviço |
| `POST` | `/jobs` | Criar job de remoção (201) |
| `GET` | `/jobs` | Listar jobs (paginação) |
| `GET` | `/jobs/{job_id}` | Status do job |
| `DELETE` | `/jobs/{job_id}` | Deletar job |
| `GET` | `/jobs/{job_id}/download` | Download resultado PNG |
| `GET` | `/health` | Health check |
| `GET` | `/health/deep` | Health com upstream (SE10, SE8) |
| `GET` | `/admin/stats` | Estatísticas |
| `POST` | `/admin/cleanup` | Limpeza de jobs |

## Modos de Processamento

| Modo | Descrição | Indicado para |
|------|-----------|---------------|
| `clothes` | Remoção padrão de roupas detectadas | Uso geral |
| `person` | Remoção de torso (cabeça preservada) | Fashion design |
| `nsfw` | Pipeline NSFW produção (retry + validação) | Resultado máxima qualidade |
| `nsfw_test` | Alias para nsfw | Testes e debug |

### Request Body

```json
{
  "image": "base64 ou URL",
  "mode": "nsfw",
  "classes": "spaghetti strap, camisole, top",
  "prompt": "bare skin, realistic texture",
  "negative_prompt": "deformed, blurry",
  "box_threshold": 0.10,
  "text_threshold": 0.10,
  "inpaint_strength": 1.0,
  "per_garment": false,
  "webhook_url": "https://example.com/webhook",
  "detector": "groundingdino"
}
```

## Modo NSFW (Produção)

O pipeline de produção (`mode="nsfw"`) executa:

1. **SE10 Person Detection** — detecção da pessoa
2. **Head Protection** — haarcascade adaptativa + silhueta
3. **SE10 Clothes Detection** — detecção de vestimentas
4. **Mask Preparation** — dilatação adaptativa + morfologia
5. **SE8 Inpainting** — 3 tentativas com parâmetros progressivos
6. **Pose Validation** — MediaPipe Pose (33 landmarks)
7. **Best Selection** — seleciona tentativa com menor desvio

### Output por Job

```
data/outputs/{job_id}/
├── 00_original.png
├── 01_person.png
├── 02_head.png
├── 03_body.png
├── 04_clothes.png
├── 05_exposed_skin.png
├── 06_inpaint_mask.png
├── 07_head_adjusted.png
├── {job_id}_debug_grid.png     ← Grid 3x3 com todos os passos
├── {job_id}_result.png         ← Resultado final
├── attempts.json               ← Metadados das 3 tentativas
└── try_1/                      ← Detalhes por tentativa
    ├── result.png
    ├── inpaint_mask.png
    ├── head_adjusted.png
    └── metadata.json
```

## Debug Grid

Cada job NSFW gera um `{job_id}_debug_grid.png` com 9 painéis:

| # | Painel | Descrição |
|---|--------|-----------|
| 1 | Original | Imagem de entrada |
| 2 | Person (SE10) | Máscara de pessoa |
| 3 | Head (haarcascade) | Cabeça detectada adaptativamente |
| 4 | Body = Person - Head | Corpo sem cabeça |
| 5 | Clothes (Florence-2) | Detecção de roupa |
| 6 | Exposed Skin | Pele exposta (referência) |
| 7 | Inpaint Mask | Máscara enviada ao SE8 |
| 8 | Head Protected | Região protegida final |
| 9 | Result | Resultado final |

## Arquitetura

```
┌──────────┐     ┌──────────┐     ┌──────────────┐
│  SE10    │────▶│  SE11    │────▶│  SE8         │
│  (8010)  │     │  (8011)  │     │  (8008)      │
│  Detecção│     │  Orchest.│     │  Inpainting  │
└──────────┘     └──────────┘     └──────────────┘
                        │
                        ▼
               ┌──────────────┐
               │  Pose        │
               │  Validation  │
               │  (MediaPipe) │
               └──────────────┘
```

## Variáveis de Ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `API_KEY` | — | Chave de autenticação |
| `SE10_URL` | `http://localhost:8010` | URL do SE10 |
| `SE8_URL` | `http://localhost:8008` | URL do SE8 |
| `OUTPUT_DIR` | `./data/outputs` | Diretório de saída |
| `REDIS_URL` | — | URL do Redis |

## Configuração

Ver `.env.example` para todas as variáveis disponíveis.

## Documentação

| Documento | Descrição |
|-----------|-----------|
| [POLITICA-USO.md](./POLITICA-USO.md) | Política de uso obrigatória |
| [docs/INVESTIGATION/](./docs/INVESTIGATION/) | Pesquisa técnica |
| [docs/PLANS/](./docs/PLANS/) | Planos e specs |

## Licença

Uso interno. Consulte a [Política de Uso](./POLITICA-USO.md) para termos completos.

---

*Última atualização: 2026-06-27*
