# TRSD Calibration Report

**Date:** 2026-02-07 00:08:18

## 📊 Overall Metrics

- **Total Videos:** 13
- **Accuracy:** 38.46%
- **Precision:** 33.33% (when blocking, correct rate)
- **Recall:** 100.00% (catch rate for videos with subtitles)
- **F1-Score:** 50.00%
- **Avg Processing Time:** 37.36s

## 🎯 Confusion Matrix

```
                    Predicted
                APPROVE    BLOCK
Actual APPROVE      1         8     (OK folder)
       BLOCK        0         4     (NOT_OK folder)
```

## 📋 Detailed Results

### ❌ False Positives (incorrectly blocked)

- **5KgYaiBd6oY** (from OK folder)

- **IyZ-sdLQATM** (from OK folder)

- **XGrMrVFuc-E** (from OK folder)

- **fRf_Uh39hVQ** (from OK folder)

- **bH1hczbzm9U** (from OK folder)

- **5Bc-aOe4pC4** (from OK folder)

- **KWC32RL-wgc** (from OK folder)

- **kVTr1c9IL8w** (from OK folder)

## ⚙️ Current Configuration

```env
TRSD_ENABLED=True
TRSD_IGNORE_STATIC_TEXT=True
TRSD_STATIC_MIN_PRESENCE=0.85
TRSD_STATIC_MAX_CHANGE=0.1
TRSD_SUBTITLE_MIN_CHANGE_RATE=0.25
TRSD_SCREENCAST_MIN_DETECTIONS=10
TRSD_TRACK_IOU_THRESHOLD=0.3
```

## 💡 Recommendations

### ⚠️ Low Precision (false blocks)
Consider:
- Increase `TRSD_SUBTITLE_MIN_CHANGE_RATE` to be more confident
- Decrease `TRSD_STATIC_MIN_PRESENCE` to classify more as static
- Review false positives in debug artifacts

## 🚀 Next Steps

1. Review debug artifacts in `storage/debug_artifacts/`
2. Analyze false positives/negatives
3. Adjust thresholds based on recommendations
4. Re-run calibration: `python calibrate_trsd.py`
5. Deploy to staging when metrics are acceptable
