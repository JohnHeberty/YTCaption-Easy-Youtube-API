# Sprint 09: Continuous Training / Model Retraining Pipeline

**Duração:** 4-5 dias  
**Dependências:** Sprints 00-08 (especialmente Sprint 00 - dataset, Sprint 06 - classifier, Sprint 08 - drift detection)  
**Objetivo:** Automatizar retreino do modelo quando drift detectado, garantindo que modelo em produção nunca degrada.

---

## Contexto & Motivação

### Problema

Após deploy em produção (Sprint 08), modelo pode degradar ao longo do tempo:

```
┌─────────────────────────────────────────────────────────────────┐
│ CENÁRIOS DE DEGRADAÇÃO                                          │
├─────────────────────────────────────────────────────────────────┤
│ 1. Feature Drift: Novos tipos de vídeo (TikTok, YouTube Shorts)│
│    → brightness, frame_count, avg_confidence mudam de range    │
│                                                                 │
│ 2. Concept Drift: YouTube muda formato de legendas (WebVTT 3.0)│
│    → "has_subtitles" agora correlaciona diferente com features │
│                                                                 │
│ 3. Upstream Changes: youtube-dl atualiza, muda extração        │
│    → Features agora têm distribuição diferente                 │
│                                                                 │
│ 4. Seasonal: Mais vídeos em português em Dez (Copa, Natal)     │
│    → language features mudam temporalmente                      │
└─────────────────────────────────────────────────────────────────┘
```

**Drift detection (Sprint 08)** identifica quando isso acontece. **Sprint 09** responde automaticamente:

```
Drift Detected → Trigger Retraining → Validate New Model → Deploy if Better
```

---

### Por Que Agora?

Sem Sprint 09, drift detection é **inútil** - alerta sem ação:

```
❌ Sprint 08 sem Sprint 09:
   Slack: "⚠️ Feature drift detected (15% of features)"
   Engenheiro: "Ok... e agora?" → Manual retraining (3-5 dias)
   
✅ Sprint 08 + Sprint 09:
   Slack: "⚠️ Feature drift detected → Retraining triggered"
   Pipeline: Retreina automaticamente overnight
   Slack: "✅ New model deployed (v7.1), F1: 97.8% → 98.1%"
```

---

### Justificativa Matemática

```
Frequência esperada de drift: cada 2-4 semanas (produção real)
Custo de retreino manual: 3-5 dias (engenheiro dedicado)
Custo de retreino automatizado: 2-4h (pipeline overnight)

Economia anual:
  Manual: (52 semanas / 3 semanas) × 4 dias = 69 dias/ano
  Automatizado: (52 / 3) × 0.2 dias = 3.5 dias/ano
  
  Saving: 65.5 dias/ano de eng time ✅

Sprint 09 investimento: 4-5 dias
ROI: Paga-se em 3-4 retreinos (≈ 2-3 meses de produção)
```

---

## Objetivo do Sprint 09

**Goal:**  
Implementar pipeline de retreino automático que:
1. **Trigger**: Detecta drift (via Sprint 08 metrics) OU manualmente
2. **Data Collection**: Coleta novos dados (production logs + labels)
3. **Retraining**: Treina novo modelo com dados recentes + históricos
4. **Validation**: Valida novo modelo vs modelo em produção (test set)
5. **Deployment**: Deploy automático **SE** novo modelo > atual (senão rollback)
6. **Monitoring**: Alerta se retreino falha OU novo modelo == pior

---

## Métrica Impactada

| Métrica | Antes Sprint 09 | Após Sprint 09 | Impacto | Status |
|---------|-----------------|----------------|---------|--------|
| **Model Staleness** | >4 semanas (manual) | <1 semana (auto) | ✅ -75% staleness | 🟢 |
| **Drift Response Time** | 3-5 dias (manual) | 2-4h (overnight) | ✅ 95% mais rápido | 🟢 |
| **F1 Degradation** | -2% ao longo 1 mês | <0.5% (retreino proativo) | ✅ +1.5pp mantido | 🟢 |
| **Eng Time Saved** | 69 dias/ano | 3.5 dias/ano | ✅ 95% redução | 🟢 |
| **Model Versions** | 1 versão (estática) | 12-20/ano (evolutivo) | ✅ Adaptação contínua | 🟢 |

**Definição de Sucesso:**

Sprint 09 **ACEITA** se:
- Pipeline roda end-to-end sem intervenção manual (100% automatizado)
- Novo modelo **só** é deployed se F1 ≥ current_model_f1 - 0.01 (tolerância 1pp)
- Retreino completo <8h (viável rodar overnight)
- Rollback automático funciona (caso novo modelo falhe em validação)
- Drift detection → retraining trigger latency <1h

---

## Arquitetura do Pipeline

### Visão Geral

