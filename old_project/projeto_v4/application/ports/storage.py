from abc import ABC, abstractmethod


class StoragePort(ABC):
    @abstractmethod
    async def save_captions_text(self, video_id: str, content: str) -> str:  # returns saved file path
        ...
