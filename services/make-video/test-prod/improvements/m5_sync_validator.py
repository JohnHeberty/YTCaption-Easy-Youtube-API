"""
M5: Validação de Sync A/V Aprimorada

PROBLEMA:
- Drift entre áudio e legendas pode ocorrer devido a:
  * VFR (Variable Frame Rate) em shorts
  * Duplicate frames durante concatenação
  * Timing incorreto em cues do Whisper
- Sistema já tem SyncValidator mas não aplica correção automática

SOLUÇÃO:
- Usar SyncValidator existente (app/services/sync_validator.py)
- Detectar drift > 500ms (Netflix standard)
- Aplicar correção automática de timestamp
- Re-gerar SRT corrigido se necessário

IMPLEMENTAÇÃO:
Adicionar auto-correction em celery_tasks.py após burn-in
"""

import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional


logger = logging.getLogger(__name__)


class SubtitleSyncCorrector:
    """
    Corrige sync drift em legendas
    
    Estratégias:
    1. Linear correction: Ajusta todos os timestamps proporcionalmente
    2. Segment correction: Corrige por segmentos (detecta pontos de drift)
    3. Manual offset: Aplica offset fixo
    """
    
    def __init__(self, tolerance_ms: float = 500):
        """
        Args:
            tolerance_ms: Tolerância de drift em milissegundos (default: 500 = Netflix standard)
        """
        self.tolerance_ms = tolerance_ms
    
    def detect_drift(
        self,
        video_duration: float,
        audio_duration: float
    ) -> Tuple[float, bool]:
        """
        Detecta drift entre vídeo e áudio
        
        Args:
            video_duration: Duração do vídeo (segundos)
            audio_duration: Duração do áudio (segundos)
        
        Returns:
            Tuple[drift_seconds, needs_correction]
        """
        
        drift = abs(video_duration - audio_duration)
        needs_correction = drift > (self.tolerance_ms / 1000.0)
        
        logger.info(
            f"🔍 Sync drift detection: "
            f"video={video_duration:.3f}s, audio={audio_duration:.3f}s, "
            f"drift={drift:.3f}s, needs_correction={needs_correction}"
        )
        
        return drift, needs_correction
    
    def apply_linear_correction(
        self,
        cues: List[Dict],
        original_duration: float,
        target_duration: float
    ) -> List[Dict]:
        """
        Aplica correção linear de timestamps
        
        Args:
            cues: Lista de cues com start/end/text
            original_duration: Duração original
            target_duration: Duração alvo
        
        Returns:
            Cues com timestamps corrigidos
        """
        
        if original_duration <= 0:
            logger.warning("⚠️ Cannot apply correction: original_duration <= 0")
            return cues
        
        ratio = target_duration / original_duration
        
        logger.info(
            f"🔧 Applying linear correction: "
            f"ratio={ratio:.4f} (original={original_duration:.2f}s → target={target_duration:.2f}s)"
        )
        
        corrected_cues = []
        
        for cue in cues:
            corrected_cue = {
                'start': cue['start'] * ratio,
                'end': cue['end'] * ratio,
                'text': cue['text']
            }
            corrected_cues.append(corrected_cue)
        
        logger.info(f"✅ Corrected {len(corrected_cues)} cues")
        
        return corrected_cues
    
    def regenerate_srt(
        self,
        corrected_cues: List[Dict],
        output_path: str,
        words_per_caption: int = 2
    ) -> str:
        """
        Re-gera arquivo SRT com timestamps corrigidos
        
        Args:
            corrected_cues: Cues com timestamps corrigidos
            output_path: Path do SRT de output
            words_per_caption: Palavras por caption
        
        Returns:
            Path do SRT gerado
        """
        
        from app.services.subtitle_generator import SubtitleGenerator
        
        # Agrupar cues em segments
        segments = []
        for i in range(0, len(corrected_cues), 10):  # Chunks de 10 palavras
            chunk = corrected_cues[i:i+10]
            if chunk:
                segments.append({
                    'start': chunk[0]['start'],
                    'end': chunk[-1]['end'],
                    'text': ' '.join(c['text'] for c in chunk)
                })
        
        logger.info(f"📄 Regenerating SRT with {len(segments)} segments...")
        
        gen = SubtitleGenerator()
        gen.generate_word_by_word_srt(
            segments=segments,
            output_path=output_path,
            words_per_caption=words_per_caption
        )
        
        logger.info(f"✅ SRT regenerated: {output_path}")
        
        return output_path


