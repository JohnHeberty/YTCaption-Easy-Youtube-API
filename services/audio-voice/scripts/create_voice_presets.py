"""Cria presets de voz para F5-TTS"""
from gtts import gTTS
from pathlib import Path
import sys

presets = {
    'female_generic': "Hello, this is a female voice preset.",
    'male_deep': "Hello, this is a male voice preset.",
    'female_pt': "Olá, esta é uma voz feminina em português.",
    'male_pt': "Olá, esta é uma voz masculina em português.",
}

def create_presets():
    """Cria arquivos de áudio para presets"""
    output_dir = Path("/app/voice_profiles/presets")
    output_dir.mkdir(exist_ok=True, parents=True)
    
    print("="*60)
    print("Creating Voice Presets")
    print("="*60)
    
    for name, text in presets.items():
        try:
            lang = 'pt' if '_pt' in name else 'en'
            output = output_dir / f"{name}.mp3"
            
            tts = gTTS(text, lang=lang)
            tts.save(str(output))
            
            print(f"✅ Created: {output}")
            
        except Exception as e:
            print(f"❌ Failed to create {name}: {e}")
    
    print("="*60)
    print(f"Presets saved to: {output_dir}")
    print("="*60)

if __name__ == "__main__":
    try:
        create_presets()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
