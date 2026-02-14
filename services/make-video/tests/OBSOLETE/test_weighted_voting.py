#!/usr/bin/env python3
"""
Teste: CLIP + PaddleOCR com Voto Ponderado por Confiança
==========================================================

Ao invés de voto simples (maioria), usar as confidências como pesos.
Isso permite que detectores mais confiantes tenham mais influência.
"""

import sys
from pathlib import Path
import json
import time
import os

os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.video_processing.detectors.clip_classifier import CLIPClassifier
from app.video_processing.detectors.paddle_detector import PaddleDetector


def load_video_dataset():
    """Carrega dataset de vídeos"""
    storage = Path(__file__).parent.parent / "storage" / "validation"
    videos = {}
    
    sample_ok = storage / "sample_OK"
    if sample_ok.exists():
        for video in sample_ok.glob("*.mp4"):
            videos[str(video)] = True
    
    sample_not_ok = storage / "sample_NOT_OK"
    if sample_not_ok.exists():
        for video in sample_not_ok.glob("*.mp4"):
            videos[str(video)] = False
    
    return videos


def weighted_vote(detections, weights=None):
    """
    Voto ponderado por confiança.
    
    Args:
        detections: Lista de (has_subtitles, confidence)
        weights: Lista de pesos base (opcional)
    
    Returns:
        (has_subtitles, combined_confidence)
    """
    if weights is None:
        weights = [1.0] * len(detections)
    
    # Score ponderado: +confidence se detectou, -confidence se não detectou
    weighted_score = 0.0
    total_weight = 0.0
    
    for (has_subs, confidence), weight in zip(detections, weights):
        # Score: positivo se detectou, negativo se não
        score = confidence if has_subs else -confidence
        weighted_score += score * weight
        total_weight += weight
    
    # Decisão: score positivo = tem legendas
    has_subtitles = weighted_score > 0
    
    # Confiança normalizada
    combined_confidence = abs(weighted_score) / total_weight if total_weight > 0 else 0.0
    
    return has_subtitles, combined_confidence


def test_weighted_voting():
    """Teste com voto ponderado"""
    
    print("\n" + "="*70)
    print("🎯 TESTE: CLIP + PaddleOCR com Voto Ponderado")
    print("="*70)
    
    videos = load_video_dataset()
    print(f"\n📊 Dataset: {len(videos)} vídeos")
    
    # Pesos: Paddle tem prioridade (baseado em performance histórica)
    weights = [0.8, 1.2]  # [CLIP, Paddle]
    print(f"⚖️ Pesos: CLIP={weights[0]}, Paddle={weights[1]}")
    
    tp = tn = fp = fn = 0
    
    for idx, (video_path, expected) in enumerate(videos.items(), 1):
        video_name = Path(video_path).name
        
        print(f"\n[{idx}/{len(videos)}] 🎬 {video_name}")
        print(f"   Truth: {'✅ COM' if expected else '❌ SEM'} legendas")
        
        # CLIP
        print("   [CLIP] Criando...")
        clip = CLIPClassifier(device='cpu')
        print("   [CLIP] Detectando...")
        result_clip = clip.detect(video_path)
        has_clip = result_clip.get('has_subtitles', False)
        conf_clip = result_clip.get('confidence', 0.0)
        print(f"   [CLIP] → {'✅' if has_clip else '❌'} ({conf_clip:.2%})")
        del clip
        
        # PaddleOCR
        print("   [Paddle] Criando...")
        paddle = PaddleDetector()
        print("   [Paddle] Detectando...")
        result_paddle = paddle.detect(video_path)
        has_paddle = result_paddle.get('has_subtitles', False)
        conf_paddle = result_paddle.get('confidence', 0.0)
        print(f"   [Paddle] → {'✅' if has_paddle else '❌'} ({conf_paddle:.2%})")
        del paddle
        
        # Voto ponderado
        detections = [
            (has_clip, conf_clip),
            (has_paddle, conf_paddle)
        ]
        predicted, combined_conf = weighted_vote(detections, weights)
        
        correct = (expected == predicted)
        print(f"   🗳️ Voto Ponderado: {'✅' if predicted else '❌'} ({combined_conf:.2%}) → {'✅ CORRETO' if correct else '❌ ERRO'}")
        
        # Métricas
        if expected and predicted:
            tp += 1
        elif not expected and not predicted:
            tn += 1
        elif not expected and predicted:
            fp += 1
        elif expected and not predicted:
            fn += 1
    
    # Resultado final
    total = tp + tn + fp + fn
    accuracy = (tp + tn) / total if total > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    print("\n" + "="*70)
    print("📊 RESULTADO FINAL - Voto Ponderado")
    print("="*70)
    print(f"\n🎯 ACURÁCIA: {accuracy:.2%}")
    print(f"📈 PRECISÃO: {precision:.2%}")
    print(f"📉 RECALL: {recall:.2%}")
    print(f"🎖️ F1-SCORE: {f1:.2%}")
    print(f"\n✅ Acertos: {tp + tn}/{total}")
    print(f"\nConfusion Matrix:")
    print(f"  TP={tp}  TN={tn}  FP={fp}  FN={fn}")
    
    if accuracy >= 0.90:
        print("\n🎉 ✅ META ATINGIDA: ≥90%!")
    elif accuracy >= 0.75:
        print(f"\n⚠️ Próximo da meta: {accuracy:.2%} (faltam {0.90-accuracy:.2%})")
    else:
        print(f"\n❌ Abaixo da meta: {accuracy:.2%} < 90%")
    
    print("="*70)
    
    assert total == len(videos)
    return accuracy


if __name__ == "__main__":
    test_weighted_voting()