```
┌────────────────────────────────────────────────────────────────────────────┐
│ CONTINUOUS TRAINING PIPELINE (Kubeflow / Airflow)                         │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  [1. Drift Detection]  ──trigger──>  [2. Data Collection]                 │
│         (Sprint 08)                      │                                 │
│                                          ├─> Production logs (S3)          │
│                                          ├─> Proxy labels (feedback)       │
│                                          └─> Human audits (1% sample)      │
│                                          │                                 │
│                                          ▼                                 │
│                                  [3. Data Validation]                      │
│                                          ├─> Schema check                  │
│                                          ├─> Quality check (missing < 5%)  │
│                                          └─> Temporal split (no leakage)   │
│                                          │                                 │
│                                          ▼                                 │
│                                  [4. Feature Engineering]                  │
│                                          ├─> Reusar pipeline Sprint 04/05   │
│                                          └─> Schema validation (Sprint 06) │
│                                          │                                 │
│                                          ▼                                 │
│                                  [5. Model Training]                       │
│                                          ├─> Train (Sprint 06 - Classifier) │
│                                          ├─> Calibrate (Sprint 07)         │
│                                          └─> Save artifacts (S3 + MLflow)  │
│                                          │                                 │
│                                          ▼                                 │
│                                  [6. Model Validation]                     │
│                                          ├─> Test set (200 videos)         │
│                                          ├─> Compare: new vs current       │
│                                          └─> Gate: deploy IF new >= current│
│                                          │                                 │
│                                          ▼                                 │
│                                  [7. Deployment]                           │
│                                          ├─> Canary deploy (Sprint 08)     │
│                                          └─> Rollback if drift detected    │
│                                          │                                 │
│                                          ▼                                 │
│                                  [8. Monitoring]                           │
│                                          ├─> Track new model performance   │
│                                          └─> Alert if F1 < threshold       │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Tarefas do Sprint 09

### 1. Setup de Infraestrutura

**1.1) Escolher Orquestrador**

Opções:

| Tool | Pros | Cons | Recomendação |
|------|------|------|--------------|
| **Airflow** | Maduro, Python-native, DAGs flexíveis | Requer setup (Postgres, Redis) | ✅ Se já usado |
| **Kubeflow Pipelines** | K8s-native, ML-focused, componentes reutilizáveis | Complexo, overkill para pipelines pequenos | ✅ Se já k8s |
| **Prefect** | Moderno, Python-friendly, menos burocrático | Menos maduro que Airflow | ⚠️ Alternativa |
| **Cron + Scripts** | Simples, zero setup | Sem DAG visualization, difícil debug | ❌ Só para MVP |

**Decisão**: **Kubeflow Pipelines** (assume k8s já existe de Sprint 08).

---

**1.2) Criar DAG do Pipeline**

```python
# pipeline/retraining_pipeline.py

import kfp
from kfp import dsl
from kfp.components import create_component_from_func

@dsl.pipeline(
    name="YTCaption Subtitle Detector Retraining Pipeline",
    description="Retreina modelo quando drift detectado"
)
def retraining_pipeline(
    drift_detected: bool = True,
    data_start_date: str = "2024-01-01",
    data_end_date: str = "2024-12-31",
    min_samples: int = 5000,  # Mínimo de samples para retreinar
    test_set_path: str = "s3://ytcaption-test-set/v1/",
    current_model_version: str = "v7.0",
):
    """
    Pipeline de retreino completo.
    
    Args:
        drift_detected: Se True, força retreino mesmo se drift mínimo
        data_start_date: Início da janela de dados (YYYY-MM-DD)
        data_end_date: Fim da janela de dados
        min_samples: Mínimo de samples necessários para retreinar
        test_set_path: Caminho S3 para test set (validação final)
        current_model_version: Versão do modelo em produção
    """
    
    # Step 1: Collect data
    data_collection_op = collect_production_data(
        start_date=data_start_date,
        end_date=data_end_date,
        min_samples=min_samples
    )
    
    # Step 2: Validate data
    data_validation_op = validate_data(
        data_path=data_collection_op.outputs['data_path']
    )
    
    # Step 3: Feature engineering
    feature_engineering_op = engineer_features(
        data_path=data_validation_op.outputs['validated_data_path'],
        schema_path="s3://ytcaption-artifacts/schemas/feature_schema_v1.json"
    )
    
    # Step 4: Train model
    model_training_op = train_model(
        features_path=feature_engineering_op.outputs['features_path'],
        hyperparams_path="s3://ytcaption-artifacts/hyperparams/best_params_v7.json"
    )
    
    # Step 5: Calibrate model (Sprint 07)
    model_calibration_op = calibrate_model(
        model_path=model_training_op.outputs['model_path'],
        calibration_data_path=feature_engineering_op.outputs['calibration_data_path']
    )
    
    # Step 6: Validate new model vs current
    validation_op = validate_new_model(
        new_model_path=model_calibration_op.outputs['calibrated_model_path'],
        current_model_version=current_model_version,
        test_set_path=test_set_path
    )
    
    # Step 7: Deploy if new model better (conditional)
    with dsl.Condition(validation_op.outputs['deploy_new_model'] == 'true'):
        deploy_op = deploy_model(
            model_path=validation_op.outputs['new_model_path'],
            model_version=validation_op.outputs['new_model_version']
        )
    
    # Step 8: Notify (success ou failure)
    notify_op = send_notification(
        status=validation_op.outputs['status'],
        metrics=validation_op.outputs['metrics']
    )

# Compile pipeline
if __name__ == '__main__':
    kfp.compiler.Compiler().compile(
        pipeline_func=retraining_pipeline,
        package_path='retraining_pipeline.yaml'
    )
```

**Componentes estimados**: ~8 componentes, ~1,200 linhas de código total.

---

### 2. Data Collection (Componente #1)

**Desafio**: Coletar dados de produção **COM labels**.

**Estratégias** (veja Sprint 08 - Proxy Labels):

```python
# pipeline/components/data_collection.py

import pandas as pd
from datetime import datetime, timedelta
from typing import Tuple

def collect_production_data(
    start_date: str,
    end_date: str,
    min_samples: int
) -> Tuple[str, dict]:
    """
    Coleta dados de produção para retreino.
    
    Fontes:
      1. Production logs (S3): features extraídas de vídeos processados
      2. Proxy labels: user feedback (via proxy_labels_collector.py)
      3. Human audits: 1% sample auditado manualmente
    
    Returns:
        data_path: S3 path para dados coletados
        metadata: {n_samples, label_distribution, sources}
    """
    
    # 1. Buscar production logs
    production_logs = load_from_s3(
        f"s3://ytcaption-production-logs/{start_date}_to_{end_date}.parquet"
    )
    # Logs contêm: video_id, features (brightness, frame_count, ...), timestamp
    
    # 2. Buscar proxy labels (feedback de usuários)
    proxy_labels = load_from_postgres(
        table="proxy_labels",
        start_date=start_date,
        end_date=end_date
    )
    # proxy_labels: video_id, label (0/1), confidence (low/medium/high), source
    
    # 3. Buscar human audits (ground truth de alta qualidade)
    human_audits = load_from_postgres(
        table="human_audits",
        start_date=start_date,
        end_date=end_date
    )
    # human_audits: video_id, label (0/1), auditor_id, timestamp
    
    # 4. Merge: production_logs + labels
    # PRIORITY: human_audits > proxy_labels (higher quality)
    df_labeled = production_logs.merge(
        human_audits, on='video_id', how='left', suffixes=('', '_human')
    ).merge(
        proxy_labels, on='video_id', how='left', suffixes=('', '_proxy')
    )
    
    # Escolher melhor label disponível
    df_labeled['label'] = df_labeled['label_human'].fillna(df_labeled['label_proxy'])
    df_labeled['label_source'] = df_labeled.apply(
        lambda row: 'human' if pd.notna(row['label_human']) else 'proxy',
        axis=1
    )
    
    # 5. Drop samples sem label
    df_labeled = df_labeled.dropna(subset=['label'])
    
    # 6. Quality check
    if len(df_labeled) < min_samples:
        raise ValueError(
            f"Insufficient labeled data: {len(df_labeled)} < {min_samples}. "
            f"Cannot retrain model."
        )
    
    # 7. Save to S3
    output_path = f"s3://ytcaption-retraining-data/{start_date}_to_{end_date}.parquet"
    df_labeled.to_parquet(output_path, index=False)
    
    metadata = {
        'n_samples': len(df_labeled),
        'label_distribution': df_labeled['label'].value_counts().to_dict(),
        'sources': df_labeled['label_source'].value_counts().to_dict(),
        'date_range': (start_date, end_date)
    }
    
    return output_path, metadata
