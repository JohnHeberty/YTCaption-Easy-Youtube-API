from abc import ABC, abstractmethod
from projeto_v3.domain.entities import VideoCaptions


class CaptionProviderPort(ABC):
    @abstractmethod
    async def get_captions(self, video_id: str) -> VideoCaptions:  # pragma: no cover - interface
        ...
