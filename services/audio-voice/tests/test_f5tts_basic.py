"""Testa instanciação básica F5-TTS"""
from f5_tts.api import F5TTS
import torch

def test_f5tts_instantiation():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Testing on device: {device}")
    
    # Instancia (vai baixar modelos na primeira vez!)
    f5tts = F5TTS(
        model="F5TTS_v1_Base",
        device=device,
        hf_cache_dir="/app/models/f5tts"
    )
    
    print(f"✅ F5TTS instantiated successfully")
    print(f"   Model: {f5tts.mel_spec_type}")
    print(f"   Sample rate: {f5tts.target_sample_rate}")
    print(f"   Device: {f5tts.device}")
    
    return True

if __name__ == "__main__":
    test_f5tts_instantiation()
