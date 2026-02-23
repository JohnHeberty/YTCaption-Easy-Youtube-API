# 🚀 ACTION PLAN: Fix OCR Calibration

**Date**: 2026-02-12  
**Status**: ✅ Ready to Execute  
**ETA**: 30 minutes + 60-80h calibration

---

## 📋 Quick Summary

**Found**: TWO root causes
1. ⚡ **Thresholds too high** (40-80% → should be 15-50%)
2. ⏰ **AV1 codec issues** (11 videos unreadable)

**Impact**: Combined effect = 19.4% accuracy (unusable)

**Solution**: Fix both issues → Expected 75-80% accuracy

---

## 🎯 Step-by-Step Fix

### STEP 1: Lower Confidence Thresholds ⚡ **2 MINUTES**

**File**: `calibrate_trsd_optuna.py`  
**Line**: ~310-320

**Change from**:
```python
min_confidence: trial.suggest_float("min_confidence", 0.30, 0.90, step=0.05),
```

**Change to**:
```python
min_confidence: trial.suggest_float("min_confidence", 0.15, 0.50, step=0.05),
```

**Why**: Manual test shows 30% works, calibration tested 40-80% (too high)

**Expected impact**: Detect 18 H.264 videos → ~60% accuracy immediately

---

### STEP 2: Convert AV1 Videos ⏰ **15-30 MINUTES**

**Command**:
```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video

# Convert 11 AV1 videos to H.264
for f in storage/validation/sample_NOT_OK/*.mp4; do
    codec=$(ffprobe -v error -select_streams v:0 \
            -show_entries stream=codec_name \
            -of default=noprint_wrappers=1:nokey=1 "$f")
    
    if [ "$codec" == "av1" ]; then
        echo "Converting $(basename "$f")..."
        ffmpeg -i "$f" -c:v libx264 -crf 23 -c:a copy \
               -y "${f%.mp4}_h264.mp4" -loglevel error
        echo "✅ Done: $(basename "${f%.mp4}_h264.mp4")"
    fi
done
```

**Expected**: 11 new H.264 files in `sample_NOT_OK/`

**Expected Impact**: +11 readable videos → ~75-80% accuracy

---

###STEP 3: Update Calibration Paths (OPTIONAL)

If using converted files with _h264.mp4 suffix:

**File**: `calibrate_trsd_optuna.py`  
**Line**: ~500

**Add filter**:
```python
# Load datasets - prefer _h264.mp4 files
ok_videos_raw = list(self.ok_dir.glob("*.mp4"))
not_ok_videos_raw = list(self.not_ok_dir.glob("*.mp4"))

# Filter: use _h264 versions if available
def prefer_h264(videos):
    h264_map = {}
    for v in videos:
        base = str(v).replace("_h264.mp4", ".mp4")
        if "_h264" in str(v):
            h264_map[base] = v
    
    result = []
    for v in videos:
        base_name = str(v).replace("_h264.mp4", ".mp4")
        if base_name in h264_map and "_h264" not in str(v):
            result.append(h264_map[base_name])  # Use H.264 version
        elif base_name not in h264_map or "_h264" in str(v):
            result.append(v)
    
    return list(set(result))

ok_videos_raw = prefer_h264(ok_videos_raw)
not_ok_videos_raw = prefer_h264(not_ok_videos_raw)
```

**OR simpler**:Replace originals with converted files:
```bash
cd storage/validation/sample_NOT_OK
for f in *_h264.mp4; do
    orig="${f%_h264.mp4}.mp4"
    if [ -f "$orig" ]; then
        mv "$orig" "${orig}.bak"
        mv "$f" "$orig"
    fi
done
```

---

### STEP 4: Re-run Calibration 🚀 **60-80 HOURS**

```bash
cd /root/YTCaption-Easy-Youtube-API/services/make-video
make calibrate-start
```

**Monitor progress**:
```bash
make cal-watch  # Updates every 30s
```