```

**Estimativa**:
- ~150 linhas de código
- Depende de: S3 (logs), Postgres (proxy_labels, human_audits)
- Tempo de execução: 10-30 min (depende de volume)

---

### 3. Data Validation (Componente #2)

**Desafio**: Garantir qualidade dos dados **ANTES** de treinar.

```python
# pipeline/components/data_validation.py

import pandas as pd
from typing import Tuple
import great_expectations as ge

def validate_data(data_path: str) -> Tuple[str, dict]:
    """
    Valida dados coletados (schema, quality, temporal leakage).
    
    Checks:
      1. Schema: colunas esperadas existem?
      2. Missing values: <5% por coluna?
      3. Duplicates: <1%?
      4. Label balance: 30-70% (não desbalanceado demais)?
      5. Temporal split: treino < validação < test (sem leakage)?
    
    Returns:
        validated_data_path: S3 path se validação OK
        validation_report: {passed: bool, checks: [...]}
    """
    
    df = pd.read_parquet(data_path)
    
    # 1. Schema check (Great Expectations)
    ge_df = ge.from_pandas(df)
    
    expectations = [
        # Colunas esperadas (56 features de Sprint 02)
        ge_df.expect_column_to_exist('brightness'),
        ge_df.expect_column_to_exist('frame_count'),
        ge_df.expect_column_to_exist('has_audio'),
        # ... (all 56 features)
        ge_df.expect_column_to_exist('label'),
        
        # Ranges válidos
        ge_df.expect_column_values_to_be_between('brightness', 0, 255),
        ge_df.expect_column_values_to_be_between('frame_count', 1, 100000),
        ge_df.expect_column_values_to_be_in_set('label', [0, 1]),
        
        # Missing values
        ge_df.expect_column_values_to_not_be_null('label', mostly=1.0),  # 100% labels
        ge_df.expect_column_values_to_not_be_null('brightness', mostly=0.95),  # 95%+
    ]
    
    validation_results = ge_df.validate()
    
    # 2. Quality checks
    missing_pct = df.isnull().sum() / len(df)
    high_missing_cols = missing_pct[missing_pct > 0.05].index.tolist()
    
    duplicates_pct = df.duplicated(subset=['video_id']).sum() / len(df)
    
    label_balance = df['label'].value_counts(normalize=True)
    is_balanced = (label_balance >= 0.30).all() and (label_balance <= 0.70).all()
    
    # 3. Temporal split (CRITICAL para evitar leakage)
    # Ordenar por timestamp, então split 60/20/20
    df = df.sort_values('timestamp')
    n = len(df)
    train_end = int(0.60 * n)
    val_end = int(0.80 * n)
    
    df['split'] = 'test'
    df.loc[:train_end, 'split'] = 'train'
    df.loc[train_end:val_end, 'split'] = 'val'
    
    # Verificar que train < val < test (timestamps)
    assert df[df['split'] == 'train']['timestamp'].max() < \
           df[df['split'] == 'val']['timestamp'].min(), \
           "Temporal leakage: train overlaps val"
    
    assert df[df['split'] == 'val']['timestamp'].max() < \
           df[df['split'] == 'test']['timestamp'].min(), \
           "Temporal leakage: val overlaps test"
    
    # 4. Save validated data
    validated_path = data_path.replace('.parquet', '_validated.parquet')
    df.to_parquet(validated_path, index=False)
    
    validation_report = {
        'passed': validation_results.success and len(high_missing_cols) == 0 and duplicates_pct < 0.01 and is_balanced,
        'checks': {
            'schema_valid': validation_results.success,
            'high_missing_cols': high_missing_cols,
            'duplicates_pct': float(duplicates_pct),
            'label_balance': label_balance.to_dict(),
            'is_balanced': is_balanced,
            'temporal_split_ok': True  # Se chegou aqui, passou
        }
    }
    
    if not validation_report['passed']:
        raise ValueError(f"Data validation failed: {validation_report}")
    
    return validated_path, validation_report
```

**Estimativa**:
- ~200 linhas de código
- Usa: Great Expectations (schema validation)
- Tempo: 5-10 min

---

### 4. Feature Engineering (Componente #3)

**Reutilizar Sprint 02** - não reinventar a roda!

```python
# pipeline/components/feature_engineering.py

from app.feature_engineering.pipeline import FeatureEngineeringPipeline

