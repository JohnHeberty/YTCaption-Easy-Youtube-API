# Sprint 06: Ensemble de Modelos Pré-Treinados (REVISADO)

**Objetivo**: Implementar sistema ensemble com 3 modelos pré-treinados para máxima precisão (plug and play, zero training)  
**Impacto Esperado**: +10-20% precision/recall (ensemble > single model)  
**Criticidade**: ⭐⭐⭐⭐⭐ **CRÍTICO** (Próxima etapa evolutiva após Multi-ROI)  
**Data**: 2026-02-14  
**Status**: 🟢 Pronto para implementar (Sprint 00-04 completos)  
**Dependências**: Sprint 00-04 (PaddleOCR + Multi-ROI ready)

> **🔄 REVISÃO ARQUITETURAL:**  
> Mudança de abordagem de ML tradicional (treinar Random Forest) para **Ensemble de Modelos Pré-Treinados**.  
> 
> **Motivo**: Evitar trabalho manual de coleta/rotulação de 200+ vídeos. Usar modelos state-of-the-art já treinados.  
> 
> **Benefícios**:  
> - ✅ **100% plug and play** (só download de modelos)  
> - ✅ **Zero manual labeling** (sem dataset collection)  
> - ✅ **Modelos robustos** (treinados em milhões de exemplos)  
> - ✅ **Rápido de implementar** (~4-6 horas vs. 1-2 semanas)  
> - ✅ **Alta precisão** (ensemble mitiga fraquezas individuais)

---

## 📋 ÍNDICE

