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

MODEL_DIR = Path("./data/models")
OUTPUT_DIR = Path("./data/outputs")

REPO_ID = "ResembleAI/Chatterbox-Multilingual-pt-br"
BASE_REPO_ID = "ResembleAI/chatterbox"
T3_FILENAME = "t3_pt_br.safetensors"
S3GEN_FILENAME = "s3gen_v3.pt"
REQUIRED_FILES = ["ve.pt", "grapheme_mtl_merged_expanded_v1.json", "conds.pt", T3_FILENAME, S3GEN_FILENAME]


def download_model(model_dir: Path) -> Path:
    token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
    if token:
        from huggingface_hub import login
        login(token=token)

    existing = [f for f in REQUIRED_FILES if (model_dir / f).exists()]
    if len(existing) == len(REQUIRED_FILES):
        print(f"[OK] All {len(REQUIRED_FILES)} model files already in {model_dir}")
        return model_dir

    print(f"[1/5] Downloading model to {model_dir}...")
    model_dir.mkdir(parents=True, exist_ok=True)

    from huggingface_hub import snapshot_download, hf_hub_download

    t0 = time.time()
    base_files = ["ve.pt", "grapheme_mtl_merged_expanded_v1.json", "conds.pt"]
    snapshot_download(
        repo_id=BASE_REPO_ID,
        repo_type="model",
        revision="main",
        allow_patterns=base_files,
        token=token,
        local_dir=str(model_dir),
        local_dir_use_symlinks=False,
    )
    print(f"  Base files: {time.time() - t0:.1f}s")

    t1 = time.time()
    for filename in (T3_FILENAME, S3GEN_FILENAME):
        dest = model_dir / filename
        if not dest.exists():
            hf_hub_download(
                repo_id=REPO_ID,
                filename=filename,
                repo_type="model",
                token=token,
                local_dir=str(model_dir),
                local_dir_use_symlinks=False,
            )
    print(f"  PT-BR files: {time.time() - t1:.1f}s")

    for f in REQUIRED_FILES:
        exists = (model_dir / f).exists()
        size = (model_dir / f).stat().st_size / (1024 * 1024) if exists else 0
        status = f"{size:.1f}MB" if exists else "MISSING"
        print(f"    {f}: {status}")

    print(f"[OK] Model downloaded to {model_dir}")
    return model_dir


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    ckpt_dir = download_model(MODEL_DIR)

    print("[2/5] Loading Chatterbox TTS from local files...")
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