def engineer_features(
    data_path: str,
    schema_path: str
) -> dict:
    """
    Aplica feature engineering (reutiliza Sprint 02).
    
    CRITICAL: Usar MESMO pipeline de Sprint 02 para evitar train/serve skew.
    """
    
    df = pd.read_parquet(data_path)
    
    # Load feature pipeline (salvo em Sprint 02)
    pipeline = FeatureEngineeringPipeline.load(
        "s3://ytcaption-artifacts/pipelines/feature_pipeline_v1.pkl"
    )
    
    # Apply transformations
    X = pipeline.transform(df)
    y = df['label']
    splits = df['split']
    
    # Validate schema (Sprint 06)
    from app.model_training.schema_validator import validate_feature_schema
    validate_feature_schema(X, schema_path)
    
    # Split data
    X_train = X[splits == 'train']
    y_train = y[splits == 'train']
    
    X_val = X[splits == 'val']
    y_val = y[splits == 'val']
    
    X_test = X[splits == 'test']
    y_test = y[splits == 'test']
    
    # Save splits
    output_paths = {
        'train': 's3://ytcaption-retraining-data/train.parquet',
        'val': 's3://ytcaption-retraining-data/val.parquet',
        'test': 's3://ytcaption-retraining-data/test.parquet'
    }
    
    for split_name, (X_split, y_split) in [
        ('train', (X_train, y_train)),
        ('val', (X_val, y_val)),
        ('test', (X_test, y_test))
    ]:
        df_split = X_split.copy()
        df_split['label'] = y_split
        df_split.to_parquet(output_paths[split_name], index=False)
    
    return output_paths
```

**Estimativa**:
- ~100 linhas de código (reutiliza Sprint 02!)
- Tempo: 5-10 min

---

### 5. Model Training (Componente #4)

**Reutilizar Sprint 05** - mesmo algoritmo, novos dados.

```python
# pipeline/components/model_training.py

from app.model_training.trainer import ModelTrainer

def train_model(
    features_path: dict,  # {train, val, test}
    hyperparams_path: str
) -> Tuple[str, dict]:
    """
    Treina novo modelo com dados recentes.
    
    Usa hyperparameters de Sprint 05 (já otimizados).
    """
    
    # Load data
    train_df = pd.read_parquet(features_path['train'])
    val_df = pd.read_parquet(features_path['val'])
    
    X_train = train_df.drop(columns=['label'])
    y_train = train_df['label']
    X_val = val_df.drop(columns=['label'])
    y_val = val_df['label']
    
    # Load hyperparameters (from Sprint 05 tuning)
    import json
    with open(hyperparams_path, 'r') as f:
        hyperparams = json.load(f)
    
    # Train model (LightGBM from Sprint 05)
    trainer = ModelTrainer()
    model, metrics = trainer.train(
        X_train, y_train,
        X_val, y_val,
        hyperparams=hyperparams
    )
    
    # Save model
    model_version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    model_path = f"s3://ytcaption-models/{model_version}/model.pkl"
    
    import joblib
    with open(model_path, 'wb') as f:
        joblib.dump(model, f)
    
    # Log to MLflow
    import mlflow
    mlflow.log_params(hyperparams)
    mlflow.log_metrics(metrics)
    mlflow.log_artifact(model_path)
    
    return model_path, metrics
```

**Estimativa**:
- ~150 linhas de código
- Tempo: 30-60 min (treino no dataset completo)

---

### 6. Model Calibration (Componente #5)

**Reutilizar Sprint 07** - mesmo processo.

```python
# pipeline/components/model_calibration.py

from app.calibration.calibrator import ModelCalibrator

def calibrate_model(
    model_path: str,
    calibration_data_path: str
) -> Tuple[str, dict]:
    """
    Calibra modelo recém-treinado (Sprint 07).
    """
    
    # Load model
    import joblib
    model = joblib.load(model_path)
    
    # Load calibration data (subset de val)
    df_cal = pd.read_parquet(calibration_data_path)
    X_cal = df_cal.drop(columns=['label'])
    y_cal = df_cal['label']
    
    # Calibrate (Platt ou Isotonic, auto-select)
    calibrator = ModelCalibrator(method='auto')
    calibrated_model = calibrator.calibrate(model, X_cal, y_cal)
    
    # Evaluate calibration
    from app.calibration.metrics import compute_brier_score, compute_expected_calibration_error
    
    y_proba_uncal = model.predict_proba(X_cal)[:, 1]
    y_proba_cal = calibrated_model.predict_proba(X_cal)[:, 1]
    
    brier_uncal = compute_brier_score(y_cal, y_proba_uncal)
    brier_cal = compute_brier_score(y_cal, y_proba_cal)
    
    ece_uncal = compute_expected_calibration_error(y_cal, y_proba_uncal)
    ece_cal = compute_expected_calibration_error(y_cal, y_proba_cal)
    
    calibration_metrics = {
        'brier_score_uncalibrated': float(brier_uncal),
        'brier_score_calibrated': float(brier_cal),
        'ece_uncalibrated': float(ece_uncal),
        'ece_calibrated': float(ece_cal),
        'brier_improvement': float(brier_uncal - brier_cal)
    }
    
    # Save calibrated model
    calibrated_model_path = model_path.replace('.pkl', '_calibrated.pkl')
    joblib.dump(calibrated_model, calibrated_model_path)
    
    return calibrated_model_path, calibration_metrics
```

**Estimativa**:
- ~120 linhas de código
- Tempo: 5-10 min

---

### 7. Model Validation (Componente #6) - **CRITICAL GATE**

**Desafio**: Garantir que novo modelo >= modelo atual **ANTES** de deploy.

```python
# pipeline/components/model_validation.py

from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
import numpy as np

