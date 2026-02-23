"""
Teste de Integração: Pipeline Completo com Melhorias de Sincronização

Testa o pipeline end-to-end:
1. Transcrição → Timestamps ponderados
2. VAD gating com bypass inteligente
3. Escrita SRT direta
4. Validação do resultado
"""

import pytest
import asyncio
from pathlib import Path

from app.services.subtitle_generator import (
    segments_to_weighted_word_cues,
    write_srt_from_word_cues
)
from app.services.subtitle_postprocessor import process_subtitles_with_vad


@pytest.mark.integration
@pytest.mark.asyncio
class TestSyncImprovementsPipeline:
    """Testa pipeline completo com melhorias de sincronização"""
    
    def test_weighted_to_srt_pipeline(self, tmp_path):
        """Pipeline: segments → weighted cues → SRT"""
        # 1. Segments de entrada (simulando Whisper)
        segments = [
            {"start": 0.0, "end": 2.5, "text": "Olá, como vai?"},
            {"start": 2.5, "end": 5.0, "text": "Tudo bem com você?"}
        ]
        
        # 2. Converter para weighted word cues
        word_cues = segments_to_weighted_word_cues(segments)
        
        # Verificar que temos palavras
        assert len(word_cues) > 0
        
        # Verificar que timestamps são contínuos
        for i in range(len(word_cues) - 1):
            # Próxima palavra começa onde anterior termina (com tolerância)
            gap = word_cues[i+1]['start'] - word_cues[i]['end']
            assert abs(gap) < 0.01  # <10ms de gap
        
        # 3. Gerar SRT
        srt_path = tmp_path / "test.srt"
        write_srt_from_word_cues(word_cues, str(srt_path), words_per_caption=2)
        
        # 4. Validar SRT gerado
        assert srt_path.exists()
        
        content = srt_path.read_text(encoding='utf-8')
        
        # Deve ter múltiplas legendas
        assert content.count("\n\n") >= 2
        
        # Deve ter timestamps válidos
        assert "00:00:00," in content
        assert "-->" in content
        
        # Texto deve estar presente
        assert any(word in content for word in ["Olá", "como", "vai", "bem"])
    
    def test_vad_bypass_when_no_speech_detected(self, tmp_path):
        """VAD bypass deve prevenir filtrar todas as legendas"""
        # Simular raw_cues
        raw_cues = [
            {'start': 0.5, 'end': 1.0, 'text': 'teste'},
            {'start': 1.0, 'end': 1.5, 'text': 'palavra'}
        ]
        
        # Criar áudio dummy (vazio - VAD não detectará fala)
        audio_path = tmp_path / "silent.wav"
        
        # Criar arquivo de áudio silencioso simples (header WAV + zeros)
        import struct
        sample_rate = 16000
        duration = 2  # 2 segundos
        num_samples = sample_rate * duration
        
        # Header WAV
        with open(audio_path, 'wb') as f:
            # RIFF header
            f.write(b'RIFF')
            f.write(struct.pack('<I', 36 + num_samples * 2))
            f.write(b'WAVE')
            
            # fmt chunk
            f.write(b'fmt ')
            f.write(struct.pack('<I', 16))  # chunk size
            f.write(struct.pack('<H', 1))   # PCM
            f.write(struct.pack('<H', 1))   # mono
            f.write(struct.pack('<I', sample_rate))
            f.write(struct.pack('<I', sample_rate * 2))
            f.write(struct.pack('<H', 2))   # block align
            f.write(struct.pack('<H', 16))  # bits per sample
            
            # data chunk
            f.write(b'data')
            f.write(struct.pack('<I', num_samples * 2))
            
            # Silence (zeros)
            f.write(b'\x00' * (num_samples * 2))
        
        # Processar com VAD
        gated_cues, vad_ok = process_subtitles_with_vad(str(audio_path), raw_cues)
        
        # VAD fallback não deve filtrar TUDO
        # Com bypass, devemos ter pelo menos algumas legendas
        assert len(gated_cues) > 0, "VAD bypass deve prevenir filtrar todas as legendas"
        
        # vad_ok False indica que fallback foi usado
        assert vad_ok is False
    
    def test_end_to_end_with_real_audio(self):
        """Teste end-to-end com áudio real (TEST-.ogg)"""
        audio_path = Path(__file__).parent.parent / "TEST-.ogg"
        
        if not audio_path.exists():
            pytest.skip("Áudio TEST-.ogg não encontrado")
        
        # Simular segments (normalmente viria do Whisper)
        segments = [
            {"start": 0.0, "end": 3.0, "text": "Este é um teste de sincronização"},
            {"start": 3.0, "end": 6.0, "text": "Com timestamps ponderados por palavra"}
        ]
        
        # 1. Weighted word cues
        word_cues = segments_to_weighted_word_cues(segments)
        
        assert len(word_cues) > 0
        
        # 2. VAD processing
        gated_cues, vad_ok = process_subtitles_with_vad(str(audio_path), word_cues)
        
        # Deve ter pelo menos algumas legendas
        assert len(gated_cues) > 0
        
        # 3. SRT generation
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            srt_path = f.name
        
        try:
            write_srt_from_word_cues(gated_cues, srt_path, words_per_caption=2)
            
            # Validar SRT
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            assert len(content) > 0
            assert "1\n" in content  # Pelo menos 1 legenda
            assert "-->" in content
            
        finally:
            import os
            if os.path.exists(srt_path):
                os.remove(srt_path)


@pytest.mark.integration
class TestVADBypassLogic:
    """Testa lógica de bypass do VAD fallback"""
    
    def test_bypass_activates_when_no_segments(self):
        """Bypass deve ativar quando VAD não detecta nenhum segment"""
        raw_cues = [
            {'start': 0.0, 'end': 1.0, 'text': 'test'}
        ]
        
        # Criar áudio mínimo
        import tempfile
        import struct
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            audio_path = f.name
            
            # WAV header básico
            sample_rate = 16000
            num_samples = sample_rate  # 1 segundo
            
            f.write(b'RIFF')
            f.write(struct.pack('<I', 36 + num_samples * 2))
            f.write(b'WAVE')
            f.write(b'fmt ')
            f.write(struct.pack('<I', 16))
            f.write(struct.pack('<H', 1))
            f.write(struct.pack('<H', 1))
            f.write(struct.pack('<I', sample_rate))
            f.write(struct.pack('<I', sample_rate * 2))
            f.write(struct.pack('<H', 2))
            f.write(struct.pack('<H', 16))
            f.write(b'data')
            f.write(struct.pack('<I', num_samples * 2))
            f.write(b'\x00' * (num_samples * 2))
        
        try:
            gated_cues, vad_ok = process_subtitles_with_vad(audio_path, raw_cues)
            
            # Bypass deve preservar legendas
            assert len(gated_cues) > 0
            assert vad_ok is False  # Indica fallback
            
        finally:
            import os
            if os.path.exists(audio_path):
                os.remove(audio_path)


# Mark para rodar apenas em ambiente com dependências completas
pytestmark = pytest.mark.integration
