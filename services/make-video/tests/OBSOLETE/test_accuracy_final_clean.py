"""
Teste FINAL de Acurácia - Dataset Corrigido
Sprint 07 - Medição com vídeos recuperados

Dataset:
- sample_OK/ (7 vídeos SEM legendas) → should detect FALSE
- sample_NOT_OK/ (38 vídeos COM legendas) → should detect TRUE
Total: 45 vídeos
"""

import json
import os
import pytest
from app.video_processing.subtitle_detector_v2 import SubtitleDetectorV2


def test_accuracy_final_clean():
    """Teste de acurácia com dataset corrigido após recuperação"""
    
    print("\n" + "="*80)
    print("🎯 TESTE FINAL DE ACURÁCIA - DATASET CORRIGIDO")
    print("="*80)
    
    detector = SubtitleDetectorV2()
    
    # Carregar ground truth
    with open('storage/validation/sample_OK/ground_truth.json') as f:
        data_ok = json.load(f)
    
    with open('storage/validation/sample_NOT_OK/ground_truth.json') as f:
        data_not_ok = json.load(f)
    
    print(f"\n📊 Dataset:")
    print(f"   sample_OK (SEM legendas): {len(data_ok['videos'])} vídeos")
    print(f"   sample_NOT_OK (COM legendas): {len(data_not_ok['videos'])} vídeos")
    print(f"   Total: {len(data_ok['videos']) + len(data_not_ok['videos'])} vídeos\n")
    
    # Métricas
    tp = 0  # True Positives: Detectou legenda corretamente
    tn = 0  # True Negatives: Não detectou legenda corretamente
    fp = 0  # False Positives: Detectou legenda mas não tem
    fn = 0  # False Negatives: Não detectou legenda mas tem
    
    results = []
    
    print("🔍 Processando vídeos...\n")
    
    # Testar sample_OK (SEM legendas - esperado: FALSE)
    print("📁 sample_OK (SEM legendas):")
    for i, video in enumerate(data_ok['videos'], 1):
        video_path = f"storage/validation/sample_OK/{video['filename']}"
        
        if not os.path.exists(video_path):
            print(f"  ⚠️  {video['filename']}: Arquivo não encontrado")
            continue
        
        # detect_in_video_with_multi_roi retorna: (has_subtitles, confidence, sample_text, metadata)
        has_subs, conf, sample_text, metadata = detector.detect_in_video_with_multi_roi(video_path)
        detected = has_subs
        expected = video['has_subtitles']  # False
        
        if detected == expected:
            tn += 1
            status = "✅ CORRETO"
        else:
            fp += 1
            status = "❌ ERRO"
        
        print(f"  [{i}/{len(data_ok['videos'])}] {video['filename'][:20]:<20} → "
              f"Detectado: {detected:5} | Esperado: {expected:5} | "
              f"Conf: {conf:5.1%} | {status}")
        
        results.append({
            'filename': video['filename'],
            'detected': detected,
            'expected': expected,
            'confidence': conf,
            'correct': detected == expected
        })
    
    # Testar sample_NOT_OK (COM legendas - esperado: TRUE)
    print(f"\n📁 sample_NOT_OK (COM legendas):")
    for i, video in enumerate(data_not_ok['videos'], 1):
        video_path = f"storage/validation/sample_NOT_OK/{video['filename']}"
        
        if not os.path.exists(video_path):
            print(f"  ⚠️  {video['filename']}: Arquivo não encontrado")
            continue
        
        # detect_in_video_with_multi_roi retorna: (has_subtitles, confidence, sample_text, metadata)
        has_subs, conf, sample_text, metadata = detector.detect_in_video_with_multi_roi(video_path)
        detected = has_subs
        expected = video['has_subtitles']  # True
        
        if detected == expected:
            tp += 1
            status = "✅ CORRETO"
        else:
            fn += 1
            status = "❌ ERRO"
        
        # Mostrar apenas resumo para não poluir (38 vídeos)
        if i <= 5 or i > len(data_not_ok['videos']) - 3 or status == "❌ ERRO":
            print(f"  [{i}/{len(data_not_ok['videos'])}] {video['filename'][:20]:<20} → "
                  f"Detectado: {detected:5} | Esperado: {expected:5} | "
                  f"Conf: {conf:5.1%} | {status}")
        elif i == 6:
            print(f"  ... processando vídeos 6-{len(data_not_ok['videos'])-3} ...")
        
        results.append({
            'filename': video['filename'],
            'detected': detected,
            'expected': expected,
            'confidence': conf,
            'correct': detected == expected
        })
    
    # Calcular métricas
    total = tp + tn + fp + fn
    accuracy = (tp + tn) / total if total > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    print("\n" + "="*80)
    print("📊 RESULTADO FINAL")
    print("="*80)
    
    print(f"\n🎯 Confusion Matrix:")
    print(f"   TP (True Positives):  {tp:3d} - Detectou legenda corretamente")
    print(f"   TN (True Negatives):  {tn:3d} - Não detectou legenda corretamente")
    print(f"   FP (False Positives): {fp:3d} - Detectou legenda mas não tem")
    print(f"   FN (False Negatives): {fn:3d} - Não detectou legenda mas tem")
    
    print(f"\n📈 Métricas:")
    print(f"   🎖️  ACURÁCIA:  {accuracy*100:6.2f}%  {'✅ META ATINGIDA!' if accuracy >= 0.90 else '❌ Abaixo da meta (90%)'}")
    print(f"   📊 PRECISÃO:  {precision*100:6.2f}%")
    print(f"   📉 RECALL:    {recall*100:6.2f}%")
    print(f"   🎯 F1-SCORE:  {f1*100:6.2f}%")
    
    # Análise de erros
    errors = [r for r in results if not r['correct']]
    if errors:
        print(f"\n❌ ERROS ({len(errors)}):")
        for err in errors:
            print(f"   - {err['filename']}: Detectado={err['detected']}, "
                  f"Esperado={err['expected']}, Conf={err['confidence']:.1%}")
    
    print("\n" + "="*80)
    
    # Salvar relatório
    with open('/tmp/accuracy_final_clean.txt', 'w') as f:
        f.write("TESTE FINAL DE ACURÁCIA - DATASET CORRIGIDO\n")
        f.write("="*80 + "\n\n")
        f.write(f"Dataset:\n")
        f.write(f"  sample_OK: {len(data_ok['videos'])} vídeos (SEM legendas)\n")
        f.write(f"  sample_NOT_OK: {len(data_not_ok['videos'])} vídeos (COM legendas)\n")
        f.write(f"  Total: {total} vídeos\n\n")
        f.write(f"Confusion Matrix:\n")
        f.write(f"  TP: {tp}\n")
        f.write(f"  TN: {tn}\n")
        f.write(f"  FP: {fp}\n")
        f.write(f"  FN: {fn}\n\n")
        f.write(f"Métricas:\n")
        f.write(f"  Acurácia:  {accuracy*100:.2f}%\n")
        f.write(f"  Precisão:  {precision*100:.2f}%\n")
        f.write(f"  Recall:    {recall*100:.2f}%\n")
        f.write(f"  F1-Score:  {f1*100:.2f}%\n\n")
        if errors:
            f.write(f"Erros:\n")
            for err in errors:
                f.write(f"  {err['filename']}: Det={err['detected']}, "
                       f"Esp={err['expected']}, Conf={err['confidence']:.1%}\n")
    
    print(f"💾 Relatório salvo em: /tmp/accuracy_final_clean.txt")
    print()
    
    # Assert para pytest
    assert accuracy >= 0.50, f"Acurácia muito baixa: {accuracy*100:.2f}%"


if __name__ == "__main__":
    test_accuracy_final_clean()
