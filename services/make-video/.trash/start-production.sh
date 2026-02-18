#!/bin/bash

# Start Make-Video Service in Production Mode
# Usage: ./start-production.sh

set -e

echo "🚀 Starting Make-Video Service in Production Mode..."
echo ""

# Check environment file
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "   Copy .env.example to .env and configure it first."
    exit 1
fi

# Activate virtual environment
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
else
    echo "⚠️  Warning: venv not found. Using system Python."
fi

# Check dependencies
echo "🔍 Checking dependencies..."
python3 -c "import fastapi, celery, redis" 2>/dev/null || {
    echo "❌ Missing dependencies. Installing..."
    pip install -r requirements.txt -q
}

# Clean old processes
echo "🧹 Cleaning old processes..."
pkill -f "uvicorn.*make-video" 2>/dev/null || true
pkill -f "celery.*make_video_queue" 2>/dev/null || true
sleep 2

# Start API server
echo "🌐 Starting API server..."
nohup python run.py > /tmp/make-video-api.log 2>&1 &
API_PID=$!
echo "   API started (PID: $API_PID)"

sleep 3

# Start Celery worker
echo "⚙️  Starting Celery worker..."
nohup celery -A app.celery_config worker \
    --loglevel=info \
    --concurrency=1 \
    --queues=make_video_queue \
    --pool=solo \
    > /tmp/make-video-worker.log 2>&1 &
WORKER_PID=$!
echo "   Worker started (PID: $WORKER_PID)"

sleep 3

# Verify services
echo ""
echo "✅ Services started successfully!"
echo ""
echo "📊 Status:"
curl -s http://localhost:8004/health | python3 -m json.tool | grep -E "(status|service|redis)" | head -5 || echo "   ⚠️  API not responding yet"
echo ""
echo "📝 Logs:"
echo "   API:    tail -f /tmp/make-video-api.log"
echo "   Worker: tail -f /tmp/make-video-worker.log"
echo ""
echo "🛑 To stop:"
echo "   kill $API_PID $WORKER_PID"
echo ""
