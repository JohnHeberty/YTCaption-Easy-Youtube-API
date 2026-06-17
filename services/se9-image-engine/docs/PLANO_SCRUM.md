# PLANO DE PROJETO SE9 IMAGE ENGINE

```
┌─────────────────────────────────────────────────────────┐
│  PROJETO: SE9 Image Engine                              │
│  VERSÃO: 1.0                                            │
│  SCRUM MASTER: Senior                                   │
│  DATA: 2026-06-17                                       │
│  DURAÇÃO ESTIMADA: 10 Sprints (20 dias úteis)           │
│  TIME: 1 Dev Senior (full-stack + ML)                   │
└─────────────────────────────────────────────────────────┘
```

## 1. VISÃO DO PRODUTO

**Problema:** FOOOCUS é um projeto open-source com 117K+ linhas, arquitetura monolítica, UI web desnecessária para API, estado global pesado, e dependências acopladas. Precisamos de um serviço de geração de imagens 100% funcional, limpo, mantível e integrável ao nosso monorepo.

**Solução:** SE9 Image Engine — reimplementation clean-room de todo o pipeline FOOOCUS como serviço FastAPI dedicado, com gerenciamento de memória GPU configurável (lazy/eager), API REST idêntica, e testes automatizados.

**Sucesso medido por:**
- 26/26 rotas funcionando (parity com FOOOCUS)
- Gerar imagem de texto → resultado correto via GPU
- Lazy load funcional (GPU→CPU fallback)
- ≥80% cobertura de testes
- Docker build < 5 minutos

## 2. ÉPICAS E USER STORIES

### ÉPICA 1: Infraestrutura Base (Sprints 1-2)

| ID | User Story | Prioridade | Estimativa |
|----|-----------|------------|------------|
| US-001 | Como dev, quero estrutura de diretórios SE9 separada do SE8 | P0 | 1 SP |
| US-002 | Como dev, quero configuração (.env, settings) herdando padrões do monorepo | P0 | 2 SP |
| US-003 | Como dev, quero detecção de GPU (CUDA/MPS/CPU) funcional | P0 | 3 SP |
| US-004 | Como dev, quero gerenciamento de VRAM (load/unload/evict) funcional | P0 | 5 SP |
| US-005 | Como dev, quero sistema de lazy/eager load configurável | P0 | 3 SP |
| US-006 | Como dev, quero Docker multi-stage build (API + Worker) | P0 | 2 SP |

**Definição de Pronto:** GPU detectada, VRAM gerenciada, container builda e roda.

### ÉPICA 2: Model Loading (Sprints 3-4)

| ID | User Story | Prioridade | Estimativa |
|----|-----------|------------|------------|
| US-007 | Como dev, quero carregar checkpoint SDXL base (UNet+CLIP+VAE) | P0 | 5 SP |
| US-008 | Como dev, quero carregar refiner SDXL (condicional) | P1 | 3 SP |
| US-009 | Como dev, quero aplicar LoRAs com pesos configuráveis | P0 | 5 SP |
| US-010 | Como dev, quero sistema de cache de modelo (evitar reload se filename = mesmo) | P1 | 2 SP |
| US-011 | Como dev, quero modelo de expansão GPT-2 (FooocusExpansion) | P1 | 3 SP |

**Definição de Pronto:** Modelo SDXL carrega na GPU, LoRAs aplicam, cache funciona.

### ÉPICA 3: Pipeline Core (Sprints 5-6)

| ID | User Story | Prioridade | Estimativa |
|----|-----------|------------|------------|
| US-012 | Como dev, quero CLIP encode de texto (positivo + negativo) | P0 | 3 SP |
| US-013 | Como dev, quero VAE encode (pixels → latents) | P0 | 3 SP |
| US-014 | Como dev, quero VAE decode (latents → pixels) | P0 | 3 SP |
| US-015 | Como dev, quero process_diffusion (sampler + scheduler) | P0 | 5 SP |
| US-016 | Como dev, quero aplicar estilos (Fooocus styles + expansion) | P1 | 3 SP |
| US-017 | Como dev, quero wildcards e array substitution | P2 | 1 SP |
| US-018 | Como dev, quero FreeU v2 patching | P2 | 1 SP |

**Definição de Pronto:** Pipeline gera imagem de texto→imagem em GPU.

### ÉPICA 4: Worker + Task Queue (Sprint 7)

| ID | User Story | Prioridade | Estimativa |
|----|-----------|------------|------------|
| US-019 | Como dev, quero task queue FIFO single-threaded (igual FOOOCUS) | P0 | 5 SP |
| US-020 | Como dev, quero AsyncTask com todos os 80+ campos | P0 | 3 SP |
| US-021 | Como dev, quero process_generate() completo (text-to-image path) | P0 | 8 SP |
| US-022 | Como dev, quero stop/interrupt funcional | P1 | 2 SP |
| US-023 | Como dev, quero webhook callback ao finalizar | P2 | 1 SP |

**Definição de Pronto:** Text-to-image completo via API, async job tracking.

### ÉPICA 5: API Routes (Sprint 8)

