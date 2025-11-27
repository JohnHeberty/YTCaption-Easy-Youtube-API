"""
Cria speaker default para dubbing genérico XTTS
Executado durante Docker build
"""
import numpy as np
import soundfile as sf
from pathlib import Path


def create_default_speaker():
    """Gera áudio sintético de 5s para referência"""
    sample_rate = 24000  # XTTS padrão
    duration = 5.0  # segundos
    
    # Gera tom senoidal simples (voz neutra)
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Frequências harmônicas (simula formantes vocais)
    f1, f2, f3 = 220, 440, 660  # Hz (voz neutra)
    audio = (
        0.3 * np.sin(2 * np.pi * f1 * t) +
        0.2 * np.sin(2 * np.pi * f2 * t) +
        0.1 * np.sin(2 * np.pi * f3 * t)
    )
    
    # Envelope (fade in/out)
    envelope = np.ones_like(audio)
    fade_samples = int(0.1 * sample_rate)  # 100ms fade
    envelope[:fade_samples] = np.linspace(0, 1, fade_samples)
    envelope[-fade_samples:] = np.linspace(1, 0, fade_samples)
    
    audio = audio * envelope
    
    # Normaliza
    audio = audio / np.max(np.abs(audio)) * 0.8
    
    # Salva
    output_path = Path('/app/uploads/default_speaker.wav')
    output_path.parent.mkdir(exist_ok=True, parents=True)
    
    sf.write(str(output_path), audio.astype(np.float32), sample_rate)
    print(f"✅ Default speaker created: {output_path}")


if __name__ == '__main__':
    create_default_speaker()
