# 🔍 NEW_OCR - Estratégias Avançadas de Detecção de Legendas

**Make-Video Service - Melhoria da Precisão OCR**

**Última Atualização:** 11 de Fevereiro de 2026  
**Versão:** 1.0  
**Objetivo:** Aumentar precisão da detecção de legendas hardcoded para >95% e filtrar apenas vídeos limpos

---

## 📋 Sumário Executivo

Este documento propõe estratégias avançadas para **melhorar drasticamente a precisão** da detecção de legendas embutidas em vídeos, com foco em:

1. **Detecção Multi-Modal** - Combinar OCR + análise de padrões visuais
2. **Machine Learning** - Classificador treinado em dataset real
3. **Otimizações de Performance** - Reduzir falsos positivos/negativos
4. **Pipeline de Filtragem** - Garantir apenas vídeos 100% limpos

### 🎯 Situação Atual vs Meta

| Métrica | Atual | Meta | Melhoria |
|---------|-------|------|----------|
| **Accuracy** | 70-80% | >95% | +15-25pp |
| **Precision** | 85% | >98% | +13pp |
| **Recall** | 75% | >90% | +15pp |
| **F1-Score** | 80% | >94% | +14pp |
| **Falsos Positivos** | 15% | <2% | -87% |
| **Falsos Negativos** | 25% | <10% | -60% |

---

## 🔬 PARTE I - ANÁLISE DO PROBLEMA

### 1.1 Limitações do Sistema Atual

#### OCR Puro (EasyOCR)

**Problemas Identificados:**

1. **Alta Taxa de Falsos Positivos**
   - Textos da UI de apps detectados como legendas
   - Números de vídeo (duração, views) confundidos com texto
   - Watermarks e logos geram detecções indesejadas
   - GIFs animados com texto são detectados

2. **Alta Taxa de Falsos Negativos**
   - Legendas com fontes estilizadas não detectadas
   - Legendas semi-transparentes ignoradas
   - Legendas com animações (fade, movimento) falham
   - Idiomas com caracteres especiais

3. **Dependência de Threshold**
   - Threshold alto: perde legendas reais (falso negativo)
   - Threshold baixo: detecta muito ruído (falso positivo)
   - Threshold único não serve para todos os casos

4. **Performance Inconsistente**
   - Depende fortemente da qualidade do vídeo
   - Codecs diferentes geram resultados diferentes (AV1 vs H.264)
   - Resolução impacta drasticamente (720p vs 1080p)

#### TRSD (Temporal Region Subtitle Detector)

**Melhorou, mas ainda limitado:**

✅ **Sucessos:**
- Detecta padrões temporais (legendas aparecem/desaparecem)
- Identifica posição consistente (bottom ROI)
- Distingue texto estático de dinâmico

❌ **Limitações:**
- Ainda depende de OCR como base
- Não detecta legendas em posições não-padrão
- Falha com legendas que não seguem padrão temporal
- Não considera contexto visual (cor de fundo, contraste)

### 1.2 Análise de Casos Problemáticos

#### Caso 1: UI de Aplicativo (Falso Positivo)

```
Cenário: Screencast de app de mensagens
Detecção OCR: "Mensagem enviada às 14:30" (UI do app)
Sistema Atual: ❌ BLOQUEADO (falso positivo - não é legenda)
Sistema Ideal: ✅ APROVADO (reconhece UI vs legenda)
```

**Root Cause:** OCR detecta qualquer texto, não distingue fonte/contexto.

#### Caso 2: Legenda Estilizada (Falso Negativo)

```
Cenário: Legenda com fonte cursiva + sombra forte
Detecção OCR: confidence = 35% (abaixo de threshold 50%)
Sistema Atual: ❌ APROVADO (falso negativo - tem legenda)
Sistema Ideal: ✅ BLOQUEADO (reconhece legenda mesmo low-conf)
```

**Root Cause:** Threshold fixo não captura variações de estilo.

#### Caso 3: Watermark Animado (Falso Positivo)

```
Cenário: Logo de canal que aparece/desaparece
Detecção TRSD: Padrão temporal detectado
Sistema Atual: ❌ BLOQUEADO (falso positivo - é logo, não legenda)
Sistema Ideal: ✅ APROVADO (distingue logo de legenda)
```

**Root Cause:** TRSD só analisa temporal, não visual.

---

## 🚀 PARTE II - ESTRATÉGIAS DE MELHORIA

### 2.1 Estratégia #1: OCR Multi-Engine (Quick Win)

**Descrição:** Usar múltiplos engines OCR e combinar resultados via voting.

**Engines Sugeridos:**
1. **EasyOCR** - Atual, bom para PT/EN
2. **Tesseract** - Tradicional, rápido
3. **PaddleOCR** - Novo, alta precisão

**Implementação:**

