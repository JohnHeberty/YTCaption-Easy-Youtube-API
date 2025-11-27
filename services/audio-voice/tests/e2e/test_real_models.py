"""
E2E Tests with Real Models - Sprint 7

Testes end-to-end com modelos reais (XTTS, F5-TTS, Whisper)
Requer GPU ou CPU com modelos baixados

Marking: pytest -m "e2e" para rodar esses testes
"""

import pytest
import numpy as np
import soundfile as sf
import time
import psutil
import os
from pathlib import Path
from typing import Dict, Any

from app.engines.xtts_engine import XttsEngine
from app.engines.f5tts_engine import F5TtsEngine
from app.models import VoiceProfile, QualityProfile


# Fixtures para performance monitoring
@pytest.fixture
def performance_monitor():
    """Monitor para métricas de performance"""
    class PerformanceMonitor:
        def __init__(self):
            self.metrics = {}
            self.process = psutil.Process()
        
        def start(self, label: str):
            self.metrics[label] = {
                'start_time': time.time(),
                'start_memory': self.process.memory_info().rss / 1024 / 1024,  # MB
            }
        
        def end(self, label: str):
            if label not in self.metrics:
                raise ValueError(f"Label {label} not started")
            
            self.metrics[label]['end_time'] = time.time()
            self.metrics[label]['end_memory'] = self.process.memory_info().rss / 1024 / 1024
            self.metrics[label]['duration'] = (
                self.metrics[label]['end_time'] - self.metrics[label]['start_time']
            )
            self.metrics[label]['memory_delta'] = (
                self.metrics[label]['end_memory'] - self.metrics[label]['start_memory']
            )
        
        def get_rtf(self, label: str, audio_duration: float) -> float:
            """Real-Time Factor: processing_time / audio_duration"""
            if label not in self.metrics:
                raise ValueError(f"Label {label} not found")
            
            return self.metrics[label]['duration'] / audio_duration if audio_duration > 0 else 0
        
        def get_report(self) -> str:
            """Generate performance report"""
            report = "\n" + "="*80 + "\n"
            report += "📊 PERFORMANCE REPORT\n"
            report += "="*80 + "\n\n"
            
            for label, data in self.metrics.items():
                report += f"🔹 {label}:\n"
                report += f"   ⏱️  Duration: {data['duration']:.2f}s\n"
                report += f"   💾 Memory Delta: {data['memory_delta']:.1f}MB\n"
                if 'rtf' in data:
                    report += f"   ⚡ RTF: {data['rtf']:.2f}x\n"
                report += "\n"
            
            return report
    
    return PerformanceMonitor()


@pytest.fixture
def temp_audio_dir(tmp_path):
    """Diretório temporário para áudios de teste"""
    audio_dir = tmp_path / "test_audio"
    audio_dir.mkdir(exist_ok=True)
    return audio_dir


@pytest.fixture
def create_reference_audio(temp_audio_dir):
    """Factory para criar áudio de referência"""
    def _create(duration: float = 5.0, sample_rate: int = 24000, filename: str = "reference.wav"):
        # Cria áudio com ruído rosa (mais natural que ruído branco)
        samples = int(duration * sample_rate)
        # Ruído rosa: mais energia em baixas frequências
        white_noise = np.random.randn(samples)
        # Aplicar filtro simples para aproximar ruído rosa
        pink_noise = np.cumsum(white_noise) / 50.0
        # Normalizar
        pink_noise = pink_noise / np.max(np.abs(pink_noise)) * 0.5
        
        audio_path = temp_audio_dir / filename
        sf.write(audio_path, pink_noise, sample_rate)
        
        return str(audio_path)
    
    return _create


# ==============================================================================
# SPRINT 7: E2E TESTS - XTTS REAL MODEL
# ==============================================================================

