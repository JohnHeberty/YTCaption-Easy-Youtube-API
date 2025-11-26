"""Testes unitários de síntese F5-TTS"""
import pytest
from pathlib import Path
from app.f5tts_client import F5TTSClient

TEST_AUDIO = Path("/app/tests/Teste.mp3")

@pytest.mark.asyncio
async def test_synthesis_with_cloned_voice():
    """Testa síntese com voz clonada de Teste.mp3"""
    client = F5TTSClient(device='cpu')
    
    # Clona voz
    profile = await client.clone_voice(
        audio_path=str(TEST_AUDIO),
        language="pt",
        voice_name="Síntese Test"
    )
    
    # Sintetiza frase DIFERENTE
    audio_bytes, duration = await client.generate_dubbing(
        text="Esta é uma nova frase gerada pela inteligência artificial",
        language="pt",
        voice_profile=profile,
        speed=1.0
    )
    
    # Valida saída
    assert len(audio_bytes) > 0
    assert duration > 0
    assert duration > 1.0  # frase razoavelmente longa
    
    # Salva para inspeção manual
    output_path = Path("/app/tests/output_clone_analysis/f5tts_synthesis_test.wav")
    output_path.parent.mkdir(exist_ok=True, parents=True)
    with open(output_path, 'wb') as f:
        f.write(audio_bytes)
    
    print(f"✅ Synthesis completed")
    print(f"   Duration: {duration:.2f}s")
    print(f"   Size: {len(audio_bytes)} bytes")
    print(f"   Saved: {output_path}")

@pytest.mark.asyncio
async def test_synthesis_same_text_as_reference():
    """Testa síntese do MESMO texto da referência"""
    client = F5TTSClient(device='cpu')
    
    # Clona voz
    profile = await client.clone_voice(
        audio_path=str(TEST_AUDIO),
        language="pt",
        voice_name="Same Text Test"
    )
    
    # Sintetiza MESMO texto: "Oi, tudo bem?"
    audio_bytes, duration = await client.generate_dubbing(
        text="Oi, tudo bem?",
        language="pt",
        voice_profile=profile,
        speed=1.0
    )
    
    # Valida
    assert len(audio_bytes) > 0
    assert duration > 0
    
    # Deve ter duração similar ao original (~2.4s)
    assert 1.0 < duration < 5.0
    
    # Salva
    output_path = Path("/app/tests/output_clone_analysis/f5tts_same_text.wav")
    with open(output_path, 'wb') as f:
        f.write(audio_bytes)
    
    print(f"✅ Same-text synthesis: {duration:.2f}s")