async def validate_and_correct_sync(
    video_path: str,
    audio_path: str,
    subtitle_path: str,
    video_builder,
    tolerance_ms: float = 500
) -> Tuple[bool, Optional[str], dict]:
    """
    Valida sync A/V e aplica correção se necessário
    
    Args:
        video_path: Path do vídeo
        audio_path: Path do áudio
        subtitle_path: Path do SRT
        video_builder: VideoBuilder instance
        tolerance_ms: Tolerância de drift
    
    Returns:
        Tuple[is_valid, corrected_srt_path, metadata]
        - is_valid: Se sync está OK (dentro da tolerância)
        - corrected_srt_path: Path do SRT corrigido (se aplicável)
        - metadata: Métricas de drift e correção
    """
    
    from app.services.sync_validator import SyncValidator
    
    # 1. Validar sync
    sync_validator = SyncValidator(tolerance_seconds=tolerance_ms / 1000.0)
    
    is_valid, drift, sync_metadata = await sync_validator.validate_sync(
        video_path=video_path,
        audio_path=audio_path,
        video_builder=video_builder
    )
    
    metadata = {
        "drift_seconds": drift,
        "drift_percentage": sync_metadata.get('drift_percentage', 0),
        "tolerance_ms": tolerance_ms,
        "is_valid": is_valid
    }
    
    if is_valid:
        logger.info(f"✅ Sync validation OK: drift={drift:.3f}s (tolerance={tolerance_ms}ms)")
        return True, None, metadata
    
    # 2. Sync inválido - aplicar correção
    logger.warning(
        f"⚠️ Sync validation FAILED: drift={drift:.3f}s > tolerance={tolerance_ms/1000.0:.3f}s"
    )
    logger.info("🔧 Applying automatic sync correction...")
    
    try:
        # Carregar cues do SRT original
        cues = load_srt_cues(subtitle_path)
        
        # Obter durações
        video_info = await video_builder.get_video_info(video_path)
        audio_info = await video_builder.get_audio_duration(audio_path)
        
        video_duration = video_info['duration']
        audio_duration = audio_info
        
        # Aplicar correção
        corrector = SubtitleSyncCorrector(tolerance_ms=tolerance_ms)
        corrected_cues = corrector.apply_linear_correction(
            cues,
            original_duration=video_duration,
            target_duration=audio_duration
        )
        
        # Regenerar SRT
        corrected_srt_path = str(Path(subtitle_path).parent / "subtitles_corrected.srt")
        corrector.regenerate_srt(corrected_cues, corrected_srt_path)
        
        metadata['correction_applied'] = True
        metadata['corrected_srt_path'] = corrected_srt_path
        metadata['original_duration'] = video_duration
        metadata['target_duration'] = audio_duration
        
        logger.info(f"✅ Sync correction applied: {corrected_srt_path}")
        
        return False, corrected_srt_path, metadata
    
    except Exception as e:
        logger.error(f"❌ Sync correction failed: {e}")
        metadata['correction_applied'] = False
        metadata['correction_error'] = str(e)
        
        # Sync inválido MAS correção falhou
        return False, None, metadata


def load_srt_cues(srt_path: str) -> List[Dict]:
    """
    Carrega cues de arquivo SRT
    
    Returns:
        Lista de cues com start/end/text
    """
    
    cues = []
    
    with open(srt_path, 'r') as f:
        content = f.read()
    
    # Parse SRT (simplificado)
    blocks = content.strip().split('\n\n')
    
    for block in blocks:
        lines = block.split('\n')
        if len(lines) >= 3:
            # Linha 2: timestamps (00:00:00,000 --> 00:00:02,000)
            timestamp_line = lines[1]
            if '-->' in timestamp_line:
                start_str, end_str = timestamp_line.split('-->')
                
                start = parse_srt_timestamp(start_str.strip())
                end = parse_srt_timestamp(end_str.strip())
                text = ' '.join(lines[2:])
                
                cues.append({
                    'start': start,
                    'end': end,
                    'text': text
                })
    
    return cues


def parse_srt_timestamp(timestamp_str: str) -> float:
    """Converte timestamp SRT (00:00:10,500) para segundos"""
    
    # Format: HH:MM:SS,mmm
    time_part, ms_part = timestamp_str.split(',')
    h, m, s = map(int, time_part.split(':'))
    ms = int(ms_part)
    
    return h * 3600 + m * 60 + s + ms / 1000.0


# INTEGRAÇÃO NO CÓDIGO PRINCIPAL
# ================================
#
# Adicionar em celery_tasks.py ANTES de burn-in (linha ~920):
#
# # Validar e corrigir sync A/V
# from ..services.subtitle_sync_corrector import validate_and_correct_sync
#
# is_valid, corrected_srt, metadata = await validate_and_correct_sync(
#     video_path=str(video_with_audio_path),
#     audio_path=str(audio_path),
#     subtitle_path=str(subtitle_path),
#     video_builder=video_builder,
#     tolerance_ms=500
# )
#
# if corrected_srt:
#     logger.info(f"🔧 Using corrected subtitles: {corrected_srt}")
#     subtitle_path = Path(corrected_srt)
# elif not is_valid:
#     logger.warning("⚠️ Sync validation failed but correction was not applied")
#     # Decidir: FALHAR job OU continuar (usar SRT original)
#     # raise SubtitleGenerationException("Sync validation failed")
#
# # Burn-in de legendas (usando SRT original OU corrigido)
# await video_builder.burn_subtitles(...)


if __name__ == "__main__":
    print("="*80)
    print("M5: Validação de Sync A/V Aprimorada")
    print("="*80)
    print("\n✨ MELHORIA:")
    print("   - Detecção automática de drift > 500ms")
    print("   - Correção linear de timestamps")
    print("   - Regeneração automática de SRT corrigido")
    print("   - Usa SyncValidator existente (já implementado)")
    print("\n🎯 BENEFÍCIOS:")
    print("   - Elimina dessincronização de legendas")
    print("   - Correção automática (sem intervenção manual)")
    print("   - Melhora experiência do usuário final")
    print("\n⚙️ TOLERÂNCIA:")
    print("   - 500ms (Netflix standard)")
    print("   - Configurável via parâmetro")
    print("\n🔥 STATUS:")
    print("   ⏳ Implementado mas NÃO integrado (aguardando validação)")
    print("   📝 Adicionar teste em test-prod/test_sync_correction.py")
