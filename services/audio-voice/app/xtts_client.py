"""
Cliente XTTS - Adapter para dublagem e clonagem de voz
Substituição completa do F5-TTS
"""
import logging
import os
import torch
import torchaudio
import soundfile as sf
import io
import asyncio
from pathlib import Path
from typing import Optional, Tuple, List, Union
from datetime import datetime, timedelta

from TTS.api import TTS

from .models import VoiceProfile
from .exceptions import InvalidAudioException

logger = logging.getLogger(__name__)


class XTTSClient:
    """Cliente XTTS para dublagem e clonagem de voz"""
    
    def __init__(
        self, 
        device: Optional[str] = None,
        fallback_to_cpu: bool = True,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    ):
        """
        Inicializa cliente XTTS
        
        Args:
            device: 'cpu' ou 'cuda' (auto-detecta se None)
            fallback_to_cpu: Se True, usa CPU quando CUDA não disponível
            model_name: Nome do modelo XTTS
        """
        # Device detection
        if device is None:
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
            if device == 'cuda' and not torch.cuda.is_available():
                if fallback_to_cpu:
                    logger.warning("CUDA requested but not available, falling back to CPU")
                    self.device = 'cpu'
                else:
                    raise RuntimeError("CUDA requested but not available")
        
        logger.info(f"Initializing XTTS client on device: {self.device}")
        
        # Model configuration
        self.model_name = model_name
        
        # XTTS parameters
        self.temperature = 0.7
        self.repetition_penalty = 5.0
        self.length_penalty = 1.0
        self.top_k = 50
        self.top_p = 0.85
        self.speed = 1.0
        self.enable_text_splitting = True
        
        # Sample rate (XTTS v2 usa 24kHz)
        self.sample_rate = 24000
        
        # Load model
        gpu = (self.device == 'cuda')
        self.tts = TTS(self.model_name, gpu=gpu)
        
        logger.info(f"XTTS model loaded: {self.model_name}")
    
    def get_supported_languages(self) -> List[str]:
        """
        Retorna lista de linguagens suportadas
        
        Returns:
            Lista de códigos de linguagem (ex: ['en', 'pt', 'es', ...])
        """
        if hasattr(self.tts, 'languages'):
            return self.tts.languages
        return ['pt', 'en', 'es', 'fr', 'de', 'it', 'pl', 'tr', 'ru', 'nl', 'cs', 'ar', 'zh-cn', 'hu', 'ko', 'ja', 'hi']
    
    async def generate_dubbing(
        self,
        text: str,
        language: str,
        voice_preset: Optional[str] = None,
        voice_profile: Optional[VoiceProfile] = None,
        temperature: Optional[float] = None,
        speed: Optional[float] = None
    ) -> Tuple[bytes, float]:
        """
        Gera áudio de dubbing (com ou sem clonagem)
        
        Args:
            text: Texto para sintetizar
            language: Código da linguagem (ex: 'pt', 'en')
            voice_preset: Preset de voz genérica (se não usar clonagem)
            voice_profile: Perfil de voz clonada (opcional)
            temperature: Controle de variação (0.1-1.0, padrão 0.7)
            speed: Velocidade de fala (0.5-2.0, padrão 1.0)
        
        Returns:
            Tuple[bytes, float]: (áudio WAV em bytes, duração em segundos)
        
        Raises:
            ValueError: Se texto vazio ou linguagem inválida
            InvalidAudioException: Se erro ao gerar áudio
        """
        # Validações
        if not text or text.strip() == "":
            raise ValueError("Texto vazio ou inválido")
        
        supported_langs = self.get_supported_languages()
        if language not in supported_langs:
            raise ValueError(f"Linguagem '{language}' não suportada. Suportadas: {supported_langs}")
        
        # Parâmetros
        temp = temperature if temperature is not None else self.temperature
        spd = speed if speed is not None else self.speed
        
        # Output temporário
        output_path = f"/tmp/xtts_output_{os.getpid()}_{datetime.now().timestamp()}.wav"
        
        try:
            # Run em thread separada (TTS é blocking)
            loop = asyncio.get_event_loop()
            
            if voice_profile is not None:
                # Dubbing com clonagem de voz
                speaker_wav = voice_profile.reference_audio_path
                
                if not os.path.exists(speaker_wav):
                    raise InvalidAudioException(f"Áudio de referência não encontrado: {speaker_wav}")
                
                await loop.run_in_executor(
                    None,
                    lambda: self.tts.tts_to_file(
                        text=text,
                        file_path=output_path,
                        speaker_wav=speaker_wav,
                        language=language,
                        split_sentences=self.enable_text_splitting
                    )
                )
            else:
                # Dubbing sem clonagem (voz genérica)
                # XTTS usa clonagem, então criamos voz genérica temporária
                # Usa áudio de referência padrão se disponível
                default_speaker = "/app/uploads/clone_20251126031159965237.ogg"
                
                if os.path.exists(default_speaker):
                    # Usa speaker de referência padrão
                    await loop.run_in_executor(
                        None,
                        lambda: self.tts.tts_to_file(
                            text=text,
                            file_path=output_path,
                            speaker_wav=default_speaker,
                            language=language,
                            split_sentences=self.enable_text_splitting
                        )
                    )
                else:
                    # Fallback: gera sem speaker (pode falhar em alguns modelos)
                    raise InvalidAudioException(
                        "XTTS requer speaker_wav para síntese. "
                        "Forneça voice_profile ou configure speaker padrão."
                    )
            
            # Lê arquivo gerado
            audio_data, sr = sf.read(output_path)
            
            # Converte para bytes (WAV format)
            buffer = io.BytesIO()
            sf.write(buffer, audio_data, sr, format='WAV')
            audio_bytes = buffer.getvalue()
            
            # Calcula duração
            duration = len(audio_data) / sr
            
            # Cleanup
            if os.path.exists(output_path):
                os.remove(output_path)
            
            logger.info(f"Generated dubbing: {duration:.2f}s, {len(audio_bytes)} bytes")
            
            return audio_bytes, duration
            
        except Exception as e:
            # Cleanup em caso de erro
            if os.path.exists(output_path):
                os.remove(output_path)
            
            logger.error(f"Error generating dubbing: {e}")
            raise InvalidAudioException(f"Erro ao gerar áudio: {str(e)}")
    
    async def clone_voice(
        self,
        audio_path: str,
        language: str,
        voice_name: str,
        description: Optional[str] = None,
        reference_text: Optional[str] = None,
        temperature: Optional[float] = None,
        repetition_penalty: Optional[float] = None
    ) -> VoiceProfile:
        """
        Cria perfil de voz clonada a partir de áudio de referência
        
        Args:
            audio_path: Caminho do áudio de referência
            language: Código da linguagem
            voice_name: Nome do perfil de voz
            description: Descrição opcional
            reference_text: Transcrição do áudio (opcional, melhora qualidade)
            temperature: Controle de variação
            repetition_penalty: Penalidade para repetições
        
        Returns:
            VoiceProfile criado
        
        Raises:
            FileNotFoundError: Se áudio não encontrado
            InvalidAudioException: Se áudio inválido (<3s, formato inválido, etc.)
        """
        # Valida áudio existe
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Áudio de referência não encontrado: {audio_path}")
        
        # Valida linguagem
        supported_langs = self.get_supported_languages()
        if language not in supported_langs:
            raise ValueError(f"Linguagem '{language}' não suportada")
        
        try:
            # Carrega e valida áudio
            audio_data, sr = sf.read(audio_path)
            duration = len(audio_data) / sr
            
            # Valida duração mínima
            if duration < 3.0:
                raise InvalidAudioException(
                    f"Áudio muito curto: {duration:.2f}s (mínimo 3s para clonagem)"
                )
            
            # Cria VoiceProfile
            profile = VoiceProfile.create_new(
                name=voice_name,
                language=language,
                source_audio_path=audio_path,
                profile_path=audio_path,  # XTTS usa áudio direto
                description=description,
                duration=duration,
                sample_rate=sr,
                ttl_days=30
            )
            
            # Adiciona campos específicos XTTS
            profile.reference_audio_path = audio_path
            profile.reference_text = reference_text
            
            logger.info(f"Voice profile created: {profile.id} ({voice_name})")
            
            return profile
            
        except sf.LibsndfileError as e:
            raise InvalidAudioException(f"Formato de áudio inválido: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating voice profile: {e}")
            raise InvalidAudioException(f"Erro ao criar perfil de voz: {str(e)}")
