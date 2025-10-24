from dataclasses import dataclass

from projeto_v3.application.ports.caption_provider import CaptionProviderPort
from projeto_v3.application.ports.storage import StoragePort


@dataclass
class FetchCaptionsUseCase:
    provider: CaptionProviderPort
    storage: StoragePort

    async def execute(self, video_id: str) -> dict:
        vc = await self.provider.get_captions(video_id)
        path = await self.storage.save_captions_text(video_id, vc.to_text())
        return {"video_id": video_id, "lines": len(vc.lines), "saved_path": path}
