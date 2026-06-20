#!/usr/bin/env python3
"""Standalone script: voice clone + test audio generation using Chatterbox directly."""
import os
import sys
import time

# Setup paths
ROOT = "/root/YTCaption-Easy-Youtube-API"
sys.path.insert(0, ROOT)
os.chdir(os.path.join(ROOT, "services/se7-audio-generation"))

from dotenv import load_dotenv
load_dotenv()

import torch
import soundfile as sf
from chatterbox.src.chatterbox.tts import ChatterboxTTS

VOICE_PATH = "data/voices/test5_clone.wav"
OUTPUT_PATH = "data/outputs/test_clone_output.wav"
MODEL_DIR = "data/models"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
T3_FILENAME = "t3_pt_br.safetensors"
S3GEN_FILENAME = "s3gen_v3.pt"
SAMPLE_RATE = 24000

TEST_TEXT = "Olá! Este é um teste de clonagem de voz. Estou usando o modelo Chatterbox para gerar áudio com a voz clonada."

def main():
    os.makedirs("data/outputs", exist_ok=True)

    print(f"Device: {DEVICE}")
    print(f"Voice: {VOICE_PATH}")
    print(f"Text: {TEST_TEXT[:80]}...")

    # Login HF
    token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
    if token:
        from huggingface_hub import login
        login(token=token)
        print("HF token loaded.")

    # Load model
    print("Loading Chatterbox model...")
    t0 = time.time()
    model = ChatterboxTTS.from_local(
        MODEL_DIR, DEVICE,
        t3_filename=T3_FILENAME,
        s3gen_filename=S3GEN_FILENAME,
    )
    print(f"Model loaded in {time.time() - t0:.1f}s")

    # Generate
    print("Generating audio with voice clone...")
    t1 = time.time()
    wav = model.generate(
        text=TEST_TEXT,
        audio_prompt_path=VOICE_PATH,
        language_id="pt",
        exaggeration=0.5,
        temperature=0.8,
        cfg_weight=0.5,
    )
    gen_time = time.time() - t1
    print(f"Generated in {gen_time:.1f}s")

    # Save
    audio_np = wav.squeeze().cpu().numpy()
    sf.write(OUTPUT_PATH, audio_np, SAMPLE_RATE)
    duration = len(audio_np) / SAMPLE_RATE
    size = os.path.getsize(OUTPUT_PATH) / 1024

    print(f"\n=== RESULTADO ===")
    print(f"Arquivo: {OUTPUT_PATH}")
    print(f"Duração: {duration:.1f}s")
    print(f"Tamanho: {size:.0f}KB")
    print(f"Sample rate: {SAMPLE_RATE}Hz")
    print(f"Tempo de geração: {gen_time:.1f}s")
    print("OK!")

if __name__ == "__main__":
    main()
