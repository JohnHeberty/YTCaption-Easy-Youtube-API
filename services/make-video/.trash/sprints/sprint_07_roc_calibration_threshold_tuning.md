# Sprint 07: ROC Calibration & Threshold Tuning

**Objetivo**: Calibrar probabilidades do classificador e otimizar threshold final via ROC curve  
**Impacto Esperado**: +1-3% (precision boost via threshold ótimo + calibração)  
**Criticidade**: ⭐⭐⭐ IMPORTANTE (Finaliza tuning do sistema)  
**Data**: 2026-02-13  
**Status**: 🟡 Aguardando Sprint 06  
**Dependências**: Sprint 06 (classificador treinado), Dataset validação (50+ vídeos)

---

## 1️⃣ Objetivo Técnico Claro

### Problema Específico

O classificador da Sprint 06 retorna **probabilidades não-calibradas**:

```python
# OUTPUT Sprint 06 (LogisticRegression)
probability = 0.92  # Mas isso NÃO significa "92% de chance real"
```

**Problemas Críticos:**

### 1) **Probabilidades não-calibradas**

LogisticRegression **não garante** que `predict_proba()` seja calibrado:

```
Vídeo A: proba=0.80 → ground truth: True  (80% ok? ✅)
Vídeo B: proba=0.80 → ground truth: False (80% ok? ❌)
Vídeo C: proba=0.80 → ground truth: True  (80% ok? ✅)
Vídeo D: proba=0.80 → ground truth: False (80% ok? ❌)

Análise de 100 vídeos com proba ≈ 0.80:
  - Positivos reais: 45 (esperado: 80, mas foi 45!)
  - Calibração: 45% != 80% (descalibrado!)
```

**Problema**: Probabilidade `0.80` deveria significar "80% de chance", mas na prática é **45%**.

**Impacto**:
- Decisões baseadas em probabilidade ficam **erradas**
- Threshold selecionado pode ser **subótimo**
- Dificulta interpretação para usuários ("92% confiável" é mentira)

---

### 2) **Threshold selecionado na Sprint 06 é "good enough", não "ótimo"**

Sprint 06 seleciona threshold via **max F1**:

```python
# Sprint 06: grid search simples
best_threshold = 0.5  # Inicial
for threshold in np.arange(0.30, 0.91, 0.05):  # Step 0.05 (grosso!)
    f1 = compute_f1(y_val, y_val_proba >= threshold)
    if f1 > best_f1:
        best_threshold = threshold
```

**Problemas**:
1. **Step 0.05 é grosso**: pode perder threshold ótimo entre 0.75 e 0.80
2. **Métrica fixa (F1)**: não considera trade-off precision/recall
3. **Sem análise de custo**: FP e FN têm custo diferente (negócio)

**Exemplo**:
```
Threshold 0.75: Precision=94%, Recall=96%, F1=95.0%
Threshold 0.78: Precision=95%, Recall=95%, F1=95.0%  ← Tie!
Threshold 0.80: Precision=96%, Recall=94%, F1=94.9%

Sprint 06 escolhe: 0.75 ou 0.78 (primeiro com max F1)
Sprint 07 escolhe: 0.80 (se custo de FP > custo de FN)
```

---

### 3) **Sem análise de trade-off Precision/Recall**

Sistema atual não **visualiza** nem **documenta** o trade-off:

```
Threshold 0.50: Precision=88%, Recall=98%  (mais recall, aceita FP)
Threshold 0.75: Precision=95%, Recall=95%  (balanceado)
Threshold 0.90: Precision=98%, Recall=88%  (mais precision, perde recall)

Qual escolher? Depende do CUSTO DO ERRO (negócio), não apenas F1!
```

**Custo do erro (exemplo real):**
- **FP (falso positivo)**: Vídeo sem legenda classificado como "tem legenda"
  - Usuário tenta extrair → processo falha → frustração → custo **BAIXO** (retry)
  
- **FN (falso negativo)**: Vídeo com legenda classificado como "sem legenda"
  - Sistema não processa → **PERDE LEGENDA** → usuário não sabe que havia legenda → custo **ALTO** (informação perdida)

**Se FN custa 3× mais que FP**, threshold ótimo **não é** max F1, é **max cost-weighted metric**.

---

### 4) **Sem monitoramento de drift**

Após deploy, sistema **não monitora** se probabilidades continuam calibradas:

```
Semana 1: proba=0.80 → acurácia 78% (ok)
Semana 4: proba=0.80 → acurácia 65% (descalibrado!)  ← Drift detectado!

Causa possível: novos tipos de vídeos (TikTok, shorts) não vistos no treino
```

Sprint 07 prepara **monitoramento de calibração** em produção.

---

### Métrica Impactada

| Métrica | After Sprint 06 | Alvo Sprint 07 | Validação |
|---------|----------------|----------------|-----------|
| **Precision** | ~97% | ~98% (+1%) | Via threshold ótimo calibrado |
| **Recall** | ~97% | ~97% (mantém) | Garante no drop |
| **FPR** | ~0.5% | ~0.3% (-0.2%) | Threshold mais conservador se custo FP alto |
| **F1 Score** | ~97% | ~97.5% (+0.5%) | Balanço precision/recall |
| **Brier Score** | ~0.08 | ~0.04 (-0.04) | Melhora calibração (0=perfeito) |
| **ECE (Expected Calibration Error)** | ~0.12 | ~0.05 (-0.07) | Probabilidades mais confiáveis |

**Nota Importante:**

Sprint 07 é **refinamento** (vs Sprint 05-06 que foram transformacionais).

Ganho esperado +1-3%:
- **Cenário conservador**: +0.5-1% (calibração melhora pouco)
- **Cenário realista**: +1-2% (threshold ótimo + calibração)
- **Cenário otimista**: +2-3% (se descalibração inicial for severa)

Impacto principal: **confiabilidade** (probabilidades corretas) + **interpretabilidade**.

---

## 2️⃣ Hipótese Técnica

### Por Que Calibração Aumenta Performance?

**Problema Raiz**: LogisticRegression minimiza **log-loss**, não **calibração**.

**Fato Empírico (ML Theory):**

LogReg pode ter **alta acurácia** mas **probabilidades descalibradas**:

```
Modelo A: Accuracy=95%, Brier Score=0.10 (descalibrado)
Modelo B: Accuracy=95%, Brier Score=0.04 (calibrado)

Ambos têm mesma accuracy, mas B tem probabilidades confiáveis!
```

**Hipótese:**

Ao **calibrar probabilidades** via Platt scaling ou Isotonic regression:
1. Probabilidades refletem **chance real** (interpretável)
2. Threshold selecionado via ROC é **mais robusto**
3. Decisões baseadas em probabilidade ficam **corretas**

---

### Base Conceitual (Calibration Theory)

#### Definição: Probabilidade Calibrada

Um modelo está **calibrado** se:

$$
P(\text{Positive} \mid \hat{p} = p) = p
$$

Ou seja: entre todos os exemplos com probabilidade predita $\hat{p} = 0.80$, **80% devem ser positivos**.

**Teste de calibração (Brier Score):**

$$
\text{Brier Score} = \frac{1}{N} \sum_{i=1}^{N} (\hat{p}_i - y_i)^2
$$

- 0 = perfeito (probabilidades exatas)
- 1 = pior (probabilidades completamente erradas)

**Teste de calibração (Expected Calibration Error - ECE):**

$$
\text{ECE} = \sum_{b=1}^{B} \frac{n_b}{N} \left| \text{acc}(b) - \text{conf}(b) \right|
$$

