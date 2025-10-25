from projeto_v3.application.ports.caption_provider import CaptionProviderPort
from projeto_v3.domain.entities import VideoCaptions
from projeto_v3.infrastructure.cache import FileCaptionCache


class CachedProvider(CaptionProviderPort):
    def __init__(self, primary: CaptionProviderPort, cache: FileCaptionCache, fallback: CaptionProviderPort | None = None):  # pylint: disable=line-too-long
        self.primary = primary
        self.cache = cache
        self.fallback = fallback

    async def get_captions(self, video_id: str) -> VideoCaptions:
        cached = self.cache.get(video_id)
        if cached is not None:
            return cached
        try:
            fresh = await self.primary.get_captions(video_id)
            self.cache.put(fresh)
            return fresh
        except Exception:
            if self.fallback is not None:
                fallback_vc = await self.fallback.get_captions(video_id)
                # não cacheia o stub para não "sujar" o cache com dados fake
                return fallback_vc
            raise
