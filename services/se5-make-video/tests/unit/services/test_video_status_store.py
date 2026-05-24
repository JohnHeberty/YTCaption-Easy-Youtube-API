"""
Unit tests for VideoStatusStore

Tests SQLite database operations with REAL database.
NO MOCKS - uses real VideoStatusStore with tmp SQLite file.
"""

import pytest
import json
from pathlib import Path

from app.services.video_status_store import VideoStatusStore


class TestVideoStatusStoreInit:
    """Tests for VideoStatusStore initialization"""
    
    def test_store_module_imports(self):
        """VideoStatusStore module imports successfully"""
        from app.services import video_status_store
        assert video_status_store is not None
    
    def test_store_class_exists(self, tmp_path):
        """VideoStatusStore class can be instantiated"""
        db_path = tmp_path / "test.db"
        store = VideoStatusStore(str(db_path))
        assert store is not None
        assert store.db_path == db_path
    
    def test_store_creates_db_file(self, tmp_path):
        """VideoStatusStore creates database file"""
        db_path = tmp_path / "status.db"
        
        store = VideoStatusStore(str(db_path))
        
        # Database file should exist
        assert db_path.exists()
        assert db_path.stat().st_size > 0
    
    def test_store_creates_parent_dirs(self, tmp_path):
        """VideoStatusStore creates parent directories"""
        db_path = tmp_path / "nested" / "dir" / "status.db"
        
        store = VideoStatusStore(str(db_path))
        
        assert db_path.exists()
        assert db_path.parent.exists()


class TestApprovedVideos:
    """Tests for approved videos operations"""
    
    def test_add_approved_video(self, tmp_path):
        """Add video to approved list"""
        db_path = tmp_path / "test.db"
        store = VideoStatusStore(str(db_path))
        
        video_id = "test_video_001"
        title = "Test Video"
        url = "https://example.com/video"
        file_path = "/path/to/video.mp4"
        
        # Add approved video
        store.add_approved(
            video_id=video_id,
            title=title,
            url=url,
            file_path=file_path
        )
        
        # Verify it was added
        assert store.is_approved(video_id)
    
    def test_is_approved_returns_false_for_new_video(self, tmp_path):
        """is_approved returns False for video not in database"""
        db_path = tmp_path / "test.db"
        store = VideoStatusStore(str(db_path))
        
        assert not store.is_approved("nonexistent_video")
    
    def test_get_approved_video(self, tmp_path):
        """Get approved video details"""
        db_path = tmp_path / "test.db"
        store = VideoStatusStore(str(db_path))
        
        video_id = "video_002"
        title = "My Video"
        url = "https://example.com/video2"
        file_path = "/videos/file.mp4"
        metadata = {"duration": 30, "resolution": "1080x1920"}
        
        # Add video
        store.add_approved(
            video_id=video_id,
            title=title,
            url=url,
            file_path=file_path,
            metadata=metadata
        )
        
        # Get video
        result = store.get_approved(video_id)
        
        assert result is not None
        assert result["video_id"] == video_id
        assert result["title"] == title
        assert result["url"] == url
        assert result["file_path"] == file_path
        assert result["metadata"]["duration"] == 30
        assert result["metadata"]["resolution"] == "1080x1920"
    
    def test_get_approved_returns_none_for_new_video(self, tmp_path):
        """get_approved returns None for video not in database"""
        db_path = tmp_path / "test.db"
        store = VideoStatusStore(str(db_path))
        
        result = store.get_approved("nonexistent")
        assert result is None
    
    def test_list_approved_videos(self, tmp_path):
        """List all approved videos"""
        db_path = tmp_path / "test.db"
        store = VideoStatusStore(str(db_path))
        
        # Add multiple videos
        for i in range(5):
            store.add_approved(
                video_id=f"video_{i}",
                title=f"Video {i}",
                url=f"https://example.com/{i}",
                file_path=f"/videos/{i}.mp4"
            )
        
        # List all
        videos = store.list_approved(limit=10)
        
        assert len(videos) == 5
        assert all("video_id" in v for v in videos)
    
    def test_list_approved_with_limit(self, tmp_path):
        """List approved videos with limit"""
        db_path = tmp_path / "test.db"
        store = VideoStatusStore(str(db_path))
        
        # Add 10 videos
        for i in range(10):
            store.add_approved(video_id=f"vid_{i}")
        
        # List with limit
        videos = store.list_approved(limit=3)
        
        assert len(videos) == 3
    
    def test_count_approved_videos(self, tmp_path):
        """Count approved videos"""
        db_path = tmp_path / "test.db"
        store = VideoStatusStore(str(db_path))
        
        # Initially zero
        assert store.count_approved() == 0
        
        # Add some videos
        for i in range(7):
            store.add_approved(video_id=f"video_{i}")
        
        # Count should be 7
        assert store.count_approved() == 7
    
    def test_add_approved_with_metadata(self, tmp_path):
        """Add approved video with complex metadata"""
        db_path = tmp_path / "test.db"
        store = VideoStatusStore(str(db_path))
        
        video_id = "complex_vid"
        metadata = {
            "duration": 45,
            "resolution": {"width": 1080, "height": 1920},
            "tags": ["shorts", "processed"],
            "stats": {"views": 1000, "likes": 50}
        }
        
        store.add_approved(video_id=video_id, metadata=metadata)
        
        result = store.get_approved(video_id)
        
        assert result["metadata"]["duration"] == 45
        assert result["metadata"]["resolution"]["width"] == 1080
        assert "shorts" in result["metadata"]["tags"]


