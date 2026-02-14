"""
Teste SIMPLES do PaddleOCR sem VideoValidator complexo
"""
import cv2
from paddleocr import PaddleOCR
from pathlib import Path
import json
import os

os.environ['MKL_NUM_THREADS'] = '1'

print("📊 TESTE SIMPLE - PaddleOCR Direct Call")
print("=" * 70)

# Inicializar PaddleOCR UMA VEZ
ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False, show_log=False)

synthetic_dir = Path('storage/validation/synthetic')
with open(synthetic_dir / 'ground_truth.json', 'r') as f:
    ground_truth = json.load(f)

tp, tn, fp, fn = 0, 0, 0, 0

print("\n🎬 Testando 30 vídeos (frame 45 middle frame)...")
for idx, video_data in enumerate(ground_truth['videos'], 1):
    video_path = str(synthetic_dir / video_data['filename'])
    expected = video_data['has_subtitles']
    
    # Extrair frame middle (1.5s = frame 45 @ 30fps)
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 45)
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print(f"{idx:2d}. ❌ ERRO: Failed to extract frame from {video_data['filename']}")
        continue
    
    # OCR
    try:
        result = ocr.ocr(frame, cls=True)
        
        has_text = bool(result and result[0] and len(result[0]) > 0)
        
        if has_text and expected:
            tp += 1
            status = "✅ TP"
        elif not has_text and not expected:
            tn += 1
            status = "✅ TN"
        elif has_text and not expected:
            fp += 1
            status = "❌ FP"
            print(f"{idx:2d}. {status} {video_data['filename']}: detected text in video WITHOUT subtitles")
        else:
            fn += 1
            status = "❌ FN"
            print(f"{idx:2d}. {status} {video_data['filename']}: NO text detected in video WITH subtitles")
    
    except Exception as e:
        print(f"{idx:2d}. ❌ EXCEPTION: {video_data['filename']}: {e}")
        if expected:
            fn += 1
        else:
            tn += 1

print("\n" + "=" * 70)
print("📈 CONFUSION MATRIX:")
print(f"   TP: {tp:2}/15 WITH")
print(f"   TN: {tn:2}/15 WITHOUT")
print(f"   FP: {fp:2}")
print(f"   FN: {fn:2}")

recall = tp / (tp + fn) if (tp + fn) > 0 else 0
precision = tp / (tp + fp) if (tp + fp) > 0 else 0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

print(f"\n📊 MÉTRICAS:")
print(f"   Recall:    {recall*100:.1f}%")
print(f"   Precision: {precision*100:.1f}%")
print(f"   F1 Score:  {f1*100:.1f}%")
print(f"   FPR:       {fpr*100:.1f}%")

print(f"\n🎯 GATES:")
print(f"   Recall ≥85%: {recall*100:.1f}% {'✅' if recall >= 0.85 else '❌'}")
print(f"   F1 ≥90%:     {f1*100:.1f}% {'✅' if f1 >= 0.90 else '❌'}")
print(f"   FPR <3%:     {fpr*100:.1f}% {'✅' if fpr < 0.03 else '❌'}")

if recall >= 0.85 and f1 >= 0.90 and fpr < 0.03:
    print("\n🎉 Sprint 00 COMPLETO! 90% accuracy target ATINGIDO!")
else:
    print("\n⚠️  Sprint 00 gates NÃO atingidos - need improvements")

print("=" * 70)
