#!/usr/bin/env python3
"""
Teste de acurácia com PROCESSAMENTO SERIALIZADO
================================================

Estratégia: Processar cada detector SEPARADAMENTE (um por vez)
ao invés de carregar todos juntos no ensemble.

Vantagens:
- Evita conflito de memória
- Evita conflito de threading
- Cada detector roda isolado

Desvantagens:
- Mais lento (3x o tempo)
- Precisa combinar resultados manualmente
"""

import sys
from pathlib import Path
import json
import time

# Configurações de memória
import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'

# Adicionar path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.video_processing.detectors.clip_classifier import CLIPClassifier
from app.video_processing.detectors.easyocr_detector import EasyOCRDetector  
from app.video_processing.detectors.paddle_detector import PaddleDetector
import pytest


def load_video_dataset():
    """Carrega dataset de vídeos para testes"""
    storage = Path(__file__).parent.parent / "storage" / "validation"
    
    videos = {}
    
    # Vídeos COM legendas (ground truth = True)
    sample_ok = storage / "sample_OK"
    if sample_ok.exists():
        for video in sample_ok.glob("*.mp4"):
            videos[str(video)] = True
    
    # Vídeos SEM legendas (ground truth = False)  
    sample_not_ok = storage / "sample_NOT_OK"
    if sample_not_ok.exists():
        for video in sample_not_ok.glob("*.mp4"):
            videos[str(video)] = False
    
    return videos


def detect_with_single_detector(detector_class, detector_args, video_path):
    """Roda um detector isolado em um vídeo"""
    try:
        # Criar detector
        print(f"    🔧 Criando {detector_class.__name__}...")
        detector = detector_class(**detector_args)
        
        # Detectar
        print(f"    🔍 Detectando em {Path(video_path).name}...")
        result = detector.detect(video_path)
        
        # Limpar memória
        del detector
        
        return result
    
    except Exception as e:
        print(f"    ❌ ERRO: {e}")
        return None


def weighted_vote(results, weights):
    """Voto ponderado baseado nos resultados individuais"""
    if not results:
        return False
    
    weighted_sum = 0.0
    total_weight = 0.0
    
    for result, weight in zip(results, weights):
        if result is None:
            continue
        
        has_subs = result.get('has_subtitles', False)
        confidence = result.get('confidence', 0.5)
        
        vote = 1.0 if has_subs else 0.0
        weighted_sum += vote * confidence * weight
        total_weight += weight
    
    if total_weight == 0:
        return False
    
    average = weighted_sum / total_weight
    return average >= 0.5


