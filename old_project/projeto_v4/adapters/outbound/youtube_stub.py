import asyncio

from projeto_v3.application.ports.caption_provider import CaptionProviderPort
from projeto_v3.domain.entities import VideoCaptions, CaptionLine
from projeto_v3.infrastructure.resilience import retry_async


class YouTubeStubProvider(CaptionProviderPort):
    def __init__(self, timeout_s: float, max_retries: int):
        self.timeout_s = timeout_s
        self.max_retries = max_retries

    @retry_async(max_retries=2)
    async def get_captions(self, video_id: str) -> VideoCaptions:
        # Simula latência pequena; nenhum acesso de rede real
        await asyncio.sleep(0.05)
        lines = [
            CaptionLine(0.0, 1.5, f"Demo caption for {video_id} - line 1"),
            CaptionLine(1.5, 3.0, "Line 2"),
        ]
        return VideoCaptions(video_id=video_id, lines=lines)
