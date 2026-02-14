"""
Teste de Acurácia SIMPLIFICADO - Apenas CLIP
Objetivo: Medir acurácia baseline rapidamente
"""

import pytest
import json
from pathlib import Path

from app.video_processing.detectors.clip_classifier import CLIPClassifier


def test_clip_only_accuracy():
    """Teste rápido: apenas CLIP"""
    print("\n" + "="*70)
    print("🎯 TESTE RÁPIDO: APENAS CLIP CLASSIFIER")
    print("="*70)
    
    storage = Path(__file__).parent.parent / "storage" / "validation"
    
    # Carregar vídeos
    videos = {}
    ok_path = storage / "sample_OK"
    not_ok_path = storage / "sample_NOT_OK"
    
    if ok_path.exists():
        for v in list(ok_path.glob("*.mp4"))[:10]:
            videos[str(v)] = True
    
    if not_ok_path.exists():
        for v in list(not_ok_path.glob("*.mp4"))[:10]:
            videos[str(v)] = False
    
    print(f"\n📊 Dataset: {len(videos)} vídeos")
    
    # CLIP
    detector = CLIPClassifier(device='cpu')
    
    results = []
    correct = 0
    
    for i, (video_path, expected) in enumerate(videos.items(), 1):
        video_name = Path(video_path).name
        print(f"\n[{i}/{len(videos)}] {video_name}")
        print(f"   Truth: {'✅' if expected else '❌'}")
        
        try:
            result = detector.detect(video_path)
            predicted = result['has_subtitles']
            conf = result['confidence']
            
            is_correct = (expected == predicted)
            if is_correct:
                correct += 1
            
            results.append((expected, predicted))
            
            print(f"   Pred:  {'✅' if predicted else '❌'} ({conf:.1f}%)")
            print(f"   {'✅ CORRETO' if is_correct else '❌ ERRO'}")
        
        except Exception as e:
            print(f"   ⚠️ ERRO: {e}")
            results.append((expected, False))
    
    # Calcular
    tp = sum(1 for exp, pred in results if exp and pred)
    tn = sum(1 for exp, pred in results if not exp and not pred)
    fp = sum(1 for exp, pred in results if not exp and pred)
    fn = sum(1 for exp, pred in results if exp and not pred)
    
    total = len(results)
    accuracy = (tp + tn) / total * 100 if total > 0 else 0
    precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
    
    print("\n" + "="*70)
    print("📊 RESULTADOS - CLIP ONLY")
    print("="*70)
    print(f"Acurácia:  {accuracy:.2f}%")
    print(f"Precisão:  {precision:.2f}%")
    print(f"Recall:    {recall:.2f}%")
    print(f"Acertos:   {correct}/{total}")
    print(f"\nTP={tp} TN={tn} FP={fp} FN={fn}")
    print("="*70)
    
    # Salvar
    results_file = Path(__file__).parent / "results_clip_only.json"
    with open(results_file, 'w') as f:
        json.dump({
            'detector': 'CLIP',
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn,
            'total': total
        }, f, indent=2)
    
    print(f"\n💾 Resultados salvos: {results_file}")
    
    assert total > 0
    assert accuracy > 0


if __name__ == '__main__':
    test_clip_only_accuracy()
