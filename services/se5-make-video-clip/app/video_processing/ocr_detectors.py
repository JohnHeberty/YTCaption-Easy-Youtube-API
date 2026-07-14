from __future__ import annotations

"""
OCR Detectors — TRSD and Legacy OCR detection extracted from video_validator.py
"""

import cv2
import numpy as np
import time
from pathlib import Path
from typing import Any

from app.subtitle_processing.subtitle_detector import TextRegionExtractor
from app.subtitle_processing.temporal_tracker import TemporalTracker
from app.subtitle_processing.subtitle_classifier_v2 import SubtitleClassifierV2
from app.infrastructure.telemetry import TRSDTelemetry, DebugArtifactSaver, PerformanceMetrics
from app.core.config import Settings
from .frame_extractor import FFmpegFrameExtractor
from common.log_utils import get_logger

logger = get_logger(__name__)


class VideoIntegrityError(Exception):
    """Exception for corrupted or invalid videos"""
    pass


def _get_sample_timestamps(duration: float, sample_interval: float = 2.0) -> list[float]:
    """Generate evenly-spaced timestamps for frame sampling."""
    if duration <= 0:
        return [0.0]
    timestamps = []
    t = 0.0
    while t < duration:
        timestamps.append(t)
        t += sample_interval
    return timestamps


