#!/usr/bin/env python3
"""
Teste Manual de Thresholds - EasyOCR
Testa rapidamente vários valores de min_confidence para encontrar o melhor
"""

import sys
import json
import gc
import os
from pathlib import Path
from typing import Dict
import cv2
import logging

# Suprimir warnings do ffmpeg/libav
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'loglevel;quiet'
os.environ['OPENCV_LOG_LEVEL'] = 'SILENT'
import warnings
warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import detector
sys.path.insert(0, str(Path(__file__).parent))
from app.ocr_detector import OCRDetector


def test_video_with_threshold(video_path: str, detector: OCRDetector, min_confidence: float):
    """
    Testa um vídeo com threshold específico
    
    Returns:
        True se detectou legendas, False caso contrário, None se erro ao processar
    """
    try:
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            logger.warning(f"Não conseguiu abrir: {Path(video_path).name}")
            return None
        
        # Sample 5 frames uniformemente distribuídos
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            cap.release()
            return None
            
        frame_indices = [int(total_frames * i / 5) for i in range(1, 6)]
        
        positive_frames = 0
        frames_read = 0
        
        for frame_idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            frames_read += 1
            result = detector.detect_subtitle_in_frame(frame, min_confidence=min_confidence)
            
            if result.has_subtitle:
                positive_frames += 1
            
            del frame
        
        cap.release()
        
        # Precisa ter lido pelo menos 3 frames válidos
        if frames_read < 3:
            return None
        
        # >40% dos frames detectados
        return positive_frames / frames_read > 0.4
        
    except Exception as e:
        logger.warning(f"Erro ao processar {Path(video_path).name}: {str(e)[:50]}")
        return None
    
    cap.release()
    gc.collect()
    
    # Considera que tem legendas se >40% dos frames detectaram
    return (positive_frames / len(frame_indices)) > 0.4


def test_threshold(ok_videos: list, not_ok_videos: list, detector: OCRDetector, threshold: float) -> Dict:
    """
    Testa um threshold específico em todo o dataset
    
    Returns:
        Dict com métricas
    """
    true_positives = 0
    false_positives = 0
    true_negatives = 0
    false_negatives = 0
    skipped = 0
    
    # Testar OK videos (não devem ter legendas)
    for video_path in ok_videos:
        detected = test_video_with_threshold(str(video_path), detector, threshold)
        if detected is None:
            skipped += 1
            logger.debug(f"Pulado: {video_path.name}")
            continue
        if not detected:
            true_negatives += 1  # Correto: não detectou em vídeo OK
        else:
            false_positives += 1  # Erro: detectou em vídeo OK
    
    # Testar NOT_OK videos (devem ter legendas)
    for video_path in not_ok_videos:
        detected = test_video_with_threshold(str(video_path), detector, threshold)
        if detected is None:
            skipped += 1
            logger.debug(f"Pulado: {video_path.name}")
            continue
        if detected:
            true_positives += 1  # Correto: detectou em vídeo NOT_OK
        else:
            false_negatives += 1  # Erro: não detectou em vídeo NOT_OK
    
    total = true_positives + true_negatives + false_positives + false_negatives
    accuracy = (true_positives + true_negatives) / total if total > 0 else 0
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    if skipped > 0:
        logger.info(f"  ⚠️ {skipped} vídeos pulados por erro de codec")
    
    return {
        "threshold": threshold,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "true_negatives": true_negatives,
        "false_negatives": false_negatives
    }