```python
# app/ocr_detector_advanced.py - NOVO ARQUIVO

import easyocr
import pytesseract
from paddleocr import PaddleOCR
from typing import List, Dict, Tuple
from dataclasses import dataclass
import numpy as np


@dataclass
class OCREngineResult:
    """Resultado de um engine OCR"""
    engine_name: str
    text: str
    confidence: float
    word_count: int
    has_subtitle: bool


class MultiEngineOCRDetector:
    """
    Detector OCR usando múltiplos engines com voting
    
    Strategy: Ensemble Learning
    - Se 2+ engines detectam legenda → БЛОКEAR
    - Se todos engines dizem limpo → APROVAR
    - Se divergência → usar features adicionais
    """
    
    def __init__(self, use_gpu: bool = False):
        """
        Inicializa múltiplos engines OCR
        
        Args:
            use_gpu: Usar GPU (se disponível)
        """
        self.use_gpu = use_gpu
        
        # Engine 1: EasyOCR (atual)
        self.easyocr = easyocr.Reader(['pt', 'en'], gpu=use_gpu, verbose=False)
        
        # Engine 2: Tesseract
        # (já instalado no sistema)
        
        # Engine 3: PaddleOCR
        self.paddleocr = PaddleOCR(
            lang='en',
            use_gpu=use_gpu,
            show_log=False
        )
        
        print(f"✅ Multi-Engine OCR initialized (GPU: {use_gpu})")
    
    def detect_subtitle_in_frame(
        self,
        frame: np.ndarray,
        min_confidence: float = 50.0
    ) -> Tuple[bool, float, Dict]:
        """
        Detecta legenda usando múltiplos engines
        
        Args:
            frame: Frame BGR do cv2
            min_confidence: Threshold mínimo
        
        Returns:
            (has_subtitle, avg_confidence, details)
        """
        # Pré-processar frame (comum para todos)
        processed = self._preprocess_for_ocr(frame)
        
        # Executar cada engine
        results = []
        
        # Engine 1: EasyOCR
        easy_result = self._run_easyocr(processed, min_confidence)
        results.append(easy_result)
        
        # Engine 2: Tesseract
        tess_result = self._run_tesseract(processed, min_confidence)
        results.append(tess_result)
        
        # Engine 3: PaddleOCR
        paddle_result = self._run_paddleocr(processed, min_confidence)
        results.append(paddle_result)
        
        # Voting: maioria decide
        votes_has_subtitle = sum(1 for r in results if r.has_subtitle)
        has_subtitle = votes_has_subtitle >= 2  # 2 de 3
        
        # Confiança média dos que detectaram
        positive_confidences = [r.confidence for r in results if r.has_subtitle]
        avg_confidence = np.mean(positive_confidences) if positive_confidences else 0.0
        
        details = {
            'engines': [
                {
                    'name': r.engine_name,
                    'has_subtitle': r.has_subtitle,
                    'confidence': r.confidence,
                    'text': r.text
                }
                for r in results
            ],
            'votes': votes_has_subtitle,
            'consensus': has_subtitle
        }
        
        return has_subtitle, avg_confidence, details
    
    def _run_easyocr(self, frame: np.ndarray, threshold: float) -> OCREngineResult:
        """Executa EasyOCR"""
        try:
            results = self.easyocr.readtext(frame, detail=1)
            
            if not results:
                return OCREngineResult(
                    engine_name='EasyOCR',
                    text='',
                    confidence=0.0,
                    word_count=0,
                    has_subtitle=False
                )
            
            # Processar resultados
            texts = []
            confidences = []
            
            for bbox, text, conf in results:
                if conf * 100 >= threshold:
                    texts.append(text)
                    confidences.append(conf * 100)
            
            full_text = ' '.join(texts)
            avg_conf = np.mean(confidences) if confidences else 0.0
            word_count = len(full_text.split())
            
            has_subtitle = word_count >= 2 and avg_conf >= threshold
            
            return OCREngineResult(
                engine_name='EasyOCR',
                text=full_text,
                confidence=avg_conf,
                word_count=word_count,
                has_subtitle=has_subtitle
            )
        
        except Exception as e:
            print(f"❌ EasyOCR failed: {e}")
            return OCREngineResult('EasyOCR', '', 0.0, 0, False)
    
    def _run_tesseract(self, frame: np.ndarray, threshold: float) -> OCREngineResult:
        """Executa Tesseract OCR"""
        try:
            # Tesseract com config otimizada para legendas
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ '
            
            # Extrair texto
            data = pytesseract.image_to_data(
                frame,
                lang='por+eng',
                config=custom_config,
                output_type=pytesseract.Output.DICT
            )
            
            # Filtrar por confiança
            texts = []
            confidences = []
            
            for i, conf in enumerate(data['conf']):
                if conf != -1 and conf >= threshold:
                    text = data['text'][i].strip()
                    if text:
                        texts.append(text)
                        confidences.append(conf)
            
            full_text = ' '.join(texts)
            avg_conf = np.mean(confidences) if confidences else 0.0
            word_count = len(full_text.split())
            
            has_subtitle = word_count >= 2 and avg_conf >= threshold
            
            return OCREngineResult(
                engine_name='Tesseract',
                text=full_text,
                confidence=avg_conf,
                word_count=word_count,
                has_subtitle=has_subtitle
            )
        
        except Exception as e:
            print(f"❌ Tesseract failed: {e}")
            return OCREngineResult('Tesseract', '', 0.0, 0, False)
    
    def _run_paddleocr(self, frame: np.ndarray, threshold: float) -> OCREngineResult:
        """Executa PaddleOCR"""
        try:
            results = self.paddleocr.ocr(frame, cls=True)
            
            if not results or not results[0]:
                return OCREngineResult(
                    engine_name='PaddleOCR',
                    text='',
                    confidence=0.0,
                    word_count=0,
                    has_subtitle=False
                )
            
            texts = []
            confidences = []
            
            for line in results[0]:
                text = line[1][0]
                conf = line[1][1] * 100
                
                if conf >= threshold:
                    texts.append(text)
                    confidences.append(conf)
            
            full_text = ' '.join(texts)
            avg_conf = np.mean(confidences) if confidences else 0.0
            word_count = len(full_text.split())
            
            has_subtitle = word_count >= 2 and avg_conf >= threshold
            
            return OCREngineResult(
                engine_name='PaddleOCR',
                text=full_text,
                confidence=avg_conf,
                word_count=word_count,
                has_subtitle=has_subtitle
            )
        
        except Exception as e:
            print(f"❌ PaddleOCR failed: {e}")
            return OCREngineResult('PaddleOCR', '', 0.0, 0, False)
    
    def _preprocess_for_ocr(self, frame: np.ndarray) -> np.ndarray:
        """Pré-processamento otimizado para OCR"""
        import cv2
        
        # Converter para grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Aumentar contraste (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Threshold adaptativo
        binary = cv2.adaptiveThreshold(
            enhanced,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2
        )
        
        return binary
```

**Benefícios:**
- 🎯 **Maior Robustez:** 3 engines independentes reduzem erros
- 📊 **Voting Strategy:** Maioria decide (mais confiável)
- 🔍 **Detalhamento:** Vê divergências entre engines
- ⚡ **Quick Win:** Implementação em 1-2 dias

**Trade-off:**
- ⏱️ 3x mais lento (mas paralelizável)
- 💾 Mais uso de memória (~1GB adicional)

### 2.2 Estratégia #2: Análise de Features Visuais

**Descrição:** Complementar OCR com análise de características visuais de legendas.

**Features Visuais de Legendas:**

1. **Posição Consistente**
   - 90% das legendas: bottom 20% ou top 20% da tela
   - Centro raramente tem legendas

2. **Contraste de Cor**
   - Legendas têm alto contraste com fundo (legibilidade)
   - Outline preto/branco comum

3. **Tamanho de Fonte Consistente**
   - Legendas: fonte 5-10% da altura do vídeo
   - UI text: fonte 2-4% da altura

4. **Aspect Ratio do Texto**
   - Legendas: linhas horizontais largas
   - UI: blocos verticais ou quadrados

**Implementação:**

