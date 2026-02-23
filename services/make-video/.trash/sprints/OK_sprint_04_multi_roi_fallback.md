# Sprint 04: Multi-ROI Fallback

**Status**: 🚧 IN PROGRESS  
**Goal**: Handle edge cases where subtitles appear in non-standard positions  
**Expected Coverage**: 10-15% edge cases (top/side subtitles)

---

## 🎯 OBJETIVOS

### Problem Statement
Current detector focuses on **bottom 25% ROI only**, which works for 85-90% of videos but misses:
- **Top subtitles**: Foreign films, dual-language videos, burned-in translations
- **Side captions**: YouTube Shorts, TikTok vertical videos, social media
- **Center text**: Embedded captions, hardcoded text overlays

### Goal
Implement **priority-based Multi-ROI fallback** system:
1. **Primary ROI**: Bottom 25% (current default, fastest)
2. **Fallback 1**: Top 25% (if bottom finds no text)
3. **Fallback 2**: Left/Right 20% (if bottom+top find nothing)
4. **Fallback 3**: Center 30%
5. **Fallback 4**: Full frame 100% (last resort for atypical layouts)

### Expected Outcomes
- ✅ Handle 10-15% additional edge cases
- ✅ Maintain 100% accuracy on standard bottom subtitles
- ✅ Performance: ≤8s per video (max 4 ROIs × 2s each)
- ✅ 6-8 pytest tests covering all ROI scenarios

---

## 📊 ROI DEFINITIONS

### ROI Layout (Percentage-based):
```
┌────────────────────────────────────┐
│                                    │
│  ╔══════════ TOP 25% ═══════════╗  │ ← Fallback 1
│  ║                              ║  │
├──╫──────────────────────────────╫──┤
│  ║                              ║  │
│ ┃║     ┌─────────────┐          ║ ┃ │
│ ┃║     │ CENTER 30%  │          ║ ┃ │ ← Fallback 3 (center)
│ ┃║     └─────────────┘          ║ ┃ │
│ ┃║                              ║ ┃ │ ← Fallback 2 (sides L/R 20%)
├─┃╫──────────────────────────────╫─┃─┤
│  ║                              ║  │
│  ╚═════════ BOTTOM 25% ════════╝  │ ← PRIMARY (current default)
│                                    │
└────────────────────────────────────┘
```

### ROI Coordinates (percentage of frame):
```python
ROI_CONFIGS = {
    'bottom': {
        'y_start': 0.75,  # Start at 75% height
        'y_end': 1.0,     # End at 100% height
        'x_start': 0.0,   # Full width
        'x_end': 1.0,
        'priority': 1     # Highest priority (check first)
    },
    'top': {
        'y_start': 0.0,
        'y_end': 0.25,
        'x_start': 0.0,
        'x_end': 1.0,
        'priority': 2
    },
    'left': {
        'y_start': 0.0,
        'y_end': 1.0,
        'x_start': 0.0,
        'x_end': 0.2,    # Left 20%
        'priority': 3
    },
    'right': {
        'y_start': 0.0,
        'y_end': 1.0,
        'x_start': 0.8,  # Right 20%
        'x_end': 1.0,
        'priority': 3
    },
    'center': {
        'y_start': 0.35,
        'y_end': 0.65,
        'x_start': 0.35,
        'x_end': 0.65,   # Center 30%×30%
        'priority': 4
    },
    'full': {
        'y_start': 0.0,
        'y_end': 1.0,
        'x_start': 0.0,
        'x_end': 1.0,    # Full frame 100%
        'priority': 5    # Lowest priority (last resort)
    }
}
```

---

## 🏗️ ARCHITECTURE

### Current Flow (Sprint 01-03):
```
Video → Extract frames (6 temporal samples) → Crop bottom 25% ROI → PaddleOCR → Result
```

### New Flow (Sprint 04):
```
Video → Extract frames (6 temporal samples) → Multi-ROI Detection:
                                                ├─ Primary: Bottom ROI → PaddleOCR
                                                │  └─ Has text? → DONE (fast path)
                                                │
                                                ├─ Fallback 1: Top ROI → PaddleOCR
                                                │  └─ Has text? → DONE
                                                │
                                                ├─ Fallback 2: Left/Right ROIs → PaddleOCR
                                                │  └─ Has text? → DONE
                                                │
                                                ├─ Fallback 3: Center ROI → PaddleOCR
                                                │  └─ Has text? → DONE
                                                │
                                                └─ Fallback 4: Full Frame → PaddleOCR
                                                   └─ Return result (text or no text)
```

### Priority-based Early Exit:
```python
def detect_with_multi_roi(frames):
    roi_priority = ['bottom', 'top', 'left', 'right', 'center', 'full']
    
    for roi_name in roi_priority:
        cropped_frames = crop_roi(frames, ROI_CONFIGS[roi_name])
        result = detect_in_roi(cropped_frames)
        
        if result.has_text:
            return result  # Early exit (found text)
    
    return no_text_result  # All ROIs scanned, no text found
```

**Key optimization**: Only scan fallback ROIs if primary finds nothing (≤1 ROI in 90% of cases)

---

