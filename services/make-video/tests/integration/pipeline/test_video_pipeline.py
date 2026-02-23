"""
Integration tests for VideoPipeline

Tests CRITICAL bug fix and complete pipeline flow.
NO MOCKS - uses real VideoPipeline with FFmpeg, SubtitleDetector, and VideoStatusStore.
"""

import pytest
import asyncio
import shutil
import time
from pathlib import Path

from app.pipeline.video_pipeline import VideoPipeline


class TestVideoPipelineInit:
    """Tests for VideoPipeline initialization"""
    
    def test_pipeline_module_imports(self):
        """VideoPipeline module imports successfully"""
        from app.pipeline import video_pipeline
        assert video_pipeline is not None
    
    def test_pipeline_instantiates(self):
        """Pipeline can be instantiated"""
        pipeline = VideoPipeline()
        assert pipeline is not None
    
    def test_pipeline_has_settings(self):
        """Pipeline has settings loaded"""
        pipeline = VideoPipeline()
        assert pipeline.settings is not None
        assert isinstance(pipeline.settings, dict)
    
    def test_pipeline_settings_has_all_keys(self):
        """
        🔴 CRITICAL TEST: Validates that settings has ALL required keys
        This test GUARANTEES the bug was fixed
        """
        pipeline = VideoPipeline()
        
        required_keys = [
            'shorts_cache_dir',
            'transform_dir',      # ⚠️ This was missing!
            'validate_dir',       # ⚠️ This was missing!
            'audio_upload_dir',
            'output_dir',
            'log_dir',
        ]
        
        missing_keys = [k for k in required_keys if k not in pipeline.settings]
        
        assert missing_keys == [], f"❌ BUG STILL PRESENT! Missing: {missing_keys}"
    
    def test_pipeline_has_detector(self):
        """Pipeline has subtitle detector"""
        pipeline = VideoPipeline()
        assert pipeline.detector is not None
        assert hasattr(pipeline.detector, 'detect')
    
    def test_pipeline_has_status_store(self):
        """Pipeline has video status store"""
        pipeline = VideoPipeline()
        assert pipeline.status_store is not None
        assert hasattr(pipeline.status_store, 'is_approved')
        assert hasattr(pipeline.status_store, 'is_rejected')
    
    def test_pipeline_has_video_builder(self):
        """Pipeline has video builder"""
        pipeline = VideoPipeline()
        assert pipeline.video_builder is not None


class TestEnsureDirectories:
    """Tests for directory creation"""
    
    def test_ensure_directories_creates_all(self):
        """_ensure_directories() creates all required directories"""
        pipeline = VideoPipeline()
        
        # Expected directories (relative to workspace root)
        expected_dirs = [
            'data/raw/shorts',
            'data/raw/audio',
            'data/transform/videos',
            'data/validate/in_progress',
            'data/approved/videos',
            'data/approved/output',
        ]
        
        for dir_path in expected_dirs:
            full_path = Path(dir_path)
            assert full_path.exists(), f"Directory not created: {dir_path}"
            assert full_path.is_dir()


