"""
OCR Detection Module

Detecta presença de legendas em frames usando EasyOCR com otimizações avançadas
"""

import os
import cv2
import numpy as np
import easyocr
import re
from typing import Tuple, Optional, List, Set
from dataclasses import dataclass
from app.infrastructure.metrics import ocr_confidence_distribution
from common.log_utils import get_logger

logger = get_logger(__name__)

def _get_ocr_gpu_setting() -> bool:
    """
    Retorna configuração de GPU para EasyOCR a partir do ambiente.
    
    Returns:
        True se OCR_USE_GPU=true (case-insensitive), False caso contrário
    """
    gpu_env = os.getenv('OCR_USE_GPU', 'false').lower().strip()
    use_gpu = gpu_env in ('true', '1', 'yes', 'on')
    
    if use_gpu:
        # Verificar se CUDA está disponível
        try:
            import torch
            cuda_available = torch.cuda.is_available()
            if not cuda_available:
                logger.warning("⚠️ OCR_USE_GPU=true mas CUDA não disponível. Usando CPU.")
                return False
            logger.info(f"🎮 GPU detectada: {torch.cuda.get_device_name(0)}")
            return True
        except ImportError:
            logger.warning("⚠️ OCR_USE_GPU=true mas PyTorch não instalado. Usando CPU.")
            return False
    
    return False

@dataclass
class OCRResult:
    """Resultado de OCR em um frame"""
    text: str
    confidence: float
    word_count: int
    has_subtitle: bool
    readable_words: List[str]  # Palavras legíveis detectadas

class OCRDetector:
    """
    Detector de legendas usando EasyOCR com validação de palavras legíveis
    
    Pipeline de processamento:
    1. EasyOCR extrai texto
    2. Regex limpa texto (apenas letras e números)
    3. Remove letras/números isolados
    4. Filtra palavras com >2 caracteres
    5. Valida se há palavras legíveis em PT/EN
    """
    
    # Palavras comuns em português e inglês para validação
    COMMON_WORDS_PT = {
        'que', 'não', 'uma', 'para', 'com', 'por', 'isso', 'mais', 'este', 'esta',
        'seu', 'sua', 'foi', 'ser', 'tem', 'pode', 'mas', 'como', 'muito', 'quando',
        'sem', 'sim', 'bem', 'também', 'só', 'até', 'depois', 'antes', 'entre', 'sobre',
        'então', 'agora', 'sempre', 'nunca', 'outro', 'nova', 'novo', 'grande', 'mesmo',
        'ainda', 'onde', 'ano', 'dia', 'vez', 'porque', 'aqui', 'lá', 'ali', 'hoje',
        'ontem', 'amanhã', 'noite', 'manhã', 'tarde', 'hora', 'minuto', 'segundo',
        'casa', 'pai', 'mãe', 'filho', 'filha', 'irmão', 'irmã', 'homem', 'mulher',
        'vida', 'morte', 'amor', 'olhar', 'ver', 'fazer', 'dar', 'ter', 'vir', 'ir',
        'dizer', 'falar', 'pensar', 'querer', 'saber', 'poder', 'dever', 'achar'
    }
    
    COMMON_WORDS_EN = {
        'the', 'and', 'for', 'you', 'are', 'not', 'this', 'that', 'with', 'from',
        'have', 'was', 'were', 'been', 'will', 'can', 'but', 'what', 'all', 'when',
        'time', 'year', 'day', 'way', 'its', 'may', 'any', 'only', 'now', 'new',
        'make', 'work', 'know', 'take', 'see', 'come', 'get', 'use', 'find', 'give',
        'tell', 'ask', 'try', 'call', 'hand', 'part', 'about', 'after', 'back',
        'just', 'good', 'another', 'where', 'every', 'much', 'before', 'right',
        'mean', 'old', 'great', 'same', 'because', 'turn', 'here', 'show', 'why',
        'help', 'put', 'different', 'away', 'again', 'off', 'went', 'number'
    }

