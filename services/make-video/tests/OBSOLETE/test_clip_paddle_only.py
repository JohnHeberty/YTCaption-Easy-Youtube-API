#!/usr/bin/env python3
"""
Teste: CLIP + PaddleOCR (SEM EasyOCR)
======================================

Testar se o problema é específico do EasyOCR ou qualquer combinação.
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


def test_clip_paddle_only():
    """Teste com CLIP + PaddleOCR apenas"""
    
    print("\n" + "="*70)
    print("🎯 TESTE: CLIP + PaddleOCR (SEM EasyOCR)")
    print("="*70)
    
    videos = load_video_dataset()
    print(f"\n📊 Dataset: {len(videos)} vídeos")
    
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
        
        # Voto simples (maioria)
        votes = [has_clip, has_paddle]
        predicted = sum(votes) > len(votes) / 2
        
        correct = (expected == predicted)
        print(f"   🗳️ Voto: {'✅' if predicted else '❌'} → {'✅ CORRETO' if correct else '❌ ERRO'}")
        
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
    
    print("\n" + "="*70)
    print("📊 RESULTADO FINAL - CLIP + PaddleOCR")
    print("="*70)
    print(f"\n🎯 ACURÁCIA: {accuracy:.2%}")
    print(f"✅ Acertos: {tp + tn}/{total}")
    print(f"\nConfusion Matrix:")
    print(f"  TP={tp}  TN={tn}  FP={fp}  FN={fn}")
    
    if accuracy >= 0.90:
        print("\n🎉 ✅ META ATINGIDA: ≥90%!")
    else:
        print(f"\n⚠️ Meta não atingida: {accuracy:.2%} < 90%")
    
    print("="*70)
    
    assert total == len(videos)
    return accuracy


if __name__ == "__main__":
    test_clip_paddle_only()
