"""
Unit tests for Synchronization Diagnostics

Tests timestamp parsing, drift calculation, and report generation.
Sprint: S-119 to S-132
"""

import pytest
from pathlib import Path
from datetime import timedelta
from unittest.mock import mock_open, patch

from app.sync_diagnostics import (
    SyncDiagnostics,
    TimestampPair,
    SyncDiscrepancy,
    SyncReport
)


class TestTimestampPair:
    """Test TimestampPair dataclass"""
    
    def test_duration_calculation(self):
        """Test subtitle duration calculation"""
        pair = TimestampPair(
            start=timedelta(seconds=10),
            end=timedelta(seconds=15),
            index=1
        )
        
        assert pair.duration == timedelta(seconds=5)
    
    def test_duration_with_milliseconds(self):
        """Test duration with milliseconds"""
        pair = TimestampPair(
            start=timedelta(seconds=10, milliseconds=500),
            end=timedelta(seconds=12, milliseconds=300),
            index=1
        )
        
        assert pair.duration == timedelta(seconds=1, milliseconds=800)


class TestSyncDiscrepancy:
    """Test SyncDiscrepancy dataclass"""
    
    def test_max_drift_calculation(self):
        """Test maximum drift calculation"""
        discrepancy = SyncDiscrepancy(
            index=1,
            srt_start=timedelta(seconds=10),
            ass_start=timedelta(seconds=10, milliseconds=150),
            srt_end=timedelta(seconds=12),
            ass_end=timedelta(seconds=12, milliseconds=50),
            start_drift_ms=150.0,
            end_drift_ms=50.0,
            text_preview="Test"
        )
        
        assert discrepancy.max_drift_ms == 150.0
    
    def test_is_significant(self):
        """Test significance detection (>100ms)"""
        # Significant drift
        disc1 = SyncDiscrepancy(
            index=1,
            srt_start=timedelta(0),
            ass_start=timedelta(0),
            srt_end=timedelta(0),
            ass_end=timedelta(0),
            start_drift_ms=150.0,
            end_drift_ms=50.0,
            text_preview=""
        )
        assert disc1.is_significant
        
        # Not significant
        disc2 = SyncDiscrepancy(
            index=2,
            srt_start=timedelta(0),
            ass_start=timedelta(0),
            srt_end=timedelta(0),
            ass_end=timedelta(0),
            start_drift_ms=50.0,
            end_drift_ms=30.0,
            text_preview=""
        )
        assert not disc2.is_significant


class TestSyncReport:
    """Test SyncReport dataclass"""
    
    def test_sync_percentage(self):
        """Test synchronization percentage calculation"""
        report = SyncReport(
            total_subtitles=100,
            synchronized_count=95,
            desynchronized_count=5,
            max_drift_ms=200.0,
            mean_drift_ms=150.0,
            discrepancies=[],
            tolerance_ms=50.0
        )
        
        assert report.sync_percentage == 95.0
    
    def test_sync_percentage_perfect(self):
        """Test 100% sync"""
        report = SyncReport(
            total_subtitles=50,
            synchronized_count=50,
            desynchronized_count=0,
            max_drift_ms=0.0,
            mean_drift_ms=0.0,
            discrepancies=[],
            tolerance_ms=50.0
        )
        
        assert report.sync_percentage == 100.0
    
    def test_sync_percentage_zero_subtitles(self):
        """Test with zero subtitles"""
        report = SyncReport(
            total_subtitles=0,
            synchronized_count=0,
            desynchronized_count=0,
            max_drift_ms=0.0,
            mean_drift_ms=0.0,
            discrepancies=[],
            tolerance_ms=50.0
        )
        
        assert report.sync_percentage == 100.0  # Edge case: no subtitles = perfect sync
    
    def test_is_acceptable(self):
        """Test acceptability threshold (>95%)"""
        # Acceptable
        report1 = SyncReport(
            total_subtitles=100,
            synchronized_count=96,
            desynchronized_count=4,
            max_drift_ms=100.0,
            mean_drift_ms=80.0,
            discrepancies=[],
            tolerance_ms=50.0
        )
        assert report1.is_acceptable
        
        # Not acceptable
        report2 = SyncReport(
            total_subtitles=100,
            synchronized_count=90,
            desynchronized_count=10,
            max_drift_ms=300.0,
            mean_drift_ms=250.0,
            discrepancies=[],
            tolerance_ms=50.0
        )
        assert not report2.is_acceptable


class TestSyncDiagnostics:
    """Test SyncDiagnostics main class"""
    
    def test_initialization(self):
        """Test diagnostics initialization"""
        diag = SyncDiagnostics(tolerance_ms=100.0)
        
        assert diag.tolerance_ms == 100.0
    
    def test_default_tolerance(self):
        """Test default tolerance value"""
        diag = SyncDiagnostics()
        
        assert diag.tolerance_ms == 50.0


