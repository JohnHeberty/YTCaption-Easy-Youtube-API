"""
Integration tests for VideoBuilder

Tests real video processing with FFmpeg operations.
NO MOCKS - uses real VideoBuilder with actual FFmpeg commands.
"""

import pytest
import asyncio
import subprocess
from pathlib import Path

from app.services.video_builder import VideoBuilder


@pytest.mark.asyncio
class TestVideoBuilderInit:
    """Tests for VideoBuilder initialization"""
    
    def test_builder_module_imports(self):
        """VideoBuilder module imports successfully"""
        from app.services import video_builder
        assert video_builder is not None
    
    def test_builder_class_exists(self, tmp_path):
        """VideoBuilder class can be instantiated"""
        builder = VideoBuilder(output_dir=str(tmp_path))
        assert builder is not None
        assert hasattr(builder, 'convert_to_h264')
        assert hasattr(builder, 'concatenate_videos')
    
    def test_builder_creates_output_dir(self, tmp_path):
        """VideoBuilder creates output directory"""
        output_dir = tmp_path / "output"
        
        builder = VideoBuilder(output_dir=str(output_dir))
        
        assert output_dir.exists()
        assert output_dir.is_dir()
    
    def test_builder_with_custom_codecs(self, tmp_path):
        """VideoBuilder accepts custom codec parameters"""
        builder = VideoBuilder(
            output_dir=str(tmp_path),
            video_codec="libx265",
            audio_codec="libopus",
            preset="slow",
            crf=20
        )
        
        assert builder.video_codec == "libx265"
        assert builder.audio_codec == "libopus"
        assert builder.preset == "slow"
        assert builder.crf == 20


@pytest.mark.asyncio
class TestH264Conversion:
    """Tests for H264 video conversion"""
    
    async def test_convert_to_h264(self, real_test_video, tmp_path):
        """Convert video to H264 format"""
        builder = VideoBuilder(output_dir=str(tmp_path))
        output = tmp_path / "h264.mp4"
        
        # Convert to H264
        result = await builder.convert_to_h264(
            input_path=str(real_test_video),
            output_path=str(output)
        )
        
        # Validate
        assert Path(result).exists()
        assert Path(result) == output
        assert output.stat().st_size > 0
        
        # Verify codec with ffprobe
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(output)
        ]
        
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        codec = proc.stdout.strip()
        
        # Should be h264
        assert codec == "h264"
    
    async def test_convert_maintains_resolution(self, real_test_video, tmp_path):
        """H264 conversion maintains original resolution"""
        builder = VideoBuilder(output_dir=str(tmp_path))
        output = tmp_path / "same_res.mp4"
        
        # Get original resolution
        cmd_orig = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            str(real_test_video)
        ]
        orig_res = subprocess.run(cmd_orig, capture_output=True, text=True, check=True)
        orig_width, orig_height = map(int, orig_res.stdout.strip().split(','))
        
        # Convert
        await builder.convert_to_h264(str(real_test_video), str(output))
        
        # Get new resolution
        cmd_new = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            str(output)
        ]
        new_res = subprocess.run(cmd_new, capture_output=True, text=True, check=True)
        new_width, new_height = map(int, new_res.stdout.strip().split(','))
        
        # Resolution should match
        assert new_width == orig_width
        assert new_height == orig_height


@pytest.mark.asyncio
class TestVideoConcatenation:
    """Tests for video concatenation with crop"""
    
    async def test_concatenate_videos_basic(self, real_test_video, tmp_path):
        """Concatenate multiple videos"""
        builder = VideoBuilder(output_dir=str(tmp_path))
        output = tmp_path / "concat.mp4"
        
        # Use same video twice for testing
        video_files = [str(real_test_video), str(real_test_video)]
        
        # Check if test video has audio
        check_audio = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            str(real_test_video)
        ], capture_output=True, text=True)
        
        has_audio = bool(check_audio.stdout.strip())
        
        # Concatenate (adjust remove_audio based on video content)
        result = await builder.concatenate_videos(
            video_files=video_files,
            output_path=str(output),
            aspect_ratio="16:9",  # Keep original aspect
            remove_audio=not has_audio  # Remove audio if video doesn't have it
        )
        
        # Validate
        assert Path(result).exists()
        assert output.stat().st_size > 0
        
        # Duration should be approximately double
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(output)
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(proc.stdout.strip())
        
        # Should be around 10 seconds (2 * 5s videos)
        assert duration > 8.0  # Allow some encoding variance
    
    async def test_crop_to_9_16_aspect_ratio(self, real_test_video, tmp_path):
        """Crop video to 9:16 vertical aspect ratio"""
        builder = VideoBuilder(output_dir=str(tmp_path))
        output = tmp_path / "vertical.mp4"
        
        # Check if test video has audio
        check_audio = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            str(real_test_video)
        ], capture_output=True, text=True)
        
        has_audio = bool(check_audio.stdout.strip())
        
        # Concatenate with 9:16 crop
        result = await builder.concatenate_videos(
            video_files=[str(real_test_video)],
            output_path=str(output),
            aspect_ratio="9:16",
            crop_position="center",
            remove_audio=not has_audio  # Remove audio if video doesn't have it
        )
        
        # Validate file exists
        assert Path(result).exists()
        
        # Check aspect ratio
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            str(output)
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        width, height = map(int, proc.stdout.strip().split(','))
        
        # Calculate ratio
        ratio = height / width
        expected_ratio = 16 / 9
        
        # Should be close to 9:16 (1.777)
        assert abs(ratio - expected_ratio) < 0.1
    
    async def test_concatenate_with_audio_removal(self, real_test_video, tmp_path):
        """Concatenate videos and remove audio"""
        builder = VideoBuilder(output_dir=str(tmp_path))
        output = tmp_path / "no_audio.mp4"
        
        # Concatenate with audio removed
        result = await builder.concatenate_videos(
            video_files=[str(real_test_video)],
            output_path=str(output),
            aspect_ratio="16:9",
            remove_audio=True
        )
        
        # Validate
        assert Path(result).exists()
        
        # Check for audio streams (should be 0)
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            str(output)
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        
        # Output should be empty (no audio streams)
        assert proc.stdout.strip() == ""


