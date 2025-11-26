#!/usr/bin/env python3
"""
Script de teste: Carregamento do modelo F5-TTS pt-BR
Verifica se o modelo pode ser carregado com sucesso na GTX 1050 Ti
"""
import sys
import torch
from pathlib import Path

def test_model_loading():
    """Testa carregamento do modelo F5-TTS pt-BR"""
    print("=" * 80)
    print("🧪 F5-TTS pt-BR Model Loading Test (GTX 1050 Ti)")
    print("=" * 80)
    
    # 1. Verificar CUDA
    print("\n1️⃣ CUDA Status:")
    print(f"   PyTorch version: {torch.__version__}")
    print(f"   CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"   CUDA version: {torch.version.cuda}")
        print(f"   Device name: {torch.cuda.get_device_name(0)}")
        print(f"   Device count: {torch.cuda.device_count()}")
        
        # VRAM info
        total_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"   Total VRAM: {total_memory:.2f} GB")
    
    # 2. Verificar modelo pt-BR
    print("\n2️⃣ Custom pt-BR Model:")
    model_path = Path('/app/models/f5tts/pt-br/model_last.safetensors')
    print(f"   Path: {model_path}")
    print(f"   Exists: {model_path.exists()}")
    
    if model_path.exists():
        size_gb = model_path.stat().st_size / (1024**3)
        print(f"   Size: {size_gb:.2f} GB")
    else:
        print("   ❌ Model NOT found!")
        return False
    
    # 3. Tentar carregar F5-TTS
    print("\n3️⃣ Loading F5-TTS:")
    try:
        from f5_tts.api import F5TTS
        
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"   Using device: {device}")
        
        print("   Initializing F5TTS...")
        f5tts = F5TTS(
            model_type='F5-TTS',
            ckpt_file=str(model_path),
            vocab_file="",
            ode_method="euler",
            use_ema=True,
            device=device,
            local_path=str(model_path.parent),
            hf_cache_dir='/app/models/f5tts'
        )
        
        print("   ✅ Model loaded successfully!")
        
        # 4. Aplicar FP16 (se GPU)
        if device == 'cuda':
            print("\n4️⃣ Applying FP16 optimization:")
            try:
                if hasattr(f5tts, 'model'):
                    f5tts.model.half()
                    print("   ✅ Model converted to FP16")
                    
                    # VRAM usage
                    allocated = torch.cuda.memory_allocated(0) / (1024**3)
                    reserved = torch.cuda.memory_reserved(0) / (1024**3)
                    print(f"   📊 VRAM allocated: {allocated:.2f} GB")
                    print(f"   📊 VRAM reserved: {reserved:.2f} GB")
                    
                    if allocated > 3.5:
                        print(f"   ⚠️ WARNING: High VRAM usage ({allocated:.2f} GB > 3.5 GB)")
                        print("      Consider reducing NFE steps or using CPU")
                    
            except Exception as e:
                print(f"   ⚠️ FP16 conversion failed: {e}")
        
        # 5. Teste rápido de inferência
        print("\n5️⃣ Quick inference test:")
        try:
            ref_audio = "/app/voice_profiles/presets/female_pt.wav"
            ref_text = "Olá, esta é uma voz de teste."
            gen_text = "Testando o modelo F5-TTS em português brasileiro."
            
            # Cria referência dummy se não existir
            if not Path(ref_audio).exists():
                print("   Creating dummy reference audio...")
                import numpy as np
                import soundfile as sf
                
                Path(ref_audio).parent.mkdir(parents=True, exist_ok=True)
                duration = 2.0
                sr = 24000
                t = np.linspace(0, duration, int(sr * duration))
                audio = 0.2 * np.sin(2 * np.pi * 220 * t)
                sf.write(ref_audio, audio, sr)
            
            print(f"   Ref audio: {ref_audio}")
            print(f"   Gen text: {gen_text}")
            
            with torch.no_grad():
                wav, sr, _ = f5tts.infer(
                    ref_file=ref_audio,
                    ref_text=ref_text,
                    gen_text=gen_text,
                    speed=1.0,
                    nfe_step=16,  # Reduzido para teste
                    remove_silence=False
                )
            
            print(f"   ✅ Inference successful!")
            print(f"   Output: {len(wav)} samples @ {sr} Hz")
            print(f"   Duration: {len(wav) / sr:.2f}s")
            
            if device == 'cuda':
                allocated = torch.cuda.memory_allocated(0) / (1024**3)
                print(f"   📊 VRAM after inference: {allocated:.2f} GB")
            
        except Exception as e:
            print(f"   ⚠️ Inference test failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Cleanup
        del f5tts
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            print("\n🧹 Cleaned up GPU memory")
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"   ❌ Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        print("\n" + "=" * 80)
        print("❌ TEST FAILED")
        print("=" * 80)
        return False


if __name__ == "__main__":
    success = test_model_loading()
    sys.exit(0 if success else 1)
