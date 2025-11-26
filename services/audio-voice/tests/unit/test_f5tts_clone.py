"""Testes unitários de clonagem F5-TTS"""
import pytest
from pathlib import Path
from app.f5tts_client import F5TTSClient

TEST_AUDIO = Path("/app/tests/Teste.mp3")

@pytest.mark.asyncio
async def test_clone_voice_creates_profile():
    """Testa se clonagem cria perfil válido"""
    client = F5TTSClient(device='cpu')
    
    profile = await client.clone_voice(
        audio_path=str(TEST_AUDIO),
        language="pt",
        voice_name="Teste Voice João"
    )
    
    # Valida perfil
    assert profile.id is not None
    assert profile.name == "Teste Voice João"
    assert profile.language == "pt"
    
    # Valida campos F5-TTS
    assert profile.reference_audio_path is not None
    assert Path(profile.reference_audio_path).exists()
    assert profile.reference_text is not None
    assert len(profile.reference_text) > 0
    
    # Valida transcrição
    ref_lower = profile.reference_text.lower()
    assert "oi" in ref_lower or "tudo" in ref_lower
    
    print(f"✅ Profile created: {profile.id}")
    print(f"   Audio: {profile.reference_audio_path}")
    print(f"   Text: {profile.reference_text}")

@pytest.mark.asyncio
async def test_clone_voice_validates_duration():
    """Testa se valida duração do áudio"""
    client = F5TTSClient(device='cpu')
    
    profile = await client.clone_voice(
        audio_path=str(TEST_AUDIO),
        language="pt",
        voice_name="Duration Test"
    )
    
    assert profile.duration is not None
    assert profile.duration > 0
    assert profile.duration < 15  # Teste.mp3 tem ~2.4s
    
    print(f"✅ Duration validated: {profile.duration:.2f}s")
