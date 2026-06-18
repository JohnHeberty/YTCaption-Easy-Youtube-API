"""CSV fixture loader — reads real data from CSVs and builds CreateVideoRequest."""
import csv
import os
import random
from typing import Optional

from app.core.models import (
    CreateVideoRequest,
    NarrationSegment,
    OnScreenText,
    SceneSuggestion,
)


def _read_csv(filename: str, fixtures_dir: str) -> list[dict]:
    """Read a CSV file from fixtures directory, return list of dicts."""
    path = os.path.join(fixtures_dir, filename)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";", quotechar='"')
        return list(reader)


def _group_by(rows: list[dict], key: str) -> dict[str, list[dict]]:
    """Group rows by a key field."""
    groups: dict[str, list[dict]] = {}
    for row in rows:
        k = row.get(key, "")
        groups.setdefault(k, []).append(row)
    return groups


def load_all_scripts(fixtures_dir: str) -> dict[str, dict]:
    """Load all CSVs and merge by script_id.

    Returns:
        dict mapping script_id → merged data dict ready for CreateVideoRequest.
    """
    scripts = _read_csv("video_scripts.csv", fixtures_dir)
    narration_rows = _read_csv("video_script_narration.csv", fixtures_dir)
    scenes_rows = _read_csv("video_script_scene_suggestions.csv", fixtures_dir)
    on_screen_rows = _read_csv("video_script_on_screen_text.csv", fixtures_dir)
    hashtags_rows = _read_csv("video_script_hashtags.csv", fixtures_dir)
    titles_rows = _read_csv("video_script_title_options.csv", fixtures_dir)
    safety_rows = _read_csv("video_script_safety_notes.csv", fixtures_dir)

    narration_groups = _group_by(narration_rows, "script_id")
    scenes_groups = _group_by(scenes_rows, "script_id")
    on_screen_groups = _group_by(on_screen_rows, "script_id")
    hashtags_groups = _group_by(hashtags_rows, "script_id")
    titles_groups = _group_by(titles_rows, "script_id")
    safety_groups = _group_by(safety_rows, "script_id")

    result = {}
    for s in scripts:
        sid = s.get("script_id", "").strip()
        if not sid:
            continue

        narration = [
            NarrationSegment(t=float(r["t"]), text=r["text"])
            for r in sorted(narration_groups.get(sid, []), key=lambda x: float(x.get("t", 0)))
            if r.get("text")
        ]
        scenes = [
            SceneSuggestion(t=float(r["t"]), visual=r["visual"])
            for r in sorted(scenes_groups.get(sid, []), key=lambda x: float(x.get("t", 0)))
            if r.get("visual")
        ]
        on_screen = [
            OnScreenText(t=float(r["t"]), text=r["text"])
            for r in sorted(on_screen_groups.get(sid, []), key=lambda x: float(x.get("t", 0)))
            if r.get("text")
        ]
        hashtags = [
            r["tag"] for r in hashtags_groups.get(sid, []) if r.get("tag")
        ]
        titles = [
            r["title"] for r in sorted(titles_groups.get(sid, []), key=lambda x: int(x.get("idx", 0)))
            if r.get("title")
        ]
        safety = [
            r["note"] for r in sorted(safety_groups.get(sid, []), key=lambda x: int(x.get("idx", 0)))
            if r.get("note")
        ]

        est = s.get("estimated_seconds", "60")
        try:
            estimated_seconds = int(float(est))
        except (ValueError, TypeError):
            estimated_seconds = 60

        if not narration or not scenes:
            continue

        result[sid] = {
            "script_id": sid,
            "post_id": s.get("post_id", sid),
            "hook": s.get("hook", ""),
            "estimated_seconds": estimated_seconds,
            "language": s.get("language", "pt-BR"),
            "content_rating": s.get("content_rating", "Geral"),
            "narration": narration,
            "scene_suggestions": scenes,
            "on_screen_text": on_screen,
            "title_options": titles,
            "hashtags": hashtags,
            "safety_notes": safety,
        }

    return result


def build_request(data: dict, **overrides) -> CreateVideoRequest:
    """Build a CreateVideoRequest from merged script data."""
    return CreateVideoRequest(
        post_id=overrides.get("post_id", data["post_id"]),
        hook=overrides.get("hook", data["hook"]),
        estimated_seconds=overrides.get("estimated_seconds", data["estimated_seconds"]),
        language=overrides.get("language", data["language"]),
        content_rating=overrides.get("content_rating", data["content_rating"]),
        narration=data["narration"],
        scene_suggestions=data["scene_suggestions"],
        on_screen_text=data.get("on_screen_text", []),
        title_options=data.get("title_options", []),
        hashtags=data.get("hashtags", []),
        safety_notes=data.get("safety_notes", []),
        voice_id=overrides.get("voice_id", "builtin_feminino"),
        aspect_ratio=overrides.get("aspect_ratio", "9:16"),
        zoom_style=overrides.get("zoom_style", "random"),
    )


def pick_random_script(fixtures_dir: Optional[str] = None, seed: Optional[int] = None) -> tuple[str, CreateVideoRequest]:
    """Pick a random script from CSV data and return (script_id, request).

    Args:
        fixtures_dir: Path to fixtures/ directory. Auto-detected if None.
        seed: Optional random seed for reproducibility.

    Returns:
        (script_id, CreateVideoRequest) tuple.
    """
    if fixtures_dir is None:
        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")

    scripts = load_all_scripts(fixtures_dir)
    if not scripts:
        raise RuntimeError(f"No scripts found in {fixtures_dir}")

    script_ids = list(scripts.keys())
    if seed is not None:
        random.seed(seed)
    script_id = random.choice(script_ids)
    return script_id, build_request(scripts[script_id])
