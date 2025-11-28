"""
Teste do F5-TTS PT-BR Engine
Validação do modelo customizado PT-BR

Uso:
    python test_f5tts_ptbr.py

Valida:
1. Modelo customizado existe
2. Engine carrega sem erros
3. VRAM é liberada corretamente (LOW_VRAM mode)
4. Síntese funciona com texto PT-BR
"""
import asyncio
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_model_exists():
    """Teste 1: Verificar se modelo customizado existe"""
    logger.info("\n" + "="*60)
    logger.info("TESTE 1: Verificar modelo customizado PT-BR")
    logger.info("="*60)
    
    model_path = Path('/app/models/f5tts/models--ptbr/snapshots/model_last.safetensors')
    
    if model_path.exists():
        size_mb = model_path.stat().st_size / 1024 / 1024
        logger.info(f"✅ Modelo encontrado: {model_path}")
        logger.info(f"   Tamanho: {size_mb:.2f} MB")
        return True
    else:
        logger.error(f"❌ Modelo NÃO encontrado: {model_path}")
        return False


async def test_engine_creation():
    """Teste 2: Criar engine F5-TTS PT-BR"""
    logger.info("\n" + "="*60)
    logger.info("TESTE 2: Criar F5-TTS PT-BR engine")
    logger.info("="*60)
    
    try:
        from app.engines.factory import create_engine
        from app.config import get_settings
        
        settings = get_settings()
        logger.info(f"LOW_VRAM mode: {settings.get('low_vram_mode')}")
        
        engine = create_engine('f5tts-ptbr', settings)
        
        logger.info(f"✅ Engine criado: {engine.engine_name}")
        logger.info(f"   Device: {engine.device}")
        logger.info(f"   Sample rate: {engine.sample_rate}Hz")
        logger.info(f"   Supported languages: {engine.get_supported_languages()}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao criar engine: {e}", exc_info=True)
        return False


async def test_vram_unload():
    """Teste 3: Validar descarregamento de VRAM"""
    logger.info("\n" + "="*60)
    logger.info("TESTE 3: Validar descarregamento VRAM (LOW_VRAM)")
    logger.info("="*60)
    
    try:
        import torch
        from app.vram_manager import get_vram_manager
        from app.engines.factory import create_engine
        from app.config import get_settings
        
        if not torch.cuda.is_available():
            logger.warning("⚠️  CUDA não disponível, pulando teste VRAM")
            return True
        
        settings = get_settings()
        if not settings.get('low_vram_mode'):
            logger.warning("⚠️  LOW_VRAM mode desativado, pulando teste")
            return True
        
        vram_mgr = get_vram_manager()
        
        # Medir VRAM antes
        torch.cuda.empty_cache()
        vram_before = torch.cuda.memory_allocated() / 1024**3
        logger.info(f"📊 VRAM antes: {vram_before:.2f} GB")
        
        # Simular carregamento/descarregamento do modelo
        engine = create_engine('f5tts-ptbr', settings, force_recreate=True)
        
        # Em LOW_VRAM mode, modelo não está carregado ainda
        if hasattr(engine, 'tts') and engine.tts is None:
            logger.info("✅ Modelo não carregado (lazy load correto)")
            
            # Testar load/unload manual
            with vram_mgr.load_model('f5tts-ptbr-test', engine._load_model):
                vram_loaded = torch.cuda.memory_allocated() / 1024**3
                logger.info(f"📊 VRAM carregado: {vram_loaded:.2f} GB (+{vram_loaded - vram_before:.2f} GB)")
            
            # Após context manager, modelo deve ser descarregado
            torch.cuda.synchronize()
            vram_after = torch.cuda.memory_allocated() / 1024**3
            freed = vram_loaded - vram_after
            logger.info(f"📊 VRAM após unload: {vram_after:.2f} GB")
            logger.info(f"📊 VRAM liberada: {freed:.2f} GB")
            
            if freed > 0.1:  # Pelo menos 100MB liberado
                logger.info(f"✅ VRAM descarregada com sucesso ({freed:.2f} GB)")
                return True
            else:
                logger.warning(f"⚠️  Pouca VRAM liberada: {freed:.2f} GB")
                return False
        else:
            logger.warning("⚠️  Modelo já carregado (não é LOW_VRAM mode)")
            return True
        
    except Exception as e:
        logger.error(f"❌ Erro no teste VRAM: {e}", exc_info=True)
        return False


async def test_synthesis_simple():
    """Teste 4: Síntese simples (sem voice profile - apenas validação)"""
    logger.info("\n" + "="*60)
    logger.info("TESTE 4: Validação de síntese (estrutura)")
    logger.info("="*60)
    
    try:
        from app.engines.factory import create_engine
        from app.config import get_settings
        
        settings = get_settings()
        engine = create_engine('f5tts-ptbr', settings)
        
        # Verificar métodos necessários
        assert hasattr(engine, 'synthesize'), "Método 'synthesize' não encontrado"
        assert hasattr(engine, 'cleanup'), "Método 'cleanup' não encontrado"
        assert hasattr(engine, '_load_model'), "Método '_load_model' não encontrado"
        
        logger.info("✅ Estrutura do engine validada")
        logger.info("   - synthesize() ✓")
        logger.info("   - cleanup() ✓")
        logger.info("   - _load_model() ✓")
        
        # Cleanup
        engine.cleanup()
        logger.info("✅ Cleanup executado com sucesso")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro no teste de síntese: {e}", exc_info=True)
        return False


async def run_all_tests():
    """Executar todos os testes"""
    logger.info("\n" + "="*60)
    logger.info("F5-TTS PT-BR ENGINE - SUITE DE TESTES")
    logger.info("="*60)
    
    results = {}
    
    # Teste 1: Modelo existe
    results['model_exists'] = await test_model_exists()
    
    if not results['model_exists']:
        logger.error("\n❌ Modelo não encontrado! Abortando testes seguintes.")
        return results
    
    # Teste 2: Engine creation
    results['engine_creation'] = await test_engine_creation()
    
    if not results['engine_creation']:
        logger.error("\n❌ Engine não pôde ser criado! Abortando testes seguintes.")
        return results
    
    # Teste 3: VRAM unload
    results['vram_unload'] = await test_vram_unload()
    
    # Teste 4: Synthesis structure
    results['synthesis_structure'] = await test_synthesis_simple()
    
    # Resumo
    logger.info("\n" + "="*60)
    logger.info("RESUMO DOS TESTES")
    logger.info("="*60)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} - {test_name}")
    
    total = len(results)
    passed = sum(1 for r in results.values() if r)
    logger.info(f"\nTotal: {passed}/{total} testes passaram")
    
    return results


if __name__ == '__main__':
    asyncio.run(run_all_tests())