onde:
- $B$: número de bins (ex: 10 bins de 0-0.1, 0.1-0.2, ..., 0.9-1.0)
- $n_b$: número de exemplos no bin $b$
- $\text{acc}(b)$: acurácia no bin $b$
- $\text{conf}(b)$: confiança média no bin $b$

**ECE = 0** → perfeitamente calibrado.

---

#### Método 1: Platt Scaling

**Ideia**: Treinar regressão logística **sobre as probabilidades** (meta-modelo):

$$
\hat{p}_{\text{calibrated}} = \sigma(a \cdot \log \frac{\hat{p}}{1 - \hat{p}} + b)
$$

onde $\sigma$ é sigmoid, $a$ e $b$ são aprendidos em **validation set separado**.

**Vantagens**:
- ✅ Rápido (2 parâmetros apenas)
- ✅ Funciona bem para LogisticRegression
- ✅ Preserva ordem (ranking)

**Desvantagens**:
- ❌ Assume forma paramétrica (logística)
- ❌ Pode não corrigir descalibração não-linear

---

#### Método 2: Isotonic Regression

**Ideia**: Mapear probabilidades via **função monotônica não-paramétrica**:

$$
\hat{p}_{\text{calibrated}} = f(\hat{p})
$$

onde $f$ é piecewise constant monotonic function aprendida via isotonic regression.

**Vantagens**:
- ✅ Mais flexível (captura não-linearidades)
- ✅ Funciona bem para tree-based models (XGBoost)
- ✅ Sem suposições paramétricas

**Desvantagens**:
- ❌ Precisa de mais dados (>100 samples validation)
- ❌ Pode overfit com poucos dados

---

#### Método 3: Beta Calibration (Estado da Arte)

**Ideia**: Usa distribuição Beta (mais flexível que Platt):

$$
\hat{p}_{\text{calibrated}} = \text{Beta}(\hat{p}; a, b, c)
$$

**Sprint 07**: Usaremos **Platt Scaling** (LogReg) ou **Isotonic** (se >100 validation).

---

### Threshold Tuning via ROC Curve

**Problema**: Threshold fixo (0.5 ou max F1) **não considera custo do erro**.

**Solução**: ROC curve + análise de custo.

#### ROC Curve (Receiver Operating Characteristic)

Plot de **TPR vs FPR** variando threshold:

```
TPR = True Positive Rate = TP / (TP + FN)  # Recall
FPR = False Positive Rate = FP / (FP + TN)

Threshold 0.0: TPR=1.00, FPR=1.00 (classifica tudo como positivo)
Threshold 0.5: TPR=0.95, FPR=0.05 (balanceado)
Threshold 1.0: TPR=0.00, FPR=0.00 (classifica tudo como negativo)
```

**AUC (Area Under Curve)**: métrica de performance global (0.5=random, 1.0=perfeito).

---

#### Seleção de Threshold via Custo

**Fórmula de custo total:**

$$
\text{Cost} = C_{\text{FP}} \cdot \text{FP} + C_{\text{FN}} \cdot \text{FN}
$$

onde:
- $C_{\text{FP}}$: custo de falso positivo (ex: 1.0)
- $C_{\text{FN}}$: custo de falso negativo (ex: 3.0)

**Threshold ótimo**: minimiza custo total no validation set.

**Exemplo:**
```python
# Assumindo C_FN = 3.0, C_FP = 1.0

best_cost = float('inf')
best_threshold = 0.5

for threshold in np.arange(0.0, 1.0, 0.01):  # Step 0.01 (fino!)
    y_pred = (y_proba >= threshold).astype(int)
    
    fp = ((y_pred == 1) & (y_true == 0)).sum()
    fn = ((y_pred == 0) & (y_true == 1)).sum()
    
    cost = 1.0 * fp + 3.0 * fn
    
    if cost < best_cost:
        best_cost = cost
        best_threshold = threshold

# Resultado: threshold ≈ 0.65 (mais conservador que 0.50)
```

---

### Matemática do Impacto

**Assumindo:**
- Modelo Sprint 06: Brier Score = 0.08, ECE = 0.12
- Após Platt Scaling: Brier Score = 0.04, ECE = 0.05
- Threshold mudou de 0.75 (max F1) para 0.68 (min custo)

**Precision Boost (via threshold ótimo):**

```
Threshold 0.75: Precision=95%, FP=5%
Threshold 0.68: Precision=96%, FP=4%

ΔPrecision ≈ +1% ✅
```

**Confiabilidade Boost (via calibração):**

```
Calibração antes: 80% dos vídeos com proba=0.80 são positivos → 60% acerto
Calibração depois: 80% dos vídeos com proba_calibrated=0.80 são positivos → 78% acerto

Melhoria: +18 pontos percentuais em confiabilidade ✅
```

---

## 3️⃣ Alterações Arquiteturais

### Mudanças em Pipeline

**Antes** (Sprint 06):
```
Classifier → predict_proba() → threshold fixo → Decision
```

**Depois** (Sprint 07):
```
Classifier → predict_proba() → Calibrator (Platt/Isotonic) → proba_calibrated → threshold ótimo (ROC) → Decision
```

**Novas Funções:**
- `calibrate_probabilities()`: Aplica Platt ou Isotonic calibration
- `plot_calibration_curve()`: Visualiza calibração (reliability diagram)
- `plot_roc_curve()`: Visualiza ROC + threshold ótimo
- `select_optimal_threshold()`: Seleciona via custo ou métrica customizada
- `compute_calibration_metrics()`: Calcula Brier Score, ECE

---

### Mudanças em Estrutura

**Extensão: `SubtitleClassifier` (app/ml/subtitle_classifier.py)**

```python
class SubtitleClassifier:
    """
    ... (código Sprint 06) ...
    """
    
    def __init__(self, ...):
        ...
        self.calibrator = None  # Platt ou Isotonic
        self.calibration_method = None  # 'platt' ou 'isotonic'
    
    def calibrate(
        self,
        X_cal: np.ndarray,
        y_cal: np.ndarray,
        method: str = 'platt'
    ):
        """
        Calibra probabilidades em calibration set SEPARADO.
        
        Args:
            X_cal: Features de calibração (não usado em treino!)
            y_cal: Labels de calibração
            method: 'platt' ou 'isotonic'
        """
        ...
    
    def predict_proba_calibrated(
        self,
        features: np.ndarray
    ) -> float:
        """
        Prediz probabilidade CALIBRADA.
        
        Returns:
            Probability calibrada [0, 1]
        """
        ...
    
    def select_optimal_threshold(
        self,
        X_val: np.ndarray,
        y_val: np.ndarray,
        cost_fp: float = 1.0,
        cost_fn: float = 1.0,
        metric: str = 'cost'  # 'cost', 'f1', 'balanced_accuracy'
    ) -> float:
        """
        Seleciona threshold ótimo via ROC curve.
        
        Args:
            X_val: Features de validação
            y_val: Labels de validação
            cost_fp: Custo de falso positivo
            cost_fn: Custo de falso negativo
            metric: Métrica para otimizar
        
        Returns:
            Threshold ótimo
        """
        ...
```

---

### Mudanças em Parâmetros

| Parâmetro | Sprint 06 | Sprint 07 | Justificativa |
|-----------|----------|----------|---------------|
| `calibration_method` | N/A | 'platt' ou 'isotonic' | Método de calibração |
| `threshold_selection` | 'max_f1' (grid 0.05) | 'min_cost' (grid 0.01) | Custo customizado |
| `cost_fp` | N/A | 1.0 (default) | Custo de FP |
| `cost_fn` | N/A | 3.0 (default - FN pior) | Custo de FN |

---

