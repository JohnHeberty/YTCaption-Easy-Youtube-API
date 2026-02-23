# SPRINT-01 Testing Guide: Auto-Recovery System

## Prerequisites

1. **Build and restart containers**:
   ```bash
   cd /root/YTCaption-Easy-Youtube-API/services/make-video
   docker compose down
   docker compose build
   docker compose up -d
   ```

2. **Verify Celery Beat is running**:
   ```bash
   docker logs ytcaption-make-video-celery-beat 2>&1 | grep "recover-orphaned-jobs"
   ```
   
   **Expected output**:
   ```
   [INFO] beat: Starting...
   [INFO] Scheduler: Sending due task recover-orphaned-jobs
   ```

## Test Scenarios

### Test 1: Simulate Orphaned Job (Worker Crash)

**Objective**: Verify that crashed jobs are automatically recovered

**Steps**:

1. **Start a video job**:
   ```bash
   curl -X POST http://localhost:8004/jobs \
     -H "Content-Type: application/json" \
     -d '{
       "audio_file": "test.mp3",
       "query": "gatos fofos",
       "max_shorts": 5,
       "subtitle_language": "pt"
     }'
   ```
   
   **Note the `job_id` in response**

2. **Monitor job progress**:
   ```bash
   watch -n 1 'curl -s http://localhost:8004/jobs/{JOB_ID} | jq ".status, .progress"'
   ```

3. **Kill worker when status = "downloading_shorts"**:
   ```bash
   docker exec ytcaption-make-video-celery pkill -9 -f "celery worker"
   ```
   
   ✅ Job is now orphaned (status stuck, no updates)

4. **Restart worker**:
   ```bash
   docker restart ytcaption-make-video-celery
   ```

5. **Wait 2-6 minutes for auto-recovery**:
   ```bash
   docker logs -f ytcaption-make-video-celery-beat | grep AUTO-RECOVERY
   ```
   
   **Expected logs**:
   ```
   🔍 [AUTO-RECOVERY] Starting orphaned jobs detection...
   ⚠️ [AUTO-RECOVERY] Found 1 orphaned jobs (older than 5min)
   🔧 [AUTO-RECOVERY] Attempting recovery of job 2AK8ZcFxXUmC6FmWLqgL7z (status=downloading_shorts, age=6.2min)
   📍 [RECOVERY] Job 2AK8ZcFxXUmC6FmWLqgL7z checkpoint: completed stages: ['analyzing_audio_completed', 'fetching_shorts_completed']
   🎯 [RECOVERY] Job 2AK8ZcFxXUmC6FmWLqgL7z will resume from stage: selecting_shorts
   ✅ [RECOVERY] Job 2AK8ZcFxXUmC6FmWLqgL7z re-submitted successfully
   📊 [AUTO-RECOVERY] Complete: 1 recovered, 0 failed out of 1 orphaned
   ```

6. **Verify job completes**:
   ```bash
   curl -s http://localhost:8004/jobs/{JOB_ID} | jq ".status, .result"
   ```
   
   ✅ Status should be "completed", result should have video file

---

### Test 2: Manual Orphan Detection (Verify Endpoint)

**Objective**: Confirm manual endpoint still works

**Steps**:

1. **Check for orphans manually**:
   ```bash
   curl http://localhost:8004/jobs/orphaned?max_age_minutes=5
   ```
   
   **Expected**: List of orphaned jobs (if any)

2. **Check health of orphan system**:
   ```bash
   curl http://localhost:8004/health
   ```
   
   ✅ Should return healthy status

---

### Test 3: Checkpoint Persistence (Worker Restart)

**Objective**: Verify checkpoints survive worker restarts

**Steps**:

1. **Start a job**:
   ```bash
   curl -X POST http://localhost:8004/jobs \
     -H "Content-Type: application/json" \
     -d '{"audio_file": "test.mp3", "query": "test", "max_shorts": 3}'
   ```

2. **Wait for stage 3 (downloading_shorts)**:
   ```bash
   watch -n 1 'curl -s http://localhost:8004/jobs/{JOB_ID} | jq ".status"'
   ```