@pytest.mark.e2e
@pytest.mark.slow
class TestXttsRealModel:
    """E2E tests para XTTS com modelo real"""
    
    @pytest.fixture(autouse=True)
    def setup_xtts(self):
        """Setup XTTS engine com modelo real"""
        self.engine = XttsEngine(
            device=None,  # Auto-detect GPU/CPU
            fallback_to_cpu=True,
            model_name='tts_models/multilingual/multi-dataset/xtts_v2'
        )
        yield
        # Cleanup se necessário
    
    @pytest.mark.asyncio
    async def test_xtts_basic_synthesis_ptbr(self, performance_monitor):
        """XTTS: síntese básica PT-BR"""
        text = "Olá, este é um teste de síntese de voz em português brasileiro."
        
        performance_monitor.start('xtts_basic_synthesis')
        
        audio_bytes, duration = await self.engine.generate_dubbing(
            text=text,
            language="pt-BR",
            quality_profile=QualityProfile.BALANCED
        )
        
        performance_monitor.end('xtts_basic_synthesis')
        
        # Validações
        assert len(audio_bytes) > 0, "Audio bytes vazio"
        assert duration > 0, "Duração inválida"
        
        # RTF
        rtf = performance_monitor.get_rtf('xtts_basic_synthesis', duration)
        performance_monitor.metrics['xtts_basic_synthesis']['rtf'] = rtf
        
        print(f"\n✅ XTTS Basic Synthesis PT-BR:")
        print(f"   Audio Duration: {duration:.2f}s")
        print(f"   Processing Time: {performance_monitor.metrics['xtts_basic_synthesis']['duration']:.2f}s")
        print(f"   RTF: {rtf:.2f}x")
        print(f"   Memory: {performance_monitor.metrics['xtts_basic_synthesis']['memory_delta']:.1f}MB")
        
        # Expectativas de performance
        assert rtf < 5.0, f"RTF muito alto: {rtf:.2f}x (esperado <5x)"
    
    @pytest.mark.asyncio
    async def test_xtts_voice_cloning_ptbr(self, create_reference_audio, performance_monitor):
        """XTTS: voice cloning PT-BR"""
        ref_audio = create_reference_audio(duration=6.0, filename="ref_xtts.wav")
        
        # Criar VoiceProfile
        profile = await self.engine.clone_voice(
            audio_path=ref_audio,
            language="pt-BR",
            voice_name="Test Voice XTTS"
        )
        
        assert profile is not None
        assert profile.name == "Test Voice XTTS"
        
        # Síntese com voz clonada
        text = "Esta é uma frase sintetizada com voz clonada."
        
        performance_monitor.start('xtts_voice_cloning')
        
        audio_bytes, duration = await self.engine.generate_dubbing(
            text=text,
            language="pt-BR",
            voice_profile=profile,
            quality_profile=QualityProfile.BALANCED
        )
        
        performance_monitor.end('xtts_voice_cloning')
        
        assert len(audio_bytes) > 0
        assert duration > 0
        
        rtf = performance_monitor.get_rtf('xtts_voice_cloning', duration)
        performance_monitor.metrics['xtts_voice_cloning']['rtf'] = rtf
        
        print(f"\n✅ XTTS Voice Cloning PT-BR:")
        print(f"   RTF: {rtf:.2f}x")
    
    @pytest.mark.asyncio
    async def test_xtts_quality_profiles_comparison(self, performance_monitor):
        """XTTS: comparação de quality profiles"""
        text = "Teste de qualidade de áudio."
        
        results = {}
        
        for profile in [QualityProfile.STABLE, QualityProfile.BALANCED, QualityProfile.EXPRESSIVE]:
            label = f'xtts_{profile.value}'
            performance_monitor.start(label)
            
            audio_bytes, duration = await self.engine.generate_dubbing(
                text=text,
                language="pt-BR",
                quality_profile=profile
            )
            
            performance_monitor.end(label)
            
            rtf = performance_monitor.get_rtf(label, duration)
            performance_monitor.metrics[label]['rtf'] = rtf
            
            results[profile.value] = {
                'duration': duration,
                'rtf': rtf,
                'size': len(audio_bytes)
            }
        
        print(f"\n✅ XTTS Quality Profiles Comparison:")
        for profile, data in results.items():
            print(f"   {profile}: RTF={data['rtf']:.2f}x, Size={data['size']/1024:.1f}KB")
    
    @pytest.mark.asyncio
    async def test_xtts_long_text_ptbr(self, performance_monitor):
        """XTTS: texto longo PT-BR (stress test)"""
        # Texto com ~200 palavras
        text = " ".join([
            "O processamento de linguagem natural em português brasileiro apresenta desafios únicos.",
            "A síntese de voz deve preservar a prosódia e entonação características do idioma.",
            "Este teste avalia a capacidade do sistema de lidar com textos extensos.",
            "A qualidade do áudio sintetizado deve permanecer consistente ao longo de toda a síntese.",
            "Além disso, o tempo de processamento deve ser razoável mesmo para textos longos.",
        ] * 10)  # Repete 10x = ~200 palavras
        
        performance_monitor.start('xtts_long_text')
        
        audio_bytes, duration = await self.engine.generate_dubbing(
            text=text,
            language="pt-BR",
            quality_profile=QualityProfile.BALANCED
        )
        
        performance_monitor.end('xtts_long_text')
        
        assert len(audio_bytes) > 0
        assert duration > 10.0, "Áudio muito curto para texto longo"
        
        rtf = performance_monitor.get_rtf('xtts_long_text', duration)
        performance_monitor.metrics['xtts_long_text']['rtf'] = rtf
        
        print(f"\n✅ XTTS Long Text PT-BR:")
        print(f"   Text Length: {len(text)} chars")
        print(f"   Audio Duration: {duration:.2f}s")
        print(f"   RTF: {rtf:.2f}x")