def validate_new_model(
    new_model_path: str,
    current_model_version: str,
    test_set_path: str,
    min_f1_improvement: float = -0.01  # Tolera até 1pp de queda
) -> dict:
    """
    Valida novo modelo vs modelo em produção.
    
    Gates:
      1. F1 (new) >= F1 (current) - 0.01  (tolera 1pp de queda)
      2. Precision (new) >= Precision (current) - 0.01
      3. Recall (new) >= Recall (current) - 0.01
      4. ROC-AUC (new) >= ROC-AUC (current) - 0.005
    
    Returns:
        {
          'deploy_new_model': 'true'/'false',
          'new_model_version': 'v7.1',
          'metrics_comparison': {...},
          'decision_reason': 'F1 improved by 0.8pp'
        }
    """
    
    # Load models
    import joblib
    new_model = joblib.load(new_model_path)
    current_model = joblib.load(
        f"s3://ytcaption-models/{current_model_version}/model_calibrated.pkl"
    )
    
    # Load test set (external, never seen in training - Sprint 08)
    test_df = pd.read_parquet(f"{test_set_path}/test_videos.parquet")
    X_test = test_df.drop(columns=['label'])
    y_test = test_df['label']
    
    # Predict with both models
    y_pred_new = new_model.predict(X_test)
    y_proba_new = new_model.predict_proba(X_test)[:, 1]
    
    y_pred_current = current_model.predict(X_test)
    y_proba_current = current_model.predict_proba(X_test)[:, 1]
    
    # Compute metrics
    metrics_new = {
        'precision': precision_score(y_test, y_pred_new),
        'recall': recall_score(y_test, y_pred_new),
        'f1': f1_score(y_test, y_pred_new),
        'roc_auc': roc_auc_score(y_test, y_proba_new)
    }
    
    metrics_current = {
        'precision': precision_score(y_test, y_pred_current),
        'recall': recall_score(y_test, y_pred_current),
        'f1': f1_score(y_test, y_pred_current),
        'roc_auc': roc_auc_score(y_test, y_proba_current)
    }
    
    # Compare
    f1_diff = metrics_new['f1'] - metrics_current['f1']
    precision_diff = metrics_new['precision'] - metrics_current['precision']
    recall_diff = metrics_new['recall'] - metrics_current['recall']
    roc_auc_diff = metrics_new['roc_auc'] - metrics_current['roc_auc']
    
    # Decision gates
    gates_passed = {
        'f1_gate': f1_diff >= min_f1_improvement,
        'precision_gate': precision_diff >= min_f1_improvement,
        'recall_gate': recall_diff >= min_f1_improvement,
        'roc_auc_gate': roc_auc_diff >= -0.005
    }
    
    deploy_new_model = all(gates_passed.values())
    
    # Statistical significance (McNemar test - Sprint 08)
    from statsmodels.stats.contingency_tables import mcnemar as mcnemar_test
    
    new_correct = (y_pred_new == y_test)
    current_correct = (y_pred_current == y_test)
    
    b = sum((~current_correct) & new_correct)  # Current wrong, new right
    c = sum(current_correct & (~new_correct))  # Current right, new wrong
    
    if b + c > 0:
        contingency_table = np.array([[sum(current_correct & new_correct), b],
                                      [c, sum((~current_correct) & (~new_correct))]])
        mcnemar_result = mcnemar_test(contingency_table, exact=False, correction=True)
        is_significant = mcnemar_result.pvalue < 0.05
    else:
        is_significant = False
    
    # Generate report
    new_model_version = new_model_path.split('/')[-2]  # Ex: v20241225_143022
    
    decision_reason = f"F1: {f1_diff:+.4f} | Precision: {precision_diff:+.4f} | Recall: {recall_diff:+.4f}"
    if not deploy_new_model:
        decision_reason = f"REJECTED - {decision_reason} (failed gates)"
    elif is_significant:
        decision_reason = f"APPROVED - {decision_reason} (statistically significant, p={mcnemar_result.pvalue:.4f})"
    else:
        decision_reason = f"APPROVED - {decision_reason} (not statistically significant, but no regression)"
    
    return {
        'deploy_new_model': 'true' if deploy_new_model else 'false',
        'new_model_version': new_model_version,
        'new_model_path': new_model_path,
        'metrics_new': metrics_new,
        'metrics_current': metrics_current,
        'metrics_comparison': {
            'f1_diff': float(f1_diff),
            'precision_diff': float(precision_diff),
            'recall_diff': float(recall_diff),
            'roc_auc_diff': float(roc_auc_diff)
        },
        'gates_passed': gates_passed,
        'is_statistically_significant': is_significant,
        'decision_reason': decision_reason,
        'status': 'success' if deploy_new_model else 'rejected'
    }
```

**Estimativa**:
- ~250 linhas de código
- Tempo: 10-15 min (avalia 200 vídeos)

---

### 8. Deployment (Componente #7)

**Reutilizar Sprint 08** - canary deployment.

```python
# pipeline/components/deployment.py

import subprocess

def deploy_model(
    model_path: str,
    model_version: str
) -> dict:
    """
    Deploy novo modelo via canary (Sprint 08).
    
    Steps:
      1. Update model artifact in S3 (novo version tag)
      2. Trigger canary deployment (10% → 50% → 100%)
      3. Monitor for 4h (drift detection ativo)
      4. Rollback if drift > threshold
    """
    
    # 1. Tag new model as "candidate"
    subprocess.run([
        'aws', 's3', 'cp',
        model_path,
        f"s3://ytcaption-models/production/candidate_{model_version}.pkl"
    ], check=True)
    
    # 2. Update k8s deployment (canary)
    subprocess.run([
        'kubectl', 'set', 'image',
        'deployment/subtitle-detector-canary',
        f'detector=ytcaption-detector:{model_version}',
        '-n', 'production'
    ], check=True)
    
    # 3. Update Istio VirtualService (10% traffic)
    # (veja Sprint 08 para detalhes)
    
    print(f"✅ Canary deployment started: {model_version} (10% traffic)")
    print("   Monitoring for 4h before full rollout...")
    
    return {
        'deployed': True,
        'model_version': model_version,
        'deployment_type': 'canary',
        'initial_traffic_pct': 10
    }
```

**Estimativa**:
- ~100 linhas de código (reutiliza Sprint 08)
- Tempo: 30s (trigger deployment, monitoring async)

---

### 9. Monitoring & Alerting (Componente #8)

```python
# pipeline/components/monitoring.py

