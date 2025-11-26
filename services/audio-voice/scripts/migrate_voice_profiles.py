"""Migra VoiceProfiles de OpenVoice (.pkl) para F5-TTS (.wav)"""
import os
import pickle
import shutil
from pathlib import Path
import sys

# Adiciona app ao path
sys.path.insert(0, '/app')

from app.redis_store import RedisJobStore
from app.f5tts_client import F5TTSClient
from app.config import get_settings

def migrate_profiles():
    """Migra perfis de voz existentes"""
    print("="*60)
    print("Voice Profile Migration: OpenVoice → F5-TTS")
    print("="*60)
    
    try:
        store = RedisJobStore()
        f5tts = F5TTSClient(device='cpu')
        
        profiles = store.get_all_voice_profiles()
        
        print(f"\nFound {len(profiles)} voice profiles")
        
        migrated = 0
        skipped = 0
        errors = 0
        
        for profile in profiles:
            print(f"\n📝 Processing profile: {profile.id} ({profile.name})")
            
            # Já migrado?
            if profile.reference_audio_path:
                print("  ✅ Already migrated (has reference_audio_path)")
                skipped += 1
                continue
            
            # Áudio original existe?
            if profile.source_audio_path and Path(profile.source_audio_path).exists():
                original_audio = profile.source_audio_path
                print(f"  Using original: {original_audio}")
            else:
                print(f"  ⚠️  Original audio not found, skipping")
                print(f"     source_audio_path: {profile.source_audio_path}")
                skipped += 1
                continue
            
            try:
                # Copia para voice_profiles
                settings = get_settings()
                new_path = Path(settings['voice_profiles_dir']) / f"{profile.id}.wav"
                shutil.copy(original_audio, new_path)
                
                # Transcreve
                ref_text = f5tts._transcribe_audio(str(new_path), profile.language)
                
                # Atualiza profile
                profile.reference_audio_path = str(new_path)
                profile.reference_text = ref_text
                
                # Salva
                store.save_voice_profile(profile)
                
                print(f"  ✅ Migrated successfully")
                print(f"     New path: {new_path}")
                print(f"     Transcription: {ref_text}")
                migrated += 1
                
            except Exception as e:
                print(f"  ❌ Migration failed: {e}")
                errors += 1
        
        print("\n" + "="*60)
        print("MIGRATION SUMMARY")
        print("="*60)
        print(f"Total profiles: {len(profiles)}")
        print(f"Migrated: {migrated}")
        print(f"Skipped: {skipped}")
        print(f"Errors: {errors}")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Migration script failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(migrate_profiles())
