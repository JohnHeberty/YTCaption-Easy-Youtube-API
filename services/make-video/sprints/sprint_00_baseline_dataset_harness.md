# Sprint 00: Baseline + Dataset + Evaluation Harness

> **Status**: 🔴 **CRITICAL - DEVE SER IMPLEMENTADA ANTES DA SPRINT 01**  
> **Prioridade**: P0 (Ultra Grave)  
> **Duração Estimada**: 1-2 semanas  
> **Dependências**: Nenhuma (é a base de tudo)

---

## 🎯 Objetivo Técnico

**Estabelecer infraestrutura de avaliação ANTES de qualquer desenvolvimento:**

1. **Dataset imutável e estratificado** com ground truth confiável
2. **Baseline mensurável** (sistema atual documentado + métricas)
3. **Harness de avaliação automatizado** (CI/CD gates para "zero regressão")

**Por que Sprint 00 é crítica?**

Sem dataset + baseline + harness **desde o início**, você:
- ❌ Não consegue provar "sem regressão" sprint a sprint
- ❌ Treina/calibra modelos (Sprints 06-07) em "areia movediça"
- ❌ Corre risco de **data leakage** e **overfit** silencioso
- ❌ Não pode validar estimativas de impacto (+5%, +8%, etc.)

**Com Sprint 00 implementada:**
- ✅ Cada sprint prova ganho vs baseline
- ✅ Gates automatizados impedem regressões
- ✅ Dataset sustenta treino/calibração de forma confiável
- ✅ Decisões técnicas baseadas em evidência

---

## 📁 Estrutura de Diretórios do Projeto

**Dataset de Validação Atual**:

```
services/make-video/storage/validation/
├── sample_OK/               # Vídeos COM legenda embutida (positivos)
│   ├── video_001.mp4
│   ├── video_002.mp4
│   └── ...
├── sample_NOT_OK/           # Vídeos SEM legenda embutida (negativos)
│   ├── video_101.mp4
│   ├── video_102.mp4
│   └── ...
├── h264_converted/          # Vídeos convertidos para H264 (processamento)
└── quick_test/              # Subset rápido para testes locais
```

**Estrutura de Dataset Recomendada para Sprint 00**:

```
services/make-video/storage/validation/
├── holdout_test_set/        # 200 vídeos (NUNCA usar para treino!)
│   ├── with_subs/           # 100 vídeos COM legenda
│   │   ├── video_001.mp4
│   │   └── ...
│   ├── without_subs/        # 100 vídeos SEM legenda
│   │   ├── video_101.mp4
│   │   └── ...
│   └── ground_truth.json    # Anotações gold standard
├── development_set/         # 100 vídeos (tuning/validação)
│   ├── with_subs/
│   ├── without_subs/
│   └── ground_truth.json
├── smoke_test_set/          # 20 vídeos (CI/CD rápido)
│   ├── videos/
│   └── golden_predictions.json
└── baseline_results/        # Resultados do baseline
    ├── baseline_metrics.json
    ├── breakdown_by_slice.json
    └── failed_videos.log
```

> **⚠️ NOTA**: Atualmente o projeto tem `sample_OK/` e `sample_NOT_OK/`. Esta sprint propõe reestruturação para separar holdout/dev/smoke sets e evitar contaminação.

---

## 📊 Componentes da Sprint 00

### 1️⃣ Dataset Imutável (Holdout Test Set)

**Objetivo**: Conjunto de teste que **NUNCA** será usado para treino/tuning.

**Especificação**:

```yaml
Holdout Test Set:
  size: 200 vídeos
  composition:
    com_legenda: 100 vídeos
    sem_legenda: 100 vídeos
  
  estratificação:
    resolucao:
      1080p: 100 vídeos (50%)
      720p: 50 vídeos (25%)
      4K: 30 vídeos (15%)
      outros: 20 vídeos (10% - vertical, 480p, etc.)
    
    complexidade_fundo:
      simples: 80 vídeos (fundo preto/gradiente)
      medio: 80 vídeos (fundo com padrões)
      complexo: 40 vídeos (fundo com texto/logos)
    
    posicao_legenda:
      bottom: 80 vídeos (80% - padrão)
      top: 10 vídeos (10% - edge case crítico)
      centro: 10 vídeos (10% - edge case)
    
    duracao_aparicao:
      curta: 20 vídeos (<2s por legenda)
      normal: 140 vídeos (2-5s)
      longa: 40 vídeos (>5s)
    
    estilo_legenda:
      branco_sombra: 60 vídeos (padrão)
      colorido: 20 vídeos
      outlined: 20 vídeos
    
    qualidade_video:
      alta: 100 vídeos (>5 Mbps)
      media: 60 vídeos (2-5 Mbps)
      baixa: 40 vídeos (<2 Mbps - artifacts)

Smoke Test Set:
  size: 20 vídeos (subset do holdout)
  purpose: Testes rápidos em CI/PR (execução <2min)
  composition:
    - 5 casos "fáceis" (1080p, bottom, fundo simples)
    - 5 casos "médios" (720p, bottom, fundo médio)
    - 5 casos "hard" (4K, top, fundo complexo)
    - 5 casos "edge" (vertical, curta duração, baixa qualidade)

Development Set (para tuning/validação durante sprints):
  size: 100 vídeos (SEPARADO do holdout!)
  purpose: Tuning de hiperparâmetros, threshold, ROI, etc.
  composition: Mesma estratificação do holdout
```

**Ground Truth Format**:

```json
{
  "video_id": "abc123xyz",
  "video_path": "services/make-video/storage/validation/holdout_test_set/with_subs/abc123xyz.mp4",
  "resolution": {"width": 1920, "height": 1080},
  "duration_seconds": 180,
  "ground_truth": {
    "has_embedded_subtitles": true,
    "subtitle_regions": [
      {
        "timestamp_start": 5.2,
        "timestamp_end": 8.7,
        "text": "Example subtitle text",
        "bbox": {"x": 640, "y": 950, "width": 640, "height": 60},
        "position": "bottom",
        "confidence_annotation": 1.0
      }
    ]
  },
  "metadata": {
    "background_complexity": "medium",
    "compression_quality": "high",
    "annotator_id": "annotator_01",
    "annotation_date": "2026-02-13",
    "validation_status": "double_checked",
    "source_folder": "sample_OK"  # Migrado de sample_OK/ existente
  }
}
```

**Guidelines de Rotulagem**:

1. **Legenda embutida** (hardcoded): texto que faz parte do frame (não SRT/ASS)
2. **Posição**: bottom (≥70% height), top (≤30% height), centro (30-70%)
3. **Dupla verificação**: 2 anotadores independentes, resolver conflitos
4. **Casos ambíguos**: texto de HUD/grafismos/logos NÃO é legenda
5. **Qualidade mínima**: legenda deve ser legível por humano (≥80% dos caracteres)

---

### 2️⃣ Baseline Documentado

**Objetivo**: Medir sistema ATUAL (antes de qualquer sprint) como ponto de partida.

**Implementação**:

```python
"""
baseline/evaluate_baseline.py

Script para avaliar sistema ATUAL no holdout test set.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List
from app.video_processing.video_validator import SubtitleValidator
from app.ocr.paddle_ocr import PaddleOCRDetector

logger = logging.getLogger(__name__)


class BaselineEvaluator:
    """
    Avalia sistema ATUAL (pre-Sprint 01) no holdout test set.
    """
    
    def __init__(self, test_set_path: str, results_dir: str):
        self.test_set_path = Path(test_set_path)
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize CURRENT system (hardcoded 1080p, full frame, etc.)
        self.ocr_detector = PaddleOCRDetector()
        self.validator = SubtitleValidator(self.ocr_detector)
    
    def evaluate(self) -> Dict:
        """
        Avalia baseline no holdout test set.
        
        Returns:
            Resultados completos com métricas + breakdown por slice
        """
        # Load ground truth
        ground_truth = self._load_ground_truth()
        
        # Run predictions
        predictions = {}
        errors = []
        
        for video_id, gt in ground_truth.items():
            try:
                video_path = gt['video_path']
                prediction = self.validator.has_embedded_subtitles(video_path)
                predictions[video_id] = prediction
            except Exception as e:
                logger.error(f"Baseline failed on {video_id}: {e}")
                errors.append({'video_id': video_id, 'error': str(e)})
                predictions[video_id] = None  # Count as error
        
        # Calculate metrics
        metrics = self._calculate_metrics(ground_truth, predictions)
        
        # Breakdown by slices
        slices = self._breakdown_by_slices(ground_truth, predictions)
        
        # Save results
        results = {
            'baseline_version': 'pre-sprint-01',
            'evaluation_date': '2026-02-13',
            'test_set_size': len(ground_truth),
            'errors': errors,
            'overall_metrics': metrics,
            'slices': slices,
        }
        
        self._save_results(results)
        
        return results
    
    def _calculate_metrics(
        self,
        ground_truth: Dict,
        predictions: Dict
    ) -> Dict:
        """
        Calcula Precision, Recall, F1, FPR, Accuracy.
        """
        tp = fp = tn = fn = 0
        
        for video_id, gt in ground_truth.items():
            gt_label = gt['ground_truth']['has_embedded_subtitles']
            pred = predictions.get(video_id)
            
            if pred is None:
                # Error = False Negative (conservative)
                if gt_label:
                    fn += 1
                else:
                    tn += 1
                continue
            
            if gt_label and pred:
                tp += 1
            elif not gt_label and not pred:
                tn += 1
            elif not gt_label and pred:
                fp += 1
            elif gt_label and not pred:
                fn += 1
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        accuracy = (tp + tn) / (tp + tn + fp + fn)
        
        return {
            'tp': tp,
            'fp': fp,
            'tn': tn,
            'fn': fn,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'fpr': fpr,
            'accuracy': accuracy,
            'error_rate': len([p for p in predictions.values() if p is None]) / len(predictions)
        }
    
    def _breakdown_by_slices(
        self,
        ground_truth: Dict,
        predictions: Dict
    ) -> Dict:
        """
        Métricas por slice (resolução, posição, complexidade).
        """
        slices = {
            'by_resolution': {},
            'by_position': {},
            'by_background': {},
            'by_duration': {},
        }
        
        # Group by slices
        for video_id, gt in ground_truth.items():
            # Resolution
            res = f"{gt['resolution']['width']}x{gt['resolution']['height']}"
            if res not in slices['by_resolution']:
                slices['by_resolution'][res] = {'gt': [], 'pred': []}
            slices['by_resolution'][res]['gt'].append(gt['ground_truth']['has_embedded_subtitles'])
            slices['by_resolution'][res]['pred'].append(predictions.get(video_id))
            
            # Position (if has subtitles)
            if gt['ground_truth']['has_embedded_subtitles'] and gt['ground_truth']['subtitle_regions']:
                pos = gt['ground_truth']['subtitle_regions'][0]['position']
                if pos not in slices['by_position']:
                    slices['by_position'][pos] = {'gt': [], 'pred': []}
                slices['by_position'][pos]['gt'].append(True)
                slices['by_position'][pos]['pred'].append(predictions.get(video_id))
            
            # Background complexity
            bg = gt['metadata']['background_complexity']
            if bg not in slices['by_background']:
                slices['by_background'][bg] = {'gt': [], 'pred': []}
            slices['by_background'][bg]['gt'].append(gt['ground_truth']['has_embedded_subtitles'])
            slices['by_background'][bg]['pred'].append(predictions.get(video_id))
        
        # Calculate metrics per slice
        for slice_type, slice_data in slices.items():
            for slice_name, data in slice_data.items():
                metrics = self._calculate_metrics_from_lists(data['gt'], data['pred'])
                slices[slice_type][slice_name] = metrics
        
        return slices
    
    def _calculate_metrics_from_lists(self, gt_list: List, pred_list: List) -> Dict:
        """Helper para calcular métricas de listas."""
        tp = fp = tn = fn = 0
        
        for gt, pred in zip(gt_list, pred_list):
            if pred is None:
                if gt:
                    fn += 1
                else:
                    tn += 1
                continue
            
            if gt and pred:
                tp += 1
            elif not gt and not pred:
                tn += 1
            elif not gt and pred:
                fp += 1
            elif gt and not pred:
                fn += 1
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        return {
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'samples': len(gt_list)
        }
    
    def _load_ground_truth(self) -> Dict:
        """Carrega ground truth do test set."""
        # Load from JSON files
        gt_file = self.test_set_path / "ground_truth.json"
        with open(gt_file) as f:
            return json.load(f)
    
    def _save_results(self, results: Dict):
        """Salva resultados em JSON."""
        output_file = self.results_dir / "baseline_results.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Baseline results saved: {output_file}")
```