## 📂 IMPLEMENTATION PLAN

### Step 1: Generate Edge Case Dataset (P0)
**Script**: `scripts/generate_edge_case_dataset.py`

**Dataset Structure**:
```
storage/validation/edge_cases/
├── top_subtitles/        (4 videos: 2 WITH + 2 WITHOUT)
│   ├── top_with_001.mp4  (subtitles at top 25%)
│   ├── top_with_002.mp4
│   ├── top_without_001.mp4
│   └── top_without_002.mp4
│
├── side_captions/        (4 videos: 2 WITH + 2 WITHOUT)
│   ├── side_left_with_001.mp4  (captions on left 20%)
│   ├── side_right_with_001.mp4 (captions on right 20%)
│   ├── side_without_001.mp4
│   └── side_without_002.mp4
│
├── center_text/          (4 videos: 2 WITH + 2 WITHOUT)
│   ├── center_with_001.mp4  (text in center 30%)
│   ├── center_with_002.mp4
│   ├── center_without_001.mp4
│   └── center_without_002.mp4
│
├── multi_position/       (4 videos: mixed positions)
│   ├── top_and_bottom_001.mp4
│   ├── side_and_bottom_001.mp4
│   ├── all_positions_001.mp4
│   └── no_text_001.mp4
│
└── ground_truth.json     (labels for all videos)
```

**Total**: 16 videos (12 WITH + 4 WITHOUT various positions)

### Step 2: Modify SubtitleDetectorV2 (P0)
**File**: `app/video_processing/subtitle_detector_v2.py`

**Changes**:
```python
class SubtitleDetectorV2:
    def __init__(self, ..., roi_mode='auto'):
        # roi_mode: 'bottom' (default), 'multi' (fallback enabled), 'all' (scan all)
        self.roi_mode = roi_mode
        self.roi_configs = ROI_CONFIGS
    
    def _detect_in_roi(self, frames, roi_config):
        """Detect text in specific ROI"""
        cropped_frames = self._crop_frames_to_roi(frames, roi_config)
        # Use existing detection pipeline
        return self._detect_in_frames(cropped_frames)
    
    def _crop_frames_to_roi(self, frames, roi_config):
        """Crop frames to ROI coordinates"""
        cropped = []
        for frame in frames:
            h, w = frame.shape[:2]
            y1 = int(h * roi_config['y_start'])
            y2 = int(h * roi_config['y_end'])
            x1 = int(w * roi_config['x_start'])
            x2 = int(w * roi_config['x_end'])
            cropped.append(frame[y1:y2, x1:x2])
        return cropped
    
    def detect_in_video_with_multi_roi(self, video_path):
        """Main detection with multi-ROI fallback"""
        frames = self._extract_temporal_frames(video_path)
        
        if self.roi_mode == 'bottom':
            # Legacy mode (Sprint 01-03)
            return self._detect_in_roi(frames, self.roi_configs['bottom'])
        
        elif self.roi_mode == 'multi':
            # Priority-based fallback
            for roi_name in ['bottom', 'top', 'left', 'right', 'center']:
                result = self._detect_in_roi(frames, self.roi_configs[roi_name])
                if result.has_text:
                    result.metadata['roi_used'] = roi_name
                    return result
            return no_text_result
        
        elif self.roi_mode == 'all':
            # Scan all ROIs, combine results (for debugging)
            all_results = {}
            for roi_name, roi_config in self.roi_configs.items():
                all_results[roi_name] = self._detect_in_roi(frames, roi_config)
            return self._combine_roi_results(all_results)
```

### Step 3: Create Pytest Suite (P0)
**File**: `tests/test_sprint04_multi_roi.py`

**Tests** (6-8 tests):
1. `test_top_subtitle_detection` - Detect top 25% subtitles
2. `test_side_left_caption_detection` - Detect left 20% captions
3. `test_side_right_caption_detection` - Detect right 20% captions
4. `test_center_text_detection` - Detect center 30% text
5. `test_roi_priority_fallback` - Verify priority order (bottom → top → sides → center)
6. `test_bottom_roi_maintained` - Ensure bottom ROI still works (regression)
7. `test_multi_roi_performance` - Performance ≤8s per video
8. `test_all_edge_cases_summary` - Overall metrics on 16 videos

**Expected Results**:
- All 8 tests PASS
- Combined: 37 tests (29 existing + 8 new)
- Accuracy: 95-100% on edge cases
- Performance: ≤8s per video

---

## 📊 SUCCESS CRITERIA

### Functional Requirements:
- ✅ Detect top 25% subtitles (100% accuracy on top dataset)
- ✅ Detect side 20% captions (100% accuracy on side dataset)
- ✅ Detect center 30% text (100% accuracy on center dataset)
- ✅ Priority-based fallback working (bottom → top → sides → center)
- ✅ Maintain 100% accuracy on existing datasets (regression test)

### Performance Requirements:
- ✅ Fast path (bottom ROI only): ≤2-4s per video (90% of cases)
- ✅ 2 ROI scan (bottom + top): ≤4-6s per video
- ✅ Full scan (all 5 ROIs): ≤8-10s per video (rare, <5% of cases)