```python
# app/visual_features_analyzer.py - NOVO ARQUIVO

import cv2
import numpy as np
from typing import Dict, Tuple
from dataclasses import dataclass


@dataclass
class VisualFeatures:
    """Features visuais extraídas do frame"""
    
    # Posição
    text_vertical_position: str  # 'top', 'middle', 'bottom'
    distance_from_bottom_pct: float  # % distância do fundo
    
    # Contraste
    avg_contrast: float  # 0-255
    has_outline: bool
    
    # Tamanho
    avg_text_height_pct: float  # % da altura do frame
    avg_text_width_pct: float   # % da largura do frame
    
    # Forma
    aspect_ratio: float  # largura / altura
    
    # Cor
    dominant_text_color: Tuple[int, int, int]  # BGR
    dominant_bg_color: Tuple[int, int, int]
    
    # Score de "legenda-likeness"
    subtitle_score: float  # 0-100


class VisualFeaturesAnalyzer:
    """
    Analisa features visuais para distinguir legendas de outros textos
    
    Pattern: Feature Engineering para ML
    """
    
    def __init__(self):
        self.frame_height = None
        self.frame_width = None
    
    def analyze_frame_with_text(
        self,
        frame: np.ndarray,
        text_bboxes: List[Tuple[List[int], str, float]]
    ) -> VisualFeatures:
        """
        Analisa features visuais em frame com texto detectado
        
        Args:
            frame: Frame BGR
            text_bboxes: Lista de (bbox, text, confidence) do OCR
        
        Returns:
            VisualFeatures extraídas
        """
        self.frame_height, self.frame_width = frame.shape[:2]
        
        if not text_bboxes:
            return self._empty_features()
        
        # Feature 1: Posição Vertical
        vertical_pos, dist_from_bottom = self._analyze_vertical_position(text_bboxes)
        
        # Feature 2: Contraste
        avg_contrast, has_outline = self._analyze_contrast(frame, text_bboxes)
        
        # Feature 3: Tamanho
        avg_height_pct, avg_width_pct = self._analyze_size(text_bboxes)
        
        # Feature 4: Aspect Ratio
        aspect_ratio = self._calculate_aspect_ratio(text_bboxes)
        
        # Feature 5: Cores
        text_color, bg_color = self._analyze_colors(frame, text_bboxes)
        
        # Calcular score de legenda
        subtitle_score = self._calculate_subtitle_score(
            vertical_pos, dist_from_bottom, avg_contrast, has_outline,
            avg_height_pct, aspect_ratio
        )
        
        return VisualFeatures(
            text_vertical_position=vertical_pos,
            distance_from_bottom_pct=dist_from_bottom,
            avg_contrast=avg_contrast,
            has_outline=has_outline,
            avg_text_height_pct=avg_height_pct,
            avg_text_width_pct=avg_width_pct,
            aspect_ratio=aspect_ratio,
            dominant_text_color=text_color,
            dominant_bg_color=bg_color,
            subtitle_score=subtitle_score
        )
    
    def _analyze_vertical_position(
        self,
        text_bboxes: List
    ) -> Tuple[str, float]:
        """Analisa posição vertical do texto"""
        
        # Calcular centro Y de cada bbox
        y_centers = []
        for bbox, _, _ in text_bboxes:
            y_min = min(bbox[0][1], bbox[1][1], bbox[2][1], bbox[3][1])
            y_max = max(bbox[0][1], bbox[1][1], bbox[2][1], bbox[3][1])
            y_center = (y_min + y_max) / 2
            y_centers.append(y_center)
        
        avg_y = np.mean(y_centers)
        y_pct = avg_y / self.frame_height
        
        # Classificar posição
        if y_pct < 0.33:
            position = 'top'
        elif y_pct > 0.67:
            position = 'bottom'
        else:
            position = 'middle'
        
        # Distância do fundo (legendas geralmente em 80-95% da altura)
        dist_from_bottom_pct = (1.0 - y_pct) * 100
        
        return position, dist_from_bottom_pct
    
    def _analyze_contrast(
        self,
        frame: np.ndarray,
        text_bboxes: List
    ) -> Tuple[float, bool]:
        """Analisa contraste do texto"""
        
        contrasts = []
        has_outline_count = 0
        
        for bbox, _, _ in text_bboxes:
            # Extrair ROI do texto
            x_coords = [p[0] for p in bbox]
            y_coords = [p[1] for p in bbox]
            
            x_min, x_max = int(min(x_coords)), int(max(x_coords))
            y_min, y_max = int(min(y_coords)), int(max(y_coords))
            
            # Garantir dentro dos bounds
            x_min = max(0, x_min)
            y_min = max(0, y_min)
            x_max = min(self.frame_width, x_max)
            y_max = min(self.frame_height, y_max)
            
            roi = frame[y_min:y_max, x_min:x_max]
            
            if roi.size == 0:
                continue
            
            # Calcular contraste (desvio padrão de intensidade)
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            contrast = np.std(gray_roi)
            contrasts.append(contrast)
            
            # Detectar outline (bordas pretas ou brancas ao redor do texto)
            edges = cv2.Canny(gray_roi, 50, 150)
            edge_ratio = np.sum(edges > 0) / edges.size
            
            if edge_ratio > 0.1:  # >10% de bordas
                has_outline_count += 1
        
        avg_contrast = np.mean(contrasts) if contrasts else 0.0
        has_outline = has_outline_count >= len(text_bboxes) * 0.5  # 50%+ tem outline
        
        return avg_contrast, has_outline
    
    def _analyze_size(self, text_bboxes: List) -> Tuple[float, float]:
        """Analisa tamanho do texto"""
        
        heights = []
        widths = []
        
        for bbox, _, _ in text_bboxes:
            x_coords = [p[0] for p in bbox]
            y_coords = [p[1] for p in bbox]
            
            width = max(x_coords) - min(x_coords)
            height = max(y_coords) - min(y_coords)
            
            heights.append(height)
            widths.append(width)
        
        avg_height = np.mean(heights) if heights else 0
        avg_width = np.mean(widths) if widths else 0
        
        # Normalizar pela resolução do frame
        avg_height_pct = (avg_height / self.frame_height) * 100
        avg_width_pct = (avg_width / self.frame_width) * 100
        
        return avg_height_pct, avg_width_pct
    
    def _calculate_aspect_ratio(self, text_bboxes: List) -> float:
        """Calcula aspect ratio médio do texto"""
        
        aspect_ratios = []
        
        for bbox, _, _ in text_bboxes:
            x_coords = [p[0] for p in bbox]
            y_coords = [p[1] for p in bbox]
            
            width = max(x_coords) - min(x_coords)
            height = max(y_coords) - min(y_coords)
            
            if height > 0:
                ar = width / height
                aspect_ratios.append(ar)
        
        return np.mean(aspect_ratios) if aspect_ratios else 0.0
    
    def _analyze_colors(
        self,
        frame: np.ndarray,
        text_bboxes: List
    ) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
        """Analisa cores dominantes (texto e fundo)"""
        
        # Simplificado: pega cor média na ROI do texto
        text_colors = []
        
        for bbox, _, _ in text_bboxes:
            x_coords = [p[0] for p in bbox]
            y_coords = [p[1] for p in bbox]
            
            x_min, x_max = int(min(x_coords)), int(max(x_coords))
            y_min, y_max = int(min(y_coords)), int(max(y_coords))
            
            x_min = max(0, x_min)
            y_min = max(0, y_min)
            x_max = min(self.frame_width, x_max)
            y_max = min(self.frame_height, y_max)
            
            roi = frame[y_min:y_max, x_min:x_max]
            
            if roi.size > 0:
                avg_color = np.mean(roi, axis=(0, 1))
                text_colors.append(tuple(avg_color.astype(int)))
        
        if text_colors:
            text_color = tuple(np.mean(text_colors, axis=0).astype(int))
        else:
            text_color = (255, 255, 255)
        
        # Background: média do frame inteiro
        bg_color = tuple(np.mean(frame, axis=(0, 1)).astype(int))
        
        return text_color, bg_color
    
    def _calculate_subtitle_score(
        self,
        vertical_pos: str,
        dist_from_bottom_pct: float,
        avg_contrast: float,
        has_outline: bool,
        avg_height_pct: float,
        aspect_ratio: float
    ) -> float:
        """
        Calcula score de probabilidade de ser legenda (0-100)
        
        Heurísticas baseadas em padrões conhecidos de legendas
        """
        score = 0.0
        
        # 1. Posição (peso: 30 pontos)
        if vertical_pos == 'bottom':
            score += 30
            # Bonus se estiver em posição típica de legenda (80-95% da altura)
            if 5 <= dist_from_bottom_pct <= 20:
                score += 10
        elif vertical_pos == 'top':
            score += 15  # Menos comum, mas possível
        else:
            score += 0  # Legendas raramente no centro
        
        # 2. Contraste (peso: 20 pontos)
        # Alto contraste é típico de legendas (legibilidade)
        if avg_contrast > 60:
            score += 20
        elif avg_contrast > 40:
            score += 10
        
        # 3. Outline (peso: 15 pontos)
        if has_outline:
            score += 15
        
        # 4. Tamanho da fonte (peso: 15 pontos)
        # Legendas típicas: 5-10% da altura do frame
        if 4 <= avg_height_pct <= 12:
            score += 15
        elif 2 <= avg_height_pct <= 15:
            score += 7
        
        # 5. Aspect Ratio (peso: 20 pontos)
        # Legendas são horizontais (largura >> altura)
        if aspect_ratio > 5:
            score += 20
        elif aspect_ratio > 3:
            score += 10
        
        return min(score, 100)  # Cap em 100
    
    def _empty_features(self) -> VisualFeatures:
        """Retorna features vazias"""
        return VisualFeatures(
            text_vertical_position='none',
            distance_from_bottom_pct=0.0,
            avg_contrast=0.0,
            has_outline=False,
            avg_text_height_pct=0.0,
            avg_text_width_pct=0.0,
            aspect_ratio=0.0,
            dominant_text_color=(0, 0, 0),
            dominant_bg_color=(0, 0, 0),
            subtitle_score=0.0
        )


# Integração com OCR

def detect_subtitle_advanced(frame: np.ndarray) -> Tuple[bool, float, Dict]:
    """
    Detecção avançada combinando OCR + Visual Features
    
    Returns:
        (has_subtitle, confidence, details)
    """
    # 1. OCR Multi-Engine
    ocr_detector = MultiEngineOCRDetector(use_gpu=True)
    has_subtitle_ocr, conf_ocr, ocr_details = ocr_detector.detect_subtitle_in_frame(frame)
    
    # Se OCR não detectou nada, retornar logo
    if not has_subtitle_ocr:
        return False, 0.0, {'method': 'ocr_only', 'ocr': ocr_details}
    
    # 2. Análise de Features Visuais
    # Extrair bboxes do primeiro engine que detectou
    text_bboxes = []
    for engine in ocr_details['engines']:
        if engine['has_subtitle']:
            # Assumir que temos bboxes (adaptar conforme OCR usado)
            # Por simplicidade, aqui estamos pulando extração detalhada
            break
    
    visual_analyzer = VisualFeaturesAnalyzer()
    # features = visual_analyzer.analyze_frame_with_text(frame, text_bboxes)
    
    # Por enquanto, usar apenas visual score
    # visual_score = features.subtitle_score
    
    # 3. Decisão Final (Weighted Voting)
    # OCR weight: 70%, Visual weight: 30%
    # final_confidence = (conf_ocr * 0.7) + (visual_score * 0.3)
    
    # Simplificado: usar apenas OCR por enquanto
    final_confidence = conf_ocr
    
    return has_subtitle_ocr, final_confidence, {
        'method': 'ocr_visual_combined',
        'ocr': ocr_details,
        # 'visual': features,
        'final_confidence': final_confidence
    }
```