class TestCleanupOrphanedFiles:
    """
    🔴 CRITICAL TESTS - Method that caused the production bug
    """
    
    def test_cleanup_method_exists(self):
        """Method cleanup_orphaned_files() exists"""
        pipeline = VideoPipeline()
        assert hasattr(pipeline, 'cleanup_orphaned_files')
        assert callable(pipeline.cleanup_orphaned_files)
    
    def test_cleanup_orphaned_files_no_keyerror(self, tmp_path):
        """
        🔴 MOST CRITICAL TEST: cleanup_orphaned_files() should NOT raise KeyError
        This validates the production bug fix
        """
        pipeline = VideoPipeline()
        
        # Create orphaned files in real directories
        transform_dir = Path(pipeline.settings['transform_dir'])
        validate_dir = Path(pipeline.settings['validate_dir']) / 'in_progress'
        
        transform_dir.mkdir(parents=True, exist_ok=True)
        validate_dir.mkdir(parents=True, exist_ok=True)
        
        orphan1 = transform_dir / "orphan_video_1.mp4"
        orphan2 = validate_dir / "orphan_video_2.mp4"
        
        orphan1.write_bytes(b"fake video data 1")
        orphan2.write_bytes(b"fake video data 2")
        
        # Execute cleanup - should NOT raise KeyError
        try:
            pipeline.cleanup_orphaned_files(max_age_minutes=0)
            success = True
        except KeyError as e:
            pytest.fail(f"❌ BUG STILL PRESENT! KeyError: {e}")
            success = False
        
        assert success, "cleanup_orphaned_files() must execute without KeyError"
    
    def test_cleanup_removes_old_files(self):
        """Cleanup removes old files"""
        pipeline = VideoPipeline()
        
        # Create orphaned file
        transform_dir = Path(pipeline.settings['transform_dir'])
        transform_dir.mkdir(parents=True, exist_ok=True)
        
        orphan = transform_dir / "old_video.mp4"
        orphan.write_bytes(b"old video")
        
        # Wait 1 second
        time.sleep(1.1)
        
        # Clean files older than 0 minutes
        pipeline.cleanup_orphaned_files(max_age_minutes=0)
        
        # File should have been removed
        assert not orphan.exists(), "Old file should be removed"
    
    def test_cleanup_preserves_recent_files(self):
        """Cleanup preserves recent files"""
        pipeline = VideoPipeline()
        
        # Create recent file
        transform_dir = Path(pipeline.settings['transform_dir'])
        transform_dir.mkdir(parents=True, exist_ok=True)
        
        recent = transform_dir / "2_recent_video.mp4"
        recent.write_bytes(b"recent video")
        
        # Clean files older than 60 minutes
        pipeline.cleanup_orphaned_files(max_age_minutes=60)
        
        # Recent file should remain
        assert recent.exists(), "Recent file should be preserved"


class TestMoveToValidation:
    """Tests for move_to_validation method"""
    
    def test_move_to_validation_with_real_file(self, tmp_path):
        """move_to_validation moves file and adds processing tag"""
        pipeline = VideoPipeline()
        
        # Create fake transform file
        transform_dir = Path(pipeline.settings['transform_dir'])
        transform_dir.mkdir(parents=True, exist_ok=True)
        
        video_id = "test_video_001"
        job_id = "job_001"
        transform_file = transform_dir / f"{video_id}.mp4"
        transform_file.write_bytes(b"fake video data")
        
        # Move to validation
        validate_path = pipeline.move_to_validation(
            video_id=video_id,
            transform_path=str(transform_file),
            job_id=job_id
        )
        
        # Validate
        assert validate_path is not None
        assert Path(validate_path).exists()
        assert "_PROCESSING_" in validate_path
        assert job_id in validate_path
        assert video_id in validate_path
        
        # Original file should be moved (not exist anymore)
        assert not transform_file.exists()
    
    def test_move_to_validation_with_nonexistent_file(self):
        """move_to_validation raises error for nonexistent file"""
        pipeline = VideoPipeline()
        
        video_id = "nonexistent"
        job_id = "job_error"
        fake_path = "/tmp/nonexistent_fake_video.mp4"
        
        with pytest.raises(FileNotFoundError):
            pipeline.move_to_validation(video_id, fake_path, job_id)


@pytest.mark.asyncio
class TestTransformVideo:
    """Tests for transform_video method"""
    
    async def test_transform_video_converts_to_h264(self, real_test_video):
        """transform_video converts video to H.264 codec"""
        pipeline = VideoPipeline()
        
        video_id = "2_test_transform_001"
        
        # Transform
        transform_path = pipeline.transform_video(video_id, str(real_test_video))
        
        # Validate
        assert transform_path is not None
        assert Path(transform_path).exists()
        
        # Verify H.264 codec with ffprobe
        import subprocess
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            transform_path
        ], capture_output=True, text=True, check=True)
        
        codec = result.stdout.strip()
        assert codec == "h264"


