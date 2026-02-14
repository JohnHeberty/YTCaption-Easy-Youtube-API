#!/usr/bin/env python3
"""
Generate Edge Case Dataset - Sprint 04
Creates synthetic videos with subtitles in non-standard positions (top, sides, center)

Usage:
    python scripts/generate_edge_case_dataset.py

Output:
    storage/validation/edge_cases/ (16 videos + ground_truth.json)
"""

import os
import json
import cv2
import numpy as np
from pathlib import Path

# Configuration
OUTPUT_DIR = Path("storage/validation/edge_cases")
RESOLUTION = (1920, 1080)  # 1080p
FPS = 30
DURATION = 3.0  # seconds
FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 1.2
FONT_THICKNESS = 2

# ROI Configurations (percentage of frame)
ROI_POSITIONS = {
    'top': {
        'y_range': (0.05, 0.20),  # Top 25% (with 5% margin from edge)
        'x_range': (0.1, 0.9),    # Centered horizontally
        'description': 'Foreign film, dual-language subtitles'
    },
    'left': {
        'y_range': (0.4, 0.6),    # Vertical center
        'x_range': (0.05, 0.15),  # Left 20%
        'description': 'YouTube Shorts, TikTok vertical captions'
    },
    'right': {
        'y_range': (0.4, 0.6),    # Vertical center
        'x_range': (0.85, 0.95),  # Right 20%
        'description': 'Social media side captions'
    },
    'center': {
        'y_range': (0.4, 0.6),    # Center 30% vertically
        'x_range': (0.35, 0.65),  # Center 30% horizontally
        'description': 'Embedded text, hardcoded overlays'
    }
}

# Sample subtitles
SAMPLE_TEXTS = [
    "This is a test subtitle",
    "Sample caption text here",
    "Edge case detection test",
    "Multi-ROI fallback system",
    "Top position subtitle",
    "Side caption example"
]


def create_background_frame(resolution, color_variation=True):
    """Create a single background frame with gradient"""
    height, width = resolution[1], resolution[0]
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    
    if color_variation:
        # Create gradient background (random colors)
        color1 = np.random.randint(20, 100, 3)
        color2 = np.random.randint(100, 180, 3)
        
        for y in range(height):
            ratio = y / height
            color = color1 * (1 - ratio) + color2 * ratio
            frame[y, :] = color.astype(np.uint8)
    else:
        # Solid dark background
        frame[:] = (30, 30, 30)
    
    return frame


def add_text_to_frame(frame, text, position_config, text_color=(255, 255, 255)):
    """Add text to frame at specified ROI position"""
    height, width = frame.shape[:2]
    
    # Calculate position based on ROI config
    y_min, y_max = position_config['y_range']
    x_min, x_max = position_config['x_range']
    
    # Center text within ROI
    y_center = int(height * (y_min + y_max) / 2)
    x_center = int(width * (x_min + x_max) / 2)
    
    # Get text size
    (text_width, text_height), baseline = cv2.getTextSize(
        text, FONT, FONT_SCALE, FONT_THICKNESS
    )
    
    # Calculate text origin (bottom-left corner)
    text_x = x_center - text_width // 2
    text_y = y_center + text_height // 2
    
    # Add black background box for readability
    padding = 10
    box_x1 = text_x - padding
    box_y1 = text_y - text_height - padding
    box_x2 = text_x + text_width + padding
    box_y2 = text_y + baseline + padding
    
    cv2.rectangle(frame, (box_x1, box_y1), (box_x2, box_y2), (0, 0, 0), -1)
    
    # Add text
    cv2.putText(
        frame, text, (text_x, text_y),
        FONT, FONT_SCALE, text_color, FONT_THICKNESS, cv2.LINE_AA
    )
    
    return frame


