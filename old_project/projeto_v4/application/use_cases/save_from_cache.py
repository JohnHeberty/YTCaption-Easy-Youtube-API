from dataclasses import dataclass
from typing import Optional

from projeto_v3.application.ports.storage import StoragePort
from projeto_v3.domain.entities import VideoCaptions
from projeto_v3.infrastructure.cache import FileCaptionCache


@dataclass
class SaveFromCacheUseCase:
    cache: FileCaptionCache
    storage: StoragePort

    async def execute(self, video_id: str) -> Optional[dict]:
        vc: Optional[VideoCaptions] = self.cache.get(video_id)
        if vc is None:
            return None
        path = await self.storage.save_captions_text(video_id, vc.to_text())
        return {"video_id": video_id, "lines": len(vc.lines), "saved_path": path}
