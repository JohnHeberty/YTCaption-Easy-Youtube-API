"""Testa se F5-TTS importa corretamente"""
import sys

def test_f5tts_imports():
    try:
        from f5_tts.api import F5TTS
        print("✅ F5TTS class imported successfully")
        
        from f5_tts.infer.utils_infer import load_model, load_vocoder
        print("✅ F5TTS utils imported successfully")
        
        from transformers import pipeline
        print("✅ Transformers imported successfully")
        
        import vocos
        print("✅ Vocos imported successfully")
        
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

if __name__ == "__main__":
    success = test_f5tts_imports()
    sys.exit(0 if success else 1)