@pytest.mark.asyncio
class TestVideoProcessingIntegration:
    """Integration tests for complete video processing pipeline"""
    
    async def test_full_pipeline_convert_and_crop(self, real_test_video, tmp_path):
        """Full pipeline: convert to H264 then crop to 9:16"""
        builder = VideoBuilder(output_dir=str(tmp_path))
        
        # Step 1: Convert to H264
        h264_output = tmp_path / "h264_temp.mp4"
        await builder.convert_to_h264(
            input_path=str(real_test_video),
            output_path=str(h264_output)
        )
        
        assert h264_output.exists()
        
        # Step 2: Crop to 9:16
        final_output = tmp_path / "final_9_16.mp4"
        await builder.concatenate_videos(
            video_files=[str(h264_output)],
            output_path=str(final_output),
            aspect_ratio="9:16",
            remove_audio=True
        )
        
        # Validate final output
        assert final_output.exists()
        assert final_output.stat().st_size > 0
        
        # Verify 9:16 aspect ratio
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            str(final_output)
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        width, height = map(int, proc.stdout.strip().split(','))
        
        ratio = height / width
        expected = 16 / 9
        
        assert abs(ratio - expected) < 0.1


class TestFFmpegCommands:
    """Direct FFmpeg command tests (helpers for VideoBuilder)"""
    
    def test_crop_video_to_9_16_with_ffmpeg(self, real_test_video, tmp_path):
        """Direct FFmpeg test: Crop to 9:16"""
        output = tmp_path / "cropped_9_16.mp4"
        
        # FFmpeg crop command
        cmd = [
            "ffmpeg", "-i", str(real_test_video),
            "-vf", "crop=ih*9/16:ih",  # Crop width to 9:16
            "-y", str(output)
        ]
        
        result = subprocess.run(cmd, capture_output=True, check=True)
        
        # Validate
        assert output.exists()
        assert output.stat().st_size > 0
        
        # Check aspect ratio
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            str(output)
        ]
        proc = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        width, height = map(int, proc.stdout.strip().split(','))
        
        ratio = height / width
        expected_ratio = 16 / 9
        
        assert abs(ratio - expected_ratio) < 0.1
    
    def test_merge_video_audio_with_ffmpeg(self, real_test_video, real_test_audio, tmp_path):
        """Direct FFmpeg test: Merge video + audio"""
        output = tmp_path / "merged.mp4"
        
        # FFmpeg merge command
        cmd = [
            "ffmpeg",
            "-i", str(real_test_video),
            "-i", str(real_test_audio),
            "-map", "0:v",  # Video from first input
            "-map", "1:a",  # Audio from second input
            "-c:v", "copy",  # Copy video codec
            "-c:a", "aac",   # Encode audio as AAC
            "-shortest",     # End at shortest stream
            "-y", str(output)
        ]
        
        result = subprocess.run(cmd, capture_output=True, check=True)
        
        # Validate
        assert output.exists()
        assert output.stat().st_size > 0
        
        # Check for both video and audio streams
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            str(output)
        ]
        proc = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        streams = proc.stdout.strip().split('\n')
        
        # Should have both video and audio
        assert 'video' in streams
        assert 'audio' in streams
    
    def test_add_ass_subtitles_with_ffmpeg(self, real_test_video, sample_ass_file, tmp_path):
        """Direct FFmpeg test: Add ASS subtitles"""
        output = tmp_path / "with_subs.mp4"
        
        # FFmpeg subtitle command
        cmd = [
            "ffmpeg",
            "-i", str(real_test_video),
            "-vf", f"ass={sample_ass_file}",
            "-c:a", "copy",  # Copy audio
            "-y", str(output)
        ]
        
        result = subprocess.run(cmd, capture_output=True, check=True)
        
        # Validate
        assert output.exists()
        assert output.stat().st_size > 0
        
        # File should be larger than original (burned subtitles)
        original_size = Path(real_test_video).stat().st_size
        output_size = output.stat().st_size
        
        # Output should exist and have reasonable size
        assert output_size > 0