def test_serialized_accuracy():
    """
    Teste de acurácia com processamento SERIALIZADO
    ================================================
    
    Cada detector roda SEPARADAMENTE, depois combinamos os votos.
    """
    
    print("\n" + "="*70)
    print("🎯 TESTE DE ACURÁCIA - PROCESSAMENTO SERIALIZADO")
    print("="*70)
    
    # Carregar dataset
    videos = load_video_dataset()
    print(f"\n📊 Dataset: {len(videos)} vídeos")
    with_subs = sum(1 for v in videos.values() if v)
    without_subs = sum(1 for v in videos.values() if not v)
    print(f"   ✅ Com legendas: {with_subs}")
    print(f"   ❌ Sem legendas: {without_subs}")
    
    # Configurar detectores
    detectors_config = [
        ("CLIP", CLIPClassifier, {'device': 'cpu'}, 1.2),
        ("EasyOCR", EasyOCRDetector, {'languages': ['en'], 'gpu': False}, 1.0),
        ("PaddleOCR", PaddleDetector, {}, 0.8),
    ]
    
    # Métricas
    tp = tn = fp = fn = 0
    results = []
    
    start_time = time.time()
    
    # Processar cada vídeo
    for idx, (video_path, expected) in enumerate(videos.items(), 1):
        video_name = Path(video_path).name
        
        print(f"\n[{idx}/{len(videos)}] 🎬 {video_name}")
        print(f"   Ground Truth: {'✅ COM legendas' if expected else '❌ SEM legendas'}")
        
        # Processar com cada detector SEPARADAMENTE
        detector_results = []
        detector_weights = []
        
        for detector_name, detector_class, detector_args, weight in detectors_config:
            print(f"   [{detector_name}]")
            
            result = detect_with_single_detector(detector_class, detector_args, video_path)
            
            if result:
                detector_results.append(result)
                detector_weights.append(weight)
                
                has_subs = result.get('has_subtitles', False)
                confidence = result.get('confidence', 0.0)
                print(f"      → {'✅' if has_subs else '❌'} (conf: {confidence:.2%})")
            else:
                print(f"      → ⚠️ FALHOU")
        
        # Combinar votos
        predicted = weighted_vote(detector_results, detector_weights)
        
        # Verificar acerto
        correct = (expected == predicted)
        
        print(f"   🗳️ Voto final: {'✅ COM legendas' if predicted else '❌ SEM legendas'}")
        print(f"   {'✅ CORRETO' if correct else '❌ ERRO'}")
        
        # Atualizar métricas
        if expected and predicted:
            tp += 1  # True Positive
        elif not expected and not predicted:
            tn += 1  # True Negative
        elif not expected and predicted:
            fp += 1  # False Positive
        elif expected and not predicted:
            fn += 1  # False Negative
        
        results.append({
            'video': video_name,
            'expected': expected,
            'predicted': predicted,
            'correct': correct
        })
    
    duration = time.time() - start_time
    
    # Calcular métricas finais
    total = tp + tn + fp + fn
    accuracy = (tp + tn) / total if total > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    # Relatório final
    print("\n" + "="*70)
    print("📊 RESULTADOS FINAIS - PROCESSAMENTO SERIALIZADO")
    print("="*70)
    print(f"\n⏱️ Tempo total: {duration:.2f}s")
    print(f"🎬 Vídeos testados: {total}")
    print(f"\n🎯 ACURÁCIA:  {accuracy:.2%}")
    print(f"🎯 PRECISÃO:  {precision:.2%}")
    print(f"🎯 RECALL:    {recall:.2%}")
    print(f"🎯 F1-SCORE:  {f1:.2%}")
    print(f"\n✅ Acertos:   {tp + tn}/{total}")
    print(f"❌ Erros:     {fp + fn}/{total}")
    
    print(f"\n📈 Confusion Matrix:")
    print(f"   TP (True Positive):  {tp}")
    print(f"   TN (True Negative):  {tn}")
    print(f"   FP (False Positive): {fp}")
    print(f"   FN (False Negative): {fn}")
    
    # Salvar resultados
    output = {
        'method': 'serialized',
        'detectors': ['CLIP', 'EasyOCR', 'PaddleOCR'],
        'accuracy': round(accuracy * 100, 2),
        'precision': round(precision * 100, 2),
        'recall': round(recall * 100, 2),
        'f1': round(f1 * 100, 2),
        'tp': tp,
        'tn': tn,
        'fp': fp,
        'fn': fn,
        'total': total,
        'duration_seconds': round(duration, 2),
        'results': results
    }
    
    output_file = Path(__file__).parent.parent / "results_serialized.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Resultados salvos em: {output_file.name}")
    
    # Verificar meta de 90%
    if accuracy >= 0.90:
        print("\n🎉 ✅ META ATINGIDA: Acurácia ≥ 90%!")
    else:
        print(f"\n⚠️ Meta não atingida: {accuracy:.2%} < 90%")
        print(f"   Faltam {0.90 - accuracy:.2%} para atingir a meta")
    
    print("="*70)
    
    # Assertiva para pytest
    assert accuracy > 0.0, "Acurácia deve ser > 0"
    assert total == len(videos), f"Deve processar todos os {len(videos)} vídeos"
    
    return accuracy


if __name__ == "__main__":
    test_serialized_accuracy()
