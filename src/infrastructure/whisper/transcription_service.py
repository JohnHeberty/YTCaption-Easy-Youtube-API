"""
Whisper Transcription Service Implementation.
Implementação concreta da interface ITranscriptionService usando OpenAI Whisper.
"""
import asyncio
from pathlib import Path
from typing import Optional
import whisper
import torch
from loguru import logger

from src.domain.interfaces import ITranscriptionService
from src.domain.entities import Transcription, VideoFile
from src.domain.value_objects import TranscriptionSegment
from src.domain.exceptions import TranscriptionError


class WhisperTranscriptionService(ITranscriptionService):
    """
    Serviço de transcrição usando OpenAI Whisper.
    Extrai áudio de vídeos e gera transcrições com timestamps.
    """
    
    def __init__(
        self,
        model_name: str = "base",
        device: Optional[str] = None,
        compute_type: str = "float32"
    ):
        """
        Inicializa o serviço Whisper.
        
        Args:
            model_name: Nome do modelo Whisper (tiny, base, small, medium, large, turbo)
            device: Dispositivo para executar o modelo (cpu, cuda)
            compute_type: Tipo de computação (float32, float16, int8)
        """
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.compute_type = compute_type
        self._model: Optional[whisper.Whisper] = None
        
        logger.info(
            f"Whisper service initialized: model={model_name}, device={self.device}"
        )
    
    def _load_model(self) -> whisper.Whisper:
        """
        Carrega o modelo Whisper (lazy loading).
        
        Returns:
            whisper.Whisper: Modelo carregado
        """
        if self._model is None:
            logger.info(f"Loading Whisper model: {self.model_name}")
            try:
                self._model = whisper.load_model(self.model_name, device=self.device)
                logger.info("Model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {str(e)}")
                raise TranscriptionError(f"Failed to load model: {str(e)}")
        
        return self._model
    
    async def transcribe(
        self,
        video_file: VideoFile,
        language: str = "auto"
    ) -> Transcription:
        """
        Transcreve um arquivo de vídeo usando Whisper.
        
        Args:
            video_file: Arquivo de vídeo
            language: Código do idioma ou 'auto' para detecção automática
            
        Returns:
            Transcription: Transcrição completa com segmentos
            
        Raises:
            TranscriptionError: Se houver erro na transcrição
        """
        try:
            logger.info(f"Starting transcription: {video_file.file_path.name}")
            
            if not video_file.exists:
                raise TranscriptionError(f"Video file not found: {video_file.file_path}")
            
            # Carregar modelo
            model = self._load_model()
            
            # Preparar opções de transcrição
            transcribe_options = {
                'task': 'transcribe',  # Apenas transcrever, não traduzir
                'verbose': False,
                'fp16': self.device == "cuda",  # Usar FP16 apenas em GPU
            }
            
            # Definir idioma se não for auto
            if language != "auto" and language:
                transcribe_options['language'] = language
            
            # Executar transcrição em thread separada
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._transcribe_sync,
                model,
                str(video_file.file_path),
                transcribe_options
            )
            
            # Criar entidade Transcription
            transcription = Transcription()
            
            # Adicionar segmentos
            for segment_data in result.get('segments', []):
                segment = TranscriptionSegment(
                    text=segment_data['text'].strip(),
                    start=segment_data['start'],
                    end=segment_data['end']
                )
                transcription.add_segment(segment)
            
            # Definir idioma detectado
            transcription.language = result.get('language', 'unknown')
            
            logger.info(
                f"Transcription completed: {len(transcription.segments)} segments, "
                f"language={transcription.language}"
            )
            
            return transcription
            
        except TranscriptionError:
            raise
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            raise TranscriptionError(f"Failed to transcribe video: {str(e)}")
    
    def _transcribe_sync(
        self,
        model: whisper.Whisper,
        audio_path: str,
        options: dict
    ) -> dict:
        """
        Executa transcrição síncrona.
        
        Args:
            model: Modelo Whisper
            audio_path: Caminho do arquivo de áudio
            options: Opções de transcrição
            
        Returns:
            dict: Resultado da transcrição
        """
        return model.transcribe(audio_path, **options)
    
    async def detect_language(self, video_file: VideoFile) -> str:
        """
        Detecta o idioma do áudio usando Whisper.
        
        Args:
            video_file: Arquivo de vídeo
            
        Returns:
            str: Código do idioma detectado
            
        Raises:
            TranscriptionError: Se houver erro na detecção
        """
        try:
            logger.info(f"Detecting language: {video_file.file_path.name}")
            
            if not video_file.exists:
                raise TranscriptionError(f"Video file not found: {video_file.file_path}")
            
            # Carregar modelo
            model = self._load_model()
            
            # Executar detecção em thread separada
            loop = asyncio.get_event_loop()
            language = await loop.run_in_executor(
                None,
                self._detect_language_sync,
                model,
                str(video_file.file_path)
            )
            
            logger.info(f"Language detected: {language}")
            return language
            
        except TranscriptionError:
            raise
        except Exception as e:
            logger.error(f"Language detection failed: {str(e)}")
            raise TranscriptionError(f"Failed to detect language: {str(e)}")
    
    def _detect_language_sync(self, model: whisper.Whisper, audio_path: str) -> str:
        """
        Detecta idioma de forma síncrona.
        
        Args:
            model: Modelo Whisper
            audio_path: Caminho do arquivo
            
        Returns:
            str: Código do idioma
        """
        # Carregar áudio e detectar idioma
        audio = whisper.load_audio(audio_path)
        audio = whisper.pad_or_trim(audio)
        
        # Criar mel spectrogram
        mel = whisper.log_mel_spectrogram(audio, n_mels=model.dims.n_mels).to(model.device)
        
        # Detectar idioma
        _, probs = model.detect_language(mel)
        detected_language = max(probs, key=probs.get)
        
        return detected_language
    
    def __del__(self):
        """Limpa recursos ao destruir o objeto."""
        if self._model is not None:
            del self._model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