class TRSDDetector:

    def __init__(
        self,
        config: Settings,
        text_extractor: TextRegionExtractor,
        classifier: SubtitleClassifierV2,
        frame_extractor: FFmpegFrameExtractor,
        telemetry: TRSDTelemetry,
        debug_saver: DebugArtifactSaver,
        get_video_info: Any,
    ) -> None:
        self.config = config
        self.text_extractor = text_extractor
        self.classifier = classifier
        self.frame_extractor = frame_extractor
        self.telemetry = telemetry
        self.debug_saver = debug_saver
        self._get_video_info = get_video_info

    def _run_ocr_frame_loop(
        self,
        extraction_result: Any,
        timeout: int,
    ) -> tuple[Any, int, int, Any, Any]:
        """Run OCR on extracted frames.

        Returns (tracker, frames_analyzed, total_lines_detected, early_result_or_none, early_tracks).
        """
        tracker = TemporalTracker(self.config)
        self.telemetry.start_timer('ocr')

        frames_analyzed = 0
        total_lines_detected = 0

        for frame_idx, (frame, ts) in enumerate(extraction_result.frames):
            frames_analyzed += 1
            text_lines = self.text_extractor.extract_from_frame(frame, ts, frame_idx)
            total_lines_detected += len(text_lines)
            tracker.update(text_lines, frame_idx)

            if frames_analyzed >= 10 and frame_idx % 5 == 0:
                partial_tracks = tracker.active_tracks
                for track in partial_tracks:
                    track.compute_metrics(frames_analyzed)

                self.telemetry.start_timer('classification')
                result = self.classifier.decide(partial_tracks)
                self.telemetry.stop_timer('classification')

                if result.has_subtitles and result.confidence >= 0.85:
                    return (tracker, frames_analyzed, total_lines_detected, result, partial_tracks)

        return (tracker, frames_analyzed, total_lines_detected, None, None)

    def _build_performance_metrics(
        self,
        total_ms: float,
        frame_extraction_ms: float,
        ocr_time_ms: float,
        classification_ms: float,
        frames_analyzed: int,
        tracks_count: int,
        lines_detected: int,
    ) -> PerformanceMetrics:
        """Build a PerformanceMetrics instance."""
        return PerformanceMetrics(
            total_time_ms=total_ms,
            frame_extraction_ms=frame_extraction_ms,
            ocr_time_ms=ocr_time_ms,
            tracking_time_ms=0.0,
            classification_time_ms=classification_ms,
            frames_analyzed=frames_analyzed,
            tracks_created=tracks_count,
            lines_detected=lines_detected
        )

    def _record_and_return(
        self,
        result: Any,
        video_id: str,
        extraction_result: Any,
        tracks: Any,
        metrics: PerformanceMetrics,
        frames_analyzed: int,
        total_lines_detected: int,
        early_exit: bool,
    ) -> tuple[bool, float, str, dict[str, Any]]:
        """Record telemetry and debug artifacts, then return detection tuple."""
        self.telemetry.record_decision(
            video_id=video_id,
            decision='block' if result.has_subtitles else 'approve',
            confidence=result.confidence,
            reason=result.reason,
            method='TRSD',
            metrics=metrics,
            tracks_by_category=result.tracks_by_category,
            decision_logic=result.decision_logic,
            early_exit=early_exit,
            debug_info={'extraction_method': extraction_result.method}
        )

        self.debug_saver.save_detection_artifacts(
            video_id, extraction_result.frames, tracks, result, metrics
        )

        return (
            result.has_subtitles,
            result.confidence,
            result.reason,
            {
                'method': 'TRSD',
                'early_exit': early_exit,
                'frames_analyzed': frames_analyzed,
                'tracks_by_category': result.tracks_by_category
            }
        )

    def detect(self, video_path: str, timeout: int = 60) -> tuple[bool, float, str, dict[str, Any]]:
        start_time = time.time()

        try:
            self.telemetry.start_timer('total')

            info = self._get_video_info(video_path)
            duration = info['duration']
            timestamps = _get_sample_timestamps(duration)

            logger.info(f"TRSD: Analyzing {len(timestamps)} frames from {duration:.1f}s video")

            self.telemetry.start_timer('frame_extraction')
            extraction_result = self.frame_extractor.extract_frames(
                video_path, timestamps, timeout
            )
            frame_extraction_ms = self.telemetry.stop_timer('frame_extraction')

            logger.info(
                f"Frame extraction: {extraction_result.method}, "
                f"{extraction_result.extraction_time_ms:.0f}ms, "
                f"{len(extraction_result.frames)} frames"
            )

            tracker, frames_analyzed, total_lines_detected, early_result, early_tracks = \
                self._run_ocr_frame_loop(extraction_result, timeout)

            video_id = Path(video_path).stem
            ocr_time_ms = self.telemetry.stop_timer('ocr')

            if early_result is not None:
                total_ms = self.telemetry.stop_timer('total')
                elapsed_ms = (time.time() - start_time) * 1000

                metrics = self._build_performance_metrics(
                    total_ms, frame_extraction_ms, ocr_time_ms,
                    0.0, frames_analyzed, len(early_result.subtitle_tracks),
                    total_lines_detected
                )

                logger.warning(
                    f"TRSD EARLY EXIT: Detected subtitles @ frame {frames_analyzed} "
                    f"(conf={early_result.confidence:.2f}, {elapsed_ms:.0f}ms)"
                )

                ret = self._record_and_return(
                    early_result, video_id, extraction_result, early_tracks,
                    metrics, frames_analyzed, total_lines_detected, early_exit=True
                )
                # Override tracks key for early exit
                return (
                    ret[0], ret[1], ret[2],
                    {**ret[3], 'tracks': len(early_result.subtitle_tracks)}
                )

            # No early exit — finalize
            final_tracks = tracker.finalize()

            self.telemetry.start_timer('classification')
            result = self.classifier.decide(final_tracks)
            classification_ms = self.telemetry.stop_timer('classification')

            total_ms = self.telemetry.stop_timer('total')
            elapsed_ms = (time.time() - start_time) * 1000

            metrics = self._build_performance_metrics(
                total_ms, frame_extraction_ms, ocr_time_ms,
                classification_ms, frames_analyzed, len(final_tracks),
                total_lines_detected
            )

            logger.info(
                f"{'WARNING' if result.has_subtitles else 'OK'} TRSD: {result.reason} "
                f"(conf={result.confidence:.2f}, {frames_analyzed} frames, {elapsed_ms:.0f}ms)"
            )

            return self._record_and_return(
                result, video_id, extraction_result, final_tracks,
                metrics, frames_analyzed, total_lines_detected, early_exit=False
            )

        except Exception as e:
            logger.error(f"TRSD detection failed: {e}", exc_info=True)
            raise


