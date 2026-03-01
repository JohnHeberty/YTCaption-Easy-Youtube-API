"""
Testes unitários para datetime_utils.helpers
Coverage target: > 95%
"""
import pytest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from .helpers import (
    ensure_timezone_aware,
    ensure_timezone_aware_utc_base,
    safe_datetime_subtract,
    safe_datetime_compare,
    format_duration_safe,
    normalize_model_datetimes
)
from . import now_brazil


# Timezone constants for tests
BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
UTC_TZ = timezone.utc


class TestEnsureTimezoneAware:
    """Test suite for ensure_timezone_aware function"""
    
    def test_none_returns_none(self):
        """Test that None input returns None"""
        result = ensure_timezone_aware(None)
        assert result is None
    
    def test_naive_datetime_gets_brazil_tz(self):
        """Test naive datetime is converted to Brazil timezone"""
        naive_dt = datetime(2026, 2, 28, 15, 30, 0)
        result = ensure_timezone_aware(naive_dt)
        
        assert result.tzinfo == BRAZIL_TZ
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 28
        assert result.hour == 15
        assert result.minute == 30
    
    def test_aware_datetime_preserved(self):
        """Test timezone-aware datetime is returned unchanged"""
        aware_dt = datetime(2026, 2, 28, 15, 30, 0, tzinfo=UTC_TZ)
        result = ensure_timezone_aware(aware_dt)
        
        assert result == aware_dt
        assert result.tzinfo == UTC_TZ
    
    def test_brazil_tz_preserved(self):
        """Test Brazil timezone datetime is preserved"""
        brazil_dt = datetime(2026, 2, 28, 15, 30, 0, tzinfo=BRAZIL_TZ)
        result = ensure_timezone_aware(brazil_dt)
        
        assert result == brazil_dt
        assert result.tzinfo == BRAZIL_TZ
    
    def test_edge_case_epoch(self):
        """Test Unix epoch datetime"""
        epoch = datetime(1970, 1, 1, 0, 0, 0)
        result = ensure_timezone_aware(epoch)
        
        assert result.tzinfo == BRAZIL_TZ
        assert result.year == 1970


class TestEnsureTimezoneAwareUtcBase:
    """Test suite for ensure_timezone_aware_utc_base function"""
    
    def test_none_returns_none(self):
        """Test None returns None"""
        result = ensure_timezone_aware_utc_base(None)
        assert result is None
    
    def test_naive_gets_converted_to_brazil(self):
        """Test naive datetime (assumed UTC) is converted to Brazil"""
        naive_dt = datetime(2026, 2, 28, 18, 30, 0)  # 18:30 UTC
        result = ensure_timezone_aware_utc_base(naive_dt)
        
        assert result.tzinfo == BRAZIL_TZ
        # Should be converted from UTC to Brazil (typically -3 hours)
        assert result.hour == 15  # 18:30 UTC = 15:30 BRT
    
    def test_aware_preserved(self):
        """Test aware datetime preserved"""
        aware_dt = datetime(2026, 2, 28, 15, 30, 0, tzinfo=BRAZIL_TZ)
        result = ensure_timezone_aware_utc_base(aware_dt)
        
        assert result == aware_dt
        assert result.tzinfo == BRAZIL_TZ


