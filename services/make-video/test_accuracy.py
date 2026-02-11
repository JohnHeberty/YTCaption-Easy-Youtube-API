import cv2
import easyocr
import re
from pathlib import Path

PT_WORDS = {
    "que", "nao", "uma", "para", "com", "por", "isso", "mais", "seu", "sua", 
    "foi", "tem", "pode", "mas", "como", "muito", "quando", "bem", "ate", "sobre",
    "entao", "agora", "sempre", "outro", "nova", "novo", "grande", "mesmo", "ainda",
    "onde", "porque", "aqui", "hoje", "casa", "vida", "amor", "ver", "fazer", "dar",
    "ter", "dizer", "falar", "querer", "saber", "poder"
}

EN_WORDS = {
    "the", "and", "for", "you", "are", "not", "this", "that", "with", "from",
    "have", "was", "were", "been", "will", "can", "but", "what", "all", "when",
    "time", "year", "way", "may", "only", "now", "new", "make", "work", "know",
    "take", "see", "come", "get", "use", "find", "give", "tell", "ask", "try",
    "call", "hand", "about", "after", "back", "just", "good", "where", "every",
    "much", "before", "right", "mean", "old", "great", "same", "because", "here",
    "show", "why", "help", "different"
}

def test_video(video_path, reader):
    """Test a single video and return detection result."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False, []
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    sample_interval = max(1, int(fps * 2))
    
    all_readable_words = []
    frames_tested = 0
    
    for frame_idx in range(0, min(total_frames, sample_interval * 5), sample_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break
        
        frames_tested += 1
        results = reader.readtext(frame, detail=0)
        
        for text in results:
            cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", text)
            words = [w.lower() for w in cleaned.split() if len(w) > 2]
            readable = [w for w in words if w in PT_WORDS or w in EN_WORDS]
            all_readable_words.extend(readable)
    
    cap.release()
    has_subtitle = len(all_readable_words) > 0
    return has_subtitle, all_readable_words

def main():
    print("Inicializando EasyOCR...")
    reader = easyocr.Reader(["pt", "en"], gpu=False, verbose=False)
    print("EasyOCR pronto\n")

    BASE_DIR = Path("/app/storage")
    OK_DIR = BASE_DIR / "OK"
    NOT_OK_DIR = BASE_DIR / "NOT_OK"

    ok_videos = sorted(list(OK_DIR.glob("*.mp4")))[:5]  # Amostra de 5 OK
    not_ok_videos = sorted(list(NOT_OK_DIR.glob("*.mp4")))[:15]  # Amostra de 15 NOT_OK

    print(f"Dataset: {len(ok_videos)} OK + {len(not_ok_videos)} NOT_OK\n")

    results = []

    print("=" * 60)
    print("TESTANDO VIDEOS OK (devem ser aprovados)")
    print("=" * 60)
    for video in ok_videos:
        print(f"\n{video.name}")
        has_sub, words = test_video(str(video), reader)
        correct = (has_sub == False)
        results.append(correct)
        print(f"   Detectou legendas: {has_sub}")
        if words:
            print(f"   Palavras: {words[:10]}")
        status = "CORRETO" if correct else "ERRO"
        print(f"   {status}")

    print("\n" + "=" * 60)
    print("TESTANDO VIDEOS NOT_OK (devem ser banidos)")
    print("=" * 60)
    for video in not_ok_videos:
        print(f"\n{video.name}")
        has_sub, words = test_video(str(video), reader)
        correct = (has_sub == True)
        results.append(correct)
        print(f"   Detectou legendas: {has_sub}")
        if words:
            print(f"   Palavras: {words[:10]}")
        status = "CORRETO" if correct else "ERRO"
        print(f"   {status}")

    print("\n" + "=" * 60)
    print("RESUMO FINAL")
    print("=" * 60)
    correct = sum(results)
    total = len(results)
    accuracy = (correct / total * 100) if total > 0 else 0

    print(f"Total: {total} videos")
    print(f"Acertos: {correct}")
    print(f"Erros: {total - correct}")
    print(f"Acuracia: {accuracy:.1f}%")

    if accuracy >= 90:
        print("\nMETA ATINGIDA! Acuracia >= 90%")
        return 0
    elif accuracy >= 70:
        print("\nAcuracia razoavel (70-90%)")
        return 1
    else:
        print("\nAcuracia baixa (<70%)")
        return 2

if __name__ == "__main__":
    exit(main())
