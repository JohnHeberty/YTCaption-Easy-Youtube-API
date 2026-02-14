# Feature Schema V1.0 - Fonte Única de Verdade

**Versão**: 1.0  
**Data**: 2026-02-13  
**Owner**: Sprints 04-05 (Feature Extraction + Temporal Aggregation)  
**Status**: **OFICIAL - Schema Fixo para Sprints 06-08**

---

## 🎯 Objetivo

Este documento define o **schema oficial de 56 features** usado pelo classificador (Sprint 06), calibração (Sprint 07) e validação (Sprint 08).

**REGRA CRÍTICA**: Qualquer mudança neste schema requer:
1. ✅ Revalidação completa no holdout test set (Sprint 00)
2. ✅ Retreino do classificador (Sprint 06)
3. ✅ Recalibração (Sprint 07)
4. ✅ Aprovação de 2+ reviewers

---

## 📊 Schema Oficial: 56 Features

### Composição

```
Total: 56 features
├─ 45 features espaciais (15 base × 3 agregações: mean/std/max)
└─ 11 features temporais
```

---

### 1️⃣ Features Espaciais (45 total)

**15 features base** extraídas por frame (Sprint 04):

#### Categoria 1: Basic Stats (5 features)
| # | Nome | Descrição | Range | Dtype |
|---|------|-----------|-------|-------|
| 1 | `num_detections` | Número de detecções OCR por frame | [0, 50] | int |
| 2 | `avg_confidence` | Confiança média OCR | [0.0, 1.0] | float |
| 3 | `max_confidence` | Confiança máxima OCR | [0.0, 1.0] | float |
| 4 | `min_confidence` | Confiança mínima OCR | [0.0, 1.0] | float |
| 5 | `std_confidence` | Desvio padrão de confiança | [0.0, 0.5] | float |

#### Categoria 2: Position Features (2 features)
| # | Nome | Descrição | Range | Dtype |
|---|------|-----------|-------|-------|
| 6 | `avg_position_y` | Posição Y média normalizada (0=top, 1=bottom) | [0.0, 1.0] | float |
| 7 | `bottom_percentage` | % detecções no bottom 20% do frame | [0.0, 1.0] | float |

#### Categoria 3: Size Features (3 features)
| # | Nome | Descrição | Range | Dtype |
|---|------|-----------|-------|-------|
| 8 | `total_area` | Área total bboxes / área frame | [0.0, 1.0] | float |
| 9 | `avg_bbox_area` | Área média bbox / área frame | [0.0, 0.5] | float |
| 10 | `avg_aspect_ratio` | Aspect ratio médio (width/height) | [1.0, 20.0] | float |

#### Categoria 4: Text Features (3 features)
| # | Nome | Descrição | Range | Dtype |
|---|------|-----------|-------|-------|
| 11 | `avg_text_length` | Tamanho médio texto (caracteres) | [0, 100] | int |
| 12 | `total_text_length` | Total de caracteres | [0, 500] | int |
| 13 | `std_text_length` | Desvio padrão tamanho texto | [0.0, 50.0] | float |

#### Categoria 5: Spatial Distribution (2 features)
| # | Nome | Descrição | Range | Dtype |
|---|------|-----------|-------|-------|
| 14 | `vertical_spread` | Spread vertical (max_y - min_y) / height | [0.0, 1.0] | float |
| 15 | `std_position_y` | Desvio padrão posição Y | [0.0, 0.5] | float |

**Agregação por Vídeo (Sprint 04):**

Para cada uma das 15 features base, computamos 3 estatísticas sobre os 30 frames:
- `<feature>_mean`: Média
- `<feature>_std`: Desvio padrão
- `<feature>_max`: Máximo

**Resultado**: 15 × 3 = **45 features espaciais**

