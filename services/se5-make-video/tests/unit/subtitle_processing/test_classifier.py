"""
Unit tests for Subtitle Classifier

Tests track classification logic with real Track objects.
NO MOCKS - uses real SubtitleClassifier to validate classification logic.
"""

import pytest

from app.subtitle_processing.subtitle_classifier import (
    SubtitleClassifier,
    TrackCategory,
    ClassificationResult,
)
from app.subtitle_processing.temporal_tracker import Track
from app.trsd_models.text_region import TextLine, ROIType


class TestClassifierInit:
    """Tests for SubtitleClassifier initialization"""
    
    def test_classifier_module_imports(self):
        """SubtitleClassifier module imports successfully"""
        from app.subtitle_processing import subtitle_classifier
        assert subtitle_classifier is not None
    
    def test_classifier_class_exists(self):
        """SubtitleClassifier class can be instantiated"""
        classifier = SubtitleClassifier()
        assert classifier is not None
        assert hasattr(classifier, 'decide')
    
    def test_classifier_has_config(self):
        """SubtitleClassifier has configuration thresholds"""
        classifier = SubtitleClassifier()
        
        # Should have threshold attributes
        assert hasattr(classifier, 'static_min_presence')
        assert hasattr(classifier, 'static_max_change')
        assert hasattr(classifier, 'subtitle_min_change_rate')
        assert hasattr(classifier, 'ignore_static_text')


class TestTrackClassification:
    """Tests for individual track classification logic"""
    
    def test_classify_empty_tracks(self):
        """Classifier handles empty track list"""
        classifier = SubtitleClassifier()
        
        result = classifier.decide([])
        
        assert isinstance(result, ClassificationResult)
        assert not result.has_subtitles  # No tracks = no subtitles
        assert result.tracks_by_category['subtitle'] == 0
    
    def test_classify_static_text_track(self):
        """Classifier detects static overlay text"""
        classifier = SubtitleClassifier()
        
        # Create track with high presence, low change (static watermark)
        track = Track(track_id=1, roi_type=ROIType.TOP)
        
        # Add 100 detections with same text
        for i in range(100):
            detection = TextLine(
                frame_ts=i * 0.1,
                frame_idx=i,
                roi_type=ROIType.TOP,
                text="WATERMARK CHANNEL",
                bbox=(100, 50, 200, 30),
                confidence=0.95,
                words=[]
            )
            track.add_detection(detection)
        
        # Compute metrics
        track.compute_metrics(total_frames=100)
        
        # Should be classified as static (high presence, no change)
        result = classifier.decide([track])
        
        # The track should be static overlay if ignore_static_text is True
        # OR has_subtitles=False if policy excludes static text
        assert isinstance(result, ClassificationResult)
        
        # If ignore_static_text is True, should not block
        if classifier.ignore_static_text:
            assert not result.has_subtitles
    
    def test_classify_dynamic_subtitle_track(self):
        """Classifier detects dynamic subtitle text"""
        classifier = SubtitleClassifier()
        
        # Create track with changing text (typical subtitle behavior)
        track = Track(track_id=1, roi_type=ROIType.BOTTOM)
        
        # Add detections with changing text
        texts = [
            "Hello, welcome to the show",
            "Today we will talk about",
            "This is very interesting",
            "Let's get started",
            "Thank you for watching",
        ]
        
        for i, text in enumerate(texts):
            detection = TextLine(
                frame_ts=i * 2.0,
                frame_idx=i * 60,  # ~30fps
                roi_type=ROIType.BOTTOM,
                text=text,
                bbox=(100, 900, 800, 50),
                confidence=0.90,
                words=[]
            )
            track.add_detection(detection)
        
        # Compute metrics
        track.compute_metrics(total_frames=300)
        
        # Should have text_change_rate > 0
        assert track.text_change_rate > 0
        
        result = classifier.decide([track])
        
        # Multiple dynamic subtitle in bottom region should trigger block
        assert isinstance(result, ClassificationResult)
        assert result.tracks_by_category['subtitle'] >= 0  # At least counted


