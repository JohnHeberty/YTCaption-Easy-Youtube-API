#!/usr/bin/env python3
"""Convert make-video.json (upstream format) → CreateVideoRequest (SE9 API format).

Usage:
    python3 scripts/convert_make_video.py make-video.json > /tmp/payload.json
    python3 scripts/convert_make_video.py make-video.json --pretty
    python3 scripts/convert_make_video.py make-video.json --send

Handles all gaps identified in INVESTIGATE.md:
- G1: negative_prompt from image.negative_prompt
- G2: camera_movement from motion.camera_movement
- G3: transition from motion.transition
- G4: global_start_seconds for caption timing
- G5: end_seconds for caption duration
- G6: global_style preserved as metadata
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── Mapping tables ──────────────────────────────────────────────────────────

# Camera movement → SE9 Ken Burns zoom style
CAMERA_MOVEMENT_MAP = {
    "static": "static",
    "slow_push_in": "slow_push_in",
    "slow_pull_out": "slow_pull_out",
}

# Transition names from upstream JSON → FFmpeg xfade names
# None = hard cut (no transition)
TRANSITION_MAP = {
    "corte seco": None,
    "fade curto": "fadeblack",
    "fade": "fadefast",
    "dissolve": "dissolve",
    "crossfade": "dissolve",
}


def convert(input_path: str) -> dict:
    """Convert make-video.json to CreateVideoRequest format."""
    with open(input_path) as f:
        data = json.load(f)

    # Handle both array and object formats
    entry = data[0] if isinstance(data, list) else data
    output = entry.get("output", entry)

    # ── narration: [{t, text}] ──
    narration = []
    for scene in output.get("scenes", []):
        narration.append({
            "t": scene["start_seconds"],
            "text": scene["narration_text"],
        })

    # ── scene_suggestions: [{t, visual, negative_prompt, camera_movement, transition}] ──
    scene_suggestions = []
    for scene in output.get("scenes", []):
        image = scene.get("image", {})
        motion = scene.get("motion", {})

        suggestion: dict = {
            "t": scene["start_seconds"],
            "visual": image.get("prompt", ""),
        }

        # G1: Include negative_prompt
        neg = image.get("negative_prompt")
        if neg:
            suggestion["negative_prompt"] = neg

        # G2: Include camera_movement
        cam = motion.get("camera_movement")
        if cam and cam in CAMERA_MOVEMENT_MAP:
            suggestion["camera_movement"] = CAMERA_MOVEMENT_MAP[cam]

        # G3: Include transition
        trans_raw = motion.get("transition")
        if trans_raw and trans_raw in TRANSITION_MAP:
            mapped = TRANSITION_MAP[trans_raw]
            if mapped is not None:  # None = hard cut, don't include
                suggestion["transition"] = mapped

        scene_suggestions.append(suggestion)

    # ── on_screen_text: [{t, text, end_seconds}] using GLOBAL timestamps ──
    on_screen_text = []
    for scene in output.get("scenes", []):
        for cap in scene.get("captions", []):
            entry: dict = {
                "t": cap.get("global_start_seconds", cap.get("start_seconds", 0)),
                "text": cap["text"],
            }
            # G5: Include end_seconds using global timing
            if "global_end_seconds" in cap:
                entry["end_seconds"] = cap["global_end_seconds"]
            elif "end_seconds" in cap:
                entry["end_seconds"] = cap["end_seconds"]
            on_screen_text.append(entry)

    # ── Build request ──
    request: dict = {
        "post_id": output.get("post_id", "unknown"),
        "hook": output.get("title", ""),
        "estimated_seconds": output.get("total_duration_seconds", 30),
        "language": output.get("language", "pt-BR"),
        "narration": narration,
        "scene_suggestions": scene_suggestions,
        "on_screen_text": on_screen_text,
        "voice_id": "builtin_feminino",
        "aspect_ratio": output.get("aspect_ratio", "9:16"),
        "zoom_style": "random",
        "normalize_text": True,
    }

    # G6: Preserve global_style metadata
    global_style = output.get("global_style")
    if global_style:
        request["global_style"] = global_style

    return request


def main():
    parser = argparse.ArgumentParser(
        description="Convert make-video.json → SE9 API payload"
    )
    parser.add_argument("input", help="Path to make-video.json")
    parser.add_argument(
        "--output", "-o",
        help="Output file (default: stdout)",
    )
    parser.add_argument(
        "--pretty", "-p",
        action="store_true",
        help="Pretty-print JSON",
    )
    parser.add_argument(
        "--send", "-s",
        action="store_true",
        help="Send directly to SE9 API (POST /jobs)",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8009",
        help="SE9 base URL (default: http://localhost:8009)",
    )
    parser.add_argument(
        "--api-key",
        default="se9-test-key-2026",
        help="API key (default: se9-test-key-2026)",
    )
    args = parser.parse_args()

    request = convert(args.input)

    if args.send:
        import httpx
        resp = httpx.post(
            f"{args.url}/jobs",
            json=request,
            headers={"X-API-Key": args.api_key},
            timeout=30,
        )
        print(f"Status: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
        return

    indent = 2 if args.pretty else None
    output = json.dumps(request, indent=indent, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(output + "\n")
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