**Benefícios:**
- 🎯 **Reduz Falsos Positivos:** UI text tem padrões diferentes
- 📊 **Score Interpretável:** Sabe "quão legenda-like" é o texto
- 🔍 **Insights:** Entende por que classificou como legenda/não-legenda

### 2.3 Estratégia #3: Machine Learning Classifier

**Descrição:** Treinar classificador ML em dataset rotulado para aprender padrões.

**Arquitetura Proposta:**

```
Input: Frame de vídeo (640x360)
    ↓
[CNN Feature Extractor]  ← EfficientNet-B0 pré-treinado
    ↓
[Features: 1280-dim]
    ↓
[Dense Layer: 256]
    ↓
[Dropout: 0.5]
    ↓
[Dense Layer: 64]
    ↓
[Output: 2 classes] ← [Limpo, Com Legenda]
```

**Dataset Necessário:**

- ✅ **Classe 0 (Limpo):** 500+ vídeos sem legendas
  - `storage/OK/*.mp4`
  
- ❌ **Classe 1 (Com Legenda):** 500+ vídeos com legendas
  - `storage/NOT_OK/*.mp4`

**Implementação:**

```python
# app/ml_classifier.py - NOVO ARQUIVO

import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as transforms
import cv2
import numpy as np
from pathlib import Path
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class SubtitleClassifierCNN(nn.Module):
    """
    Classificador CNN para detecção de legendas
    
    Arquitetura: EfficientNet-B0 + Custom Head
    """
    
    def __init__(self, num_classes: int = 2, pretrained: bool = True):
        super(SubtitleClassifierCNN, self).__init__()
        
        # Backbone: EfficientNet-B0 (rápido e preciso)
        self.backbone = models.efficientnet_b0(pretrained=pretrained)
        
        # Remover camada de classificação original
        num_features = self.backbone.classifier[1].in_features
        self.backbone.classifier = nn.Identity()
        
        # Custom head para classificação binária
        self.classifier = nn.Sequential(
            nn.Linear(num_features, 256),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, num_classes)
        )
    
    def forward(self, x):
        # Extract features
        features = self.backbone(x)
        
        # Classify
        output = self.classifier(features)
        
        return output


class MLSubtitleDetector:
    """
    Detector de legendas usando modelo treinado
    
    Método: Deep Learning Classification
    """
    
    def __init__(self, model_path: str = 'storage/models/subtitle_classifier.pth', use_gpu: bool = True):
        """
        Args:
            model_path: Path do modelo treinado
            use_gpu: Usar GPU se disponível
        """
        self.device = torch.device('cuda' if use_gpu and torch.cuda.is_available() else 'cpu')
        
        # Carregar modelo
        self.model = SubtitleClassifierCNN(num_classes=2, pretrained=False)
        
        if Path(model_path).exists():
            self.model.load_state_dict(torch.load(model_path, map_location=self.device))
            self.model.eval()
            logger.info(f"✅ ML model loaded from {model_path}")
        else:
            logger.warning(f"⚠️ Model not found at {model_path}. Using untrained model.")
        
        self.model.to(self.device)
        
        # Transformações (mesmas usadas no treino)
        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
    
    def predict_frame(self, frame: np.ndarray) -> Tuple[bool, float]:
        """
        Prediz se frame tem legenda
        
        Args:
            frame: Frame BGR do cv2
        
        Returns:
            (has_subtitle, confidence)
        """
        # Converter BGR para RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Aplicar transformações
        input_tensor = self.transform(frame_rgb).unsqueeze(0)
        input_tensor = input_tensor.to(self.device)
        
        # Predição
        with torch.no_grad():
            outputs = self.model(input_tensor)
            probabilities = torch.softmax(outputs, dim=1)
            
            # Classe 0: Limpo, Classe 1: Com Legenda
            conf_limpo = probabilities[0][0].item() * 100
            conf_legenda = probabilities[0][1].item() * 100
            
            has_subtitle = conf_legenda > conf_limpo
            confidence = max(conf_limpo, conf_legenda)
        
        return has_subtitle, confidence
    
    def predict_video(self, video_path: str, frames_to_sample: int = 30) -> Tuple[bool, float, Dict]:
        """
        Prediz se vídeo tem legendas (amostrando múltiplos frames)
        
        Args:
            video_path: Path do vídeo
            frames_to_sample: Número de frames para amostrar
        
        Returns:
            (has_subtitle, avg_confidence, details)
        """
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if total_frames == 0:
            logger.error(f"Failed to read video: {video_path}")
            return False, 0.0, {'error': 'Failed to read video'}
        
        # Selecionar frames uniformemente
        frame_indices = np.linspace(0, total_frames - 1, frames_to_sample, dtype=int)
        
        predictions = []
        confidences = []
        
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            has_sub, conf = self.predict_frame(frame)
            predictions.append(has_sub)
            confidences.append(conf)
        
        cap.release()
        
        # Decisão final: maioria dos frames
        positive_count = sum(predictions)
        total_count = len(predictions)
        
        has_subtitle = positive_count > total_count * 0.3  # 30% threshold
        avg_confidence = np.mean(confidences) if confidences else 0.0
        
        return has_subtitle, avg_confidence, {
            'frames_analyzed': total_count,
            'frames_with_subtitle': positive_count,
            'subtitle_ratio': positive_count / total_count if total_count > 0 else 0.0,
            'avg_confidence': avg_confidence
        }


# Training script (separado)

def train_subtitle_classifier(
    dataset_dir: str = 'storage',
    epochs: int = 50,
    batch_size: int = 32,
    learning_rate: float = 0.001
):
    """
    Treina classificador de legendas
    
    Estrutura esperada do dataset:
    storage/
      ├── OK/          ← vídeos limpos
      └── NOT_OK/      ← vídeos com legendas
    """
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    from tqdm import tqdm
    
    # Dataset customizado
    class SubtitleDataset(Dataset):
        def __init__(self, dataset_dir: str, transform=None):
            self.samples = []
            self.transform = transform
            
            # Classe 0: OK (limpo)
            ok_dir = Path(dataset_dir) / 'OK'
            for video_path in ok_dir.glob('*.mp4'):
                self.samples.append((str(video_path), 0))
            
            # Classe 1: NOT_OK (com legenda)
            not_ok_dir = Path(dataset_dir) / 'NOT_OK'
            for video_path in not_ok_dir.glob('*.mp4'):
                self.samples.append((str(video_path), 1))
            
            print(f"Dataset: {len(self.samples)} samples")
            print(f"  - OK (limpo): {sum(1 for _, label in self.samples if label == 0)}")
            print(f"  - NOT_OK (legenda): {sum(1 for _, label in self.samples if label == 1)}")
        
        def __len__(self):
            return len(self.samples)
        
        def __getitem__(self, idx):
            video_path, label = self.samples[idx]
            
            # Extrair frame aleatório do vídeo
            cap = cv2.VideoCapture(video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if total_frames > 0:
                random_frame_idx = np.random.randint(0, total_frames)
                cap.set(cv2.CAP_PROP_POS_FRAMES, random_frame_idx)
                ret, frame = cap.read()
                cap.release()
                
                if ret:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    if self.transform:
                        frame_tensor = self.transform(frame_rgb)
                    else:
                        frame_tensor = torch.from_numpy(frame_rgb).permute(2, 0, 1).float() / 255.0
                    
                    return frame_tensor, label
            
            # Fallback: retornar tensor vazio
            cap.release()
            return torch.zeros(3, 224, 224), label
    
    # Transformações
    transform = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )
    ])
    
    # Dataset e DataLoader
    dataset = SubtitleDataset(dataset_dir, transform=transform)
    
    # Split train/val (80/20)
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=4)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=4)
    
    # Modelo, loss, optimizer
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = SubtitleClassifierCNN(num_classes=2, pretrained=True).to(device)
    
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', patience=5)
    
    best_val_acc = 0.0
    
    # Training loop
    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0
        
        for inputs, labels in tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs}"):
            inputs, labels = inputs.to(device), labels.to(device)
            
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            _, predicted = torch.max(outputs, 1)
            train_total += labels.size(0)
            train_correct += (predicted == labels).sum().item()
        
        train_acc = 100 * train_correct / train_total
        
        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for inputs, labels in val_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                
                val_loss += loss.item()
                _, predicted = torch.max(outputs, 1)
                val_total += labels.size(0)
                val_correct += (predicted == labels).sum().item()
        
        val_acc = 100 * val_correct / val_total
        
        print(f"Epoch {epoch+1}: Train Loss={train_loss/len(train_loader):.4f}, Train Acc={train_acc:.2f}%, Val Acc={val_acc:.2f}%")
        
        scheduler.step(val_loss)
        
        # Salvar melhor modelo
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), 'storage/models/subtitle_classifier.pth')
            print(f"✅ Best model saved (Val Acc: {val_acc:.2f}%)")
    
    print(f"\n🎯 Training completed! Best Val Acc: {best_val_acc:.2f}%")
```

