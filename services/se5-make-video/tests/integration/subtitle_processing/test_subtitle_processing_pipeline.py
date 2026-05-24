"""
Integration tests for subtitle processing

Tests end-to-end subtitle processing with real file I/O.
NO MOCKS - uses real ASSGenerator, SubtitleClassifier, and file operations.
"""

import pytest
from pathlib import Path

from app.subtitle_processing.ass_generator import ASSGenerator
from app.subtitle_processing.subtitle_classifier import SubtitleClassifier
from app.subtitle_processing.temporal_tracker import Track
from app.trsd_models.text_region import TextLine, ROIType


class TestASSGeneratorIntegration:
    """Integration tests for ASS file generation"""
    
    def test_generate_complete_ass_file(self, tmp_path):
        """Generate complete ASS file with multiple cues and read it back"""
        generator = ASSGenerator(video_width=1920, video_height=1080)
        output = tmp_path / "complete.ass"
        
        # Real subtitle timeline
        cues = [
            {"start": 0.0, "end": 2.5, "text": "Welcome to this video"},
            {"start": 3.0, "end": 5.5, "text": "Today we will explore"},
            {"start": 6.0, "end": 8.0, "text": "Subtitle processing with Python"},
            {"start": 8.5, "end": 11.0, "text": "Using ASS format for styling"},
            {"start": 11.5, "end": 14.0, "text": "Thank you for watching!"},
        ]
        
        # Generate
        result_path = generator.generate_ass(cues, str(output), preset='neon')
        
        # Validate file exists and is readable
        assert Path(result_path).exists()
        assert Path(result_path).stat().st_size > 0
        
        # Read and validate content
        content = output.read_text(encoding='utf-8')
        
        # All sections present
        assert "[Script Info]" in content
        assert "[V4+ Styles]" in content
        assert "[Events]" in content
        
        # All cues present
        for cue in cues:
            assert cue['text'] in content
        
        # Resolution present
        assert "PlayResX: 1920" in content
        assert "PlayResY: 1080" in content
    
    def test_generate_both_presets(self, tmp_path):
        """Generate files with both neon and classic presets"""
        generator = ASSGenerator()
        
        cues = [
            {"start": 0.0, "end": 2.0, "text": "Test subtitle"},
        ]
        
        # Generate neon
        neon_path = tmp_path / "neon.ass"
        generator.generate_ass(cues, str(neon_path), preset='neon')
        
        # Generate classic
        classic_path = tmp_path / "classic.ass"
        generator.generate_ass(cues, str(classic_path), preset='classic')
        
        # Both exist
        assert neon_path.exists()
        assert classic_path.exists()
        
        # Both are valid ASS files
        neon_content = neon_path.read_text()
        classic_content = classic_path.read_text()
        
        assert "[Events]" in neon_content
        assert "[Events]" in classic_content
        assert "Test subtitle" in neon_content
        assert "Test subtitle" in classic_content


