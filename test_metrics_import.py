#!/usr/bin/env python3
"""
Test script to verify Prometheus metrics don't have duplicates.
Run this before deploy to catch registry conflicts.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

def test_metrics_import():
    """Test that all metrics can be imported without registry conflicts."""
    
    print("🧪 Testing Prometheus metrics import...")
    print("=" * 60)
    
    try:
        # Import YouTube metrics first
        print("\n1️⃣ Importing YouTube metrics...")
        from src.infrastructure.youtube.metrics import (
            youtube_downloads_total,
            youtube_download_duration,
            youtube_download_size_bytes
        )
        print("   ✅ YouTube metrics imported successfully")
        
        # Import monitoring metrics
        print("\n2️⃣ Importing Monitoring metrics...")
        from src.infrastructure.monitoring.metrics import (
            MetricsCollector,
            transcription_requests_counter,
            transcription_duration_histogram
        )
        print("   ✅ Monitoring metrics imported successfully")
        
        # Import main app (full integration test)
        print("\n3️⃣ Testing routes imports...")
        from src.presentation.api.routes import transcription
        print("   ✅ Transcription route imported successfully")
        
        from src.presentation.api.routes import video_info
        print("   ✅ Video info route imported successfully")
        
        from src.presentation.api.routes import system
        print("   ✅ System route imported successfully")
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED - No metric duplicates detected!")
        print("=" * 60)
        
        return True
        
    except ValueError as e:
        if "Duplicated timeseries" in str(e):
            print("\n" + "=" * 60)
            print("❌ DUPLICATE METRICS DETECTED!")
            print("=" * 60)
            print(f"\nError: {e}")
            print("\nThis will cause CrashLoopBackOff in production!")
            return False
        else:
            raise
    
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ UNEXPECTED ERROR: {type(e).__name__}")
        print("=" * 60)
        print(f"\n{e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_metrics_import()
    sys.exit(0 if success else 1)