class TestSafeDatetimeSubtract:
    """Test suite for safe_datetime_subtract function"""
    
    def test_both_aware_subtraction(self):
        """Test subtraction of two aware datetimes"""
        dt1 = datetime(2026, 2, 28, 15, 30, 0, tzinfo=BRAZIL_TZ)
        dt2 = datetime(2026, 2, 28, 15, 20, 0, tzinfo=BRAZIL_TZ)
        
        result = safe_datetime_subtract(dt1, dt2)
        assert result == timedelta(minutes=10)
    
    def test_both_naive_subtraction(self):
        """Test subtraction of two naive datetimes (normalized)"""
        dt1 = datetime(2026, 2, 28, 15, 30, 0)
        dt2 = datetime(2026, 2, 28, 15, 20, 0)
        
        result = safe_datetime_subtract(dt1, dt2)
        assert result == timedelta(minutes=10)
    
    def test_mixed_naive_aware_subtraction(self):
        """Test subtraction when mixing naive and aware (auto-normalized)"""
        dt1_naive = datetime(2026, 2, 28, 15, 30, 0)
        dt2_aware = datetime(2026, 2, 28, 15, 20, 0, tzinfo=BRAZIL_TZ)
        
        # Should normalize and subtract successfully
        result = safe_datetime_subtract(dt1_naive, dt2_aware)
        assert isinstance(result, timedelta)
        assert result == timedelta(minutes=10)
    
    def test_negative_timedelta(self):
        """Test negative timedelta (dt2 > dt1)"""
        dt1 = datetime(2026, 2, 28, 15, 20, 0, tzinfo=BRAZIL_TZ)
        dt2 = datetime(2026, 2, 28, 15, 30, 0, tzinfo=BRAZIL_TZ)
        
        result = safe_datetime_subtract(dt1, dt2)
        assert result == timedelta(minutes=-10)
    
    def test_different_timezones(self):
        """Test subtraction across different timezones"""
        dt1_utc = datetime(2026, 2, 28, 18, 30, 0, tzinfo=UTC_TZ)  # 18:30 UTC
        dt2_brazil = datetime(2026, 2, 28, 15, 30, 0, tzinfo=BRAZIL_TZ)  # 15:30 BRT (≈18:30 UTC)
        
        result = safe_datetime_subtract(dt1_utc, dt2_brazil)
        # Should be close to 0 (same moment in time)
        assert abs(result.total_seconds()) < 3600  # Within 1 hour


class TestSafeDatetimeCompare:
    """Test suite for safe_datetime_compare function"""
    
    def test_dt1_greater_than_dt2(self):
        """Test when dt1 > dt2 returns 1"""
        dt1 = datetime(2026, 2, 28, 16, 0, 0, tzinfo=BRAZIL_TZ)
        dt2 = datetime(2026, 2, 28, 15, 0, 0, tzinfo=BRAZIL_TZ)
        result = safe_datetime_compare(dt1, dt2)
        assert result == 1
    
    def test_dt1_less_than_dt2(self):
        """Test when dt1 < dt2 returns -1"""
        dt1 = datetime(2026, 2, 28, 15, 0, 0, tzinfo=BRAZIL_TZ)
        dt2 = datetime(2026, 2, 28, 16, 0, 0, tzinfo=BRAZIL_TZ)
        result = safe_datetime_compare(dt1, dt2)
        assert result == -1
    
    def test_dt1_equals_dt2(self):
        """Test when dt1 == dt2 returns 0"""
        dt1 = datetime(2026, 2, 28, 15, 0, 0, tzinfo=BRAZIL_TZ)
        dt2 = datetime(2026, 2, 28, 15, 0, 0, tzinfo=BRAZIL_TZ)
        result = safe_datetime_compare(dt1, dt2)
        assert result == 0
    
    def test_naive_vs_aware_comparison(self):
        """Test comparison normalizes naive vs aware"""
        dt1_naive = datetime(2026, 2, 28, 15, 30, 0)
        dt2_aware = datetime(2026, 2, 28, 15, 20, 0, tzinfo=BRAZIL_TZ)
        result = safe_datetime_compare(dt1_naive, dt2_aware)
        assert result == 1  # 15:30 > 15:20


