import os
import tempfile
import asyncio
from typing import List
import yt_dlp
import whisper

from projeto_v3.application.ports.caption_provider import CaptionProviderPort
from projeto_v3.domain.entities import VideoCaptions, CaptionLine
from projeto_v3.infrastructure.resilience import retry_async, with_timeout


class WhisperProvider(CaptionProviderPort):
    def __init__(self, timeout_s: float, max_retries: int, model_name: str = "base"):
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        """Lazy load do modelo Whisper"""
        if self._model is None:
            self._model = whisper.load_model(self.model_name)
        return self._model

    @retry_async(max_retries=2)
    async def get_captions(self, video_id: str) -> VideoCaptions:
        """Baixa o vídeo e transcreve usando Whisper"""
        
        def _download_and_transcribe() -> VideoCaptions:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Configuração do yt-dlp para baixar apenas o áudio
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
                    'extractaudio': True,
                    'audioformat': 'wav',
                    'quiet': True,
                    'no_warnings': True,
                }
                
                # Baixa o áudio
                url = f"https://www.youtube.com/watch?v={video_id}"
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    audio_file = ydl.prepare_filename(info)
                    
                    # Remove extensão e adiciona .wav (yt-dlp pode converter)
                    base_name = os.path.splitext(audio_file)[0]
                    possible_files = [f"{base_name}.wav", f"{base_name}.m4a", f"{base_name}.webm", audio_file]
                    
                    actual_file = None
                    for pf in possible_files:
                        if os.path.exists(pf):
                            actual_file = pf
                            break
                    
                    if not actual_file:
                        raise RuntimeError(f"Audio file not found after download for {video_id}")
                
                # Transcreve com Whisper
                model = self._get_model()
                result = model.transcribe(actual_file)
                
                # Converte resultado do Whisper para nosso formato
                lines: List[CaptionLine] = []
                for segment in result['segments']:
                    lines.append(CaptionLine(
                        start=float(segment['start']),
                        end=float(segment['end']),
                        text=segment['text'].strip()
                    ))
                
                return VideoCaptions(video_id=video_id, lines=lines)
        
        # Executa em thread separada com timeout
        return await with_timeout(
            asyncio.to_thread(_download_and_transcribe),
            timeout_s=self.timeout_s
        )