### Test Coverage:
- ✅ 8 new pytest tests (all PASS)
- ✅ Combined: 37 tests (29 existing + 8 new)
- ✅ Coverage: bottom, top, left, right, center, priority, performance, regression

---

## 🎓 RISK ASSESSMENT

### Potential Issues:
1. **Performance degradation**: Scanning multiple ROIs could be slow
   - **Mitigation**: Early exit on first text found (priority-based)
   - **Mitigation**: Only enable multi-ROI mode when needed

2. **False positives increase**: More ROIs = more chances to find non-subtitle text
   - **Mitigation**: Feature-based filtering (use Sprint 03 features)
   - **Mitigation**: ROI-specific thresholds (center ROI = higher confidence threshold)

3. **Regression on standard cases**: Multi-ROI logic might break existing detector
   - **Mitigation**: Regression tests on Sprint 00-03 datasets
   - **Mitigation**: roi_mode='bottom' keeps legacy behavior

### Edge Cases:
- **Multiple subtitle tracks**: Top (English) + Bottom (Portuguese)
  - **Solution**: Return first found (priority order)
  - **Future**: Combine results in metadata

- **Vertical videos** (9:16 aspect ratio): Left/right ROIs might overlap with content
  - **Solution**: Aspect ratio detection, adjust ROI percentages

- **Very short videos** (<2s): Not enough frames for temporal sampling
  - **Solution**: Fallback to single-frame detection

---

## 🚀 NEXT STEPS (After Sprint 04)

### Sprint 05: Temporal Tracker (OPTIONAL)
- Track text regions between frames (IOU-based)
- Identify persistent vs. transient text
- Improve subtitle vs. UI element distinction

### Sprint 06: ML Classifier (CRITICAL)
- Train Random Forest on 56 features (from Sprint 03)
- Collect 200+ labeled real-world YouTube videos
- Target: ≥92% F1 on real-world dataset
- Use multi-ROI detection results as input

### Sprint 07: Confidence Calibration
- Platt scaling for probability calibration
- Per-ROI confidence adjustment

### Sprint 08: Production Deployment
- Deploy multi-ROI detector to production
- A/B test vs. single-ROI detector
- Monitoring and telemetry

---

## 📝 IMPLEMENTATION CHECKLIST

### Phase 1: Dataset Generation
- [ ] Create `generate_edge_case_dataset.py` script
- [ ] Generate top subtitle videos (4)
- [ ] Generate side caption videos (4)
- [ ] Generate center text videos (4)
- [ ] Generate multi-position videos (4)
- [ ] Create `ground_truth.json` with labels
- [ ] Validate dataset (manual check)

### Phase 2: Core Implementation
- [ ] Add `ROI_CONFIGS` to SubtitleDetectorV2
- [ ] Implement `_crop_frames_to_roi()` method
- [ ] Implement `_detect_in_roi()` method
- [ ] Implement `detect_in_video_with_multi_roi()` method
- [ ] Add `roi_mode` parameter ('bottom', 'multi', 'all')
- [ ] Add ROI metadata to results

### Phase 3: Testing
- [ ] Create `test_sprint04_multi_roi.py`
- [ ] Test 1: Top subtitle detection
- [ ] Test 2: Side left caption detection
- [ ] Test 3: Side right caption detection
- [ ] Test 4: Center text detection
- [ ] Test 5: ROI priority fallback
- [ ] Test 6: Bottom ROI regression test
- [ ] Test 7: Multi-ROI performance test
- [ ] Test 8: All edge cases summary
- [ ] Run all 37 tests (29 existing + 8 new)
- [ ] Validate 100% pass rate

### Phase 4: Documentation
- [ ] Create `OK_SPRINT_04_SUMMARY.md`
- [ ] Update `RELATORIO_GERAL_PROGRESSO.md`
- [ ] Rename `sprint_04_multi_roi_fallback.md` → `OK_sprint_04_multi_roi_fallback.md`
- [ ] Document ROI configurations
- [ ] Document performance metrics

---

## 📚 REFERENCES

### Sprint 03 Features (to be used for ROI validation):
- `pos_vertical_mean`: Position indicator (top=0.0-0.25, bottom=0.75-1.0)
- `pos_bottom_ratio`: Proportion of text in bottom 25%
- `pos_top_ratio`: Proportion of text in top 25%
- `temp_persistence_mean`: Subtitles are temporally persistent
- `ocr_confidence_mean`: High confidence = likely subtitle

### Use Case Examples:
1. **Foreign film with top subtitles**: `pos_top_ratio > 0.7` → Top ROI catches it
2. **YouTube Short with side captions**: `pos_horizontal_mean < 0.2 or > 0.8` → Side ROIs catch it
3. **Embedded center text**: `pos_vertical_mean ≈ 0.5` → Center ROI catches it

---

**Status**: 🚧 Ready to implement  
**Estimated Time**: 1-2 days  
**Priority**: P1 (OPTIONAL, can skip to Sprint 06 if needed)  
**Dependencies**: Sprint 00-03 complete ✅

**Next Action**: Generate edge case dataset → Implement multi-ROI logic → Test with pytest → Document
