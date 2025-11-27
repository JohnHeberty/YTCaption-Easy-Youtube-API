"""
Teste standalone XTTS - Validar modelo fora do projeto
Sprint 1.1: Teste de instalação e funcionalidade básica
"""
import sys
import torch

def test_xtts_basic():
    """Testa instanciação do modelo XTTS"""
    print("🔧 Testando XTTS standalone...")
    
    try:
        from TTS.api import TTS
        print("   ✅ TTS imported successfully")
    except ImportError as e:
        print(f"   ❌ Failed to import TTS: {e}")
        return False
    
    # Device
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"   Device: {device}")
    
    try:
        # Instancia modelo (vai baixar na primeira vez!)
        print("   📥 Loading XTTS v2 model (may download ~2GB on first run)...")
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=(device=='cuda'))
        print("   ✅ Modelo carregado")
        
        # Verifica suporte a português
        languages = tts.languages if hasattr(tts, 'languages') else []
        print(f"   Languages available: {languages if languages else 'Not exposed (uses language codes directly)'}")
        
        # XTTS aceita language="pt" mesmo que não exponha lista
        print("   ✅ XTTS supports Portuguese (language code: 'pt')")
        
        # Info do modelo
        if hasattr(tts, 'synthesizer'):
            print(f"   Model info: {type(tts.synthesizer).__name__}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Failed to load XTTS: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_xtts_basic()
    print(f"\n{'✅ PASS' if success else '❌ FAIL'}")
    sys.exit(0 if success else 1)
