#!/bin/bash
# Monitor build progress without interrupting

while true; do
  clear
  echo "=== BUILD PROGRESS MONITOR ==="
  echo "Time: $(date)"
  echo ""
  
  # Check if build.log exists and show last 30 lines
  if [ -f build.log ]; then
    echo "--- Last 30 lines of build.log ---"
    tail -30 build.log
  else
    echo "build.log not found yet..."
  fi
  
  echo ""
  echo "--- Docker processes ---"
  ps aux | grep -E 'docker|buildkit' | grep -v grep | head -5
  
  echo ""
  echo "Press Ctrl+C to stop monitoring (build will continue)"
  sleep 10
done
