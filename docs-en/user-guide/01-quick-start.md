# ⚡ Quick Start

**From installation to first transcription in 5 minutes**

---

## 🎯 Objective

By the end of this guide you will have:
- ✅ YTCaption running locally
- ✅ First complete transcription
- ✅ Access to monitoring dashboards

**Estimated time**: 5 minutes

---

## 🚀 Step 1: Clone and Configure

```bash
# 1. Clone the repository
git clone https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API.git
cd YTCaption-Easy-Youtube-API

# 2. Copy the configuration file
cp .env.example .env

# 3. (Optional) Edit settings
nano .env
```

**Minimum configuration** (already in `.env.example`):
```bash
WHISPER_MODEL=base
ENABLE_TOR_PROXY=false  # Change to true if YouTube blocks
```

---

## 🐳 Step 2: Start with Docker

```bash
docker-compose up -d
```

**Wait** ~30 seconds for containers to start.

### Check if it's running

```bash
docker-compose ps
```

**Expected**:
```
NAME                        STATUS
whisper-transcription-api   Up (healthy)
whisper-prometheus          Up
whisper-grafana             Up
whisper-tor-proxy           Up
```

---

## 🧪 Step 3: Test the API

### Health Check

```bash
curl http://localhost:8000/health
```

**Expected**:
```json
{
  "status": "healthy",
  "whisper_model": "base",
  "timestamp": "2025-10-22T10:30:00"
}
```

---

## 🎬 Step 4: First Transcription

### Option 1: Native Subtitles (FAST - 1-2s)

```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "use_youtube_transcript": true
  }'
```

### Option 2: Whisper AI (ACCURATE - 30s-2min)

```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "use_youtube_transcript": false,
    "language": "en"
  }'
```

### Expected Response

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up",
  "duration": 213.0,
  "language": "en",
  "method": "whisper",
  "processing_time": 45.2,
  "transcription": {
    "text": "We're no strangers to love. You know the rules and so do I...",
    "segments": [
      {
        "start": 0.0,
        "end": 3.5,
        "text": "We're no strangers to love"
      },
      {
        "start": 3.5,
        "end": 6.8,
        "text": "You know the rules and so do I"
      }
    ]
  }
}
```

---

## 📊 Step 5: Access Dashboards

### Swagger UI (Interactive Documentation)
```
http://localhost:8000/docs
```

### Grafana (Monitoring)
```
http://localhost:3000
Login: admin / whisper2024
```

**Available dashboards**:
- YouTube Resilience v3.0 (download metrics)
- System Performance (API, Whisper, resources)

### Prometheus (Raw Metrics)
```
http://localhost:9090
```

---

## ❌ Common Issues

### Error: "Connection refused"

**Cause**: Containers didn't start

**Solution**:
```bash
docker-compose logs -f

# If necessary, rebuild:
docker-compose down
docker-compose build
docker-compose up -d
```

---

### Error: "HTTP 403 Forbidden" (YouTube)

**Cause**: YouTube detected automated requests

**Quick Solution**:
```bash
# 1. Edit .env
nano .env

# 2. Enable Tor
ENABLE_TOR_PROXY=true

# 3. Restart
docker-compose restart whisper-api

# 4. Wait for Tor (30s)
docker-compose logs tor-proxy | grep "Bootstrapped 100%"

# 5. Try again
```

📖 [Complete troubleshooting](./05-troubleshooting.md#http-403-forbidden)

---

### Error: "Out of Memory"

**Cause**: Whisper model too large for available RAM

**Solution**:
```bash
# .env - Use smaller model
WHISPER_MODEL=tiny  # Was base

docker-compose restart whisper-api
```

---

## 🎓 Next Steps

Now that you have YTCaption running:

1. **Configure for your needs**  
   → [Configuration Guide](./03-configuration.md)

2. **Understand all API endpoints**  
   → [API Usage](./04-api-usage.md)

3. **Prepare for production**  
   → [Deployment Guide](./06-deployment.md)

4. **Configure YouTube Resilience v3.0**  
   → [Configuration - YouTube Resilience](./03-configuration.md#youtube-resilience-v30)

---

## 🆘 Need Help?

- **Technical issues**: [Troubleshooting](./05-troubleshooting.md)
- **Configuration questions**: [Configuration](./03-configuration.md)
- **GitHub issue**: [Open issue](https://github.com/JohnHeberty/YTCaption-Easy-Youtube-API/issues)

---

## ✅ Success Checklist

- [ ] Docker Compose running (`docker-compose ps` shows 4 containers Up)
- [ ] Health check returns `"status": "healthy"`
- [ ] First transcription complete (Whisper or YouTube Transcript)
- [ ] Grafana accessible at http://localhost:3000
- [ ] Swagger UI accessible at http://localhost:8000/docs

**Everything working?** 🎉 Congratulations! You're ready to use YTCaption!

---

**[← Back to User Guide](./README.md)** | **[Next: Installation →](./02-installation.md)**