## 4️⃣ Mudanças de Código (Pseudo + Real)

### Pseudocódigo: Calibração + Threshold Tuning

```python
# CRITICAL: Pipeline com split ÚNICO e DISJUNTO (sem vazamento)
# Ordem: train → cal → val → test (sem reutilização)

# FASE 0: Split único em 4 conjuntos disjuntos
from sklearn.model_selection import train_test_split

# Split 1: test set (20%)
X_trainvalcal, X_test, y_trainvalcal, y_test = train_test_split(
    X_all, y_all,
    test_size=0.20,
    stratify=y_all,
    random_state=42
)

# Split 2: cal set (15% do trainvalcal = 12% do total)
X_trainval, X_cal, y_trainval, y_cal = train_test_split(
    X_trainvalcal, y_trainvalcal,
    test_size=0.15,
    stratify=y_trainvalcal,
    random_state=42
)

# Split 3: val set (20% do trainval = 13.6% do total)
X_train, X_val, y_train, y_val = train_test_split(
    X_trainval, y_trainval,
    test_size=0.20,
    stratify=y_trainval,
    random_state=42
)

print(f"Split disjunto:")
print(f"  Train: {len(X_train)} samples (54.4% - treino do modelo)")
print(f"  Cal:   {len(X_cal)} samples (12.0% - calibração)")
print(f"  Val:   {len(X_val)} samples (13.6% - threshold tuning)")
print(f"  Test:  {len(X_test)} samples (20.0% - avaliação final)")

# FASE 1: Treinar modelo DO ZERO (dentro da Sprint 07)
# CRITICAL: NÃO carregar modelo pronto (evita vazamento)
clf = SubtitleClassifier(model_type='logistic')
clf.train(X_train, y_train)  # Treina SEM validação interna (será calibrado depois)

print(f"\nModelo treinado em {len(X_train)} samples")

# FASE 2: Calibração (cal set - NUNCA visto no treino)
# ⚠️ **CORREÇÃO P1 (FIX_OCR.md + scikit-learn best practices)**
# Isotonic regression NÃO é recomendada com amostras pequenas (<< 1000)
# Fonte: https://scikit-learn.org/stable/modules/calibration.html
# "Isotonic calibration is generally more powerful than parametric methods such as Platt scaling.
#  However, it tends to overfit the calibration set which is significantly smaller than the train set."
#  
# Recommendation sklearn docs: N_cal >> 1000 para isotonic ser seguro
# Com N_cal < 500, preferir Platt (sigmoid) por robustez

N_cal = len(X_cal)
if N_cal < 500:  # Threshold conservador (era 100, agora 500)
    calibration_method = 'platt'  # Mais robusto com poucos dados
    print(f"N_cal={N_cal} < 500 → usando Platt Scaling (robusto, recomendado por sklearn)")
    print(f"  Razão: Isotonic regression tende a overfit com N < 500")
else:
    calibration_method = 'platt'  # Default: SEMPRE Platt (mais seguro)
    print(f"N_cal={N_cal} ≥ 500 → usando Platt Scaling (default seguro)")
    print(f"  Nota: Isotonic poderia ser usado, mas Platt é mais robusto")
    print(f"  Se desejar isotonic explicitamente, mudar para method='isotonic' manual")

# Alternative: Force Platt always (safest)
# calibration_method = 'platt'  # Sempre Platt (mais conservador)

clf.calibrate(X_cal, y_cal, method=calibration_method, verbose=True)

# FASE 3: Threshold tuning (val set - NUNCA visto no treino/cal)
optimal_threshold = clf.select_optimal_threshold(
    X_val,
    y_val,
    cost_fp=1.0,
    cost_fn=3.0,  # FN custa 3× mais (exemplo)
    metric='cost',
    verbose=True
)

print(f"\nOptimal threshold: {optimal_threshold:.3f}")
clf.threshold = optimal_threshold

# FASE 4: Avaliação final no test set (NUNCA visto antes)
y_test_proba_uncal = clf.predict_proba(X_test)  # Uncalibrated
y_test_proba_cal = clf.predict_proba_calibrated(X_test)  # Calibrated
y_test_pred = (y_test_proba_cal >= clf.threshold).astype(int)

# Métricas de calibração
brier_uncal = compute_brier_score(y_test, y_test_proba_uncal)
brier_cal = compute_brier_score(y_test, y_test_proba_cal)
ece_uncal = compute_expected_calibration_error(y_test, y_test_proba_uncal)
ece_cal = compute_expected_calibration_error(y_test, y_test_proba_cal)

# AUC antes/depois (reportar, não assumir que mantém)
from sklearn.metrics import roc_auc_score, average_precision_score
auc_uncal = roc_auc_score(y_test, y_test_proba_uncal)
auc_cal = roc_auc_score(y_test, y_test_proba_cal)
pr_auc_uncal = average_precision_score(y_test, y_test_proba_uncal)
pr_auc_cal = average_precision_score(y_test, y_test_proba_cal)

print(f"\n{'='*60}")
print(f"CALIBRATION IMPACT")
print(f"{'='*60}")
print(f"Brier Score: {brier_uncal:.4f} → {brier_cal:.4f} (Δ={brier_uncal - brier_cal:.4f})")
print(f"ECE:         {ece_uncal:.4f} → {ece_cal:.4f} (Δ={ece_uncal - ece_cal:.4f})")
print(f"ROC-AUC:     {auc_uncal:.4f} → {auc_cal:.4f} (Δ={auc_cal - auc_uncal:.4f})")
print(f"PR-AUC:      {pr_auc_uncal:.4f} → {pr_auc_cal:.4f} (Δ={pr_auc_cal - pr_auc_uncal:.4f})")

# Plot
plot_calibration_curve(y_test, y_test_proba_uncal, y_test_proba_cal)
plot_roc_curve(y_test, y_test_proba_cal, threshold=optimal_threshold)

# FASE 5: Save model com calibrador + metadata
metadata = {
    'calibration_method': calibration_method,
    'n_calibration_samples': N_cal,
    'optimal_threshold': optimal_threshold,
    'brier_uncalibrated': float(brier_uncal),
    'brier_calibrated': float(brier_cal),
    'ece_uncalibrated': float(ece_uncal),
    'ece_calibrated': float(ece_cal),
    'roc_auc_uncalibrated': float(auc_uncal),
    'roc_auc_calibrated': float(auc_cal),
    'pr_auc_uncalibrated': float(pr_auc_uncal),
    'pr_auc_calibrated': float(pr_auc_cal),
}

clf.save("models/subtitle_classifier_calibrated_v1.pkl", metadata=metadata)
print(f"\n✅ Modelo salvo com calibração {calibration_method} e threshold {optimal_threshold:.3f}")
```

---

### Mudanças Reais (Código Completo)

#### Arquivo 1: `app/ml/subtitle_classifier.py` (ESTENDER)

**Novas Funções: Calibração**