# ==============================================================================
# SPRINT 7: E2E TESTS - F5-TTS REAL MODEL
# ==============================================================================

@pytest.mark.e2e
@pytest.mark.slow
class TestF5TtsRealModel:
    """E2E tests para F5-TTS com modelo real"""
    
    @pytest.fixture(autouse=True)
    def setup_f5tts(self):
        """Setup F5-TTS engine com modelo real"""
        self.engine = F5TtsEngine(
            device=None,  # Auto-detect GPU/CPU
            fallback_to_cpu=True,
            model_name='SWivid/F5-TTS'
        )
        yield
    
    @pytest.mark.asyncio
    async def test_f5tts_basic_synthesis_ptbr(self, performance_monitor):
        """F5-TTS: síntese básica PT-BR"""
        text = "Olá, este é um teste de síntese com F5-TTS em português brasileiro."
        
        performance_monitor.start('f5tts_basic_synthesis')
        
        audio_bytes, duration = await self.engine.generate_dubbing(
            text=text,
            language="pt-BR",
            quality_profile=QualityProfile.BALANCED
        )
        
        performance_monitor.end('f5tts_basic_synthesis')
        
        assert len(audio_bytes) > 0
        assert duration > 0
        
        rtf = performance_monitor.get_rtf('f5tts_basic_synthesis', duration)
        performance_monitor.metrics['f5tts_basic_synthesis']['rtf'] = rtf
        
        print(f"\n✅ F5-TTS Basic Synthesis PT-BR:")
        print(f"   Audio Duration: {duration:.2f}s")
        print(f"   RTF: {rtf:.2f}x")
        print(f"   Memory: {performance_monitor.metrics['f5tts_basic_synthesis']['memory_delta']:.1f}MB")
    
    @pytest.mark.asyncio
    async def test_f5tts_voice_cloning_with_ref_text(
        self, 
        create_reference_audio, 
        performance_monitor
    ):
        """F5-TTS: voice cloning com ref_text (modo preferencial)"""
        ref_audio = create_reference_audio(duration=6.0, filename="ref_f5tts.wav")
        ref_text = "Esta é a transcrição do áudio de referência em português."
        
        # Clone voice com ref_text
        profile = await self.engine.clone_voice(
            audio_path=ref_audio,
            language="pt-BR",
            voice_name="Test Voice F5-TTS",
            ref_text=ref_text
        )
        
        assert profile is not None
        assert profile.ref_text == ref_text
        
        # Síntese com voz clonada
        text = "Agora sintetizando com a voz clonada usando F5-TTS."
        
        performance_monitor.start('f5tts_voice_cloning_ref_text')
        
        audio_bytes, duration = await self.engine.generate_dubbing(
            text=text,
            language="pt-BR",
            voice_profile=profile,
            quality_profile=QualityProfile.BALANCED
        )
        
        performance_monitor.end('f5tts_voice_cloning_ref_text')
        
        assert len(audio_bytes) > 0
        
        rtf = performance_monitor.get_rtf('f5tts_voice_cloning_ref_text', duration)
        performance_monitor.metrics['f5tts_voice_cloning_ref_text']['rtf'] = rtf
        
        print(f"\n✅ F5-TTS Voice Cloning with ref_text:")
        print(f"   RTF: {rtf:.2f}x")
    
    @pytest.mark.asyncio
    async def test_f5tts_auto_transcription(
        self, 
        create_reference_audio, 
        performance_monitor
    ):
        """F5-TTS: auto-transcription com Whisper (fallback)"""
        ref_audio = create_reference_audio(duration=6.0, filename="ref_f5tts_auto.wav")
        
        # Clone voice SEM ref_text (trigger auto-transcription)
        performance_monitor.start('f5tts_auto_transcription')
        
        profile = await self.engine.clone_voice(
            audio_path=ref_audio,
            language="pt-BR",
            voice_name="Auto Transcribed Voice",
            ref_text=None  # Trigger Whisper
        )
        
        performance_monitor.end('f5tts_auto_transcription')
        
        assert profile is not None
        # Com ruído rosa, Whisper pode retornar texto vazio ou noise
        # Apenas valida que não crashou
        print(f"\n✅ F5-TTS Auto-transcription:")
        print(f"   Transcribed: {profile.ref_text or '(vazio - ruído)'}")
        print(f"   Time: {performance_monitor.metrics['f5tts_auto_transcription']['duration']:.2f}s")
    
    @pytest.mark.asyncio
    async def test_f5tts_quality_profiles_nfe_steps(self, performance_monitor):
        """F5-TTS: comparação de NFE steps (quality vs speed)"""
        text = "Teste de qualidade F5-TTS."
        
        results = {}
        
        for profile in [QualityProfile.STABLE, QualityProfile.BALANCED, QualityProfile.EXPRESSIVE]:
            label = f'f5tts_{profile.value}'
            performance_monitor.start(label)
            
            audio_bytes, duration = await self.engine.generate_dubbing(
                text=text,
                language="pt-BR",
                quality_profile=profile
            )
            
            performance_monitor.end(label)
            
            rtf = performance_monitor.get_rtf(label, duration)
            performance_monitor.metrics[label]['rtf'] = rtf
            
            results[profile.value] = {
                'duration': duration,
                'rtf': rtf,
                'processing_time': performance_monitor.metrics[label]['duration']
            }
        
        print(f"\n✅ F5-TTS Quality Profiles (NFE Steps) Comparison:")
        for profile, data in results.items():
            print(f"   {profile}: RTF={data['rtf']:.2f}x, ProcessTime={data['processing_time']:.2f}s")