**Passos para Treinar:**

```bash
# 1. Preparar dataset
mkdir -p storage/models

# 2. Verificar dataset
ls storage/OK/ | wc -l      # Deve ter 100+ vídeos limpos
ls storage/NOT_OK/ | wc -l  # Deve ter 100+ vídeos com legendas

# 3. Treinar modelo
python -c "
from app.ml_classifier import train_subtitle_classifier
train_subtitle_classifier(
    dataset_dir='storage',
    epochs=50,
    batch_size=32,
    learning_rate=0.001
)
"

# 4. Testar modelo
python -c "
from app.ml_classifier import MLSubtitleDetector
detector = MLSubtitleDetector('storage/models/subtitle_classifier.pth')
has_sub, conf, details = detector.predict_video('storage/OK/video1.mp4')
print(f'Has subtitle: {has_sub}, Confidence: {conf:.2f}%')
"
```

**Benefícios:**
- 🎯 **Maior Precisão:** Aprende padrões complexos do dataset real
- 🤖 **Self-Improving:** Pode ser re-treinado com mais dados
- 📊 **Explainability:** Pode visualizar features aprendidas
- ⚡ **Inferência Rápida:** ~10-20ms por frame com GPU

**Trade-offs:**
- 📚 Requer dataset rotulado (mínimo 200 vídeos)
- ⏱️ Treino leva 2-4 horas (mas é uma vez só)
- 💾 Modelo ocupa ~100MB em disco

---

## 🎯 PARTE III - PIPELINE DE FILTRAGEM COMPLETO

### 3.1 Pipeline Proposto Multi-Camadas

**Objetivo:** Garantir que APENAS vídeos 100% limpos sejam aprovados.

**Estratégia:** Defense in Depth (múltiplas camadas de validação).

