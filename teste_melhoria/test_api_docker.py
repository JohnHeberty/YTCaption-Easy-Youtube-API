"""
Teste da API com transcrição paralela via Docker.
Testa endpoint /transcribe com configuração paralela.
"""
import requests
import time
from loguru import logger
import sys


def test_api_transcription(base_url: str, youtube_url: str, use_parallel: bool = False):
    """
    Testa endpoint de transcrição da API.
    
    Args:
        base_url: URL base da API (ex: http://localhost:8000)
        youtube_url: URL do vídeo do YouTube
        use_parallel: Se True, testa com transcrição paralela
    """
    endpoint = f"{base_url}/api/v1/transcribe"
    
    mode = "PARALLEL" if use_parallel else "NORMAL"
    logger.info("=" * 70)
    logger.info(f"🧪 Testing API Transcription ({mode} mode)")
    logger.info("=" * 70)
    logger.info(f"📡 Endpoint: {endpoint}")
    logger.info(f"🔗 YouTube URL: {youtube_url}")
    logger.info(f"🚀 Parallel: {use_parallel}")
    logger.info("")
    
    # Payload
    payload = {
        "youtube_url": youtube_url,
        "language": "auto",
        "response_format": "json"
    }
    
    # Request
    logger.info("📤 Sending request...")
    start_time = time.time()
    
    try:
        response = requests.post(endpoint, json=payload, timeout=600)
        elapsed_time = time.time() - start_time
        
        logger.info(f"📥 Response received in {elapsed_time:.2f}s")
        logger.info(f"📊 Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            logger.info("✅ Transcription successful!")
            logger.info(f"⏱️  Total time: {elapsed_time:.2f}s")
            logger.info(f"🌍 Language: {data.get('language', 'unknown')}")
            logger.info(f"📝 Segments: {len(data.get('segments', []))}")
            
            # Preview do texto
            text = data.get('text', '')
            if text:
                logger.info(f"📄 Text preview (first 200 chars):")
                logger.info(f"   {text[:200]}...")
            
            return {
                'success': True,
                'time': elapsed_time,
                'data': data,
                'mode': mode
            }
        else:
            logger.error(f"❌ Request failed: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return {
                'success': False,
                'error': f"HTTP {response.status_code}",
                'mode': mode
            }
            
    except requests.exceptions.Timeout:
        logger.error("❌ Request timeout (>600s)")
        return {
            'success': False,
            'error': 'Timeout',
            'mode': mode
        }
    except Exception as e:
        logger.error(f"❌ Request failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'mode': mode
        }


def compare_api_results(normal_result: dict, parallel_result: dict):
    """
    Compara resultados dos dois modos da API.
    """
    logger.info("\n" + "=" * 70)
    logger.info("📊 API COMPARISON RESULTS")
    logger.info("=" * 70)
    
    if not normal_result.get('success') or not parallel_result.get('success'):
        logger.error("❌ Cannot compare - one or both tests failed")
        return
    
    normal_time = normal_result['time']
    parallel_time = parallel_result['time']
    speedup = normal_time / parallel_time
    
    logger.info(f"\n⏱️  TIME COMPARISON:")
    logger.info(f"  Normal mode:   {normal_time:.2f}s")
    logger.info(f"  Parallel mode: {parallel_time:.2f}s")
    logger.info(f"  Speedup:       {speedup:.2f}x")
    
    if speedup > 1:
        improvement = ((normal_time - parallel_time) / normal_time) * 100
        logger.info(f"  ✅ Parallel is {improvement:.1f}% FASTER")
    else:
        degradation = ((parallel_time - normal_time) / normal_time) * 100
        logger.warning(f"  ⚠️  Parallel is {degradation:.1f}% SLOWER")
    
    # Comparar dados
    normal_data = normal_result.get('data', {})
    parallel_data = parallel_result.get('data', {})
    
    normal_segments = len(normal_data.get('segments', []))
    parallel_segments = len(parallel_data.get('segments', []))
    
    logger.info(f"\n📝 QUALITY:")
    logger.info(f"  Normal segments:   {normal_segments}")
    logger.info(f"  Parallel segments: {parallel_segments}")
    logger.info(f"  Difference:        {abs(normal_segments - parallel_segments)}")
    
    logger.info(f"\n🌍 LANGUAGE:")
    logger.info(f"  Normal:   {normal_data.get('language', 'unknown')}")
    logger.info(f"  Parallel: {parallel_data.get('language', 'unknown')}")


def main():
    """
    Executa testes da API.
    """
    logger.info("🚀 API DOCKER TEST: Normal vs Parallel Transcription")
    logger.info("=" * 70)
    
    # Configuração
    BASE_URL = "http://localhost:8000"
    
    # URL de vídeo curto para teste (ajustar conforme necessário)
    # Usar vídeo de ~2-5 minutos para teste rápido
    YOUTUBE_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # 19 segundos
    
    logger.info(f"📡 API URL: {BASE_URL}")
    logger.info(f"🔗 Test video: {YOUTUBE_URL}")
    logger.info("")
    
    # Verificar se API está online
    try:
        health_response = requests.get(f"{BASE_URL}/health", timeout=5)
        if health_response.status_code == 200:
            logger.info("✅ API is online")
        else:
            logger.error("❌ API is not responding correctly")
            return
    except Exception as e:
        logger.error(f"❌ Cannot connect to API: {e}")
        logger.info("💡 Make sure Docker container is running:")
        logger.info("   docker-compose up -d")
        return
    
    logger.info("")
    
    # Teste 1: Modo normal
    logger.info("📝 NOTE: First test uses NORMAL transcription (ENABLE_PARALLEL_TRANSCRIPTION=false)")
    logger.info("         Change in .env and restart container to test parallel mode")
    logger.info("")
    
    result = test_api_transcription(BASE_URL, YOUTUBE_URL, use_parallel=False)
    
    if result['success']:
        logger.info("\n✅ API test completed successfully!")
        logger.info(f"⏱️  Total time: {result['time']:.2f}s")
    else:
        logger.error("\n❌ API test failed!")
    
    logger.info("\n" + "=" * 70)
    logger.info("📝 TO TEST PARALLEL MODE:")
    logger.info("=" * 70)
    logger.info("1. Edit .env file:")
    logger.info("   ENABLE_PARALLEL_TRANSCRIPTION=true")
    logger.info("   PARALLEL_WORKERS=4")
    logger.info("   PARALLEL_CHUNK_DURATION=120")
    logger.info("")
    logger.info("2. Restart Docker container:")
    logger.info("   docker-compose restart")
    logger.info("")
    logger.info("3. Run this test again")
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
    main()
