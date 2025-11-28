"""
CUDA Availability Check Module

Executa no startup para validar disponibilidade de GPU e logar informações.
Ajuda a diagnosticar problemas de CUDA/GPU antes do carregamento dos modelos.

Uso:
    from app.cuda_check import check_cuda
    
    # No startup
    check_cuda()
"""
import logging
import os

logger = logging.getLogger(__name__)


def check_cuda() -> bool:
    """
    Verifica disponibilidade de CUDA e loga informações detalhadas.
    
    Returns:
        bool: True se CUDA disponível, False caso contrário
    """
    try:
        import torch
    except ImportError:
        logger.error("❌ PyTorch não instalado! Não é possível verificar CUDA.")
        return False
    
    # Verificar se CUDA está disponível
    cuda_available = torch.cuda.is_available()
    
    if not cuda_available:
        logger.warning("⚠️  CUDA NÃO DISPONÍVEL!")
        logger.warning("    Modelos TTS rodarão em CPU (mais lento)")
        logger.warning("    Verifique:")
        logger.warning("    1. Driver NVIDIA instalado: nvidia-smi")
        logger.warning("    2. NVIDIA Docker runtime: docker info | grep -i nvidia")
        logger.warning("    3. Container com --gpus all ou deploy.resources.devices")
        return False
    
    # CUDA disponível - logar informações
    try:
        device_count = torch.cuda.device_count()
        current_device = torch.cuda.current_device()
        gpu_name = torch.cuda.get_device_name(current_device)
        gpu_props = torch.cuda.get_device_properties(current_device)
        
        vram_total_gb = gpu_props.total_memory / 1024**3
        vram_total_mb = gpu_props.total_memory / 1024**2
        
        # Log informações básicas
        logger.info("=" * 60)
        logger.info("🎮 CUDA DISPONÍVEL")
        logger.info("=" * 60)
        logger.info(f"📊 GPU: {gpu_name}")
        logger.info(f"📊 CUDA Version: {torch.version.cuda}")
        logger.info(f"📊 PyTorch Version: {torch.__version__}")
        logger.info(f"📊 Device Count: {device_count}")
        logger.info(f"📊 Current Device: {current_device}")
        logger.info(f"📊 VRAM Total: {vram_total_gb:.2f} GB ({vram_total_mb:.0f} MB)")
        logger.info(f"📊 Compute Capability: {gpu_props.major}.{gpu_props.minor}")
        
        # Verificar memória disponível
        free_mem, total_mem = torch.cuda.mem_get_info(current_device)
        free_gb = free_mem / 1024**3
        
        logger.info(f"📊 VRAM Livre: {free_gb:.2f} GB ({free_mem / 1024**2:.0f} MB)")
        logger.info("=" * 60)
        
        # Avisos baseados na quantidade de VRAM
        if vram_total_gb < 4.0:
            logger.warning("⚠️  GPU MUITO PEQUENA (< 4GB)!")
            logger.warning("    Recomendação: Use CPU para TTS")
            logger.warning("    Configure: XTTS_DEVICE=cpu F5TTS_DEVICE=cpu")
        
        elif vram_total_gb < 6.0:
            logger.warning("⚠️  GPU PEQUENA (< 6GB) DETECTADA!")
            logger.warning("    CRITICAL: Ative LOW_VRAM mode para evitar OOM!")
            logger.warning("    Configure: LOW_VRAM=true no .env")
            logger.warning("")
            
            # Verificar se LOW_VRAM está ativado
            low_vram = os.getenv('LOW_VRAM', 'false').lower() == 'true'
            if low_vram:
                logger.info("✅ LOW_VRAM mode ATIVADO (correto para GPU < 6GB)")
            else:
                logger.error("❌ LOW_VRAM mode DESATIVADO!")
                logger.error("   GPU pequena sem LOW_VRAM = OOM garantido!")
                logger.error("   AÇÃO NECESSÁRIA: Configure LOW_VRAM=true no .env")
        
        elif vram_total_gb < 8.0:
            logger.info("ℹ️  GPU média detectada (6-8GB)")
            logger.info("   Recomendação: LOW_VRAM=true para maior estabilidade")
        
        else:
            logger.info("✅ GPU grande detectada (>= 8GB)")
            logger.info("   Pode rodar XTTS + F5-TTS simultaneamente")
            logger.info("   LOW_VRAM=false é seguro")
        
        return True
    
    except Exception as e:
        logger.error(f"❌ Erro ao verificar informações CUDA: {e}", exc_info=True)
        return False


def log_cuda_memory_usage(prefix: str = ""):
    """
    Loga uso atual de memória CUDA (útil para debugging).
    
    Args:
        prefix: Prefixo para a mensagem de log
    """
    try:
        import torch
        
        if not torch.cuda.is_available():
            return
        
        allocated = torch.cuda.memory_allocated() / 1024**3
        reserved = torch.cuda.memory_reserved() / 1024**3
        free, total = torch.cuda.mem_get_info()
        free_gb = free / 1024**3
        total_gb = total / 1024**3
        
        msg = f"{prefix}VRAM: allocated={allocated:.2f}GB, reserved={reserved:.2f}GB, free={free_gb:.2f}GB/{total_gb:.2f}GB"
        logger.info(f"📊 {msg}")
    
    except Exception as e:
        logger.warning(f"⚠️  Não foi possível logar uso de VRAM: {e}")


if __name__ == "__main__":
    # Teste standalone
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    result = check_cuda()
    print(f"\nCUDA Available: {result}")
