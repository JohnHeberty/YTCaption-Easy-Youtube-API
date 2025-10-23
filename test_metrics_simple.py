#!/usr/bin/env python3
"""
Simple test to verify Prometheus metrics don't have duplicates.
This test only checks the metrics modules without external dependencies.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

print("🧪 Testing Prometheus Metrics Registry...")
print("=" * 70)

try:
    print("\n📊 Step 1: Importing YouTube metrics...")
    from src.infrastructure.youtube.metrics import (
        youtube_downloads_total,
        youtube_download_duration,
        youtube_download_size_bytes,
        youtube_strategy_success,
        youtube_circuit_breaker_state
    )
    print("   ✅ YouTube metrics imported (5 metrics)")
    
    print("\n📊 Step 2: Importing Monitoring metrics...")
    from src.infrastructure.monitoring.metrics import (
        MetricsCollector,
        transcription_requests_counter,
        transcription_duration_histogram,
        cache_hit_rate_gauge,
        worker_pool_queue_gauge,
        circuit_breaker_state_gauge
    )
    print("   ✅ Monitoring metrics imported (6 metrics)")
    
    print("\n📊 Step 3: Verifying Prometheus Registry...")
    from prometheus_client import REGISTRY
    
    # Get all registered metrics
    metrics_names = set()
    for collector in REGISTRY._collector_to_names.values():
        metrics_names.update(collector)
    
    print(f"   ✅ Total metrics in registry: {len(metrics_names)}")
    
    # Check for the previously duplicated metric
    youtube_metrics = [m for m in metrics_names if 'youtube_download' in m]
    print(f"\n📋 YouTube download metrics found: {len(youtube_metrics)}")
    for metric in sorted(youtube_metrics):
        print(f"   - {metric}")
    
    print("\n" + "=" * 70)
    print("✅ SUCCESS! No duplicate metrics detected!")
    print("=" * 70)
    print("\n🚀 Container should start successfully now!")
    print("   Ready to deploy to Proxmox.\n")
    
    sys.exit(0)
    
except ValueError as e:
    if "Duplicated timeseries" in str(e):
        print("\n" + "=" * 70)
        print("❌ FAILURE! Duplicate metrics detected:")
        print("=" * 70)
        print(f"\n{e}\n")
        print("⚠️  This will cause CrashLoopBackOff in production!")
        print("   Do NOT deploy until fixed.\n")
        sys.exit(1)
    else:
        raise

except Exception as e:
    print("\n" + "=" * 70)
    print(f"❌ ERROR: {type(e).__name__}")
    print("=" * 70)
    print(f"\n{e}\n")
    import traceback
    traceback.print_exc()
    sys.exit(1)