1. [Objetivo Técnico](#1️⃣-objetivo-técnico-claro)
2. [Arquitetura do Ensemble](#2️⃣-arquitetura-do-ensemble)
3. [Modelos Pré-Treinados](#3️⃣-modelos-pré-treinados)
4. [Sistema de Votação](#4️⃣-sistema-de-votação)
5. [Implementação](#5️⃣-implementação)
6. [Testes](#6️⃣-testes-esperados)
7. [Integração](#7️⃣-integração-com-sprints-anteriores)

---

## 1️⃣ Objetivo Técnico Claro

### Problema Específico

Atualmente (Sprint 00-04) temos **apenas PaddleOCR** como detector:

```python
# CÓDIGO ATUAL (após Sprint 04)
detector = SubtitleDetectorV2(roi_mode='multi')
has_subs, conf, text, metadata = detector.detect_in_video_with_multi_roi(video_path)

# Problema: Single point of failure
# - Se PaddleOCR falhar → sistema erra
# - Sem redundância ou validação cruzada
```

**Problemas Críticos:**

### 1) **Single Point of Failure**
- PaddleOCR pode falhar em:
  - Fontes raras ou estilizadas
  - Baixo contraste (mesmo com CLAHE)
  - Texto rotacionado ou distorcido
  - Idiomas específicos (árabe, japonês)

### 2) **Sem Validação Cruzada**
- Uma única detecção = decisão final
- Nenhuma confirmação por modelo independente
- Alto risco de falsos positivos/negativos

### 3) **Não Aproveita Modelos State-of-the-Art**
- CLIP (OpenAI) = zero-shot classifier de 400M imagens
- CRAFT = detector de texto state-of-the-art
- EasyOCR = alternativa ao PaddleOCR, multi-idioma

**Solução**: Ensemble de 3 modelos pré-treinados com votação ponderada.

---

## 2️⃣ Arquitetura do Ensemble

### Visão Geral

```
┌─────────────────────────────────────────────────────────────────┐
│                    ENSEMBLE SYSTEM (Sprint 06)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Input: video_path                                                │
│     │                                                             │
│     ├──────────┬──────────────┬──────────────┐                  │
│     │          │              │              │                  │
│     ▼          ▼              ▼              ▼                  │
│  ┌──────┐  ┌──────┐      ┌──────┐      ┌──────┐               │
│  │Paddle│  │ CLIP │      │CRAFT │      │ Easy │  (4 models)   │
│  │ OCR  │  │(Zero-│      │(Text │      │ OCR  │               │
│  │Multi-│  │Shot) │      │Detect│      │(Alt.)│               │
│  │ ROI  │  │      │      │)     │      │      │               │
│  └───┬──┘  └───┬──┘      └───┬──┘      └───┬──┘               │
│      │         │             │             │                   │
│      ├─────────┴─────────────┴─────────────┤                   │
│      │                                      │                   │
│      ▼                  ▼                                       │
│  ┌─────────────────────────────────┐                           │
│  │   Voting System (Sprint 07)      │                           │
│  │   - Weighted Average              │                           │
│  │   - Confidence Aggregation        │                           │
│  │   - Conflict Resolution           │                           │
│  └──────────────┬──────────────────┘                           │
│                 │                                                │
│                 ▼                                                │
│    Output: {has_subtitles, confidence, votes, metadata}         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Fluxo de Execução

```python
1. Preprocessamento (Sprint 01-02)
   ├─ Resize para resolução adequada
   ├─ CLAHE (contrast enhancement)
   └─ Extract temporal frames (6 frames)

2. Detecção Paralela (4 modelos)
   ├─ PaddleOCR + Multi-ROI (Sprint 04)
   ├─ CLIP zero-shot classification
   ├─ CRAFT text detection
   └─ EasyOCR (alternativo)

3. Votação Ponderada (Sprint 07)
   ├─ Peso por confiabilidade do modelo
   ├─ Detecção de conflitos
   └─ Confidence final agregado

4. Decisão Final
   └─ has_subtitles: bool (weighted vote > 0.5)
      confidence: float (0-1)
      votes: dict (resultado de cada modelo)
      metadata: dict (ROI usado, tempos, etc.)
```

---

## 3️⃣ Modelos Pré-Treinados

### Modelo 1: PaddleOCR + Multi-ROI (Sprint 00-04) ✅ JÁ IMPLEMENTADO

**Status**: ✅ Completo (36/37 testes passando)

**Características**:
- 6 ROIs (bottom, top, left, right, center, full)
- Priority-based fallback
- 100% accuracy nos 83 vídeos de teste
- Performance: ≤8s worst case, ≤3s fast path

**Vantagens**:
- ✅ Já implementado e testado
- ✅ Multi-ROI coverage (100%)
- ✅ Otimizado para legendas

**Limitações**:
- ⚠️ Pode falhar em fontes muito estilizadas
- ⚠️ Depende de OCR (precisa ler texto)

**Peso no Ensemble**: 35% (confiável, mas não perfeito)

---

### Modelo 2: CLIP (OpenAI) - Zero-Shot Classification 🆕

**O que é**:
- Modelo de visão-linguagem da OpenAI
- Treinado em 400M pares (imagem, texto)
- Zero-shot: classifica sem treino adicional

**Como funciona**:
```python
from transformers import CLIPProcessor, CLIPModel
import torch

# 1. Carregar modelo (só download, ~600MB)
model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

# 2. Preparar prompts
text_prompts = [
    "A video frame with burned-in subtitles at the bottom",
    "A video frame with hardcoded subtitles or captions",
    "A video frame without any subtitles or text overlays",
    "A clean video frame with no embedded text"
]

# 3. Classificar frame
inputs = processor(
    text=text_prompts,
    images=frame,
    return_tensors="pt",
    padding=True
)

with torch.no_grad():
    outputs = model(**inputs)
    logits_per_image = outputs.logits_per_image  # Shape: [1, 4]
    probs = logits_per_image.softmax(dim=1)      # Normalize

# 4. Decisão
has_subtitles_prob = (probs[0][0] + probs[0][1]) / 2  # Média dos 2 primeiros
no_subtitles_prob = (probs[0][2] + probs[0][3]) / 2   # Média dos 2 últimos

has_subtitles = has_subtitles_prob > no_subtitles_prob
confidence = max(has_subtitles_prob, no_subtitles_prob).item()
```

**Vantagens**:
- ✅ Zero-shot (sem treino)
- ✅ Robusto (400M exemplos)
- ✅ Detecta padrões semânticos (não só OCR)
- ✅ Funciona com qualquer idioma
- ✅ Rápido (~50ms por frame com GPU)

**Limitações**:
- ⚠️ Pode confundir texto geral com legendas
- ⚠️ Menos preciso que OCR para texto específico
- ⚠️ Requer GPU para ser rápido

**Peso no Ensemble**: 30% (boa visão geral, mas menos específico)

**Instalação**:
```bash
pip install transformers torch pillow
```

---

### Modelo 3: CRAFT (Character Region Awareness) 🆕

**O que é**:
- Detector de texto state-of-the-art (2019)
- Treinado em ICDAR, SynthText, COCO-Text
- Detecta regiões de texto com bounding boxes

**Como funciona**:
```python
import craft_text_detector
from PIL import Image

# 1. Carregar modelo (só download, ~150MB)
detector = craft_text_detector.Craft(
    output_dir='storage/craft_output/',
    crop_type="box",
    cuda=True
)

# 2. Detectar texto no frame
frame_path = 'frame.jpg'
prediction_result = detector.detect_text(frame_path)

# 3. Analisar regiões detectadas
text_boxes = prediction_result['boxes']
frame_height = frame.shape[0]

# Filtrar regiões no bottom 25% (típico de legendas)
bottom_boxes = [
    box for box in text_boxes 
    if box['y'] + box['height'] > frame_height * 0.75
]

# Calcular métricas
total_text_area = sum(box['width'] * box['height'] for box in text_boxes)
bottom_text_area = sum(box['width'] * box['height'] for box in bottom_boxes)
bottom_ratio = bottom_text_area / total_text_area if total_text_area > 0 else 0

# Decisão
has_subtitles = (
    len(bottom_boxes) >= 1 and                    # Pelo menos 1 região no bottom
    bottom_ratio > 0.6 and                        # 60%+ do texto está no bottom
    any(box['width'] > frame.shape[1] * 0.3       # Alguma região com largura > 30% do frame
        for box in bottom_boxes)
)

confidence = min(bottom_ratio, len(bottom_boxes) / 3)  # Max 3 boxes = 100%
```

**Vantagens**:
- ✅ Estado-da-arte em detecção de texto
- ✅ Não precisa OCR (só detecta regiões)
- ✅ Funciona com qualquer idioma/fonte
- ✅ Detecta padrões geométricos de legendas

**Limitações**:
- ⚠️ Pesado (~150MB)
- ⚠️ Requer GPU para ser eficiente
- ⚠️ Pode detectar UI elements como texto

**Peso no Ensemble**: 25% (ótimo complemento, mas pode ter FP)

**Instalação**:
```bash
pip install craft-text-detector
```

---

### Modelo 4: EasyOCR (Alternativo) 🆕 OPCIONAL

**O que é**:
- Alternativa ao PaddleOCR
- Suporta 80+ idiomas
- Baseado em CRAFT + CRNN

**Como funciona**:
```python
import easyocr

# 1. Carregar modelo (download automático)
reader = easyocr.Reader(['en', 'pt', 'es'], gpu=True)

# 2. Detectar texto
results = reader.readtext(frame)

# 3. Análise (similar ao PaddleOCR)
bottom_texts = [
    res for res in results
    if res[0][0][1] > frame_height * 0.75  # y-coordinate no bottom 25%
]

has_subtitles = len(bottom_texts) >= 1
confidence = max([res[2] for res in bottom_texts], default=0.0)
```

**Vantagens**:
- ✅ Multi-idioma (80+ languages)
- ✅ Fácil de usar
- ✅ Boa alternativa ao PaddleOCR

**Limitações**:
- ⚠️ Mais lento que PaddleOCR
- ⚠️ Overlap significativo com PaddleOCR

**Peso no Ensemble**: 10% (redundante com Paddle, mas útil como fallback)

**Instalação**:
```bash
pip install easyocr
```

---

## 4️⃣ Sistema de Votação

### Estratégia 1: Weighted Average (Simples) ✅ RECOMENDADO

```python
class EnsembleSubtitleDetector:
    def __init__(self):
        self.weights = {
            'paddle': 0.35,  # 35% - Mais confiável (Sprint 00-04)
            'clip': 0.30,    # 30% - Boa visão geral
            'craft': 0.25,   # 25% - Especializado em texto
            'easyocr': 0.10  # 10% - Fallback redundante
        }
    
    def detect(self, video_path):
        # 1. Rodar todos os modelos
        votes = {}
        
        # Paddle (Multi-ROI)
        paddle_result = self.paddle_detector.detect_in_video_with_multi_roi(video_path)
        votes['paddle'] = {
            'has_subtitles': paddle_result[0],
            'confidence': paddle_result[1],
            'weight': self.weights['paddle']
        }
        
        # CLIP (Zero-shot)
        clip_result = self.clip_classifier.classify(video_path)
        votes['clip'] = {
            'has_subtitles': clip_result['has_subtitles'],
            'confidence': clip_result['confidence'],
            'weight': self.weights['clip']
        }
        
        # CRAFT (Text detection)
        craft_result = self.craft_detector.detect(video_path)
        votes['craft'] = {
            'has_subtitles': craft_result['has_subtitles'],
            'confidence': craft_result['confidence'],
            'weight': self.weights['craft']
        }
        
        # EasyOCR (optional)
        if self.use_easyocr:
            easyocr_result = self.easyocr_detector.detect(video_path)
            votes['easyocr'] = {
                'has_subtitles': easyocr_result['has_subtitles'],
                'confidence': easyocr_result['confidence'],
                'weight': self.weights['easyocr']
            }
        
        # 2. Votação ponderada
        weighted_score = 0.0
        total_weight = 0.0
        
        for model_name, vote in votes.items():
            if vote['has_subtitles']:
                weighted_score += vote['confidence'] * vote['weight']
            total_weight += vote['weight']
        
        # Normalizar
        final_confidence = weighted_score / total_weight if total_weight > 0 else 0.0
        final_decision = final_confidence >= 0.5
        
        return {
            'has_subtitles': final_decision,
            'confidence': final_confidence,
            'votes': votes,
            'metadata': {
                'ensemble_method': 'weighted_average',
                'weights': self.weights,
                'timestamp': time.time()
            }
        }
```

**Exemplo de Votação**:

```python
# Caso 1: Consenso (3/3 concordam)
votes = {
    'paddle': {'has_subtitles': True, 'confidence': 0.92, 'weight': 0.35},
    'clip':   {'has_subtitles': True, 'confidence': 0.88, 'weight': 0.30},
    'craft':  {'has_subtitles': True, 'confidence': 0.85, 'weight': 0.25}
}

weighted_score = 0.92*0.35 + 0.88*0.30 + 0.85*0.25 = 0.322 + 0.264 + 0.2125 = 0.7985
final_confidence = 0.7985 / 0.90 = 0.887  # 88.7% confiança
final_decision = True  # TEM legendas ✅

# Caso 2: Desacordo (2/3 vs 1/3)
votes = {
    'paddle': {'has_subtitles': True,  'confidence': 0.75, 'weight': 0.35},
    'clip':   {'has_subtitles': False, 'confidence': 0.82, 'weight': 0.30},
    'craft':  {'has_subtitles': True,  'confidence': 0.68, 'weight': 0.25}
}

weighted_score = 0.75*0.35 + 0 + 0.68*0.25 = 0.2625 + 0 + 0.17 = 0.4325
final_confidence = 0.4325 / 0.90 = 0.480  # 48% confiança
final_decision = False  # NÃO TEM legendas (below 50%) ⚠️

# Caso 3: Paddle forte, outros fracos
votes = {
    'paddle': {'has_subtitles': True,  'confidence': 0.95, 'weight': 0.35},
    'clip':   {'has_subtitles': False, 'confidence': 0.55, 'weight': 0.30},
    'craft':  {'has_subtitles': False, 'confidence': 0.60, 'weight': 0.25}
}

weighted_score = 0.95*0.35 + 0 + 0 = 0.3325
final_confidence = 0.3325 / 0.90 = 0.369  # 37% confiança
final_decision = False  # NÃO TEM (Paddle sozinho não basta) ⚠️
```

---

### Estratégia 2: Majority Voting (Alternativa)

```python
def majority_voting(votes):
    """
    Votação simples: maioria vence (sem pesos).
    """
    yes_votes = sum(1 for v in votes.values() if v['has_subtitles'])
    no_votes = len(votes) - yes_votes
    
    final_decision = yes_votes > no_votes
    
    # Confidence = proporção da maioria
    total_votes = len(votes)
    final_confidence = yes_votes / total_votes if final_decision else no_votes / total_votes
    
    return final_decision, final_confidence
```

---

## 5️⃣ Implementação

### Fase 1: Setup dos Modelos (30 min)

```bash
# 1. Instalar dependências
pip install transformers torch pillow craft-text-detector easyocr

# 2. Download dos modelos (automático no primeiro uso)
# - CLIP: ~/.cache/huggingface/transformers/ (~600MB)
# - CRAFT: ~/.craft_text_detector/ (~150MB)
# - EasyOCR: ~/.EasyOCR/model/ (~150MB por idioma)
```

### Fase 2: Implementar Classes Base (2h)

**Estrutura de arquivos**:

```
services/make-video/
├── app/
│   ├── video_processing/
│   │   ├── subtitle_detector_v2.py         # ✅ Já existe (Sprint 04)
│   │   ├── ensemble_detector.py            # 🆕 Main ensemble
│   │   ├── detectors/
│   │   │   ├── __init__.py
│   │   │   ├── paddle_detector.py          # 🆕 Wrapper do V2
│   │   │   ├── clip_classifier.py          # 🆕 CLIP
│   │   │   ├── craft_detector.py           # 🆕 CRAFT
│   │   │   └── easyocr_detector.py         # 🆕 EasyOCR (opcional)
│   │   └── voting/
│   │       ├── __init__.py
│   │       ├── weighted_voting.py          # 🆕 Weighted average
│   │       └── majority_voting.py          # 🆕 Simple majority
```

**Interface Comum**:

```python
# app/video_processing/detectors/base_detector.py
from abc import ABC, abstractmethod
from typing import Dict, Tuple

class BaseSubtitleDetector(ABC):
    """
    Interface comum para todos os detectores do ensemble.
    """
    
    @abstractmethod
    def detect(self, video_path: str) -> Dict:
        """
        Detecta legendas em um vídeo.
        
        Args:
            video_path: Caminho para o arquivo de vídeo
        
        Returns:
            {
                'has_subtitles': bool,
                'confidence': float,  # 0-1
                'metadata': dict
            }
        """
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Retorna nome do modelo."""
        pass
    
    @abstractmethod
    def get_weight(self) -> float:
        """Retorna peso padrão no ensemble."""
        pass
```

### Fase 3: Implementar Detectores (3h)

#### 3.1 PaddleDetector (Wrapper) - 30 min

```python
# app/video_processing/detectors/paddle_detector.py
from .base_detector import BaseSubtitleDetector
from ..subtitle_detector_v2 import SubtitleDetectorV2

class PaddleDetector(BaseSubtitleDetector):
    """
    Wrapper do SubtitleDetectorV2 (Sprint 00-04).
    """
    
    def __init__(self, roi_mode='multi'):
        self.detector = SubtitleDetectorV2(roi_mode=roi_mode)
    
    def detect(self, video_path: str) -> dict:
        has_subs, confidence, text, metadata = \
            self.detector.detect_in_video_with_multi_roi(video_path)
        
        return {
            'has_subtitles': has_subs,
            'confidence': confidence,
            'metadata': {
                'text': text,
                'roi_used': metadata.get('roi_used'),
                'model': 'paddleocr'
            }
        }
    
    def get_model_name(self) -> str:
        return 'paddle'
    
    def get_weight(self) -> float:
        return 0.35  # 35% weight
```

#### 3.2 CLIPClassifier - 1h

```python
# app/video_processing/detectors/clip_classifier.py
import torch
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import cv2
from .base_detector import BaseSubtitleDetector

class CLIPClassifier(BaseSubtitleDetector):
    """
    Zero-shot subtitle classifier usando CLIP.
    """
    
    def __init__(self, device='cuda' if torch.cuda.is_available() else 'cpu'):
        self.device = device
        
        # Carregar modelo
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        
        # Prompts para classificação
        self.prompts = [
            "A video frame with burned-in subtitles or captions at the bottom",
            "A video frame with hardcoded text overlays or subtitles",
            "A clean video frame without any subtitles or embedded text",
            "A video frame with no captions or text overlays"
        ]
    
    def detect(self, video_path: str) -> dict:
        # 1. Extrair frames (usar mesma estratégia do Sprint 01)
        frames = self._extract_frames(video_path, n_frames=6)
        
        # 2. Classificar cada frame
        frame_results = []
        for frame in frames:
            result = self._classify_frame(frame)
            frame_results.append(result)
        
        # 3. Agregar resultados
        has_subtitles_votes = sum(1 for r in frame_results if r['has_subtitles'])
        confidence_scores = [r['confidence'] for r in frame_results]
        
        has_subtitles = has_subtitles_votes >= (len(frames) // 2)  # Maioria
        confidence = sum(confidence_scores) / len(confidence_scores)  # Média
        
        return {
            'has_subtitles': has_subtitles,
            'confidence': confidence,
            'metadata': {
                'frame_results': frame_results,
                'votes': f'{has_subtitles_votes}/{len(frames)}',
                'model': 'clip'
            }
        }
    
    def _classify_frame(self, frame) -> dict:
        """Classifica um único frame."""
        # Converter BGR (OpenCV) para RGB (PIL)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)
        
        # Processar com CLIP
        inputs = self.processor(
            text=self.prompts,
            images=pil_image,
            return_tensors="pt",
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits_per_image
            probs = logits.softmax(dim=1)
        
        # Calcular probabilidades
        has_subtitles_prob = (probs[0][0] + probs[0][1]) / 2  # Média prompts 0 e 1
        no_subtitles_prob = (probs[0][2] + probs[0][3]) / 2   # Média prompts 2 e 3
        
        has_subtitles = has_subtitles_prob > no_subtitles_prob
        confidence = max(has_subtitles_prob, no_subtitles_prob).item()
        
        return {
            'has_subtitles': has_subtitles,
            'confidence': confidence
        }
    
    def _extract_frames(self, video_path: str, n_frames: int = 6):
        """Extrair frames temporais (mesma lógica Sprint 01)."""
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps > 0 else 0
        
        # Timestamps distribuídos (20%-80% do vídeo)
        timestamps = [
            duration * 0.2,
            duration * 0.35,
            duration * 0.5,
            duration * 0.65,
            duration * 0.8,
            duration * 0.95
        ]
        
        frames = []
        for ts in timestamps:
            cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
            ret, frame = cap.read()
            if ret:
                frames.append(frame)
        
        cap.release()
        return frames
    
    def get_model_name(self) -> str:
        return 'clip'
    
    def get_weight(self) -> float:
        return 0.30  # 30% weight
```

#### 3.3 CRAFTDetector - 1h

```python
# app/video_processing/detectors/craft_detector.py
import craft_text_detector
import cv2
from .base_detector import BaseSubtitleDetector

class CRAFTDetector(BaseSubtitleDetector):
    """
    Text detection usando CRAFT.
    """
    
    def __init__(self, output_dir='storage/craft_output/', use_gpu=True):
        self.detector = craft_text_detector.Craft(
            output_dir=output_dir,
            crop_type="box",
            cuda=use_gpu
        )
    
    def detect(self, video_path: str) -> dict:
        # 1. Extrair frames
        frames = self._extract_frames(video_path, n_frames=6)
        
        # 2. Detectar texto em cada frame
        frame_results = []
        for i, frame in enumerate(frames):
            result = self._detect_in_frame(frame, frame_idx=i)
            frame_results.append(result)
        
        # 3. Agregar resultados
        has_subtitles_votes = sum(1 for r in frame_results if r['has_subtitles'])
        confidence_scores = [r['confidence'] for r in frame_results]
        
        has_subtitles = has_subtitles_votes >= (len(frames) // 2)
        confidence = sum(confidence_scores) / len(confidence_scores)
        
        return {
            'has_subtitles': has_subtitles,
            'confidence': confidence,
            'metadata': {
                'frame_results': frame_results,
                'votes': f'{has_subtitles_votes}/{len(frames)}',
                'model': 'craft'
            }
        }
    
    def _detect_in_frame(self, frame, frame_idx: int) -> dict:
        """Detecta texto em um frame."""
        # Salvar frame temporariamente (CRAFT precisa de arquivo)
        temp_path = f'/tmp/frame_{frame_idx}.jpg'
        cv2.imwrite(temp_path, frame)
        
        # Detectar texto
        prediction_result = self.detector.detect_text(temp_path)
        text_boxes = prediction_result['boxes']
        
        if not text_boxes:
            return {'has_subtitles': False, 'confidence': 0.0}
        
        # Analisar regiões
        frame_height, frame_width = frame.shape[:2]
        
        # Filtrar regiões no bottom 25%
        bottom_boxes = [
            box for box in text_boxes
            if box['y'] + box['height'] > frame_height * 0.75
        ]
        
        if not bottom_boxes:
            return {'has_subtitles': False, 'confidence': 0.2}
        
        # Calcular métricas
        total_text_area = sum(box['width'] * box['height'] for box in text_boxes)
        bottom_text_area = sum(box['width'] * box['height'] for box in bottom_boxes)
        bottom_ratio = bottom_text_area / total_text_area if total_text_area > 0 else 0
        
        # Verificar se há região larga (típico de legenda)
        has_wide_box = any(
            box['width'] > frame_width * 0.3
            for box in bottom_boxes
        )
        
        # Decisão
        has_subtitles = (
            len(bottom_boxes) >= 1 and
            bottom_ratio > 0.5 and
            has_wide_box
        )
        
        confidence = min(bottom_ratio, len(bottom_boxes) / 3.0)
        
        return {
            'has_subtitles': has_subtitles,
            'confidence': confidence
        }
    
    def _extract_frames(self, video_path: str, n_frames: int = 6):
        """Mesma lógica de CLIPClassifier."""
        # ... (copiar implementation do CLIP)
        pass
    
    def get_model_name(self) -> str:
        return 'craft'
    
    def get_weight(self) -> float:
        return 0.25  # 25% weight
```

### Fase 4: Implementar Ensemble (1h)

```python
# app/video_processing/ensemble_detector.py
from typing import Dict, List
from .detectors.base_detector import BaseSubtitleDetector
from .detectors.paddle_detector import PaddleDetector
from .detectors.clip_classifier import CLIPClassifier
from .detectors.craft_detector import CRAFTDetector

class EnsembleSubtitleDetector:
    """
    Ensemble de múltiplos detectores de legenda.
    """
    
    def __init__(
        self,
        detectors: List[BaseSubtitleDetector] = None,
        voting_method: str = 'weighted'
    ):
        if detectors is None:
            # Carregar detectores padrão
            self.detectors = [
                PaddleDetector(roi_mode='multi'),
                CLIPClassifier(),
                CRAFTDetector()
            ]
        else:
            self.detectors = detectors
        
        self.voting_method = voting_method
    
    def detect(self, video_path: str) -> Dict:
        """
        Detecta legendas usando ensemble.
        
        Returns:
            {
                'has_subtitles': bool,
                'confidence': float,
                'votes': dict,  # Resultado de cada detector
                'metadata': dict
            }
        """
        # 1. Rodar todos os detectores
        votes = {}
        for detector in self.detectors:
            model_name = detector.get_model_name()
            result = detector.detect(video_path)
            
            votes[model_name] = {
                'has_subtitles': result['has_subtitles'],
                'confidence': result['confidence'],
                'weight': detector.get_weight(),
                'metadata': result['metadata']
            }
        
        # 2. Votação
        if self.voting_method == 'weighted':
            final_result = self._weighted_voting(votes)
        elif self.voting_method == 'majority':
            final_result = self._majority_voting(votes)
        else:
            raise ValueError(f"Unknown voting method: {self.voting_method}")
        
        # 3. Adicionar metadata
        final_result['votes'] = votes
        final_result['metadata']['ensemble_method'] = self.voting_method
        
        return final_result
    
    def _weighted_voting(self, votes: Dict) -> Dict:
        """Votação ponderada por peso."""
        weighted_score = 0.0
        total_weight = 0.0
        
        for model_name, vote in votes.items():
            if vote['has_subtitles']:
                weighted_score += vote['confidence'] * vote['weight']
            total_weight += vote['weight']
        
        final_confidence = weighted_score / total_weight if total_weight > 0 else 0.0
        final_decision = final_confidence >= 0.5
        
        return {
            'has_subtitles': final_decision,
            'confidence': final_confidence,
            'metadata': {'voting_type': 'weighted'}
        }
    
    def _majority_voting(self, votes: Dict) -> Dict:
        """Votação por maioria simples."""
        yes_votes = sum(1 for v in votes.values() if v['has_subtitles'])
        total_votes = len(votes)
        
        final_decision = yes_votes > (total_votes / 2)
        final_confidence = yes_votes / total_votes if final_decision else \
                          (total_votes - yes_votes) / total_votes
        
        return {
            'has_subtitles': final_decision,
            'confidence': final_confidence,
            'metadata': {
                'voting_type': 'majority',
                'votes_distribution': f'{yes_votes}/{total_votes}'
            }
        }
```

---

## 6️⃣ Testes Esperados

### Estrutura de Testes

```python
# tests/test_sprint06_ensemble.py
import pytest
from app.video_processing.ensemble_detector import EnsembleSubtitleDetector
from app.video_processing.detectors import PaddleDetector, CLIPClassifier, CRAFTDetector

class TestSprint06Ensemble:
    
    @pytest.fixture
    def ensemble_detector(self):
        """Ensemble com 3 detectores."""
        return EnsembleSubtitleDetector()
    
    @pytest.fixture
    def video_with_subs(self):
        """Vídeo com legendas (do dataset Sprint 00)."""
        return "storage/validation/base/video_with_subs_1.mp4"
    
    @pytest.fixture
    def video_without_subs(self):
        """Vídeo sem legendas."""
        return "storage/validation/base/video_without_subs_1.mp4"
    
    # ========== TESTES INDIVIDUAIS ==========
    
    def test_paddle_detector_individual(self, video_with_subs, video_without_subs):
        """Test 1: PaddleDetector standalone."""
        detector = PaddleDetector(roi_mode='multi')
        
        # WITH subs
        result = detector.detect(video_with_subs)
        assert result['has_subtitles'] == True
        assert result['confidence'] > 0.8
        assert result['metadata']['model'] == 'paddleocr'
        
        # WITHOUT subs
        result = detector.detect(video_without_subs)
        assert result['has_subtitles'] == False
    
    def test_clip_classifier_individual(self, video_with_subs, video_without_subs):
        """Test 2: CLIPClassifier standalone."""
        classifier = CLIPClassifier()
        
        # WITH subs
        result = classifier.detect(video_with_subs)
        assert result['has_subtitles'] == True
        assert result['confidence'] > 0.5
        assert result['metadata']['model'] == 'clip'
        
        # WITHOUT subs
        result = classifier.detect(video_without_subs)
        assert result['has_subtitles'] == False
    
    def test_craft_detector_individual(self, video_with_subs, video_without_subs):
        """Test 3: CRAFTDetector standalone."""
        detector = CRAFTDetector()
        
        # WITH subs
        result = detector.detect(video_with_subs)
        assert result['has_subtitles'] == True
        assert result['metadata']['model'] == 'craft'
        
        # WITHOUT subs
        result = detector.detect(video_without_subs)
        assert result['has_subtitles'] == False
    
    # ========== TESTES DE ENSEMBLE ==========
    
    def test_ensemble_weighted_voting(self, ensemble_detector, video_with_subs):
        """Test 4: Ensemble com votação ponderada."""
        result = ensemble_detector.detect(video_with_subs)
        
        assert 'has_subtitles' in result
        assert 'confidence' in result
        assert 'votes' in result
        
        # Verificar que todos os modelos votaram
        assert 'paddle' in result['votes']
        assert 'clip' in result['votes']
        assert 'craft' in result['votes']
        
        # Decisão deve ser True (vídeo tem legendas)
        assert result['has_subtitles'] == True
        assert result['confidence'] > 0.7
    
    def test_ensemble_consensus(self, ensemble_detector):
        """Test 5: Ensemble em consenso (3/3 concordam)."""
        # Usar vídeo óbvio com legendas
        video = "storage/validation/base/video_with_subs_obvious.mp4"
        result = ensemble_detector.detect(video)
        
        # Todos devem concordar
        votes = result['votes']
        yes_votes = sum(1 for v in votes.values() if v['has_subtitles'])
        
        assert yes_votes == 3  # Consenso total
        assert result['has_subtitles'] == True
        assert result['confidence'] > 0.85
    
    def test_ensemble_disagreement(self, ensemble_detector):
        """Test 6: Ensemble em desacordo (2/3 vs 1/3)."""
        # Usar vídeo ambíguo (com texto, mas não legenda típica)
        video = "storage/validation/edge_cases/center/video_with_center_text_2.mp4"
        result = ensemble_detector.detect(video)
        
        # Verificar que houve divergência
        votes = result['votes']
        yes_votes = sum(1 for v in votes.values() if v['has_subtitles'])
        
        assert yes_votes in [1, 2]  # Não-consenso
        
        # Decisão final deve seguir votação ponderada
        assert 'confidence' in result
        assert 0.3 < result['confidence'] < 0.7  # Indecisão
    
    def test_ensemble_vs_paddle_alone(self, video_with_subs):
        """Test 7: Comparar ensemble vs. PaddleOCR alone."""
        # PaddleOCR alone
        paddle = PaddleDetector(roi_mode='multi')
        paddle_result = paddle.detect(video_with_subs)
        
        # Ensemble
        ensemble = EnsembleSubtitleDetector()
        ensemble_result = ensemble.detect(video_with_subs)
        
        # Ambos devem detectar, mas ensemble pode ter confidence diferente
        assert paddle_result['has_subtitles'] == ensemble_result['has_subtitles']
        
        # Ensemble geralmente tem confidence mais calibrado
        print(f"Paddle confidence: {paddle_result['confidence']:.3f}")
        print(f"Ensemble confidence: {ensemble_result['confidence']:.3f}")
    
    # ========== TESTES DE DATASET COMPLETO ==========
    
    def test_ensemble_on_full_dataset(self, ensemble_detector):
        """Test 8: Ensemble em todos os 83 vídeos de teste."""
        import glob
        
        # Carregar ground truth
        with open('storage/validation/ground_truth.json', 'r') as f:
            ground_truth = json.load(f)
        
        results = []
        for video_path, expected in ground_truth.items():
            result = ensemble_detector.detect(video_path)
            results.append({
                'video': video_path,
                'expected': expected,
                'predicted': result['has_subtitles'],
                'confidence': result['confidence'],
                'correct': result['has_subtitles'] == expected
            })
        
        # Calcular métricas
        accuracy = sum(1 for r in results if r['correct']) / len(results)
        
        # Ensemble deve ter accuracy >= 95%
        assert accuracy >= 0.95, f"Ensemble accuracy: {accuracy:.2%} (expected ≥95%)"
        
        # Contar erros
        errors = [r for r in results if not r['correct']]
        print(f"\nEnsemble accuracy: {accuracy:.2%}")
        print(f"Errors: {len(errors)}/{len(results)}")
        for err in errors:
            print(f"  - {err['video']}: expected={err['expected']}, got={err['predicted']}")
    
    # ========== TESTES DE PERFORMANCE ==========
    
    def test_ensemble_performance(self, ensemble_detector, video_with_subs):
        """Test 9: Ensemble performance (<15s por vídeo)."""
        import time
        
        start = time.time()
        result = ensemble_detector.detect(video_with_subs)
        elapsed = time.time() - start
        
        # Ensemble deve ser < 15s (3 modelos × ~5s cada)
        assert elapsed < 15.0, f"Ensemble too slow: {elapsed:.2f}s (expected <15s)"
        
        print(f"\nEnsemble time: {elapsed:.2f}s")
    
    # ========== TESTES DE ROBUSTEZ ==========
    
    def test_ensemble_on_edge_cases(self, ensemble_detector):
        """Test 10: Ensemble em edge cases (Sprint 04)."""
        edge_case_videos = [
            "storage/validation/edge_cases/top/video_with_top_subs_1.mp4",
            "storage/validation/edge_cases/left/video_with_left_text_1.mp4",
            "storage/validation/edge_cases/right/video_with_right_text_1.mp4",
            "storage/validation/edge_cases/center/video_with_center_text_1.mp4"
        ]
        
        for video in edge_case_videos:
            result = ensemble_detector.detect(video)
            
            # Ensemble deve detectar todas as posições
            assert result['has_subtitles'] == True
            assert result['confidence'] > 0.6
            
            print(f"{video}: {result['has_subtitles']} (conf: {result['confidence']:.2f})")
```

**Expected Test Results:**

```
Sprint 06 Tests: 10/10 PASSED
├─ test_paddle_detector_individual: PASSED
├─ test_clip_classifier_individual: PASSED
├─ test_craft_detector_individual: PASSED
├─ test_ensemble_weighted_voting: PASSED
├─ test_ensemble_consensus: PASSED
├─ test_ensemble_disagreement: PASSED
├─ test_ensemble_vs_paddle_alone: PASSED
├─ test_ensemble_on_full_dataset: PASSED (accuracy ≥95%)
├─ test_ensemble_performance: PASSED (<15s)
└─ test_ensemble_on_edge_cases: PASSED

Total: 46/47 tests PASSED (Sprint 00-06)
Run time: ~180s (3 min)
```

---

## 7️⃣ Integração com Sprints Anteriores

### Sprint 00-02: Preprocessamento ✅ MANTIDO
- Resize (Sprint 01) ainda aplicado antes de todos os detectores
- CLAHE (Sprint 02) melhora qualidade para OCR e text detection
- Nenhuma mudança necessária

### Sprint 03: Features ⚠️ OPCIONAL AGORA
- Features visuais NÃO são mais usadas para classificação
- Ensemble usa modelos pré-treinados (não features manuais)
- **MAS**: Features ainda úteis para:
  - Análise e debugging
  - Metadata enriquecida
  - Possível fallback ou filtro pós-ensemble
- **Status**: Manter Sprint 03 como OPCIONAL, não remover

### Sprint 04: Multi-ROI ✅ INTEGRADO
- PaddleDetector no ensemble usa Multi-ROI (roi_mode='multi')
- Multi-ROI melhora performance do componente PaddleOCR
- 100% compatível com ensemble

### Sprint 05: Temporal Aggregation ✅ MANTIDO
- Ainda será implementado (útil para todos os detectores)
- Pode melhorar confidence de CLIP e CRAFT também
- Nenhuma mudança necessária

---

## 📈 Expected Results

### Accuracy Comparison

```
┌──────────────────────┬──────────┬─────────────┬────────┐
│ Method               │ Accuracy │ Precision   │ Recall │
├──────────────────────┼──────────┼─────────────┼────────┤
│ Paddle alone (Sprint │  100.0%  │    100.0%   │ 100.0% │
│ 04)                  │ (83/83)  │             │        │
├──────────────────────┼──────────┼─────────────┼────────┤
│ CLIP alone           │   85-90% │    80-85%   │ 90-95% │
│                      │          │             │        │
├──────────────────────┼──────────┼─────────────┼────────┤
│ CRAFT alone          │   80-85% │    75-80%   │ 85-90% │
│                      │          │             │        │
├──────────────────────┼──────────┼─────────────┼────────┤
│ ENSEMBLE (3 models)  │   95-98% │    95-97%   │ 96-99% │
│                      │          │             │        │
└──────────────────────┴──────────┴─────────────┴────────┘

Goal: ≥95% accuracy on full dataset (200+ videos quando expandir)
```

### Performance

```
Single model:
- PaddleOCR: 3-8s per video
- CLIP: 2-5s per video (with GPU)
- CRAFT: 4-10s per video (with GPU)

Ensemble (parallel):
- Sequential: ~15-20s (soma dos 3)
- Parallel (futuro): ~8-10s (max dos 3)

Goal: <15s per video for ensemble
```

---

## 🚀 Next Steps (Sprint 07)

Após Sprint 06, implementar:

**Sprint 07: Ensemble Voting & Confidence Aggregation**
- Implementar votação avançada (não só weighted)
- Detecção de conflitos (quando modelos discordam muito)
- Calibração de confidence (Platt scaling por modelo)
- Ajuste dinâmico de pesos baseado em performance
- A/B testing framework

---

## 📝 Acceptance Criteria

- ✅ 3 detectores implementados (Paddle, CLIP, CRAFT)
- ✅ Ensemble system com votação ponderada
- ✅ 10 testes de pytest (individuais + ensemble)
- ✅ Accuracy ≥95% no dataset completo (83+ vídeos)
- ✅ Performance <15s por vídeo
- ✅ 100% backward compatible (Sprint 00-05 mantidos)
- ✅ Zero manual labeling (all plug and play)
- ✅ Documentação completa (README + docstrings)

---

## ⚠️ Dependencies

### External Packages

```bash
# requirements.txt additions
transformers==4.36.0      # CLIP
torch==2.1.0              # CLIP backend
pillow==10.1.0            # Image processing
craft-text-detector==0.4.3  # CRAFT
easyocr==1.7.0            # EasyOCR (optional)
```

### Model Downloads (Auto)

- CLIP: `~/.cache/huggingface/` (~600MB)
- CRAFT: `~/.craft_text_detector/` (~150MB)
- EasyOCR: `~/.EasyOCR/model/` (~150MB per language)

**Total**: ~900MB-1.2GB additional storage

---

## 🎯 Success Metrics

```python
success_criteria = {
    'accuracy': '≥95% on 83 test videos',
    'precision': '≥95%',
    'recall': '≥96%',
    'performance': '<15s per video',
    'code_coverage': '≥90%',
    'backward_compatible': 'Sprint 00-05 tests still passing',
    'manual_work': '0 hours (100% automated)',
    'implementation_time': '4-6 hours'
}
```

---

**Status**: 🟢 Ready to implement  
**Blocker**: None (Sprint 00-04 complete)  
**Next Sprint**: Sprint 07 (Voting & Confidence)