**Baseline Report Example**:

```
BASELINE EVALUATION (Pre-Sprint 01)
====================================

Overall Metrics:
  Precision: 0.745
  Recall: 0.718
  F1: 0.731
  FPR: 0.080 (8.0%)
  Accuracy: 0.835
  Error Rate: 0.068 (6.8% crashes/exceptions)

Breakdown by Resolution:
  1080p (100 videos):
    Precision: 0.820, Recall: 0.800, F1: 0.810
  720p (50 videos):
    Precision: 0.650, Recall: 0.580, F1: 0.613 ⚠️ BAIXO!
  4K (30 videos):
    Precision: 0.600, Recall: 0.520, F1: 0.557 ⚠️ MUITO BAIXO!
  Others (20 videos):
    Precision: 0.700, Recall: 0.650, F1: 0.674

Breakdown by Subtitle Position:
  Bottom (80 videos):
    Precision: 0.810, Recall: 0.780, F1: 0.795
  Top (10 videos):
    Precision: 0.500, Recall: 0.400, F1: 0.444 ❌ CRÍTICO!
  Center (10 videos):
    Precision: 0.667, Recall: 0.600, F1: 0.632

Breakdown by Background Complexity:
  Simple (80 videos):
    Precision: 0.850, Recall: 0.820, F1: 0.835
  Medium (80 videos):
    Precision: 0.740, Recall: 0.710, F1: 0.725
  Complex (40 videos):
    Precision: 0.600, Recall: 0.580, F1: 0.590 ⚠️ BAIXO!
```

**Baseline estabelece targets para as sprints:**
- Sprint 01 deve melhorar 720p/4K (reduzir crashes)
- Sprint 02 deve melhorar top subtitles (ROI com fallback!)
- Sprint 03 deve melhorar complex background

---

### 3️⃣ Evaluation Harness (CI/CD Gates)

**Objetivo**: Gate automatizado que roda a cada PR/sprint e impede regressões.

**Implementação**:

