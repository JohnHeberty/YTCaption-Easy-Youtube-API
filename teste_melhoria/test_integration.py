"""
Teste de integração: Transcrição Paralela vs Normal
Testa ambos os serviços com vídeo real e compara resultados.
"""
import asyncio
import time
import sys
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from src.domain.entities import VideoFile
from src.infrastructure.whisper.transcription_service import WhisperTranscriptionService
from src.infrastructure.whisper.parallel_transcription_service import WhisperParallelTranscriptionService


async def test_normal_transcription(video_path: Path, model: str = "base"):
    """
    Testa transcrição normal (single-threaded).
    """
    logger.info("=" * 70)
    logger.info("🔵 TEST 1: NORMAL TRANSCRIPTION (Single-Threaded)")
    logger.info("=" * 70)
    
    service = WhisperTranscriptionService(
        model_name=model,
        device="cpu"
    )
    
    video_file = VideoFile(file_path=video_path)
    
    start_time = time.time()
    
    try:
        transcription = await service.transcribe(video_file, language="auto")
        elapsed_time = time.time() - start_time
        
        logger.info("✅ Normal transcription completed!")
        logger.info(f"⏱️  Time: {elapsed_time:.2f}s")
        logger.info(f"📝 Segments: {len(transcription.segments)}")
        logger.info(f"🌍 Language: {transcription.language}")
        logger.info(f"📄 Text preview: {transcription.get_full_text()[:100]}...")
        
        return {
            'success': True,
            'method': 'normal',
            'time': elapsed_time,
            'segments': len(transcription.segments),
            'language': transcription.language,
            'text_preview': transcription.get_full_text()[:200],
            'transcription': transcription
        }
        
    except Exception as e:
        logger.error(f"❌ Normal transcription failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {'success': False, 'error': str(e)}


async def test_parallel_transcription(
    video_path: Path,
    model: str = "base",
    num_workers: int = 4,
    chunk_duration: int = 120
):
    """
    Testa transcrição paralela (multi-process).
    """
    logger.info("=" * 70)
    logger.info("🟢 TEST 2: PARALLEL TRANSCRIPTION (Multi-Process)")
    logger.info("=" * 70)
    
    service = WhisperParallelTranscriptionService(
        model_name=model,
        device="cpu",
        num_workers=num_workers,
        chunk_duration_seconds=chunk_duration
    )
    
    video_file = VideoFile(file_path=video_path)
    
    start_time = time.time()
    
    try:
        transcription = await service.transcribe(video_file, language="auto")
        elapsed_time = time.time() - start_time
        
        logger.info("✅ Parallel transcription completed!")
        logger.info(f"⏱️  Time: {elapsed_time:.2f}s")
        logger.info(f"👷 Workers: {num_workers}")
        logger.info(f"📦 Chunk duration: {chunk_duration}s")
        logger.info(f"📝 Segments: {len(transcription.segments)}")
        logger.info(f"🌍 Language: {transcription.language}")
        logger.info(f"📄 Text preview: {transcription.get_full_text()[:100]}...")
        
        return {
            'success': True,
            'method': 'parallel',
            'time': elapsed_time,
            'workers': num_workers,
            'chunk_duration': chunk_duration,
            'segments': len(transcription.segments),
            'language': transcription.language,
            'text_preview': transcription.get_full_text()[:200],
            'transcription': transcription
        }
        
    except Exception as e:
        logger.error(f"❌ Parallel transcription failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {'success': False, 'error': str(e)}


def compare_results(normal_result: dict, parallel_result: dict):
    """
    Compara resultados dos dois métodos.
    """
    logger.info("\n" + "=" * 70)
    logger.info("📊 COMPARISON RESULTS")
    logger.info("=" * 70)
    
    if not normal_result.get('success') or not parallel_result.get('success'):
        logger.error("❌ Cannot compare - one or both tests failed")
        if not normal_result.get('success'):
            logger.error(f"   Normal error: {normal_result.get('error')}")
        if not parallel_result.get('success'):
            logger.error(f"   Parallel error: {parallel_result.get('error')}")
        return
    
    # Tempos
    normal_time = normal_result['time']
    parallel_time = parallel_result['time']
    speedup = normal_time / parallel_time
    improvement_pct = ((normal_time - parallel_time) / normal_time) * 100
    
    logger.info("\n⏱️  TIME COMPARISON:")
    logger.info(f"  Normal:   {normal_time:.2f}s")
    logger.info(f"  Parallel: {parallel_time:.2f}s ({parallel_result['workers']} workers)")
    logger.info(f"  Speedup:  {speedup:.2f}x")
    
    if speedup > 1:
        logger.info(f"  ✅ Parallel is {improvement_pct:.1f}% FASTER")
    else:
        logger.warning(f"  ⚠️  Parallel is {abs(improvement_pct):.1f}% SLOWER")
    
    # Qualidade
    logger.info("\n📝 QUALITY COMPARISON:")
    logger.info(f"  Normal segments:   {normal_result['segments']}")
    logger.info(f"  Parallel segments: {parallel_result['segments']}")
    
    segment_diff = abs(normal_result['segments'] - parallel_result['segments'])
    if normal_result['segments'] > 0:
        segment_diff_pct = (segment_diff / normal_result['segments']) * 100
    else:
        segment_diff_pct = 0
    
    logger.info(f"  Difference: {segment_diff} segments ({segment_diff_pct:.1f}%)")
    
    if segment_diff_pct < 5:
        logger.info("  ✅ Quality is COMPARABLE")
    elif segment_diff_pct < 10:
        logger.warning("  ⚠️  Quality has SMALL difference")
    else:
        logger.warning("  ⚠️  Quality has SIGNIFICANT difference")
    
    # Idioma
    logger.info("\n🌍 LANGUAGE DETECTION:")
    logger.info(f"  Normal:   {normal_result['language']}")
    logger.info(f"  Parallel: {parallel_result['language']}")
    
    if normal_result['language'] == parallel_result['language']:
        logger.info("  ✅ Languages MATCH")
    else:
        logger.warning("  ⚠️  Languages DIFFER")
    
    # Texto
    logger.info("\n📄 TEXT COMPARISON (first 200 chars):")
    logger.info(f"  Normal:   {normal_result['text_preview']}")
    logger.info(f"  Parallel: {parallel_result['text_preview']}")
    
    # Conclusão
    logger.info("\n" + "=" * 70)
    logger.info("🎯 CONCLUSION:")
    logger.info("=" * 70)
    
    if speedup >= 2.0 and segment_diff_pct < 10:
        logger.info(f"✅ EXCELLENT: Parallel is {speedup:.2f}x faster with good quality")
        logger.info(f"   Recommended for production with {parallel_result['workers']} workers")
    elif speedup >= 1.5 and segment_diff_pct < 10:
        logger.info(f"✅ GOOD: Parallel is {speedup:.2f}x faster with acceptable quality")
        logger.info(f"   Consider enabling for high-load scenarios")
    elif speedup > 1.0:
        logger.warning(f"⚠️  MARGINAL: Only {speedup:.2f}x faster")
        logger.warning(f"   Overhead may be too high - evaluate use case")
    else:
        logger.warning(f"❌ NOT RECOMMENDED: Parallel is slower ({speedup:.2f}x)")
        logger.warning(f"   Stick with normal transcription")


async def main():
    """
    Executa teste completo de integração.
    """
    logger.info("🚀 INTEGRATION TEST: Normal vs Parallel Transcription")
    logger.info("=" * 70)
    
    # Configuração
    VIDEO_PATH = Path("./temp/test_video.wav")
    MODEL = "base"
    NUM_WORKERS = 4
    CHUNK_DURATION = 120
    
    # Verificar se arquivo existe
    if not VIDEO_PATH.exists():
        logger.error(f"❌ Test video not found: {VIDEO_PATH}")
        logger.info("📝 Create test audio first:")
        logger.info("   python teste_melhoria/create_synthetic_audio.py")
        return
    
    logger.info(f"📹 Test video: {VIDEO_PATH.name}")
    logger.info(f"📦 Size: {VIDEO_PATH.stat().st_size / (1024*1024):.2f} MB")
    logger.info(f"🤖 Model: {MODEL}")
    logger.info(f"👷 Parallel workers: {NUM_WORKERS}")
    logger.info(f"⏱️  Chunk duration: {CHUNK_DURATION}s")
    logger.info("")
    
    # Teste 1: Normal
    normal_result = await test_normal_transcription(VIDEO_PATH, MODEL)
    
    logger.info("\n⏸️  Waiting 5 seconds before next test...\n")
    await asyncio.sleep(5)
    
    # Teste 2: Parallel
    parallel_result = await test_parallel_transcription(
        VIDEO_PATH,
        MODEL,
        NUM_WORKERS,
        CHUNK_DURATION
    )
    
    # Comparação
    compare_results(normal_result, parallel_result)
    
    logger.info("\n" + "=" * 70)
    logger.info("✅ Integration test completed!")
    logger.info("=" * 70)


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
