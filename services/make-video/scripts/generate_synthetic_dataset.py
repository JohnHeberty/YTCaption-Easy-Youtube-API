#!/usr/bin/env python3
"""
Synthetic Dataset Generator for Subtitle Detection Testing

Gera vídeos sintéticos COM e SEM legendas burned-in para testar VideoValidator
e atingir meta de 90% de acurácia.

Características:
- Vídeos simples com cenas variadas (gradientes, formas, cores)
- Legendas burned-in em posição bottom (típica)
- Ground truth preciso e verificável
- Balanceado (50% WITH, 50% WITHOUT)

Usage:
    python scripts/generate_synthetic_dataset.py --num-videos 30 --duration 5
"""

import cv2
import numpy as np
from pathlib import Path
import json
from datetime import datetime
import argparse
from typing import List, Tuple, Dict
import random


class SyntheticVideoGenerator:
    """Gerador de vídeos sintéticos para teste de detecção de legendas"""
    
    def __init__(self, output_dir: Path, fps: int = 30):
        """
        Args:
            output_dir: Diretório de saída para vídeos
            fps: Frames por segundo
        """
        self.output_dir = output_dir
        self.fps = fps
        self.resolution = (1920, 1080)  # Full HD
        
        # Textos de legendas (variados)
        self.subtitle_texts = [
            "This is a test subtitle",
            "Legendas em português também",
            "Another example of subtitle text",
            "Testing OCR detection capabilities",
            "Multiple words in this subtitle line",
            "Short sub",
            "Very long subtitle text that spans more characters to test OCR",
            "Numbers 12345 and symbols !@#$%",
            "UPPERCASE SUBTITLE TEXT",
            "lowercase subtitle text",
            "MiXeD CaSe TeXt HeRe",
            "Testing with -- special characters",
            "Subtitle numero uno",
            "The quick brown fox jumps",
            "Hello world from subtitles",
        ]
        
        # Cores de fundo (variadas para simular diferentes cenas)
        self.background_colors = [
            (30, 30, 30),    # Dark gray
            (100, 50, 50),   # Dark blue
            (50, 100, 50),   # Dark green
            (50, 50, 100),   # Dark red
            (70, 70, 70),    # Medium gray
            (40, 80, 120),   # Brown
        ]
    
    def create_video_with_subtitles(
        self, 
        filename: str, 
        duration: int = 5,
        subtitle_position: str = 'bottom'
    ) -> Path:
        """
        Cria vídeo COM legendas burned-in
        
        Args:
            filename: Nome do arquivo (ex: 'video_001.mp4')
            duration: Duração em segundos
            subtitle_position: Posição da legenda ('bottom', 'top', 'center')
        
        Returns:
            Path do vídeo criado
        """
        output_path = self.output_dir / filename
        
        # Configurar VideoWriter
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(
            str(output_path), 
            fourcc, 
            self.fps, 
            self.resolution
        )
        
        total_frames = duration * self.fps
        subtitle_text = random.choice(self.subtitle_texts)
        bg_color = random.choice(self.background_colors)
        
        print(f"  Criando {filename} ({duration}s, {total_frames} frames)")
        print(f"    Legenda: '{subtitle_text}'")
        
        for frame_idx in range(total_frames):
            # Criar frame com background
            frame = self._create_background(bg_color, frame_idx, total_frames)
            
            # Adicionar legenda burned-in
            frame = self._add_subtitle(frame, subtitle_text, subtitle_position)
            
            out.write(frame)
        
        out.release()
        print(f"  ✅ {filename} criado ({output_path.stat().st_size // 1024} KB)")
        
        return output_path
    
    def create_video_without_subtitles(
        self, 
        filename: str, 
        duration: int = 5
    ) -> Path:
        """
        Cria vídeo SEM legendas
        
        Args:
            filename: Nome do arquivo
            duration: Duração em segundos
        
        Returns:
            Path do vídeo criado
        """
        output_path = self.output_dir / filename
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(
            str(output_path), 
            fourcc, 
            self.fps, 
            self.resolution
        )
        
        total_frames = duration * self.fps
        bg_color = random.choice(self.background_colors)
        
        print(f"  Criando {filename} ({duration}s, {total_frames} frames)")
        print(f"    SEM legendas")
        
        for frame_idx in range(total_frames):
            # Criar frame com background (sem legenda)
            frame = self._create_background(bg_color, frame_idx, total_frames)
            out.write(frame)
        
        out.release()
        print(f"  ✅ {filename} criado ({output_path.stat().st_size // 1024} KB)")
        
        return output_path
    
    def _create_background(
        self, 
        base_color: Tuple[int, int, int], 
        frame_idx: int, 
        total_frames: int
    ) -> np.ndarray:
        """
        Cria background variado para simular cena de vídeo
        
        Args:
            base_color: Cor base (B, G, R)
            frame_idx: Índice do frame atual
            total_frames: Total de frames do vídeo
        
        Returns:
            Frame BGR (1080, 1920, 3)
        """
        height, width = self.resolution[1], self.resolution[0]
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Criar gradiente vertical suave
        for y in range(height):
            color_factor = y / height
            color = tuple(int(c * (0.7 + 0.3 * color_factor)) for c in base_color)
            frame[y, :] = color
        
        # Adicionar formas geométricas (simular elementos de cena)
        progress = frame_idx / total_frames
        
        # Círculo animado
        circle_x = int(width * 0.3 + width * 0.4 * progress)
        circle_y = int(height * 0.3)
        cv2.circle(frame, (circle_x, circle_y), 50, (150, 150, 150), -1)
        
        # Retângulo
        rect_x = int(width * 0.6)
        rect_y = int(height * 0.5 + 50 * np.sin(progress * 2 * np.pi))
        cv2.rectangle(
            frame, 
            (rect_x, rect_y), 
            (rect_x + 100, rect_y + 60), 
            (180, 180, 180), 
            -1
        )
        
        return frame
    
    def _add_subtitle(
        self, 
        frame: np.ndarray, 
        text: str, 
        position: str = 'bottom'
    ) -> np.ndarray:
        """
        Adiciona legenda burned-in no frame
        
        Args:
            frame: Frame BGR
            text: Texto da legenda
            position: Posição ('bottom', 'top', 'center')
        
        Returns:
            Frame com legenda
        """
        height, width = frame.shape[:2]
        
        # Configuração de texto
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.2
        thickness = 3
        color = (255, 255, 255)  # Branco
        
        # Calcular tamanho do texto
        (text_width, text_height), baseline = cv2.getTextSize(
            text, font, font_scale, thickness
        )
        
        # Determinar posição
        if position == 'bottom':
            x = (width - text_width) // 2
            y = height - 100  # 100px do bottom
        elif position == 'top':
            x = (width - text_width) // 2
            y = 100  # 100px do top
        else:  # center
            x = (width - text_width) // 2
            y = (height + text_height) // 2
        
        # Adicionar fundo preto semitransparente (típico de legendas)
        padding = 20
        overlay = frame.copy()
        cv2.rectangle(
            overlay,
            (x - padding, y - text_height - padding),
            (x + text_width + padding, y + baseline + padding),
            (0, 0, 0),
            -1
        )
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
        
        # Adicionar texto
        cv2.putText(
            frame, text, (x, y), 
            font, font_scale, color, thickness, cv2.LINE_AA
        )
        
        return frame
    
    def generate_balanced_dataset(
        self, 
        num_videos: int = 30, 
        duration: int = 5
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Gera dataset balanceado (50% WITH, 50% WITHOUT)
        
        Args:
            num_videos: Total de vídeos (será dividido igualmente)
            duration: Duração de cada vídeo em segundos
        
        Returns:
            Tuple (videos_with_subs, videos_without_subs)
        """
        num_positive = num_videos // 2
        num_negative = num_videos - num_positive
        
        print(f"\n🎬 Gerando Dataset Sintético:")
        print(f"   Total: {num_videos} vídeos ({duration}s cada)")
        print(f"   WITH subtitles: {num_positive}")
        print(f"   WITHOUT subtitles: {num_negative}")
        print()
        
        videos_with = []
        videos_without = []
        
        # Gerar vídeos COM legendas
        print("📹 Gerando vídeos COM legendas...")
        for i in range(num_positive):
            filename = f"synthetic_WITH_{i+1:03d}.mp4"
            path = self.create_video_with_subtitles(filename, duration)
            
            videos_with.append({
                "filename": filename,
                "has_subtitles": True,
                "subtitle_type": "burned_in",
                "expected_result": True,
                "duration_seconds": duration,
                "resolution": f"{self.resolution[0]}x{self.resolution[1]}",
                "generated_at": datetime.now().isoformat()
            })
        
        print()
        
        # Gerar vídeos SEM legendas
        print("📹 Gerando vídeos SEM legendas...")
        for i in range(num_negative):
            filename = f"synthetic_WITHOUT_{i+1:03d}.mp4"
            path = self.create_video_without_subtitles(filename, duration)
            
            videos_without.append({
                "filename": filename,
                "has_subtitles": False,
                "subtitle_type": None,
                "expected_result": False,
                "duration_seconds": duration,
                "resolution": f"{self.resolution[0]}x{self.resolution[1]}",
                "generated_at": datetime.now().isoformat()
            })
        
        print()
        print(f"✅ Dataset gerado: {num_videos} vídeos")
        
        return videos_with, videos_without


def create_ground_truth_json(
    videos_with: List[Dict],
    videos_without: List[Dict],
    output_path: Path
) -> None:
    """
    Cria arquivo ground_truth.json com metadados completos
    
    Args:
        videos_with: Lista de vídeos COM legendas
        videos_without: Lista de vídeos SEM legendas
        output_path: Path para salvar ground_truth.json
    """
    ground_truth = {
        "dataset_info": {
            "name": "Synthetic Subtitle Detection Dataset",
            "version": "1.0.0",
            "created_at": datetime.now().isoformat(),
            "created_by": "generate_synthetic_dataset.py",
            "description": "Dataset sintético para teste de detecção de legendas burned-in",
            "total_videos": len(videos_with) + len(videos_without),
            "positive_samples": len(videos_with),
            "negative_samples": len(videos_without),
            "balance_ratio": f"{len(videos_with)}/{len(videos_with) + len(videos_without)} ({len(videos_with)/(len(videos_with) + len(videos_without))*100:.1f}%)"
        },
        "videos": videos_with + videos_without
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(ground_truth, f, indent=2, ensure_ascii=False)
    
    print(f"📄 Ground truth salvo: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Gera dataset sintético para teste de detecção de legendas"
    )
    parser.add_argument(
        '--num-videos', 
        type=int, 
        default=30,
        help='Total de vídeos a gerar (default: 30)'
    )
    parser.add_argument(
        '--duration', 
        type=int, 
        default=5,
        help='Duração de cada vídeo em segundos (default: 5)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='storage/validation/synthetic',
        help='Diretório de saída (default: storage/validation/synthetic)'
    )
    
    args = parser.parse_args()
    
    # Criar diretórios de saída
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("🎬 SYNTHETIC DATASET GENERATOR")
    print("=" * 70)
    print(f"Output: {output_dir}")
    print(f"Videos: {args.num_videos} ({args.duration}s cada)")
    print()
    
    # Gerar dataset
    generator = SyntheticVideoGenerator(output_dir)
    videos_with, videos_without = generator.generate_balanced_dataset(
        num_videos=args.num_videos,
        duration=args.duration
    )
    
    # Criar ground truth
    gt_path = output_dir / 'ground_truth.json'
    create_ground_truth_json(videos_with, videos_without, gt_path)
    
    print()
    print("=" * 70)
    print("✅ DATASET SINTÉTICO CRIADO COM SUCESSO!")
    print("=" * 70)
    print(f"📹 Vídeos: {args.num_videos}")
    print(f"📊 Balance: {len(videos_with)} WITH / {len(videos_without)} WITHOUT")
    print(f"📁 Localização: {output_dir.absolute()}")
    print(f"📄 Ground truth: {gt_path.absolute()}")
    print()
    print("🔧 Próximo passo: Validar com PaddleOCR")
    print("   python scripts/validate_synthetic_dataset.py")


if __name__ == '__main__':
    main()
