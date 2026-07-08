from __future__ import annotations

from typing import Any

from app.services.vad_detectors import SpeechSegment
from common.log_utils import get_logger

logger = get_logger(__name__)


class SubtitleCue:
    def __init__(self, index: int, start: float, end: float, text: str) -> None:
        self.index = index
        self.start = start
        self.end = end
        self.text = text


def _intervals_intersect(
    a_start: float, a_end: float,
    b_start: float, b_end: float,
) -> bool:
    return not (a_end < b_start or b_end < a_start)


def _find_intersecting_segment(
    cue: SubtitleCue,
    segments: list[SpeechSegment],
) -> SpeechSegment | None:
    for segment in segments:
        if _intervals_intersect(cue.start, cue.end, segment.start, segment.end):
            return segment
    return None


def _clamp_cue_to_segment(
    cue: SubtitleCue,
    segment: SpeechSegment,
    audio_duration: float,
    pre_pad: float,
    post_pad: float,
    word_post_pad: float,
    min_duration: float,
) -> SubtitleCue:
    allowed_start = max(0.0, segment.start - pre_pad)
    allowed_end = min(audio_duration, segment.end + post_pad)

    clamped_start = max(allowed_start, cue.start)
    clamped_end = min(allowed_end, cue.end + word_post_pad)

    if clamped_end - clamped_start < min_duration:
        clamped_end = min(allowed_end, clamped_start + min_duration)

    if clamped_end <= clamped_start:
        clamped_end = min(allowed_end, clamped_start + min_duration)

    return SubtitleCue(
        index=cue.index,
        start=clamped_start,
        end=clamped_end,
        text=cue.text,
    )


def _merge_close_cues(cues: list[SubtitleCue], merge_gap: float) -> list[SubtitleCue]:
    if not cues:
        return []

    merged: list[SubtitleCue] = [cues[0]]

    for cue in cues[1:]:
        prev = merged[-1]
        gap = cue.start - prev.end

        if gap < merge_gap:
            merged[-1] = SubtitleCue(
                index=prev.index,
                start=prev.start,
                end=cue.end,
                text=f"{prev.text} {cue.text}",
            )
        else:
            merged.append(cue)

    return merged


def gate_subtitles(
    cues: list[SubtitleCue],
    speech_segments: list[SpeechSegment],
    audio_duration: float,
    pre_pad: float,
    post_pad: float,
    word_post_pad: float,
    min_duration: float,
    merge_gap: float,
) -> list[SubtitleCue]:
    gated_cues: list[SubtitleCue] = []
    dropped_count = 0

    for cue in cues:
        intersecting_segment = _find_intersecting_segment(cue, speech_segments)

        if intersecting_segment is None:
            logger.debug(f"⚠️ DROP cue '{cue.text}' (fora de fala)")
            dropped_count += 1
            continue

        gated_cues.append(_clamp_cue_to_segment(
            cue, intersecting_segment, audio_duration,
            pre_pad, post_pad, word_post_pad, min_duration,
        ))

    merged_cues = _merge_close_cues(gated_cues, merge_gap)

    merged_count = len(gated_cues) - len(merged_cues)
    logger.info(
        f"✅ Speech gating: {len(merged_cues)}/{len(cues)} cues finais, "
        f"{dropped_count} dropped, {merged_count} merged"
    )

    return merged_cues


def validate_speech_gating(
    cues: list[SubtitleCue],
    speech_segments: list[SpeechSegment],
    vad_ok: bool,
) -> dict[str, Any]:
    if not cues:
        return {
            'total_cues': 0,
            'cues_outside_speech': 0,
            'pct_outside_speech': 0.0,
            'vad_ok': vad_ok,
            'passed': True,
            'target': '0% quando VAD OK',
        }

    cues_outside_speech = 0

    for cue in cues:
        has_speech = _find_intersecting_segment(cue, speech_segments) is not None

        if not has_speech:
            cues_outside_speech += 1
            logger.warning(
                f"⚠️ Cue fora de fala: '{cue.text}' @ {cue.start:.2f}s"
            )

    pct_outside = cues_outside_speech / len(cues) * 100
    passed = (pct_outside == 0) if vad_ok else None

    return {
        'total_cues': len(cues),
        'cues_outside_speech': cues_outside_speech,
        'pct_outside_speech': pct_outside,
        'vad_ok': vad_ok,
        'passed': passed,
        'target': '0% quando VAD OK; fallback_rate < 5%',
    }
