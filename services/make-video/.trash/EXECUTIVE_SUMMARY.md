# 📋 Executive Summary: OCR Calibration Crisis

**Date**: 2026-02-12  
**Severity**: 🔴 CRITICAL  
**Status**: Under investigation

---

## 🚨 The Problem

### Symptoms
1. **Accuracy: 19.4%** (vs expected 60% from old Tesseract system)
2. **Zero true positives**: System detected NONE of 29 videos with subtitles
3. **Calibration stopped at 25/100 trials** (reason unknown)
4. **All trials identical**: Every trial produced same dismal results

### Impact
- Current OCR detection is **unusable** for production
- System classifies ALL videos with subtitles as "no subtitles"
- 80% failure rate (29/36 videos misclassified)

---

## 🔍 What We Found

### Discovery 1: System Behavior
```
Dataset: 7 OK (no subs) + 29 NOT_OK (has subs) = 36 videos

Results (ALL 25 trials):
- True Negatives: 7   ✅ (correctly identified no subs)
- False Negatives: 29 ❌ (MISSED all videos with subs)
- True Positives: 0   ❌ (detected nothing)
- False Positives: 0  ✅ (no false alarms)

Accuracy = 7/36 = 19.4%
```

### Discovery 2: Old Code Was Used
- Calibration ran with OLD version (1 parameter: min_confidence only)
- NEW version (6 parameters) was written AFTER calibration completed
- Results are NOT from improved system

### Discovery 3: Threshold Hypothesis
**Most likely root cause**: Confidence thresholds too high

- Tested range: min_confidence 0.40-0.80 (40%-80%)
- PaddleOCR may return lower confidence scores than expected
- Need to test much lower: 0.15-0.50 (15%-50%)

---

## 🎯 Investigation in Progress

### Manual Test Running
**Objective**: Test 5 videos with multiple thresholds (30, 40, 50, 60, 70, 80)

**Will answer**:
- Can PaddleOCR detect subtitles at ANY threshold?
- What confidence scores do real subtitles get?
- Which threshold range actually works?

**Status**: ⏳ Downloading models, then will process videos

**ETA**: 5-10 minutes

---

## 💡 Proposed Solutions

### Short-term (Immediate)
1. **Lower confidence thresholds**
   - Current: 30%-90%
   - Proposed: 15%-50%

2. **Lower frame threshold**
   - Current: 20%-50% frames must have text
   - Proposed: 10%-25%

3. **More frame samples**
   - Current: 8-15 frames
   - Proposed: 15-25 frames

### Medium-term (After Manual Test)
1. Analyze manual test results
2. Adjust parameter ranges based on findings
3. Re-run calibration with:
   - ✅ New 6-parameter code
   - ✅ Adjusted ranges
   - ✅ Monitor first 5 trials for TP > 0

### Long-term (Architecture)
1. Compare with old Tesseract system (find what made it 60%)
2. Consider hybrid approach (PaddleOCR + Tesseract)
3. Implement ensemble detection

---

## 📊 Key Metrics to Watch

### Success Criteria for Next Calibration
- ✅ **True Positives > 0** (at least detect SOME videos)
- ✅ **Accuracy > 50%** (better than random)
- ✅ **Trials show variation** (not all identical)
- ✅ **Complete 100 trials** (no crashes)

### Red Flags
- ❌ TP = 0 after 5 trials → STOP and debug
- ❌ All trials identical → Parameter bug
- ❌ Crashes/OOM → Resource issue

---

## 🔗 Related Files

- **Investigation**: [INVESTIGATION.md](INVESTIGATION.md) (detailed analysis)
- **Optimization guide**: [OPTUNA_OPTIMIZATION.md](OPTUNA_OPTIMIZATION.md)
- **Calibration code**: [calibrate_trsd_optuna.py](calibrate_trsd_optuna.py)
- **Manual test**: [test_manual_detection.py](test_manual_detection.py)
- **Results**: `storage/calibration/optuna_incremental_results.json`

---

## 🎬 Next Actions

1. ⏳ **Wait for manual test** to complete (~5 min)
2. 📊 **Analyze results** → Identify working thresholds
3. ⚙️ **Adjust parameters** in calibration code
4. 🚀 **Re-run calibration** with new settings
5. 👁️ **Monitor first 5 trials** → Verify TP > 0

---

**Priority**: 🔴 **URGENT** - Production system is broken
**Owner**: Investigation team
**Next update**: After manual test completes
