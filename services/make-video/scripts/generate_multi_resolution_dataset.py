"""
Generate multi-resolution test videos for Sprint 01

Creates synthetic videos in:
- 720p (1280x720)
- 1080p (1920x1080)  
- 1440p (2560x1440)
- 4K (3840x2160)

Each resolution: 2 WITH + 2 WITHOUT = 8 videos per resolution
Total: 32 videos for robust testing
"""
import cv2
import numpy as np
from pathlib import Path
import json
from datetime import datetime


def generate_multi_resolution_dataset(output_dir: str = 'storage/validation/multi_resolution'):
    """Generate test videos in multiple resolutions"""
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Resolution configurations
    resolutions = [
        ('720p', 1280, 720),
        ('1080p', 1920, 1080),
        ('1440p', 2560, 1440),
        ('4K', 3840, 2160)
    ]
    
    fps = 30
    duration_seconds = 3
    total_frames = fps * duration_seconds
    
    videos_metadata = []
    
    print(f"🎬 Generating multi-resolution test dataset...")
    print(f"   Output: {output_dir}")
    print(f"   Resolutions: {len(resolutions)}")
    print(f"   Videos per resolution: 4 (2 WITH + 2 WITHOUT)")
    print(f"   Total videos: {len(resolutions) * 4}")
    print("=" * 70)
    
    for res_name, width, height in resolutions:
        print(f"\n📐 Generating {res_name} ({width}x{height}) videos...")
        
        # Calculate subtitle bar position (bottom 25%)
        subtitle_bar_height = int(height * 0.25)
        subtitle_bar_y_start = height - subtitle_bar_height
        
        # Font scale proportional to resolution
        base_scale = 1.0  # For 1080p
        font_scale = (height / 1080) * base_scale
        font_thickness = max(2, int(font_scale * 2))
        
        # Generate 2 WITH subtitles
        for i in range(1, 3):
            filename = f'{res_name}_WITH_{i:02d}.mp4'
            video_path = output_path / filename
            
            subtitle_texts = [
                "Multi-resolution subtitle detection test",
                f"Resolution: {width}x{height} ({res_name})"
            ]
            subtitle_text = subtitle_texts[(i-1) % len(subtitle_texts)]
            
            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))
            
            for frame_num in range(total_frames):
                # Create gradient background
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                
                # Gradient from dark to light
                gradient_value = int(30 + (frame_num / total_frames) * 50)
                frame[:, :] = [gradient_value, gradient_value + 20, gradient_value + 40]
                
                # Draw black subtitle bar at bottom
                cv2.rectangle(frame, (0, subtitle_bar_y_start), (width, height), (0, 0, 0), -1)
                
                # Calculate text size and position
                text_size = cv2.getTextSize(subtitle_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)[0]
                text_x = (width - text_size[0]) // 2
                text_y = subtitle_bar_y_start + (subtitle_bar_height // 2) + (text_size[1] // 2)
                
                # Draw white text
                cv2.putText(frame, subtitle_text, (text_x, text_y),
                           cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), font_thickness, cv2.LINE_AA)
                
                writer.write(frame)
            
            writer.release()
            
            file_size = video_path.stat().st_size / 1024  # KB
            print(f"  ✅ {filename}: {file_size:.1f} KB")
            
            videos_metadata.append({
                'filename': filename,
                'resolution': res_name,
                'width': width,
                'height': height,
                'has_subtitles': True,
                'subtitle_type': 'burned_in',
                'subtitle_position': 'bottom_25_percent',
                'expected_result': True,
                'duration_seconds': duration_seconds,
                'file_size_kb': round(file_size, 1),
                'generated_at': datetime.now().isoformat()
            })
        
        # Generate 2 WITHOUT subtitles
        for i in range(1, 3):
            filename = f'{res_name}_WITHOUT_{i:02d}.mp4'
            video_path = output_path / filename
            
            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))
            
            for frame_num in range(total_frames):
                # Create solid color background (varied colors)
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                
                # Different colors for variety
                if i == 1:
                    # Blue gradient
                    gradient_value = int(40 + (frame_num / total_frames) * 80)
                    frame[:, :] = [gradient_value + 20, gradient_value, gradient_value + 60]
                else:
                    # Green gradient
                    gradient_value = int(30 + (frame_num / total_frames) * 70)
                    frame[:, :] = [gradient_value, gradient_value + 50, gradient_value + 10]
                
                writer.write(frame)
            
            writer.release()
            
            file_size = video_path.stat().st_size / 1024  # KB
            print(f"  ✅ {filename}: {file_size:.1f} KB")
            
            videos_metadata.append({
                'filename': filename,
                'resolution': res_name,
                'width': width,
                'height': height,
                'has_subtitles': False,
                'subtitle_type': None,
                'expected_result': False,
                'duration_seconds': duration_seconds,
                'file_size_kb': round(file_size, 1),
                'generated_at': datetime.now().isoformat()
            })
    
    # Save ground truth
    ground_truth = {
        'dataset_info': {
            'name': 'Multi-Resolution Subtitle Detection Dataset',
            'version': '1.0.0',
            'created_at': datetime.now().isoformat(),
            'total_videos': len(videos_metadata),
            'resolutions': [f"{r[0]} ({r[1]}x{r[2]})" for r in resolutions],
            'videos_per_resolution': 4,
            'positive_samples': sum(1 for v in videos_metadata if v['has_subtitles']),
            'negative_samples': sum(1 for v in videos_metadata if not v['has_subtitles']),
            'balance_ratio': '50.0%'
        },
        'videos': videos_metadata
    }
    
    ground_truth_path = output_path / 'ground_truth.json'
    with open(ground_truth_path, 'w', encoding='utf-8') as f:
        json.dump(ground_truth, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 70)
    print("✅ Multi-resolution dataset generation complete!")
    print(f"   Total videos: {len(videos_metadata)}")
    print(f"   Resolutions: {len(resolutions)} (720p, 1080p, 1440p, 4K)")
    print(f"   Positive (WITH): {ground_truth['dataset_info']['positive_samples']}")
    print(f"   Negative (WITHOUT): {ground_truth['dataset_info']['negative_samples']}")
    print(f"   Ground truth: {ground_truth_path}")
    
    total_size = sum(v['file_size_kb'] for v in videos_metadata) / 1024  # MB
    print(f"   Total size: {total_size:.1f} MB")
    print("=" * 70)
    
    return str(output_path), ground_truth


if __name__ == '__main__':
    generate_multi_resolution_dataset()