class LegacyOCRDetector:

    def __init__(
        self,
        ocr_detector: Any,
        visual_analyzer: Any,
        ocr_lock: Any,
        min_confidence: float,
        frames_per_second: int | None,
        max_frames: int | None,
        ensure_supported_codec: Any,
    ) -> None:
        self.ocr_detector = ocr_detector
        self.visual_analyzer = visual_analyzer
        self._ocr_lock = ocr_lock
        self.min_confidence = min_confidence
        self.frames_per_second = frames_per_second
        self.max_frames = max_frames
        self._ensure_supported_codec = ensure_supported_codec

    def detect(self, video_path: str, timeout: int = 300) -> tuple[bool, float, str, int]:
        start_time = time.time()
        working_path = video_path
        cleanup_path = None

        try:
            working_path, cleanup_path = self._ensure_supported_codec(video_path)

            cap = cv2.VideoCapture(working_path)
            if not cap.isOpened():
                raise VideoIntegrityError(f"Cannot open video: {working_path}")

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 0

            frame_step = max(1, int(fps / self.frames_per_second)) if self.frames_per_second else 1
            max_frames_to_process = self.max_frames if self.max_frames else total_frames

            logger.info(
                f"OCR: processing up to {max_frames_to_process} frames "
                f"(step={frame_step}, {fps:.2f} fps, {duration:.1f}s video)"
            )

            frames_analyzed = 0
            all_detections = []
            first_text_detected = None
            frame_count = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1
                if frame_count % frame_step != 0:
                    continue

                if frames_analyzed >= max_frames_to_process:
                    break

                frames_analyzed += 1

                if frames_analyzed % 100 == 0:
                    logger.debug(f"   Processing frame {frames_analyzed}/{total_frames}...")

                try:
                    with self._ocr_lock:
                        ocr_results = self.ocr_detector.detect_text(frame)

                    if ocr_results:
                        all_texts = []
                        max_conf = 0.0

                        for result in ocr_results:
                            if result.text.strip():
                                all_texts.append(result.text)
                                max_conf = max(max_conf, result.confidence)

                        if all_texts:
                            text = ' '.join(all_texts).strip()
                            timestamp = frames_analyzed / fps if fps > 0 else frames_analyzed

                            all_detections.append((text, max_conf, timestamp))

                            if first_text_detected is None and max_conf >= self.min_confidence:
                                first_text_detected = (text, max_conf, timestamp)
                                logger.warning(
                                    f"TEXT DETECTED at frame {frames_analyzed}/{total_frames} "
                                    f"(ts={timestamp:.1f}s, conf={max_conf:.2f}): {text[:80]}"
                                )

                except Exception as e:
                    logger.debug(f"Error at frame {frames_analyzed}: {e}")
                    continue

            cap.release()

            elapsed_ms = (time.time() - start_time) * 1000

            if first_text_detected:
                text, conf, ts = first_text_detected
                logger.error(
                    f"EMBEDDED SUBTITLES DETECTED - BAN!\n"
                    f"   Frames analyzed: {frames_analyzed}/{total_frames}\n"
                    f"   Total detections: {len(all_detections)}\n"
                    f"   First detection: frame @ {ts:.1f}s (conf={conf:.2f})\n"
                    f"   Text: {text[:100]}\n"
                    f"   Time: {elapsed_ms:.0f}ms"
                )
                return True, conf, text, frames_analyzed

            logger.info(
                f"Video APPROVED - No text detected\n"
                f"   Frames analyzed: {frames_analyzed}/{total_frames}\n"
                f"   Low confidence detections: {len(all_detections)}\n"
                f"   Time: {elapsed_ms:.0f}ms"
            )
            return False, 0.0, "", frames_analyzed

        except Exception as e:
            logger.error(f"OCR detection error: {e}", exc_info=True)
            return False, 0.0, f"Error: {e}", 0

        finally:
            if cleanup_path:
                try:
                    Path(cleanup_path).unlink(missing_ok=True)
                except Exception:
                    logger.debug(f"Could not remove temp transcoded file: {cleanup_path}")
