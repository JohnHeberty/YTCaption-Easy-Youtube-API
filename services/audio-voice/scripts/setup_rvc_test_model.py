#!/usr/bin/env python3
"""
Script para configurar modelo RVC de teste
Cria um modelo RVC básico para testar a funcionalidade de conversão de voz
"""
import os
import json
import shutil
from pathlib import Path

# Diretórios
BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = BASE_DIR / "models" / "rvc"
TEST_AUDIO = BASE_DIR / "tests" / "Teste.ogg"

def setup_test_model():
    """Configura modelo RVC de teste"""
    print("="*80)
    print("🎯 CONFIGURANDO MODELO RVC DE TESTE")
    print("="*80)
    
    # Criar diretório de modelos
    model_dir = MODELS_DIR / "test-voice"
    model_dir.mkdir(parents=True, exist_ok=True)
    
    # Copiar áudio de teste como referência
    if TEST_AUDIO.exists():
        ref_audio = model_dir / "reference.ogg"
        shutil.copy(TEST_AUDIO, ref_audio)
        print(f"\n✅ Áudio de referência copiado: {ref_audio}")
    else:
        print(f"\n❌ Arquivo de teste não encontrado: {TEST_AUDIO}")
        return
    
    # Criar arquivo de metadados do modelo
    metadata = {
        "id": "test-voice-v1",
        "name": "Test Voice RVC Model",
        "description": "Modelo RVC de teste baseado em Teste.ogg",
        "version": "1.0",
        "language": "pt-BR",
        "sample_rate": 48000,
        "f0_method": "rmvpe",
        "created_at": "2025-11-27",
        "model_file": "test_voice.pth",
        "index_file": "test_voice.index",
        "config": {
            "pitch": 0,
            "index_rate": 0.75,
            "filter_radius": 3,
            "rms_mix_rate": 0.25,
            "protect": 0.33
        }
    }
    
    metadata_file = model_dir / "metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Metadados criados: {metadata_file}")
    
    # Criar placeholder para arquivos do modelo (RVC precisa treinar)
    # Para teste, vamos criar arquivos vazios
    model_file = model_dir / "test_voice.pth"
    index_file = model_dir / "test_voice.index"
    
    # Nota: Estes são placeholders. Para RVC real, você precisa treinar o modelo
    model_file.touch()
    index_file.touch()
    
    print(f"⚠️  Placeholders criados (modelo precisa ser treinado):")
    print(f"   - {model_file}")
    print(f"   - {index_file}")
    
    print("\n" + "="*80)
    print("✅ MODELO RVC DE TESTE CONFIGURADO")
    print("="*80)
    print(f"\n📂 Diretório: {model_dir}")
    print(f"🆔 Model ID: {metadata['id']}")
    print(f"\n⚠️  IMPORTANTE:")
    print("   Para usar RVC de verdade, você precisa:")
    print("   1. Treinar o modelo com o RVC-WebUI")
    print("   2. Copiar os arquivos .pth e .index treinados")
    print("   3. Atualizar metadata.json com as configurações corretas")
    print("\n   Por enquanto, use sem RVC (enable_rvc=False)")
    print("="*80)

if __name__ == "__main__":
    setup_test_model()
