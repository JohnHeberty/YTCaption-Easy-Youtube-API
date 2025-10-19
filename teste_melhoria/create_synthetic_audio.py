"""
Cria arquivo de áudio de teste sintético para benchmark.
"""
from pathlib import Path
import numpy as np
import wave

def create_test_audio(duration_seconds=300, output_path="temp/test_video.wav"):
    """
    Cria áudio sintético de teste.
    
    Args:
        duration_seconds: Duração em segundos (padrão: 5 minutos)
        output_path: Caminho de saída
    """
    print(f"🎵 Criando áudio de teste sintético...")
    print(f"⏱️  Duração: {duration_seconds}s ({duration_seconds // 60} minutos)")
    
    # Criar diretório
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Parâmetros
    sample_rate = 16000  # 16kHz (mesmo do Whisper)
    num_samples = duration_seconds * sample_rate
    
    # Gerar áudio sintético (tons variados para simular fala)
    print("🎼 Gerando formas de onda...")
    t = np.linspace(0, duration_seconds, num_samples)
    
    # Mistura de frequências para simular fala
    audio = np.zeros(num_samples)
    freqs = [200, 400, 800, 1200]  # Frequências básicas da fala
    for freq in freqs:
        audio += 0.1 * np.sin(2 * np.pi * freq * t)
    
    # Adicionar variação de amplitude (simular prosódia)
    envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 0.1 * t)
    audio = audio * envelope
    
    # Normalizar para int16
    audio = np.int16(audio * 32767)
    
    # Salvar como WAV
    print(f"💾 Salvando em {output_file}...")
    with wave.open(str(output_file), 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio.tobytes())
    
    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"✅ Áudio criado com sucesso!")
    print(f"📁 Arquivo: {output_file}")
    print(f"📦 Tamanho: {size_mb:.2f} MB")
    print(f"⏱️  Duração: {duration_seconds}s")
    print(f"🎤 Sample rate: {sample_rate} Hz")

if __name__ == "__main__":
    # Criar áudio de 5 minutos para teste
    create_test_audio(duration_seconds=300, output_path="temp/test_video.wav")
    print("\n✅ Pronto para benchmark!")
    print("Execute: python teste_melhoria/test_multi_workers.py")