class TestFormatDurationSafe:
    """Test suite for format_duration_safe function"""
    
    def test_hours_minutes_from_datetimes(self):
        """Test formatting with hours and minutes"""
        start = datetime(2026, 2, 28, 10, 0, 0, tzinfo=BRAZIL_TZ)
        end = datetime(2026, 2, 28, 12, 30, 0, tzinfo=BRAZIL_TZ)
        result = format_duration_safe(start, end)
        assert "2h" in result
        assert "30m" in result
    
    def test_only_minutes(self):
        """Test formatting with only minutes"""
        start = datetime(2026, 2, 28, 10, 0, 0, tzinfo=BRAZIL_TZ)
        end = datetime(2026, 2, 28, 10, 15, 0, tzinfo=BRAZIL_TZ)
        result = format_duration_safe(start, end)
        assert "15m" in result or "15" in result
    
    def test_only_seconds(self):
        """Test formatting with only seconds"""
        start = datetime(2026, 2, 28, 10, 0, 0, tzinfo=BRAZIL_TZ)
        end = datetime(2026, 2, 28, 10, 0, 45, tzinfo=BRAZIL_TZ)
        result = format_duration_safe(start, end)
        assert "45s" in result or "45" in result
    
    def test_default_end_is_now(self):
        """Test that end defaults to now_brazil()"""
        past = datetime(2026, 2, 28, 10, 0, 0, tzinfo=BRAZIL_TZ)
        result = format_duration_safe(past)
        # Should be a valid duration string
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_large_duration_days(self):
        """Test large duration with days"""
        start = datetime(2026, 2, 26, 10, 0, 0, tzinfo=BRAZIL_TZ)
        end = datetime(2026, 2, 28, 12, 30, 0, tzinfo=BRAZIL_TZ)
        result = format_duration_safe(start, end)
        # Should show large hours or days
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_negative_duration_returns_0s(self):
        """Test negative duration (end before start) returns 0s"""
        start = datetime(2026, 2, 28, 12, 0, 0, tzinfo=BRAZIL_TZ)
        end = datetime(2026, 2, 28, 10, 0, 0, tzinfo=BRAZIL_TZ)
        result = format_duration_safe(start, end)
        assert result == "0s"


class TestNormalizeModelDatetimes:
    """Test suite for normalize_model_datetimes function"""
    
    def test_object_normalizes_datetime_attributes(self):
        """Test normalizing object with datetime attributes"""
        class SimpleObject:
            def __init__(self):
                self.created_at = datetime(2026, 2, 28, 15, 30, 0)
                self.updated_at = datetime(2026, 2, 28, 16, 0, 0)
                self.name = "test"
        
        obj = SimpleObject()
        result = normalize_model_datetimes(obj)
        assert result.created_at.tzinfo == BRAZIL_TZ
        assert result.updated_at.tzinfo == BRAZIL_TZ
        assert result.name == "test"
    
    def test_object_with_specific_fields(self):
        """Test normalizing only specified fields"""
        class Job:
            def __init__(self):
                self.created_at = datetime(2026, 2, 28, 15, 30, 0)
                self.expires_at = datetime(2026, 3, 1, 0, 0, 0)
                self.name = "test"
        
        obj = Job()
        result = normalize_model_datetimes(obj, fields=["created_at"])
        assert result.created_at.tzinfo == BRAZIL_TZ
        assert result.expires_at.tzinfo is None  # Not in fields list
    
    def test_object_with_attributes(self):
        """Test normalizing object with datetime attributes"""
        class Job:
            def __init__(self):
                self.created_at = datetime(2026, 2, 28, 15, 30, 0)
                self.updated_at = datetime(2026, 2, 28, 16, 0, 0)
                self.name = "test"
        
        obj = Job()
        result = normalize_model_datetimes(obj)
        
        assert result.created_at.tzinfo == BRAZIL_TZ
        assert result.updated_at.tzinfo == BRAZIL_TZ
        assert result.name == "test"
    
    def test_none_values_preserved(self):
        """Test None values are preserved"""
        class Job:
            def __init__(self):
                self.created_at = None
                self.updated_at = datetime(2026, 2, 28, 16, 0, 0)
        
        obj = Job()
        result = normalize_model_datetimes(obj, fields=["created_at", "updated_at"])
        assert result.created_at is None
        assert result.updated_at.tzinfo == BRAZIL_TZ
    
    def test_already_aware_preserved(self):
        """Test already aware datetimes are preserved"""
        aware_dt = datetime(2026, 2, 28, 15, 30, 0, tzinfo=UTC_TZ)
        obj = {"created_at": aware_dt}
        
        result = normalize_model_datetimes(obj)
        assert result["created_at"] == aware_dt
        assert result["created_at"].tzinfo == UTC_TZ