**Exemplo**:
```python
# Frame-level features (15 per frame)
frame_features = [
    num_detections=3,
    avg_confidence=0.85,
    max_confidence=0.92,
    ...
]

# Video-level aggregated (45 total)
video_features = [
    num_detections_mean=3.2,
    num_detections_std=1.1,
    num_detections_max=5,
    avg_confidence_mean=0.847,
    avg_confidence_std=0.073,
    avg_confidence_max=0.925,
    ...  # 45 total
]
```

---

### 2️⃣ Features Temporais (11 total)

**11 features temporais** agregadas sobre 30 frames (Sprint 05):

| # | Nome | Descrição | Range | Dtype |
|---|------|-----------|-------|-------|
| 46 | `persistence_ratio` | % frames com detecções OCR | [0.0, 1.0] | float |
| 47 | `max_consecutive_frames` | Máximo de frames consecutivos com texto | [0, 30] | int |
| 48 | `num_runs` | Número de "runs" (aparições/desaparições) | [0, 15] | int |
| 49 | `bbox_iou_consecutive_mean` | IOU médio entre bboxes consecutivos | [0.0, 1.0] | float |
| 50 | `bbox_stability_y_mean` | Posição Y média (estabilidade vertical) | [0.0, 1.0] | float |
| 51 | `bbox_stability_y_std` | Desvio Y (variação vertical) | [0.0, 0.5] | float |
| 52 | `text_similarity_consecutive_mean` | Similaridade texto consecutivo (Levenshtein) | [0.0, 1.0] | float |
| 53 | `text_similarity_consecutive_std` | Desvio similaridade texto | [0.0, 0.5] | float |
| 54 | `text_similarity_overall` | Similaridade texto geral (frames) | [0.0, 1.0] | float |
| 55 | `avg_confidence_temporal_mean` | Confiança média temporal | [0.0, 1.0] | float |
| 56 | `avg_confidence_temporal_std` | Desvio confiança temporal | [0.0, 0.5] | float |

**Total**: **56 features** (45 espaciais + 11 temporais)

---

## 🔍 Validação de Schema

### Implementação (Sprint 06)

```python
# app/models/feature_schema.py

FEATURE_SCHEMA_V1 = {
    "version": "1.0",
    "total_features": 56,
    "spatial_features": 45,
    "temporal_features": 11,
    
    "feature_names": [
        # Spatial aggregated (45)
        "num_detections_mean", "num_detections_std", "num_detections_max",
        "avg_confidence_mean", "avg_confidence_std", "avg_confidence_max",
        "max_confidence_mean", "max_confidence_std", "max_confidence_max",
        "min_confidence_mean", "min_confidence_std", "min_confidence_max",
        "std_confidence_mean", "std_confidence_std", "std_confidence_max",
        "avg_position_y_mean", "avg_position_y_std", "avg_position_y_max",
        "bottom_percentage_mean", "bottom_percentage_std", "bottom_percentage_max",
        "total_area_mean", "total_area_std", "total_area_max",
        "avg_bbox_area_mean", "avg_bbox_area_std", "avg_bbox_area_max",
        "avg_aspect_ratio_mean", "avg_aspect_ratio_std", "avg_aspect_ratio_max",
        "avg_text_length_mean", "avg_text_length_std", "avg_text_length_max",
        "total_text_length_mean", "total_text_length_std", "total_text_length_max",
        "std_text_length_mean", "std_text_length_std", "std_text_length_max",
        "vertical_spread_mean", "vertical_spread_std", "vertical_spread_max",
        "std_position_y_mean", "std_position_y_std", "std_position_y_max",
        
        # Temporal (11)
        "persistence_ratio",
        "max_consecutive_frames",
        "num_runs",
        "bbox_iou_consecutive_mean",
        "bbox_stability_y_mean",
        "bbox_stability_y_std",
        "text_similarity_consecutive_mean",
        "text_similarity_consecutive_std",
        "text_similarity_overall",
        "avg_confidence_temporal_mean",
        "avg_confidence_temporal_std",
    ],
    
    "dtypes": {
        # Spatial
        **{f"{base}_mean": "float32" for base in ["avg_confidence", "max_confidence", ...]},
        **{f"{base}_std": "float32" for base in [...]},
        **{f"{base}_max": "float32" for base in [...]},
        
        # Temporal
        "persistence_ratio": "float32",
        "max_consecutive_frames": "int32",
        "num_runs": "int32",
        ...
    },
    
    "ranges": {
        "num_detections_mean": (0, 50),
        "avg_confidence_mean": (0.0, 1.0),
        "persistence_ratio": (0.0, 1.0),
        ...
    }
}


def validate_feature_schema(features: np.ndarray) -> None:
    """
    Valida que features seguem o schema oficial.
    
    Raises:
        ValueError: Se schema não bate
    """
    if features.shape[-1] != 56:
        raise ValueError(
            f"Expected 56 features, got {features.shape[-1]}. "
            "Schema violation! Check FEATURE_SCHEMA.md"
        )
    
    # Validate ranges (exemplo)
    if not (0.0 <= features[..., 0] <= 50.0).all():  # num_detections_mean
        raise ValueError("num_detections_mean out of range [0, 50]")
    
    # ... mais validações
```

