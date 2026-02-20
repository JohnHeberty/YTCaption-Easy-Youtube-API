"""
M1: VAD Fallback com Threshold Dinâmico

PROBLEMA:
- VAD com threshold alto (0.5) pode filtrar TODAS as legendas em áudios com baixo volume
- Resultado: final_cues = [] → SRT vazio → Job FALHA (mesmo com fala presente)

SOLUÇÃO:
- Se len(final_cues) == 0 após VAD primário, tentar threshold mais baixo (0.3 → 0.1)
- Previne falsos negativos em áudios com baixo volume, sussurros, etc.

IMPLEMENTAÇÃO:
Adicionar fallback automático em subtitle_postprocessor.py
"""

from typing import List, Dict, Tuple
import logging


logger = logging.getLogger(__name__)


def process_subtitles_with_vad_fallback(
    audio_path: str,
    cues: List[Dict],
    primary_threshold: float = 0.5,
    fallback_threshold: float = 0.3,
    last_resort_threshold: float = 0.1
) -> Tuple[List[Dict], bool, str]:
    """
    Processa legendas com VAD e aplica fallback automático se necessário
    
    Args:
        audio_path: Path do áudio
        cues: Lista de cues da transcrição
        primary_threshold: Threshold primário (padrão: 0.5)
        fallback_threshold: Threshold de fallback (padrão: 0.3)
        last_resort_threshold: Threshold mínimo (padrão: 0.1)
    
    Returns:
        Tuple[final_cues, vad_ok, strategy_used]
        - final_cues: Cues filtrados por VAD
        - vad_ok: Se VAD primário foi usado com sucesso
        - strategy_used: Estratégia utilizada
    
    Estratégias (em ordem de preferência):
    1. VAD primário (threshold=0.5, Silero-VAD)
    2. VAD fallback (threshold=0.3, Silero-VAD)
    3. VAD last resort (threshold=0.1, Silero-VAD)
    4. WebRTC VAD (fallback de sistema)
    5. RMS threshold (último recurso - sem gating)
    """
    
    from app.services.subtitle_postprocessor import process_subtitles_with_vad
    
    # Tentar VAD primário
    logger.info(f"🎙️ VAD primário (threshold={primary_threshold})...")
    final_cues, vad_ok = process_subtitles_with_vad(audio_path, cues, threshold=primary_threshold)
    
    if len(final_cues) > 0:
        logger.info(f"   ✅ VAD primário OK: {len(final_cues)}/{len(cues)} cues")
        return final_cues, vad_ok, "primary"
    
    # VAD primário retornou vazio - tentar fallback
    logger.warning(
        f"   ⚠️ VAD primário filtrou TODAS as legendas ({len(final_cues)}/{len(cues)})"
    )
    logger.info(f"🔄 VAD fallback (threshold={fallback_threshold})...")
    
    final_cues, vad_ok = process_subtitles_with_vad(audio_path, cues, threshold=fallback_threshold)
    
    if len(final_cues) > 0:
        logger.info(
            f"   ✅ VAD fallback OK: {len(final_cues)}/{len(cues)} cues "
            f"(recuperados com threshold mais baixo)"
        )
        return final_cues, vad_ok, "fallback"
    
    # Fallback também retornou vazio - tentar last resort
    logger.warning(
        f"   ⚠️ VAD fallback também filtrou TODAS as legendas"
    )
    logger.info(f"🔄 VAD last resort (threshold={last_resort_threshold})...")
    
    final_cues, vad_ok = process_subtitles_with_vad(audio_path, cues, threshold=last_resort_threshold)
    
    if len(final_cues) > 0:
        logger.info(
            f"   ✅ VAD last resort OK: {len(final_cues)}/{len(cues)} cues "
            f"(recuperados com threshold mínimo)"
        )
        return final_cues, vad_ok, "last_resort"
    
    # TODOS os VADs retornaram vazio - áudio realmente não tem fala
    logger.error(
        f"   ❌ TODOS os VADs falharam: áudio não contém fala detectável "
        f"(testados thresholds: {primary_threshold}, {fallback_threshold}, {last_resort_threshold})"
    )
    
    # Retornar vazio - job irá FALHAR (comportamento correto após bug fix)
    return [], False, "all_failed"


def monkey_patch_vad_in_celery_tasks():
    """
    Monkey patch para substituir process_subtitles_with_vad por versão com fallback
    
    Aplica fallback automático em celery_tasks.py sem modificar código original.
    """
    
    import app.infrastructure.celery_tasks as celery_tasks
    
    # Salvar função original
    original_function = celery_tasks.process_subtitles_with_vad
    
    # Substituir por versão com fallback
    def wrapper(audio_path: str, cues: List[Dict], **kwargs):
        final_cues, vad_ok, strategy = process_subtitles_with_vad_fallback(
            audio_path, cues
        )
        logger.info(f"💡 VAD strategy used: {strategy}")
        return final_cues, vad_ok
    
    celery_tasks.process_subtitles_with_vad = wrapper
    
    logger.info("✅ VAD fallback monkey patch aplicado")


# INTEGRAÇÃO NO CÓDIGO PRINCIPAL
# ================================
#
# Opção 1: Monkey Patch (Rápido, não invasivo)
# --------------------------------------------
# from test-prod.improvements.m1_vad_fallback import monkey_patch_vad_in_celery_tasks
# monkey_patch_vad_in_celery_tasks()
#
# Opção 2: Substituir Código Original (Permanente, mais limpo)
# ------------------------------------------------------------
# 1. Adicionar esta função em app/services/subtitle_postprocessor.py
# 2. Modificar celery_tasks.py linha ~850:
#
#    # ANTES:
#    gated_cues, vad_ok = process_subtitles_with_vad(str(audio_path), raw_cues)
#
#    # DEPOIS:
#    from ..services.subtitle_postprocessor import process_subtitles_with_vad_fallback
#    gated_cues, vad_ok, strategy = process_subtitles_with_vad_fallback(str(audio_path), raw_cues)
#    logger.info(f"💡 VAD strategy: {strategy}")
#
# 3. Se strategy == "all_failed", exception já será lançada pela validação seguinte


if __name__ == "__main__":
    print("="*80)
    print("M1: VAD Fallback com Threshold Dinâmico")
    print("="*80)
    print("\n✨ MELHORIA:")
    print("   - VAD fallback automático quando threshold primário falha")
    print("   - Previne falsos negativos em áudios com baixo volume")
    print("   - 3 níveis de threshold: 0.5 → 0.3 → 0.1")
    print("\n📋 INTEGRAÇÃO:")
    print("   1. Monkey patch (rápido): monkey_patch_vad_in_celery_tasks()")
    print("   2. Código permanente: Adicionar em subtitle_postprocessor.py")
    print("\n🔥 STATUS:")
    print("   ⏳ Implementado mas NÃO integrado (aguardando validação)")
    print("   📝 Adicionar teste em test-prod/test_vad_fallback.py")
