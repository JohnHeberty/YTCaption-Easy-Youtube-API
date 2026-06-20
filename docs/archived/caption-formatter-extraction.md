# CaptionFormatter Extraction — SRP Violation Fix (MELHORE 1.2)

**Date:** 2026-06-13  
**Status:** ✅ RESOLVIDO  

## Problem
`_convert_to_srt()` and `_seconds_to_srt_time()` existed as duplicate methods in both:
- `processor.py` (lines 907-927) — used at line 563 for job completion output
- `transcription_service.py` (lines 331-356) — used at line 296

Both were pure functions with zero dependencies on class state, violating SRP by living inside orchestrator classes.

## Solution
Created standalone `app/shared/caption_formatter.py` with:
- `CaptionFormatter.to_srt()` / `.to_vtt()` / `.to_txt()` / `.to_lrc()` / `.to_sam()` — all static methods
- `_seconds_to_timestamp(seconds, fmt)` — shared timestamp converter supporting SRT/VTT/LRC formats (comma vs dot separator)
- `format(segments, output_format)` — dispatcher method for format selection
- Legacy aliases: `convert_to_srt()`, `seconds_to_srt_time()`

## Files Changed
1. **NEW** `app/shared/caption_formatter.py` — standalone module (~90 lines)
2. **MODIFIED** `processor.py`: removed `_convert_to_srt()` + `_seconds_to_srt_time()`, added import, replaced call site at line 563 → `CaptionFormatter.to_srt(result["segments"])`
3. **MODIFIED** `transcription_service.py`: removed duplicate methods (lines 331-356), added import, replaced call site at line 297 → `CaptionFormatter.to_srt(segments)`

## Validation
All formats tested inside Docker container:
- SRT: `00:00:00,500 --> 00:00:02,299` (comma separator) ✓
- VTT: WEBVTT header + dot-separated timestamps ✓  
- TXT: plain text join ✓
- LRC: `[mm:ss.xx]text` format ✓
- SAM: matches SRT format ✓
- Empty segment edge cases handled ✓

## Lines Removed from processor.py
21 lines (methods 907-927) → reduces file to ~1086 lines  
Next extraction target per MELHORE.md remains AudioConverter (~180 lines).