```python
# Adicionar imports
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression

class SubtitleClassifier:
    """... (código Sprint 06) ..."""
    
    def __init__(self, ...):
        # ... (código Sprint 06) ...
        self.calibrator = None  # CalibratedClassifierCV ou IsotonicRegression
        self.calibration_method = None
        self.is_calibrated = False
    
    def calibrate(
        self,
        X_cal: np.ndarray,
        y_cal: np.ndarray,
        method: Literal['platt', 'isotonic', 'auto'] = 'auto',
        verbose: bool = True
    ):
        """
        Calibra probabilidades em calibration set SEPARADO.
        
        Args:
            X_cal: Features de calibração (N, 56)
            y_cal: Labels de calibração (N,)
            method: 'platt' (sigmoid), 'isotonic' (non-parametric), 'auto' (escolhe baseado em N)
            verbose: Print métricas
        
        Note:
            CRUCIAL: X_cal NÃO pode ter sido usado no treinamento do modelo base!
            Usar calibration set independente previne overfitting.
            
            Auto-selection rule:
              - N < 100: Platt Scaling (mais robusto com poucos dados)
              - N >= 100: Isotonic Regression (mais flexível com muitos dados)
        """
        if self.model is None:
            raise ValueError("Model not trained. Train first, then calibrate.")
        
        # Validate
        self.validate_feature_vector(X_cal)
        
        N_cal = len(X_cal)
        
        # Auto-select method based on calibration set size
        if method == 'auto':
            if N_cal < 100:
                method = 'platt'
                if verbose:
                    print(f"Auto-select: N_cal={N_cal} < 100 → using Platt Scaling (robust)")
            else:
                method = 'isotonic'
                if verbose:
                    print(f"Auto-select: N_cal={N_cal} >= 100 → using Isotonic Regression (flexible)")
        
        # Warning for small calibration sets
        if N_cal < 50:
            print(f"⚠️  WARNING: Calibration set very small (N={N_cal}). Results may be unreliable.")
            print(f"    Recommendation: Use at least 50-100 samples for calibration.")
        
        # Get uncalibrated probabilities
        if self.scaler is not None:
            X_cal_scaled = self.scaler.transform(X_cal)
        else:
            X_cal_scaled = X_cal
        
        y_proba_uncalibrated = self.model.predict_proba(X_cal_scaled)[:, 1]
        
        # Compute uncalibrated Brier Score
        brier_before = np.mean((y_proba_uncalibrated - y_cal) ** 2)
        
        # Calibrate
        if method == 'platt':
            # Platt scaling: fit logistic regression on predictions
            # Use robust solver and regularization for small samples
            from sklearn.linear_model import LogisticRegression
            
            self.calibrator = LogisticRegression(
                solver='lbfgs',
                max_iter=1000,
                C=1.0,  # L2 regularization (default)
                random_state=42
            )
            self.calibrator.fit(y_proba_uncalibrated.reshape(-1, 1), y_cal)
        
        elif method == 'isotonic':
            # Isotonic regression: fit monotonic function
            # Only use if N >= 100 (more data needed)
            if N_cal < 100:
                print(f"⚠️  WARNING: Isotonic with N={N_cal} < 100 may overfit. Consider 'platt'.")
            
            self.calibrator = IsotonicRegression(
                out_of_bounds='clip',
                increasing=True  # Ensure monotonicity
            )
            self.calibrator.fit(y_proba_uncalibrated, y_cal)
        
        else:
            raise ValueError(f"Unknown calibration method: {method}")
        
        self.calibration_method = method
        self.is_calibrated = True
        self.n_calibration_samples = N_cal
        
        # Get calibrated probabilities
        y_proba_calibrated = self._calibrate_proba(y_proba_uncalibrated)
        
        # Compute calibrated Brier Score
        brier_after = np.mean((y_proba_calibrated - y_cal) ** 2)
        
        if verbose:
            print(f"\nCalibration ({method}):")
            print(f"  N samples: {N_cal}")
            print(f"  Brier Score Before: {brier_before:.4f}")
            print(f"  Brier Score After:  {brier_after:.4f}")
            print(f"  Improvement: {brier_before - brier_after:.4f}")
    
    def _calibrate_proba(self, proba_uncalibrated: np.ndarray) -> np.ndarray:
        """
        Aplica calibrador nas probabilidades.
        
        Args:
            proba_uncalibrated: Probabilidades não-calibradas
        
        Returns:
            Probabilidades calibradas
        """
        if not self.is_calibrated:
            return proba_uncalibrated
        
        if self.calibration_method == 'platt':
            # Platt: predict via logistic regression
            proba_calibrated = self.calibrator.predict_proba(
                proba_uncalibrated.reshape(-1, 1)
            )[:, 1]
        elif self.calibration_method == 'isotonic':
            # Isotonic: transform via monotonic function
            proba_calibrated = self.calibrator.predict(proba_uncalibrated)
        else:
            proba_calibrated = proba_uncalibrated
        
        return np.clip(proba_calibrated, 0.0, 1.0)
    
    def predict_proba_calibrated(self, features: np.ndarray) -> float:
        """
        Prediz probabilidade CALIBRADA.
        
        Args:
            features: Feature vector (56,) ou (N, 56)
        
        Returns:
            Probability calibrada [0, 1]
        """
        # Get uncalibrated probability
        proba_uncalibrated = self.predict_proba(features)
        
        # Calibrate
        if self.is_calibrated:
            if isinstance(proba_uncalibrated, float):
                proba_uncalibrated = np.array([proba_uncalibrated])
            
            proba_calibrated = self._calibrate_proba(proba_uncalibrated)
            
            if proba_calibrated.shape[0] == 1:
                return float(proba_calibrated[0])
            return proba_calibrated
        else:
            return proba_uncalibrated
    
    def select_optimal_threshold(
        self,
        X_val: np.ndarray,
        y_val: np.ndarray,
        cost_fp: float = 1.0,
        cost_fn: float = 1.0,
        metric: Literal['cost', 'f1', 'balanced_accuracy', 'youden'] = 'cost',
        step: float = 0.01,
        verbose: bool = True
    ) -> float:
        """
        Seleciona threshold ótimo via ROC curve.
        
        Args:
            X_val: Features de validação (N, 56)
            y_val: Labels de validação (N,)
            cost_fp: Custo de falso positivo (default=1.0)
            cost_fn: Custo de falso negativo (default=1.0)
            metric: Métrica para otimizar
              - 'cost': minimiza custo total (cost_fp × FP + cost_fn × FN)
              - 'f1': maximiza F1 score
              - 'balanced_accuracy': maximiza (TPR + TNR) / 2
              - 'youden': maximiza Youden's J statistic (TPR - FPR)
            step: Step do grid search (default=0.01)
            verbose: Print resultados
        
        Returns:
            Threshold ótimo
        
        Note:
            - Usa probabilidades CALIBRADAS se calibrator está setado
            - Threshold é selecionado no validation set, NÃO no trainset
            - Se cost_fn > cost_fp: threshold tende para MENOR (mais recall)
            - Se cost_fp > cost_fn: threshold tende para MAIOR (mais precision)
        """
        # Get probabilities (calibrated if available)
        if self.is_calibrated:
            y_proba = self.predict_proba_calibrated(X_val)
        else:
            y_proba = self.predict_proba(X_val)
        
        best_score = float('-inf') if metric != 'cost' else float('inf')
        best_threshold = 0.5
        
        results = []
        
        for threshold in np.arange(0.0, 1.0 + step, step):
            y_pred = (y_proba >= threshold).astype(int)
            
            # Confusion matrix
            tp = ((y_pred == 1) & (y_val == 1)).sum()
            tn = ((y_pred == 0) & (y_val == 0)).sum()
            fp = ((y_pred == 1) & (y_val == 0)).sum()
            fn = ((y_pred == 0) & (y_val == 1)).sum()
            
            # Compute metric
            if metric == 'cost':
                score = cost_fp * fp + cost_fn * fn
                is_better = score < best_score  # Minimize cost
            
            elif metric == 'f1':
                precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                score = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
                is_better = score > best_score  # Maximize F1
            
            elif metric == 'balanced_accuracy':
                tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                tnr = tn / (tn + fp) if (tn + fp) > 0 else 0.0
                score = (tpr + tnr) / 2.0
                is_better = score > best_score  # Maximize balanced accuracy
            
            elif metric == 'youden':
                tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
                score = tpr - fpr  # Youden's J statistic
                is_better = score > best_score  # Maximize J
            
            else:
                raise ValueError(f"Unknown metric: {metric}")
            
            results.append({
                'threshold': threshold,
                'score': score,
                'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn,
            })
            
            if is_better:
                best_score = score
                best_threshold = threshold
        
        if verbose:
            best_result = [r for r in results if r['threshold'] == best_threshold][0]
            
            tp, tn, fp, fn = best_result['tp'], best_result['tn'], best_result['fp'], best_result['fn']
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            
            print(f"\\nOptimal Threshold Selection (metric={metric}):")
            print(f"  Threshold: {best_threshold:.3f}")
            print(f"  Metric Score: {best_score:.4f}")
            print(f"  Precision: {precision:.4f}")
            print(f"  Recall: {recall:.4f}")
            print(f"  F1: {f1:.4f}")
            print(f"  FP: {fp}, FN: {fn}")
            
            if metric == 'cost':
                print(f"  Total Cost: {best_score:.2f} (FP cost={cost_fp}, FN cost={cost_fn})")
        
        return best_threshold
```