### Testes Automatizados (Great Expectations)

```python
# tests/data_quality/test_feature_schema.py

import great_expectations as gx

def test_feature_schema_v1():
    """
    Valida schema usando Great Expectations.
    """
    context = gx.get_context()
    
    # Load dataset
    batch = context.get_batch(
        datasource_name="features_v1",
        data_asset_name="training_features"
    )
    
    # Expectations
    batch.expect_table_column_count_to_equal(56)
    
    batch.expect_column_values_to_be_between(
        column="num_detections_mean",
        min_value=0,
        max_value=50
    )
    
    batch.expect_column_values_to_be_between(
        column="avg_confidence_mean",
        min_value=0.0,
        max_value=1.0
    )
    
    batch.expect_column_values_to_be_between(
        column="persistence_ratio",
        min_value=0.0,
        max_value=1.0
    )
    
    # ... 56 expectations total
    
    results = batch.validate()
    assert results.success, f"Schema validation failed: {results}"
```

---

## 📝 Changelog

### V1.0 (2026-02-13)
- ✅ Schema inicial definido: 56 features (45 espaciais + 11 temporais)
- ✅ Sprints 04-05 implementadas e validadas
- ✅ Documentação completa com ranges, dtypes, validação
- ✅ Aprovado para uso em Sprints 06-08

### Próximas Versões

**V2.0** (Sprint 10 - Fase 2, opcional):
- +14 features visuais avançadas (top subtitle handling, contrast features, stylized text)
- Total: 70 features
- Requer revalidação completa + retreino

---

## ⚠️ Notas Críticas

1. **Schema Fixo**: Sprints 06-08 dependem de exatamente 56 features. Não mudar sem aprovação.

2. **Ordem Importa**: Features devem estar na ordem especificada (array indexing em produção).

3. **Validação Obrigatória**: Todo pipeline deve validar schema antes de passar para classifier.

4. **Backward Compatibility**: Se mudar para V2.0, manter suporte a V1.0 para rollback.

5. **Data Quality Tests**: Rodar Great Expectations em CI/CD para detectar schema drift.

---

## 🔗 Referências

- **Sprint 04**: [Feature Extraction](sprint_04_feature_extraction.md) - Define 15 features base + agregação
- **Sprint 05**: [Temporal Aggregation](sprint_05_temporal_aggregation.md) - Define 11 features temporais
- **Sprint 06**: [Lightweight Classifier](sprint_06_lightweight_classifier.md) - Consome schema V1.0
- **Sprint 00**: [Baseline + Dataset](sprint_00_baseline_dataset_harness.md) - Dataset para validação
- **Great Expectations**: [Data Quality Docs](https://docs.greatexpectations.io/docs/reference/learn/data_quality_use_cases/schema/)