```python
"""
tests/evaluation/test_no_regression.py

Harness de avaliação com gates automáticos.
"""

import pytest
import json
from pathlib import Path
from baseline.evaluate_baseline import BaselineEvaluator


class TestNoRegression:
    """
    Gates de regressão - FALHAM se métricas piorarem.
    """
    
    @pytest.fixture(scope='class')
    def baseline_metrics(self):
        """Carrega métricas do baseline."""
        baseline_file = Path('results/baseline_results.json')
        with open(baseline_file) as f:
            return json.load(f)['overall_metrics']
    
    @pytest.fixture(scope='class')
    def current_metrics(self):
        """Avalia sistema ATUAL no smoke test set (20 vídeos)."""
        evaluator = BaselineEvaluator(
            test_set_path='data/smoke_test',
            results_dir='results/current'
        )
        results = evaluator.evaluate()
        return results['overall_metrics']
    
    def test_precision_no_regression(self, baseline_metrics, current_metrics):
        """Gate: Precisão não pode regredir mais de 1%."""
        baseline_prec = baseline_metrics['precision']
        current_prec = current_metrics['precision']
        
        regression = baseline_prec - current_prec
        
        assert regression <= 0.01, (
            f"PRECISION REGRESSION: "
            f"baseline={baseline_prec:.4f}, current={current_prec:.4f}, "
            f"delta={regression:.4f} (max allowed: 0.01)"
        )
    
    def test_recall_no_regression(self, baseline_metrics, current_metrics):
        """Gate: Recall não pode regredir mais de 2%."""
        baseline_rec = baseline_metrics['recall']
        current_rec = current_metrics['recall']
        
        regression = baseline_rec - current_rec
        
        assert regression <= 0.02, (
            f"RECALL REGRESSION: "
            f"baseline={baseline_rec:.4f}, current={current_rec:.4f}, "
            f"delta={regression:.4f} (max allowed: 0.02)"
        )
    
    def test_fpr_no_regression(self, baseline_metrics, current_metrics):
        """Gate: FPR não pode aumentar mais de 0.5%."""
        baseline_fpr = baseline_metrics['fpr']
        current_fpr = current_metrics['fpr']
        
        increase = current_fpr - baseline_fpr
        
        assert increase <= 0.005, (
            f"FPR REGRESSION: "
            f"baseline={baseline_fpr:.4f}, current={current_fpr:.4f}, "
            f"delta={increase:.4f} (max allowed: 0.005)"
        )
    
    def test_error_rate_improved_or_stable(self, baseline_metrics, current_metrics):
        """Gate: Error rate (crashes) não pode aumentar."""
        baseline_err = baseline_metrics['error_rate']
        current_err = current_metrics['error_rate']
        
        increase = current_err - baseline_err
        
        assert increase <= 0.0, (
            f"ERROR RATE REGRESSION: "
            f"baseline={baseline_err:.4f}, current={current_err:.4f}, "
            f"delta={increase:.4f} (must not increase)"
        )
    
    def test_smoke_set_intact(self, current_metrics):
        """Gate: Smoke set (20 vídeos fixos) deve manter predictions."""
        # Load smoke set "golden predictions" (from baseline)
        golden_file = Path('services/make-video/storage/validation/smoke_test_set/golden_predictions.json')
        with open(golden_file) as f:
            golden = json.load(f)
        
        # Run current system on smoke set
        from app.video_processing.video_validator import SubtitleValidator
        from app.ocr.paddle_ocr import PaddleOCRDetector
        
        validator = SubtitleValidator(PaddleOCRDetector())
        
        smoke_test_dir = Path('services/make-video/storage/validation/smoke_test_set/videos')
        regressions = []
        for video_id, expected_pred in golden.items():
            video_path = smoke_test_dir / f"{video_id}.mp4"
            current_pred = validator.has_embedded_subtitles(str(video_path))
            
            if current_pred != expected_pred:
                regressions.append({
                    'video_id': video_id,
                    'expected': expected_pred,
                    'got': current_pred
                })
        
        assert len(regressions) <= 1, (
            f"SMOKE SET REGRESSION: {len(regressions)} videos changed predictions "
            f"(max allowed: 1). Details: {regressions}"
        )
```

**CI/CD Integration (.github/workflows/regression_check.yml)**:

```yaml
name: Regression Check

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  regression-test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest
      
      - name: Download test dataset
        run: |
          # Download smoke test set (20 videos)
          aws s3 sync s3://ytcaption-test-data/smoke_test data/smoke_test
      
      - name: Run regression tests
        run: |
          pytest tests/evaluation/test_no_regression.py -v --tb=short
      
      - name: Fail if regressions detected
        if: failure()
        run: |
          echo "❌ REGRESSION DETECTED - PR BLOCKED"
          exit 1
```

---

## 📋 Critério de Aceite Sprint 00

```
✅ CRÍTICO (MUST HAVE)
  □ Holdout test set criado: 200 vídeos estratificados
  □ Smoke test set criado: 20 vídeos (subset do holdout)
  □ Development set criado: 100 vídeos (separado do holdout)
  □ Ground truth anotado por 2 anotadores independentes
  □ Guidelines de rotulagem documentadas
  □ Baseline avaliado no holdout: métricas salvas em baseline_results.json
  □ Breakdown por slices documentado (resolução, posição, background)
  □ Harness de avaliação implementado: test_no_regression.py
  □ CI/CD gates configurados: regression_check.yml
  □ Smoke set validado: ≤1 regressão permitida

✅ IMPORTANTE (SHOULD HAVE)
  □ Dataset versionado (Git LFS ou DVC)
  □ Documentação de coleta/amostragem de vídeos
  □ Scripts de validação de ground truth (dupla checagem)
  □ Dashboard de métricas (Grafana/MLflow)
  □ Slices adicionais: duração, qualidade, estilo

✅ NICE TO HAVE (COULD HAVE)
  □ Anotação semi-automática (OCR + review manual)
  □ Inter-annotator agreement (Kappa score)
  □ Test set expandido (500 vídeos)
```

