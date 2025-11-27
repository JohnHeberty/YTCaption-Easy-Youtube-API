#!/usr/bin/env python3
"""
Test script for high-fidelity voice cloning with RVC
Tests voice cloning using Teste.ogg with XTTS + RVC
"""
import os
import sys
import asyncio
import soundfile as sf
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import get_settings
from app.engines.factory import EngineFactory
from app.models import VoiceProfile, QualityProfile, RvcModel, RvcParameters
from datetime import datetime, timedelta
from uuid import uuid4

# Load config
config = get_settings()

async def test_voice_cloning():
    """Test voice cloning with highest fidelity"""
    
    print("=" * 80)
    print("🎤 HIGH-FIDELITY VOICE CLONING TEST WITH RVC")
    print("=" * 80)
    
    # Test audio path
    test_audio = Path("tests/Teste.ogg")
    
    if not test_audio.exists():
        print(f"❌ Test audio not found: {test_audio}")
        return
    
    print(f"✅ Test audio found: {test_audio}")
    print(f"   Size: {test_audio.stat().st_size / 1024:.2f} KB\n")
    
    # Load audio info
    data, sr = sf.read(str(test_audio))
    duration = len(data) / sr
    print(f"📊 Audio Info:")
    print(f"   Duration: {duration:.2f}s")
    print(f"   Sample Rate: {sr} Hz")
    print(f"   Channels: {1 if len(data.shape) == 1 else data.shape[1]}\n")
    
    # Initialize XTTS engine
    print("🔧 Initializing XTTS engine...")
    factory = EngineFactory()
    engine = factory.get_engine('xtts')
    print(f"✅ Engine loaded: {engine.engine_name}")
    print(f"   Device: {engine.device}")
    print(f"   Sample Rate: {engine.sample_rate} Hz\n")
    
    # Create voice profile
    print("🎭 Creating voice profile from Teste.ogg...")
    voice_profile = await engine.clone_voice(
        audio_path=str(test_audio),
        language='pt-BR',
        voice_name='Teste_Voice_RVC',
        description='High-fidelity test voice with RVC enhancement'
    )
    print(f"✅ Voice profile created: {voice_profile.name}")
    print(f"   ID: {voice_profile.id}")
    print(f"   Language: {voice_profile.language}\n")
    
    # Test text for dubbing
    test_texts = [
        "Olá, este é um teste de clonagem de voz com alta fidelidade usando XTTS e RVC.",
        "A tecnologia de síntese de voz avançou muito nos últimos anos.",
        "Agora podemos criar vozes sintéticas que soam extremamente naturais e expressivas."
    ]
    
    # Configure RVC model (if available)
    rvc_model = None
    rvc_enabled = config.get('rvc_enabled', True)
    
    if rvc_enabled:
        # Create RVC model config
        model_path = Path(config.get('rvc_model_dir', './models/rvc/checkpoints'))
        
        # Check for available RVC models
        if model_path.exists():
            models = list(model_path.glob('*.pth'))
            if models:
                print(f"📁 Found {len(models)} RVC model(s)")
                for m in models:
                    print(f"   - {m.name}")
                print()
        
        # Configure RVC parameters for HIGH QUALITY
        rvc_params = RvcParameters(
            f0_method='rmvpe',  # Best pitch extraction
            f0_up_key=0,  # No pitch shift
            index_rate=0.75,  # High index influence for quality
            filter_radius=3,  # Median filter
            resample_sr=0,  # Auto
            rms_mix_rate=0.25,  # Low mix for natural sound
            protect_voiceless=0.33  # Protect consonants
        )
        
        print("🎛️  RVC Configuration:")
        print(f"   Enabled: {rvc_enabled}")
        print(f"   F0 Method: {rvc_params.f0_method} (highest quality)")
        print(f"   Index Rate: {rvc_params.index_rate}")
        print(f"   Protect Voiceless: {rvc_params.protect_voiceless}\n")
    else:
        print("⚠️  RVC disabled - using XTTS only\n")
        rvc_params = None
    
    # Test dubbing with different quality profiles
    quality_profiles = [
        QualityProfile.QUALITY,  # Highest quality
    ]
    
    results = []
    
    for i, text in enumerate(test_texts, 1):
        print(f"{'=' * 80}")
        print(f"🎙️  TEST {i}/{len(test_texts)}")
        print(f"{'=' * 80}")
        print(f"Text: {text}\n")
        
        for quality in quality_profiles:
            print(f"🎚️  Quality Profile: {quality.value}")
            
            try:
                # Generate audio
                print("   Generating audio...")
                start_time = datetime.now()
                
                audio_bytes, audio_duration = await engine.generate_dubbing(
                    text=text,
                    language='pt-BR',
                    voice_profile=voice_profile,
                    quality_profile=quality,
                    speed=1.0,
                    enable_rvc=rvc_enabled,
                    rvc_params=rvc_params
                )
                
                end_time = datetime.now()
                generation_time = (end_time - start_time).total_seconds()
                rtf = generation_time / audio_duration if audio_duration > 0 else 0
                
                # Save output
                output_dir = Path("temp/test_outputs")
                output_dir.mkdir(parents=True, exist_ok=True)
                
                output_file = output_dir / f"test_{i}_{quality.value}_rvc{rvc_enabled}.wav"
                
                with open(output_file, 'wb') as f:
                    f.write(audio_bytes)
                
                print(f"   ✅ Success!")
                print(f"   Duration: {audio_duration:.2f}s")
                print(f"   Generation Time: {generation_time:.2f}s")
                print(f"   RTF (Real-Time Factor): {rtf:.3f}x")
                print(f"   Output Size: {len(audio_bytes) / 1024:.2f} KB")
                print(f"   Saved: {output_file}\n")
                
                results.append({
                    'test': i,
                    'quality': quality.value,
                    'rvc': rvc_enabled,
                    'duration': audio_duration,
                    'gen_time': generation_time,
                    'rtf': rtf,
                    'file': output_file,
                    'success': True
                })
                
            except Exception as e:
                print(f"   ❌ Error: {e}\n")
                results.append({
                    'test': i,
                    'quality': quality.value,
                    'rvc': rvc_enabled,
                    'success': False,
                    'error': str(e)
                })
    
    # Summary
    print("=" * 80)
    print("📊 RESULTS SUMMARY")
    print("=" * 80)
    
    successful = [r for r in results if r.get('success')]
    failed = [r for r in results if not r.get('success')]
    
    print(f"✅ Successful: {len(successful)}/{len(results)}")
    print(f"❌ Failed: {len(failed)}/{len(results)}\n")
    
    if successful:
        avg_rtf = sum(r['rtf'] for r in successful) / len(successful)
        total_audio = sum(r['duration'] for r in successful)
        total_gen = sum(r['gen_time'] for r in successful)
        
        print(f"Average RTF: {avg_rtf:.3f}x")
        print(f"Total Audio Generated: {total_audio:.2f}s")
        print(f"Total Generation Time: {total_gen:.2f}s\n")
        
        print("Generated Files:")
        for r in successful:
            print(f"   📄 {r['file'].name}")
            print(f"      Quality: {r['quality']}, RVC: {r['rvc']}, RTF: {r['rtf']:.3f}x")
    
    if failed:
        print("\n❌ Failed Tests:")
        for r in failed:
            print(f"   Test {r['test']}, Quality: {r['quality']}")
            print(f"   Error: {r.get('error', 'Unknown')}")
    
    print("\n" + "=" * 80)
    print("✅ TEST COMPLETE!")
    print("=" * 80)
    
    return results

if __name__ == "__main__":
    try:
        # Run async test
        results = asyncio.run(test_voice_cloning())
        
        # Exit code based on results
        if results and any(r.get('success') for r in results):
            sys.exit(0)
        else:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(2)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