3. **Check checkpoint in Redis**:
   ```bash
   docker exec ytcaption-redis redis-cli GET make_video:checkpoint:{JOB_ID}
   ```
   
   **Expected**:
   ```json
   {"completed_stages": ["analyzing_audio_completed", "fetching_shorts_completed"], "last_updated": "2026-02-07T..."}
   ```

4. **Restart worker**:
   ```bash
   docker restart ytcaption-make-video-celery
   ```

5. **Checkpoint should still exist**:
   ```bash
   docker exec ytcaption-redis redis-cli GET make_video:checkpoint:{JOB_ID}
   ```
   
   ✅ Checkpoint persists (TTL = 48 hours)

---

### Test 4: No False Positives (Active Jobs)

**Objective**: Ensure active jobs are NOT marked as orphaned

**Steps**:

1. **Start a long-running job**:
   ```bash
   curl -X POST http://localhost:8004/jobs \
     -H "Content-Type: application/json" \
     -d '{"audio_file": "long_audio.mp3", "query": "test", "max_shorts": 20}'
   ```

2. **Monitor auto-recovery logs during processing**:
   ```bash
   docker logs -f ytcaption-make-video-celery-beat | grep AUTO-RECOVERY
   ```

3. **Verify job is NOT detected as orphan**:
   - Recovery should log: `✅ [AUTO-RECOVERY] No orphaned jobs found`
   - Job `updated_at` timestamp should update regularly

4. **Check Redis checkpoint updates**:
   ```bash
   watch -n 5 'docker exec ytcaption-redis redis-cli GET make_video:checkpoint:{JOB_ID}'
   ```
   
   ✅ `last_updated` should change as stages complete

---

## Expected Metrics

After running all tests, check recovery statistics:

```bash
# Count orphaned jobs detected in last hour
docker logs ytcaption-make-video-celery-beat --since 1h | grep "Found .* orphaned" | wc -l

# Count successful recoveries
docker logs ytcaption-make-video-celery-beat --since 1h | grep "recovered successfully" | wc -l

# Count failed recoveries
docker logs ytcaption-make-video-celery-beat --since 1h | grep "recovery failed" | wc -l
```

**Success Criteria**:
- ✅ All orphaned jobs are detected within 2-5 minutes
- ✅ Recovery success rate > 90%
- ✅ No false positives (active jobs NOT marked as orphaned)
- ✅ Checkpoints persist across worker restarts
- ✅ Jobs resume from correct stage (not restart)

---

## Troubleshooting

### Issue: Auto-recovery not running

**Check**:
```bash
docker logs ytcaption-make-video-celery-beat | grep "beat: Starting"
```

**Fix**: Restart Beat
```bash
docker restart ytcaption-make-video-celery-beat
```

---

### Issue: Jobs detected but not recovered

**Check Redis connection**:
```bash
docker exec ytcaption-make-video-celery celery -A app.celery_config inspect ping
```

**Check worker status**:
```bash
docker exec ytcaption-make-video-celery celery -A app.celery_config inspect active
```

**Fix**: Restart worker
```bash
docker restart ytcaption-make-video-celery
```

---

### Issue: Checkpoint not found

**Verify Redis key**:
```bash
docker exec ytcaption-redis redis-cli KEYS "make_video:checkpoint:*"
```

**Check TTL**:
```bash
docker exec ytcaption-redis redis-cli TTL make_video:checkpoint:{JOB_ID}
```

**Fix**: Checkpoints expire after 48 hours, recreate job

---

## Validation Checklist

- [ ] Containers built and running
- [ ] Celery Beat logs show periodic recovery attempts (every 2 min)
- [ ] Test 1: Orphaned job recovered successfully
- [أن Test 2: Manual endpoint returns orphans
- [ ] Test 3: Checkpoints persist after worker restart
- [ ] Test 4: No false positives detected
- [ ] Metrics show >90% recovery success rate
- [ ] Job `2AK8ZcFxXUmC6FmWLqgL7z` (original issue) resolved

---

**Last Updated**: 2026-02-07  
**Sprint**: SPRINT-01 (Auto-Recovery System)  
**Status**: ✅ Implementation Complete