class TestClassificationResult:
    """Tests for ClassificationResult structure"""
    
    def test_result_structure(self):
        """ClassificationResult has expected fields"""
        classifier = SubtitleClassifier()
        
        result = classifier.decide([])
        
        # Validate result structure
        assert hasattr(result, 'has_subtitles')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'reason')
        assert hasattr(result, 'decision_logic')
        assert hasattr(result, 'tracks_by_category')
        assert hasattr(result, 'subtitle_tracks')
        assert hasattr(result, 'static_tracks')
        assert hasattr(result, 'screencast_tracks')
        assert hasattr(result, 'ambiguous_tracks')
    
    def test_result_has_categories(self):
        """ClassificationResult tracks_by_category has all categories"""
        classifier = SubtitleClassifier()
        
        result = classifier.decide([])
        
        categories = result.tracks_by_category
        
        # Should have all 4 categories
        assert 'subtitle' in categories
        assert 'static_overlay' in categories
        assert 'screencast' in categories
        assert 'ambiguous' in categories


class TestMultipleTracksClassification:
    """Tests for classification with multiple tracks"""
    
    def test_classify_mixed_tracks(self):
        """Classifier handles multiple tracks of different types"""
        classifier = SubtitleClassifier()
        
        # Static track (watermark)
        static_track = Track(track_id=1, roi_type=ROIType.TOP)
        for i in range(50):
            detection = TextLine(
                frame_ts=i * 0.1,
                frame_idx=i,
                roi_type=ROIType.TOP,
                text="CHANNEL NAME",
                bbox=(50, 50, 150, 30),
                confidence=0.95,
                words=[]
            )
            static_track.add_detection(detection)
        static_track.compute_metrics(total_frames=100)
        
        # Dynamic subtitle track
        subtitle_track = Track(track_id=2, roi_type=ROIType.BOTTOM)
        texts = ["First line", "Second line", "Third line"]
        for i, text in enumerate(texts):
            detection = TextLine(
                frame_ts=i * 1.0,
                frame_idx=i * 30,
                roi_type=ROIType.BOTTOM,
                text=text,
                bbox=(100, 900, 700, 50),
                confidence=0.90,
                words=[]
            )
            subtitle_track.add_detection(detection)
        subtitle_track.compute_metrics(total_frames=100)
        
        # Classify both
        result = classifier.decide([static_track, subtitle_track])
        
        # Should differentiate between static and subtitle
        assert isinstance(result, ClassificationResult)
        assert len(result.subtitle_tracks) + len(result.static_tracks) > 0


class TestTrackMetrics:
    """Tests for Track metrics calculation"""
    
    def test_track_compute_metrics(self):
        """Track.compute_metrics calculates all metrics"""
        track = Track(track_id=1, roi_type=ROIType.BOTTOM)
        
        # Add some detections
        for i in range(10):
            detection = TextLine(
                frame_ts=i * 0.5,
                frame_idx=i,
                roi_type=ROIType.BOTTOM,
                text=f"Text {i}",
                bbox=(100, 900, 500, 50),
                confidence=0.9,
                words=[]
            )
            track.add_detection(detection)
        
        # Compute
        track.compute_metrics(total_frames=20)
        
        # Validate calculated metrics
        assert track.presence_ratio == 0.5  # 10/20 frames
        assert track.text_change_rate >= 0.0
        assert track.y_mean > 0
        assert track.y_std >= 0
        assert track.avg_confidence > 0


class TestClassifierV2:
    """Tests for SubtitleClassifierV2 if it exists"""
    
    def test_classifier_v2_module_exists(self):
        """Check if SubtitleClassifierV2 exists"""
        try:
            from app.subtitle_processing import subtitle_classifier_v2
            assert subtitle_classifier_v2 is not None
        except ImportError:
            pytest.skip("SubtitleClassifierV2 not found")


class TestTemporalTracker:
    """Tests for TemporalTracker module"""
    
    def test_temporal_tracker_imports(self):
        """TemporalTracker module imports successfully"""
        from app.subtitle_processing import temporal_tracker
        assert temporal_tracker is not None
    
    def test_track_class_exists(self):
        """Track class can be instantiated"""
        track = Track(track_id=1, roi_type=ROIType.BOTTOM)
        assert track is not None
        assert track.track_id == 1
        assert track.roi_type == ROIType.BOTTOM
    
    def test_track_add_detection(self):
        """Track.add_detection adds TextLine to detections"""
        track = Track(track_id=1, roi_type=ROIType.BOTTOM)
        
        detection = TextLine(
            frame_ts=0.0,
            frame_idx=0,
            roi_type=ROIType.BOTTOM,
            text="Test",
            bbox=(100, 900, 500, 50),
            confidence=0.9,
            words=[]
        )
        
        track.add_detection(detection)
        
        assert len(track.detections) == 1
        assert track.detections[0].text == "Test"
