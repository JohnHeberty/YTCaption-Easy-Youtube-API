import os
import asyncio

from projeto_v3.application.ports.storage import StoragePort


class FileStorage(StoragePort):
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.captions_dir = os.path.join(base_dir, "captions")
        os.makedirs(self.captions_dir, exist_ok=True)

    async def save_captions_text(self, video_id: str, content: str) -> str:
        path = os.path.join(self.captions_dir, f"{video_id}.txt")

        def _write() -> None:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

        await asyncio.to_thread(_write)
        return path
