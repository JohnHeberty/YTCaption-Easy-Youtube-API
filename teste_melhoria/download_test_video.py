"""
Script auxiliar para baixar vídeo de teste do YouTube.
"""
import subprocess
from pathlib import Path
from loguru import logger
import sys


def download_test_video(url: str, output_path: Path, max_duration: int = 600):
    """
    Baixa vídeo de teste do YouTube.
    
    Args:
        url: URL do YouTube
        output_path: Caminho de saída
        max_duration: Duração máxima em segundos (padrão: 10 minutos)
    """
    logger.info(f"📥 Downloading test video from YouTube...")
    logger.info(f"🔗 URL: {url}")
    logger.info(f"📁 Output: {output_path}")
    logger.info(f"⏱️  Max duration: {max_duration}s ({max_duration // 60} minutes)")
    
    # Criar diretório se não existir
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Comando yt-dlp
    cmd = [
        "yt-dlp",
        "-f", "bestaudio[ext=m4a]/best",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", str(output_path),
        url
    ]
    
    try:
        logger.info("🚀 Starting download...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info("✅ Download completed successfully!")
        
        # Verificar arquivo
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"📦 File size: {size_mb:.2f} MB")
            logger.info(f"📂 Location: {output_path}")
        else:
            logger.error("❌ File not found after download")
            
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Download failed: {e}")
        logger.error(f"Error output: {e.stderr}")
        raise
    except FileNotFoundError:
        logger.error("❌ yt-dlp not found!")
        logger.info("Install yt-dlp first:")
        logger.info("  pip install yt-dlp")
        raise


if __name__ == "__main__":
    # Configurar logger
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # URL de exemplo (5 minutos de vídeo)
    # Substituir por URL desejada
    TEST_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo" - primeiro vídeo do YouTube
    OUTPUT_PATH = Path("./temp/test_video.mp3")
    
    logger.info("=" * 60)
    logger.info("🎬 TEST VIDEO DOWNLOADER")
    logger.info("=" * 60)
    
    if len(sys.argv) > 1:
        TEST_URL = sys.argv[1]
        logger.info(f"📝 Using URL from argument: {TEST_URL}")
    else:
        logger.info(f"📝 Using default URL: {TEST_URL}")
        logger.info("💡 Tip: Pass YouTube URL as argument:")
        logger.info(f"   python {Path(__file__).name} 'YOUR_YOUTUBE_URL'")
    
    print()
    
    try:
        download_test_video(TEST_URL, OUTPUT_PATH)
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ Ready for benchmark!")
        logger.info("=" * 60)
        logger.info("Next step: Run benchmark script")
        logger.info("  python teste_melhoria/benchmark_parallel_transcription.py")
        
    except Exception as e:
        logger.error(f"\n❌ Failed: {e}")
        sys.exit(1)
