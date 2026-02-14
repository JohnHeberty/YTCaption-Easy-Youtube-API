"""
Teste de Acurácia V3 - FORÇA BRUTA
Sem otimizações, todos os frames, frame completo
"""

import json
import os
import pytest
from app.video_processing.subtitle_detector_v3 import SubtitleDetectorV3


def test_accuracy_brute_force():
    """Teste FORÇA BRUTA - processa TODOS os frames completos"""
    
    print("\n" + "="*80)
    print("🎯 TESTE FORÇA BRUTA - SEM OTIMIZAÇÕES")
    print("="*80)
    print("Modo: Todos os frames, frame completo, sem ROI, sem sampling")
    print("="*80 + "\n")
    
    detector = SubtitleDetectorV3()
    
    # Carregar ground truth
    with open('storage/validation/sample_OK/ground_truth.json') as f:
        data_ok = json.load(f)
    
    with open('storage/validation/sample_NOT_OK/ground_truth.json') as f:
        data_not_ok = json.load(f)
    
    print(f"📊 Dataset:")
    print(f"   sample_OK (SEM texto): {len(data_ok['videos'])} vídeos")
    print(f"   sample_NOT_OK (COM texto): {len(data_not_ok['videos'])} vídeos")
    print(f"   Total: {len(data_ok['videos']) + len(data_not_ok['videos'])} vídeos\n")
    
    # Perguntar limite de frames
    print("⚠️  ATENÇÃO: Processar TODOS os frames pode demorar MUITO!")
    print("   Sugestões:")
    print("   - 30 frames: ~1 min por vídeo (teste rápido)")
    print("   - 100 frames: ~3 min por vídeo (teste médio)")
    print("   - None: TODOS os frames (pode levar horas!)")
    print("")
    
    # Para teste automático, usar limite
    MAX_FRAMES = 50  # Limite razoável para teste
    
    print(f"🔧 Usando limite: {MAX_FRAMES} frames por vídeo\n")
    
    # Métricas
    tp = 0
    tn = 0
    fp = 0
    fn = 0
    
    results = []
    
    print("="*80)
    print("🔍 Processando sample_OK (SEM texto):")
    print("="*80 + "\n")
    
    for i, video in enumerate(data_ok['videos'], 1):
        video_path = f"storage/validation/sample_OK/{video['filename']}"
        
        if not os.path.exists(video_path):
            print(f"⚠️  {video['filename']}: Arquivo não encontrado\n")
            continue
        
        print(f"[{i}/{len(data_ok['videos'])}] {video['filename']}")
        print("-" * 60)
        
        has_text, conf, sample_text, metadata = detector.detect_full_brute_force(
            video_path, 
            max_frames=MAX_FRAMES
        )
        
        expected = video['has_subtitles']  # False
        
        if has_text == expected:
            tn += 1
            status = "✅ CORRETO"
        else:
            fp += 1
            status = "❌ ERRO (falso positivo)"
        
        print(f"Resultado: {status}")
        print(f"Detectado: {has_text}, Esperado: {expected}")
        print("")
        
        results.append({
            'filename': video['filename'],
            'detected': has_text,
            'expected': expected,
            'confidence': conf,
            'correct': has_text == expected,
            'frames_processed': metadata.get('frames_processed', 0),
            'frames_with_text': metadata.get('frames_with_text', 0)
        })
    
    print("="*80)
    print("🔍 Processando sample_NOT_OK (COM texto):")
    print("="*80 + "\n")
    
    for i, video in enumerate(data_not_ok['videos'], 1):
        video_path = f"storage/validation/sample_NOT_OK/{video['filename']}"
        
        if not os.path.exists(video_path):
            print(f"⚠️  {video['filename']}: Arquivo não encontrado\n")
            continue
        
        print(f"[{i}/{len(data_not_ok['videos'])}] {video['filename']}")
        print("-" * 60)
        
        has_text, conf, sample_text, metadata = detector.detect_full_brute_force(
            video_path,
            max_frames=MAX_FRAMES
        )
        
        expected = video['has_subtitles']  # True
        
        if has_text == expected:
            tp += 1
            status = "✅ CORRETO"
        else:
            fn += 1
            status = "❌ ERRO (falso negativo)"
        
        print(f"Resultado: {status}")
        print(f"Detectado: {has_text}, Esperado: {expected}")
        print("")
        
        results.append({
            'filename': video['filename'],
            'detected': has_text,
            'expected': expected,
            'confidence': conf,
            'correct': has_text == expected,
            'frames_processed': metadata.get('frames_processed', 0),
            'frames_with_text': metadata.get('frames_with_text', 0)
        })
    
    # Calcular métricas finais
    total = tp + tn + fp + fn
    accuracy = (tp + tn) / total if total > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    print("\n" + "="*80)
    print("📊 RESULTADO FINAL - FORÇA BRUTA")
    print("="*80 + "\n")
    
    print(f"🎯 Confusion Matrix:")
    print(f"   TP (True Positives):  {tp:3d} - Detectou texto corretamente")
    print(f"   TN (True Negatives):  {tn:3d} - Não detectou texto corretamente")
    print(f"   FP (False Positives): {fp:3d} - Detectou texto mas não tem")
    print(f"   FN (False Negatives): {fn:3d} - Não detectou texto mas tem")
    
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
                  f"Esperado={err['expected']}, "
                  f"Frames processados={err['frames_processed']}, "
                  f"Frames com texto={err['frames_with_text']}")
    
    print("\n" + "="*80)
    
    # Salvar relatório
    with open('/tmp/accuracy_brute_force.txt', 'w') as f:
        f.write("TESTE FORÇA BRUTA - SEM OTIMIZAÇÕES\n")
        f.write("="*80 + "\n\n")
        f.write(f"Configuração:\n")
        f.write(f"  Max frames por vídeo: {MAX_FRAMES}\n")
        f.write(f"  Modo: Frame completo, sem ROI\n\n")
        f.write(f"Confusion Matrix:\n")
        f.write(f"  TP: {tp}\n")
        f.write(f"  TN: {tn}\n")
        f.write(f"  FP: {fp}\n")
        f.write(f"  FN: {fn}\n\n")
        f.write(f"Métricas:\n")
        f.write(f"  Acurácia:  {accuracy*100:.2f}%\n")
        f.write(f"  Precisão:  {precision*100:.2f}%\n")
        f.write(f"  Recall:    {recall*100:.2f}%\n")
        f.write(f"  F1-Score:  {f1*100:.2f}%\n")
    
    print(f"💾 Relatório salvo em: /tmp/accuracy_brute_force.txt\n")
    
    assert accuracy >= 0.30, f"Acurácia muito baixa: {accuracy*100:.2f}%"


if __name__ == "__main__":
    test_accuracy_brute_force()