---

#### Arquivo 2: `app/ml/calibration_utils.py` (NOVO)

**Utilidades para Análise de Calibração**

```python
"""
Calibration utilities (Sprint 07).

Funções para análise e visualização de calibração de probabilidades.
"""
import numpy as np
import matplotlib.pyplot as plt
from sklearn.calibration import calibration_curve
from sklearn.metrics import roc_curve, auc, brier_score_loss


def compute_expected_calibration_error(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    n_bins: int = 10,
    strategy: Literal['uniform', 'quantile'] = 'uniform'
) -> float:
    """
    Calcula Expected Calibration Error (ECE).
    
    Args:
        y_true: Labels verdadeiros (0 ou 1)
        y_proba: Probabilidades preditas [0, 1]
        n_bins: Número de bins para agrupar probabilidades
        strategy: 'uniform' (bins de largura igual) ou 'quantile' (adaptive bins)
    
    Returns:
        ECE (0 = perfeitamente calibrado)
    
    Note:
        ECE mede distância média entre confiança predita e acurácia real.
        
        Strategies:
          - 'uniform': Bins [0, 0.1), [0.1, 0.2), ..., [0.9, 1.0]
            → Bom quando probabilidades distribuídas uniformemente
          - 'quantile': Bins com mesmo número de amostras
            → Melhor quando probabilidades concentradas (ex: 90% em [0.8, 1.0])
        
        Exemplo:
          Bin [0.7, 0.8]: 100 exemplos
            - Confidence média: 0.75
            - Acurácia real: 0.68
            - Contribuição: (100/N) × |0.75 - 0.68| = (100/N) × 0.07
    """
    # Create bins
    if strategy == 'uniform':
        bins = np.linspace(0, 1, n_bins + 1)
    elif strategy == 'quantile':
        # Adaptive bins: equal number of samples per bin
        bins = np.percentile(y_proba, np.linspace(0, 100, n_bins + 1))
        bins[0] = 0.0  # Ensure 0
        bins[-1] = 1.0  # Ensure 1
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
    
    bin_indices = np.digitize(y_proba, bins) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)
    
    ece = 0.0
    
    for bin_idx in range(n_bins):
        mask = (bin_indices == bin_idx)
        
        if mask.sum() == 0:
            continue
        
        bin_confidence = y_proba[mask].mean()
        bin_accuracy = y_true[mask].mean()
        bin_weight = mask.sum() / len(y_true)
        
        ece += bin_weight * abs(bin_confidence - bin_accuracy)
    
    return ece


def plot_calibration_curve(
    y_true: np.ndarray,
    y_proba_uncalibrated: np.ndarray,
    y_proba_calibrated: Optional[np.ndarray] = None,
    n_bins: int = 10,
    save_path: Optional[str] = None
):
    """
    Plota reliability diagram (calibration curve).
    
    Args:
        y_true: Labels verdadeiros
        y_proba_uncalibrated: Probabilidades não-calibradas
        y_proba_calibrated: Probabilidades calibradas (opcional)
        n_bins: Número de bins
        save_path: Se fornecido, salva figura
    
    Note:
        Reliability diagram: plota confiança predita vs acurácia real.
        Linha diagonal = perfeitamente calibrado.
        Abaixo da diagonal = overconfident.
        Acima da diagonal = underconfident.
    """
    fig, ax = plt.subplots(figsize=(8, 6))
    
    # Uncalibrated curve
    fraction_of_positives, mean_predicted_value = calibration_curve(
        y_true, y_proba_uncalibrated, n_bins=n_bins, strategy='uniform'
    )
    
    ax.plot(mean_predicted_value, fraction_of_positives, 's-',
            label='Uncalibrated', color='red', alpha=0.7)
    
    # Calibrated curve (if provided)
    if y_proba_calibrated is not None:
        fraction_of_positives_cal, mean_predicted_value_cal = calibration_curve(
            y_true, y_proba_calibrated, n_bins=n_bins, strategy='uniform'
        )
        
        ax.plot(mean_predicted_value_cal, fraction_of_positives_cal, 'o-',
                label='Calibrated', color='green', alpha=0.7)
    
    # Perfect calibration line
    ax.plot([0, 1], [0, 1], 'k--', label='Perfect Calibration')
    
    ax.set_xlabel('Mean Predicted Probability')
    ax.set_ylabel('Fraction of Positives (Accuracy)')
    ax.set_title('Calibration Curve (Reliability Diagram)')
    ax.legend()
    ax.grid(alpha=0.3)
    
    # Compute metrics
    brier_uncal = brier_score_loss(y_true, y_proba_uncalibrated)
    ece_uncal = compute_expected_calibration_error(y_true, y_proba_uncalibrated, n_bins)
    
    text = f"Uncalibrated:\\n  Brier: {brier_uncal:.4f}\\n  ECE: {ece_uncal:.4f}"
    
    if y_proba_calibrated is not None:
        brier_cal = brier_score_loss(y_true, y_proba_calibrated)
        ece_cal = compute_expected_calibration_error(y_true, y_proba_calibrated, n_bins)
        
        text += f"\\n\\nCalibrated:\\n  Brier: {brier_cal:.4f}\\n  ECE: {ece_cal:.4f}"
    
    ax.text(0.05, 0.95, text, transform=ax.transAxes,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150)
        print(f"Calibration curve saved to {save_path}")
    else:
        plt.show()


def plot_roc_curve_with_threshold(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    threshold: float = 0.5,
    save_path: Optional[str] = None
):
    """
    Plota ROC curve com threshold marcado.
    
    Args:
        y_true: Labels verdadeiros
        y_proba: Probabilidades preditas
        threshold: Threshold selecionado (marca no plot)
        save_path: Se fornecido, salva figura
    """
    # Compute ROC curve
    fpr, tpr, thresholds = roc_curve(y_true, y_proba)
    roc_auc = auc(fpr, tpr)
    
    # Find threshold point
    threshold_idx = np.argmin(np.abs(thresholds - threshold))
    threshold_fpr = fpr[threshold_idx]
    threshold_tpr = tpr[threshold_idx]
    
    # Plot
    fig, ax = plt.subplots(figsize=(8, 6))
    
    ax.plot(fpr, tpr, color='darkblue', lw=2,
            label=f'ROC Curve (AUC = {roc_auc:.3f})')
    
    # Mark selected threshold
    ax.plot(threshold_fpr, threshold_tpr, 'ro', markersize=10,
            label=f'Threshold = {threshold:.3f}\\n(TPR={threshold_tpr:.3f}, FPR={threshold_fpr:.3f})')
    
    # Random classifier line
    ax.plot([0, 1], [0, 1], 'k--', lw=1, label='Random Classifier')
    
    ax.set_xlabel('False Positive Rate (FPR)')
    ax.set_ylabel('True Positive Rate (TPR / Recall)')
    ax.set_title('ROC Curve')
    ax.legend(loc='lower right')
    ax.grid(alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150)
        print(f"ROC curve saved to {save_path}")
    else:
        plt.show()
```

