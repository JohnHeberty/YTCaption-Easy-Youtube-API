"""
Sprint 03 Test Suite - Feature Engineering

Tests feature extraction from video detections:
- 56 features extracted correctly
- Position features (vertical/horizontal distribution)
- Temporal features (duration, persistence, change rate)
- Visual features (bbox size, contrast)
- Text features (length, word count, language)
- OCR features (confidence scores)

Validates:
1. All 56 features extracted
2. Feature values in valid ranges
3. Consistent feature extraction
4. Integration with SubtitleDetectorV2
"""

import pytest
import sys
from pathlib import Path
import json
import numpy as np

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.video_processing.feature_extractor import FeatureExtractor
from app.video_processing.subtitle_detector_v2 import SubtitleDetectorV2


class TestSprint03FeatureExtraction:
    """Sprint 03: Feature Engineering Tests"""
    
    @pytest.fixture(scope='class')
    def feature_extractor(self):
        """Create feature extractor instance"""
        return FeatureExtractor()
    
    @pytest.fixture(scope='class')
    def sample_detections(self):
        """Create sample detection data for testing"""
        return [
            {
                'timestamp': 0.0,
                'has_text': True,
                'texts': ['Sample subtitle text'],
                'confidences': [0.95],
                'bboxes': [np.array([100, 800, 500, 800, 500, 900, 100, 900])],  # Bottom of frame
            },
            {
                'timestamp': 0.5,
                'has_text': True,
                'texts': ['Sample subtitle text'],
                'confidences': [0.96],
                'bboxes': [np.array([100, 800, 500, 800, 500, 900, 100, 900])],
            },
            {
                'timestamp': 1.0,
                'has_text': False,
                'texts': [],
                'confidences': [],
                'bboxes': [],
            },
            {
                'timestamp': 1.5,
                'has_text': True,
                'texts': ['Another subtitle line'],
                'confidences': [0.92],
                'bboxes': [np.array([120, 820, 520, 820, 520, 920, 120, 920])],
            },
        ]
    
    def test_feature_extractor_initialization(self, feature_extractor):
        """Test that feature extractor initializes correctly"""
        assert feature_extractor is not None
        
        feature_names = feature_extractor.get_feature_names()
        assert len(feature_names) == 56, f"Expected 56 features, got {len(feature_names)}"
        
        # Check that all categories are present
        categories = set(name.split('_')[0] for name in feature_names)
        expected_categories = {'pos', 'temp', 'vis', 'text', 'ocr'}
        assert categories == expected_categories
        
        print(f"\n✅ FeatureExtractor initialized with {len(feature_names)} features")
        print(f"   Categories: {categories}")
    
    def test_position_features_extraction(self, feature_extractor, sample_detections):
        """Test position feature extraction"""
        # Extract bboxes
        all_bboxes = []
        for d in sample_detections:
            all_bboxes.extend(d.get('bboxes', []))
        
        frame_shape = (1080, 1920)  # HD resolution
        pos_features = feature_extractor.extract_position_features(all_bboxes, frame_shape)
        
        # Check all position features present
        expected_pos_features = [
            'pos_vertical_mean', 'pos_vertical_std', 'pos_bottom_ratio',
            'pos_top_ratio', 'pos_horizontal_mean', 'pos_horizontal_std',
            'pos_center_ratio', 'pos_consistency'
        ]
        
        for feature in expected_pos_features:
            assert feature in pos_features, f"Missing position feature: {feature}"
            assert 0.0 <= pos_features[feature] <= 1.0, f"{feature} out of range [0,1]: {pos_features[feature]}"
        
        # Bboxes are at bottom (y ~= 800-900 out of 1080), so vertical_mean should be high
        assert pos_features['pos_vertical_mean'] > 0.7, "Subtitles should be in bottom area"
        assert pos_features['pos_bottom_ratio'] > 0.5, "Most text should be in bottom 25%"
        
        print(f"\n✅ Position features:")
        print(f"   Vertical mean: {pos_features['pos_vertical_mean']:.3f} (bottom)")
        print(f"   Bottom ratio:  {pos_features['pos_bottom_ratio']:.3f}")
        print(f"   Consistency:   {pos_features['pos_consistency']:.3f}")
    
    def test_temporal_features_extraction(self, feature_extractor, sample_detections):
        """Test temporal feature extraction"""
        duration = 2.0  # 2 seconds
        temp_features = feature_extractor.extract_temporal_features(sample_detections, duration)
        
        # Check all temporal features present
        expected_temp_features = [
            'temp_duration_total', 'temp_text_frames', 'temp_text_ratio',
            'temp_persistence_mean', 'temp_persistence_max', 'temp_change_rate',
            'temp_first_appear', 'temp_last_appear', 'temp_coverage',
            'temp_gaps_count', 'temp_gaps_mean', 'temp_stability'
        ]
        
        for feature in expected_temp_features:
            assert feature in temp_features, f"Missing temporal feature: {feature}"
        
        # Validate values
        assert temp_features['temp_duration_total'] == duration
        assert temp_features['temp_text_frames'] == 3  # 3 frames with text
        assert 0.0 <= temp_features['temp_text_ratio'] <= 1.0
        assert 0.0 <= temp_features['temp_first_appear'] <= 1.0
        assert 0.0 <= temp_features['temp_last_appear'] <= 1.0
        
        print(f"\n✅ Temporal features:")
        print(f"   Duration:    {temp_features['temp_duration_total']:.1f}s")
        print(f"   Text frames: {temp_features['temp_text_frames']}")
        print(f"   Text ratio:  {temp_features['temp_text_ratio']:.3f}")
        print(f"   Gaps count:  {temp_features['temp_gaps_count']}")
    
    def test_text_features_extraction(self, feature_extractor, sample_detections):
        """Test text feature extraction"""
        # Extract all texts
        all_texts = []
        for d in sample_detections:
            all_texts.extend(d.get('texts', []))
        
        text_features = feature_extractor.extract_text_features(all_texts)
        
        # Check all text features present
        expected_text_features = [
            'text_length_mean', 'text_length_std', 'text_length_max',
            'text_word_count_mean', 'text_word_count_max', 'text_unique_ratio',
            'text_digit_ratio', 'text_special_char_ratio', 'text_uppercase_ratio',
            'text_language_en_prob', 'text_repetition_ratio', 'text_newline_ratio'
        ]
        
        for feature in expected_text_features:
            assert feature in text_features, f"Missing text feature: {feature}"
            assert text_features[feature] >= 0.0, f"{feature} should be non-negative"
        
        # Validate specific values
        assert text_features['text_length_mean'] > 0, "Mean text length should be > 0"
        assert text_features['text_word_count_mean'] > 0, "Mean word count should be > 0"
        assert 0.0 <= text_features['text_unique_ratio'] <= 1.0
        
        print(f"\n✅ Text features:")
        print(f"   Mean length:     {text_features['text_length_mean']:.1f} chars")
        print(f"   Mean word count: {text_features['text_word_count_mean']:.1f} words")
        print(f"   Unique ratio:    {text_features['text_unique_ratio']:.3f}")
    
    def test_ocr_features_extraction(self, feature_extractor, sample_detections):
        """Test OCR confidence feature extraction"""
        # Extract all confidences
        all_confidences = []
        for d in sample_detections:
            all_confidences.extend(d.get('confidences', []))
        
        ocr_features = feature_extractor.extract_ocr_features(all_confidences)
        
        # Check all OCR features present
        expected_ocr_features = [
            'ocr_confidence_mean', 'ocr_confidence_std', 'ocr_confidence_min',
            'ocr_low_conf_ratio', 'ocr_high_conf_ratio', 'ocr_conf_consistency',
            'ocr_angle_variance', 'ocr_processing_time'
        ]
        
        for feature in expected_ocr_features:
            assert feature in ocr_features, f"Missing OCR feature: {feature}"
        
        # Validate confidence values
        assert 0.0 <= ocr_features['ocr_confidence_mean'] <= 1.0
        assert 0.0 <= ocr_features['ocr_confidence_min'] <= 1.0
        assert 0.0 <= ocr_features['ocr_low_conf_ratio'] <= 1.0
        assert 0.0 <= ocr_features['ocr_high_conf_ratio'] <= 1.0
        
        # Sample data has high confidence (0.92-0.96)
        assert ocr_features['ocr_confidence_mean'] > 0.9, "Sample data should have high confidence"
        
        print(f"\n✅ OCR features:")
        print(f"   Mean confidence: {ocr_features['ocr_confidence_mean']:.3f}")
        print(f"   Min confidence:  {ocr_features['ocr_confidence_min']:.3f}")
        print(f"   High conf ratio: {ocr_features['ocr_high_conf_ratio']:.3f}")
    
    def test_all_features_extraction(self, feature_extractor, sample_detections):
        """Test extraction of all 56 features together"""
        duration = 2.0
        frame_shape = (1080, 1920)
        
        all_features = feature_extractor.extract_all_features(
            sample_detections,
            duration,
            frames=None,
            frame_shape=frame_shape
        )
        
        # Check that all 56 features are present
        assert len(all_features) == 56, f"Expected 56 features, got {len(all_features)}"
        
        # Check that all feature names match
        feature_names = feature_extractor.get_feature_names()
        for name in feature_names:
            assert name in all_features, f"Feature {name} not in extracted features"
        
        # Check that all values are numeric
        for name, value in all_features.items():
            assert isinstance(value, (int, float, np.number)), f"{name} has non-numeric value: {value}"
            assert not np.isnan(value), f"{name} is NaN"
            assert not np.isinf(value), f"{name} is infinite"
        
        print(f"\n✅ All features extracted:")
        print(f"   Total: {len(all_features)} features")
        print(f"   All numeric: ✅")
        print(f"   No NaN/Inf:  ✅")
    
    def test_feature_vector_conversion(self, feature_extractor, sample_detections):
        """Test conversion of features to numpy vector"""
        duration = 2.0
        all_features = feature_extractor.extract_all_features(
            sample_detections,
            duration,
            frame_shape=(1080, 1920)
        )
        
        # Convert to vector
        feature_vector = feature_extractor.get_feature_vector(all_features)
        
        # Check vector properties
        assert isinstance(feature_vector, np.ndarray)
        assert feature_vector.shape == (56,), f"Expected shape (56,), got {feature_vector.shape}"
        assert not np.any(np.isnan(feature_vector)), "Feature vector contains NaN"
        assert not np.any(np.isinf(feature_vector)), "Feature vector contains Inf"
        
        print(f"\n✅ Feature vector:")
        print(f"   Shape: {feature_vector.shape}")
        print(f"   Min:   {feature_vector.min():.3f}")
        print(f"   Max:   {feature_vector.max():.3f}")
        print(f"   Mean:  {feature_vector.mean():.3f}")
    
    def test_empty_detections_handling(self, feature_extractor):
        """Test that empty detections are handled gracefully"""
        empty_detections = []
        duration = 0.0
        
        all_features = feature_extractor.extract_all_features(
            empty_detections,
            duration,
            frame_shape=(1080, 1920)
        )
        
        # Should return 56 features with default values (likely 0.0)
        assert len(all_features) == 56
        
        # All features should be numeric (not None or NaN)
        for name, value in all_features.items():
            assert isinstance(value, (int, float, np.number))
            assert not np.isnan(value)
        
        print(f"\n✅ Empty detections handled gracefully")
        print(f"   Features: {len(all_features)}")
        print(f"   All zeros: {all(v == 0.0 for v in all_features.values())}")
    
    def test_integration_with_detector(self):
        """Test feature extraction integrated with SubtitleDetectorV2"""
        # Load a test video
        test_video = Path('storage/validation/synthetic/synthetic_WITH_001.mp4')
        
        if not test_video.exists():
            pytest.skip("Synthetic dataset not found")
        
        # Detect subtitles
        detector = SubtitleDetectorV2(show_log=False)
        has_subs, conf, text, metadata = detector.detect_in_video(str(test_video))
        
        # Create feature extractor
        extractor = FeatureExtractor()
        
        # Build detection data (simplified - would need full detector refactor to get all data)
        # For now, just test with minimal data
        sample_detection = [{
            'timestamp': 1.0,
            'has_text': has_subs,
            'texts': [text] if text else [],
            'confidences': [conf] if has_subs else [],
            'bboxes': [],
        }]
        
        features = extractor.extract_all_features(
            sample_detection,
            duration=3.0,
            frame_shape=(1080, 1920)
        )
        
        assert len(features) == 56
        
        print(f"\n✅ Integration test:")
        print(f"   Video: {test_video.name}")
        print(f"   Has subs: {has_subs}")
        print(f"   Features extracted: {len(features)}")
        print(f"   OCR confidence: {features['ocr_confidence_mean']:.3f}")
    
    def test_feature_consistency(self, feature_extractor, sample_detections):
        """Test that feature extraction is consistent (deterministic)"""
        duration = 2.0
        
        # Extract features twice
        features1 = feature_extractor.extract_all_features(
            sample_detections,
            duration,
            frame_shape=(1080, 1920)
        )
        
        features2 = feature_extractor.extract_all_features(
            sample_detections,
            duration,
            frame_shape=(1080, 1920)
        )
        
        # Should be identical
        for name in features1.keys():
            assert features1[name] == features2[name], f"Feature {name} not consistent: {features1[name]} vs {features2[name]}"
        
        print(f"\n✅ Feature extraction is deterministic")


if __name__ == "__main__":
    pytest.main([__file__, '-v', '--tb=short'])
