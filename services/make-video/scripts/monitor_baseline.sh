#!/bin/bash
# Monitor baseline completion and show results

echo "🔍 Monitoring baseline measurement (PID 560703)..."
echo ""

# Wait for process to complete (max 5 minutes)
for i in {1..30}; do
    if ps aux | grep -q "560703.*measure_baseline" | grep -v grep; then
        echo "[$i/30] Still running... $(date +%H:%M:%S)"
        sleep 10
    else
        echo "✅ Process completed!"
        break
    fi
done

# Check if completed
if ps aux | grep -q "560703.*measure_baseline" | grep -v grep; then
    echo "⚠️ Process still running after 5 minutes"
    echo "Showing current progress:"
    tail -30 /root/YTCaption-Easy-Youtube-API/services/make-video/baseline_complete.log
    exit 1
fi

# Show results
echo ""
echo "=" | tr '=' '=' | head -c 70 && echo
echo "📊 BASELINE MEASUREMENT RESULTS" 
echo "=" | tr '=' '=' | head -c 70 && echo
echo ""

cd /root/YTCaption-Easy-Youtube-API/services/make-video

# Show metrics from log
if grep -q "BASELINE METRICS" baseline_complete.log; then
    grep -A 50 "BASELINE METRICS" baseline_complete.log | head -60
else
    echo "⚠️ Metrics not found in log. Showing last 50 lines:"
    tail -50 baseline_complete.log
fi

echo ""
echo "=" | tr '=' '=' | head -c 70 && echo
echo "📄 Results saved to: storage/validation/baseline_results.json"
echo "=" | tr '=' '=' | head -c 70 && echo