### Definição de "Done" Sprint 00

1. ✅ Holdout test set (200 vídeos) pronto e versionado
2. ✅ Baseline medido: Precision/Recall/FPR/Error Rate
3. ✅ Breakdown por slices mostra gargalos (720p/4K/top subs)
4. ✅ Harness CI/CD bloqueando PRs com regressão
5. ✅ Smoke set (20 vídeos) rodando em <2min
6. ✅ Time alinhado: baseline é "source of truth" para as sprints

---

## 🚀 Impacto da Sprint 00

| Aspecto | Antes (sem Sprint 00) | Depois (com Sprint 00) |
|---------|----------------------|------------------------|
| **Treino Sprint 06** | Dataset indefinido, risco de leakage | Dataset limpo, split disjunto, sem leakage ✅ |
| **Calibração Sprint 07** | Sem holdout para calibrar | Holdout dedicado, isotonic seguro ✅ |
| **Zero Regressão** | Sem como provar | Gates automatizados por sprint ✅ |
| **Decisões técnicas** | Baseadas em "achismo" | Baseadas em breakdown por slice ✅ |
| **Risco de overfit** | ALTO (sem holdout) | BAIXO (holdout imutável) ✅ |
| **Tempo de validação** | Manual, demorado | Automatizado, <2min (smoke set) ✅ |

**ROI da Sprint 00**:
- Investimento: 1-2 semanas (anotação + scripts)
- Retorno: **Evita 4-6 semanas de retrabalho** (treino em dataset ruim, regressões não detectadas, overfit em produção)

---

## 📝 Checklist de Implementação

```
Sprint 00 Checklist - Status: 🟡 IN PROGRESS (2025-02-13)

  Infrastructure & Environment:
    ✅ Setup Python environment (3.11.2 + venv)
    ✅ Install PaddleOCR 3.4.0 (CPU version)
    ✅ Install testing framework (pytest 7.4.3 + pytest-cov)
    ✅ Install dependencies (prometheus-client, fastapi, opencv, etc.)
    ⚠️ Fix PaddleOCR MKL arithmetic error (BLOCKER - needs resolution)

  Dataset Structure:
    ✅ Create validation directory structure
    ✅ Create sample_OK/ directory (7 videos)
    ✅ Create sample_NOT_OK/ directory (39 videos)
    ✅ Create ground_truth.json for sample_OK (7 videos)
    ✅ Create ground_truth.json for sample_NOT_OK (39 videos)
    ✅ Create holdout_test_set/ directory (ready for population)
    ✅ Create dev_set/ directory (ready for population)
    ✅ Create smoke_set/ directory (ready for population)
    ⚠️ Dataset imbalanced (15.2% positive class - needs more positive samples)
    ☐ Collect 320 videos total (200 holdout + 100 dev + 20 smoke)
    ☐ Stratify by resolution/position/complexity
    ☐ Annotate ground truth (2 independent annotators)
    ☐ Resolve annotation conflicts
    ☐ Validate annotation quality (spot check 10%)
    ☐ Version dataset (Git LFS / DVC)

  Baseline Measurement:
    ✅ Create scripts/measure_baseline.py (260 lines - full implementation)
    ✅ Create scripts/measure_baseline_simple.py (189 lines - fallback)
    ✅ Generate baseline_results.json (placeholder - OCR pending)
    ⚠️ OCR measurement BLOCKED by PaddleOCR initialization error
    ☐ Fix PaddleOCR or implement pytesseract fallback
    ☐ Run actual baseline measurement on videos
    ☐ Document breakdown by slices (resolution/position/complexity)

  Regression Test Harness:
    ✅ Create tests/test_sprint00_harness.py (regression gates)
    ✅ Implement baseline_exists test (PASSING)
    ✅ Implement baseline_sanity test (PENDING - needs real metrics)
    ✅ Implement no_regression gates (F1, Recall, FPR)
    ✅ Implement goal_tracking tests (informational)
    ✅ Implement smoke_videos_process test (SKIPPED - needs smoke_set videos)
    ✅ Create storage/validation/README.md (dataset documentation)
    ☐ Configure CI/CD: .github/workflows/regression_check.yml
    ☐ Validate gates: simulate deliberate regression (should block)

  Documentation & Finalization:
    ✅ Update sprint_00 checklist (this document)
    ☐ Document baseline as "source of truth"
    ☐ Prepare presentation for team (alignment)
    ☐ Approve Sprint 00 as "complete"
    ☐ Rename to OK_sprint_00_baseline_dataset_harness.md
    ☐ Unblock Sprint 01 (baseline established)

  BLOCKERS (P0 - Must Resolve):
    🔴 PaddleOCR MKL arithmetic error (SIGFPE) - prevents OCR measurement
       Solutions:
         A. Fix PaddleOCR installation (different version/backend)
         B. Implement pytesseract fallback temporarily
         C. Use cloud OCR API (Google Vision, AWS Rekognition)
    
    🟡 Dataset imbalance (15.2% positive class)
       Solution: Add 20+ more videos WITH subtitles to sample_OK
```

