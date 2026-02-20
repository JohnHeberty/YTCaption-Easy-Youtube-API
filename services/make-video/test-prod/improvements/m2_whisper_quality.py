"""
M2: Validação de Quality Score (Whisper)

PROBLEMA:
- Whisper pode retornar transcrições com baixa confiança (no_speech_prob alto)
- Legendas geradas são de baixa qualidade (texto incorreto, aleatório)
- Job completa com SUCESSO mas vídeo tem legendas ruins

SOLUÇÃO:
- Adicionar check de `no_speech_prob` retornado pelo Whisper
- Se no_speech_prob > threshold (ex: 0.6), rejeitar transcrição
- Job FALHA com mensagem clara (qualidade de transcrição insuficiente)

IMPLEMENTAÇÃO:
Validar quality score após transcrição em celery_tasks.py
"""

from typing import List, Dict, Optional
import logging


logger = logging.getLogger(__name__)


class WhisperQualityValidator:
    """
    Valida qualidade de transcrições do Whisper
    
    Métricas analisadas:
    - no_speech_prob: Probabilidade de não haver fala (0.0 a 1.0)
    - avg_logprob: Log-probabilidade média dos tokens (-inf a 0.0)
    - compression_ratio: Razão de compressão do texto (> 2.4 = repetição)
    """
    
    def __init__(
        self,
        no_speech_threshold: float = 0.6,
        min_avg_logprob: float = -1.0,
        max_compression_ratio: float = 2.4
    ):
        """
        Args:
            no_speech_threshold: Máximo permitido para no_speech_prob (padrão: 0.6)
            min_avg_logprob: Mínimo permitido para avg_logprob (padrão: -1.0)
            max_compression_ratio: Máximo permitido para compression_ratio (padrão: 2.4)
        """
        self.no_speech_threshold = no_speech_threshold
        self.min_avg_logprob = min_avg_logprob
        self.max_compression_ratio = max_compression_ratio
    
    def validate_transcription(
        self,
        segments: List[Dict],
        audio_duration: float
    ) -> tuple[bool, Optional[str], Dict]:
        """
        Valida qualidade de transcrição
        
        Args:
            segments: Segments retornados pelo Whisper
            audio_duration: Duração do áudio (segundos)
        
        Returns:
            Tuple[is_valid, failure_reason, quality_metrics]
        """
        
        if not segments:
            return False, "No segments returned by Whisper", {
                "segments_count": 0,
                "audio_duration": audio_duration
            }
        
        # Extrair métricas
        no_speech_probs = []
        avg_logprobs = []
        compression_ratios = []
        
        for segment in segments:
            # Whisper pode retornar estas métricas opcionalmente
            if 'no_speech_prob' in segment:
                no_speech_probs.append(segment['no_speech_prob'])
            if 'avg_logprob' in segment:
                avg_logprobs.append(segment['avg_logprob'])
            if 'compression_ratio' in segment:
                compression_ratios.append(segment['compression_ratio'])
        
        # Calcular médias
        metrics = {
            "segments_count": len(segments),
            "audio_duration": audio_duration,
            "no_speech_prob_avg": sum(no_speech_probs) / len(no_speech_probs) if no_speech_probs else None,
            "no_speech_prob_max": max(no_speech_probs) if no_speech_probs else None,
            "avg_logprob_avg": sum(avg_logprobs) / len(avg_logprobs) if avg_logprobs else None,
            "compression_ratio_avg": sum(compression_ratios) / len(compression_ratios) if compression_ratios else None,
            "compression_ratio_max": max(compression_ratios) if compression_ratios else None
        }
        
        # Validação 1: no_speech_prob muito alto
        if metrics["no_speech_prob_avg"] is not None:
            if metrics["no_speech_prob_avg"] > self.no_speech_threshold:
                return False, (
                    f"Transcription quality too low: no_speech_prob={metrics['no_speech_prob_avg']:.2f} "
                    f"(threshold={self.no_speech_threshold})"
                ), metrics
        
        # Validação 2: avg_logprob muito baixo (tokens com baixa probabilidade)
        if metrics["avg_logprob_avg"] is not None:
            if metrics["avg_logprob_avg"] < self.min_avg_logprob:
                return False, (
                    f"Transcription confidence too low: avg_logprob={metrics['avg_logprob_avg']:.2f} "
                    f"(min={self.min_avg_logprob})"
                ), metrics
        
        # Validação 3: compression_ratio muito alto (texto repetitivo)
        if metrics["compression_ratio_max"] is not None:
            if metrics["compression_ratio_max"] > self.max_compression_ratio:
                return False, (
                    f"Transcription has repetitive text: compression_ratio={metrics['compression_ratio_max']:.2f} "
                    f"(max={self.max_compression_ratio})"
                ), metrics
        
        # Validação 4: Duração de transcrição vs áudio (sanity check)
        transcription_duration = segments[-1]['end'] - segments[0]['start']
        duration_ratio = transcription_duration / audio_duration if audio_duration > 0 else 0
        
        metrics["transcription_duration"] = transcription_duration
        metrics["duration_ratio"] = duration_ratio
        
        if duration_ratio < 0.3:  # Menos de 30% do áudio transcrito
            return False, (
                f"Transcription covers only {duration_ratio*100:.1f}% of audio "
                f"(expected >= 30%)"
            ), metrics
        
        # Tudo OK
        logger.info(f"✅ Transcription quality validated: {metrics}")
        return True, None, metrics


