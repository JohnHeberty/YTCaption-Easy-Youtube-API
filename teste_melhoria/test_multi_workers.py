"""
Teste Rápido: Comparação de múltiplas configurações de workers.
Testa: 1 worker (single), 2 workers, 4 workers, 8 workers.
"""
import asyncio
import time
from pathlib import Path
import sys
import os

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from teste_melhoria.whisper_parallel_service import WhisperParallelTranscriptionService
from src.domain.entities import VideoFile


async def test_configuration(
    video_file: VideoFile,
    num_workers: int,
    model: str = "base",
    chunk_duration: int = 120
):
    """
    Testa uma configuração específica de workers.
    """
    logger.info("=" * 60)
    logger.info(f"🧪 TESTING: {num_workers} WORKERS")
    logger.info("=" * 60)
    
    service = WhisperParallelTranscriptionService(
        model_name=model,
        device="cpu",
        num_workers=num_workers,
        chunk_duration_seconds=chunk_duration
    )
    
    start_time = time.time()
    
    try:
        transcription = await service.transcribe(video_file, language="auto")
        elapsed_time = time.time() - start_time
        
        logger.info(f"✅ Completed in {elapsed_time:.2f}s")
        logger.info(f"📝 Segments: {len(transcription.segments)}")
        logger.info(f"🌍 Language: {transcription.language}")
        
        return {
            'workers': num_workers,
            'time': elapsed_time,
            'segments': len(transcription.segments),
            'language': transcription.language
        }
        
    except Exception as e:
        logger.error(f"❌ Failed with {num_workers} workers: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


async def main():
    """
    Executa testes com diferentes números de workers.
    """
    logger.info("🚀 Multi-Worker Benchmark")
    logger.info("=" * 60)
    
    # Configuração
    VIDEO_PATH = Path("./temp/test_video.wav")
    MODEL = "base"
    CHUNK_DURATION = 120
    
    # Detectar CPU cores
    cpu_cores = os.cpu_count() or 4
    logger.info(f"💻 CPU Cores: {cpu_cores}")
    
    # Verificar arquivo
    if not VIDEO_PATH.exists():
        logger.error(f"❌ Test video not found: {VIDEO_PATH}")
        logger.info("📝 Download test video first:")
        logger.info("   python teste_melhoria/download_test_video.py")
        return
    
    video_file = VideoFile(file_path=VIDEO_PATH)
    logger.info(f"📹 Video: {VIDEO_PATH.name} ({video_file.file_size_mb:.2f} MB)")
    logger.info(f"🤖 Model: {MODEL}")
    logger.info(f"⏱️  Chunk: {CHUNK_DURATION}s")
    logger.info("")
    
    # Configurações para testar
    worker_configs = [1, 2, 4, min(8, cpu_cores)]
    results = []
    
    # Executar testes
    for num_workers in worker_configs:
        result = await test_configuration(
            video_file,
            num_workers,
            MODEL,
            CHUNK_DURATION
        )
        
        if result:
            results.append(result)
        
        # Pausa entre testes
        if num_workers != worker_configs[-1]:
            logger.info("\n⏸️  Waiting 3 seconds...\n")
            await asyncio.sleep(3)
    
    # Mostrar comparação
    logger.info("\n" + "=" * 60)
    logger.info("📊 RESULTS COMPARISON")
    logger.info("=" * 60)
    
    if not results:
        logger.error("❌ No results to compare")
        return
    
    # Tabela de resultados
    logger.info("\n┌────────────┬────────────┬──────────────┬────────────┐")
    logger.info("│   Workers  │    Time    │   Speedup    │  Segments  │")
    logger.info("├────────────┼────────────┼──────────────┼────────────┤")
    
    baseline_time = results[0]['time']
    
    for r in results:
        speedup = baseline_time / r['time']
        logger.info(
            f"│ {r['workers']:^10} │ {r['time']:>8.2f}s │ {speedup:>10.2f}x │ {r['segments']:>10} │"
        )
    
    logger.info("└────────────┴────────────┴──────────────┴────────────┘")
    
    # Melhor configuração
    best = min(results, key=lambda x: x['time'])
    logger.info(f"\n🏆 BEST CONFIGURATION: {best['workers']} workers")
    logger.info(f"   Time: {best['time']:.2f}s")
    logger.info(f"   Speedup: {baseline_time / best['time']:.2f}x vs single worker")
    
    # Eficiência
    logger.info("\n📈 EFFICIENCY ANALYSIS:")
    for r in results:
        speedup = baseline_time / r['time']
        efficiency = (speedup / r['workers']) * 100 if r['workers'] > 1 else 100
        logger.info(
            f"   {r['workers']} workers: {efficiency:.1f}% efficient "
            f"({speedup:.2f}x speedup / {r['workers']} workers)"
        )
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ Benchmark completed!")
    logger.info("=" * 60)


if __name__ == "__main__":
    # Configurar logger
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # Executar
    asyncio.run(main())