# ==============================================================================
# SPRINT 7: E2E TESTS - PERFORMANCE COMPARISON
# ==============================================================================

@pytest.mark.e2e
@pytest.mark.slow
class TestEngineComparison:
    """Comparação de performance XTTS vs F5-TTS"""
    
    @pytest.fixture(autouse=True)
    def setup_engines(self):
        """Setup ambos engines"""
        self.xtts = XttsEngine(device=None, fallback_to_cpu=True)
        self.f5tts = F5TtsEngine(device=None, fallback_to_cpu=True)
        yield
    
    @pytest.mark.asyncio
    async def test_comparative_synthesis_ptbr(self, performance_monitor):
        """Comparação direta: XTTS vs F5-TTS para mesmo texto"""
        text = "Esta é uma frase de comparação entre os dois motores de TTS."
        
        # XTTS
        performance_monitor.start('comparison_xtts')
        xtts_audio, xtts_duration = await self.xtts.generate_dubbing(
            text=text,
            language="pt-BR",
            quality_profile=QualityProfile.BALANCED
        )
        performance_monitor.end('comparison_xtts')
        
        # F5-TTS
        performance_monitor.start('comparison_f5tts')
        f5tts_audio, f5tts_duration = await self.f5tts.generate_dubbing(
            text=text,
            language="pt-BR",
            quality_profile=QualityProfile.BALANCED
        )
        performance_monitor.end('comparison_f5tts')
        
        # Calcular RTF
        xtts_rtf = performance_monitor.get_rtf('comparison_xtts', xtts_duration)
        f5tts_rtf = performance_monitor.get_rtf('comparison_f5tts', f5tts_duration)
        
        performance_monitor.metrics['comparison_xtts']['rtf'] = xtts_rtf
        performance_monitor.metrics['comparison_f5tts']['rtf'] = f5tts_rtf
        
        print(f"\n" + "="*80)
        print(f"📊 COMPARATIVE ANALYSIS: XTTS vs F5-TTS")
        print("="*80)
        print(f"\nText: '{text}'")
        print(f"\n🔹 XTTS:")
        print(f"   Audio Duration: {xtts_duration:.2f}s")
        print(f"   Processing Time: {performance_monitor.metrics['comparison_xtts']['duration']:.2f}s")
        print(f"   RTF: {xtts_rtf:.2f}x")
        print(f"   Memory: {performance_monitor.metrics['comparison_xtts']['memory_delta']:.1f}MB")
        print(f"   Size: {len(xtts_audio)/1024:.1f}KB")
        
        print(f"\n🔹 F5-TTS:")
        print(f"   Audio Duration: {f5tts_duration:.2f}s")
        print(f"   Processing Time: {performance_monitor.metrics['comparison_f5tts']['duration']:.2f}s")
        print(f"   RTF: {f5tts_rtf:.2f}x")
        print(f"   Memory: {performance_monitor.metrics['comparison_f5tts']['memory_delta']:.1f}MB")
        print(f"   Size: {len(f5tts_audio)/1024:.1f}KB")
        
        print(f"\n📈 Comparison:")
        if xtts_rtf < f5tts_rtf:
            print(f"   ⚡ XTTS é {f5tts_rtf/xtts_rtf:.2f}x mais rápido")
        else:
            print(f"   ⚡ F5-TTS é {xtts_rtf/f5tts_rtf:.2f}x mais rápido")
        
        print("="*80 + "\n")


