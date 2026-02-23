#!/usr/bin/env python3
"""
Script de teste simples para validar EasyOCR com vídeos de referência
"""

import sys
import cv2
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.ocr_detector import OCRDetector

def test_video(video_path: str, expected_has_subtitle: bool):
    """
    Testa um vídeo e verifica se detecta legendas corretamente
    
    Args:
        video_path: Path do vídeo
        expected_has_subtitle: Se esperamos detectar legendas (True para NOT_OK, False para OK)
    """
    print(f"\n{'='*80}")
    print(f"📹 Testando: {Path(video_path).name}")
    print(f"   Esperado: {'BANIR (tem legendas)' if expected_has_subtitle else 'APROVAR (sem legendas)'}")
    print(f"{'='*80}")
    
    # Inicializar detector
    detector = OCRDetector()
    
    # Abrir vídeo
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"❌ Erro ao abrir vídeo: {video_path}")
        return False
    
    # Pegar informações do vídeo
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = total_frames / fps if fps > 0 else 0
    
    print(f"📊 Informações:")
    print(f"   ├─ Frames: {total_frames}")
    print(f"   ├─ FPS: {fps:.1f}")
    print(f"   └─ Duração: {duration:.1f}s")
    
    # Amostrar frames (a cada 2 segundos)
    sample_interval = max(1, int(fps * 2))
    detections = []
    
    print(f"\n🔍 Analisando frames...")
    for frame_idx in range(0, min(total_frames, sample_interval * 10), sample_interval):  # Max 10 samples
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        
        if not ret:
            break
        
        # Detectar legendas
        result = detector.detect_subtitle_in_frame(frame)
        detections.append(result.has_subtitle)
        
        if result.has_subtitle:
            print(f"   Frame {frame_idx}: ✅ LEGENDAS DETECTADAS")
            print(f"      ├─ Palavras legíveis: {result.readable_words}")
            print(f"      ├─ Confiança: {result.confidence:.1f}%")
            print(f"      └─ Texto bruto: '{result.text[:50]}...'")
    
    cap.release()
    
    # Resultado final
    has_subtitles = any(detections)
    positive_frames = sum(detections)
    total_tested = len(detections)
    
    print(f"\n📈 Resultado:")
    print(f"   ├─ Frames testados: {total_tested}")
    print(f"   ├─ Frames com legendas: {positive_frames}")
    print(f"   └─ Veredicto: {'BANIR 🚫' if has_subtitles else 'APROVAR ✅'}")
    
    # Validar
    correct = has_subtitles == expected_has_subtitle
    
    if correct:
        print(f"\n✅ ✅ ✅ CORRETO! Vídeo classificado como esperado")
    else:
        print(f"\n❌ ❌ ❌ INCORRETO! Esperava {expected_has_subtitle}, obteve {has_subtitles}")
    
    return correct


def main():
    """Testa vídeos OK e NOT_OK"""
    
    print("\n" + "="*80)
    print("🧪 TESTE DE VALIDAÇÃO DO EASYOCR")
    print("="*80)
    
    BASE_DIR = Path(__file__).parent / "storage"
    OK_DIR = BASE_DIR / "OK"
    NOT_OK_DIR = BASE_DIR / "NOT_OK"
    
    # Pegar alguns vídeos de cada categoria
    ok_videos = list(OK_DIR.glob("*.mp4"))[:3]  # 3 primeiros
    not_ok_videos = list(NOT_OK_DIR.glob("*.mp4"))[:3]  # 3 primeiros
    
    print(f"\n📁 Dataset de teste:")
    print(f"   ├─ Vídeos OK (sem legendas): {len(ok_videos)}")
    print(f"   └─ Vídeos NOT_OK (com legendas): {len(not_ok_videos)}")
    
    results = []
    
    # Testar vídeos OK (não devem ter legendas)
    print(f"\n{'#'*80}")
    print(f"# TESTANDO VÍDEOS OK (devem ser APROVADOS)")
    print(f"{'#'*80}")
    for video in ok_videos:
        results.append(test_video(str(video), expected_has_subtitle=False))
    
    # Testar vídeos NOT_OK (devem ter legendas)
    print(f"\n{'#'*80}")
    print(f"# TESTANDO VÍDEOS NOT_OK (devem ser BANIDOS)")
    print(f"{'#'*80}")
    for video in not_ok_videos:
        results.append(test_video(str(video), expected_has_subtitle=True))
    
    # Resumo final
    print(f"\n{'='*80}")
    print(f"📊 RESUMO FINAL")
    print(f"{'='*80}")
    
    correct = sum(results)
    total = len(results)
    accuracy = (correct / total * 100) if total > 0 else 0
    
    print(f"   ├─ Total de vídeos testados: {total}")
    print(f"   ├─ Acertos: {correct}")
    print(f"   ├─ Erros: {total - correct}")
    print(f"   └─ Acurácia: {accuracy:.1f}%")
    
    if accuracy >= 90:
        print(f"\n🎉 🎉 🎉 META ATINGIDA! Acurácia >= 90%")
    elif accuracy >= 70:
        print(f"\n⚠️  Acurácia razoável, mas abaixo da meta de 90%")
    else:
        print(f"\n❌ Acurácia baixa, necessário ajustar parâmetros")
    
    return accuracy


if __name__ == "__main__":
    try:
        accuracy = main()
        sys.exit(0 if accuracy >= 90 else 1)
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