def validate_whisper_transcription(
    segments: List[Dict],
    audio_duration: float,
    no_speech_threshold: float = 0.6
) -> tuple[bool, Optional[str], Dict]:
    """
    Wrapper função de validação (para integração fácil)
    
    Args:
        segments: Segments do Whisper
        audio_duration: Duração do áudio
        no_speech_threshold: Threshold para no_speech_prob
    
    Returns:
        Tuple[is_valid, failure_reason, metrics]
    """
    
    validator = WhisperQualityValidator(no_speech_threshold=no_speech_threshold)
    return validator.validate_transcription(segments, audio_duration)


# INTEGRAÇÃO NO CÓDIGO PRINCIPAL
# ================================
#
# Adicionar em celery_tasks.py após transcrição (linha ~730):
#
# segments = await api_client.transcribe_audio(str(audio_path), job.subtitle_language)
# logger.info(f"✅ Subtitles generated: {len(segments)} segments (attempt #{retry_attempt})")
#
# # NOVO: Validar quality score
# from ..services.whisper_quality_validator import validate_whisper_transcription
#
# is_valid, failure_reason, metrics = validate_whisper_transcription(
#     segments, audio_duration
# )
#
# if not is_valid:
#     logger.warning(f"⚠️ Transcription quality check failed: {failure_reason}")
#     logger.info(f"📊 Quality metrics: {metrics}")
#     
#     # Opção A: FALHAR imediatamente
#     raise SubtitleGenerationException(
#         reason=f"Transcription quality insufficient: {failure_reason}",
#         details=metrics
#     )
#     
#     # Opção B: RETRY com modelo diferente (ver M3)
#     if retry_attempt < 3:
#         logger.info("🔄 Retrying with different Whisper model...")
#         continue  # Próximo retry


if __name__ == "__main__":
    print("="*80)
    print("M2: Validação de Quality Score (Whisper)")
    print("="*80)
    print("\n✨ MELHORIA:")
    print("   - Valida qualidade de transcrições do Whisper")
    print("   - Rejeita transcrições com no_speech_prob > 0.6")
    print("   - Detecta texto repetitivo (compression_ratio > 2.4)")
    print("   - Valida cobertura de duração (>= 30% do áudio)")
    print("\n📊 MÉTRICAS VALIDADAS:")
    print("   1. no_speech_prob: Probabilidade de não haver fala")
    print("   2. avg_logprob: Confiança dos tokens")
    print("   3. compression_ratio: Texto repetitivo")
    print("   4. duration_ratio: Cobertura do áudio")
    print("\n🔥 STATUS:")
    print("   ⏳ Implementado mas NÃO integrado (aguardando validação)")
    print("   📝 Adicionar teste em test-prod/test_whisper_quality.py")
