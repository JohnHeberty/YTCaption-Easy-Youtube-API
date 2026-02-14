#!/usr/bin/env python3
"""
Teste: PaddleOCR APENAS (sem ensemble)
=======================================

Teste de baseline: usar apenas PaddleOCR (detector Sprint 00-04)
sem nenhum ensemble, para medir performance isolada.

Hipótese: Ensembles estão PIORANDO a performance devido à
lógica de voto que exige unanimidade.
"""

import sys
from pathlib import Path
import json
import time
import os

os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'

sys.path.insert(0, str(Path(__file__).parent.parent))

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


def test_paddle_only():
    """Teste com PaddleOCR apenas (baseline)"""
    
    print("\n" + "="*70)
    print("🎯 TESTE: PaddleOCR APENAS (sem ensemble)")
    print("="*70)
    
    videos = load_video_dataset()
    print(f"\n📊 Dataset: {len(videos)} vídeos")
    
    tp = tn = fp = fn = 0
    
    for idx, (video_path, expected) in enumerate(videos.items(), 1):
        video_name = Path(video_path).name
        
        print(f"\n[{idx}/{len(videos)}] 🎬 {video_name}")
        print(f"   Truth: {'✅ COM' if expected else '❌ SEM'} legendas")
        
        # PaddleOCR
        print("   [Paddle] Criando...")
        paddle = PaddleDetector()
        print("   [Paddle] Detectando...")
        result_paddle = paddle.detect(video_path)
        has_paddle = result_paddle.get('has_subtitles', False)
        conf_paddle = result_paddle.get('confidence', 0.0)
        text_paddle = result_paddle.get('metadata', {}).get('text', '')
        print(f"   [Paddle] → {'✅' if has_paddle else '❌'} ({conf_paddle:.2%})")
        if text_paddle:
            print(f"   [Paddle] Text: {text_paddle[:50]}")
        del paddle
        
        # Decisão: usar resultado do Paddle diretamente
        predicted = has_paddle
        
        correct = (expected == predicted)
        print(f"   🎯 Decisão: {'✅' if predicted else '❌'} → {'✅ CORRETO' if correct else '❌ ERRO'}")
        
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
    print("📊 RESULTADO FINAL - PaddleOCR Apenas")
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
    test_paddle_only()
