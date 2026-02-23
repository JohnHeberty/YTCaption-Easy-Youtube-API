"""
Synchronization Diagnostics

Compares SRT and ASS subtitle timestamps to detect desynchronization.
Calculates temporal drift and generates diagnostic reports.

Sprint: S-119 to S-132
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import timedelta

from common.log_utils.structured import get_logger

logger = get_logger(__name__)


@dataclass
class TimestampPair:
    """Represents a subtitle timestamp pair (start, end)"""
    start: timedelta
    end: timedelta
    index: int
    text: str = ""
    
    @property
    def duration(self) -> timedelta:
        """Calculate subtitle duration"""
        return self.end - self.start


@dataclass
class SyncDiscrepancy:
    """Represents a synchronization discrepancy between SRT and ASS"""
    index: int
    srt_start: timedelta
    ass_start: timedelta
    srt_end: timedelta
    ass_end: timedelta
    start_drift_ms: float
    end_drift_ms: float
    text_preview: str
    
    @property
    def max_drift_ms(self) -> float:
        """Maximum drift between start and end"""
        return max(abs(self.start_drift_ms), abs(self.end_drift_ms))
    
    @property
    def is_significant(self) -> bool:
        """Check if drift is significant (>100ms)"""
        return self.max_drift_ms > 100.0


@dataclass
class SyncReport:
    """Comprehensive synchronization diagnostic report"""
    total_subtitles: int
    synchronized_count: int
    desynchronized_count: int
    max_drift_ms: float
    mean_drift_ms: float
    discrepancies: List[SyncDiscrepancy]
    tolerance_ms: float
    
    @property
    def sync_percentage(self) -> float:
        """Percentage of synchronized subtitles"""
        if self.total_subtitles == 0:
            return 100.0
        return (self.synchronized_count / self.total_subtitles) * 100.0
    
    @property
    def is_acceptable(self) -> bool:
        """Check if synchronization is acceptable (>95% sync)"""
        return self.sync_percentage >= 95.0


class SyncDiagnostics:
    """
    Synchronization diagnostics tool
    
    Compares SRT and ASS timestamps to detect drift and desynchronization.
    Provides detailed reports for debugging and validation.
    """
    
    # SRT timestamp regex: 00:00:20,000 --> 00:00:24,400
    SRT_TIMESTAMP_PATTERN = re.compile(
        r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*'
        r'(\d{2}):(\d{2}):(\d{2}),(\d{3})'
    )
    
    # ASS timestamp regex: 0:00:20.00
    ASS_TIMESTAMP_PATTERN = re.compile(
        r'(\d+):(\d{2}):(\d{2})\.(\d{2})'
    )
    
    def __init__(self, tolerance_ms: float = 50.0):
        """
        Initialize sync diagnostics
        
        Args:
            tolerance_ms: Acceptable drift tolerance in milliseconds
        """
        self.tolerance_ms = tolerance_ms
        
        logger.info(
            "sync_diagnostics_initialized",
            tolerance_ms=tolerance_ms
        )
    
    def _parse_srt_timestamp(self, timestamp_str: str) -> timedelta:
        """
        Parse SRT timestamp string to timedelta
        
        Args:
            timestamp_str: SRT timestamp (HH:MM:SS,mmm)
            
        Returns:
            timedelta object
            
        Raises:
            ValueError: If timestamp format is invalid
        """
        match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', timestamp_str.strip())
        if not match:
            raise ValueError(f"Invalid SRT timestamp: {timestamp_str}")
        
        hours, minutes, seconds, milliseconds = map(int, match.groups())
        return timedelta(
            hours=hours,
            minutes=minutes,
            seconds=seconds,
            milliseconds=milliseconds
        )
    
    def _parse_ass_timestamp(self, timestamp_str: str) -> timedelta:
        """
        Parse ASS timestamp string to timedelta
        
        Args:
            timestamp_str: ASS timestamp (H:MM:SS.CC)
            
        Returns:
            timedelta object
            
        Raises:
            ValueError: If timestamp format is invalid
        """
        match = self.ASS_TIMESTAMP_PATTERN.match(timestamp_str.strip())
        if not match:
            raise ValueError(f"Invalid ASS timestamp: {timestamp_str}")
        
        hours, minutes, seconds, centiseconds = map(int, match.groups())
        return timedelta(
            hours=hours,
            minutes=minutes,
            seconds=seconds,
            milliseconds=centiseconds * 10  # centiseconds to milliseconds
        )
    
    def parse_srt_file(self, srt_path: Path) -> List[TimestampPair]:
        """
        Parse SRT file and extract timestamps
        
        Args:
            srt_path: Path to SRT file
            
        Returns:
            List of TimestampPair objects
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If SRT format is invalid
        """
        srt_path = Path(srt_path)
        
        if not srt_path.exists():
            raise FileNotFoundError(f"SRT file not found: {srt_path}")
        
        content = srt_path.read_text(encoding='utf-8')
        timestamps = []
        
        # Split by double newline (subtitle separator)
        blocks = re.split(r'\n\s*\n', content.strip())
        
        for block in blocks:
            if not block.strip():
                continue
            
            lines = block.strip().split('\n')
            
            if len(lines) < 3:
                continue
            
            try:
                # Line 1: Index
                index = int(lines[0].strip())
                
                # Line 2: Timestamps
                timestamp_line = lines[1].strip()
                match = self.SRT_TIMESTAMP_PATTERN.match(timestamp_line)
                
                if not match:
                    logger.warning(
                        "srt_timestamp_parse_failed",
                        line=timestamp_line
                    )
                    continue
                
                # Parse timestamps
                start_parts = match.groups()[:4]
                end_parts = match.groups()[4:]
                
                start_time = timedelta(
                    hours=int(start_parts[0]),
                    minutes=int(start_parts[1]),
                    seconds=int(start_parts[2]),
                    milliseconds=int(start_parts[3])
                )
                
                end_time = timedelta(
                    hours=int(end_parts[0]),
                    minutes=int(end_parts[1]),
                    seconds=int(end_parts[2]),
                    milliseconds=int(end_parts[3])
                )
                
                # Lines 3+: Text
                text = '\n'.join(lines[2:])
                
                timestamps.append(TimestampPair(
                    start=start_time,
                    end=end_time,
                    index=index,
                    text=text[:50]  # Preview only
                ))
                
            except (ValueError, IndexError) as e:
                logger.warning(
                    "srt_block_parse_error",
                    block_preview=block[:100],
                    error=str(e)
                )
                continue
        
        logger.info(
            "srt_file_parsed",
            path=str(srt_path),
            subtitle_count=len(timestamps)
        )
        
        return timestamps
    
    def parse_ass_file(self, ass_path: Path) -> List[TimestampPair]:
        """
        Parse ASS file and extract timestamps from Dialogue events
        
        Args:
            ass_path: Path to ASS file
            
        Returns:
            List of TimestampPair objects
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If ASS format is invalid
        """
        ass_path = Path(ass_path)
        
        if not ass_path.exists():
            raise FileNotFoundError(f"ASS file not found: {ass_path}")
        
        content = ass_path.read_text(encoding='utf-8')
        timestamps = []
        
        # Find dialogue lines
        dialogue_pattern = re.compile(
            r'Dialogue:\s*\d+,(\d+:\d{2}:\d{2}\.\d{2}),(\d+:\d{2}:\d{2}\.\d{2}),'
            r'[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,(.*)$',
            re.MULTILINE
        )
        
        for index, match in enumerate(dialogue_pattern.finditer(content), start=1):
            start_str, end_str, text = match.groups()
            
            try:
                start_time = self._parse_ass_timestamp(start_str)
                end_time = self._parse_ass_timestamp(end_str)
                
                # Remove ASS formatting from text preview
                text_clean = re.sub(r'\\N', ' ', text)  # Convert line breaks
                text_clean = re.sub(r'\{[^}]*\}', '', text_clean)  # Remove tags
                
                timestamps.append(TimestampPair(
                    start=start_time,
                    end=end_time,
                    index=index,
                    text=text_clean[:50]  # Preview only
                ))
                
            except ValueError as e:
                logger.warning(
                    "ass_dialogue_parse_error",
                    line=match.group(0)[:100],
                    error=str(e)
                )
                continue
        
        logger.info(
            "ass_file_parsed",
            path=str(ass_path),
            dialogue_count=len(timestamps)
        )
        
        return timestamps
    
    def calculate_drift(
        self,
        srt_timestamps: List[TimestampPair],
        ass_timestamps: List[TimestampPair]
    ) -> List[SyncDiscrepancy]:
        """
        Calculate drift between SRT and ASS timestamps
        
        Args:
            srt_timestamps: List of SRT timestamp pairs
            ass_timestamps: List of ASS timestamp pairs
            
        Returns:
            List of SyncDiscrepancy objects where drift exceeds tolerance
        """
        discrepancies = []
        
        # Ensure same length
        min_length = min(len(srt_timestamps), len(ass_timestamps))
        
        if len(srt_timestamps) != len(ass_timestamps):
            logger.warning(
                "subtitle_count_mismatch",
                srt_count=len(srt_timestamps),
                ass_count=len(ass_timestamps),
                comparing=min_length
            )
        
        for i in range(min_length):
            srt_ts = srt_timestamps[i]
            ass_ts = ass_timestamps[i]
            
            # Calculate drift in milliseconds
            start_drift_ms = (ass_ts.start - srt_ts.start).total_seconds() * 1000
            end_drift_ms = (ass_ts.end - srt_ts.end).total_seconds() * 1000
            
            # Check if exceeds tolerance
            if abs(start_drift_ms) > self.tolerance_ms or abs(end_drift_ms) > self.tolerance_ms:
                discrepancies.append(SyncDiscrepancy(
                    index=srt_ts.index,
                    srt_start=srt_ts.start,
                    ass_start=ass_ts.start,
                    srt_end=srt_ts.end,
                    ass_end=ass_ts.end,
                    start_drift_ms=start_drift_ms,
                    end_drift_ms=end_drift_ms,
                    text_preview=srt_ts.text
                ))
        
        logger.info(
            "drift_calculation_complete",
            total_compared=min_length,
            discrepancies_found=len(discrepancies)
        )
        
        return discrepancies
    
    def generate_report(
        self,
        srt_timestamps: List[TimestampPair],
        ass_timestamps: List[TimestampPair]
    ) -> SyncReport:
        """
        Generate comprehensive synchronization report
        
        Args:
            srt_timestamps: List of SRT timestamp pairs
            ass_timestamps: List of ASS timestamp pairs
            
        Returns:
            SyncReport object with complete diagnostics
        """
        discrepancies = self.calculate_drift(srt_timestamps, ass_timestamps)
        
        total = min(len(srt_timestamps), len(ass_timestamps))
        desync_count = len(discrepancies)
        sync_count = total - desync_count
        
        # Calculate drift statistics
        if discrepancies:
            max_drift = max(d.max_drift_ms for d in discrepancies)
            mean_drift = sum(d.max_drift_ms for d in discrepancies) / len(discrepancies)
        else:
            max_drift = 0.0
            mean_drift = 0.0
        
        report = SyncReport(
            total_subtitles=total,
            synchronized_count=sync_count,
            desynchronized_count=desync_count,
            max_drift_ms=max_drift,
            mean_drift_ms=mean_drift,
            discrepancies=discrepancies,
            tolerance_ms=self.tolerance_ms
        )
        
        logger.info(
            "sync_report_generated",
            total=total,
            synchronized=sync_count,
            desynchronized=desync_count,
            sync_percentage=report.sync_percentage,
            acceptable=report.is_acceptable
        )
        
        return report
    
    def diagnose_files(
        self,
        srt_path: Path,
        ass_path: Path
    ) -> SyncReport:
        """
        Diagnose synchronization between SRT and ASS files
        
        Args:
            srt_path: Path to SRT file
            ass_path: Path to ASS file
            
        Returns:
            SyncReport with complete diagnostics
            
        Raises:
            FileNotFoundError: If files don't exist
            ValueError: If parsing fails
        """
        srt_timestamps = self.parse_srt_file(srt_path)
        ass_timestamps = self.parse_ass_file(ass_path)
        
        return self.generate_report(srt_timestamps, ass_timestamps)