---

## 🎯 Próximos Passos

1. ✅ **Aprovar Sprint 00 como crítica** (bloqueia Sprints 01-10)
2. ⏳ Alocar recursos: 1-2 pessoas full-time por 1-2 semanas
3. ⏳ Coletar e anotar dataset (200 + 100 + 20 vídeos)
4. ⏳ Implementar baseline evaluator + harness
5. ⏳ Configurar CI/CD gates
6. ✅ **Aprovar baseline como "source of truth"**
7. ➡️ **Liberar Sprint 01** (com baseline estabelecido)

---

## 📌 Nota Crítica

> **SEM SPRINT 00, O ROADMAP SPRINTS 01-10 É ARRISCADO A PONTO DE SER INVIÁVEL.**
>
> Esta sprint resolve o problema #1 identificado no documento FIX_OCR.md:
> - ✅ Dataset + ground truth + harness ANTES do desenvolvimento
> - ✅ Sustenta treino/calibração (Sprints 06-07)
> - ✅ Gates automatizados para "zero regressão"
> - ✅ Decisões baseadas em evidência (breakdown por slice)
>
> **Recomendação: Implementar Sprint 00 IMEDIATAMENTE antes de qualquer outra sprint.**

---

## 🔄 Migração de Dados Existentes

**Situação Atual**: O projeto já possui datasets em:
- `services/make-video/storage/validation/sample_OK/` - vídeos COM legenda embutida
- `services/make-video/storage/validation/sample_NOT_OK/` - vídeos SEM legenda embutida

**Plano de Migração para Estrutura Sprint 00**:

