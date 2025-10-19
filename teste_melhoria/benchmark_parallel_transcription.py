"""
Benchmark: Single-Core vs Multi-Core Whisper Transcription
Compara performance entre transcrição sequencial e paralela por chunks.
"""
import asyncio
import time
from pathlib import Path
import sys

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.infrastructure.whisper.transcription_service import WhisperTranscriptionService
from teste_melhoria.whisper_parallel_service import WhisperParallelTranscriptionService
from src.domain.entities import VideoFile


async def benchmark_single_core(video_file: VideoFile, model: str = "base"):
    """
    Benchmark: Transcrição single-core (método atual).
    """
    logger.info("=" * 60)
    logger.info("🔵 BENCHMARK: SINGLE-CORE TRANSCRIPTION")
    logger.info("=" * 60)
    
    service = WhisperTranscriptionService(
        model_name=model,
        device="cpu"
    )
    
    start_time = time.time()
    
    try:
        transcription = await service.transcribe(video_file, language="auto")
        
        elapsed_time = time.time() - start_time
        
        logger.info("✅ Single-core transcription completed!")
        logger.info(f"⏱️  Total time: {elapsed_time:.2f}s")
        logger.info(f"📝 Segments: {len(transcription.segments)}")
        logger.info(f"🌍 Language: {transcription.language}")
        
        return {
            'method': 'single-core',
            'time': elapsed_time,
            'segments': len(transcription.segments),
            'language': transcription.language,
            'transcription': transcription
        }
        
    except Exception as e:
        logger.error(f"❌ Single-core failed: {e}")
        return None


async def benchmark_multi_core(
    video_file: VideoFile,
    model: str = "base",
    num_workers: int = 4,
    chunk_duration: int = 120
):
    """
    Benchmark: Transcrição multi-core com chunks paralelos.
    """
    logger.info("=" * 60)
    logger.info("🟢 BENCHMARK: MULTI-CORE TRANSCRIPTION (PARALLEL CHUNKS)")
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
        
        logger.info("✅ Multi-core transcription completed!")
        logger.info(f"⏱️  Total time: {elapsed_time:.2f}s")
        logger.info(f"👷 Workers: {num_workers}")
        logger.info(f"📦 Chunk duration: {chunk_duration}s")
        logger.info(f"📝 Segments: {len(transcription.segments)}")
        logger.info(f"🌍 Language: {transcription.language}")
        
        return {
            'method': 'multi-core',
            'time': elapsed_time,
            'workers': num_workers,
            'chunk_duration': chunk_duration,
            'segments': len(transcription.segments),
            'language': transcription.language,
            'transcription': transcription
        }
        
    except Exception as e:
        logger.error(f"❌ Multi-core failed: {e}")
        return None


