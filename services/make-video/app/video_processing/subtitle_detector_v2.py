"""
SubtitleDetectorV2 - Dynamic Resolution Support + Preprocessing (Sprint 02)

Simple, reliable subtitle detection with:
- Auto-detection of video resolution
- Adaptive ROI (bottom 20-30% based on resolution)
- Temporal sampling (6 strategic timestamps)
- Advanced preprocessing (CLAHE, noise reduction, etc.)
- Single OCR engine: PaddleOCR 2.7.3

Based on Sprint 00 success: 100% accuracy with simple approach
Sprint 02: Added preprocessing for low-quality videos
"""
import cv2
from paddleocr import PaddleOCR
from pathlib import Path
from typing import Tuple, List, Optional, Dict
import os
import random
from .frame_preprocessor import FramePreprocessor


class SubtitleDetectorV2:
    """
    Resolution-aware subtitle detector with Multi-ROI support (Sprint 04)
    
    Features:
    - Supports 480p, 720p, 1080p, 4K, any custom resolution
    - Multi-ROI fallback (bottom, top, left, right, center)
    - 6-point temporal sampling for robust detection
    - Single PaddleOCR instance (thread-safe, no complexity)
    """
    
    # ROI Configurations (Sprint 04)
    ROI_CONFIGS = {
        'bottom': {
            'y_start': 0.75,
            'y_end': 1.0,
            'x_start': 0.0,
            'x_end': 1.0,
            'priority': 1,
            'description': 'Standard bottom subtitles (most common)'
        },
        'top': {
            'y_start': 0.0,
            'y_end': 0.25,
            'x_start': 0.0,
            'x_end': 1.0,
            'priority': 2,
            'description': 'Top subtitles (foreign films, dual-language)'
        },
        'left': {
            'y_start': 0.0,
            'y_end': 1.0,
            'x_start': 0.0,
            'x_end': 0.2,
            'priority': 3,
            'description': 'Left side captions (YouTube Shorts, vertical)'
        },
        'right': {
            'y_start': 0.0,
            'y_end': 1.0,
            'x_start': 0.8,
            'x_end': 1.0,
            'priority': 3,
            'description': 'Right side captions (social media)'
        },
        'center': {
            'y_start': 0.35,
            'y_end': 0.65,
            'x_start': 0.35,
            'x_end': 0.65,
            'priority': 4,
            'description': 'Center text (embedded, hardcoded)'
        },
        'full': {
            'y_start': 0.0,
            'y_end': 1.0,
            'x_start': 0.0,
            'x_end': 1.0,
            'priority': 5,
            'description': 'Full frame scan (last resort for atypical layouts)'
        }
    }
    
    def __init__(self, show_log: bool = False, preprocessing_preset: str = 'none', roi_mode: str = 'bottom'):
        """
        Initialize PaddleOCR detector with optional preprocessing and multi-ROI
        
        Args:
            show_log: Show PaddleOCR logs
            preprocessing_preset: Preset for frame preprocessing
                - 'none': No preprocessing (default, Sprint 00/01 behavior)
                - 'light': CLAHE only (fast)
                - 'medium': CLAHE + noise reduction (balanced)
                - 'heavy': All techniques (slow)
                - 'low_quality': Optimized for compressed videos
                - 'high_quality': Minimal processing
            roi_mode: ROI detection mode (Sprint 04)
                - 'bottom': Legacy mode, bottom 25% only (default, backward compatible)
                - 'multi': Priority-based fallback (bottom → top → sides → center)
                - 'all': Scan all ROIs, combine results (debugging)
        """
        os.environ['MKL_NUM_THREADS'] = '1'
        os.environ['OPENBLAS_NUM_THREADS'] = '1'
        os.environ['OMP_NUM_THREADS'] = '1'
        
        self.ocr = PaddleOCR(
            use_angle_cls=True,
            lang='en',
            use_gpu=False,
            show_log=show_log
        )
        
        # Initialize preprocessor (Sprint 02)
        self.preprocessing_preset = preprocessing_preset
        if preprocessing_preset != 'none':
            self.preprocessor = FramePreprocessor.create_preset(preprocessing_preset)
        else:
            self.preprocessor = None
        
        # ROI mode (Sprint 04)
        self.roi_mode = roi_mode
        if roi_mode not in ['bottom', 'multi', 'all']:
            raise ValueError(f"Invalid roi_mode: {roi_mode}. Must be 'bottom', 'multi', or 'all'")
    
    def detect_resolution(self, video_path: str) -> Tuple[int, int, float]:
        """
        Detect video resolution and duration
        
        Returns:
            (width, height, duration_seconds)
        """
        cap = cv2.VideoCapture(video_path)
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        duration = frame_count / fps if fps > 0 else 0
        
        cap.release()
        
        return width, height, duration
    
    def get_roi_for_resolution(self, frame, resolution: Tuple[int, int]) -> Tuple[any, dict]:
        """
        Get ROI (Region of Interest) for subtitle detection
        
        Subtitles typically appear in bottom 20-30% of frame
        Adaptive based on resolution:
        - 4K (3840x2160): bottom 540px (25%)
        - 1080p (1920x1080): bottom 270px (25%)
        - 720p (1280x720): bottom 180px (25%)
        - 480p (854x480): bottom 120px (25%)
        
        Args:
            frame: Full video frame
            resolution: (width, height)
        
        Returns:
            (roi_frame, metadata_dict)
        """
        width, height = resolution
        
        # ROI: bottom 25% of frame
        roi_percentage = 0.25
        roi_height = int(height * roi_percentage)
        roi_y_start = height - roi_height
        
        # Crop ROI
        roi_frame = frame[roi_y_start:height, 0:width]
        
        metadata = {
            'full_resolution': (width, height),
            'roi_percentage': roi_percentage,
            'roi_height': roi_height,
            'roi_y_start': roi_y_start,
            'roi_size': (width, roi_height)
        }
        
        return roi_frame, metadata
    
    def _crop_frame_to_roi(self, frame: any, roi_config: dict) -> any:
        """
        Crop frame to specified ROI (Sprint 04)
        
        Args:
            frame: Full video frame
            roi_config: ROI configuration dict with y_start, y_end, x_start, x_end
        
        Returns:
            Cropped frame
        """
        h, w = frame.shape[:2]
        
        y1 = int(h * roi_config['y_start'])
        y2 = int(h * roi_config['y_end'])
        x1 = int(w * roi_config['x_start'])
        x2 = int(w * roi_config['x_end'])
        
        return frame[y1:y2, x1:x2]
    
    def _detect_in_roi(self, frames: List[any], roi_config: dict, roi_name: str) -> Tuple[bool, float, List[str], dict]:
        """
        Detect text in specific ROI across multiple frames (Sprint 04)
        
        Args:
            frames: List of full video frames
            roi_config: ROI configuration
            roi_name: Name of ROI (for metadata)
        
        Returns:
            (has_text, confidence, texts, metadata)
        """
        detections = []
        all_texts = []
        
        for frame_idx, frame in enumerate(frames):
            if frame is None:
                continue
            
            # Crop to ROI
            roi_frame = self._crop_frame_to_roi(frame, roi_config)
            
            # Apply preprocessing if enabled
            process_frame = roi_frame
            if self.preprocessor is not None:
                process_frame = self.preprocessor.preprocess(roi_frame)
            
            # Run OCR
            try:
                result = self.ocr.ocr(process_frame, cls=True)
                
                if result and result[0]:
                    texts = []
                    confidences = []
                    
                    for line in result[0]:
                        text = line[1][0].strip()
                        conf = line[1][1]
                        
                        if text:
                            texts.append(text)
                            confidences.append(conf)
                    
                    has_text_frame = len(texts) > 0
                    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
                    
                    detections.append({
                        'frame_idx': frame_idx,
                        'has_text': has_text_frame,
                        'confidence': avg_conf,
                        'texts': texts
                    })
                    
                    if texts:
                        all_texts.extend(texts)
            except Exception:
                pass
        
        # Combine detections
        frames_with_text = sum(1 for d in detections if d['has_text'])
        detection_ratio = frames_with_text / len(frames) if frames else 0.0
        
        has_text = detection_ratio >= 0.5  # At least 50% of frames must have text
        
        confidences = [d['confidence'] for d in detections if d['has_text']]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        metadata = {
            'roi_name': roi_name,
            'roi_config': roi_config,
            'frames_analyzed': len(frames),
            'frames_with_text': frames_with_text,
            'detection_ratio': detection_ratio,
            'detections': detections
        }
        
        return has_text, avg_confidence, all_texts, metadata
    
    def sample_temporal_frames(self, duration: float, num_samples: int = 6) -> List[float]:
        """
        Generate strategic timestamps for sampling
        
        Strategy:
        - Start (0.0s)
        - 1/4 point
        - Middle
        - 3/4 point
        - Near end (90%)
        - Random mid-point (for variety)
        
        Args:
            duration: Video duration in seconds
            num_samples: Number of samples (default: 6)
        
        Returns:
            List of timestamps in seconds
        """
        if duration <= 0:
            return [0.0]
        
        timestamps = [
            0.0,                          # Start
            duration * 0.25,              # 1/4
            duration * 0.50,              # Middle
            duration * 0.75,              # 3/4
            duration * 0.90,              # Near end
            duration * random.uniform(0.3, 0.7)  # Random middle
        ]
        
        # Limit to duration
        timestamps = [min(ts, duration - 0.1) for ts in timestamps]
        
        # Sort and deduplicate
        timestamps = sorted(list(set([round(ts, 2) for ts in timestamps])))
        
        return timestamps[:num_samples]
    
    def extract_frame_at_timestamp(self, video_path: str, timestamp: float) -> Optional[any]:
        """Extract single frame at timestamp"""
        cap = cv2.VideoCapture(video_path)
        
        # Seek to timestamp (milliseconds)
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        
        ret, frame = cap.read()
        cap.release()
        
        return frame if ret else None
    
    def has_text_in_frame(self, frame: any, use_roi: bool = True, resolution: Optional[Tuple[int, int]] = None) -> Tuple[bool, float, List[str]]:
        """
        Check if frame has text using OCR
        
        Args:
            frame: Video frame (BGR)
            use_roi: If True, crop to ROI before OCR
            resolution: (width, height) for ROI calculation
        
        Returns:
            (has_text, confidence, texts_list)
        """
        process_frame = frame
        
        if use_roi and resolution:
            roi_frame, _ = self.get_roi_for_resolution(frame, resolution)
            process_frame = roi_frame
        
        # Apply preprocessing if enabled (Sprint 02)
        if self.preprocessor is not None:
            process_frame = self.preprocessor.preprocess(process_frame)
        
        try:
            result = self.ocr.ocr(process_frame, cls=True)
            
            if not result or not result[0]:
                return False, 0.0, []
            
            # Extract texts and confidences
            texts = []
            confidences = []
            
            for line in result[0]:
                text = line[1][0].strip()
                conf = line[1][1]
                
                if text:
                    texts.append(text)
                    confidences.append(conf)
            
            has_text = len(texts) > 0
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return has_text, avg_confidence, texts
        
        except Exception as e:
            return False, 0.0, []
    
    def detect_in_video(self, video_path: str, use_roi: bool = True, num_samples: int = 6, detection_threshold: float = 0.5) -> Tuple[bool, float, str, Dict]:
        """
        Main detection pipeline with dynamic resolution support
        
        Args:
            video_path: Path to video file
            use_roi: Use ROI cropping (recommended: True)
            num_samples: Number of temporal samples (default: 6)
            detection_threshold: Minimum detection ratio (default: 0.5 = 50% of samples must detect text)
        
        Returns:
            (has_subtitles, confidence, sample_text, metadata_dict)
        """
        # Step 1: Detect resolution
        width, height, duration = self.detect_resolution(video_path)
        resolution = (width, height)
        
        # Step 2: Sample temporal frames
        timestamps = self.sample_temporal_frames(duration, num_samples)
        
        # Step 3: Process each frame
        detections = []
        all_texts = []
        
        for ts in timestamps:
            frame = self.extract_frame_at_timestamp(video_path, ts)
            
            if frame is None:
                continue
            
            has_text, conf, texts = self.has_text_in_frame(frame, use_roi, resolution)
            
            detections.append({
                'timestamp': ts,
                'has_text': has_text,
                'confidence': conf,
                'texts': texts
            })
            
            if texts:
                all_texts.extend(texts)
        
        # Step 4: Combine detections
        if not detections:
            return False, 0.0, "", {
                'resolution': resolution,
                'duration': duration,
                'timestamps_sampled': timestamps,
                'frames_analyzed': 0,
                'detections': []
            }
        
        # Detection logic: at least detection_threshold% of frames must have text
        frames_with_text = sum(1 for d in detections if d['has_text'])
        detection_ratio = frames_with_text / len(detections)
        
        has_subtitles = detection_ratio >= detection_threshold
        
        # Average confidence from frames with text
        confidences = [d['confidence'] for d in detections if d['has_text']]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Sample text (first detected text)
        sample_text = all_texts[0] if all_texts else ""
        
        metadata = {
            'resolution': resolution,
            'duration': duration,
            'timestamps_sampled': timestamps,
            'frames_analyzed': len(detections),
            'frames_with_text': frames_with_text,
            'detection_ratio': detection_ratio,
            'detection_threshold': detection_threshold,
            'detections': detections
        }
        
        return has_subtitles, avg_confidence, sample_text, metadata
    
    def detect_in_video_with_multi_roi(self, video_path: str, num_samples: int = 6) -> Tuple[bool, float, str, Dict]:
        """
        Multi-ROI detection with priority-based fallback (Sprint 04)
        
        Priority order: bottom → top → left → right → center
        Early exit: stops at first ROI that finds text (optimization)
        
        Args:
            video_path: Path to video file
            num_samples: Number of temporal samples (default: 6)
        
        Returns:
            (has_subtitles, confidence, sample_text, metadata_dict)
        """
        # Step 1: Detect resolution and sample timestamps
        width, height, duration = self.detect_resolution(video_path)
        resolution = (width, height)
        timestamps = self.sample_temporal_frames(duration, num_samples)
        
        # Step 2: Extract all frames first
        frames = []
        for ts in timestamps:
            frame = self.extract_frame_at_timestamp(video_path, ts)
            if frame is not None:
                frames.append(frame)
        
        if not frames:
            return False, 0.0, "", {
                'resolution': resolution,
                'duration': duration,
                'timestamps_sampled': timestamps,
                'frames_extracted': 0,
                'roi_mode': self.roi_mode,
                'roi_used': None
            }
        
        # Step 3: ROI detection based on mode
        if self.roi_mode == 'bottom':
            # Legacy mode: bottom 25% only (backward compatible)
            roi_config = self.ROI_CONFIGS['bottom']
            has_text, confidence, texts, roi_metadata = self._detect_in_roi(frames, roi_config, 'bottom')
            
            metadata = {
                'resolution': resolution,
                'duration': duration,
                'timestamps_sampled': timestamps,
                'frames_extracted': len(frames),
                'roi_mode': 'bottom',
                'roi_used': 'bottom' if has_text else None,
                'roi_metadata': roi_metadata
            }
            
            sample_text = texts[0] if texts else ""
            return has_text, confidence, sample_text, metadata
        
        elif self.roi_mode == 'multi':
            # Priority-based fallback: stop at first ROI that finds text
            roi_priority = sorted(
                self.ROI_CONFIGS.items(),
                key=lambda x: x[1]['priority']
            )
            
            all_roi_results = {}
            
            for roi_name, roi_config in roi_priority:
                has_text, confidence, texts, roi_metadata = self._detect_in_roi(frames, roi_config, roi_name)
                
                all_roi_results[roi_name] = {
                    'has_text': has_text,
                    'confidence': confidence,
                    'texts': texts,
                    'metadata': roi_metadata
                }
                
                # Early exit: found text in this ROI
                if has_text:
                    metadata = {
                        'resolution': resolution,
                        'duration': duration,
                        'timestamps_sampled': timestamps,
                        'frames_extracted': len(frames),
                        'roi_mode': 'multi',
                        'roi_used': roi_name,
                        'roi_priority': roi_config['priority'],
                        'roi_metadata': roi_metadata,
                        'rois_checked': list(all_roi_results.keys())
                    }
                    
                    sample_text = texts[0] if texts else ""
                    return has_text, confidence, sample_text, metadata
            
            # No text found in any ROI
            metadata = {
                'resolution': resolution,
                'duration': duration,
                'timestamps_sampled': timestamps,
                'frames_extracted': len(frames),
                'roi_mode': 'multi',
                'roi_used': None,
                'all_roi_results': all_roi_results,
                'rois_checked': list(all_roi_results.keys())
            }
            
            return False, 0.0, "", metadata
        
        elif self.roi_mode == 'all':
            # Scan all ROIs, combine results (debugging mode)
            all_roi_results = {}
            
            for roi_name, roi_config in self.ROI_CONFIGS.items():
                has_text, confidence, texts, roi_metadata = self._detect_in_roi(frames, roi_config, roi_name)
                
                all_roi_results[roi_name] = {
                    'has_text': has_text,
                    'confidence': confidence,
                    'texts': texts,
                    'metadata': roi_metadata
                }
            
            # Determine overall result (any ROI with text = has subtitles)
            has_any_text = any(r['has_text'] for r in all_roi_results.values())
            
            # Best ROI (highest confidence)
            best_roi = max(
                all_roi_results.items(),
                key=lambda x: x[1]['confidence'] if x[1]['has_text'] else 0.0
            )
            best_roi_name, best_roi_data = best_roi
            
            metadata = {
                'resolution': resolution,
                'duration': duration,
                'timestamps_sampled': timestamps,
                'frames_extracted': len(frames),
                'roi_mode': 'all',
                'roi_used': best_roi_name if has_any_text else None,
                'best_roi_confidence': best_roi_data['confidence'],
                'all_roi_results': all_roi_results
            }
            
            sample_text = best_roi_data['texts'][0] if best_roi_data['texts'] else ""
            return has_any_text, best_roi_data['confidence'], sample_text, metadata


def test_detector():
    """Quick test of SubtitleDetectorV2"""
    print("🧪 Testing SubtitleDetectorV2...")
    
    detector = SubtitleDetectorV2(show_log=False)
    
    # Test on synthetic dataset
    synthetic_dir = Path('storage/validation/synthetic')
    
    if not synthetic_dir.exists():
        print("❌ Synthetic dataset not found")
        return
    
    test_videos = [
        ('synthetic_WITH_001.mp4', True),
        ('synthetic_WITHOUT_001.mp4', False)
    ]
    
    for filename, expected in test_videos:
        video_path = str(synthetic_dir / filename)
        
        if not Path(video_path).exists():
            print(f"⚠️ Skipping {filename} (not found)")
            continue
        
        has_subs, conf, text, meta = detector.detect_in_video(video_path)
        
        status = "✅" if has_subs == expected else "❌"
        print(f"{status} {filename}: detected={has_subs}, expected={expected}, conf={conf:.2f}")
        print(f"   Resolution: {meta['resolution']}, Frames: {meta['frames_with_text']}/{meta['frames_analyzed']}")
        if text:
            print(f"   Text: '{text[:50]}'")


if __name__ == '__main__':
    test_detector()