def send_notification(
    status: str,  # 'success', 'rejected', 'failed'
    metrics: dict
) -> None:
    """
    Envia notificação Slack sobre retraining.
    """
    
    import requests
    
    if status == 'success':
        message = f"""
✅ **Model Retraining SUCCESSFUL**

New model deployed: {metrics['new_model_version']}
F1 improvement: {metrics['metrics_comparison']['f1_diff']:+.4f}
Precision: {metrics['metrics_new']['precision']:.4f}
Recall: {metrics['metrics_new']['recall']:.4f}

Canary deployment started (10% traffic).
Monitoring for 4h before full rollout.
        """
    elif status == 'rejected':
        message = f"""
⚠️ **Model Retraining REJECTED**

New model did NOT pass validation gates.
Reason: {metrics['decision_reason']}

Current model remains in production.
        """
    else:  # failed
        message = f"""
❌ **Model Retraining FAILED**

Pipeline failed at: {metrics.get('failed_step', 'unknown')}
Error: {metrics.get('error_message', 'unknown error')}

Manual intervention required.
        """
    
    # Send to Slack
    slack_webhook = "https://hooks.slack.com/services/YOUR_WEBHOOK"
    requests.post(slack_webhook, json={'text': message})
```

**Estimativa**:
- ~80 linhas de código
- Tempo: <1s

---

## Estratégias de Data Collection

### Estratégia 1: Expanding Window (Recomendada para início)

```
Treino sempre inclui TODOS os dados históricos + novos dados.

Exemplo:
  Retreino #1: Jan-Jun 2024 (6 meses)
  Retreino #2: Jan-Sep 2024 (9 meses) ← Inclui Jan-Jun + Jul-Sep
  Retreino #3: Jan-Dez 2024 (12 meses) ← Inclui tudo até agora

PROS:
  + Modelo aprende padrões históricos + recentes (mais robusto)
  + Dataset cresce → melhor performance geralmente
  
CONS:
  - Treino cada vez mais lento (mais dados)
  - Conceitos antigos podem "diluir" padrões recentes
  - Após 2-3 anos, dataset enorme (inviável)
```

---

### Estratégia 2: Rolling Window (Recomendada para longo prazo)

```
Treino usa apenas últimos N meses de dados.

Exemplo (N=6 meses):
  Retreino #1: Jan-Jun 2024
  Retreino #2: Apr-Sep 2024 ← Esquece Jan-Mar
  Retreino #3: Jul-Dez 2024 ← Esquece Apr-Jun

PROS:
  + Dataset tamanho fixo → treino rápido (consistente)
  + Foca em padrões recentes (adapta a concept drift)
  
CONS:
  - Esquece padrões históricos (pode perder generalização)
  - Requer N suficientemente grande (ex: 6 meses ≈ 50k samples)
```

---

### Estratégia 3: Weighted Sampling (Híbrido)

```
Mantém todos dados históricos, mas sobreamostra dados recentes.

Exemplo:
  Dados Jan-Jun: weight = 1.0
  Dados Jul-Sep: weight = 2.0  ← Treino vê 2x mais
  Dados Out-Dez: weight = 3.0  ← Treino vê 3x mais

PROS:
  + Combina robustez (histórico) + adaptação (recente)
  + Dataset completo (útil para análises)
  
CONS:
  - Complexidade adicional (requer LightGBM weights)
  - Treino ainda cresce com tempo (mas mais lento)
```

---

**Decisão para Sprint 09**: Usar **Expanding Window** inicialmente (primeiros 6-12 meses), depois migrar para **Rolling Window (6 meses)** quando dataset > 100k samples.

```python
# Pseudocódigo

def get_training_data(strategy='expanding', window_months=6):
    if strategy == 'expanding':
        # Todos os dados desde início do projeto
        start_date = '2024-01-01'  # Data de deploy inicial
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    elif strategy == 'rolling':
        # Últimos N meses
        end_date = datetime.now()
        start_date = (end_date - timedelta(days=window_months * 30)).strftime('%Y-%m-%d')
        end_date = end_date.strftime('%Y-%m-%d')
    
    return collect_production_data(start_date, end_date, min_samples=5000)
```

---

## Trigger Strategies

### Trigger 1: Drift Detection (Automático)

```python
# Trigger retraining quando drift detectado (Sprint 08)

from app.monitoring.drift_detector import DriftDetector

drift_detector = DriftDetector()
drift_report = drift_detector.detect_drift(
    reference_data=X_train_original,  # Dados de treino originais (v7.0)
    production_data=X_production_recent  # Últimas 2 semanas
)

if drift_report['feature_drift_detected']:
    # Trigger retraining pipeline
    trigger_retraining_pipeline(reason='feature_drift', drift_report=drift_report)
```

**Thresholds:**
- Feature drift: >15% features com drift (KS p-value < 0.05 após FDR)
- Prediction drift: PSI > 0.2
- Performance drift: F1 cai >2pp (via proxy labels)

---

### Trigger 2: Scheduled (Periódico)

```python
# Retreino a cada N semanas, mesmo sem drift (segurança)

# Cron job: toda segunda-feira às 2am
# 0 2 * * 1 /usr/local/bin/trigger_retraining.sh

trigger_retraining_pipeline(reason='scheduled_weekly')
```

**Frequência recomendada**: 1x/semana (se produção estável) ou 2x/semana (se mudanças frequentes).

---

### Trigger 3: Manual (On-demand)

```python
# Engenheiro dispara manualmente (ex: após bug fix, nova feature)

# Via CLI
$ python pipeline/trigger_retraining.py \
    --reason "manual: fixed youtube-dl bug" \
    --data-start-date "2024-11-01" \
    --data-end-date "2024-12-31"
```

---

## Estrutura de Arquivos

```
services/make-video/
├── pipeline/
│   ├── retraining_pipeline.py          # Main DAG (Kubeflow) (~400 linhas)
│   ├── trigger_retraining.py           # CLI para trigger manual (~150 linhas)
│   ├── components/
│   │   ├── data_collection.py          # Componente #1 (~150 linhas)
│   │   ├── data_validation.py          # Componente #2 (~200 linhas)
│   │   ├── feature_engineering.py      # Componente #3 (~100 linhas)
│   │   ├── model_training.py           # Componente #4 (~150 linhas)
│   │   ├── model_calibration.py        # Componente #5 (~120 linhas)
│   │   ├── model_validation.py         # Componente #6 (~250 linhas) ⭐ GATE
│   │   ├── deployment.py               # Componente #7 (~100 linhas)
│   │   └── monitoring.py               # Componente #8 (~80 linhas)
│   └── config/
│       ├── kubeflow_pipeline.yaml      # Compiled pipeline (~200 linhas)
│       └── retraining_config.yaml      # Hyperparameters, thresholds (~100 linhas)
├── scripts/
│   ├── setup_kubeflow.sh               # Setup infrastructure (~80 linhas)
│   └── deploy_pipeline.sh              # Deploy pipeline to Kubeflow (~50 linhas)
└── tests/
    ├── test_retraining_pipeline.py     # Integration test (~300 linhas)
    └── fixtures/
        └── mock_production_data.parquet # Mock data for testing