---

#### Arquivo 3: `scripts/calibrate_and_tune_threshold.py` (NOVO)

**Script de Calibração + Threshold Tuning**

```python
"""
Script para calibrar classificador e tunar threshold (Sprint 07).

Usage:
  python scripts/calibrate_and_tune_threshold.py \\
    --model models/subtitle_classifier.pkl \\
    --dataset data/features.csv \\
    --output models/subtitle_classifier_calibrated.pkl \\
    --calibration-method platt \\
    --cost-fn 3.0
"""
import argparse
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from app.ml.subtitle_classifier import SubtitleClassifier
from app.ml.calibration_utils import (
    plot_calibration_curve,
    plot_roc_curve_with_threshold,
    compute_expected_calibration_error,
)
from sklearn.metrics import brier_score_loss


def main():
    parser = argparse.ArgumentParser(description='Calibrate classifier and tune threshold')
    parser.add_argument('--dataset', required=True, help='Path to dataset CSV')
    parser.add_argument('--output', required=True, help='Output calibrated model path')
    parser.add_argument('--calibration-method', default='auto', choices=['platt', 'isotonic', 'auto'],
                        help='Calibration method (auto=Platt if N<100, Isotonic if N>=100)')
    parser.add_argument('--cost-fp', type=float, default=1.0, help='Cost of false positive')
    parser.add_argument('--cost-fn', type=float, default=3.0, help='Cost of false negative')
    parser.add_argument('--test-size', type=float, default=0.20, help='Hold-out test size')
    parser.add_argument('--cal-size', type=float, default=0.15, help='Calibration set size (from trainval)')
    args = parser.parse_args()
    
    # Load dataset
    df = pd.read_csv(args.dataset)
    y = df['has_subtitles'].values
    X = df.drop(columns=['video_path', 'has_subtitles']).values
    
    print(f"Dataset: {X.shape[0]} samples, {X.shape[1]} features")
    
    # Split: test / trainval
    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=args.test_size, stratify=y, random_state=42
    )
    
    # Split trainval: calibration / train-threshold
    X_train_threshold, X_cal, y_train_threshold, y_cal = train_test_split(
        X_trainval, y_trainval, test_size=args.cal_size, stratify=y_trainval, random_state=42
    )
    
    # Split train_threshold: train / val (for threshold selection)
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_threshold, y_train_threshold, test_size=0.20, stratify=y_train_threshold, random_state=42
    )
    
    print(f"\\nSplit:")
    print(f"  Train:       {len(X_train)} (model training)")
    print(f"  Val:         {len(X_val)} (threshold selection)")
    print(f"  Calibration: {len(X_cal)} (calibration)")
    print(f"  Test:        {len(X_test)} (final evaluation)")
    
    # Load model
    print(f"\\n{'='*60}")
    print(f"Loading model from {args.model}")
    print(f"{'='*60}")
    
    clf = SubtitleClassifier()
    clf.load(args.model)
    
    # Evaluate uncalibrated
    print(f"\\n{'='*60}")
    print(f"Uncalibrated Model Performance")
    print(f"{'='*60}")
    
    y_test_proba_uncal = clf.predict_proba(X_test)
    brier_uncal = brier_score_loss(y_test, y_test_proba_uncal)
    ece_uncal = compute_expected_calibration_error(y_test, y_test_proba_uncal)
    
    print(f"  Brier Score: {brier_uncal:.4f}")
    print(f"  ECE:         {ece_uncal:.4f}")
    
    # Calibrate
    print(f"\\n{'='*60}")
    print(f"Calibrating with method={args.calibration_method}")
    print(f"{'='*60}")
    
    clf.calibrate(X_cal, y_cal, method=args.calibration_method, verbose=True)
    
    # Evaluate calibrated
    y_test_proba_cal = clf.predict_proba_calibrated(X_test)
    brier_cal = brier_score_loss(y_test, y_test_proba_cal)
    ece_cal = compute_expected_calibration_error(y_test, y_test_proba_cal)
    
    print(f"\\nCalibrated Performance:")
    print(f"  Brier Score: {brier_cal:.4f} (Δ={brier_uncal - brier_cal:.4f})")
    print(f"  ECE:         {ece_cal:.4f} (Δ={ece_uncal - ece_cal:.4f})")
    
    # Tune threshold
    print(f"\\n{'='*60}")
    print(f"Threshold Tuning (cost_fp={args.cost_fp}, cost_fn={args.cost_fn})")
    print(f"{'='*60}")
    
    optimal_threshold = clf.select_optimal_threshold(
        X_val, y_val,
        cost_fp=args.cost_fp,
        cost_fn=args.cost_fn,
        metric='cost',
        verbose=True
    )
    
    clf.threshold = optimal_threshold
    
    # Final evaluation on test
    print(f"\\n{'='*60}")
    print(f"Final Test Set Evaluation (calibrated + optimal threshold)")
    print(f"{'='*60}")
    
    y_test_pred = clf.predict(X_test)
    
    from sklearn.metrics import classification_report
    print(classification_report(y_test, y_test_pred, target_names=['No Subtitle', 'Has Subtitle']))
    
    # Plot calibration curve
    print(f"\\nGenerating calibration curve...")
    plot_calibration_curve(
        y_test, y_test_proba_uncal, y_test_proba_cal,
        save_path='outputs/calibration_curve.png'
    )
    
    # Plot ROC curve
    print(f"Generating ROC curve...")
    plot_roc_curve_with_threshold(
        y_test, y_test_proba_cal, threshold=optimal_threshold,
        save_path='outputs/roc_curve.png'
    )
    
    # Save calibrated model
    metadata = {
        'calibration_method': args.calibration_method,
        'optimal_threshold': optimal_threshold,
        'cost_fp': args.cost_fp,
        'cost_fn': args.cost_fn,
        'brier_score_uncalibrated': float(brier_uncal),
        'brier_score_calibrated': float(brier_cal),
        'ece_uncalibrated': float(ece_uncal),
        'ece_calibrated': float(ece_cal),
    }
    
    clf.save(args.output, metadata=metadata)
    
    print(f"\\n✅ Calibrated model saved to {args.output}")
    print(f"   Calibration: {args.calibration_method}")
    print(f"   Threshold: {optimal_threshold:.3f}")
    print(f"   Brier improvement: {brier_uncal - brier_cal:.4f}")
    print(f"   ECE improvement: {ece_uncal - ece_cal:.4f}")


if __name__ == '__main__':
    main()
```

---

### Resumo das Mudanças

| Arquivo | Funções Afetadas | Tipo Mudança | Linhas |
|---------|------------------|-------------|--------|
| `app/ml/subtitle_classifier.py` **(ESTENDER)** | `calibrate()`, `predict_proba_calibrated()`, `select_optimal_threshold()` | Adicionar calibração + threshold tuning | +250 |
| `app/ml/calibration_utils.py` **(NOVO)** | `compute_expected_calibration_error()`, `plot_calibration_curve()`, `plot_roc_curve_with_threshold()` | Utils de calibração | +180 |
| `scripts/calibrate_and_tune_threshold.py` **(NOVO)** | Script CLI de calibração | Calibrar + tunar threshold | +150 |
| **TOTAL** | | | **~580 linhas** |