class TestTimestampParsing:
    """Test timestamp parsing"""
    
    def test_parse_srt_timestamp(self):
        """Test SRT timestamp parsing"""
        diag = SyncDiagnostics()
        
        ts = diag._parse_srt_timestamp("00:01:30,500")
        
        assert ts == timedelta(minutes=1, seconds=30, milliseconds=500)
    
    def test_parse_srt_timestamp_with_hours(self):
        """Test SRT timestamp with hours"""
        diag = SyncDiagnostics()
        
        ts = diag._parse_srt_timestamp("01:30:45,123")
        
        assert ts == timedelta(hours=1, minutes=30, seconds=45, milliseconds=123)
    
    def test_parse_srt_timestamp_invalid(self):
        """Test invalid SRT timestamp"""
        diag = SyncDiagnostics()
        
        with pytest.raises(ValueError, match="Invalid SRT timestamp"):
            diag._parse_srt_timestamp("invalid")
    
    def test_parse_ass_timestamp(self):
        """Test ASS timestamp parsing"""
        diag = SyncDiagnostics()
        
        ts = diag._parse_ass_timestamp("0:01:30.50")
        
        assert ts == timedelta(minutes=1, seconds=30, milliseconds=500)
    
    def test_parse_ass_timestamp_with_hours(self):
        """Test ASS timestamp with hours"""
        diag = SyncDiagnostics()
        
        ts = diag._parse_ass_timestamp("1:30:45.12")
        
        assert ts == timedelta(hours=1, minutes=30, seconds=45, milliseconds=120)
    
    def test_parse_ass_timestamp_invalid(self):
        """Test invalid ASS timestamp"""
        diag = SyncDiagnostics()
        
        with pytest.raises(ValueError, match="Invalid ASS timestamp"):
            diag._parse_ass_timestamp("invalid")


class TestSRTFileParsing:
    """Test SRT file parsing"""
    
    def test_parse_srt_file(self, tmp_path):
        """Test SRT file parsing"""
        srt_content = """1
00:00:20,000 --> 00:00:24,400
First subtitle

2
00:00:24,600 --> 00:00:27,800
Second subtitle
"""
        
        srt_path = tmp_path / "test.srt"
        srt_path.write_text(srt_content, encoding='utf-8')
        
        diag = SyncDiagnostics()
        timestamps = diag.parse_srt_file(srt_path)
        
        assert len(timestamps) == 2
        assert timestamps[0].index == 1
        assert timestamps[0].start == timedelta(seconds=20)
        assert timestamps[0].end == timedelta(seconds=24, milliseconds=400)
        assert "First" in timestamps[0].text
        
        assert timestamps[1].index == 2
        assert timestamps[1].start == timedelta(seconds=24, milliseconds=600)
    
    def test_parse_srt_file_not_found(self):
        """Test SRT file not found"""
        diag = SyncDiagnostics()
        
        with pytest.raises(FileNotFoundError):
            diag.parse_srt_file(Path("/nonexistent/file.srt"))
    
    def test_parse_srt_file_invalid_blocks(self, tmp_path):
        """Test SRT file with invalid blocks (should skip)"""
        srt_content = """1
00:00:01,000 --> 00:00:02,000
Valid subtitle

invalid block

2
00:00:03,000 --> 00:00:04,000
Another valid
"""
        
        srt_path = tmp_path / "test.srt"
        srt_path.write_text(srt_content, encoding='utf-8')
        
        diag = SyncDiagnostics()
        timestamps = diag.parse_srt_file(srt_path)
        
        # Should skip invalid block
        assert len(timestamps) == 2
        assert timestamps[0].index == 1
        assert timestamps[1].index == 2


class TestASSFileParsing:
    """Test ASS file parsing"""
    
    def test_parse_ass_file(self, tmp_path):
        """Test ASS file parsing"""
        ass_content = """[Script Info]
Title: Test

[V4+ Styles]
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,1,2,10,10,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:20.00,0:00:24.40,Default,,0,0,0,,First subtitle
Dialogue: 0,0:00:24.60,0:00:27.80,Default,,0,0,0,,Second subtitle
"""
        
        ass_path = tmp_path / "test.ass"
        ass_path.write_text(ass_content, encoding='utf-8')
        
        diag = SyncDiagnostics()
        timestamps = diag.parse_ass_file(ass_path)
        
        assert len(timestamps) == 2
        assert timestamps[0].start == timedelta(seconds=20)
        assert timestamps[0].end == timedelta(seconds=24, milliseconds=400)
        assert "First" in timestamps[0].text
        
        assert timestamps[1].start == timedelta(seconds=24, milliseconds=600)
        assert timestamps[1].end == timedelta(seconds=27, milliseconds=800)
    
    def test_parse_ass_file_with_formatting(self, tmp_path):
        """Test ASS file with formatting tags"""
        ass_content = """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Text with {\\b1}formatting{\\b0}
"""
        
        ass_path = tmp_path / "test.ass"
        ass_path.write_text(ass_content, encoding='utf-8')
        
        diag = SyncDiagnostics()
        timestamps = diag.parse_ass_file(ass_path)
        
        assert len(timestamps) == 1
        # Formatting tags should be removed from preview
        assert "{\\b1}" not in timestamps[0].text
        assert "formatting" in timestamps[0].text
    
    def test_parse_ass_file_not_found(self):
        """Test ASS file not found"""
        diag = SyncDiagnostics()
        
        with pytest.raises(FileNotFoundError):
            diag.parse_ass_file(Path("/nonexistent/file.ass"))


