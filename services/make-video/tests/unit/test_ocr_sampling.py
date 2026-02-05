"""
Testes para nova lógica de amostragem OCR por segundo
"""

import pytest
import sys
from unittest.mock import Mock, patch, MagicMock

# Mock cv2 and pytesseract before importing VideoValidator
sys.modules['cv2'] = MagicMock()
sys.modules['pytesseract'] = MagicMock()

from app.video_validator import VideoValidator


class TestOCRSamplingStrategy:
    """Testes para amostragem frames-per-second"""
    
    def test_sampling_basic_6fps(self):
        """Testa amostragem básica: 6 frames/s em vídeo de 10s"""
        validator = VideoValidator(frames_per_second=6, max_frames=1000)
        timestamps = validator._get_sample_timestamps(duration=10.0)
        
        # 10s × 6fps = 60 frames
        assert len(timestamps) == 60
        
        # Primeiro frame deve estar próximo de 0
        assert timestamps[0] < 0.2
        
        # Último frame deve estar próximo de 10s
        assert timestamps[-1] < 10.0
        assert timestamps[-1] > 9.8
    
    def test_sampling_with_max_frames_limit(self):
        """Testa limite máximo de frames"""
        validator = VideoValidator(frames_per_second=6, max_frames=240)
        
        # Vídeo de 60s × 6fps = 360 frames, mas limite é 240
        timestamps = validator._get_sample_timestamps(duration=60.0)
        
        assert len(timestamps) == 240  # Deve respeitar o limite
        assert timestamps[-1] < 60.0  # Dentro da duração
    
    def test_sampling_short_video(self):
        """Testa vídeo curto (5s)"""
        validator = VideoValidator(frames_per_second=6, max_frames=240)
        timestamps = validator._get_sample_timestamps(duration=5.0)
        
        # 5s × 6fps = 30 frames
        assert len(timestamps) == 30
        assert all(0 <= ts < 5.0 for ts in timestamps)
    
    def test_sampling_long_video_adaptive_fps(self):
        """Testa vídeo longo com FPS adaptativo"""
        validator = VideoValidator(frames_per_second=10, max_frames=300)
        
        # Vídeo de 60s × 10fps = 600 frames, mas limite é 300
        timestamps = validator._get_sample_timestamps(duration=60.0)
        
        assert len(timestamps) == 300
        # FPS efetivo deve ser 300/60 = 5fps
        # Espaçamento entre frames: ~0.2s
        if len(timestamps) > 1:
            avg_spacing = (timestamps[-1] - timestamps[0]) / (len(timestamps) - 1)
            assert 0.18 < avg_spacing < 0.22  # ~0.2s ± 10%
    
    def test_sampling_very_short_video(self):
        """Testa vídeo muito curto (1s)"""
        validator = VideoValidator(frames_per_second=6, max_frames=240)
        timestamps = validator._get_sample_timestamps(duration=1.0)
        
        # 1s × 6fps = 6 frames
        assert len(timestamps) == 6
        assert all(0 <= ts < 1.0 for ts in timestamps)
    
    def test_sampling_timestamps_ascending(self):
        """Testa que timestamps estão em ordem crescente"""
        validator = VideoValidator(frames_per_second=4, max_frames=240)
        timestamps = validator._get_sample_timestamps(duration=30.0)
        
        # Verificar ordem
        for i in range(len(timestamps) - 1):
            assert timestamps[i] < timestamps[i + 1]
    
    def test_custom_fps_values(self):
        """Testa diferentes valores de FPS"""
        test_cases = [
            (2, 10, 20),   # 2fps × 10s = 20 frames
            (4, 15, 60),   # 4fps × 15s = 60 frames
            (12, 5, 60),   # 12fps × 5s = 60 frames
        ]
        
        for fps, duration, expected_frames in test_cases:
            validator = VideoValidator(frames_per_second=fps, max_frames=1000)
            timestamps = validator._get_sample_timestamps(duration=duration)
            
            assert len(timestamps) == expected_frames, \
                f"Failed for {fps}fps × {duration}s (expected {expected_frames}, got {len(timestamps)})"
    
    def test_zero_duration_edge_case(self):
        """Testa caso extremo: duração zero"""
        validator = VideoValidator(frames_per_second=6, max_frames=240)
        timestamps = validator._get_sample_timestamps(duration=0.0)
        
        # Deve retornar lista vazia
        assert len(timestamps) == 0
    
    def test_max_frames_prevents_oom(self):
        """Testa que max_frames previne OOM em vídeos longos"""
        validator = VideoValidator(frames_per_second=30, max_frames=100)
        
        # Vídeo de 1 hora × 30fps = 108.000 frames!
        timestamps = validator._get_sample_timestamps(duration=3600.0)
        
        # Deve ser limitado a 100 frames
        assert len(timestamps) == 100
        assert timestamps[-1] < 3600.0


class TestConstructorParameters:
    """Testes para parâmetros do construtor"""
    
    def test_default_parameters(self):
        """Testa valores padrão"""
        validator = VideoValidator()
        
        assert validator.frames_per_second == 6
        assert validator.max_frames == 240
        assert validator.min_confidence == 0.40
    
    def test_custom_parameters(self):
        """Testa parâmetros customizados"""
        validator = VideoValidator(
            frames_per_second=4,
            max_frames=180,
            min_confidence=0.50
        )
        
        assert validator.frames_per_second == 4
        assert validator.max_frames == 180
        assert validator.min_confidence == 0.50
    
    def test_backward_compatibility_warning(self):
        """Testa que parâmetro antigo (num_sample_frames) não existe mais"""
        # Deve usar novos parâmetros
        validator = VideoValidator(frames_per_second=6)
        
        # Não deve ter atributo antigo
        assert not hasattr(validator, 'num_sample_frames')