**Total**: ~2,400 linhas de código (pipeline + testes).
```

---

## Testes

### 1. Unit Tests (Componentes Isolados)

```python
# tests/test_data_collection.py

def test_collect_production_data():
    """Testa coleta de dados com mock."""
    
    # Mock S3/Postgres
    with mock_s3(), mock_postgres():
        data_path, metadata = collect_production_data(
            start_date='2024-01-01',
            end_date='2024-01-31',
            min_samples=100
        )
        
        df = pd.read_parquet(data_path)
        
        assert len(df) >= 100, "Min samples not met"
        assert 'label' in df.columns, "Labels missing"
        assert df['label'].isnull().sum() == 0, "Null labels found"
        assert set(df['label_source'].unique()) <= {'human', 'proxy'}, "Invalid label source"
```

---

### 2. Integration Test (Pipeline End-to-End)

```python
# tests/test_retraining_pipeline.py

def test_retraining_pipeline_end_to_end():
    """
    Testa pipeline completo com dados mock.
    
    Steps:
      1. Mock data collection (100 samples)
      2. Run full pipeline
      3. Verify new model trained
      4. Verify validation gate works
      5. Verify deployment (or rejection) happens
    """
    
    # 1. Inject mock data
    mock_data = create_mock_production_data(n_samples=100)
    upload_to_s3(mock_data, 's3://ytcaption-test/mock_data.parquet')
    
    # 2. Run pipeline (against test environment)
    result = run_retraining_pipeline(
        drift_detected=True,
        data_start_date='2024-01-01',
        data_end_date='2024-01-31',
        test_mode=True  # Uses test S3 bucket, test k8s namespace
    )
    
    # 3. Verify steps completed
    assert result['data_collection']['status'] == 'success'
    assert result['data_validation']['status'] == 'success'
    assert result['model_training']['status'] == 'success'
    assert result['model_validation']['status'] in ['success', 'rejected']
    
    # 4. If validation passed, verify deployment triggered
    if result['model_validation']['deploy_new_model'] == 'true':
        assert result['deployment']['status'] == 'success'
        assert result['deployment']['deployed'] == True
    
    # 5. Verify Slack notification sent
    assert result['monitoring']['notification_sent'] == True
```

---

### 3. Validation Gate Test (CRITICAL)

```python
# tests/test_model_validation_gate.py

def test_validation_gate_rejects_worse_model():
    """Verifica que gate REJEITA modelo pior."""
    
    # Current model: F1 = 0.98
    # New model: F1 = 0.96 (2pp pior)
    
    mock_current_model = create_mock_model(f1=0.98)
    mock_new_model = create_mock_model(f1=0.96)
    
    result = validate_new_model(
        new_model_path=save_model(mock_new_model),
        current_model_version='v7.0',
        test_set_path='s3://ytcaption-test-set/v1/',
        min_f1_improvement=-0.01  # Tolera 1pp de queda
    )
    
    # Gate deve rejeitar (2pp > 1pp threshold)
    assert result['deploy_new_model'] == 'false'
    assert 'REJECTED' in result['decision_reason']


def test_validation_gate_accepts_better_model():
    """Verifica que gate ACEITA modelo melhor."""
    
    # Current model: F1 = 0.98
    # New model: F1 = 0.985 (0.5pp melhor)
    
    mock_current_model = create_mock_model(f1=0.98)
    mock_new_model = create_mock_model(f1=0.985)
    
    result = validate_new_model(
        new_model_path=save_model(mock_new_model),
        current_model_version='v7.0',
        test_set_path='s3://ytcaption-test-set/v1/',
        min_f1_improvement=-0.01
    )
    
    # Gate deve aceitar
    assert result['deploy_new_model'] == 'true'
    assert 'APPROVED' in result['decision_reason']


def test_validation_gate_accepts_small_regression():
    """Verifica que gate ACEITA regressão pequena (dentro de tolerância)."""
    
    # Current model: F1 = 0.980
    # New model: F1 = 0.975 (0.5pp pior, mas < 1pp threshold)
    
    mock_current_model = create_mock_model(f1=0.980)
    mock_new_model = create_mock_model(f1=0.975)
    
    result = validate_new_model(
        new_model_path=save_model(mock_new_model),
        current_model_version='v7.0',
        test_set_path='s3://ytcaption-test-set/v1/',
        min_f1_improvement=-0.01  # Tolera 1pp
    )
    
    # Gate deve aceitar (0.5pp < 1pp threshold)
    assert result['deploy_new_model'] == 'true'
```

---

## Exemplo de Execução (E2E)

```bash
# 1. Deploy pipeline to Kubeflow
$ python pipeline/retraining_pipeline.py
✅ Pipeline compiled: retraining_pipeline.yaml

$ kubectl apply -f config/kubeflow_pipeline.yaml
pipeline.kubeflow.org/ytcaption-retraining created

# 2. Trigger retraining (manual)
$ python pipeline/trigger_retraining.py \
    --reason "weekly_scheduled" \
    --data-start-date "2024-11-01" \
    --data-end-date "2024-12-31"

🚀 Triggering retraining pipeline...
   Pipeline ID: 12345abc
   View at: https://kubeflow.example.com/pipelines/12345abc

# 3. Pipeline executes (2-4h total)

[Step 1/8] Data Collection... ✅ (10 min)
  → Collected 8,234 samples (6,123 proxy labels, 2,111 human audits)

