import json
import os
import time
from typing import Optional

from projeto_v3.domain.entities import CaptionLine, VideoCaptions


class FileCaptionCache:
    def __init__(self, base_dir: str, ttl_seconds: int = 86400):
        self.cache_dir = os.path.join(base_dir, "cache")
        self.ttl_seconds = ttl_seconds
        os.makedirs(self.cache_dir, exist_ok=True)

    def _path(self, video_id: str) -> str:
        return os.path.join(self.cache_dir, f"{video_id}.json")

    def get(self, video_id: str) -> Optional[VideoCaptions]:
        path = self._path(video_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if (time.time() - data.get("ts", 0)) > self.ttl_seconds:
                return None
            lines = [CaptionLine(**l) for l in data.get("lines", [])]
            return VideoCaptions(video_id=video_id, lines=lines)
        except Exception:
            return None

    def put(self, vc: VideoCaptions) -> None:
        path = self._path(vc.video_id)
        payload = {
            "ts": time.time(),
            "lines": [
                {"start": l.start, "end": l.end, "text": l.text}
                for l in vc.lines
            ],
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
