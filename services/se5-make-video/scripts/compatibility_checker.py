#!/usr/bin/env python3
"""
Script para verificar compatibilidade de vídeos (sem converter).
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
    """Verifica compatibilidade dos vídeos sem converter."""
    if len(sys.argv) < 2:
        print("❌ Uso: python scripts/compatibility_checker.py <diretório>")
        sys.exit(1)
    
    video_dir = Path(sys.argv[1])
    
    if not video_dir.exists():
        print(f"❌ Diretório não encontrado: {video_dir}")
        sys.exit(1)
    
    fixer = VideoCompatibilityFixer()
    videos = sorted(video_dir.glob("*.mp4"))
    
    if not videos:
        print("❌ Nenhum vídeo .mp4 encontrado")
        sys.exit(1)
    
    print(f"🔍 Verificando compatibilidade em: {video_dir}")
    print(f"📊 Analisando {len(videos)} vídeos...\n")
    
    specs = []
    for video in videos:
        spec = await fixer._detect_specs(video)
        specs.append((video.name, spec))
        
        aspect_ratio = spec.width / spec.height if spec.height > 0 else 0
        
        print(f"  {video.name}:")
        print(f"    Resolução: {spec.width}x{spec.height} ({aspect_ratio:.2f})")
        print(f"    FPS: {spec.fps}")
        print(f"    Codec: {spec.codec}")
        print()
    
    # Verificar incompatibilidades
    resolutions = set(s.resolution for _, s in specs)
    codecs = set(s.codec for _, s in specs)
    
    if len(resolutions) > 1:
        print("⚠️  INCOMPATÍVEL: Vídeos têm resoluções diferentes")
        print(f"    Resoluções encontradas: {', '.join(sorted(resolutions))}")
        sys.exit(1)
    
    if len(codecs) > 1:
        print("⚠️  INCOMPATÍVEL: Vídeos têm codecs diferentes")
        print(f"    Codecs encontrados: {', '.join(sorted(codecs))}")
        sys.exit(1)
    
    print("✅ COMPATÍVEL: Todos os vídeos têm mesma resolução e codec")


if __name__ == "__main__":
    asyncio.run(main())
