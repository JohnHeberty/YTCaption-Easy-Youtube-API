# Sprint 00: Dataset & Validation Structure

Este diretório contém os datasets para validação e testes do sistema de detecção de legendas embutidas.

## 📁 Estrutura de Diretórios

```
storage/validation/
├── sample_OK/              # Vídeos COM legenda embutida (ground truth: TRUE)
├── sample_NOT_OK/          # Vídeos SEM legenda embutida (ground truth: FALSE)
├── holdout_test_set/       # Test set imutável (200 vídeos) - NÃO USAR EM TREINO
├── dev_set/                # Development set (100 vídeos) - Para tuning/experimentos
├── smoke_set/              # Smoke tests (10-20 vídeos) - Para CI rápido
└── baseline_results.json   # Métricas baseline (v0 - sistema atual)
```

## 🎯 Propósito de Cada Set

### sample_OK / sample_NOT_OK
- **Uso**: Desenvolvimento inicial, prototipagem, debugging
- **Tamanho**: 5-20 vídeos de cada tipo
- **Características**: 
  - Casos típicos (legendas bottom, contraste normal)
  - Vídeos curtos (10-30 segundos)
  - Fácil inspeção manual

### holdout_test_set
- **Uso**: Validação final de cada sprint (NÃO usar em treino/tuning)
- **Tamanho**: 200 vídeos (100 OK + 100 NOT_OK)
- **Características**:
  - Estratificado por resolução (4K, 1080p, 720p)
  - Estratificado por posição de legenda (bottom, top, center)
  - Estratificado por complexidade de fundo
  - Distribuição balanceada
- **CRÍTICO**: Este set é IMUTÁVEL - não adicionar nem remover vídeos após Sprint 00

### dev_set
- **Uso**: Tuning de hiperparâmetros, ROI, thresholds, features
- **Tamanho**: 100 vídeos (50 OK + 50 NOT_OK)
- **Características**: Similar ao holdout, mas pode ser usado em experimentos

### smoke_set
- **Uso**: CI/CD (testes rápidos em cada commit/PR)
- **Tamanho**: 10-20 vídeos (5-10 de cada tipo)
- **Características**:
  - Vídeos pequenos (<10MB total)
  - Processamento rápido (<1 minuto total)
  - Casos representativos

## 📝 Ground Truth Format

Cada diretório deve ter um arquivo `ground_truth.json`:

```json
{
  "videos": [
    {
      "filename": "video_001.mp4",
      "has_subtitles": true,
      "resolution": "1080p",
      "subtitle_position": "bottom",
      "background_complexity": "simple",
      "notes": "Legenda branca, fundo escuro"
    }
  ]
}
```

## 🚀 Como Usar

### 1. Medir Baseline (Sprint 00)

```bash
# Adicionar vídeos em sample_OK e sample_NOT_OK
cd storage/validation
mkdir -p sample_OK sample_NOT_OK

# Copiar vídeos de teste
cp /path/to/videos_com_legenda/*.mp4 sample_OK/
cp /path/to/videos_sem_legenda/*.mp4 sample_NOT_OK/

# Medir baseline
cd ../.. 
python scripts/measure_baseline.py
```

### 2. Executar Regression Tests

```bash
# Smoke test (rápido)
pytest tests/test_sprint00_harness.py::TestRegressionHarness::test_smoke_videos_process -v

# Regression completo
pytest tests/test_sprint00_harness.py -v

# Com coverage
pytest tests/test_sprint00_harness.py --cov=app --cov-report=html
```

### 3. Validar Após Sprint

```bash
# Re-medir métricas
python scripts/measure_baseline.py

# Comparar com baseline
pytest tests/test_sprint00_harness.py::TestRegressionHarness::test_no_regression_f1 -v
```

## 📊 Métricas de Sucesso

Sprint 00 define as metas:
- **F1 Score**: ≥90%
- **Recall**: ≥85%
- **FPR**: <3%

Gates de regressão (FAIL se violados):
- F1 não deve cair >2% vs baseline
- Recall não deve cair >2% vs baseline
- FPR não deve aumentar >2% vs baseline

## 🔒 Regras de Ouro

1. **NUNCA treinar/tunar em holdout_test_set** - Apenas validação final
2. **Split por vídeo, não por frame** - Prevenir data leakage
3. **Estratificar por características** - 4K, top subs, fundo complexo
4. **Versionar ground truth** - Git track ground_truth.json
5. **Documentar erros** - Casos de falha devem virar testes

## 📁 Exemplo de População (Sprint 00)

```bash
# sample_OK (vídeos COM legenda)
sample_OK/
├── youtube_comedy_1080p_001.mp4     # Legenda bottom, fundo simples
├── youtube_news_1080p_002.mp4       # Legenda bottom, fundo complexo
├── youtube_tutorial_4k_003.mp4      # Legenda bottom, 4K
├── youtube_vlog_720p_004.mp4        # Legenda center, fundo médio
├── youtube_music_1080p_005.mp4      # Legenda top, fundo complexo

# sample_NOT_OK (vídeos SEM legenda)
sample_NOT_OK/
├── youtube_raw_1080p_001.mp4        # Sem legenda, sem watermark
├── youtube_raw_4k_002.mp4           # Sem legenda, 4K
├── youtube_gameplay_720p_003.mp4    # Sem legenda, HUD no bottom
├── youtube_cooking_1080p_004.mp4    # Sem legenda, logo no corner
├── youtube_nature_1080p_005.mp4     # Sem legenda, texto ocasional (title card)
```

## 🐛 Troubleshooting

### "Baseline não encontrado"
```bash
python scripts/measure_baseline.py
```

### "Smoke set vazio"
```bash
# Copiar alguns vídeos de sample_OK/sample_NOT_OK para smoke_set
mkdir -p smoke_set
cp sample_OK/youtube_*.mp4 smoke_set/ | head -5
cp sample_NOT_OK/youtube_*.mp4 smoke_set/ | head -5
```

### "Nenhum vídeo encontrado"
- Verificar extensões (apenas .mp4 suportado)
- Verificar permissões (chmod +r *.mp4)
- Verificar encoding (H.264 preferido)

## 📚 Referências

- [Sprint 00 Documentation](../../sprints/sprint_00_baseline_dataset_harness.md)
- [ROADMAP v2.0](../../sprints/ROADMAP.md)
- [FIX_OCR.md - Section 1.5 (NC Resolution)](../../FIX_OCR.md#15-não-conformidades-resolvidas-ncs)
