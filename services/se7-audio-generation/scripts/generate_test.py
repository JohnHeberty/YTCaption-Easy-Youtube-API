#!/usr/bin/env python3
"""
Download Chatterbox model to data/models/ and generate a test audio in data/outputs/.

Usage:
    cd services/se7-audio-generation
    PYTHONPATH=/tmp/chatterbox-space:. HUGGINGFACE_TOKEN=... python3 scripts/generate_test.py
"""
import os
import sys
import time
from pathlib import Path

from app.infrastructure.hf_downloader import (
    T3_FILENAME,
    S3GEN_FILENAME,
    REQUIRED_FILES,
    download_chatterbox_model,
)
from app.core.constants import BYTES_PER_MB

MODEL_DIR = Path("./data/models")
OUTPUT_DIR = Path("./data/outputs")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    ckpt_dir = download_chatterbox_model(MODEL_DIR)

    for f in REQUIRED_FILES:
        exists = (ckpt_dir / f).exists()
        size = (ckpt_dir / f).stat().st_size / BYTES_PER_MB if exists else 0
        status = f"{size:.1f}MB" if exists else "MISSING"
        print(f"  {f}: {status}")

    print(f"[2/5] Loading Chatterbox TTS from local files...")
    t0 = time.time()
    from chatterbox.src.chatterbox.tts import ChatterboxTTS
    model = ChatterboxTTS.from_local(
        ckpt_dir, "cpu",
        t3_filename=T3_FILENAME,
        s3gen_filename=S3GEN_FILENAME,
    )
    print(f"[OK] Model loaded in {time.time() - t0:.1f}s")

    test_text = (
        "Olá! Este é um teste de geração de áudio "
        "usando o modelo Chatterbox em português brasileiro. "
        "Se você está ouvindo esta mensagem, significa que o "
        "serviço de geração de áudio está funcionando corretamente."
    )

    print(f"[3/5] Generating audio ({len(test_text)} chars)...")
    t0 = time.time()
    wav = model.generate(
        text=test_text,
        language_id="pt",
        exaggeration=0.5,
        temperature=0.8,
        cfg_weight=0.5,
    )
    gen_time = time.time() - t0
    print(f"[OK] Audio generated in {gen_time:.1f}s")

    print("[4/5] Saving output...")
    import torch
    import soundfile as sf
    import numpy as np

    audio_np = wav.cpu().numpy()
    if audio_np.ndim > 1:
        audio_np = audio_np.squeeze()
    if audio_np.dtype != np.float32:
        audio_np = audio_np.astype(np.float32)

    sr = 24000
    output_path = str(OUTPUT_DIR / "test_chatterbox_ptbr.wav")
    sf.write(output_path, audio_np, sr)

    duration = len(audio_np) / sr
    size_kb = os.path.getsize(output_path) / 1024
    print(f"[OK] Saved: {output_path}")
    print(f"     Duration: {duration:.1f}s | Size: {size_kb:.0f}KB | Sample rate: {sr}Hz")

    print("[5/5] Summary:")
    print(f"     Model dir: {ckpt_dir}")
    print(f"     Device: cpu")
    print(f"     Text: '{test_text[:60]}...'")
    print(f"     Generation time: {gen_time:.1f}s")
    print(f"     Output: {output_path}")
    print()
    print("SUCCESS!")

    info_path = str(MODEL_DIR / "model_info.txt")
    with open(info_path, "w") as f:
        f.write(f"Model: ResembleAI/Chatterbox-Multilingual-pt-br\n")
        f.write(f"Device: cpu\n")
        f.write(f"Sample rate: 24000\n")
        f.write(f"Model dir: {ckpt_dir}\n")
        f.write(f"Test generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Test output: {output_path}\n")
        f.write(f"Generation time: {gen_time:.1f}s\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
