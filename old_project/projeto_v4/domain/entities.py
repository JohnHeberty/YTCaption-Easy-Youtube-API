from dataclasses import dataclass
from typing import List


@dataclass
class CaptionLine:
    start: float
    end: float
    text: str


@dataclass
class VideoCaptions:
    video_id: str
    lines: List[CaptionLine]

    def to_text(self) -> str:
        return "\n".join(f"[{l.start:.2f}-{l.end:.2f}] {l.text}" for l in self.lines)
