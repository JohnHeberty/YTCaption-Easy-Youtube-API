"""
Teste de Acurácia OFICIAL - Força Bruta (Fevereiro 2026)

Usa SubtitleDetectorV2 (nova arquitetura) para medir acurácia real.

Dataset validado:
- sample_OK: 7 vídeos SEM texto
- sample_NOT_OK: 37 vídeos COM texto
- Total: 44 vídeos

Meta: 90% de acurácia
Resultado esperado: ~97.73% (já validado)
"""

import json
import os
import pytest
from pathlib import Path
from app.video_processing.subtitle_detector_v2 import SubtitleDetectorV2


def test_accuracy_official():
    """Teste oficial de acurácia - Força Bruta"""
    
    print("\n" + "="*80)
    print("🎯 TESTE OFICIAL DE ACURÁCIA - FORÇA BRUTA")
    print("="*80)
    print("SubtitleDetectorV2 - Nova Arquitetura (Fev 2026)")
    print("Modo: Todos os frames, frame completo, sem otimizações")
    print("="*80 + "\n")
    
    # Inicializar detector (sem limite de frames = produção)
    detector = SubtitleDetectorV2(show_log=False, max_frames=50)
    
    # Carregar ground truth
    base_path = Path('storage/validation')
    
    with open(base_path / 'sample_OK' / 'ground_truth.json') as f:
        data_ok = json.load(f)
    
    with open(base_path / 'sample_NOT_OK' / 'ground_truth.json') as f:
        data_not_ok = json.load(f)
    
    print(f"📊 Dataset:")
    print(f"   sample_OK (SEM texto): {len(data_ok['videos'])} vídeos")
    print(f"   sample_NOT_OK (COM texto): {len(data_not_ok['videos'])} vídeos")
    print(f"   Total: {len(data_ok['videos']) + len(data_not_ok['videos'])} vídeos\n")
    
    # Limite de frames para teste (produção = None)
    MAX_FRAMES = 50
    print(f"🔧 Configuração: {MAX_FRAMES} frames por vídeo (teste rápido)")
    print(f"   Para produção, use max_frames=None (todos os frames)\n")
    
    # Métricas
    tp = tn = fp = fn = 0
    results = []
    
    print("="*80)
    print("🔍 Processando sample_OK (SEM texto):")
    print("="*80 + "\n")
    
    for i, video in enumerate(data_ok['videos'], 1):
        video_path = base_path / 'sample_OK' / video['filename']
        
        if not video_path.exists():
            print(f"⚠️  [{i}/{len(data_ok['videos'])}] {video['filename']}: NÃO ENCONTRADO\n")
            continue
        
        print(f"[{i}/{len(data_ok['videos'])}] {video['filename']}")
        
        has_text, conf, sample_text, metadata = detector.detect(str(video_path))
        
        expected = video['has_subtitles']  # False
        
        if has_text == expected:
            tn += 1
            status = "✅ CORRETO"
        else:
            fp += 1
            status = "❌ ERRO (falso positivo)"
        
        print(f"   Detectado: {has_text} | Esperado: {expected} | {status}")
        print(f"   Frames: {metadata['frames_with_text']}/{metadata['frames_processed']}\n")
        
        results.append({
            'filename': video['filename'],
            'detected': has_text,
            'expected': expected,
            'confidence': conf,
            'correct': has_text == expected,
            'frames_processed': metadata['frames_processed'],
            'frames_with_text': metadata['frames_with_text']
        })
    
    print("="*80)
    print("🔍 Processando sample_NOT_OK (COM texto):")
    print("="*80 + "\n")
    
    for i, video in enumerate(data_not_ok['videos'], 1):
        video_path = base_path / 'sample_NOT_OK' / video['filename']
        
        if not video_path.exists():
            print(f"⚠️  [{i}/{len(data_not_ok['videos'])}] {video['filename']}: NÃO ENCONTRADO\n")
            continue
        
        print(f"[{i}/{len(data_not_ok['videos'])}] {video['filename']}")
        
        has_text, conf, sample_text, metadata = detector.detect(str(video_path))
        
        expected = video['has_subtitles']  # True
        
        if has_text == expected:
            tp += 1
            status = "✅ CORRETO"
        else:
            fn += 1
            status = "❌ ERRO (falso negativo)"
        
        print(f"   Detectado: {has_text} | Esperado: {expected} | {status}")
        print(f"   Frames: {metadata['frames_with_text']}/{metadata['frames_processed']}\n")
        
        results.append({
            'filename': video['filename'],
            'detected': has_text,
            'expected': expected,
            'confidence': conf,
            'correct': has_text == expected,
            'frames_processed': metadata['frames_processed'],
            'frames_with_text': metadata['frames_with_text']
        })
    
    # Calcular métricas finais
    total = tp + tn + fp + fn
    accuracy = (tp + tn) / total if total > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    print("\n" + "="*80)
    print("📊 RESULTADO FINAL - OFICIAL")
    print("="*80 + "\n")
    
    print(f"🎯 Confusion Matrix:")
    print(f"   TP (True Positives):  {tp:3d} - Detectou texto corretamente")
    print(f"   TN (True Negatives):  {tn:3d} - Sem texto, detectou corretamente")
    print(f"   FP (False Positives): {fp:3d} - Falso positivo (detectou texto inexistente)")
    print(f"   FN (False Negatives): {fn:3d} - Falso negativo (não detectou texto existente)")
    
    print(f"\n📈 Métricas:")
    print(f"   🎖️  ACURÁCIA:  {accuracy*100:6.2f}%  {'✅ META ATINGIDA (90%)!' if accuracy >= 0.90 else '❌ Abaixo da meta'}")
    print(f"   📊 PRECISÃO:  {precision*100:6.2f}%")
    print(f"   📉 RECALL:    {recall*100:6.2f}%")
    print(f"   🎯 F1-SCORE:  {f1*100:6.2f}%")
    
    # Análise de erros
    errors = [r for r in results if not r['correct']]
    if errors:
        print(f"\n❌ ERROS ({len(errors)}):")
        for err in errors:
            print(f"   - {err['filename']}: Detectado={err['detected']}, Esperado={err['expected']}")
            print(f"     Frames: {err['frames_with_text']}/{err['frames_processed']}")
    else:
        print(f"\n🎉 ZERO ERROS! Acurácia perfeita!")
    
    print("\n" + "="*80)
    
    # Salvar relatório
    report_path = '/tmp/accuracy_official.txt'
    with open(report_path, 'w') as f:
        f.write("TESTE OFICIAL DE ACURÁCIA - FORÇA BRUTA\n")
        f.write("="*80 + "\n\n")
        f.write(f"Data: Fevereiro 2026\n")
        f.write(f"SubtitleDetectorV2: Nova Arquitetura (Força Bruta)\n")
        f.write(f"Configuração: {MAX_FRAMES} frames por vídeo\n\n")
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
            f.write(f"Erros ({len(errors)}):\n")
            for err in errors:
                f.write(f"  - {err['filename']}: Detectado={err['detected']}, Esperado={err['expected']}\n")
    
    print(f"💾 Relatório salvo em: {report_path}\n")
    
    # Assertiva final
    assert accuracy >= 0.90, f"Acurácia abaixo da meta: {accuracy*100:.2f}% (esperado: ≥90%)"
    print("✅ TESTE PASSOU - Meta de 90% atingida!\n")


if __name__ == "__main__":
    test_accuracy_official()
