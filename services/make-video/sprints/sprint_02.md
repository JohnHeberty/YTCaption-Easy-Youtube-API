# Sprint Pack 02/12 - Correção de Posicionamento (Quick Win)

**Escopo deste pack:** Implementar correção do posicionamento de legendas de bottom para center, aplicando Alignment=5 em todos os estilos, removendo MarginV, e validando visualmente. Este é o "quick win" mais simples do projeto (P0).

## Índice

- [S-013: Corrigir Alignment em estilo "static"](#s-013)
- [S-014: Corrigir Alignment em estilo "dynamic"](#s-014)
- [S-015: Corrigir Alignment em estilo "minimal"](#s-015)
- [S-016: Remover MarginV de todos os estilos](#s-016)
- [S-017: Adicionar testes unitários de posicionamento](#s-017)
- [S-018: Criar teste de validação visual automatizado](#s-018)
- [S-019: Gerar vídeo de teste com posicionamento corrigido](#s-019)
- [S-020: Criar script de validação manual de posicionamento](#s-020)
- [S-021: Documentar correção no CHANGELOG](#s-021)
- [S-022: Adicionar métrica de posicionamento](#s-022)
- [S-023: Validar com 5 vídeos de teste diferentes](#s-023)
- [S-024: Deploy e rollback test](#s-024)

---

<a name="s-013"></a>
## S-013: Corrigir Alignment em estilo "static"

**Objetivo:** Alterar Alignment de 10 para 5 no estilo "static", garantindo legendas centralizadas verticalmente.

**Escopo (IN/OUT):**
- **IN:** Modificar apenas o parâmetro Alignment no estilo static
- **OUT:** Não modificar outros parâmetros (FontSize, cores, Outline, Bold)

**Arquivos tocados:**
- `services/make-video/app/video_builder.py`

**Mudanças exatas:**
- Localizar linha com `"static": "FontSize=20,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=2,Bold=1,Alignment=10,MarginV=280"`
- Alterar para `"static": "FontSize=20,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=2,Bold=1,Alignment=5"`
- Remover `,MarginV=280` completamente

**Critérios de Aceite / Definition of Done:**
- [ ] Alignment=5 no estilo static
- [ ] MarginV removido do estilo static
- [ ] Código compila sem erros
- [ ] Nenhum outro parâmetro alterado

**Testes:**
- Unit: `tests/test_video_builder.py::test_static_style_alignment_is_5()`
- Manual: Gerar vídeo com estilo static e verificar centro

**Observabilidade:**
- Log: `logger.info("subtitle_style_applied", style="static", alignment=5)`

**Riscos/Rollback:**
- Risco: Legendas podem sobrepor conteúdo importante no centro
- Rollback: Reverter para Alignment=2 (bottom center) se houver reclamações

**Dependências:** S-001 (estrutura)

---

<a name="s-014"></a>
## S-014: Corrigir Alignment em estilo "dynamic"

**Objetivo:** Alterar Alignment de 10 para 5 no estilo "dynamic", consistente com static.

**Escopo (IN/OUT):**
- **IN:** Modificar apenas Alignment no estilo dynamic
- **OUT:** Não alterar cores ciano (PrimaryColour=&H00FFFF&) ou outros parâmetros

**Arquivos tocados:**
- `services/make-video/app/video_builder.py`

**Mudanças exatas:**
- Localizar linha com `"dynamic": "FontSize=22,PrimaryColour=&H00FFFF&,OutlineColour=&H000000&,Outline=2,Bold=1,Alignment=10,MarginV=280"`
- Alterar para `"dynamic": "FontSize=22,PrimaryColour=&H00FFFF&,OutlineColour=&H000000&,Outline=2,Bold=1,Alignment=5"`
- Remover `,MarginV=280`

**Critérios de Aceite / Definition of Done:**
- [ ] Alignment=5 no estilo dynamic
- [ ] MarginV removido
- [ ] Cores ciano preservadas
- [ ] FontSize=22 preservado

**Testes:**
- Unit: `tests/test_video_builder.py::test_dynamic_style_alignment_is_5()`
- Manual: Gerar vídeo com dynamic e validar centralização

**Observabilidade:**
- Log: `logger.info("subtitle_style_applied", style="dynamic", alignment=5)`

**Riscos/Rollback:**
- Risco: Mesmo de S-013
- Rollback: Reverter para Alignment=2

**Dependências:** S-013

---

<a name="s-015"></a>
## S-015: Corrigir Alignment em estilo "minimal"

**Objetivo:** Alterar Alignment de 10 para 5 no estilo "minimal", completando correção em todos os 3 estilos.

**Escopo (IN/OUT):**
- **IN:** Modificar apenas Alignment no estilo minimal
- **OUT:** Não alterar Outline=1 (mais fino) ou outros parâmetros do minimal

**Arquivos tocados:**
- `services/make-video/app/video_builder.py`

**Mudanças exatas:**
- Localizar linha com `"minimal": "FontSize=18,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=1,Alignment=10,MarginV=280"`
- Alterar para `"minimal": "FontSize=18,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=1,Alignment=5"`
- Remover `,MarginV=280`

**Critérios de Aceite / Definition of Done:**
- [ ] Alignment=5 no estilo minimal
- [ ] MarginV removido
- [ ] Outline=1 preservado (diferenciador do minimal)
- [ ] Todos os 3 estilos agora têm Alignment=5

**Testes:**
- Unit: `tests/test_video_builder.py::test_minimal_style_alignment_is_5()`
- Unit: `tests/test_video_builder.py::test_all_styles_have_alignment_5()`

**Observabilidade:**
- Log: `logger.info("subtitle_style_applied", style="minimal", alignment=5)`

**Riscos/Rollback:**
- Risco: Mesmo anterior
- Rollback: Reverter todos os 3 estilos simultaneamente

**Dependências:** S-014

---

<a name="s-016"></a>
## S-016: Remover MarginV de todos os estilos

**Objetivo:** Garantir que MarginV foi removido completamente de todos os estilos, validando que nenhum vestígio permaneceu.

**Escopo (IN/OUT):**
- **IN:** Buscar e validar remoção de MarginV em toda a codebase
- **OUT:** Não adicionar novos parâmetros

**Arquivos tocados:**
- `services/make-video/app/video_builder.py`

**Mudanças exatas:**
- Executar grep: `grep -n "MarginV" app/video_builder.py` deve retornar 0 resultados
- Se encontrar qualquer ocorrência, remover
- Adicionar comentário: `# MarginV removido: Alignment=5 centraliza sem necessidade de margem`

**Critérios de Aceite / Definition of Done:**
- [ ] `grep MarginV` retorna vazio
- [ ] Comentário explicativo adicionado
- [ ] Nenhuma referência a MarginV em styles

**Testes:**
- Unit: `tests/test_video_builder.py::test_no_marginv_in_styles()`
- CI: Lint que rejeita MarginV em styles

**Observabilidade:**
- N/A (limpeza de código)

**Riscos/Rollback:**
- Risco: Nenhum (remoção segura)
- Rollback: N/A

**Dependências:** S-015

---

<a name="s-017"></a>
## S-017: Adicionar testes unitários de posicionamento

**Objetivo:** Criar testes automatizados que validam programaticamente que Alignment=5 em todos os estilos.

**Escopo (IN/OUT):**
- **IN:** Testes que parsam styles e verificam Alignment, ausência de MarginV
- **OUT:** Não testar rendering visual ainda (próxima sprint)

**Arquivos tocados:**
- `services/make-video/tests/test_video_builder.py`

**Mudanças exatas:**
- Criar `def test_static_style_has_alignment_5()`: assert "Alignment=5" in styles["static"]
- Criar `def test_dynamic_style_has_alignment_5()`: assert "Alignment=5" in styles["dynamic"]
- Criar `def test_minimal_style_has_alignment_5()`: assert "Alignment=5" in styles["minimal"]
- Criar `def test_no_style_has_marginv()`: for style in styles.values(): assert "MarginV" not in style
- Criar `def test_all_styles_have_alignment_5()`: validar lista completa

**Critérios de Aceite / Definition of Done:**
- [ ] 5 testes unitários criados
- [ ] Todos os testes passam: `pytest tests/test_video_builder.py::test_*_alignment -v`
- [ ] Cobertura: 100% das linhas de styles

**Testes:**
- Self-test: Executar pytest

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: Testes frágeis se formato de styles mudar
- Rollback: Usar regex mais flexível

**Dependências:** S-016

---

<a name="s-018"></a>
## S-018: Criar teste de validação visual automatizado

**Objetivo:** Implementar teste que extrai frame de vídeo gerado e valida posição vertical do texto usando OCR ou análise de imagem.

**Escopo (IN/OUT):**
- **IN:** Gerar vídeo de teste, extrair frame do meio, detectar bbox do texto, validar posição Y
- **OUT:** Não validar conteúdo do texto, apenas posição

**Arquivos tocados:**
- `services/make-video/tests/test_subtitle_positioning.py` (novo)

**Mudanças exatas:**
- Criar função `def extract_frame_at_timestamp(video_path, timestamp) -> np.ndarray` usando FFmpeg
- Criar função `def detect_text_bbox(frame) -> dict` usando cv2 ou pytesseract
- Criar teste `async def test_subtitle_appears_in_center(sample_video)`
- No teste: gerar vídeo com legenda, extrair frame, bbox = detect_text_bbox(frame)
- Validar: `center_y = bbox['y'] + bbox['height']/2`, `video_center = frame.shape[0]/2`
- Assert: `abs(center_y - video_center) < frame.shape[0] * 0.1` (tolerância 10%)

**Critérios de Aceite / Definition of Done:**
- [ ] Teste cria vídeo com legenda
- [ ] Frame extraído corretamente
- [ ] Bbox detectado com confiança >80%
- [ ] Posição validada como centro ±10%

**Testes:**
- Integration: `pytest tests/test_subtitle_positioning.py::test_subtitle_appears_in_center -v`

**Observabilidade:**
- Log: `logger.info("visual_validation", center_y=..., video_center=..., diff_pct=...)`

**Riscos/Rollback:**
- Risco: OCR falha em detectar bbox
- Rollback: Usar análise de contraste (branco em frame escuro)

**Dependências:** S-017, S-010 (fixtures)

---

<a name="s-019"></a>
## S-019: Gerar vídeo de teste com posicionamento corrigido

**Objetivo:** Criar vídeo de teste manual para validação visual humana do posicionamento correto.

**Escopo (IN/OUT):**
- **IN:** Script que gera vídeo 10s com legendas usando cada estilo (static/dynamic/minimal)
- **OUT:** Não automatizar análise visual ainda

**Arquivos tocados:**
- `services/make-video/scripts/generate_test_video.py` (novo)

**Mudanças exatas:**
- Criar script CLI: `python scripts/generate_test_video.py --style static --output test_static.mp4`
- Script chama `video_builder.burn_subtitles()` com SRT de teste
- SRT de teste: 3 cues de 3s cada, texto "TEST SUBTITLE CENTER"
- Gerar 3 vídeos: `test_static.mp4`, `test_dynamic.mp4`, `test_minimal.mp4`

**Critérios de Aceite / Definition of Done:**
- [ ] Script executável e gera 3 vídeos
- [ ] Cada vídeo tem 10s de duração
- [ ] Legendas visíveis e legíveis
- [ ] Armazenados em `tests/fixtures/positioning/`

**Testes:**
- Manual: Assistir os 3 vídeos e confirmar legendas no centro
- CI: Validar que vídeos foram criados (existem no fs)

**Observabilidade:**
- Log: `logger.info("test_video_generated", style="...", path="...")`

**Riscos/Rollback:**
- Risco: Vídeos grandes (armazenamento)
- Rollback: Gerar apenas sob demanda, não committar vídeos

**Dependências:** S-018

---

<a name="s-020"></a>
## S-020: Criar script de validação manual de posicionamento

**Objetivo:** Criar checklist interativo para QA manual validar posicionamento em diferentes resoluções e players.

**Escopo (IN/OUT):**
- **IN:** Script que lista passos de validação, gera vídeos de teste, abre player
- **OUT:** Não automatizar aprovação/reprovação

**Arquivos tocados:**
- `services/make-video/scripts/validate_positioning_manual.sh` (novo)

**Mudanças exatas:**
- Criar shell script com seções: "1. Generate test videos", "2. Open in VLC", "3. Checklist"
- Checklist: "[ ] Legendas aparecem no centro vertical?", "[ ] Não sobrepõem conteúdo importante?", "[ ] Visível em 1080x1920?", "[ ] Visível em 720x1280?"
- Script gera vídeos com generate_test_video.py
- Abre VLC com `vlc test_*.mp4` (se disponível)
- Pede confirmação: "Press Y to approve, N to reject"

**Critérios de Aceite / Definition of Done:**
- [ ] Script executável
- [ ] Checklist tem 5+ itens
- [ ] Vídeos gerados automaticamente
- [ ] Input de usuário capturado

**Testes:**
- Manual: Executar script e seguir checklist

**Observabilidade:**
- Log: Resultado da validação manual salvo em `validation_results.txt`

**Riscos/Rollback:**
- Risco: VLC não disponível
- Rollback: Usar player padrão do sistema ou instruir manual

**Dependências:** S-019

---

<a name="s-021"></a>
## S-021: Documentar correção no CHANGELOG

**Objetivo:** Adicionar entrada no CHANGELOG.md do projeto documentando a correção de posicionamento.

**Escopo (IN/OUT):**
- **IN:** Adicionar seção "## v1.X - Positioning Fix" com detalhes
- **OUT:** Não atualizar README principal ainda

**Arquivos tocados:**
- `services/make-video/CHANGELOG.md`

**Mudanças exatas:**
- Adicionar no topo: `## [Unreleased] - 2026-01-29`
- Seção `### Fixed`
- Item: `- **Subtitle Positioning:** Corrected alignment from top (Alignment=10) to center (Alignment=5) in all styles (static, dynamic, minimal). Removed MarginV parameter as no longer needed.`
- Item: `- **Impact:** Subtitles now appear in the vertical center of video, improving readability without obstructing bottom content.`

**Critérios de Aceite / Definition of Done:**
- [ ] Entrada adicionada ao CHANGELOG
- [ ] Formato consistente com entradas anteriores
- [ ] Data correta (2026-01-29)
- [ ] Menciona os 3 estilos

**Testes:**
- Manual: Ler CHANGELOG e verificar clareza

**Observabilidade:**
- N/A (documentation)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-015 (correção completa)

---

<a name="s-022"></a>
## S-022: Adicionar métrica de posicionamento

**Objetivo:** Adicionar contador de vídeos gerados por estilo de legenda para observabilidade.

**Escopo (IN/OUT):**
- **IN:** Métrica counter `videos_generated_total` com tag `style={static|dynamic|minimal}`
- **OUT:** Não adicionar outras métricas ainda

**Arquivos tocados:**
- `services/make-video/app/video_builder.py`

**Mudanças exatas:**
- Em `burn_subtitles()`, após sucesso, adicionar: `metrics.counter("videos_generated_total", 1, {"style": style})`
- Importar metrics: `from app.metrics import counter`

**Critérios de Aceite / Definition of Done:**
- [ ] Métrica incrementa ao gerar vídeo
- [ ] Tag `style` tem valores: static, dynamic, minimal
- [ ] Visível em endpoint `/metrics`

**Testes:**
- Unit: `tests/test_video_builder.py::test_metric_increments_on_burn()`
- Integration: Gerar vídeo e verificar métrica aumentou

**Observabilidade:**
- Métrica: `videos_generated_total{style="static"}`, `videos_generated_total{style="dynamic"}`, `videos_generated_total{style="minimal"}`

**Riscos/Rollback:**
- Risco: Métrica não incrementa (bug)
- Rollback: Remover linha de métrica

**Dependências:** S-008 (infra de métricas)

---

<a name="s-023"></a>
## S-023: Validar com 5 vídeos de teste diferentes

**Objetivo:** Executar pipeline completo com 5 vídeos de teste (diferentes resoluções, durações) e validar posicionamento em todos.

**Escopo (IN/OUT):**
- **IN:** Criar 5 vídeos teste, processar com cada estilo, validar visualmente
- **OUT:** Não processar vídeos de produção ainda

**Arquivos tocados:**
- `services/make-video/tests/test_positioning_scenarios.py` (novo)

**Mudanças exatas:**
- Criar 5 vídeos: `test_1080x1920.mp4` (vertical), `test_1920x1080.mp4` (horizontal), `test_720x1280.mp4` (vertical low-res), `test_short_5s.mp4`, `test_long_60s.mp4`
- Para cada vídeo + estilo (3 estilos): gerar versão com legenda
- Total: 15 vídeos de saída
- Validar programaticamente posição do texto em cada frame central

**Critérios de Aceite / Definition of Done:**
- [ ] 5 vídeos de entrada criados
- [ ] 15 vídeos de saída gerados (5 vídeos × 3 estilos)
- [ ] Todos passam no teste de posicionamento (centro ±10%)
- [ ] Resultados documentados em `tests/positioning_validation_report.txt`

**Testes:**
- Integration: `pytest tests/test_positioning_scenarios.py -v`

**Observabilidade:**
- Log: `logger.info("positioning_validated", video="...", style="...", passed=True/False)`

**Riscos/Rollback:**
- Risco: Testes lentos (15 vídeos)
- Rollback: Reduzir para 3 vídeos × 2 estilos

**Dependências:** S-018, S-019

---

<a name="s-024"></a>
## S-024: Deploy e rollback test

**Objetivo:** Fazer deploy da correção em ambiente de staging, testar, e validar procedimento de rollback.

**Escopo (IN/OUT):**
- **IN:** Deploy em staging, gerar 3 vídeos reais, rollback para versão anterior, re-deploy
- **OUT:** Não fazer deploy em produção ainda

**Arquivos tocados:**
- Nenhum (operacional)

**Mudanças exatas:**
- Executar: `git checkout -b feature/positioning-fix`
- Commit das mudanças: `git commit -m "fix: correct subtitle alignment to center (Alignment=5)"`
- Push: `git push origin feature/positioning-fix`
- Deploy em staging: `./deploy.sh staging`
- Gerar 3 vídeos de teste via API de staging
- Baixar e validar vídeos manualmente
- Rollback: `git checkout main && ./deploy.sh staging`
- Re-deploy fix: `git checkout feature/positioning-fix && ./deploy.sh staging`

**Critérios de Aceite / Definition of Done:**
- [ ] Branch criada
- [ ] Deploy em staging bem-sucedido
- [ ] 3 vídeos gerados e validados
- [ ] Rollback executado sem erros
- [ ] Re-deploy funcional

**Testes:**
- Manual: Acessar staging e criar job
- Manual: Validar vídeo final tem legendas no centro

**Observabilidade:**
- Logs de deploy: timestamp, branch, environment
- Métricas: `videos_generated_total` deve incrementar em staging

**Riscos/Rollback:**
- Risco: Deploy quebra staging
- Rollback: `git checkout main && ./deploy.sh staging` (já testado)

**Dependências:** S-001 a S-023 (todos anteriores)

---

## Mapa de Dependências (Pack 02)

```
S-013 (static) → S-014
S-014 (dynamic) → S-015
S-015 (minimal) → S-016, S-021
S-016 (remover MarginV) → S-017
S-017 (unit tests) → S-018
S-018 (visual validation) → S-019, S-023
S-019 (test video) → S-020, S-023
S-020 (manual script) ← S-019
S-021 (CHANGELOG) ← S-015
S-022 (métrica) ← S-008
S-023 (5 cenários) ← S-018, S-019
S-024 (deploy) ← todos anteriores
```

**Próximo pack:** Sprint 03 - Validação de integridade de vídeo (ffprobe + decode real)
