import os
import asyncio
from pathlib import Path
import whisper
import logging
from .models import Job, JobStatus, TranscriptionSegment
from .exceptions import AudioTranscriptionException

logger = logging.getLogger(__name__)


class TranscriptionProcessor:
    def __init__(self):
        self.job_store = None  # Will be injected
        self.model = None  # Lazy loading
    
    def _load_model(self):
        """Carrega modelo Whisper (lazy loading)"""
        if self.model is None:
            try:
                logger.info("Carregando modelo Whisper...")
                self.model = whisper.load_model("base")
                logger.info("Modelo Whisper carregado com sucesso")
            except Exception as e:
                logger.error(f"Erro ao carregar modelo Whisper: {e}")
                raise AudioTranscriptionException(f"Falha ao carregar modelo: {str(e)}")
    
    async def process_transcription_job(self, job: Job):
        """Processa um job de transcrição"""
        try:
            logger.info(f"Iniciando processamento do job: {job.id}")
            
            # Atualiza status para processando
            job.status = JobStatus.PROCESSING
            if self.job_store:
                self.job_store.update_job(job)
            
            # Validação robusta do arquivo com ffprobe
            from .security import validate_audio_content_with_ffprobe
            try:
                file_info = validate_audio_content_with_ffprobe(job.input_file)
                logger.info(f"Arquivo validado com ffprobe: {file_info['type']}")
                
                # Se for vídeo, extrai áudio automaticamente
                if file_info['type'] == 'video_with_audio':
                    logger.info("Arquivo de vídeo detectado, extraindo áudio...")
                    job.input_file = await self._extract_audio_from_video(job.input_file)
                    logger.info(f"Áudio extraído para: {job.input_file}")
                    
            except Exception as e:
                logger.error(f"Validação ffprobe falhou: {e}")
                raise AudioTranscriptionException(str(e))
            
            # Carrega modelo se necessário
            self._load_model()
            
            # Atualiza progresso
            job.progress = 25.0
            if self.job_store:
                self.job_store.update_job(job)
            
            # Processa transcrição
            logger.info(f"Transcrevendo arquivo: {job.input_file}")
            result = self.model.transcribe(job.input_file, language=None if job.language == "auto" else job.language)
            
            # Atualiza progresso
            job.progress = 75.0
            if self.job_store:
                self.job_store.update_job(job)
            
            # Converte segments para o formato com start, end, duration
            transcription_segments = []
            for seg in result["segments"]:
                segment = TranscriptionSegment(
                    text=seg["text"].strip(),
                    start=seg["start"],
                    end=seg["end"],
                    duration=seg["end"] - seg["start"]
                )
                transcription_segments.append(segment)
            
            # Salva arquivo de transcrição
            transcription_dir = Path("./transcriptions")
            transcription_dir.mkdir(exist_ok=True)
            
            output_path = transcription_dir / f"{job.id}_transcription.srt"
            
            # Converte para formato SRT
            srt_content = self._convert_to_srt(result["segments"])
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
            
            # Finaliza job
            job.output_file = str(output_path)
            job.status = JobStatus.COMPLETED
            job.progress = 100.0
            job.transcription_text = result["text"]
            job.transcription_segments = transcription_segments  # Adiciona segments ao job
            job.file_size_output = output_path.stat().st_size
            
            if self.job_store:
                self.job_store.update_job(job)
            
            logger.info(f"Job {job.id} transcrito com sucesso")
            logger.info(f"Total de segmentos: {len(transcription_segments)}")
            
        except Exception as e:
            # Marca job como falhou
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            
            if self.job_store:
                self.job_store.update_job(job)
            
            logger.error(f"Job {job.id} falhou: {e}")
            raise AudioTranscriptionException(f"Erro na transcrição: {str(e)}")
    
    def _convert_to_srt(self, segments):
        """Converte segmentos do Whisper para formato SRT"""
        srt_content = ""
        
        for i, segment in enumerate(segments, 1):
            start_time = self._seconds_to_srt_time(segment["start"])
            end_time = self._seconds_to_srt_time(segment["end"])
            text = segment["text"].strip()
            
            srt_content += f"{i}\n{start_time} --> {end_time}\n{text}\n\n"
        
        return srt_content
    
    def _seconds_to_srt_time(self, seconds):
        """Converte segundos para formato de tempo SRT (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    async def _extract_audio_from_video(self, video_file_path: str) -> str:
        """
        Extrai áudio de arquivo de vídeo usando ffmpeg
        
        Args:
            video_file_path: Caminho para o arquivo de vídeo
            
        Returns:
            str: Caminho para o arquivo de áudio extraído
        """
        import subprocess
        
        try:
            # Cria arquivo temporário para o áudio extraído
            temp_dir = Path("temp")
            temp_dir.mkdir(exist_ok=True)
            
            video_path = Path(video_file_path)
            audio_filename = f"{video_path.stem}_audio.wav"
            audio_path = temp_dir / audio_filename
            
            # Comando ffmpeg para extrair áudio
            cmd = [
                'ffmpeg', '-i', str(video_file_path),
                '-vn',  # Remove streams de vídeo
                '-acodec', 'pcm_s16le',  # Codec áudio para compatibilidade
                '-ar', '16000',  # Sample rate 16kHz (ótimo para Whisper)
                '-ac', '1',  # Mono
                '-y',  # Sobrescrever se existir
                str(audio_path)
            ]
            
            logger.info(f"Extraindo áudio: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                raise AudioTranscriptionException(f"Falha ao extrair áudio: {result.stderr}")
            
            if not audio_path.exists():
                raise AudioTranscriptionException("Arquivo de áudio extraído não foi criado")
                
            logger.info(f"Áudio extraído com sucesso: {audio_path}")
            return str(audio_path)
            
        except subprocess.TimeoutExpired:
            raise AudioTranscriptionException("Timeout ao extrair áudio do vídeo")
        except Exception as e:
            raise AudioTranscriptionException(f"Erro ao extrair áudio: {str(e)}")