```bash
# Script de migração (migrate_dataset.sh)

#!/bin/bash
set -e

VALIDATION_ROOT="services/make-video/storage/validation"
SOURCE_OK="$VALIDATION_ROOT/sample_OK"
SOURCE_NOT_OK="$VALIDATION_ROOT/sample_NOT_OK"

# Criar nova estrutura
mkdir -p "$VALIDATION_ROOT/holdout_test_set/with_subs"
mkdir -p "$VALIDATION_ROOT/holdout_test_set/without_subs"
mkdir -p "$VALIDATION_ROOT/development_set/with_subs"
mkdir -p "$VALIDATION_ROOT/development_set/without_subs"
mkdir -p "$VALIDATION_ROOT/smoke_test_set/videos"
mkdir -p "$VALIDATION_ROOT/baseline_results"

# Contar vídeos disponíveis
NUM_OK=$(ls -1 "$SOURCE_OK"/*.mp4 2>/dev/null | wc -l)
NUM_NOT_OK=$(ls -1 "$SOURCE_NOT_OK"/*.mp4 2>/dev/null | wc -l)

echo "Vídeos disponíveis:"
echo "  - COM legenda (sample_OK): $NUM_OK"
echo "  - SEM legenda (sample_NOT_OK): $NUM_NOT_OK"

# Estratégia de split (70% holdout, 25% dev, 5% smoke)
# Para 100 vídeos OK: 70 holdout, 25 dev, 5 smoke
# Para 100 vídeos NOT_OK: 70 holdout, 25 dev, 5 smoke

# Assumindo sample_OK tem suficientes vídeos, fazer split aleatório
cd "$SOURCE_OK"
ls -1 *.mp4 | shuf > /tmp/ok_shuffled.txt

# Split sample_OK
head -n 70 /tmp/ok_shuffled.txt | while read video; do
    cp "$video" "$VALIDATION_ROOT/holdout_test_set/with_subs/"
done

tail -n +71 /tmp/ok_shuffled.txt | head -n 25 | while read video; do
    cp "$video" "$VALIDATION_ROOT/development_set/with_subs/"
done

tail -n 5 /tmp/ok_shuffled.txt | while read video; do
    cp "$video" "$VALIDATION_ROOT/smoke_test_set/videos/"
done

# Split sample_NOT_OK (similar)
cd "$SOURCE_NOT_OK"
ls -1 *.mp4 | shuf > /tmp/not_ok_shuffled.txt

head -n 70 /tmp/not_ok_shuffled.txt | while read video; do
    cp "$video" "$VALIDATION_ROOT/holdout_test_set/without_subs/"
done

tail -n +71 /tmp/not_ok_shuffled.txt | head -n 25 | while read video; do
    cp "$video" "$VALIDATION_ROOT/development_set/without_subs/"
done

tail -n 5 /tmp/not_ok_shuffled.txt | while read video; do
    cp "$video" "$VALIDATION_ROOT/smoke_test_set/videos/"
done

echo "✅ Migração concluída!"
echo "Estrutura criada em: $VALIDATION_ROOT"
```

**Próximos Passos Após Migração**:

1. **Anotar ground truth**: Criar `ground_truth.json` para holdout/dev sets
2. **Validar qualidade**: Spot check manual de 10% dos vídeos
3. **Rodar baseline**: Executar `baseline/evaluate_baseline.py`
4. **Gerar golden predictions**: Para smoke test set (CI/CD)
5. **Versionar datasets**: Usar Git LFS ou DVC

**Exemplo de Ground Truth Inicial**:

```python
# scripts/generate_initial_ground_truth.py

import json
from pathlib import Path

def generate_ground_truth(videos_dir: Path, has_subs: bool) -> dict:
    """
    Gera ground truth inicial (placeholder) para validação manual posterior.
    """
    ground_truth = {}
    
    for video_path in videos_dir.glob("*.mp4"):
        video_id = video_path.stem
        ground_truth[video_id] = {
            "video_id": video_id,
            "video_path": str(video_path),
            "ground_truth": {
                "has_embedded_subtitles": has_subs,
                "subtitle_regions": [],  # Anotar manualmente
                "needs_annotation": True
            },
            "metadata": {
                "source_folder": "sample_OK" if has_subs else "sample_NOT_OK",
                "annotation_status": "pending"
            }
        }
    
    return ground_truth

# Gerar para holdout
holdout_ok = Path("services/make-video/storage/validation/holdout_test_set/with_subs")
holdout_not_ok = Path("services/make-video/storage/validation/holdout_test_set/without_subs")

gt_ok = generate_ground_truth(holdout_ok, has_subs=True)
gt_not_ok = generate_ground_truth(holdout_not_ok, has_subs=False)

combined_gt = {**gt_ok, **gt_not_ok}

output_path = Path("services/make-video/storage/validation/holdout_test_set/ground_truth.json")
with open(output_path, 'w') as f:
    json.dump(combined_gt, f, indent=2)

print(f"✅ Ground truth inicial salvo em: {output_path}")
print(f"   Total de vídeos: {len(combined_gt)}")
print(f"   ⚠️  ATENÇÃO: Revisar manualmente e preencher 'subtitle_regions'")
```

> **⚠️ IMPORTANTE**: Os vídeos em `sample_OK/` e `sample_NOT_OK/` existentes são um **ótimo ponto de partida**, mas precisam de:
> 1. Anotação detalhada (bbox, timestamps, posição)
> 2. Estratificação por resolução/complexidade
> 3. Validação por 2 anotadores independentes
> 4. Coleta de vídeos adicionais se necessário (meta: 200 holdout + 100 dev)


