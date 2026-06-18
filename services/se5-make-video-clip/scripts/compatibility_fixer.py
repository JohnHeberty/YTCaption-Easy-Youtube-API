#!/usr/bin/env python3
"""
Script para executar compatibilização de vídeos via linha de comando.
"""
import asyncio
import sys
from pathlib import Path

# Adicionar app ao path - ajustar para localização correta
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from app.services.video_compatibility_fixer import VideoCompatibilityFixer


async def main():
    """Executa compatibilização de vídeos em um diretório."""
    if len(sys.argv) < 2:
        print("❌ Uso: python scripts/compatibility_fixer.py <diretório>")
        sys.exit(1)
    
    video_dir = Path(sys.argv[1])
    
    if not video_dir.exists():
        print(f"❌ Diretório não encontrado: {video_dir}")
        sys.exit(1)
    
    fixer = VideoCompatibilityFixer()
    
    print(f"🎬 Compatibilizando vídeos em: {video_dir}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    result = await fixer.reprocess_incompatible_videos(video_dir, pattern="*.mp4")
    
    print()
    print("✅ Compatibilização concluída:")
    print(f"   Processados:      {result['processed']}")
    print(f"   Convertidos:      {result['converted']}")
    print(f"   Já compatíveis:   {result['already_compatible']}")
    print(f"   Erros:            {result['errors']}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


if __name__ == "__main__":
    asyncio.run(main())
