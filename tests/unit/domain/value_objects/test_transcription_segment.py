"""
Testes unitários para o value object TranscriptionSegment.
"""
import pytest
from src.domain.value_objects.transcription_segment import TranscriptionSegment


class TestTranscriptionSegment:
    """Testes para o value object TranscriptionSegment."""
    
    def test_create_valid_segment(self):
        """Deve criar segmento válido."""
        segment = TranscriptionSegment(
            text="Hello world",
            start=0.0,
            end=3.5
        )
        
        assert segment.text == "Hello world"
        assert segment.start == 0.0
        assert segment.end == 3.5
    
    def test_segment_duration_property(self):
        """Deve calcular duração do segmento."""
        segment = TranscriptionSegment(
            text="Test",
            start=1.5,
            end=5.7
        )
        
        assert segment.duration == pytest.approx(4.2)
    
    def test_segment_is_immutable(self):
        """Segmento deve ser imutável (frozen dataclass)."""
        segment = TranscriptionSegment(
            text="Immutable",
            start=0.0,
            end=1.0
        )
        
        with pytest.raises(Exception):  # FrozenInstanceError
            segment.text = "Changed"
    
    def test_invalid_start_time(self):
        """Deve rejeitar start time negativo."""
        with pytest.raises(ValueError, match="Start time must be non-negative"):
            TranscriptionSegment(
                text="Invalid",
                start=-1.0,
                end=5.0
            )
    
    def test_invalid_end_before_start(self):
        """Deve rejeitar end time antes de start time."""
        with pytest.raises(ValueError, match="End time must be greater than or equal to start time"):
            TranscriptionSegment(
                text="Invalid",
                start=5.0,
                end=3.0
            )
    
    def test_empty_text(self):
        """Deve rejeitar texto vazio."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            TranscriptionSegment(
                text="   ",
                start=0.0,
                end=1.0
            )
    
    def test_segment_equality(self):
        """Segmentos com mesmos valores devem ser iguais."""
        segment1 = TranscriptionSegment(
            text="Same",
            start=1.0,
            end=2.0
        )
        segment2 = TranscriptionSegment(
            text="Same",
            start=1.0,
            end=2.0
        )
        
        assert segment1 == segment2
    
    def test_to_srt_format(self):
        """Deve converter para formato SRT."""
        segment = TranscriptionSegment(
            text="Hello world",
            start=1.5,
            end=4.8
        )
        
        srt = segment.to_srt_format(index=1)
        
        assert "1\n" in srt
        assert "00:00:01,500" in srt  # Start time
        assert "00:00:04,8" in srt  # End time (pode ser 799 ou 800 ms)
        assert "Hello world" in srt
    
    def test_to_vtt_format(self):
        """Deve converter para formato WebVTT."""
        segment = TranscriptionSegment(
            text="Test subtitle",
            start=2.0,
            end=5.5
        )
        
        vtt = segment.to_vtt_format()
        
        assert "00:00:02.000 --> 00:00:05.500" in vtt
        assert "Test subtitle" in vtt
    
    def test_timestamp_formatting(self):
        """Deve formatar timestamp corretamente."""
        # Teste com timestamp complexo (horas, minutos, segundos, milissegundos)
        segment = TranscriptionSegment(
            text="Long video segment",
            start=3661.123,  # 1h 1min 1.123s
            end=7322.456     # 2h 2min 2.456s
        )
        
        srt = segment.to_srt_format(index=1)
        
        assert "01:01:01,123" in srt
        assert "02:02:02,456" in srt