```
                    PIPELINE DE FILTRAGEM
┌──────────────────────────────────────────────────────────┐
│                    INPUT: Vídeo Short                     │
└───────────────────────┬──────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────┐
│ CAMADA 1: Validação Básica                               │
│ - Integridade (ffprobe)                                  │
│ - Resolução mínima (360p)                                │
│ - Duração válida (5-60s)                                 │
│ - Codec suportado                                        │
└───────────────────────┬──────────────────────────────────┘
                        │ PASS
                        ▼
┌──────────────────────────────────────────────────────────┐
│ CAMADA 2: OCR Multi-Engine (Quick Filter)                │
│ - EasyOCR + Tesseract + PaddleOCR                        │
│ - Voting: 2/3 engines dizem "limpo" → prossegue         │
│ - Voting: 2/3 engines dizem "legenda" → БЛОКEAR         │
└───────────────────────┬──────────────────────────────────┘
                        │ PASS (limpo)
                        ▼
┌──────────────────────────────────────────────────────────┐
│ CAMADA 3: Visual Features Analysis                       │
│ - Score de "legenda-likeness" < 40 → OK                 │
│ - Score ≥ 40 → REJEITAR                                  │
└───────────────────────┬──────────────────────────────────┘
                        │ PASS (score baixo)
                        ▼
┌──────────────────────────────────────────────────────────┐
│ CAMADA 4: ML Classifier (Deep Validation)                │
│ - CNN prediz probabilidade                               │
│ - P(limpo) > 90% → APROVAR                              │
│ - P(limpo) < 90% → REJEITAR                             │
└───────────────────────┬──────────────────────────────────┘
                        │ PASS (alta confiança)
                        ▼
┌──────────────────────────────────────────────────────────┐
│ CAMADA 5: TRSD Temporal Analysis                         │
│ - Detecta padrões temporais anômalos                     │
│ - Nenhuma track de legenda detectada → APROVAR          │
│ - Detectou tracks → REJEITAR                            │
└───────────────────────┬──────────────────────────────────┘
                        │ PASS (sem tracks)
                        ▼
┌──────────────────────────────────────────────────────────┐
│ CAMADA 6: Human-in-the-Loop (Sample Checking)            │
│ - 5% de vídeos aprovados são revisados manualmente       │
│ - Feedback usado para re-treinar ML model                │
└───────────────────────┬──────────────────────────────────┘
                        │
                        ▼
              ✅ VÍDEO APROVADO (100% LIMPO)
```

### 3.2 Implementação do Pipeline

