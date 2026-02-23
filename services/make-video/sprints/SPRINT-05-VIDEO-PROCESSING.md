# 🎬 SPRINT 5 - VIDEO PROCESSING

**Status**: ⏳ Pendente  
**Prioridade**: 🔴 CRÍTICA  
**Duração Estimada**: 6-8 horas  
**Pré-requisitos**: Sprint 0, 1, 3

---

## 🎯 OBJETIVOS

1. ✅ Testar detector de legendas com vídeos REAIS
2. ✅ Validar OCR com frames reais
3. ✅ Testar Frame Extractor com FFmpeg real
4. ✅ Validar ensemble detector
5. ✅ Testar feature extractor
6. ✅ Garantir acurácia > 95%

---

## 📁 ARQUIVOS (~40 arquivos)

```
app/video_processing/
├── subtitle_detector_v2.py      # Detector principal
├── frame_extractor.py           # Extração de frames
├── ocr_detector.py              # OCR básico
├── ocr_detector_advanced.py    # OCR avançado
├── ensemble_detector.py         # Ensemble de detectores
├── feature_extractor.py         # Extração de features
├── visual_features.py           # Features visuais
├── video_validator.py           # Validação de vídeo
├── detectors/                   # Detectores específicos
└── voting/                      # Sistema de votação
```

---

## 🧪 TESTES PRINCIPAIS

```python
# tests/integration/video_processing/test_subtitle_detector_v2.py
import pytest
from app.video_processing.subtitle_detector_v2 import SubtitleDetectorV2


@pytest.mark.requires_video
@pytest.mark.slow
class TestSubtitleDetectorV2:
    """Testes com vídeos REAIS"""
    
    @pytest.fixture
    def detector(self):
        return SubtitleDetectorV2(show_log=True)
    
    def test_detect_clean_video(self, detector, real_test_video):
        """Detecta em vídeo SEM legendas"""
        result = detector.detect(str(real_test_video))
        
        assert 'has_subtitles' in result
        assert isinstance(result['has_subtitles'], bool)
        assert 'confidence' in result
        assert 0 <= result['confidence'] <= 1
    
    def test_detect_video_with_subtitles(self, detector, video_with_subtitles):
        """Detecta em vídeo COM legendas"""
        result = detector.detect(str(video_with_subtitles))
        
        # Deve detectar legendas
        assert result['has_subtitles'] is True
        assert result['confidence'] > 0.5
    
    def test_detector_accuracy(self, detector):
        """Valida acurácia do detector"""
        # Testes com múltiplos vídeos
        # Acurácia deve ser > 95%
        pass


# tests/unit/video_processing/test_frame_extractor.py
@pytest.mark.requires_video
@pytest.mark.requires_ffmpeg
class TestFrameExtractor:
    """Testes de extração de frames"""
    
    def test_extract_frames(self, real_test_video):
        """Extrai frames de vídeo real"""
        import cv2
        import subprocess
        import numpy as np
        
        # Extrair frame com FFmpeg
        output = subprocess.run([
            "ffmpeg", "-i", str(real_test_video),
            "-vf", "select='eq(n,0)'",
            "-vframes", "1",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-"
        ], capture_output=True, check=True)
        
        # Converter para numpy array
        nparr = np.frombuffer(output.stdout, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        assert frame is not None
        assert frame.shape[2] == 3  # RGB
    
    def test_extract_multiple_frames(self, real_test_video):
        """Extrai múltiplos frames"""
        import subprocess
        
        # Extrair 5 frames
        result = subprocess.run([
            "ffmpeg", "-i", str(real_test_video),
            "-vf", "fps=1",  # 1 frame por segundo
            "-vframes", "5",
            "-f", "null", "-"
        ], capture_output=True)
        
        assert result.returncode == 0


# tests/unit/video_processing/test_ocr_detector.py
@pytest.mark.requires_video
class TestOCRDetector:
    """Testes de OCR"""
    
    def test_ocr_on_frame_with_text(self, tmp_path):
        """OCR em frame com texto"""
        import subprocess
        
        # Criar imagem com texto
        text_image = tmp_path / "text.png"
        subprocess.run([
            "ffmpeg", "-f", "lavfi",
            "-i", "color=c=white:s=640x480",
            "-vf", "drawtext=text='SUBTITLE':fontsize=48:fontcolor=black:x=100:y=200",
            "-frames:v", "1",
            str(text_image)
        ], check=True, capture_output=True)
        
        assert text_image.exists()
        
        # Tentar OCR (se disponível)
        try:
            import easyocr
            reader = easyocr.Reader(['en'])
            result = reader.readtext(str(text_image))
            
            # Deve detectar algo
            assert len(result) > 0
        except ImportError:
            pytest.skip("EasyOCR not installed")
```

---

## 📋 IMPLEMENTAÇÃO

```bash
mkdir -p tests/integration/video_processing
mkdir -p tests/unit/video_processing

# Criar arquivos
touch tests/integration/video_processing/__init__.py
touch tests/integration/video_processing/test_subtitle_detector_v2.py
touch tests/unit/video_processing/test_frame_extractor.py
touch tests/unit/video_processing/test_ocr_detector.py

# Executar
pytest tests/integration/video_processing/ -v -m requires_video
pytest tests/unit/video_processing/ -v
```

---

## ✅ CRITÉRIOS

- [ ] Detector funciona com vídeos reais
- [ ] OCR processa frames reais
- [ ] Frames extraídos corretamente
- [ ] Acurácia > 95%
- [ ] Cobertura > 75%

---

**Status**: ⏳ Pendente