def compare_results(single_result, multi_result):
    """
    Compara resultados dos dois métodos.
    """
    logger.info("=" * 60)
    logger.info("📊 COMPARISON RESULTS")
    logger.info("=" * 60)
    
    if not single_result or not multi_result:
        logger.error("❌ Cannot compare - one or both methods failed")
        return
    
    # Tempos
    single_time = single_result['time']
    multi_time = multi_result['time']
    speedup = single_time / multi_time
    improvement_pct = ((single_time - multi_time) / single_time) * 100
    
    logger.info("\n⏱️  TIME COMPARISON:")
    logger.info(f"  Single-core: {single_time:.2f}s")
    logger.info(f"  Multi-core:  {multi_time:.2f}s ({multi_result['workers']} workers)")
    logger.info(f"  Speedup:     {speedup:.2f}x")
    logger.info(f"  Improvement: {improvement_pct:.1f}% faster")
    
    # Qualidade
    logger.info("\n📝 QUALITY COMPARISON:")
    logger.info(f"  Single-core segments: {single_result['segments']}")
    logger.info(f"  Multi-core segments:  {multi_result['segments']}")
    
    segment_diff = abs(single_result['segments'] - multi_result['segments'])
    segment_diff_pct = (segment_diff / single_result['segments']) * 100
    logger.info(f"  Difference:           {segment_diff} segments ({segment_diff_pct:.1f}%)")
    
    # Idioma
    logger.info("\n🌍 LANGUAGE DETECTION:")
    logger.info(f"  Single-core: {single_result['language']}")
    logger.info(f"  Multi-core:  {multi_result['language']}")
    logger.info(f"  Match:       {'✅ YES' if single_result['language'] == multi_result['language'] else '❌ NO'}")
    
    # Texto (primeiros 200 chars de cada)
    single_text = single_result['transcription'].get_full_text()[:200]
    multi_text = multi_result['transcription'].get_full_text()[:200]
    
    logger.info("\n📄 TEXT PREVIEW (first 200 chars):")
    logger.info(f"  Single: {single_text}...")
    logger.info(f"  Multi:  {multi_text}...")
    
    # Conclusão
    logger.info("\n" + "=" * 60)
    logger.info("🎯 CONCLUSION:")
    logger.info("=" * 60)
    
    if speedup > 1.5:
        logger.info(f"✅ Multi-core is SIGNIFICANTLY FASTER ({speedup:.2f}x speedup)")
        logger.info(f"   Recommended for production with {multi_result['workers']} workers")
    elif speedup > 1.1:
        logger.info(f"✅ Multi-core is FASTER ({speedup:.2f}x speedup)")
        logger.info(f"   Consider using for high-load scenarios")
    else:
        logger.info(f"⚠️  Multi-core has MINIMAL improvement ({speedup:.2f}x)")
        logger.info(f"   Overhead may be too high - single-core recommended")
    
    if segment_diff_pct > 10:
        logger.warning(f"⚠️  Quality difference is SIGNIFICANT ({segment_diff_pct:.1f}%)")
        logger.warning(f"   Review chunk boundaries and overlap strategies")
    else:
        logger.info(f"✅ Quality is COMPARABLE ({segment_diff_pct:.1f}% difference)")


async def main():
    """
    Executa benchmark completo.
    """
    logger.info("🚀 Starting Whisper Transcription Benchmark")
    logger.info("=" * 60)
    
    # Configuração
    VIDEO_PATH = Path("./temp/test_video.mp3")  # Ajustar para vídeo de teste
    MODEL = "base"
    NUM_WORKERS = 4  # Ajustar conforme CPUs disponíveis
    CHUNK_DURATION = 120  # 2 minutos por chunk
    
    # Verificar se arquivo existe
    if not VIDEO_PATH.exists():
        logger.error(f"❌ Test video not found: {VIDEO_PATH}")
        logger.info("📝 Please download a test video first:")
        logger.info("   Example: yt-dlp -o ./temp/test_video.mp4 'https://youtube.com/watch?v=...'")
        return
    
    # Criar VideoFile entity
    video_file = VideoFile(file_path=VIDEO_PATH)
    
    logger.info(f"📹 Test video: {VIDEO_PATH.name}")
    logger.info(f"📦 Video size: {video_file.file_size_mb:.2f} MB")
    logger.info(f"🤖 Model: {MODEL}")
    logger.info(f"👷 Workers: {NUM_WORKERS}")
    logger.info(f"⏱️  Chunk duration: {CHUNK_DURATION}s")
    logger.info("")
    
    # Benchmark 1: Single-core
    single_result = await benchmark_single_core(video_file, MODEL)
    
    logger.info("\n⏸️  Waiting 5 seconds before next test...\n")
    await asyncio.sleep(5)
    
    # Benchmark 2: Multi-core
    multi_result = await benchmark_multi_core(
        video_file,
        MODEL,
        NUM_WORKERS,
        CHUNK_DURATION
    )
    
    # Comparação
    compare_results(single_result, multi_result)
    
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
    
    # Executar benchmark
    asyncio.run(main())
