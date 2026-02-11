# TRSD Optuna Optimization Report

**Date**: 2026-02-07

**Best Accuracy**: 0.4348

**Trials**: 20

## Best Parameters

```python
TRSD_CONFIG = {
    "area_threshold": 0.0400,
    "area_weight": 0.2273,
    "aspect_ratio_max": 12.0000,
    "aspect_ratio_min": 3.0000,
    "aspect_ratio_weight": 0.2273,
    "cooldown_frames": 9,
    "max_frames": 150,
    "max_text_regions": 5,
    "max_words_per_region": 5,
    "min_confidence": 0.6500,
    "min_consecutive_detections": 6,
    "min_region_area": 800,
    "min_subtitle_score": 0.9000,
    "position_center_max": 0.8000,
    "position_center_min": 0.4000,
    "position_weight": 0.0909,
    "proximity_threshold": 20,
    "stability_window": 5,
    "target_fps": 3.0000,
    "temporal_weight": 0.4545,
}
```

## Dataset

- OK (no subtitles): 10 videos
- NOT_OK (has subtitles): 13 videos
