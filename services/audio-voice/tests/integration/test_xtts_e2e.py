"""
Testes End-to-End XTTS: Fluxo completo de clonagem → dubbing
Sprint 1.3 (RED PHASE): Testes vão FALHAR até implementar XTTSClient
"""
import pytest
import sys
import os
import io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from app.xtts_client import XTTSClient
from app.models import VoiceProfile


class TestXTTSEndToEnd:
    """Testes E2E - Fluxo completo de clonagem e dubbing"""
    
    @pytest.mark.asyncio
    async def test_e2e_clone_and_dub(self):
        """Testa fluxo completo: clonar voz → usar para dubbing"""
        client = XTTSClient(device='cpu')
        
        # PASSO 1: Clonar voz
        print("\n🎤 Clonando voz...")
        ref_audio = "/app/uploads/clone_20251126031159965237.ogg"
        
        if not os.path.exists(ref_audio):
            pytest.skip(f"Áudio de referência não encontrado: {ref_audio}")
        
        profile = await client.clone_voice(
            audio_path=ref_audio,
            language="pt",
            voice_name="E2E Test Voice",
            description="Voz de teste end-to-end"
        )
        
        assert profile is not None, "Profile não foi criado"
        assert isinstance(profile, VoiceProfile), "Profile tipo incorreto"
        assert profile.name == "E2E Test Voice"
        print(f"   ✅ Voz clonada: {profile.id}")
        
        # PASSO 2: Gerar dubbing com voz clonada
        print("\n🎬 Gerando dubbing com voz clonada...")
        audio_bytes, duration = await client.generate_dubbing(
            text="Este é um teste de dubbing com voz clonada usando XTTS.",
            language="pt",
            voice_profile=profile
        )
        
        assert len(audio_bytes) > 0, "Áudio vazio"
        assert duration > 0, "Duração inválida"
        assert duration > 2, "Áudio muito curto para frase completa"
        print(f"   ✅ Dubbing gerado: {duration:.2f}s, {len(audio_bytes)} bytes")
        
        # PASSO 3: Validar qualidade do áudio
        try:
            import soundfile as sf
            
            audio_data, sr = sf.read(io.BytesIO(audio_bytes))
            assert sr == 24000, f"Sample rate deve ser 24kHz XTTS, got {sr}"
            assert len(audio_data) > sr * 2, "Áudio deve ter pelo menos 2 segundos"
            print("   ✅ Qualidade validada (24kHz, >2s)")
        except ImportError:
            # soundfile não instalado - valida apenas tamanho
            print("   ⚠️  soundfile não disponível - validação parcial")
            assert len(audio_bytes) > 10000, "Áudio muito pequeno"
    
    @pytest.mark.asyncio
    async def test_e2e_multiple_dubbing_same_voice(self):
        """Testa múltiplos dubbings com mesma voz clonada"""
        client = XTTSClient(device='cpu')
        
        ref_audio = "/app/uploads/clone_20251126031159965237.ogg"
        
        if not os.path.exists(ref_audio):
            pytest.skip("Áudio de referência não encontrado")
        
        # Clone voice
        profile = await client.clone_voice(
            audio_path=ref_audio,
            language="pt",
            voice_name="Multi Dubbing Test"
        )
        
        # Gera 3 dubbings diferentes com mesma voz
        texts = [
            "Primeira frase com voz clonada.",
            "Segunda frase de teste.",
            "Terceira e última frase de validação."
        ]
        
        results = []
        for i, text in enumerate(texts, 1):
            print(f"\n🎬 Dubbing {i}/3...")
            audio_bytes, duration = await client.generate_dubbing(
                text=text,
                language="pt",
                voice_profile=profile
            )
            
            assert len(audio_bytes) > 0, f"Dubbing {i} vazio"
            assert duration > 0, f"Dubbing {i} duração inválida"
            
            results.append({
                'text': text,
                'size': len(audio_bytes),
                'duration': duration
            })
            print(f"   ✅ Dubbing {i}: {duration:.2f}s, {len(audio_bytes)} bytes")
        
        # Valida que todos foram gerados
        assert len(results) == 3, "Nem todos os dubbings foram gerados"
        
        # Valida que durações são proporcionais ao texto
        assert results[0]['duration'] > 1, "Dubbing 1 muito curto"
        assert results[1]['duration'] > 1, "Dubbing 2 muito curto"
        assert results[2]['duration'] > 1, "Dubbing 3 muito curto"
    
    @pytest.mark.asyncio
    async def test_e2e_without_cloning(self):
        """Testa dubbing sem clonagem (voz genérica)"""
        client = XTTSClient(device='cpu')
        
        print("\n🎬 Gerando dubbing sem clonagem...")
        audio_bytes, duration = await client.generate_dubbing(
            text="Este é um teste sem clonagem de voz.",
            language="pt",
            voice_preset="female_generic"  # Voz genérica
        )
        
        assert len(audio_bytes) > 0, "Áudio vazio"
        assert duration > 0, "Duração inválida"
        print(f"   ✅ Dubbing genérico: {duration:.2f}s")
    
    @pytest.mark.asyncio
    async def test_e2e_different_languages(self):
        """Testa dubbing em múltiplas linguagens (se suportado)"""
        client = XTTSClient(device='cpu')
        
        languages = client.get_supported_languages()
        
        # Testa português (sempre deve ter) e inglês (comum)
        test_cases = [
            ("pt", "Teste em português"),
            ("en", "Test in English"),
        ]
        
        for lang, text in test_cases:
            if lang not in languages:
                print(f"   ⚠️  Linguagem {lang} não suportada, pulando")
                continue
            
            print(f"\n🌍 Testando {lang}...")
            audio_bytes, duration = await client.generate_dubbing(
                text=text,
                language=lang,
                voice_preset="female_generic"
            )
            
            assert len(audio_bytes) > 0, f"Áudio {lang} vazio"
            assert duration > 0, f"Duração {lang} inválida"
            print(f"   ✅ {lang}: {duration:.2f}s")
    
    @pytest.mark.asyncio
    async def test_e2e_performance_benchmark(self):
        """Testa performance: tempo real vs tempo de geração"""
        import time
        
        client = XTTSClient(device='cpu')
        
        text = "Este é um teste de performance para medir a velocidade de geração de áudio."
        
        print("\n⏱️  Benchmark de performance...")
        start_time = time.time()
        
        audio_bytes, duration = await client.generate_dubbing(
            text=text,
            language="pt",
            voice_preset="female_generic"
        )
        
        generation_time = time.time() - start_time
        
        assert len(audio_bytes) > 0, "Áudio vazio"
        assert duration > 0, "Duração inválida"
        
        # Calcula real-time factor
        rtf = generation_time / duration
        
        print(f"   🎵 Áudio: {duration:.2f}s")
        print(f"   ⚙️  Geração: {generation_time:.2f}s")
        print(f"   📊 RTF: {rtf:.2f}x")
        
        # Performance aceitável: <10x real-time em CPU
        assert rtf < 10, f"Performance muito lenta: {rtf:.2f}x (máx 10x)"
        
        if rtf < 1:
            print("   🚀 Faster than real-time!")
        else:
            print(f"   ✅ Performance aceitável ({rtf:.2f}x)")