# ===== SINGLETON PATTERN (P1 Optimization) =====
_global_ocr_detector = None
_detector_lock = None

def get_ocr_detector() -> 'OCRDetector':
    """
    Retorna instância singleton de OCRDetector (P1 Optimization)
    
    Thread-safe para uso em Celery workers.
    Reduz uso de memória de ~500MB por worker para ~50MB overhead.
    
    Returns:
        Instância singleton de OCRDetector
    """
    global _global_ocr_detector, _detector_lock
    
    # Inicializar lock na primeira chamada
    if _detector_lock is None:
        import threading
        _detector_lock = threading.Lock()
    
    if _global_ocr_detector is None:
        with _detector_lock:
            # Double-check locking
            if _global_ocr_detector is None:
                logger.info("🔧 Creating OCRDetector singleton instance...")
                _global_ocr_detector = OCRDetector()
                logger.info("✅ OCRDetector singleton created")
    
    return _global_ocr_detector

class OCRDetector:
    """
    Detector de legendas em frames usando EasyOCR
    
    IMPORTANTE: Use get_ocr_detector() ao invés de instanciar diretamente
    para aproveitar otimização singleton (P1).
    """
    
    def __init__(self):
        """
        Inicializa detector com EasyOCR configurado para PT e EN
        
        Configuração GPU/CPU via variável de ambiente OCR_USE_GPU:
        - OCR_USE_GPU=true: Usa GPU (requer CUDA)
        - OCR_USE_GPU=false: Usa CPU (padrão)
        """
        use_gpu = _get_ocr_gpu_setting()
        mode = "GPU" if use_gpu else "CPU"
        
        logger.info(f"🚀 Initializing EasyOCR detector (pt+en, {mode})...")
        try:
            # Inicializar EasyOCR com português e inglês
            self.reader = easyocr.Reader(['pt', 'en'], gpu=use_gpu, verbose=False)
            self.use_gpu = use_gpu
            logger.info(f"✅ EasyOCR detector initialized successfully ({mode})")
        except Exception as e:
            logger.error(f"❌ Failed to initialize EasyOCR: {e}")
            raise
    
    def detect_subtitle_in_frame(
        self,
        frame: np.ndarray,
        min_confidence: float = 60.0
    ) -> OCRResult:
        """
        Detecta legenda em um frame usando EasyOCR com validação de palavras legíveis
        
        Pipeline:
        1. Pré-processamento da imagem
        2. EasyOCR extrai texto
        3. Limpeza com regex (apenas letras/números)
        4. Remoção de caracteres isolados
        5. Filtragem de palavras >2 caracteres
        6. Validação de palavras legíveis (PT/EN)
        
        Args:
            frame: Frame BGR do cv2
            min_confidence: Confiança mínima (0-100) para aceitar detecção
        
        Returns:
            OCRResult com texto processado e lista de palavras legíveis
        """
        # Pré-processar para melhorar OCR
        processed = self._preprocess_for_ocr(frame)
        
        # Executar EasyOCR
        try:
            ocr_results = self.reader.readtext(processed, detail=1)
        except Exception as e:
            logger.warning(f"EasyOCR failed: {e}")
            return OCRResult(
                text="",
                confidence=0.0,
                word_count=0,
                has_subtitle=False,
                readable_words=[]
            )
        
        # Processar resultados do EasyOCR aplicando threshold
        raw_text, confidence, readable_words = self._process_easyocr_results(ocr_results, min_confidence)
        
        # Critério de validação: presença de palavras legíveis
        has_subtitle = len(readable_words) > 0
        word_count = len(readable_words)
        
        # Registrar métrica
        ocr_confidence_distribution.observe(confidence)
        
        logger.debug(
            f"📝 OCR: conf={confidence:.1f}%, words={word_count}, "
            f"readable={readable_words}, has_subtitle={has_subtitle}"
        )
        
        return OCRResult(
            text=raw_text,
            confidence=confidence,
            word_count=word_count,
            has_subtitle=has_subtitle,
            readable_words=readable_words
        )
    
    def _preprocess_for_ocr(self, frame: np.ndarray) -> np.ndarray:
        """
        Pré-processa frame para melhorar OCR
        
        - Converte para grayscale
        - Aplica threshold adaptativo
        - Inverte cores (texto branco → preto)
        
        Args:
            frame: Frame completo em BGR
        
        Returns:
            Imagem processada para OCR
        """
        # Converter para grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Threshold adaptativo (binarização)
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2
        )
        
        # Inverter cores se necessário (texto branco em fundo preto → preto em branco)
        # Tesseract funciona melhor com texto escuro em fundo claro
        mean_val = np.mean(binary)
        if mean_val < 127:  # Imagem predominantemente escura
            binary = cv2.bitwise_not(binary)
        
        return binary
    
    def _process_easyocr_results(self, ocr_results: List, min_confidence: float = 60.0) -> Tuple[str, float, List[str]]:
        """
        Processa resultados do EasyOCR aplicando pipeline de limpeza
        
        Pipeline:
        1. Extrai texto bruto e confiança (filtrando por threshold)
        2. Aplica regex: mantém apenas letras e números
        3. Remove caracteres isolados (letras/números sozinhos)
        4. Filtra palavras >2 caracteres
        5. Valida palavras legíveis em PT/EN
        
        Args:
            ocr_results: Lista de tuplas (bbox, text, confidence) do EasyOCR
            min_confidence: Confiança mínima (0-100) para aceitar detecção
        
        Returns:
            (texto_bruto, confiança_média, lista_palavras_legíveis)
        """
        if not ocr_results:
            return "", 0.0, []
        
        # Extrair textos e confianças (filtrar por threshold)
        all_texts = []
        confidences = []
        
        for bbox, text, conf in ocr_results:
            conf_percent = conf * 100  # Converter para percentual
            # Aplicar threshold de confiança
            if text.strip() and conf_percent >= min_confidence:
                all_texts.append(text)
                confidences.append(conf_percent)
        
        if not all_texts:
            return "", 0.0, []
        
        # Texto bruto concatenado
        raw_text = " ".join(all_texts)
        
        # Confiança média
        avg_confidence = sum(confidences) / len(confidences)
        
        # STEP 1: Regex - manter apenas letras e números
        cleaned_text = re.sub(r'[^a-zA-Z0-9\s]', '', raw_text)
        
        # STEP 2: Dividir em palavras
        words = cleaned_text.split()
        
        # STEP 3: Remover caracteres isolados (letras/números sozinhos)
        # STEP 4: Filtrar palavras com >2 caracteres
        filtered_words = [w.lower() for w in words if len(w) > 2]
        
        # STEP 5: Validar palavras legíveis (presentes em dicionários PT/EN)
        readable_words = [
            w for w in filtered_words
            if w in self.COMMON_WORDS_PT or w in self.COMMON_WORDS_EN
        ]
        
        logger.debug(
            f"📊 Pipeline: raw='{raw_text}' → cleaned='{cleaned_text}' → "
            f"filtered={filtered_words} → readable={readable_words}"
        )
        
        return raw_text, avg_confidence, readable_words
    
    def extract_frame_at_timestamp(
        self,
        video_path: str,
        timestamp: float
    ) -> Optional[np.ndarray]:
        """
        Extrai frame em um timestamp específico
        
        Args:
            video_path: Path do vídeo
            timestamp: Timestamp em segundos
        
        Returns:
            Frame BGR ou None se falhar
        """
        cap = cv2.VideoCapture(video_path)
        
        try:
            # Setar posição do vídeo
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            
            # Ler frame
            ret, frame = cap.read()
            
            if not ret:
                logger.warning(f"Failed to extract frame at {timestamp}s")
                return None
            
            return frame
        
        finally:
            cap.release()
