"""
Feature Extractor Module - Sprint 03

Extracts 56+ visual, temporal, and text features from video frames for ML classification.

Feature Groups:
1. Position Features (8): Vertical/horizontal position, distribution
2. Temporal Features (12): Duration, persistence, change rate
3. Visual Features (16): Contrast, size, aspect ratio, color
4. Text Features (12): Length, word count, language, chars
5. OCR Features (8): Confidence, box count, density

Total: 56 features for ML classifier (Sprint 06)

Author: YTCaption Team
Sprint: 03 - Feature Engineering
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
import re
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """
    Extract comprehensive features from video frames for ML classification.
    
    Features extracted:
    - Position: Where text appears (H3: vertical position prominence)
    - Temporal: How long text persists, change rate
    - Visual: Contrast, size, aspect ratio, color distribution
    - Text: Length, word count, special characters, language hints
    - OCR: Confidence scores, bounding box metrics
    
    Usage:
        extractor = FeatureExtractor()
        features = extractor.extract_from_video(video_path, ocr_results)
        # Returns dict with 56+ features
    """
    
    def __init__(self):
        """Initialize feature extractor"""
        self.feature_names = self._generate_feature_names()
        logger.info(f"FeatureExtractor initialized with {len(self.feature_names)} features")
    
    def _generate_feature_names(self) -> List[str]:
        """Generate list of all feature names"""
        features = []
        
        # Position features (8)
        features.extend([
            'pos_vertical_mean',      # Mean vertical position (0-1, 0=top)
            'pos_vertical_std',       # Std dev of vertical positions
            'pos_bottom_ratio',       # Ratio of text in bottom 25%
            'pos_top_ratio',          # Ratio of text in top 25%
            'pos_horizontal_mean',    # Mean horizontal position (0-1, 0=left)
            'pos_horizontal_std',     # Std dev of horizontal positions
            'pos_center_ratio',       # Ratio of text in center 50%
            'pos_consistency',        # How consistent positions are (1-std)
        ])
        
        # Temporal features (12)
        features.extend([
            'temp_duration_total',    # Total video duration (seconds)
            'temp_text_frames',       # Number of frames with text
            'temp_text_ratio',        # Ratio of frames with text
            'temp_persistence_mean',  # Mean duration of text appearance
            'temp_persistence_max',   # Max duration of text appearance
            'temp_change_rate',       # How often text changes (changes/sec)
            'temp_first_appear',      # When text first appears (0-1)
            'temp_last_appear',       # When text last appears (0-1)
            'temp_coverage',          # Temporal coverage (last-first)
            'temp_gaps_count',        # Number of gaps (no text)
            'temp_gaps_mean',         # Mean gap duration
            'temp_stability',         # How stable text is (low change = high stability)
        ])
        
        # Visual features (16)
        features.extend([
            'vis_bbox_area_mean',     # Mean bounding box area (pixels)
            'vis_bbox_area_std',      # Std dev of bbox areas
            'vis_bbox_width_mean',    # Mean bbox width
            'vis_bbox_height_mean',   # Mean bbox height
            'vis_aspect_ratio_mean',  # Mean aspect ratio (w/h)
            'vis_aspect_ratio_std',   # Std dev of aspect ratios
            'vis_contrast_mean',      # Mean contrast in text regions
            'vis_contrast_std',       # Std dev of contrast
            'vis_brightness_mean',    # Mean brightness in text regions
            'vis_brightness_std',     # Std dev of brightness
            'vis_edge_density_mean',  # Mean edge density (Canny edges)
            'vis_color_variance',     # Color variance in bbox
            'vis_bbox_count_mean',    # Mean number of bboxes per frame
            'vis_bbox_count_max',     # Max number of bboxes per frame
            'vis_overlap_ratio',      # How much bboxes overlap
            'vis_size_consistency',   # Consistency of bbox sizes (1-std/mean)
        ])
        
        # Text features (12)
        features.extend([
            'text_length_mean',       # Mean text length (chars)
            'text_length_std',        # Std dev of text lengths
            'text_length_max',        # Max text length
            'text_word_count_mean',   # Mean word count
            'text_word_count_max',    # Max word count
            'text_unique_ratio',      # Ratio of unique texts
            'text_digit_ratio',       # Ratio of digits in text
            'text_special_char_ratio',# Ratio of special chars
            'text_uppercase_ratio',   # Ratio of uppercase chars
            'text_language_en_prob',  # Probability of English (heuristic)
            'text_repetition_ratio',  # How much text repeats
            'text_newline_ratio',     # Ratio of texts with newlines
        ])
        
        # OCR features (8)
        features.extend([
            'ocr_confidence_mean',    # Mean OCR confidence
            'ocr_confidence_std',     # Std dev of confidences
            'ocr_confidence_min',     # Min OCR confidence
            'ocr_low_conf_ratio',     # Ratio of low confidence (<0.8)
            'ocr_high_conf_ratio',    # Ratio of high confidence (>0.95)
            'ocr_conf_consistency',   # Consistency of confidence (1-std/mean)
            'ocr_angle_variance',     # Variance in text angles
            'ocr_processing_time',    # Time to process (if available)
        ])
        
        return features
    
    def extract_position_features(self, bboxes: List[np.ndarray], frame_shape: Tuple[int, int]) -> Dict[str, float]:
        """
        Extract position-based features from bounding boxes.
        
        Args:
            bboxes: List of bounding boxes [[x1,y1,x2,y2,x3,y3,x4,y4], ...]
            frame_shape: (height, width) of frame
        
        Returns:
            Dict with 8 position features
        """
        if not bboxes:
            return {name: 0.0 for name in self.feature_names if name.startswith('pos_')}
        
        height, width = frame_shape
        
        # Extract center points and normalize
        vertical_positions = []
        horizontal_positions = []
        
        for bbox in bboxes:
            # bbox is [x1,y1,x2,y2,x3,y3,x4,y4]
            xs = [bbox[i] for i in range(0, 8, 2)]
            ys = [bbox[i] for i in range(1, 8, 2)]
            
            center_x = np.mean(xs) / width
            center_y = np.mean(ys) / height
            
            horizontal_positions.append(center_x)
            vertical_positions.append(center_y)
        
        # Calculate features
        v_mean = np.mean(vertical_positions)
        v_std = np.std(vertical_positions)
        h_mean = np.mean(horizontal_positions)
        h_std = np.std(horizontal_positions)
        
        bottom_ratio = sum(1 for y in vertical_positions if y > 0.75) / len(vertical_positions)
        top_ratio = sum(1 for y in vertical_positions if y < 0.25) / len(vertical_positions)
        center_ratio = sum(1 for x in horizontal_positions if 0.25 < x < 0.75) / len(horizontal_positions)
        
        consistency = 1.0 - v_std if v_std < 1.0 else 0.0
        
        return {
            'pos_vertical_mean': v_mean,
            'pos_vertical_std': v_std,
            'pos_bottom_ratio': bottom_ratio,
            'pos_top_ratio': top_ratio,
            'pos_horizontal_mean': h_mean,
            'pos_horizontal_std': h_std,
            'pos_center_ratio': center_ratio,
            'pos_consistency': consistency,
        }
    
    def extract_temporal_features(self, frame_detections: List[Dict], duration: float) -> Dict[str, float]:
        """
        Extract temporal features from frame-by-frame detections.
        
        Args:
            frame_detections: List of detections per frame [{'has_text': bool, 'timestamp': float}, ...]
            duration: Total video duration (seconds)
        
        Returns:
            Dict with 12 temporal features
        """
        if not frame_detections:
            return {name: 0.0 for name in self.feature_names if name.startswith('temp_')}
        
        # Count frames with text
        text_frames = sum(1 for d in frame_detections if d.get('has_text', False))
        text_ratio = text_frames / len(frame_detections)
        
        # Find first and last appearance (normalized)
        text_timestamps = [d['timestamp'] for d in frame_detections if d.get('has_text', False)]
        first_appear = (text_timestamps[0] / duration) if text_timestamps else 0.0
        last_appear = (text_timestamps[-1] / duration) if text_timestamps else 0.0
        coverage = last_appear - first_appear
        
        # Calculate persistence (consecutive frames with text)
        persistences = []
        current_persist = 0
        prev_had_text = False
        
        for d in frame_detections:
            if d.get('has_text', False):
                current_persist += 1
                prev_had_text = True
            else:
                if prev_had_text and current_persist > 0:
                    persistences.append(current_persist)
                current_persist = 0
                prev_had_text = False
        
        if current_persist > 0:
            persistences.append(current_persist)
        
        persistence_mean = np.mean(persistences) if persistences else 0.0
        persistence_max = max(persistences) if persistences else 0.0
        
        # Calculate gaps (consecutive frames without text)
        gaps = []
        current_gap = 0
        
        for d in frame_detections:
            if not d.get('has_text', False):
                current_gap += 1
            else:
                if current_gap > 0:
                    gaps.append(current_gap)
                current_gap = 0
        
        gaps_count = len(gaps)
        gaps_mean = np.mean(gaps) if gaps else 0.0
        
        # Change rate: number of transitions / duration
        transitions = 0
        for i in range(1, len(frame_detections)):
            if frame_detections[i].get('has_text') != frame_detections[i-1].get('has_text'):
                transitions += 1
        
        change_rate = transitions / duration if duration > 0 else 0.0
        stability = 1.0 - min(change_rate / 10.0, 1.0)  # Normalize to 0-1
        
        return {
            'temp_duration_total': duration,
            'temp_text_frames': text_frames,
            'temp_text_ratio': text_ratio,
            'temp_persistence_mean': persistence_mean,
            'temp_persistence_max': persistence_max,
            'temp_change_rate': change_rate,
            'temp_first_appear': first_appear,
            'temp_last_appear': last_appear,
            'temp_coverage': coverage,
            'temp_gaps_count': gaps_count,
            'temp_gaps_mean': gaps_mean,
            'temp_stability': stability,
        }
    
    def extract_visual_features(self, frames: List[np.ndarray], bboxes_per_frame: List[List[np.ndarray]]) -> Dict[str, float]:
        """
        Extract visual features from frames and bounding boxes.
        
        Args:
            frames: List of video frames
            bboxes_per_frame: List of bounding boxes for each frame
        
        Returns:
            Dict with 16 visual features
        """
        if not frames or not bboxes_per_frame:
            return {name: 0.0 for name in self.feature_names if name.startswith('vis_')}
        
        bbox_areas = []
        bbox_widths = []
        bbox_heights = []
        aspect_ratios = []
        contrasts = []
        brightnesses = []
        edge_densities = []
        bbox_counts = []
        
        for frame, bboxes in zip(frames, bboxes_per_frame):
            if not bboxes:
                continue
            
            bbox_counts.append(len(bboxes))
            
            for bbox in bboxes:
                # Calculate bbox dimensions
                xs = [bbox[i] for i in range(0, 8, 2)]
                ys = [bbox[i] for i in range(1, 8, 2)]
                
                width = max(xs) - min(xs)
                height = max(ys) - min(ys)
                area = width * height
                
                bbox_areas.append(area)
                bbox_widths.append(width)
                bbox_heights.append(height)
                aspect_ratios.append(width / height if height > 0 else 0.0)
                
                # Extract region
                x1, y1 = int(min(xs)), int(min(ys))
                x2, y2 = int(max(xs)), int(max(ys))
                
                # Ensure bounds
                h, w = frame.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                
                if x2 > x1 and y2 > y1:
                    region = frame[y1:y2, x1:x2]
                    
                    # Convert to grayscale if needed
                    if len(region.shape) == 3:
                        gray_region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
                    else:
                        gray_region = region
                    
                    # Contrast (std dev)
                    contrasts.append(np.std(gray_region))
                    
                    # Brightness (mean)
                    brightnesses.append(np.mean(gray_region))
                    
                    # Edge density (Canny edges)
                    edges = cv2.Canny(gray_region, 50, 150)
                    edge_density = np.sum(edges > 0) / edges.size
                    edge_densities.append(edge_density)
        
        # Calculate statistics
        bbox_area_mean = np.mean(bbox_areas) if bbox_areas else 0.0
        bbox_area_std = np.std(bbox_areas) if bbox_areas else 0.0
        bbox_width_mean = np.mean(bbox_widths) if bbox_widths else 0.0
        bbox_height_mean = np.mean(bbox_heights) if bbox_heights else 0.0
        aspect_ratio_mean = np.mean(aspect_ratios) if aspect_ratios else 0.0
        aspect_ratio_std = np.std(aspect_ratios) if aspect_ratios else 0.0
        contrast_mean = np.mean(contrasts) if contrasts else 0.0
        contrast_std = np.std(contrasts) if contrasts else 0.0
        brightness_mean = np.mean(brightnesses) if brightnesses else 0.0
        brightness_std = np.std(brightnesses) if brightnesses else 0.0
        edge_density_mean = np.mean(edge_densities) if edge_densities else 0.0
        
        bbox_count_mean = np.mean(bbox_counts) if bbox_counts else 0.0
        bbox_count_max = max(bbox_counts) if bbox_counts else 0.0
        
        # Size consistency
        size_consistency = 1.0 - (bbox_area_std / bbox_area_mean) if bbox_area_mean > 0 else 0.0
        size_consistency = max(0.0, min(1.0, size_consistency))
        
        return {
            'vis_bbox_area_mean': bbox_area_mean,
            'vis_bbox_area_std': bbox_area_std,
            'vis_bbox_width_mean': bbox_width_mean,
            'vis_bbox_height_mean': bbox_height_mean,
            'vis_aspect_ratio_mean': aspect_ratio_mean,
            'vis_aspect_ratio_std': aspect_ratio_std,
            'vis_contrast_mean': contrast_mean,
            'vis_contrast_std': contrast_std,
            'vis_brightness_mean': brightness_mean,
            'vis_brightness_std': brightness_std,
            'vis_edge_density_mean': edge_density_mean,
            'vis_color_variance': 0.0,  # Placeholder (would need color analysis)
            'vis_bbox_count_mean': bbox_count_mean,
            'vis_bbox_count_max': bbox_count_max,
            'vis_overlap_ratio': 0.0,  # Placeholder (would need overlap calculation)
            'vis_size_consistency': size_consistency,
        }
    
    def extract_text_features(self, texts: List[str]) -> Dict[str, float]:
        """
        Extract text-based features.
        
        Args:
            texts: List of detected text strings
        
        Returns:
            Dict with 12 text features
        """
        if not texts:
            return {name: 0.0 for name in self.feature_names if name.startswith('text_')}
        
        # Length features
        lengths = [len(t) for t in texts]
        length_mean = np.mean(lengths)
        length_std = np.std(lengths)
        length_max = max(lengths)
        
        # Word count features
        word_counts = [len(t.split()) for t in texts]
        word_count_mean = np.mean(word_counts)
        word_count_max = max(word_counts)
        
        # Uniqueness
        unique_ratio = len(set(texts)) / len(texts)
        
        # Character analysis
        all_text = ''.join(texts)
        total_chars = len(all_text)
        
        digit_ratio = sum(1 for c in all_text if c.isdigit()) / total_chars if total_chars > 0 else 0.0
        special_ratio = sum(1 for c in all_text if not c.isalnum() and not c.isspace()) / total_chars if total_chars > 0 else 0.0
        uppercase_ratio = sum(1 for c in all_text if c.isupper()) / total_chars if total_chars > 0 else 0.0
        
        # Language detection (simple heuristic: English common words)
        english_words = set(['the', 'is', 'at', 'which', 'on', 'a', 'an', 'as', 'are', 'was', 'were', 'been', 'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might', 'must', 'can', 'of', 'to', 'in', 'for', 'with', 'and', 'or', 'but'])
        all_words = ' '.join(texts).lower().split()
        english_count = sum(1 for w in all_words if w in english_words)
        language_en_prob = english_count / len(all_words) if all_words else 0.0
        
        # Repetition
        text_counter = Counter(texts)
        repetition_ratio = sum(count - 1 for count in text_counter.values()) / len(texts) if len(texts) > 1 else 0.0
        
        # Newlines
        newline_ratio = sum(1 for t in texts if '\n' in t) / len(texts)
        
        return {
            'text_length_mean': length_mean,
            'text_length_std': length_std,
            'text_length_max': length_max,
            'text_word_count_mean': word_count_mean,
            'text_word_count_max': word_count_max,
            'text_unique_ratio': unique_ratio,
            'text_digit_ratio': digit_ratio,
            'text_special_char_ratio': special_ratio,
            'text_uppercase_ratio': uppercase_ratio,
            'text_language_en_prob': language_en_prob,
            'text_repetition_ratio': repetition_ratio,
            'text_newline_ratio': newline_ratio,
        }
    
    def extract_ocr_features(self, confidences: List[float]) -> Dict[str, float]:
        """
        Extract OCR confidence features.
        
        Args:
            confidences: List of OCR confidence scores (0-1)
        
        Returns:
            Dict with 8 OCR features
        """
        if not confidences:
            return {name: 0.0 for name in self.feature_names if name.startswith('ocr_')}
        
        conf_mean = np.mean(confidences)
        conf_std = np.std(confidences)
        conf_min = min(confidences)
        
        low_conf_ratio = sum(1 for c in confidences if c < 0.8) / len(confidences)
        high_conf_ratio = sum(1 for c in confidences if c > 0.95) / len(confidences)
        
        conf_consistency = 1.0 - (conf_std / conf_mean) if conf_mean > 0 else 0.0
        conf_consistency = max(0.0, min(1.0, conf_consistency))
        
        return {
            'ocr_confidence_mean': conf_mean,
            'ocr_confidence_std': conf_std,
            'ocr_confidence_min': conf_min,
            'ocr_low_conf_ratio': low_conf_ratio,
            'ocr_high_conf_ratio': high_conf_ratio,
            'ocr_conf_consistency': conf_consistency,
            'ocr_angle_variance': 0.0,  # Placeholder
            'ocr_processing_time': 0.0,  # Placeholder
        }
    
    def extract_all_features(
        self,
        frame_detections: List[Dict],
        duration: float,
        frames: Optional[List[np.ndarray]] = None,
        frame_shape: Tuple[int, int] = (1080, 1920)
    ) -> Dict[str, float]:
        """
        Extract all 56 features from detection data.
        
        Args:
            frame_detections: List of dicts with detection info per frame
                [{'has_text': bool, 'timestamp': float, 'texts': [str], 
                  'confidences': [float], 'bboxes': [[...]]}, ...]
            duration: Total video duration (seconds)
            frames: Optional list of actual frames for visual features
            frame_shape: (height, width) if frames not provided
        
        Returns:
            Dict with all 56 features
        """
        # Collect data
        all_bboxes = []
        all_texts = []
        all_confidences = []
        bboxes_per_frame = []
        
        for detection in frame_detections:
            if detection.get('has_text', False):
                bboxes = detection.get('bboxes', [])
                texts = detection.get('texts', [])
                confidences = detection.get('confidences', [])
                
                all_bboxes.extend(bboxes)
                all_texts.extend(texts)
                all_confidences.extend(confidences)
                bboxes_per_frame.append(bboxes)
            else:
                bboxes_per_frame.append([])
        
        # Extract features
        pos_features = self.extract_position_features(all_bboxes, frame_shape)
        temp_features = self.extract_temporal_features(frame_detections, duration)
        
        if frames:
            vis_features = self.extract_visual_features(frames, bboxes_per_frame)
        else:
            vis_features = {name: 0.0 for name in self.feature_names if name.startswith('vis_')}
        
        text_features = self.extract_text_features(all_texts)
        ocr_features = self.extract_ocr_features(all_confidences)
        
        # Combine all features
        all_features = {}
        all_features.update(pos_features)
        all_features.update(temp_features)
        all_features.update(vis_features)
        all_features.update(text_features)
        all_features.update(ocr_features)
        
        return all_features
    
    def get_feature_vector(self, features: Dict[str, float]) -> np.ndarray:
        """Convert feature dict to numpy array in consistent order"""
        return np.array([features.get(name, 0.0) for name in self.feature_names])
    
    def get_feature_names(self) -> List[str]:
        """Get list of feature names in order"""
        return self.feature_names.copy()


if __name__ == "__main__":
    # Quick test
    print("FeatureExtractor - Sprint 03")
    print("=" * 70)
    
    extractor = FeatureExtractor()
    print(f"\n✅ {len(extractor.feature_names)} features defined:")
    
    # Group by category
    categories = {}
    for name in extractor.feature_names:
        prefix = name.split('_')[0]
        if prefix not in categories:
            categories[prefix] = []
        categories[prefix].append(name)
    
    for cat, names in categories.items():
        print(f"\n{cat.upper()}: {len(names)} features")
        for name in names[:3]:  # Show first 3
            print(f"  - {name}")
        if len(names) > 3:
            print(f"  ... and {len(names) - 3} more")
    
    print("\n🎉 FeatureExtractor module working!")