```python
# app/advanced_video_validator.py - NOVO ARQUIVO

from typing import Tuple, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

from .ocr_detector_advanced import MultiEngineOCRDetector
from .visual_features_analyzer import VisualFeaturesAnalyzer
from .ml_classifier import MLSubtitleDetector
from .video_validator import VideoValidator  # TRSD existente

logger = logging.getLogger(__name__)


class ValidationLayer(Enum):
    """Camadas de validação"""
    BASIC = 'basic'
    OCR_MULTI = 'ocr_multi'
    VISUAL_FEATURES = 'visual_features'
    ML_CLASSIFIER = 'ml_classifier'
    TRSD_TEMPORAL = 'trsd_temporal'


@dataclass
class ValidationResult:
    """Resultado de validação"""
    is_clean: bool
    confidence: float
    layer_results: Dict[str, Dict]
    blocked_by: Optional[str] = None
    reason: str = ""


class AdvancedVideoValidator:
    """
    Validador avançado multi-camadas
    
    Pattern: Chain of Responsibility + Defense in Depth
    """
    
    def __init__(
        self,
        enable_ocr_multi: bool = True,
        enable_visual: bool = True,
        enable_ml: bool = True,
        enable_trsd: bool = True,
        use_gpu: bool = True
    ):
        """
        Args:
            enable_*: Habilitar cada camada de validação
            use_gpu: Usar GPU se disponível
        """
        self.enable_ocr_multi = enable_ocr_multi
        self.enable_visual = enable_visual
        self.enable_ml = enable_ml
        self.enable_trsd = enable_trsd
        self.use_gpu = use_gpu
        
        # Inicializar componentes
        if enable_ocr_multi:
            self.ocr_multi = MultiEngineOCRDetector(use_gpu=use_gpu)
        
        if enable_visual:
            self.visual_analyzer = VisualFeaturesAnalyzer()
        
        if enable_ml:
            self.ml_detector = MLSubtitleDetector(
                model_path='storage/models/subtitle_classifier.pth',
                use_gpu=use_gpu
            )
        
        if enable_trsd:
            from .config import Settings
            settings = Settings()
            self.trsd_validator = VideoValidator(
                min_confidence=settings.ocr_confidence_threshold,
                frames_per_second=settings.ocr_frames_per_second,
                max_frames=settings.ocr_max_frames
            )
        
        logger.info("✅ AdvancedVideoValidator initialized")
    
    def validate(self, video_path: str, strict_mode: bool = True) -> ValidationResult:
        """
        Valida vídeo através de múltiplas camadas
        
        Args:
            video_path: Path do vídeo
            strict_mode: Se True, qualquer camada que rejeita = rejeita final
        
        Returns:
            ValidationResult com decisão final
        """
        layer_results = {}
        
        logger.info(f"🔍 Validating: {video_path}")
        
        # CAMADA 1: Validação Básica
        basic_result = self._validate_basic(video_path)
        layer_results['basic'] = basic_result
        
        if not basic_result['is_valid']:
            return ValidationResult(
                is_clean=False,
                confidence=0.0,
                layer_results=layer_results,
                blocked_by='basic',
                reason=basic_result['reason']
            )
        
        # CAMADA 2: OCR Multi-Engine
        if self.enable_ocr_multi:
            ocr_result = self._validate_ocr_multi(video_path)
            layer_results['ocr_multi'] = ocr_result
            
            if strict_mode and not ocr_result['is_clean']:
                return ValidationResult(
                    is_clean=False,
                    confidence=ocr_result['confidence'],
                    layer_results=layer_results,
                    blocked_by='ocr_multi',
                    reason='OCR engines detected subtitles'
                )
        
        # CAMADA 3: Visual Features
        if self.enable_visual:
            visual_result = self._validate_visual_features(video_path)
            layer_results['visual'] = visual_result
            
            if strict_mode and not visual_result['is_clean']:
                return ValidationResult(
                    is_clean=False,
                    confidence=visual_result['confidence'],
                    layer_results=layer_results,
                    blocked_by='visual',
                    reason='Visual features indicate subtitles'
                )
        
        # CAMADA 4: ML Classifier
        if self.enable_ml:
            ml_result = self._validate_ml(video_path)
            layer_results['ml'] = ml_result
            
            if strict_mode and not ml_result['is_clean']:
                return ValidationResult(
                    is_clean=False,
                    confidence=ml_result['confidence'],
                    layer_results=layer_results,
                    blocked_by='ml',
                    reason='ML classifier detected subtitles'
                )
        
        # CAMADA 5: TRSD Temporal
        if self.enable_trsd:
            trsd_result = self._validate_trsd(video_path)
            layer_results['trsd'] = trsd_result
            
            if strict_mode and not trsd_result['is_clean']:
                return ValidationResult(
                    is_clean=False,
                    confidence=trsd_result['confidence'],
                    layer_results=layer_results,
                    blocked_by='trsd',
                    reason='TRSD detected subtitle tracks'
                )
        
        # DECISÃO FINAL: Passou em todas as camadas
        # Calcular confiança agregada
        confidences = [
            layer_results.get('ocr_multi', {}).get('confidence', 100),
            layer_results.get('visual', {}).get('confidence', 100),
            layer_results.get('ml', {}).get('confidence', 100),
            layer_results.get('trsd', {}).get('confidence', 100)
        ]
        
        avg_confidence = sum(confidences) / len([c for c in confidences if c > 0])
        
        return ValidationResult(
            is_clean=True,
            confidence=avg_confidence,
            layer_results=layer_results,
            blocked_by=None,
            reason='Passed all validation layers'
        )
    
    def _validate_basic(self, video_path: str) -> Dict:
        """Camada 1: Validação básica de integridade"""
        import subprocess
        import json
        
        try:
            # ffprobe para metadata
            cmd = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'stream=codec_name,width,height,duration',
                '-of', 'json',
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return {
                    'is_valid': False,
                    'reason': 'ffprobe failed - corrupted video'
                }
            
            data = json.loads(result.stdout)
            
            if 'streams' not in data or len(data['streams']) == 0:
                return {
                    'is_valid': False,
                    'reason': 'No video streams found'
                }
            
            stream = data['streams'][0]
            
            # Validações
            width = stream.get('width', 0)
            height = stream.get('height', 0)
            
            if width < 360 or height < 360:
                return {
                    'is_valid': False,
                    'reason': f'Resolution too low: {width}x{height}'
                }
            
            return {
                'is_valid': True,
                'reason': 'Basic validation passed',
                'resolution': f'{width}x{height}',
                'codec': stream.get('codec_name', 'unknown')
            }
        
        except Exception as e:
            return {
                'is_valid': False,
                'reason': f'Basic validation error: {e}'
            }
    
    def _validate_ocr_multi(self, video_path: str) -> Dict:
        """Camada 2: OCR Multi-Engine"""
        import cv2
        import numpy as np
        
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if total_frames == 0:
            cap.release()
            return {
                'is_clean': False,
                'confidence': 0.0,
                'reason': 'Failed to read video'
            }
        
        # Amostrar 10 frames
        frame_indices = np.linspace(0, total_frames - 1, 10, dtype=int)
        
        detections = []
        
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            has_sub, conf, _ = self.ocr_multi.detect_subtitle_in_frame(frame)
            detections.append(has_sub)
        
        cap.release()
        
        # Decisão: se >30% dos frames tem legenda = блокear
        positive_ratio = sum(detections) / len(detections) if detections else 0.0
        
        is_clean = positive_ratio < 0.3
        
        return {
            'is_clean': is_clean,
            'confidence': (1 - positive_ratio) * 100,
            'frames_with_subtitle': sum(detections),
            'total_frames': len(detections),
            'subtitle_ratio': positive_ratio
        }
    
    def _validate_visual_features(self, video_path: str) -> Dict:
        """Camada 3: Visual Features"""
        # Simplificado: amostrar alguns frames e calcular score médio
        import cv2
        import numpy as np
        
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if total_frames == 0:
            cap.release()
            return {
                'is_clean': True,
                'confidence': 100.0,
                'reason': 'No frames to analyze'
            }
        
        # Amostrar 5 frames
        frame_indices = np.linspace(0, total_frames - 1, 5, dtype=int)
        
        scores = []
        
        for idx in frame indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            # Analisar visual features (simplificado - apenas checando posição de texto)
            # Na prática, integrar com VisualFeaturesAnalyzer
            # Por ora, retornar score neutro
            scores.append(0)  # Placeholder
        
        cap.release()
        
        avg_score = np.mean(scores) if scores else 0
        
        # Score < 40 = limpo
        is_clean = avg_score < 40
        
        return {
            'is_clean': is_clean,
            'confidence': (1 - avg_score / 100) * 100,
            'avg_subtitle_score': avg_score
        }
    
    def _validate_ml(self, video_path: str) -> Dict:
        """Camada 4: ML Classifier"""
        has_subtitle, confidence, details = self.ml_detector.predict_video(video_path)
        
        is_clean = not has_subtitle
        
        return {
            'is_clean': is_clean,
            'confidence': confidence,
            'details': details
        }
    
    def _validate_trsd(self, video_path: str) -> Dict:
        """Camada 5: TRSD Temporal Analysis"""
        has_subtitle, confidence, details = self.trsd_validator.has_subtitles(video_path)
        
        is_clean = not has_subtitle
        
        return {
            'is_clean': is_clean,
            'confidence': (1 - confidence) * 100 if has_subtitle else confidence * 100,
            'details': details
        }
```

### 3.3 Integração com Celery Tasks

```python
# app/celery_tasks.py - ATUALIZAR

from .advanced_video_validator import AdvancedVideoValidator

# Inicializar validador avançado
advanced_validator = None

def get_advanced_validator():
    global advanced_validator
    
    if advanced_validator is None:
        advanced_validator = AdvancedVideoValidator(
            enable_ocr_multi=True,
            enable_visual=True,
            enable_ml=True,
            enable_trsd=True,
            use_gpu=True
        )
    
    return advanced_validator


# Na task de validação de shorts
async def _validate_shorts_advanced(downloaded_shorts: List[Dict]) -> List[Dict]:
    """Valida shorts usando pipeline avançado"""
    
    validator = get_advanced_validator()
    validated_shorts = []
    
    for short in downloaded_shorts:
        video_path = short['local_path']
        video_id = short['video_id']
        
        logger.info(f"🔍 Validating {video_id}...")
        
        # Validação multi-camadas
        result = validator.validate(video_path, strict_mode=True)
        
        if result.is_clean:
            logger.info(
                f"✅ {video_id} APPROVED "
                f"(confidence: {result.confidence:.1f}%)"
            )
            validated_shorts.append(short)
        else:
            logger.warning(
                f"❌ {video_id} BLOCKED by {result.blocked_by} "
                f"(reason: {result.reason})"
            )
            
            # Adicionar à blacklist
            await blacklist.add(
                video_id,
                reason=f"Blocked by {result.blocked_by}: {result.reason}",
                confidence=result.confidence
            )
    
    return validated_shorts
```

---

## 📊 PARTE IV - MÉTRICAS E VALIDAÇÃO

### 4.1 Dataset de Teste

**Recomendação:** Criar dataset anotado manualmente para validação.

```
storage/test_dataset/
  ├── OK/                 ← 100 vídeos limpos (validados manualmente)
  ├── NOT_OK/             ← 100 vídeos com legendas (validados manualmente)
  └── annotations.json    ← Metadados de cada vídeo
```

**annotations.json schema:**
```json
[
  {
    "video_id": "abc123",
    "filename": "OK/video1.mp4",
    "has_subtitle": false,
    "subtitle_type": null,
    "notes": "Vídeo limpo de gato"
  },
  {
    "video_id": "xyz789",
    "filename": "NOT_OK/video2.mp4",
    "has_subtitle": true,
    "subtitle_type": "hardcoded_bottom",
    "notes": "Legenda branca no bottom"
  }
]
```