[Step 2/8] Data Validation... ✅ (5 min)
  → Schema valid, 0 missing labels, 0.2% duplicates, 45/55 balance

[Step 3/8] Feature Engineering... ✅ (8 min)
  → Train: 4,940 | Val: 1,647 | Test: 1,647

[Step 4/8] Model Training... ✅ (45 min)
  → LightGBM trained, Val F1: 0.981

[Step 5/8] Model Calibration... ✅ (5 min)
  → Brier: 0.085 → 0.042 (improved)

[Step 6/8] Model Validation... ✅ (12 min)
  → Current model (v7.0): F1 = 0.978
  → New model (v20241225): F1 = 0.983 (+0.005)
  → Gate: PASSED ✅ (all thresholds met)

[Step 7/8] Deployment... ✅ (30s)
  → Canary deployment started: v20241225 (10% traffic)

[Step 8/8] Monitoring... ✅ (1s)
  → Slack notification sent

🎉 Pipeline completed successfully!

# 4. Slack notification received:

✅ Model Retraining SUCCESSFUL

New model deployed: v20241225_143022
F1 improvement: +0.0050
Precision: 0.9842
Recall: 0.9819

Canary deployment started (10% traffic).
Monitoring for 4h before full rollout.
```

---

## Rollback Strategy

### Cenário: Novo modelo degrada em produção (detectado após canary)

```python
# app/monitoring/auto_rollback.py

class AutoRollback:
    """
    Monitora modelo em canary e rollback automático se degradação.
    """
    
    def monitor_canary(self, canary_version: str, monitoring_duration_hours: int = 4):
        """
        Monitora modelo canary por N horas.
        
        Se drift > threshold OU error rate > threshold OU latency > threshold:
          → Rollback automático
        """
        
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=monitoring_duration_hours)
        
        drift_detector = DriftDetector()
        
        while datetime.now() < end_time:
            # 1. Check feature drift (canary vs reference)
            drift_report = drift_detector.detect_drift(
                reference_data=load_reference_data(),
                production_data=load_canary_data(canary_version, last_n_minutes=30)
            )
            
            # 2. Check error rate
            error_rate = get_canary_error_rate(canary_version)
            
            # 3. Check latency
            latency_p95 = get_canary_latency_p95(canary_version)
            
            # 4. Rollback conditions
            if drift_report['feature_drift_detected']:
                self.rollback(canary_version, reason='feature_drift')
                return False
            
            if error_rate > 0.05:  # 5% error rate
                self.rollback(canary_version, reason='high_error_rate')
                return False
            
            if latency_p95 > 20:  # 20s P95
                self.rollback(canary_version, reason='high_latency')
                return False
            
            # Sleep 5 min before next check
            time.sleep(300)
        
        # Monitoring completo, sem issues → promote to 100%
        self.promote_canary(canary_version)
        return True
    
    def rollback(self, canary_version: str, reason: str):
        """Rollback automático."""
        
        print(f"🔴 Rollback triggered: {reason}")
        
        # 1. Scale canary to 0%
        subprocess.run([
            'kubectl', 'scale', 'deployment/subtitle-detector-canary',
            '--replicas=0', '-n', 'production'
        ])
        
        # 2. Route 100% traffic to stable version
        # (update Istio VirtualService)
        
        # 3. Notify Slack
        send_slack_notification(
            f"🔴 **ROLLBACK**: Canary {canary_version} rolled back\nReason: {reason}"
        )
    
    def promote_canary(self, canary_version: str):
        """Promote canary to 100% após monitoring bem-sucedido."""
        
        print(f"✅ Canary {canary_version} promoted to 100%")
        
        # Gradual: 10% → 50% → 100% (cada etapa: 30 min monitoring)
        for traffic_pct in [50, 100]:
            update_traffic_split(canary_pct=traffic_pct)
            time.sleep(1800)  # 30 min
            
            # Check se ainda ok
            if get_canary_error_rate(canary_version) > 0.05:
                self.rollback(canary_version, reason='error_rate_during_promotion')
                return
        
        # Sucesso! Canary agora é stable
        mark_as_stable(canary_version)
        send_slack_notification(
            f"✅ **Canary promoted**: {canary_version} now serving 100% traffic"
        )
```

---

## Definição de Sucesso (Sprint 09)

Sprint 09 **ACEITA** se:

✅ **Pipeline completo funciona end-to-end**:
  - Data collection → validation → training → calibration → validation gate → deployment
  - Tempo total <8h (viável rodar overnight)

✅ **Validation gate funciona**:
  - Novo modelo deployd **SE E SOMENTE SE** F1 >= current - 0.01
  - Caso contrário, rollback automático

✅ **Rollback automático funciona**:
  - Canary monitorado por 4h
  - Rollback se drift/error_rate/latency > threshold

✅ **Drift detection trigger funciona**:
  - Sprint 08 detecta drift → Sprint 09 pipeline triggered automaticamente
  - Latência <1h entre detecção e trigger

✅ **Testes passam**:
  - Unit tests: 100% cobertura de componentes críticos
  - Integration test: pipeline E2E com mock data
  - Validation gate test: aceita melhor, rejeita pior

---

## Próximos Passos (Após Sprint 09)

- **Sprint 10**: Feature Engineering V2 (adicionar novos sinais: áudio fingerprinting, NLP em títulos)
- **Sprint 11**: Model Explainability (SHAP values, feature importance reporting)
- **Sprint 12**: Cost Optimization (reduzir custos de infraestrutura, otimizar batch processing)

---

## Referências

- [Google MLOps Best Practices](https://cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning)
- [Kubeflow Pipelines Documentation](https://www.kubeflow.org/docs/components/pipelines/)
- [Continuous Training in Production ML](https://www.oreilly.com/library/view/building-machine-learning/9781492053187/)
- Sprint 08: Validation & Production (drift detection)
- Sprint 07: Calibration (Platt scaling + threshold tuning)
- Sprint 05: Model Training (LightGBM + hyperparameter tuning)

---

**Status**: 📋 DocumentationComplete  
**Próximo Sprint**: Sprint 10 (Feature Engineering V2)  
