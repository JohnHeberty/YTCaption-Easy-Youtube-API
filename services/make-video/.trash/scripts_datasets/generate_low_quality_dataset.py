"""
Generate Low-Quality Test Dataset - Sprint 02

Creates synthetic videos with various quality degradations:
- Low contrast (dark text on dark background)
- High compression (JPEG artifacts)
- Motion blur
- Low resolution upscaled
- Noise/grain

Purpose: Test preprocessing improvements on challenging videos
"""

import cv2
import numpy as np
from pathlib import Path
import json
from datetime import datetime


def add_low_contrast(frame, contrast_factor=0.3):
    """Reduce contrast (darken, make text harder to see)"""
    # Convert to float and reduce contrast
    frame_float = frame.astype(float)
    mean = frame_float.mean()
    reduced = mean + (frame_float - mean) * contrast_factor
    return np.clip(reduced, 0, 255).astype(np.uint8)


def add_compression_artifacts(frame, quality=10):
    """Add JPEG compression artifacts (quality: 0-100, lower = more artifacts)"""
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    _, encoded = cv2.imencode('.jpg', frame, encode_param)
    decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    return decoded


def add_motion_blur(frame, kernel_size=15):
    """Add horizontal motion blur"""
    kernel = np.zeros((kernel_size, kernel_size))
    kernel[int((kernel_size - 1) / 2), :] = np.ones(kernel_size)
    kernel = kernel / kernel_size
    blurred = cv2.filter2D(frame, -1, kernel)
    return blurred


def add_noise(frame, noise_level=25):
    """Add Gaussian noise"""
    noise = np.random.normal(0, noise_level, frame.shape).astype(np.int16)
    noisy = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return noisy


def downscale_upscale(frame, scale_factor=0.3):
    """Simulate low-res capture by downscaling then upscaling"""
    h, w = frame.shape[:2]
    small = cv2.resize(frame, (int(w * scale_factor), int(h * scale_factor)), interpolation=cv2.INTER_AREA)
    upscaled = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
    return upscaled


def create_low_quality_video_with_subs(
    output_path, 
    width=1920, 
    height=1080, 
    fps=30, 
    duration=3,
    degradation='low_contrast',
    has_subtitles=True
):
    """
    Create low-quality video with optional burned-in subtitles
    
    Args:
        output_path: Output video path
        width, height: Video dimensions
        fps: Frames per second
        duration: Duration in seconds
        degradation: Type of quality degradation
            - 'low_contrast': Dark scene, hard to see text
            - 'compressed': Heavy compression artifacts
            - 'motion_blur': Blurred frames
            - 'noisy': High noise/grain
            - 'low_res': Upscaled from low resolution
            - 'combined': Multiple degradations
        has_subtitles: Add burned-in subtitles at bottom
    
    Returns:
        dict with metadata
    """
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    
    total_frames = fps * duration
    subtitle_text = "Low quality subtitle test" if has_subtitles else None
    
    # Subtitle positioning (bottom 25%)
    subtitle_y = int(height * 0.85)
    subtitle_height = int(height * 0.10)
    
    for frame_idx in range(total_frames):
        # Create base frame (dark gray background)
        if degradation in ['low_contrast', 'combined']:
            # Dark background to make text harder to see
            base_color = (40, 40, 40)  # Very dark gray
        else:
            # Medium gray background
            base_color = (100, 100, 100)
        
        frame = np.full((height, width, 3), base_color, dtype=np.uint8)
        
        # Add animated element (moving circle)
        circle_x = int((frame_idx / total_frames) * width)
        circle_y = height // 4
        cv2.circle(frame, (circle_x, circle_y), 30, (150, 150, 150), -1)
        
        # Add subtitle if needed
        if has_subtitles:
            # Draw subtitle bar
            cv2.rectangle(
                frame,
                (0, subtitle_y),
                (width, subtitle_y + subtitle_height),
                (30, 30, 30),  # Dark subtitle bar
                -1
            )
            
            # Calculate text position (centered)
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = width / 1920  # Scale with resolution
            thickness = max(1, int(2 * font_scale))
            
            text_size = cv2.getTextSize(subtitle_text, font, font_scale, thickness)[0]
            text_x = (width - text_size[0]) // 2
            text_y = subtitle_y + (subtitle_height + text_size[1]) // 2
            
            # Draw text (light gray on dark background = low contrast)
            text_color = (180, 180, 180) if degradation in ['low_contrast', 'combined'] else (255, 255, 255)
            cv2.putText(frame, subtitle_text, (text_x, text_y), font, font_scale, text_color, thickness, cv2.LINE_AA)
        
        # Apply degradation
        if degradation == 'low_contrast':
            frame = add_low_contrast(frame, contrast_factor=0.4)
        
        elif degradation == 'compressed':
            frame = add_compression_artifacts(frame, quality=5)
        
        elif degradation == 'motion_blur':
            frame = add_motion_blur(frame, kernel_size=11)
        
        elif degradation == 'noisy':
            frame = add_noise(frame, noise_level=30)
        
        elif degradation == 'low_res':
            frame = downscale_upscale(frame, scale_factor=0.25)
        
        elif degradation == 'combined':
            # Apply multiple degradations
            frame = add_low_contrast(frame, contrast_factor=0.3)
            frame = add_compression_artifacts(frame, quality=8)
            frame = add_noise(frame, noise_level=20)
        
        out.write(frame)
    
    out.release()
    
    file_size = Path(output_path).stat().st_size
    
    metadata = {
        'filename': Path(output_path).name,
        'resolution': f"{width}x{height}",
        'width': width,
        'height': height,
        'fps': fps,
        'duration': duration,
        'has_subtitles': has_subtitles,
        'degradation': degradation,
        'file_size_kb': round(file_size / 1024, 2),
        'generated_at': datetime.now().isoformat()
    }
    
    return metadata