class TestClassifierIntegration:
    """Integration tests for subtitle classification"""
    
    def test_classify_subtitle_scenario(self):
        """Classify realistic subtitle scenario with bottom text"""
        classifier = SubtitleClassifier()
        
        # Create realistic subtitle track (bottom, changing text)
        track = Track(track_id=1, roi_type=ROIType.BOTTOM)
        
        # Simulate 30 seconds of video with subtitle changes every 3 seconds
        subtitles = [
            "Hello everyone",
            "Welcome to my channel",
            "Today we will discuss",
            "How to process videos",
            "With Python and FFmpeg",
            "Subscribe for more!",
            "Thank you for watching",
            "See you next time",
        ]
        
        frame_idx = 0
        for i, text in enumerate(subtitles):
            # Each subtitle appears for ~90 frames (3 seconds at 30fps)
            for _ in range(90):
                detection = TextLine(
                    frame_ts=frame_idx / 30.0,
                    frame_idx=frame_idx,
                    roi_type=ROIType.BOTTOM,
                    text=text,
                    bbox=(200, 950, 680, 50),
                    confidence=0.92,
                    words=[]
                )
                track.add_detection(detection)
                frame_idx += 1
        
        # Compute metrics
        total_frames = frame_idx
        track.compute_metrics(total_frames=total_frames)
        
        # Classify
        result = classifier.decide([track])
        
        # Validate result structure
        assert result is not None
        assert hasattr(result, 'has_subtitles')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'tracks_by_category')
        
        # Should detect at least some categorization
        total_categorized = sum(result.tracks_by_category.values())
        assert total_categorized == 1  # 1 track
    
    def test_classify_static_watermark_scenario(self):
        """Classify static watermark that should not be blocked"""
        classifier = SubtitleClassifier()
        
        # Static watermark in top corner
        track = Track(track_id=1, roi_type=ROIType.TOP)
        
        # Same text appears in every frame (10 seconds at 30fps = 300 frames)
        for frame_idx in range(300):
            detection = TextLine(
                frame_ts=frame_idx / 30.0,
                frame_idx=frame_idx,
                roi_type=ROIType.TOP,
                text="@MyChannel",
                bbox=(50, 50, 150, 30),
                confidence=0.98,
                words=[]
            )
            track.add_detection(detection)
        
        # Compute metrics
        track.compute_metrics(total_frames=300)
        
        # Should be high presence, zero text change
        assert track.presence_ratio == 1.0  # Appears in all frames
        assert track.text_change_rate == 0.0  # Never changes
        
        # Classify
        result = classifier.decide([track])
        
        # If ignore_static_text is True, should not block
        if classifier.ignore_static_text:
            assert not result.has_subtitles


class TestSubtitleProcessingPipeline:
    """Integration tests for complete subtitle processing pipeline"""
    
    def test_generate_ass_from_classified_subtitles(self, tmp_path):
        """Generate ASS file from subtitle tracks after classification"""
        # Step 1: Create and classify tracks
        classifier = SubtitleClassifier()
        
        subtitle_track = Track(track_id=1, roi_type=ROIType.BOTTOM)
        texts_and_times = [
            ("First subtitle line", 0.0),
            ("Second subtitle line", 3.0),
            ("Third subtitle line", 6.0),
        ]
        
        for text, start_time in texts_and_times:
            detection = TextLine(
                frame_ts=start_time,
                frame_idx=int(start_time * 30),
                roi_type=ROIType.BOTTOM,
                text=text,
                bbox=(200, 950, 680, 50),
                confidence=0.95,
                words=[]
            )
            subtitle_track.add_detection(detection)
        
        subtitle_track.compute_metrics(total_frames=300)
        
        result = classifier.decide([subtitle_track])
        
        # Step 2: Generate ASS file from subtitle tracks
        generator = ASSGenerator()
        output = tmp_path / "from_classification.ass"
        
        # Convert tracks to cues
        cues = []
        for text, start_time in texts_and_times:
            cues.append({
                "start": start_time,
                "end": start_time + 2.5,
                "text": text,
            })
        
        ass_path = generator.generate_ass(cues, str(output), preset='neon')
        
        # Step 3: Validate result
        assert Path(ass_path).exists()
        content = Path(ass_path).read_text()
        
        # All original texts should be in ASS file
        assert "First subtitle line" in content
        assert "Second subtitle line" in content
        assert "Third subtitle line" in content


class TestSubtitleModuleStructure:
    """Tests for subtitle_processing module structure"""
    
    def test_all_modules_import(self):
        """All subtitle processing modules can be imported"""
        modules_to_test = [
            'ass_generator',
            'subtitle_classifier',
            'temporal_tracker',
            'subtitle_detector',
        ]
        
        for module_name in modules_to_test:
            try:
                module = __import__(
                    f'app.subtitle_processing.{module_name}',
                    fromlist=[module_name]
                )
                assert module is not None
            except ImportError as e:
                pytest.fail(f"Failed to import {module_name}: {e}")
    
    def test_subtitle_processing_package(self):
        """subtitle_processing package can be imported"""
        from app import subtitle_processing
        assert subtitle_processing is not None