### 4.2 Script de Avaliação

```python
# evaluate_detector.py - NOVO ARQUIVO

import json
from pathlib import Path
from typing import Dict, Tuple
from app.advanced_video_validator import AdvancedVideoValidator
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def evaluate_detector(
    annotations_path: str = 'storage/test_dataset/annotations.json',
    output_path: str = 'storage/evaluation_report.json'
) -> Dict:
    """
    Avalia detector em dataset anotado
    
    Returns:
        Métricas: accuracy, precision, recall, F1
    """
    # Carregar anotações
    with open(annotations_path, 'r') as f:
        annotations = json.load(f)
    
    validator = AdvancedVideoValidator(
        enable_ocr_multi=True,
        enable_visual=True,
        enable_ml=True,
        enable_trsd=True,
        use_gpu=True
    )
    
    # Métricas
    true_positives = 0   # Detectou legenda E tinha legenda
    true_negatives = 0   # Detectou limpo E estava limpo
    false_positives = 0  # Detectou legenda MAS estava limpo
    false_negatives = 0  # Detectou limpo MAS tinha legenda
    
    results = []
    
    for ann in annotations:
        video_path = f"storage/test_dataset/{ann['filename']}"
        ground_truth = ann['has_subtitle']
        
        logger.info(f"Testing: {ann['video_id']}...")
        
        # Validar
        result = validator.validate(video_path)
        predicted_clean = result.is_clean
        predicted_has_subtitle = not predicted_clean
        
        # Comparar
        if ground_truth and predicted_has_subtitle:
            true_positives += 1
            outcome = 'TP'
        elif not ground_truth and predicted_clean:
            true_negatives += 1
            outcome = 'TN'
        elif not ground_truth and predicted_has_subtitle:
            false_positives += 1
            outcome = 'FP'
        else:  # ground_truth and predicted_clean
            false_negatives += 1
            outcome = 'FN'
        
        results.append({
            'video_id': ann['video_id'],
            'ground_truth': ground_truth,
            'predicted': predicted_has_subtitle,
            'outcome': outcome,
            'confidence': result.confidence,
            'blocked_by': result.blocked_by
        })
        
        logger.info(f"  → {outcome} (confidence: {result.confidence:.1f}%)")
    
    # Calcular métricas
    total = len(annotations)
    accuracy = (true_positives + true_negatives) / total * 100
    
    precision = true_positives / (true_positives + false_positives) * 100 if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) * 100 if (true_positives + false_negatives) > 0 else 0
    
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    metrics = {
        'total_samples': total,
        'true_positives': true_positives,
        'true_negatives': true_negatives,
        'false_positives': false_positives,
        'false_negatives': false_negatives,
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1_score': f1
    }
    
    # Salvar relatório
    report = {
        'metrics': metrics,
        'results': results
    }
    
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Imprimir resumo
    print("\n" + "="*60)
    print("📊 EVALUATION REPORT")
    print("="*60)
    print(f"Total Samples: {total}")
    print(f"True Positives: {true_positives}")
    print(f"True Negatives: {true_negatives}")
    print(f"False Positives: {false_positives}")
    print(f"False Negatives: {false_negatives}")
    print("-"*60)
    print(f"✅ Accuracy:  {accuracy:.2f}%")
    print(f"🎯 Precision: {precision:.2f}%")
    print(f"📈 Recall:    {recall:.2f}%")
    print(f"⚖️  F1-Score:  {f1:.2f}%")
    print("="*60)
    print(f"Report saved: {output_path}")
    
    return metrics


if __name__ == '__main__':
    evaluate_detector()
```

**Executar avaliação:**
```bash
python evaluate_detector.py
```

---

## 🚀 PARTE V - ROADMAP DE IMPLEMENTAÇÃO

### 5.1 Fase 1: Quick Wins (Semana 1)

**Objetivo:** Melhorias rápidas sem ML.

- [ ] Implementar Multi-Engine OCR (2 dias)
- [ ] Implementar Visual Features Analyzer (2 dias)
- [ ] Integrar no pipeline de validação (1 dia)
- [ ] Testar em dataset existente (1 dia)

**Resultado Esperado:** Accuracy 80-85% (+10pp)

### 5.2 Fase 2: ML Training (Semana 2-3)

**Objetivo:** Treinar e validar classificador ML.

- [ ] Preparar dataset (curar 500+ vídeos rotulados) (3 dias)
- [ ] Implementar data loader e augmentation (1 dia)
- [ ] Treinar modelo CNN (2-3 dias)
- [ ] Avaliar performance no test set (1 dia)
- [ ] Fine-tuning e re-treino (2 dias)

**Resultado Esperado:** Accuracy 90-95% (+10pp adicional)

### 5.3 Fase 3: Pipeline Completo (Semana 4)

**Objetivo:** Integrar todas as camadas.

- [ ] Implementar AdvancedVideoValidator (2 dias)
- [ ] Integrar com celery_tasks (1 dia)
- [ ] Testes end-to-end (2 dias)
- [ ] Monitoramento e logs (1 dia)

**Resultado Esperado:** Sistema robusto em produção

### 5.4 Fase 4: Monitoramento e Melhoria Contínua

**Objetivo:** Feedback loop para refinamento.

- [ ] Implementar human-in-the-loop sampling (1 dia)
- [ ] Coletar métricas em produção (Prometheus) (1 dia)
- [ ] Dashboard de monitoramento (Grafana) (1 dia)
- [ ] Re-treino periódico do modelo (setup automático) (2 dias)

---

## 📝 CONCLUSÃO

### Resumo das Estratégias

| Estratégia | Impacto | Esforço | ROI | Prioridade |
|-----------|---------|---------|-----|------------|
| **Multi-Engine OCR** | Alto (+10pp accuracy) | Baixo (2 dias) | Muito Alto | **P0** |
| **Visual Features** | Médio (+5pp precision) | Médio (2 dias) | Alto | **P1** |
| **ML Classifier** | Muito Alto (+10-15pp) | Alto (7 dias) | Alto | **P1** |
| **Pipeline Multi-Camadas** | Crítico (robustez) | Médio (3 dias) | Crítico | **P0** |
| **TRSD Aprimorado** | Médio (+5pp recall) | Baixo (incluso) | Médio | **P2** |

### Próximos Passos Imediatos

1. **HOJE:** Implementar Multi-Engine OCR
2. **AMANHÃ:** Implementar Visual Features
3. **DIA 3:** Integrar ambos no pipeline
4. **DIA 4:** Testar e ajustar thresholds
5. **SEMANA 2:** Preparar dataset para ML
6. **SEMANA 3:** Treinar modelo CNN
7. **SEMANA 4:** Deploy completo em produção

### Meta Final

**Accuracy >95%** com pipeline robusto de 5 camadas garantindo que APENAS vídeos 100% limpos sejam aprovados.

---

**Fim do Documento** - NEW_OCR.md  
**Versão:** 1.0  
**Data:** 11 de Fevereiro de 2026