| ID | User Story | Prioridade | Estimativa |
|----|-----------|------------|------------|
| US-024 | Como dev, quero 26 rotas API com parity com FOOOCUS | P0 | 5 SP |
| US-025 | Como dev, quero V1 multipart routes (5 generation + stop + query) | P0 | 3 SP |
| US-026 | Como dev, quero V2 JSON routes (5 generation) | P0 | 3 SP |
| US-027 | Como dev, quero query/job-queue/job-history/outputs | P1 | 2 SP |
| US-028 | Como dev, quero engine routes (all-models, styles, clean_vram) | P1 | 2 SP |
| US-029 | Como dev, quero tools routes (describe-image, generate_mask) | P1 | 3 SP |
| US-030 | Como dev, quero file serving (GET /files/{date}/{name}) | P1 | 1 SP |
| US-031 | Como dev, quero health/ping/home endpoints | P1 | 1 SP |
| US-032 | Como dev, quero auth middleware (API key) | P1 | 1 SP |

**Definição de Pronto:** Todas as 26 rotas respondem corretamente.

### ÉPICA 6: Features Avançadas (Sprint 9)

| ID | User Story | Prioridade | Estimativa |
|----|-----------|------------|------------|
| US-033 | Como dev, quero image upscale/vary (V1 + V2) | P1 | 5 SP |
| US-034 | Como dev, quero image inpaint/outpaint | P1 | 5 SP |
| US-035 | Como dev, quero image prompt (ControlNet/IP-Adapter) | P1 | 5 SP |
| US-036 | Como dev, quero image enhance pipeline | P2 | 5 SP |
| US-037 | Como dev, quero performance modes (LCM/Lightning/Hyper-SD) | P2 | 3 SP |

**Definição de Pronto:** Todos os modos de geração funcionam.

### ÉPICA 7: Qualidade (Sprint 10)

| ID | User Story | Prioridade | Estimativa |
|----|-----------|------------|------------|
| US-038 | Como QA, quero ≥80% cobertura de testes | P0 | 5 SP |
| US-039 | Como QA, quero testes de integração (geração real na GPU) | P0 | 3 SP |
| US-040 | Como PM, quero documentação de API (OpenAPI) | P1 | 2 SP |
| US-041 | Como dev, quero deploy script e health check | P1 | 2 SP |

**Definição de Pronto:** Suite completa de testes, deploy automatizado.

## 3. VELOCIDADE E SPRINT PLANNING

| Sprint | Épica | Story Points | Foco |
|--------|-------|-------------|------|
| S1 | 1 (infra) | 13 | Estrutura, config, GPU detection |
| S2 | 1 (infra) | 10 | VRAM, lazy/eager, Docker |
| S3 | 2 (models) | 13 | SDXL base checkpoint loading |
| S4 | 2 (models) | 10 | Refiner, LoRAs, cache, expansion |
| S5 | 3 (pipeline) | 9 | CLIP encode, VAE encode/decode |
| S6 | 3 (pipeline) | 9 | Diffusion, styles, wildcards |
| S7 | 4 (worker) | 19 | Task queue, process_generate |
| S8 | 5 (API) | 21 | 26 rotas, auth |
| S9 | 6 (features) | 23 | Upscale, inpaint, IP-Adapter, enhance |
| S10 | 7 (quality) | 12 | Testes, docs, deploy |

**Velocidade média:** ~15 SP/Sprint → 10 Sprints × 15 = 150 SP total
**Buffer:** 150 - 140 = 10 SP (7% buffer — razoável para riscos de GPU)

## 4. DECISÕES DO PRODUCT OWNER

| # | Questão | Decisão |
|---|---------|---------|
| 1 | ldm_patched | Refatorar em módulos limpos (não copiar como está) |
| 2 | Model downloads | Automático via HuggingFace |
| 3 | Monkey-patches | Replicar TODOS os 8 patches |
| 4 | Async | Migrar para Celery + Redis (padrão monorepo) |
| 5 | Prioridade | Text-to-image primeiro, depois expandir |

## 5. RISCOS E MITIGAÇÕES

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| GPU OOM durante desenvolvimento | Alto | Alta | Lazy load como default, testes com modelos pequenos |
| ldm_patched hard to port | Alto | Média | Refatoração em módulos limpos, spike em S1-S2 |
| Model downloads lentos | Médio | Alta | Cache local, volumes Docker persistentes |
| monkey-patches quebram isolamento | Alto | Média | Documentar cada patch, replicar todos |
| Testes de integração precisam GPU | Médio | Alta | Marcar @pytest.mark.gpu, CI com runner GPU |

## 6. DEFINIÇÃO DE FEITO

- [ ] Código passa AST parse
- [ ] Código passa type check (pyright/mypy)
- [ ] Testes unitários passam (mock GPU)
- [ ] Testes de integração passam (GPU real, Docker)
- [ ] Docker build + deploy funcional
- [ ] 26/26 rotas respondem com dados corretos
- [ ] Lazy load funciona (verificar VRAM antes/depois)
- [ ] README atualizado
