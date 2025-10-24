from projeto_v3.application.ports.caption_provider import CaptionProviderPort
from projeto_v3.domain.entities import VideoCaptions, CaptionLine
from projeto_v3.infrastructure.resilience import retry_async


class YouTubeTranscriptProvider(CaptionProviderPort):
    def __init__(self, timeout_s: float, max_retries: int):
        self.timeout_s = timeout_s
        self.max_retries = max_retries

    @retry_async(max_retries=2)
    async def get_captions(self, video_id: str) -> VideoCaptions:
        # Import local para evitar custo caso não seja usado
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
        # A biblioteca não é async, então rodamos em thread
        import asyncio

        def _fetch():
            tr_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['pt', 'pt-BR', 'en'])
            lines = []
            for item in tr_list:
                text = item.get('text', '').replace('\n', ' ').strip()
                start = float(item.get('start', 0.0))
                end = start + float(item.get('duration', 0.0))
                if text:
                    lines.append(CaptionLine(start=start, end=end, text=text))
            return VideoCaptions(video_id=video_id, lines=lines)

        vc = await asyncio.to_thread(_fetch)
        if not vc.lines:
            raise RuntimeError("No transcript lines found")
        return vc