def generate_low_quality_dataset(output_dir='storage/validation/low_quality', num_videos_per_type=2):
    """
    Generate complete low-quality test dataset
    
    Creates videos with various degradations:
    - low_contrast: 2 WITH + 2 WITHOUT
    - compressed: 2 WITH + 2 WITHOUT
    - motion_blur: 2 WITH + 2 WITHOUT
    - noisy: 2 WITH + 2 WITHOUT
    - low_res: 2 WITH + 2 WITHOUT
    - combined: 2 WITH + 2 WITHOUT
    
    Total: 24 videos (12 WITH + 12 WITHOUT subtitles)
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    degradations = ['low_contrast', 'compressed', 'motion_blur', 'noisy', 'low_res', 'combined']
    
    all_metadata = []
    video_count = 0
    
    print("=" * 70)
    print("🎬 GENERATING LOW-QUALITY TEST DATASET - SPRINT 02")
    print("=" * 70)
    print(f"Output: {output_path}")
    print(f"Degradations: {len(degradations)}")
    print(f"Videos per degradation: {num_videos_per_type} WITH + {num_videos_per_type} WITHOUT")
    print(f"Total videos: {len(degradations) * num_videos_per_type * 2}")
    print()
    
    for degradation in degradations:
        print(f"\n📹 Generating {degradation} videos...")
        
        # Generate WITH subtitles
        for i in range(num_videos_per_type):
            video_num = video_count + 1
            filename = f"low_quality_{degradation:15s}_WITH_{i+1:03d}.mp4"
            filepath = output_path / filename
            
            metadata = create_low_quality_video_with_subs(
                filepath,
                width=1920,
                height=1080,
                fps=30,
                duration=3,
                degradation=degradation,
                has_subtitles=True
            )
            all_metadata.append(metadata)
            video_count += 1
            
            print(f"  ✅ {filename:50s} ({metadata['file_size_kb']:6.1f} KB)")
        
        # Generate WITHOUT subtitles
        for i in range(num_videos_per_type):
            video_num = video_count + 1
            filename = f"low_quality_{degradation:15s}_WITHOUT_{i+1:03d}.mp4"
            filepath = output_path / filename
            
            metadata = create_low_quality_video_with_subs(
                filepath,
                width=1920,
                height=1080,
                fps=30,
                duration=3,
                degradation=degradation,
                has_subtitles=False
            )
            all_metadata.append(metadata)
            video_count += 1
            
            print(f"  ✅ {filename:50s} ({metadata['file_size_kb']:6.1f} KB)")
    
    # Create ground truth JSON
    ground_truth = {
        'dataset_info': {
            'name': 'low_quality_test_dataset_sprint_02',
            'total_videos': len(all_metadata),
            'with_subtitles': sum(1 for m in all_metadata if m['has_subtitles']),
            'without_subtitles': sum(1 for m in all_metadata if not m['has_subtitles']),
            'degradations': degradations,
            'generated_at': datetime.now().isoformat(),
        },
        'videos': all_metadata
    }
    
    ground_truth_path = output_path / 'ground_truth.json'
    with open(ground_truth_path, 'w') as f:
        json.dump(ground_truth, f, indent=2)
    
    # Summary
    total_size = sum(m['file_size_kb'] for m in all_metadata)
    
    print("\n" + "=" * 70)
    print("✅ DATASET GENERATION COMPLETE!")
    print("=" * 70)
    print(f"Total videos: {len(all_metadata)}")
    print(f"  - WITH subtitles:    {ground_truth['dataset_info']['with_subtitles']}")
    print(f"  - WITHOUT subtitles: {ground_truth['dataset_info']['without_subtitles']}")
    print(f"Total size: {total_size / 1024:.1f} MB")
    print(f"Ground truth: {ground_truth_path}")
    print()
    
    # Per degradation summary
    print("Per-Degradation Summary:")
    for degradation in degradations:
        deg_videos = [m for m in all_metadata if m['degradation'] == degradation]
        deg_size = sum(m['file_size_kb'] for m in deg_videos)
        print(f"  {degradation:15s}: {len(deg_videos)} videos, {deg_size/1024:.1f} MB")
    
    return ground_truth


if __name__ == "__main__":
    result = generate_low_quality_dataset(num_videos_per_type=2)
    print("\n🎉 Low-quality dataset ready for Sprint 02 testing!")