class TestDriftCalculation:
    """Test drift calculation"""
    
    def test_calculate_drift_perfect_sync(self):
        """Test perfectly synchronized subtitles"""
        srt_ts = [
            TimestampPair(timedelta(seconds=10), timedelta(seconds=12), 1),
            TimestampPair(timedelta(seconds=15), timedelta(seconds=18), 2)
        ]
        
        ass_ts = [
            TimestampPair(timedelta(seconds=10), timedelta(seconds=12), 1),
            TimestampPair(timedelta(seconds=15), timedelta(seconds=18), 2)
        ]
        
        diag = SyncDiagnostics(tolerance_ms=50.0)
        discrepancies = diag.calculate_drift(srt_ts, ass_ts)
        
        assert len(discrepancies) == 0
    
    def test_calculate_drift_with_discrepancies(self):
        """Test drift detection"""
        srt_ts = [
            TimestampPair(timedelta(seconds=10), timedelta(seconds=12), 1),
        ]
        
        # ASS has 200ms drift on start
        ass_ts = [
            TimestampPair(
                timedelta(seconds=10, milliseconds=200),
                timedelta(seconds=12),
                1
            ),
        ]
        
        diag = SyncDiagnostics(tolerance_ms=50.0)
        discrepancies = diag.calculate_drift(srt_ts, ass_ts)
        
        assert len(discrepancies) == 1
        assert discrepancies[0].start_drift_ms == 200.0
        assert discrepancies[0].end_drift_ms == 0.0
    
    def test_calculate_drift_length_mismatch(self):
        """Test with mismatched subtitle counts"""
        srt_ts = [
            TimestampPair(timedelta(seconds=10), timedelta(seconds=12), 1),
            TimestampPair(timedelta(seconds=15), timedelta(seconds=18), 2),
            TimestampPair(timedelta(seconds=20), timedelta(seconds=22), 3),
        ]
        
        ass_ts = [
            TimestampPair(timedelta(seconds=10), timedelta(seconds=12), 1),
            TimestampPair(timedelta(seconds=15), timedelta(seconds=18), 2),
        ]
        
        diag = SyncDiagnostics()
        discrepancies = diag.calculate_drift(srt_ts, ass_ts)
        
        # Should only compare first 2 (minimum length)
        # Since they're in sync, no discrepancies
        assert len(discrepancies) == 0


class TestReportGeneration:
    """Test report generation"""
    
    def test_generate_report_perfect_sync(self):
        """Test report with perfect synchronization"""
        srt_ts = [
            TimestampPair(timedelta(seconds=i), timedelta(seconds=i+2), i)
            for i in range(10)
        ]
        ass_ts = srt_ts.copy()
        
        diag = SyncDiagnostics()
        report = diag.generate_report(srt_ts, ass_ts)
        
        assert report.total_subtitles == 10
        assert report.synchronized_count == 10
        assert report.desynchronized_count == 0
        assert report.max_drift_ms == 0.0
        assert report.sync_percentage == 100.0
        assert report.is_acceptable
    
    def test_generate_report_with_drift(self):
        """Test report with some drift"""
        srt_ts = [
            TimestampPair(timedelta(seconds=10), timedelta(seconds=12), 1),
            TimestampPair(timedelta(seconds=15), timedelta(seconds=18), 2),
            TimestampPair(timedelta(seconds=20), timedelta(seconds=22), 3),
        ]
        
        # Second subtitle has 100ms drift
        ass_ts = [
            TimestampPair(timedelta(seconds=10), timedelta(seconds=12), 1),
            TimestampPair(
                timedelta(seconds=15, milliseconds=100),
                timedelta(seconds=18),
                2
            ),
            TimestampPair(timedelta(seconds=20), timedelta(seconds=22), 3),
        ]
        
        diag = SyncDiagnostics(tolerance_ms=50.0)
        report = diag.generate_report(srt_ts, ass_ts)
        
        assert report.total_subtitles == 3
        assert report.synchronized_count == 2
        assert report.desynchronized_count == 1
        assert report.max_drift_ms == 100.0
        assert report.sync_percentage == pytest.approx(66.67, rel=0.01)


class TestFileDiagnostics:
    """Test file-based diagnostics"""
    
    def test_diagnose_files(self, tmp_path):
        """Test complete file diagnosis"""
        # Create SRT file
        srt_content = """1
00:00:10,000 --> 00:00:12,000
Test subtitle
"""
        srt_path = tmp_path / "test.srt"
        srt_path.write_text(srt_content, encoding='utf-8')
        
        # Create ASS file
        ass_content = """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:10.00,0:00:12.00,Default,,0,0,0,,Test subtitle
"""
        ass_path = tmp_path / "test.ass"
        ass_path.write_text(ass_content, encoding='utf-8')
        
        diag = SyncDiagnostics()
        report = diag.diagnose_files(srt_path, ass_path)
        
        assert report.total_subtitles == 1
        assert report.synchronized_count == 1
        assert report.is_acceptable