# ==============================================================================
# SPRINT 7: E2E TESTS - AUDIO QUALITY VALIDATION
# ==============================================================================

@pytest.mark.e2e
@pytest.mark.slow
class TestAudioQuality:
    """Validação de qualidade de áudio"""
    
    @pytest.mark.asyncio
    async def test_audio_sample_rate_validation(self):
        """Valida sample rate do áudio gerado"""
        engine = XttsEngine(device=None, fallback_to_cpu=True)
        
        audio_bytes, duration = await engine.generate_dubbing(
            text="Teste de sample rate",
            language="pt-BR"
        )
        
        # Salvar e verificar sample rate
        import io
        audio_array, sample_rate = sf.read(io.BytesIO(audio_bytes))
        
        assert sample_rate == 24000, f"Sample rate inválido: {sample_rate}"
        
        print(f"\n✅ Audio Sample Rate: {sample_rate}Hz")
    
    @pytest.mark.asyncio
    async def test_audio_normalization_no_clipping(self):
        """Valida que áudio está normalizado sem clipping"""
        engine = F5TtsEngine(device=None, fallback_to_cpu=True)
        
        audio_bytes, duration = await engine.generate_dubbing(
            text="Teste de normalização e clipping",
            language="pt-BR"
        )
        
        # Ler áudio
        import io
        audio_array, sample_rate = sf.read(io.BytesIO(audio_bytes))
        
        # Verificar clipping
        max_value = np.max(np.abs(audio_array))
        
        assert max_value <= 1.0, f"Clipping detectado: max={max_value}"
        assert max_value > 0.1, "Áudio muito baixo (possível erro)"
        
        print(f"\n✅ Audio Peak Level: {max_value:.3f} (normalized, no clipping)")
    
    @pytest.mark.asyncio
    async def test_audio_snr_basic(self):
        """Valida SNR básico (detecta silêncio vs áudio)"""
        engine = XttsEngine(device=None, fallback_to_cpu=True)
        
        audio_bytes, duration = await engine.generate_dubbing(
            text="Teste de relação sinal-ruído",
            language="pt-BR"
        )
        
        import io
        audio_array, sample_rate = sf.read(io.BytesIO(audio_bytes))
        
        # Calcular RMS
        rms = np.sqrt(np.mean(audio_array**2))
        
        # RMS deve ser significativo (não silêncio)
        assert rms > 0.01, f"Áudio muito baixo (RMS={rms:.4f}), possível silêncio"
        
        print(f"\n✅ Audio RMS: {rms:.4f} (signal present)")


