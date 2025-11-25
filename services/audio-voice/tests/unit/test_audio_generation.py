"""
Testes unitários para geração de áudio pelo MockOpenVoiceModel
"""
import pytest
import numpy as np
from app.openvoice_client import MockOpenVoiceModel


def test_mock_tts_generates_audio():
    """Testa se TTS mock gera áudio com som"""
    model = MockOpenVoiceModel()
    
    audio = model.tts("Hello world", "default", "en")
    
    # Verifica shape
    assert isinstance(audio, np.ndarray)
    assert len(audio.shape) == 1  # Array 1D
    assert audio.shape[0] > 0  # Tem samples
    
    # Verifica que NÃO é silêncio
    assert audio.max() > 0.1, "Audio deve ter som audível!"
    assert audio.min() < -0.1, "Audio deve ter variação negativa!"
    
    # Verifica range esperado (amplitude ~30%)
    assert abs(audio.max()) <= 0.5, "Audio não deve ultrapassar 50% da amplitude"
    
    print(f"✅ Audio gerado: {audio.shape[0]} samples, range [{audio.min():.3f}, {audio.max():.3f}]")


def test_mock_tts_duration_proportional_to_text():
    """Testa se duração do áudio é proporcional ao texto"""
    model = MockOpenVoiceModel()
    
    short_audio = model.tts("Hi", "default", "en")
    long_audio = model.tts("This is a much longer text that should generate longer audio", "default", "en")
    
    # Áudio longo deve ter mais samples
    assert long_audio.shape[0] > short_audio.shape[0]
    
    print(f"✅ Short: {short_audio.shape[0]} samples, Long: {long_audio.shape[0]} samples")


def test_mock_tts_with_voice_generates_audio():
    """Testa se TTS com voz clonada gera áudio"""
    model = MockOpenVoiceModel()
    
    # Cria embedding fake
    embedding = np.random.randn(256).astype(np.float32)
    
    audio = model.tts_with_voice("Test text", embedding)
    
    # Verifica que tem som
    assert audio.max() > 0.1
    assert audio.min() < -0.1
    
    print(f"✅ Cloned voice audio: {audio.shape[0]} samples, range [{audio.min():.3f}, {audio.max():.3f}]")


def test_mock_extract_embedding():
    """Testa se extração de embedding funciona"""
    model = MockOpenVoiceModel()
    
    embedding = model.extract_voice_embedding("/fake/path.wav", "en")
    
    # Verifica shape
    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (256,)
    
    # Verifica normalização
    norm = np.linalg.norm(embedding)
    assert abs(norm - 1.0) < 0.01, "Embedding deve estar normalizado"
    
    print(f"✅ Embedding gerado: shape={embedding.shape}, norm={norm:.3f}")


def test_mock_embedding_deterministic():
    """Testa se embedding é determinístico para mesmo path"""
    model = MockOpenVoiceModel()
    
    emb1 = model.extract_voice_embedding("/same/path.wav", "en")
    emb2 = model.extract_voice_embedding("/same/path.wav", "en")
    
    # Deve ser idêntico
    np.testing.assert_array_equal(emb1, emb2)
    
    print("✅ Embeddings determinísticos para mesmo path")


def test_mock_different_texts_produce_different_audio():
    """Testa se textos diferentes produzem áudios distinguíveis"""
    model = MockOpenVoiceModel()
    
    audio1 = model.tts("Text one", "default", "en")
    audio2 = model.tts("Text two", "default", "en")
    
    # Podem ter tamanhos diferentes ou características diferentes
    # (devido à variação de frequência baseada no comprimento)
    different = not np.array_equal(audio1, audio2)
    
    assert different or audio1.shape != audio2.shape, "Textos diferentes devem gerar áudios diferentes"
    
    print("✅ Textos diferentes geram áudios distinguíveis")


def test_audio_has_envelope():
    """Testa se áudio tem envelope suave (sem cliques)"""
    model = MockOpenVoiceModel()
    
    audio = model.tts("Test envelope", "default", "en")
    
    # Verifica que início e fim têm amplitude menor (envelope)
    attack_samples = 100
    release_samples = 100
    
    # Início deve começar próximo de zero
    assert abs(audio[0]) < 0.1, "Audio deve começar suave"
    
    # Fim deve terminar próximo de zero
    assert abs(audio[-1]) < 0.1, "Audio deve terminar suave"
    
    # Meio deve ter amplitude maior
    middle = audio[len(audio)//2]
    assert abs(middle) > 0.2, "Meio do áudio deve ter amplitude significativa"
    
    print("✅ Audio tem envelope suave (ADSR)")


if __name__ == "__main__":
    print("\n🧪 Running audio generation tests...\n")
    
    test_mock_tts_generates_audio()
    test_mock_tts_duration_proportional_to_text()
    test_mock_tts_with_voice_generates_audio()
    test_mock_extract_embedding()
    test_mock_embedding_deterministic()
    test_mock_different_texts_produce_different_audio()
    test_audio_has_envelope()
    
    print("\n✅ All audio generation tests passed!\n")