---

## 5️⃣ Plano de Validação

### Como Medir Impacto?

**Métrica Principal**: **Brier Score + ECE** (calibração) + **Precision/Recall** (threshold ótimo)

---

### Método

**1. Baseline (Post-Sprint 06 - uncalibrated)**

```bash
$ python evaluate_model.py --model models/subtitle_classifier.pkl --dataset test_dataset/

Esperado:
┌─────────────────────────────────────────┐
│ POST-SPRINT-06 BASELINE (uncalibrated)  │
├─────────────────────────────────────────┤
│ Precision: 97%                          │
│ Recall: 97%                             │
│ F1: 97%                                 │
│ Threshold: 0.75 (max F1)                │
│                                         │
│ Calibration:                            │
│   Brier Score: 0.08                     │
│   ECE: 0.12                             │
└─────────────────────────────────────────┘
```

---

**2. Calibrar + Tunar Threshold (Sprint 07)**

```bash
$ python scripts/calibrate_and_tune_threshold.py \\
    --model models/subtitle_classifier.pkl \\
    --dataset data/features.csv \\
    --output models/subtitle_classifier_calibrated.pkl \\
    --calibration-method platt \\
    --cost-fn 3.0  # FN custa 3× mais que FP

Esperado:
┌─────────────────────────────────────────┐
│ CALIBRATION (Platt Scaling)            │
├─────────────────────────────────────────┤
│ Brier Score Before: 0.08                │
│ Brier Score After:  0.04  (-0.04) ✅    │
│ ECE Before: 0.12                        │
│ ECE After:  0.05  (-0.07) ✅            │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ THRESHOLD TUNING (cost-based)           │
├─────────────────────────────────────────┤
│ Old Threshold: 0.75 (max F1)            │
│ New Threshold: 0.68 (min cost, FN=3×FP) │
│                                         │
│ Precision: 98% (+1%) ✅                 │
│ Recall: 97% (mantém) ✅                 │
│ F1: 97.5% (+0.5%) ✅                    │
│ Total Cost: 12.5 (vs 15.0 antes)       │
└─────────────────────────────────────────┘
```

---

**3. A/B Test: Uncalibrated vs Calibrated**

```bash
# Uncalibrated (Sprint 06)
$ python measure_baseline.py --model models/subtitle_classifier.pkl

# Calibrated (Sprint 07)
$ python measure_baseline.py --model models/subtitle_classifier_calibrated.pkl
```

---

**4. Análise Visual**

```bash
# Gerar plots
$ python scripts/calibrate_and_tune_threshold.py --model ... --dataset ...

# Outputs:
#   outputs/calibration_curve.png  → Reliability diagram
#   outputs/roc_curve.png          → ROC com threshold marcado
```

**Análise esperada:**

**Calibration Curve (Reliability Diagram):**
```
Antes: Pontos longe da diagonal (descalibrado)
  - proba=0.80 → acurácia real=0.60 (overconfident)
  - proba=0.50 → acurácia real=0.70 (underconfident)

Depois: Pontos próximos da diagonal (calibrado)
  - proba=0.80 → acurácia real=0.78 ✅
  - proba=0.50 → acurácia real=0.52 ✅
```

**ROC Curve:**
```
AUC: 0.987 (mantém, calibração não muda AUC)
Threshold marcado: 0.68 (vs 0.75 antes)
```

---

### Métrica de Validação

| Métrica | Threshold | Status |
|---------|-----------|--------|
| **Δ Brier Score** | ≤ -0.02 | ✅ Aceita sprint |
| **Δ ECE** | ≤ -0.05 | ✅ Aceita sprint |
| **Precision** | ≥ 97% (no drop) | ✅ Aceita sprint |
| **Recall** | ≥ 97% (no drop) | ✅ Aceita sprint |
| **F1 Score** | ≥ 97% | ✅ Aceita sprint |
| **Calibration curve** | Pontos próximos diagonal | ✅ Visual check |

---

## 6️⃣ Risco & Trade-offs

### Riscos Identificados

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|--------|-----------|
| **Calibration set pequeno** (<50 samples) | 30% | MÉDIO | Usar >80 samples; se não, usar Platt (mais robusto) |
| **Overfitting no threshold** (tunar em trainset) | 20% | ALTO | SEMPRE tunar em validation set separado! |
| **Custo FP/FN mal estimado** | 40% | MÉDIO | Validar com stakeholders; fazer sensitivity analysis |
| **Calibração piora AUC** | 5% | BAIXO | Calibração preserva ranking (não deve piorar AUC) |

---

### Trade-offs

#### Trade-off 1: Platt vs Isotonic

**Opção A**: Platt Scaling ← **RECOMENDADO (LogReg)**
- ✅ Rápido (2 parâmetros)
- ✅ Funciona bem com LogisticRegression
- ✅ Robusto com poucos dados (50+ samples ok)
- ❌ Assume forma paramétrica (sigmoid)

**Opção B**: Isotonic Regression
- ✅ Mais flexível (captura não-linearidades)
- ✅ Funciona bem com XGBoost
- ❌ Precisa de mais dados (100+ samples)
- ❌ Pode overfit

→ **Decisão**: Platt para LogReg (Sprint 06), Isotonic se usar XGBoost.

---

#### Trade-off 2: Métrica para Threshold Tuning

**Opção A**: Max F1 ← **Sprint 06 baseline**
- ✅ Simples
- ❌ Não considera custo FP vs FN

**Opção B**: Min Cost (weighted) ← **RECOMENDADO Sprint 07**
- ✅ Customizável (cost_fp, cost_fn)
- ✅ Alinhado com negócio
- ❌ Requer estimativa de custo

**Opção C**: Max Youden's J (TPR - FPR)
- ✅ Maximiza "distância" do random classifier
- ❌ Dá peso igual a FP e FN (como F1)

→ **Decisão**: Min Cost (Opção B), mas permitir F1, Youden como alternativas.

---

#### Trade-off 3: Threshold Step Size

**Opção A**: Step 0.05 (Sprint 06)
- ✅ Rápido (20 thresholds testados)
- ❌ Pode perder ótimo

**Opção B**: Step 0.01 ← **Sprint 07**
- ✅ Mais preciso (100 thresholds)
- ✅ Negligível overhead (<1s)

→ **Decisão**: Step 0.01 (mais preciso, custo baixo).

---

## 7️⃣ Critério de Aceite da Sprint

> **⚠️ CORREÇÃO P1 (FIX_OCR.md - Alignment com Meta do Produto)**  
> Critérios originais (Precision/Recall ≥97%) eram **self-blocking** e não alinhados com meta do produto.  
> **Meta do produto**: Precision ≥90%, Recall ≥85%, FPR <3%  
> **Critérios Sprint 07 revisados**: Não regredir de Sprint 06, garantir FPR <3% via threshold tuning

### Criterios Técnicos de Aceitação