# ==============================================================================
# SPRINT 7: E2E TESTS - EDGE CASES
# ==============================================================================

@pytest.mark.e2e
@pytest.mark.slow
class TestEdgeCases:
    """Testes de edge cases e robustez"""
    
    @pytest.mark.asyncio
    async def test_special_characters_ptbr(self):
        """Testa caracteres especiais PT-BR"""
        engine = XttsEngine(device=None, fallback_to_cpu=True)
        
        text = "Ação, coração, não, pão, mãe, canção, José, açúcar!"
        
        audio_bytes, duration = await engine.generate_dubbing(
            text=text,
            language="pt-BR"
        )
        
        assert len(audio_bytes) > 0
        assert duration > 0
        
        print(f"\n✅ Special Characters PT-BR: OK (duration={duration:.2f}s)")
    
    @pytest.mark.asyncio
    async def test_multiple_sentences(self):
        """Testa múltiplas frases"""
        engine = F5TtsEngine(device=None, fallback_to_cpu=True)
        
        text = "Primeira frase. Segunda frase! Terceira frase? Quarta frase."
        
        audio_bytes, duration = await engine.generate_dubbing(
            text=text,
            language="pt-BR"
        )
        
        assert len(audio_bytes) > 0
        assert duration > 2.0  # Deve ter duração razoável
        
        print(f"\n✅ Multiple Sentences: OK (duration={duration:.2f}s)")
    
    @pytest.mark.asyncio
    async def test_numbers_and_symbols(self):
        """Testa números e símbolos"""
        engine = XttsEngine(device=None, fallback_to_cpu=True)
        
        text = "O ano é 2025, com 100% de sucesso. R$ 1.000,00 investidos!"
        
        audio_bytes, duration = await engine.generate_dubbing(
            text=text,
            language="pt-BR"
        )
        
        assert len(audio_bytes) > 0
        
        print(f"\n✅ Numbers and Symbols: OK")


# ==============================================================================
# SPRINT 7: PERFORMANCE REPORT (after all tests)
# ==============================================================================

def pytest_sessionfinish(session, exitstatus):
    """Hook para gerar relatório final após todos testes"""
    # Este hook será executado pelo pytest
    pass