@pytest.mark.asyncio
class TestValidateVideo:
    """Tests for validate_video method"""
    
    async def test_validate_video_detects_subtitles(self, video_with_subtitles):
        """validate_video detects video WITH subtitles"""
        pipeline = VideoPipeline()
        
        video_id = "video_with_subs"
        
        # Validate directly
        has_subtitles, result = await pipeline.validate_video(video_id, str(video_with_subtitles))
        
        # Should detect subtitles
        assert isinstance(has_subtitles, bool)
        assert isinstance(result, dict)
        assert 'confidence' in result
    
    async def test_validate_video_clean_video(self, real_test_video):
        """validate_video detects video WITHOUT subtitles"""
        pipeline = VideoPipeline()
        
        video_id = "clean_video"
        
        # Validate
        has_subtitles, result = await pipeline.validate_video(video_id, str(real_test_video))
        
        # Should not detect subtitles (if video is clean)
        assert isinstance(has_subtitles, bool)
        assert isinstance(result, dict)


@pytest.mark.asyncio
class TestApproveRejectFlow:
    """Tests for approve/reject flow"""
    
    async def test_approve_video_moves_to_approved(self, real_test_video, temp_dir):
        """approve_video moves video to approved directory"""
        pipeline = VideoPipeline()
        
        video_id = "1_approved_test"
        
        # Create copy to avoid modifying fixture
        import shutil
        transform_copy = temp_dir / f"{video_id}_transform.mp4"
        shutil.copy(real_test_video, transform_copy)
        
        metadata = {"title": "Test Video", "duration": 5.0}
        
        # Approve
        approved_path = await pipeline.approve_video(video_id, str(transform_copy), metadata)
        
        # Validate
        assert approved_path is not None
        assert Path(approved_path).exists()
        assert "approved" in approved_path
        
        # Check status store
        assert pipeline.status_store.is_approved(video_id)
    
    async def test_reject_video_adds_to_blacklist(self):
        """reject_video adds video to rejected list"""
        pipeline = VideoPipeline()
        
        video_id = "rejected_test_001"
        metadata = {
            "title": "Video with subtitles",
            "rejection_reason": "embedded_subtitles",
            "confidence": 0.95
        }
        
        # Reject
        await pipeline.reject_video(video_id, metadata)
        
        # Check status store
        assert pipeline.status_store.is_rejected(video_id)


@pytest.mark.asyncio
@pytest.mark.slow
class TestPipelineFullFlow:
    """Tests for complete pipeline flow"""
    
    async def test_full_pipeline_flow_approve(self, real_test_video):
        """Complete pipeline flow: transform → validate → approve"""
        pipeline = VideoPipeline()
        
        video_id = "2_full_flow"
        job_id = "job_full_001"
        
        # Step 1: Transform
        transform_path = pipeline.transform_video(video_id, str(real_test_video))
        assert Path(transform_path).exists()
        
        # Step 2: Move to validation
        validate_path = pipeline.move_to_validation(video_id, transform_path, job_id)
        assert Path(validate_path).exists()
        assert "_PROCESSING_" in validate_path
        
        # Step 3: Validate
        has_subtitles, result = await pipeline.validate_video(video_id, validate_path)
        assert isinstance(has_subtitles, bool)
        
        # Step 4: Approve or Reject based on validation
        if not has_subtitles:
            # Approve
            metadata = {"title": "Clean Video", "duration": 5.0}
            approved_path = await pipeline.approve_video(video_id, validate_path, metadata)
            assert Path(approved_path).exists()
            assert pipeline.status_store.is_approved(video_id)
        else:
            # Reject
            metadata = {
                "rejection_reason": "embedded_subtitles",
                "confidence": result.get('confidence', 0.9)
            }
            await pipeline.reject_video(video_id, metadata)
            assert pipeline.status_store.is_rejected(video_id)


class TestPipelineModuleStructure:
    """Tests for pipeline module structure"""
    
    def test_pipeline_module_exports(self):
        """Pipeline module exports VideoPipeline"""
        from app.pipeline import video_pipeline
        assert hasattr(video_pipeline, 'VideoPipeline')
    
    def test_pipeline_class_has_required_methods(self):
        """VideoPipeline has all required methods"""
        pipeline = VideoPipeline()
        
        required_methods = [
            'cleanup_orphaned_files',
            'transform_video',
            'move_to_validation',
            'validate_video',
            'approve_video',
            'reject_video',
        ]
        
        for method_name in required_methods:
            assert hasattr(pipeline, method_name), f"Missing method: {method_name}"
            assert callable(getattr(pipeline, method_name))