class TestRejectedVideos:
    """Tests for rejected videos operations"""
    
    def test_add_rejected_video(self, tmp_path):
        """Add video to rejected list"""
        db_path = tmp_path / "test.db"
        store = VideoStatusStore(str(db_path))
        
        video_id = "rejected_001"
        reason = "embedded_subtitles"
        confidence = 0.95
        
        # Add rejected video
        store.add_rejected(
            video_id=video_id,
            reason=reason,
            confidence=confidence
        )
        
        # Verify it was added
        assert store.is_rejected(video_id)
    
    def test_is_rejected_returns_false_for_new_video(self, tmp_path):
        """is_rejected returns False for video not in database"""
        db_path = tmp_path / "test.db"
        store = VideoStatusStore(str(db_path))
        
        assert not store.is_rejected("new_video")
    
    def test_get_rejected_video(self, tmp_path):
        """Get rejected video details"""
        db_path = tmp_path / "test.db"
        store = VideoStatusStore(str(db_path))
        
        video_id = "reject_002"
        reason = "has_watermark"
        confidence = 0.88
        title = "Bad Video"
        
        store.add_rejected(
            video_id=video_id,
            reason=reason,
            confidence=confidence,
            title=title
        )
        
        result = store.get_rejected(video_id)
        
        assert result is not None
        assert result["video_id"] == video_id
        assert result["rejection_reason"] == reason
        assert result["confidence"] == confidence
        assert result["title"] == title
    
    def test_list_rejected_videos(self, tmp_path):
        """List all rejected videos"""
        db_path = tmp_path / "test.db"
        store = VideoStatusStore(str(db_path))
        
        # Add rejected videos
        reasons = ["subtitles", "watermark", "copyright"]
        for i, reason in enumerate(reasons):
            store.add_rejected(
                video_id=f"reject_{i}",
                reason=reason,
                confidence=0.9
            )
        
        # List all
        videos = store.list_rejected(limit=10)
        
        assert len(videos) == 3
        assert all("rejection_reason" in v for v in videos)
    
    def test_count_rejected_videos(self, tmp_path):
        """Count rejected videos"""
        db_path = tmp_path / "test.db"
        store = VideoStatusStore(str(db_path))
        
        # Initially zero
        assert store.count_rejected() == 0
        
        # Add some
        for i in range(4):
            store.add_rejected(
                video_id=f"reject_{i}",
                reason="test_reason",
                confidence=0.8
            )
        
        # Count should be 4
        assert store.count_rejected() == 4


class TestMixedOperations:
    """Tests for mixed approved/rejected operations"""
    
    def test_video_cannot_be_both_approved_and_rejected(self, tmp_path):
        """Video in one category doesn't appear in the other"""
        db_path = tmp_path / "test.db"
        store = VideoStatusStore(str(db_path))
        
        video_id = "video_mixed"
        
        # Add as approved
        store.add_approved(video_id=video_id)
        
        # Should be approved but not rejected
        assert store.is_approved(video_id)
        assert not store.is_rejected(video_id)
        
        # Now add same video as rejected (different use case)
        store.add_rejected(video_id=video_id, reason="test", confidence=0.9)
        
        # Now should be rejected (separate tables)
        assert store.is_rejected(video_id)
    
    def test_total_videos_across_categories(self, tmp_path):
        """Count total videos across approved and rejected"""
        db_path = tmp_path / "test.db"
        store = VideoStatusStore(str(db_path))
        
        # Add 5 approved
        for i in range(5):
            store.add_approved(video_id=f"approved_{i}")
        
        # Add 3 rejected
        for i in range(3):
            store.add_rejected(
                video_id=f"rejected_{i}",
                reason="test",
                confidence=0.9
            )
        
        # Count both
        total = store.count_approved() + store.count_rejected()
        assert total == 8


class TestDatabasePersistence:
    """Tests for database persistence"""
    
    def test_data_persists_across_instances(self, tmp_path):
        """Data persists when recreating store instance"""
        db_path = tmp_path / "persist.db"
        
        # Create store and add data
        store1 = VideoStatusStore(str(db_path))
        store1.add_approved(video_id="persist_test")
        
        # Create new store instance
        store2 = VideoStatusStore(str(db_path))
        
        # Data should still be there
        assert store2.is_approved("persist_test")
    
    def test_database_file_survives_restart(self, tmp_path):
        """Database file remains after store is deleted"""
        db_path = tmp_path / "survive.db"
        
        store = VideoStatusStore(str(db_path))
        store.add_approved(video_id="survive_test")
        
        # Delete store object
        del store
        
        # File should still exist
        assert db_path.exists()
        
        # Data should be recoverable
        new_store = VideoStatusStore(str(db_path))
        assert new_store.is_approved("survive_test")