class TestNowBrazil:
    """Test suite for now_brazil function"""
    
    def test_returns_aware_datetime(self):
        """Test now_brazil returns timezone-aware datetime"""
        result = now_brazil()
        assert result.tzinfo == BRAZIL_TZ
    
    def test_returns_current_time(self):
        """Test now_brazil returns current time (within 1 second)"""
        before = datetime.now(BRAZIL_TZ)
        result = now_brazil()
        after = datetime.now(BRAZIL_TZ)
        
        assert before <= result <= after
    
    def test_multiple_calls_increment(self):
        """Test multiple calls show time progression"""
        time1 = now_brazil()
        import time
        time.sleep(0.01)  # 10ms
        time2 = now_brazil()
        
        assert time2 > time1


class TestIntegration:
    """Integration tests combining multiple functions"""
    
    def test_full_job_workflow(self):
        """Test typical job creation and age calculation workflow"""
        # Simulate job creation with naive datetime (old code)
        job_created_naive = datetime(2026, 2, 28, 10, 0, 0)
        
        # Normalize when reading from Redis
        job_created_aware = ensure_timezone_aware(job_created_naive)
        
        # Calculate age with current time
        now = now_brazil()
        age = safe_datetime_subtract(now, job_created_aware)
        seconds = age.total_seconds()
        formatted = format_duration_safe(job_created_aware, now)
        
        # Assertions
        assert job_created_aware.tzinfo == BRAZIL_TZ
        assert seconds >= 0
        assert isinstance(formatted, str) and len(formatted) > 0
    
    def test_model_normalization_end_to_end(self):
        """Test complete model normalization"""
        # Simulate job object from Redis (mixed naive/aware)
        class Job:
            def __init__(self):
                self.id = "test123"
                self.created_at = datetime(2026, 2, 28, 10, 0, 0)  # naive
                self.updated_at = datetime(2026, 2, 28, 11, 0, 0, tzinfo=BRAZIL_TZ)  # aware
                self.completed_at = None
                self.status = "processing"
        
        job_data = Job()
        
        # Normalize
        normalized = normalize_model_datetimes(job_data, fields=["created_at", "updated_at", "completed_at"])
        
        # All datetime fields should be aware (or None)
        assert normalized.created_at.tzinfo == BRAZIL_TZ
        assert normalized.updated_at.tzinfo == BRAZIL_TZ
        assert normalized.completed_at is None
        
        # Calculate duration
        duration = safe_datetime_subtract(
            normalized.updated_at,
            normalized.created_at
        )
        assert duration == timedelta(hours=1)


# Performance tests
class TestPerformance:
    """Performance validation tests"""
    
    def test_ensure_timezone_aware_performance(self):
        """Test ensure_timezone_aware is O(1) and fast"""
        import time
        
        naive_dt = datetime(2026, 2, 28, 15, 30, 0)
        
        start = time.perf_counter()
        for _ in range(10000):
            ensure_timezone_aware(naive_dt)
        elapsed = time.perf_counter() - start
        
        # Should process 10K in < 100ms (< 10µs per call)
        assert elapsed < 0.1, f"Too slow: {elapsed*1000:.2f}ms for 10K ops"
    
    def test_safe_datetime_subtract_performance(self):
        """Test safe_datetime_subtract is fast"""
        import time
        
        dt1 = datetime(2026, 2, 28, 15, 30, 0, tzinfo=BRAZIL_TZ)
        dt2 = datetime(2026, 2, 28, 15, 20, 0, tzinfo=BRAZIL_TZ)
        
        start = time.perf_counter()
        for _ in range(10000):
            safe_datetime_subtract(dt1, dt2)
        elapsed = time.perf_counter() - start
        
        assert elapsed < 0.1, f"Too slow: {elapsed*1000:.2f}ms for 10K ops"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--cov=.helpers", "--cov-report=term-missing"])