```
✅ CRÍTICO (MUST HAVE)
  □ calibrate() implementado (Platt recomendado, isotonic se N≥500)
  □ predict_proba_calibrated() implementado
  □ select_optimal_threshold() implementado (cost-based + FPR constraint)
  □ Split único disjunto: train/cal/val/test (SEM vazamento, por vídeo!)
  □ Modelo treinado DO ZERO no script (não carregar pronto)
  □ Calibration set SEPARADO (nunca visto no treino)
  □ Threshold tunado em validation set SEPARADO (nunca visto no treino/cal)
  □ Calibration melhora: Brier Score ≤ Baseline, ECE ≤ Baseline
  □ ROC-AUC reportado antes/depois (sem assumir que mantém)
  □ **FPR <3%** via threshold tuning (meta CRÍTICA do produto) ✅
  □ No regression vs Sprint 06: Precision ± 1pp, Recall ± 2pp

✅ IMPORTANTE (SHOULD HAVE)
  □ Calibration curve plotada (reliability diagram)
  □ ROC curve plotada (threshold marcado, FPR<3% destacado)
  □ Precision: ≥ 90% (meta do produto, não 97%)
  □ Recall: ≥ 85% (meta do produto, não 97%)
  □ F1: ≥ 87% (derivado de precision/recall metas)
  □ Threshold selecionado via custo customizado com constraint FPR<3%

✅ NICE TO HAVE (COULD HAVE)
  □ Monitoramento de calibração em produção
  □ Sensitivity analysis (variar cost_fp/cost_fn)
  □ Comparison Platt vs Isotonic (se N_cal ≥ 500)
```

### Definição de "Sucesso" para Sprint 07

**Requisito de Aprovação (REVISADO - alinhado com meta do produto):**

1. ✅ Código completo (calibração + threshold tuning)
2. ✅ Calibration set independente (não usado em treino, split por vídeo)
3. ✅ Calibration melhora: Brier Score e ECE não pioram vs baseline
4. ✅ **FPR <3%** via threshold tuning (CRÍTICO) ✅
5. ✅ Precision: ≥ 90% (meta do produto, não 97%)
6. ✅ Recall: ≥ 85% (meta do produto, não 97%)
7. ✅ Threshold: selecionado via custo + constraint FPR<3%
8. ✅ Calibration curve: confiável (ECE ≤ 0.10)
9. ✅ ROC curve: AUC ≥ 0.95 (alta discriminação)
10. ✅ Código review aprovado
11. ✅ Testes unitários: test_calibration.py (coverage 90%)

**Nota sobre metas 97%/97%:**  
Metas originais (97% precision/ 97% recall) eram aspiracionais mas **bloqueiam roadmap** se não atingidas.  
Sprint 07 é aprovada se atingir meta do produto (≥90%/≥85%) + FPR<3%.  
Metas >95% são "stretch goals" (nice-to-have, não blockers).

---

### Checklist de Implementação

```
Code Implementation:
  ☐ app/ml/subtitle_classifier.py estendido (~250 linhas)
    ☐ calibrate() implementado (Platt + Isotonic + 'auto')
    ☐ Auto-select: Platt se N_cal < 100, Isotonic se >= 100
    ☐ _calibrate_proba() helper implementado
    ☐ predict_proba_calibrated() implementado
    ☐ select_optimal_threshold() implementado (cost/f1/youden)
    ☐ Validação de calibration set separado
    ☐ Guardar n_calibration_samples no metadata
  ☐ app/ml/calibration_utils.py criado (~180 linhas)
    ☐ compute_expected_calibration_error() implementado
    ☐ Suporte para strategy='uniform' e 'quantile'
    ☐ plot_calibration_curve() implementado
    ☐ plot_roc_curve_with_threshold() implementado
  ☐ scripts/calibrate_and_tune_threshold.py criado (~180 linhas)
    ☐ CLI de calibração + threshold tuning
    ☐ Split ÚNICO disjunto: train / cal / val / test
    ☐ Treinar modelo DO ZERO (não carregar pronto)
    ☐ Reportar ROC-AUC e PR-AUC antes/depois
    ☐ Reportar ECE uniform e quantile
    ☐ Gerar plots (calibration curve, ROC curve)
    ☐ Metadata completo (N_cal, AUCs, ECEs, costs)

Validation:
  ☐ Baseline uncalibrated medido (Brier, ECE)
  ☐ Calibração aplicada (Platt ou Isotonic)
  ☐ Threshold tunado (cost-based)
  ☐ Validação em test set:
    ☐ Brier Score melhora ≥ -0.02
    ☐ ECE melhora ≥ -0.05
    ☐ Precision ≥ 97%
    ☐ Recall ≥ 97%
    ☐ F1 ≥ 97%
  ☐ Calibration curve plotada e analisada
  ☐ ROC curve plotada (threshold marcado)

Testing:
  ☐ Testes escritos:
    ☐ test_calibration.py (calibrate + predict_proba_calibrated)
    ☐ test_threshold_selection.py (select_optimal_threshold)
    ☐ test_calibration_utils.py (ECE, plots)
  ☐ Coverage ≥ 90%

Documentation:
  ☐ Docstrings completos
  ☐ README: instruções de calibração
  ☐ Calibration report (comparativo uncal vs cal)

Deployment:
  ☐ Code review feito
  ☐ A/B test Sprint 06 (uncalibrated) vs Sprint 07 (calibrated)
  ☐ Brier/ECE validados
  ☐ Precision/Recall mantidos
  ☐ Aprovação de PM/Tech Lead
  ☐ Merge para main
  ☐ Deploy em produção (10% tráfego)
  ☐ Monitoramento 48h (calibração + métricas)
  ☐ 100% rollout se Brier < 0.05
```

---

## 📋 Resumo da Sprint

| Aspecto | Detalhe |
|---------|---------|
| **Objetivo** | Calibrar probabilidades e otimizar threshold via ROC curve |
| **Problema** | Probabilidades não-calibradas (Brier=0.08) + threshold não-ótimo (max F1 apenas) |
| **Solução** | Platt Scaling/Isotonic + threshold tuning via custo customizado |
| **Impacto** | +1-3% precision/recall, -0.04 Brier, -0.07 ECE |
| **Arquitetura** | Classificador → Calibrador → proba_calibrated → threshold ótimo → Decision |
| **Risco** | BAIXO (calibração é step padrão, bem validado) |
| **Esforço** | ~6-8h (calibração 40%, threshold tuning 40%, validation 20%) |
| **Latência** | +0.1-0.5ms (calibração adicional, negligível) |
| **Linhas de código** | ~580 linhas (extensão classifier + utils + script) |
| **Calibração** | **Platt Scaling (LogReg) ou Isotonic (XGBoost)** |
| **Threshold** | **Selecionado via min cost (customizável: FP, FN weights)** |
| **Métricas** | **Brier Score, ECE (calibração) + Precision/Recall (threshold)** |
| **Dependências** | Sprint 06 (classificador treinado), Calibration set (50+ vídeos) |
| **Próxima Sprint** | Sprint 08 (Validation, Regression Testing & Production) |

---

## 🚀 Próximos Passos

1. ✅ Sprint 07 documentada
2. ⏳ **Implementar calibração** (Platt Scaling)
3. ⏳ **Implementar threshold tuning** (via custo)
4. ⏳ **Validar no test set** (Brier -0.02, ECE -0.05)
5. 📊 **Gerar calibration curve** (reliability diagram)
6. 📊 **Gerar ROC curve** (threshold marcado)
7. ➡️ Proceder para Sprint 08 (Validation & Production)

---

**Nota Final:**

Sprint 07 é **refinamento final**:
- Remove descalibração (Brier 0.08 → 0.04)
- Otimiza threshold via custo (alinhado com negócio)
- Prepara sistema para produção (probabilidades confiáveis)

**Ganho esperado: +1-3%** em precision/recall, mas **impacto real é confiabilidade**.

Probabilidades calibradas = **decisões mais corretas** = **melhor UX** = **menos erros custosos**.

Sprint 08 validará todo o sistema (Sprints 01-07) em hold-out final e preparará deploy.