def main():
    """Main function"""
    
    # Diretórios
    BASE_DIR = Path(__file__).parent / "storage"
    
    # Usar quick_test (apenas H.264, sem AV1 problemáticos)
    OK_DIR = BASE_DIR / "calibration" / "quick_test" / "OK"
    NOT_OK_DIR = BASE_DIR / "calibration" / "quick_test" / "NOT_OK"
    
    CALIBRATION_DIR = BASE_DIR / "calibration"
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    
    logger.info("="*60)
    logger.info("TESTE MANUAL DE THRESHOLDS - EasyOCR")
    logger.info("="*60)
    
    # Carregar vídeos
    ok_videos = list(OK_DIR.glob("*.mp4"))
    not_ok_videos = list(NOT_OK_DIR.glob("*.mp4"))
    
    logger.info(f"📁 Dataset: {len(ok_videos)} OK + {len(not_ok_videos)} NOT_OK")
    
    # Inicializar detector
    logger.info("🚀 Inicializando EasyOCR...")
    detector = OCRDetector()
    logger.info("✅ EasyOCR pronto\n")
    
    # Thresholds para testar (3 valores críticos para acelerar)
    thresholds = [45, 50, 55]
    logger.info(f"🎯 Testando {len(thresholds)} thresholds: {thresholds}")
    
    results = []
    best_result = None
    
    logger.info("🧪 Testando thresholds:\n")
    
    for i, threshold in enumerate(thresholds):
        logger.info(f"[{i+1}/{len(thresholds)}] Testing min_confidence={threshold}...")
        
        result = test_threshold(ok_videos, not_ok_videos, detector, threshold)
        results.append(result)
        
        logger.info(
            f"   Accuracy: {result['accuracy']:.1%} | "
            f"Precision: {result['precision']:.1%} | "
            f"Recall: {result['recall']:.1%} | "
            f"F1: {result['f1']:.1%}"
        )
        
        if best_result is None or result['accuracy'] > best_result['accuracy']:
            best_result = result
    
    # Salvar resultados
    output_file = CALIBRATION_DIR / "manual_threshold_results.json"
    with open(output_file, "w") as f:
        json.dump({
            "results": results,
            "best_result": best_result,
            "dataset_size": {
                "ok_videos": len(ok_videos),
                "not_ok_videos": len(not_ok_videos)
            }
        }, f, indent=2)
    
    # Imprimir resumo
    logger.info("\n" + "="*60)
    logger.info("RESUMO DOS RESULTADOS")
    logger.info("="*60)
    
    # Ordenar por accuracy
    results_sorted = sorted(results, key=lambda x: x['accuracy'], reverse=True)
    
    logger.info("\nTop 3 thresholds por acurácia:\n")
    for i, result in enumerate(results_sorted[:3]):
        logger.info(
            f"{i+1}. min_confidence={result['threshold']} → "
            f"Accuracy={result['accuracy']:.1%} "
            f"(Precision={result['precision']:.1%}, Recall={result['recall']:.1%})"
        )
    
    logger.info("\n" + "="*60)
    logger.info("🎯 MELHOR CONFIGURAÇÃO")
    logger.info("="*60)
    logger.info(f"min_confidence: {best_result['threshold']}")
    logger.info(f"Accuracy: {best_result['accuracy']:.1%}")
    logger.info(f"Precision: {best_result['precision']:.1%}")
    logger.info(f"Recall: {best_result['recall']:.1%}")
    logger.info(f"F1-Score: {best_result['f1']:.1%}")
    logger.info("\nConfusion Matrix:")
    logger.info(f"  True Positives:  {best_result['true_positives']}")
    logger.info(f"  False Positives: {best_result['false_positives']}")
    logger.info(f"  True Negatives:  {best_result['true_negatives']}")
    logger.info(f"  False Negatives: {best_result['false_negatives']}")
    
    logger.info(f"\n💾 Resultados salvos em: {output_file}")
    
    # Recomendar ação
    if best_result['accuracy'] >= 0.90:
        logger.info("\n🎉 META ATINGIDA! Acurácia >= 90%")
        logger.info("✅ Pode usar este threshold em produção")
    elif best_result['accuracy'] >= 0.80:
        logger.info("\n⚠️  Acurácia razoável (80-90%)")
        logger.info("💡 Considere executar calibração Optuna para otimizar mais")
    else:
        logger.info("\n❌ Acurácia abaixo de 80%")
        logger.info("💡 Recomendação: Execute calibração Optuna (100 trials)")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
