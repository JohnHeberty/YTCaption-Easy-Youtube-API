"""
Cliente XTTS - Adapter para dublagem e clonagem de voz
Engine: Coqui TTS XTTS v2 (único engine suportado)
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

# MONKEY PATCH para auto-aceitar ToS do Coqui TTS
import builtins
_original_input = builtins.input
def _auto_accept_tos(prompt=""):
    """Auto-aceita ToS do Coqui TTS quando solicitado"""
    if ">" in prompt or "agree" in prompt.lower() or "tos" in prompt.lower():
        return "y"
    return _original_input(prompt)
builtins.input = _auto_accept_tos

from TTS.api import TTS

from .models import VoiceProfile, QualityProfile, XTTSParameters, RvcModel, RvcParameters
from .exceptions import InvalidAudioException, TTSEngineException
from .resilience import retry_async, with_timeout

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
        # progress_bar=False evita prompts interativos durante download
        self.tts = TTS(self.model_name, gpu=gpu, progress_bar=False)
        
        logger.info(f"XTTS model loaded: {self.model_name}")
        
        # RVC client (lazy load - só carrega quando enable_rvc=True)
        self.rvc_client = None
    
    def get_supported_languages(self) -> List[str]:
        """
        Retorna lista de linguagens suportadas
        
        Returns:
            Lista de códigos de linguagem (ex: ['en', 'pt', 'pt-BR', 'es', ...])
        """
        if hasattr(self.tts, 'languages'):
            return self.tts.languages
        # XTTS suporta estas linguagens - pt-BR usa engine 'pt'
        return ['pt', 'pt-BR', 'en', 'es', 'fr', 'de', 'it', 'pl', 'tr', 'ru', 'nl', 'cs', 'ar', 'zh-cn', 'hu', 'ko', 'ja', 'hi']
    
    def _load_rvc_client(self):
        """
        Carrega RVC client (lazy loading)
        
        Só carrega quando RVC é necessário, economizando 2-4GB VRAM.
        Carregamento é idempotente (múltiplas chamadas não recriam instância).
        """
        if self.rvc_client is not None:
            return  # Já carregado
        
        from .rvc_client import RvcClient
        
        logger.info("Initializing RVC client (lazy load)")
        self.rvc_client = RvcClient(
            device=self.device,
            fallback_to_cpu=True
        )
        logger.info("RVC client ready")
    
    @retry_async(max_attempts=3, delay_seconds=5, backoff_multiplier=2.0)
    async def generate_dubbing(
        self,
        text: str,
        language: str,
        voice_preset: Optional[str] = None,
        voice_profile: Optional[VoiceProfile] = None,
        quality_profile: QualityProfile = QualityProfile.BALANCED,
        temperature: Optional[float] = None,
        speed: Optional[float] = None,
        # === NOVOS PARÂMETROS RVC (Sprint 4) ===
        enable_rvc: bool = False,
        rvc_model: Optional[RvcModel] = None,
        rvc_params: Optional[RvcParameters] = None
    ) -> Tuple[bytes, float]:
        """
        Gera áudio de dubbing (com ou sem clonagem)
        
        Args:
            text: Texto para sintetizar
            language: Código da linguagem (ex: 'pt', 'en')
            voice_preset: Preset de voz genérica (se não usar clonagem)
            voice_profile: Perfil de voz clonada (opcional)
            quality_profile: Perfil de qualidade (BALANCED, EXPRESSIVE, STABLE)
            temperature: Controle de variação (0.1-1.0, sobrescreve quality_profile)
            speed: Velocidade de fala (0.5-2.0, sobrescreve quality_profile)
            enable_rvc: Se True, aplica conversão RVC após XTTS
            rvc_model: Modelo RVC a usar (obrigatório se enable_rvc=True)
            rvc_params: Parâmetros RVC (usa defaults se None)
        
        Returns:
            Tuple[bytes, float]: (áudio WAV em bytes, duração em segundos)
        
        Raises:
            ValueError: Se texto vazio ou linguagem inválida
            InvalidAudioException: Se erro ao gerar áudio
        """
        # Validações
        if not text or text.strip() == "":
            raise ValueError("Texto vazio ou inválido")
        
        # Normaliza pt-BR para pt ANTES da validação (XTTS usa 'pt' internamente)
        normalized_lang = 'pt' if language == 'pt-BR' else language
        
        supported_langs = self.get_supported_languages()
        if normalized_lang not in supported_langs:
            raise ValueError(f"Linguagem '{normalized_lang}' (original: '{language}') não suportada. Suportadas: {supported_langs}")
        
        # Obter parâmetros do perfil de qualidade
        params = XTTSParameters.from_profile(quality_profile)
        
        # Parâmetros customizados sobrescrevem perfil
        if temperature is not None:
            params.temperature = temperature
        if speed is not None:
            params.speed = speed
        
        logger.info(f"Generating dubbing with profile: {quality_profile.value}")
        logger.debug(f"XTTS params: temp={params.temperature}, "
                    f"rep_pen={params.repetition_penalty}, "
                    f"top_p={params.top_p}, top_k={params.top_k}")
        
        # Output temporário
        output_path = f"/tmp/xtts_output_{os.getpid()}_{datetime.now().timestamp()}.wav"
        
        try:
            # Run em thread separada (TTS é blocking)
            loop = asyncio.get_event_loop()
            
            # Configurar parâmetros do modelo XTTS antes da inferência
            # Nota: TTS API não expõe todos parâmetros, então modificamos o modelo subjacente
            # Armazena parâmetros originais para restaurar depois
            original_params = {}
            
            if hasattr(self.tts, 'synthesizer') and hasattr(self.tts.synthesizer, 'tts_model'):
                model = self.tts.synthesizer.tts_model
                if hasattr(model, 'inference'):
                    
                    # Mapeia parâmetros para atributos do modelo
                    param_mapping = {
                        'temperature': 'temperature',
                        'repetition_penalty': 'repetition_penalty',
                        'top_p': 'top_p',
                        'top_k': 'top_k',
                        'length_penalty': 'length_penalty',
                        'speed': 'speed'
                    }
                    
                    for param_name, attr_name in param_mapping.items():
                        if hasattr(model, attr_name):
                            original_params[attr_name] = getattr(model, attr_name)
                            new_value = getattr(params, param_name)
                            setattr(model, attr_name, new_value)
                            logger.debug(f"Set model.{attr_name} = {new_value}")
            
            if voice_profile is not None:
                # Dubbing com clonagem de voz
                speaker_wav = voice_profile.source_audio_path
                
                if not os.path.exists(speaker_wav):
                    raise InvalidAudioException(f"Áudio de referência não encontrado: {speaker_wav}")
                
                # Timeout de 300s (5min) para inferência XTTS
                await with_timeout(
                    loop.run_in_executor(
                        None,
                        lambda: self.tts.tts_to_file(
                            text=text,
                            file_path=output_path,
                            speaker_wav=speaker_wav,
                            language=normalized_lang,
                            split_sentences=params.enable_text_splitting,
                            speed=params.speed
                        )
                    ),
                    timeout_seconds=300
                )
            else:
                # Dubbing sem clonagem (voz genérica)
                # XTTS requer speaker_wav, então usa speaker default
                DEFAULT_SPEAKER = "/app/uploads/default_speaker.wav"
                
                if not os.path.exists(DEFAULT_SPEAKER):
                    raise TTSEngineException(
                        f"Default speaker not found: {DEFAULT_SPEAKER}. "
                        "Run scripts/create_default_speaker.py to create it."
                    )
                
                speaker_wav = DEFAULT_SPEAKER
                logger.info("Using default speaker for generic dubbing")
                
                # Gera com speaker padrão (timeout de 300s)
                await with_timeout(
                    loop.run_in_executor(
                        None,
                        lambda: self.tts.tts_to_file(
                            text=text,
                            file_path=output_path,
                            speaker_wav=speaker_wav,
                            language=normalized_lang,
                            split_sentences=params.enable_text_splitting,
                            speed=params.speed
                        )
                    ),
                    timeout_seconds=300
                )
            
            # Restaurar parâmetros originais do modelo
            if hasattr(self.tts, 'synthesizer') and hasattr(self.tts.synthesizer, 'tts_model'):
                model = self.tts.synthesizer.tts_model
                for attr_name, original_value in original_params.items():
                    setattr(model, attr_name, original_value)
            
            # Lê arquivo gerado
            audio_data, sr = sf.read(output_path)
            
            # === PONTO DE INSERÇÃO RVC (Sprint 4) ===
            # Se RVC habilitado, aplica conversão de voz
            if enable_rvc:
                if rvc_model is None:
                    logger.warning("RVC enabled but no model provided, skipping RVC conversion")
                else:
                    try:
                        logger.info(f"Applying RVC conversion with model: {rvc_model.name}")
                        
                        # Carrega RVC client (lazy)
                        self._load_rvc_client()
                        
                        # Usa parâmetros default se não fornecidos
                        if rvc_params is None:
                            rvc_params = RvcParameters()
                        
                        # Aplica conversão RVC
                        converted_audio, rvc_duration = await self.rvc_client.convert_audio(
                            audio_data=audio_data,
                            sample_rate=sr,
                            rvc_model=rvc_model,
                            params=rvc_params
                        )
                        
                        # Substitui áudio original pelo convertido
                        audio_data = converted_audio
                        logger.info(f"RVC conversion successful: {rvc_duration:.2f}s")
                        
                    except Exception as e:
                        # Fallback: retorna áudio XTTS puro se RVC falhar
                        logger.error(f"RVC conversion failed, using XTTS audio: {e}")
                        logger.warning("Falling back to XTTS-only audio")
                        # audio_data permanece inalterado (XTTS original)
            
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
    
    @retry_async(max_attempts=2, delay_seconds=3, backoff_multiplier=2.0)
    async def clone_voice(
        self,
        audio_path: str,
        language: str,
        voice_name: str,
        description: Optional[str] = None
    ) -> VoiceProfile:
        """
        Cria perfil de voz clonada a partir de áudio de referência
        
        Args:
            audio_path: Caminho do áudio de referência
            language: Código da linguagem (pt, pt-BR, en, es, etc.)
            voice_name: Nome do perfil de voz
            description: Descrição opcional
        
        Returns:
            VoiceProfile criado
        
        Raises:
            FileNotFoundError: Se áudio não encontrado
            InvalidAudioException: Se áudio inválido (<3s, formato inválido, etc.)
        """
        # Valida áudio existe
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Áudio de referência não encontrado: {audio_path}")
        
        # Normaliza pt-BR para pt ANTES da validação (XTTS usa 'pt' internamente)
        normalized_lang = 'pt' if language == 'pt-BR' else language
        
        # Valida linguagem
        supported_langs = self.get_supported_languages()
        if normalized_lang not in supported_langs:
            raise ValueError(f"Linguagem '{normalized_lang}' (original: '{language}') não suportada")
        
        try:
            # Carrega e valida áudio
            audio_data, sr = sf.read(audio_path)
            duration = len(audio_data) / sr
            
            # Valida duração mínima
            if duration < 3.0:
                raise InvalidAudioException(
                    f"Áudio muito curto: {duration:.2f}s (mínimo 3s para clonagem)"
                )
            
            # Cria VoiceProfile (XTTS usa WAV direto como referência)
            profile = VoiceProfile.create_new(
                name=voice_name,
                language=language,
                source_audio_path=audio_path,
                profile_path=audio_path,  # XTTS usa áudio direto, sem embedding separado
                description=description,
                duration=duration,
                sample_rate=sr,
                ttl_days=30
            )
            # XTTS não precisa de campos extras - usa source_audio_path diretamente
            
            logger.info(f"Voice profile created: {profile.id} ({voice_name})")
            
            return profile
            
        except sf.LibsndfileError as e:
            raise InvalidAudioException(f"Formato de áudio inválido: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating voice profile: {e}")
            raise InvalidAudioException(f"Erro ao criar perfil de voz: {str(e)}")
