#!/usr/bin/env python3
"""
Script para baixar modelos TTS no RUNTIME (não no build!)
Execute APENAS no primeiro deploy via docker-compose ou kubernetes init container.

Uso:
    python scripts/download_models.py
"""

import os
import sys
from pathlib import Path

def setup_cache_dirs():
    """Configura diretórios de cache para modelos."""
    models_dir = Path("/app/models")
    
    cache_dirs = {
        "TRANSFORMERS_CACHE": models_dir / "transformers",
        "HF_HOME": models_dir / "huggingface",
        "COQUI_TTS_CACHE": models_dir / "coqui",
        "TORCH_HOME": models_dir / "torch",
    }
    
    for env_var, cache_path in cache_dirs.items():
        cache_path.mkdir(parents=True, exist_ok=True)
        os.environ[env_var] = str(cache_path)
        print(f"✓ {env_var} = {cache_path}")
    
    return cache_dirs

def download_coqui_xtts():
    """Baixa modelo XTTS v2 da Coqui TTS (~2 GB)."""
    print("\n[1/3] Baixando Coqui XTTS v2...")
    try:
        from TTS.api import TTS
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
        print("✓ Coqui XTTS v2 baixado com sucesso!")
        return True
    except Exception as e:
        print(f"✗ Erro ao baixar Coqui XTTS: {e}")
        return False

def download_f5tts_models():
    """Baixa modelos F5-TTS se necessário."""
    print("\n[2/3] Verificando F5-TTS...")
    try:
        # F5-TTS baixa modelos automaticamente na primeira inferência
        # Apenas verificamos se a biblioteca está instalada
        import f5_tts
        print("✓ F5-TTS disponível (modelos serão baixados sob demanda)")
        return True
    except ImportError:
        print("⚠ F5-TTS não instalado (OK se não for usar)")
        return True

def download_transformers_models():
    """Baixa modelos do Transformers se necessário."""
    print("\n[3/3] Verificando Transformers...")
    try:
        from transformers import AutoTokenizer
        # Baixa um tokenizer pequeno como teste
        AutoTokenizer.from_pretrained("bert-base-uncased")
        print("✓ Transformers configurado corretamente")
        return True
    except Exception as e:
        print(f"⚠ Transformers: {e}")
        return True  # Não é crítico

def main():
    """Executa download de todos os modelos."""
    print("=" * 60)
    print("  Download de Modelos TTS - Audio Voice Service")
    print("=" * 60)
    
    # Configura diretórios de cache
    cache_dirs = setup_cache_dirs()
    
    # Downloads
    results = []
    results.append(download_coqui_xtts())
    results.append(download_f5tts_models())
    results.append(download_transformers_models())
    
    # Resumo
    print("\n" + "=" * 60)
    if all(results):
        print("✓ Todos os modelos foram baixados com sucesso!")
        print("=" * 60)
        return 0
    else:
        print("⚠ Alguns modelos falharam (veja logs acima)")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
