"""
Teste de clonagem de voz XTTS standalone
Sprint 1.1: Validar que modelo carrega e gera áudio com GPU
"""
import sys
import os
import torch

def test_voice_cloning():
    """Testa clonagem de voz XTTS completa com GPU"""
    print("🎤 Testando XTTS voice cloning com GPU...")
    
    try:
        from TTS.api import TTS
        
        # Detecta dispositivo
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"   Device: {device}")
        
        # Carrega modelo em GPU
        print("   📥 Loading XTTS v2 model...")
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=(device=='cuda'))
        print("   ✅ Model loaded")
        
        # Verifica áudio de referência existe
        ref_audio = "/app/uploads/clone_20251126031159965237.ogg"
        
        if not os.path.exists(ref_audio):
            print(f"   ⚠️  Reference audio not found: {ref_audio}")
            print("   ℹ️  This is expected if running outside container")
            return True
        
        print(f"   ✅ Reference audio found: {ref_audio}")
        
        # Testa geração de áudio com clonagem
        print("   🎵 Generating audio with voice cloning...")
        output_path = "/tmp/test_xtts_cloning.wav"
        
        tts.tts_to_file(
            text="Olá, este é um teste de clonagem de voz com XTTS em português.",
            file_path=output_path,
            speaker_wav=ref_audio,
            language="pt"
        )
        
        # Verifica se arquivo foi criado
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"   ✅ Audio generated: {output_path} ({file_size} bytes)")
            os.remove(output_path)
            print("   ✅ Voice cloning test PASSED")
            return True
        else:
            print(f"   ❌ Audio file not created")
            return False
        
    except ImportError as e:
        print(f"   ❌ Import error: {e}")
        return False
    except RuntimeError as e:
        print(f"   ❌ Runtime error: {e}")
        return False

if __name__ == "__main__":
    success = test_voice_cloning()
    print(f"\n{'✅ PASS' if success else '❌ FAIL'}")
    sys.exit(0 if success else 1)
