from projeto_v3.application.ports.caption_provider import CaptionProviderPort
from projeto_v3.domain.entities import VideoCaptions


class FallbackProvider(CaptionProviderPort):
    def __init__(self, providers: list[CaptionProviderPort]):
        self.providers = providers

    async def get_captions(self, video_id: str) -> VideoCaptions:
        last_exception = None
        
        for provider in self.providers:
            try:
                return await provider.get_captions(video_id)
            except Exception as e:
                last_exception = e
                continue
        
        # Se todos falharam, relança a última exceção
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("No providers available")