def generate_video_with_subtitles(output_path, position_name, position_config, text, has_text=True):
    """Generate a single video with text at specified position"""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, FPS, RESOLUTION)
    
    total_frames = int(DURATION * FPS)
    
    for frame_idx in range(total_frames):
        # Create background
        frame = create_background_frame(RESOLUTION, color_variation=True)
        
        # Add some noise for realism
        noise = np.random.randint(-10, 10, frame.shape, dtype=np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
        if has_text:
            # Add text at specified position
            frame = add_text_to_frame(frame, text, position_config)
        
        out.write(frame)
    
    out.release()
    print(f"✅ Created: {output_path.name} ({'WITH' if has_text else 'WITHOUT'} text at {position_name})")


def generate_multi_position_video(output_path, positions, texts):
    """Generate video with text at multiple positions simultaneously"""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, FPS, RESOLUTION)
    
    total_frames = int(DURATION * FPS)
    
    for frame_idx in range(total_frames):
        frame = create_background_frame(RESOLUTION, color_variation=True)
        noise = np.random.randint(-10, 10, frame.shape, dtype=np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
        # Add text at multiple positions
        for pos_name, text in zip(positions, texts):
            if pos_name in ROI_POSITIONS:
                frame = add_text_to_frame(frame, text, ROI_POSITIONS[pos_name])
        
        out.write(frame)
    
    out.release()
    print(f"✅ Created: {output_path.name} (multi-position)")


def main():
    """Generate complete edge case dataset"""
    print("=" * 60)
    print("SPRINT 04: Generate Edge Case Dataset")
    print("=" * 60)
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Resolution: {RESOLUTION[0]}x{RESOLUTION[1]} (1080p)")
    print(f"Duration: {DURATION}s @ {FPS} FPS")
    print()
    
    # Create output directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for pos_name in ROI_POSITIONS.keys():
        (OUTPUT_DIR / pos_name).mkdir(exist_ok=True)
    (OUTPUT_DIR / 'multi_position').mkdir(exist_ok=True)
    
    ground_truth = {}
    video_count = 0
    
    # Generate single-position videos (top, left, right, center)
    print("\n1. Generating SINGLE-POSITION videos:")
    print("-" * 60)
    
    for pos_name, pos_config in ROI_POSITIONS.items():
        print(f"\nPosition: {pos_name.upper()} - {pos_config['description']}")
        
        # WITH text (2 videos)
        for i in range(1, 3):
            video_name = f"{pos_name}_with_{i:03d}.mp4"
            video_path = OUTPUT_DIR / pos_name / video_name
            text = SAMPLE_TEXTS[(video_count + i) % len(SAMPLE_TEXTS)]
            
            generate_video_with_subtitles(
                video_path, pos_name, pos_config, text, has_text=True
            )
            
            ground_truth[video_name] = {
                'has_subtitles': True,
                'position': pos_name,
                'text': text,
                'roi_config': pos_config
            }
            video_count += 1
        
        # WITHOUT text (1 video)
        video_name = f"{pos_name}_without_001.mp4"
        video_path = OUTPUT_DIR / pos_name / video_name
        
        generate_video_with_subtitles(
            video_path, pos_name, pos_config, "", has_text=False
        )
        
        ground_truth[video_name] = {
            'has_subtitles': False,
            'position': pos_name,
            'text': None,
            'roi_config': pos_config
        }
        video_count += 1
    
    # Generate multi-position videos
    print("\n\n2. Generating MULTI-POSITION videos:")
    print("-" * 60)
    
    multi_scenarios = [
        {
            'name': 'top_and_bottom',
            'positions': ['top', 'bottom'],
            'texts': ['English subtitle', 'Portuguese legenda'],
            'has_subtitles': True
        },
        {
            'name': 'left_and_right',
            'positions': ['left', 'right'],
            'texts': ['Left caption', 'Right caption'],
            'has_subtitles': True
        },
        {
            'name': 'all_positions',
            'positions': ['top', 'left', 'right', 'center'],
            'texts': ['Top', 'Left', 'Right', 'Center'],
            'has_subtitles': True
        },
        {
            'name': 'no_text',
            'positions': [],
            'texts': [],
            'has_subtitles': False
        }
    ]
    
    # Add bottom config for multi-position videos
    ROI_POSITIONS['bottom'] = {
        'y_range': (0.80, 0.95),
        'x_range': (0.1, 0.9),
        'description': 'Standard bottom subtitle'
    }
    
    for scenario in multi_scenarios:
        video_name = f"{scenario['name']}_001.mp4"
        video_path = OUTPUT_DIR / 'multi_position' / video_name
        
        if scenario['has_subtitles']:
            generate_multi_position_video(
                video_path, scenario['positions'], scenario['texts']
            )
        else:
            # Generate video without text
            generate_video_with_subtitles(
                video_path, 'none', ROI_POSITIONS['center'], "", has_text=False
            )
        
        ground_truth[video_name] = {
            'has_subtitles': scenario['has_subtitles'],
            'positions': scenario['positions'],
            'texts': scenario['texts'] if scenario['has_subtitles'] else None
        }
        video_count += 1
    
    # Save ground truth
    ground_truth_path = OUTPUT_DIR / 'ground_truth.json'
    with open(ground_truth_path, 'w') as f:
        json.dump(ground_truth, f, indent=2)
    
    print(f"\n✅ Saved ground truth: {ground_truth_path}")
    
    # Calculate dataset size
    total_size = sum(
        f.stat().st_size 
        for f in OUTPUT_DIR.rglob('*.mp4')
    ) / (1024 * 1024)
    
    # Summary
    print("\n" + "=" * 60)
    print("DATASET GENERATION COMPLETE")
    print("=" * 60)
    print(f"Total videos: {video_count}")
    print(f"Total size: {total_size:.1f} MB")
    print(f"\nBreakdown:")
    print(f"  - Top position: 3 videos (2 WITH + 1 WITHOUT)")
    print(f"  - Left position: 3 videos (2 WITH + 1 WITHOUT)")
    print(f"  - Right position: 3 videos (2 WITH + 1 WITHOUT)")
    print(f"  - Center position: 3 videos (2 WITH + 1 WITHOUT)")
    print(f"  - Multi-position: 4 videos (3 WITH + 1 WITHOUT)")
    print(f"\nGround truth: {ground_truth_path}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("\n🎉 Edge case dataset ready for Sprint 04 testing!")


if __name__ == "__main__":
    main()