**Check after 5 trials**:
```bash
make cal-status
```

**Success criteria**:
- ✅ TP > 0 (detecting SOME videos)
- ✅ Accuracy > 50%
- ✅ Results vary between trials  
- ✅ No AV1 errors in logs

**If fails after 5 trials**: STOP and debug further

---

## 📊 Expected Results

### Before Fix (Current)
```
Accuracy: 19.4%
TP: 0, FP: 0, TN: 7, FN: 29
Precision: undefined
Recall: 0%
F1: 0
```

### After Fix #1 (Lower Thresholds)
```
Accuracy: ~60-70%
TP: 13-16 (of 18 H.264), FP: 0-1, TN: 6-7, FN: 13-16
Precision: ~95%
Recall: ~50-60%
F1: ~65-70%
```

### After Fix #1 + #2 (Both Fixes)
```
Accuracy: ~75-80%
TP: 20-23, FP: 1-2, TN: 6-7, FN: 6-9
Precision: ~90-95%
Recall: ~70-80%
F1: ~78-85%
```

---

## ⏱️ Timeline

| Task | Duration | Can Start |
|------|----------|-----------|
| Fix #1: Lower thresholds | 2 min | NOW |
| Fix #2: Convert videos | 15-30 min | NOW (parallel) |
| Start calibration | 1 min | After #1 & #2 |
| First results | ~30 min | After start |
| Verify success | 5 min | After 5 trials |
| Complete calibration | 60-80 hours | If verified |

**Total time to first results**: ~45 minutes  
**Total time to completion**: 3-4 days

---

## 🚦 Decision Points

### After Step 1 (Lower Thresholds)
**Question**: Run calibration now or wait for AV1 conversion?

- **Option A**: Run NOW with 18 H.264 → Get ~60% accuracy quickly
- **Option B**: Wait for conversion → Get ~75-80% accuracy in one go

**Recommendation**: Option B (wait 30min, get better results)

### After 5 Trials
**Check**: Is TP > 0? Is accuracy > 50%?

- **YES**: Continue to 100 trials ✅
- **NO**: Stop and debug further ❌

### After 25 Trials
**Check**: Are results varying? Best accuracy improving?

- **YES**: Continue ✅
- **NO**: May have new issue, investigate ⚠️

---

## 🔧 Commands Quick Reference

```bash
# Navigate to service
cd /root/YTCaption-Easy-Youtube-API/services/make-video

# 1. Edit thresholds
nano calibrate_trsd_optuna.py  # Line ~310

# 2. Convert AV1 videos (inline command above)

# 3. Verify conversions
ls -lh storage/validation/sample_NOT_OK/*_h264.mp4 | wc -l  # Should be 11

# 4. Start calibration
make calibrate-start

# 5. Monitor
make cal-watch  # Or: make cal-status

# 6. Check logs
make cal-logs

# 7. Stop if needed
make cal-stop
```

---

## 📝 Related Documentation

- **[INVESTIGATION.md](INVESTIGATION.md)** - Full technical analysis
- **[INVESTIGATION_CONCLUSION.md](INVESTIGATION_CONCLUSION.md)** - Root cause summary
- **[EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md)** - Management overview
- **[OPTUNA_OPTIMIZATION.md](OPTUNA_OPTIMIZATION.md)** - Calibration guide

---

## ✅ Pre-Flight Checklist

Before running calibration:
- [ ] Thresholds lowered to 0.15-0.50
- [ ] AV1 videos converted (11 files)
- [ ] Conversions verified (ffprobe check)
- [ ] No other calibration running (make cal-status)
- [ ] Sufficient disk space (~5GB free)
- [ ] Can monitor for next 4 days

---

**Ready to execute**: YES ✅  
**Risk level**: LOW (changes are safe and reversible)  
**Confidence**: HIGH (root causes identified and verified)

**👉 TO START**: Run Step 1, then Step 2, then Step 4
