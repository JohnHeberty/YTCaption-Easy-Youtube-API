#!/usr/bin/env python3
"""
Script para garantir que TODOS os vídeos estão em formato H264
compatível com OpenCV.

Resolve o problema de AV1 codec que não é suportado.
"""
import os
import json
import subprocess
from pathlib import Path


def get_video_codec(video_path):
    """Retorna o codec do vídeo"""
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ], capture_output=True, text=True)
        return result.stdout.strip()
    except Exception as e:
        return None


def convert_to_h264(input_path, output_path):
    """Converte vídeo para H264"""
    print(f"  Convertendo: {input_path}")
    try:
        subprocess.run([
            'ffmpeg', '-y', '-i', input_path,
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            output_path
        ], check=True, capture_output=True)
        return True
    except Exception as e:
        print(f"    ❌ Erro: {e}")
        return False


def main():
    base_path = Path('storage/validation')
    
    for folder in ['sample_OK', 'sample_NOT_OK']:
        folder_path = base_path / folder
        ground_truth_path = folder_path / 'ground_truth.json'
        
        if not ground_truth_path.exists():
            continue
        
        print(f"\n{'='*80}")
        print(f"📁 Processando: {folder}")
        print('='*80 + '\n')
        
        with open(ground_truth_path) as f:
            data = json.load(f)
        
        videos = data['videos']
        print(f"Total de vídeos: {len(videos)}\n")
        
        for i, video in enumerate(videos, 1):
            filename = video['filename']
            video_path = folder_path / filename
            
            if not video_path.exists():
                print(f"[{i}/{len(videos)}] ⚠️  {filename}: Arquivo não encontrado")
                continue
            
            codec = get_video_codec(str(video_path))
            
            if codec == 'h264':
                print(f"[{i}/{len(videos)}] ✅ {filename}: H264 OK")
            else:
                print(f"[{i}/{len(videos)}] 🔄 {filename}: {codec} -> H264")
                temp_path = folder_path / f"temp_{filename}"
                
                if convert_to_h264(str(video_path), str(temp_path)):
                    # Substituir original
                    os.rename(str(temp_path), str(video_path))
                    print(f"    ✅ Convertido com sucesso")
                else:
                    if temp_path.exists():
                        os.remove(str(temp_path))
                    print(f"    ❌ Falha na conversão")
    
    print(f"\n{'='*80}")
    print("✅ Processamento concluído!")
    print('='*80 + '\n')


if __name__ == "__main__":
    main()
