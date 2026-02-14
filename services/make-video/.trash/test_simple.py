#!/usr/bin/env python3
"""
Teste standalone do EasyOCR - versão minimalista
"""

import cv2
import easyocr
import re
from pathlib import Path

def clean_text(text):
    """Limpa texto com regex e filtra palavras"""
    # Manter apenas letras e números
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    # Palavras >2 caracteres
    words = [w.lower() for w in cleaned.split() if len(w) > 2]
    return words

# Dicionários de palavras comuns
PT_WORDS = {'que', 'não', 'uma', 'para', 'com', 'por', 'isso', 'mais', 'seu', 'sua', 'foi', 'tem', 'pode', 'mas', 'como', 'muito', 'quando', 'bem', 'até', 'sobre', 'então', 'agora', 'sempre', 'outro', 'nova', 'novo', 'grande', 'mesmo', 'ainda', 'onde', 'porque', 'aqui', 'hoje', 'casa', 'vida', 'amor', 'ver', 'fazer', 'dar', 'ter', 'dizer', 'falar', 'querer', 'saber', 'poder'}

EN_WORDS = {'the', 'and', 'for', 'you', 'are', 'not', 'this', 'that', 'with', 'from', 'have', 'was', 'were', 'been', 'will', 'can', 'but', 'what', 'all', 'when', 'time', 'year', 'way', 'may', 'only', 'now', 'new', 'make', 'work', 'know', 'take', 'see', 'come', 'get', 'use', 'find', 'give', 'tell', 'ask', 'try', 'call', 'hand', 'about', 'after', 'back', 'just', 'good', 'where', 'every', 'much', 'before', 'right', 'mean', 'old', 'great', 'same', 'because', 'here', 'show', 'why', 'help', 'different'}

def has_readable_words(words):
    """Verifica se há palavras legíveis"""
    return any(w in PT_WORDS or w in EN_WORDS for w in words)

def test_video(video_path, reader):
    """Testa um vídeo"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False, []
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    sample_interval = max(1, int(fps * 2))
    
    all_readable_words = []
    
    for frame_idx in range(0, min(total_frames, sample_interval * 5), sample_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break
        
        # OCR
        results = reader.readtext(frame, detail=0)
        
        for text in results:
            words = clean_text(text)
            readable = [w for w in words if w in PT_WORDS or w in EN_WORDS]
            all_readable_words.extend(readable)
    
    cap.release()
    
    has_subtitle = len(all_readable_words) > 0
    return has_subtitle, all_readable_words

# Main
print("🚀 Inicializando EasyOCR...")
reader = easyocr.Reader(['pt', 'en'], gpu=False, verbose=False)
print("✅ EasyOCR pronto\n")

BASE_DIR = Path("/app/storage")
OK_DIR = BASE_DIR / "OK"
NOT_OK_DIR = BASE_DIR / "NOT_OK"

ok_videos = list(OK_DIR.glob("*.mp4"))[:3]
not_ok_videos = list(NOT_OK_DIR.glob("*.mp4"))[:3]

print(f"📁 Dataset: {len(ok_videos)} OK + {len(not_ok_videos)} NOT_OK\n")

results = []

print("="*60)
print("TESTANDO VÍDEOS OK (devem ser aprovados - sem legendas)")
print("="*60)
for video in ok_videos:
    print(f"\n📹 {video.name}")
    has_sub, words = test_video(str(video), reader)
    expected = False
    correct = (has_sub == expected)
    results.append(correct)
    
    status = "✅ CORRETO" if correct else "❌ ERRO"
    print(f"   Detectou legendas: {has_sub}")
    print(f"   Palavras: {words[:10]}")
    print(f"   {status}")

print("\n" + "="*60)
print("TESTANDO VÍDEOS NOT_OK (devem ser banidos - com legendas)")
print("="*60)
for video in not_ok_videos:
    print(f"\n📹 {video.name}")
    has_sub, words = test_video(str(video), reader)
    expected = True
    correct = (has_sub == expected)
    results.append(correct)
    
    status = "✅ CORRETO" if correct else "❌ ERRO"
    print(f"   Detectou legendas: {has_sub}")
    print(f"   Palavras: {words[:10]}")
    print(f"   {status}")

# Resumo
print("\n" + "="*60)
print("RESUMO FINAL")
print("="*60)
correct = sum(results)
total = len(results)
accuracy = (correct / total * 100) if total > 0 else 0

print(f"Total: {total} vídeos")
print(f"Acertos: {correct}")
print(f"Erros: {total - correct}")
print(f"Acurácia: {accuracy:.1f}%")

if accuracy >= 90:
    print("\n🎉 META ATINGIDA! Acurácia >= 90%")
elif accuracy >= 70:
    print("\n⚠️  Acurácia razoável (70-90%)")
else:
    print("\n❌ Acurácia baixa (<70%)")
