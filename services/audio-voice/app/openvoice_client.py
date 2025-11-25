"""
Cliente OpenVoice - Adapter para dublagem e clonagem de voz

IMPORTANTE: Este é um ADAPTER/MOCK para OpenVoice.
A implementação real depende da instalação e API do OpenVoice.

Referência: https://github.com/myshell-ai/OpenVoice

Para integração completa:
1. Instalar OpenVoice: pip install git+https://github.com/myshell-ai/OpenVoice.git
2. Baixar modelos pré-treinados
3. Ajustar imports e chamadas conforme API OpenVoice
"""
import logging
import os
import torch
import torchaudio
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import pickle

from .models import VoiceProfile
from .config import get_settings
from .exceptions import OpenVoiceException, InvalidAudioException

logger = logging.getLogger(__name__)

# ===== SIMULAÇÃO DE IMPORTS OPENVOICE =====
# Em produção, substituir por imports reais:
# from openvoice import se_extractor
# from openvoice.api import ToneColorConverter, BaseSpeakerTTS


class MockOpenVoiceModel:
    """Mock do modelo OpenVoice para desenvolvimento/teste"""
    def __init__(self, device='cpu'):
        self.device = device
        logger.warning("Using MOCK OpenVoice model - not production ready!")
    
    def tts(self, text: str, speaker: str, language: str, **kwargs) -> np.ndarray:
        """Simula geração de TTS que SONA como fala humana"""
        logger.info(f"🎵 MOCK TTS: '{text[:50]}...' speaker={speaker} lang={language}")
        
        sample_rate = 24000
        
        # Parâmetros de voz baseados no speaker
        if 'female' in speaker.lower() or 'woman' in speaker.lower():
            base_pitch = 220  # Lá3 (voz feminina)
            pitch_variation = 50
            logger.info(f"  Using FEMALE voice (base pitch: {base_pitch} Hz)")
        else:
            base_pitch = 130  # Dó3 (voz masculina)
            pitch_variation = 30
            logger.info(f"  Using MALE voice (base pitch: {base_pitch} Hz)")
        
        # Simula palavras/sílabas do texto
        words = text.split()
        logger.info(f"  Text: {len(text)} chars, {len(words)} words")
        logger.info(f"  🔊 Starting syllable-by-syllable generation:")
        
        audio_segments = []
        total_syllables = 0
        
        for word_idx, word in enumerate(words):
            # Cada palavra tem 1-4 sílabas (estimativa)
            num_syllables = max(1, min(4, len(word) // 2))
            total_syllables += num_syllables
            
            if word_idx < 3:
                logger.info(f"     Word '{word}': {num_syllables} syllables")
            
            for syllable_idx in range(num_syllables):
                # Duração da sílaba: 0.08-0.15s (velocidade natural de fala)
                syllable_duration = 0.08 + np.random.rand() * 0.07
                syllable_samples = int(sample_rate * syllable_duration)
                
                # Pitch varia por sílaba (prosódia natural)
                pitch_offset = (np.random.rand() - 0.5) * pitch_variation
                syllable_pitch = base_pitch + pitch_offset
                
                if word_idx < 3:
                    logger.info(f"       Syl {syllable_idx+1}: pitch={syllable_pitch:.1f}Hz, dur={syllable_duration*1000:.0f}ms")
                
                # Gera sílaba com MÚLTIPLAS FREQUÊNCIAS (sons humanos)
                t = np.arange(syllable_samples) / sample_rate
                
                # Fundamental (pitch da voz) - REDUZIDO para dar espaço aos formantes
                fundamental = 0.25 * np.sin(2 * np.pi * syllable_pitch * t)
                
                # Harmônicos (timbre humano) - REDUZIDOS
                harmonic2 = 0.12 * np.sin(2 * np.pi * syllable_pitch * 2 * t)
                harmonic3 = 0.06 * np.sin(2 * np.pi * syllable_pitch * 3 * t)
                harmonic4 = 0.03 * np.sin(2 * np.pi * syllable_pitch * 4 * t)
                
                # Formantes (ressonâncias da voz - variam por vogal simulada) - AUMENTADOS!
                formant1_freq = 700 + (syllable_idx % 3) * 200  # ~700-1100 Hz
                formant2_freq = 1200 + (syllable_idx % 3) * 300  # ~1200-1800 Hz
                formant1 = 0.6 * np.sin(2 * np.pi * formant1_freq * t)  # DOMINANTE!
                formant2 = 0.4 * np.sin(2 * np.pi * formant2_freq * t)  # FORTE!
                
                # Ruído de respiração (aspiration) - simula naturalidade
                breath_noise = 0.015 * np.random.randn(syllable_samples)
                
                # Vibrato leve (modulação natural da voz)
                vibrato_freq = 5.5  # 5.5 Hz
                vibrato_depth = 0.025  # 2.5% de variação
                vibrato = 1 + vibrato_depth * np.sin(2 * np.pi * vibrato_freq * t)
                
                if word_idx < 3:
                    logger.info(f"         Harmonics: F={syllable_pitch:.0f}Hz@0.25, 2F={syllable_pitch*2:.0f}Hz@0.12, 3F={syllable_pitch*3:.0f}Hz@0.06")
                    logger.info(f"         Formants: F1={formant1_freq:.0f}Hz@0.6, F2={formant2_freq:.0f}Hz@0.4 [DOMINANTES]")
                    logger.info(f"         Breath noise: 0.015, Vibrato: {vibrato_freq}Hz @ {vibrato_depth*100:.1f}%")
                
                # Combina todas as frequências
                syllable = fundamental + harmonic2 + harmonic3 + harmonic4 + formant1 + formant2 + breath_noise
                
                # Aplica vibrato (modulação natural)
                syllable *= vibrato
                
                # Envelope ADSR mais natural (Attack, Decay, Sustain, Release)
                attack = int(syllable_samples * 0.10)   # 10% - ataque mais suave
                decay = int(syllable_samples * 0.15)    # 15% - decay para sustain
                sustain_end = int(syllable_samples * 0.65)  # 65% - sustain
                release = syllable_samples - sustain_end    # 10% - release rápido
                
                envelope = np.ones(syllable_samples)
                
                # Attack: 0.2 → 1.0 (mais suave)
                if attack > 0:
                    envelope[:attack] = np.linspace(0.2, 1.0, attack)
                
                # Decay: 1.0 → 0.85 (leve queda)
                if decay > 0 and attack + decay < syllable_samples:
                    envelope[attack:attack+decay] = np.linspace(1.0, 0.85, decay)
                
                # Sustain: mantém em 0.85
                if sustain_end > attack + decay:
                    envelope[attack+decay:sustain_end] = 0.85
                
                # Release: 0.85 → 0.05 (fade suave)
                if release > 0:
                    envelope[sustain_end:] = np.linspace(0.85, 0.05, release)
                
                syllable *= envelope
                
                # Amplitude varia (sílabas tônicas vs átonas)
                if syllable_idx == 0 or syllable_idx % 2 == 0:
                    amplitude = 0.7  # Sílaba tônica
                else:
                    amplitude = 0.5  # Sílaba átona
                
                syllable *= amplitude
                
                # Análise da sílaba
                syl_rms = np.sqrt(np.mean(syllable**2))
                syl_peak = np.abs(syllable).max()
                
                if word_idx < 3:
                    logger.info(f"         Result: RMS={syl_rms:.4f}, peak={syl_peak:.4f}, tonic={syllable_idx==0 or syllable_idx%2==0}")
                
                audio_segments.append(syllable)
                
                # Micro-pausa entre sílabas (20-40ms)
                if syllable_idx < num_syllables - 1:
                    pause_samples = int(sample_rate * (0.02 + np.random.rand() * 0.02))
                    audio_segments.append(np.zeros(pause_samples))
            
            # PAUSA entre palavras (80-150ms)
            if word_idx < len(words) - 1:
                pause_duration = 0.08 + np.random.rand() * 0.07
                pause_samples = int(sample_rate * pause_duration)
                audio_segments.append(np.zeros(pause_samples))
        
        # Concatena todos os segmentos
        audio = np.concatenate(audio_segments)
        
        logger.info(f"  Total syllables generated: {total_syllables}")
        logger.info(f"  Total audio segments: {len(audio_segments)}")
        
        # Normalização suave para volume natural de fala (60%)
        max_val = np.abs(audio).max()
        if max_val > 0:
            audio = audio / max_val * 0.6  # Mais conservador para evitar distorção
        
        # Soft clipping para suavizar picos remanescentes
        audio = np.tanh(audio * 1.2) * 0.8
        
        audio_data = audio.astype(np.float32)
        
        # Logs detalhados
        duration = len(audio_data) / sample_rate
        rms = np.sqrt(np.mean(audio_data**2))
        non_zero = np.count_nonzero(np.abs(audio_data) > 0.01)
        
        # Análise FFT para detectar frequências dominantes
        fft_samples = min(sample_rate, len(audio_data))  # Primeiro segundo
        fft = np.fft.fft(audio_data[:fft_samples])
        freqs = np.fft.fftfreq(fft_samples, 1/sample_rate)
        magnitudes = np.abs(fft)
        
        # Top 5 frequências
        positive_mask = freqs > 0
        top_indices = np.argsort(magnitudes[positive_mask])[-5:][::-1]
        top_freqs = freqs[positive_mask][top_indices]
        top_mags = magnitudes[positive_mask][top_indices]
        
        logger.info(f"🎵 Audio generated:")
        logger.info(f"  - Duration: {duration:.2f}s ({len(audio_data)} samples)")
        logger.info(f"  - Amplitude: [{audio_data.min():.3f}, {audio_data.max():.3f}]")
        logger.info(f"  - RMS: {rms:.3f}")
        logger.info(f"  - Non-zero: {non_zero}/{len(audio_data)} ({non_zero/len(audio_data)*100:.1f}%)")
        logger.info(f"  - Top frequencies (first 1s):")
        for freq, mag in zip(top_freqs, top_mags):
            logger.info(f"      {freq:.1f} Hz (magnitude: {mag:.0f})")
        logger.info(f"  - First 10 samples: {audio_data[:10]}")
        logger.info(f"  - Last 10 samples: {audio_data[-10:]}")
        
        # Análise de variação temporal
        chunks = np.array_split(audio_data, 10)
        chunk_rms = [np.sqrt(np.mean(c**2)) for c in chunks]
        logger.info(f"  - RMS by chunk (10 chunks): {[f'{x:.3f}' for x in chunk_rms]}")
        
        return audio_data
    
    def tts_with_voice(self, text: str, voice_embedding: np.ndarray, **kwargs) -> np.ndarray:
        """Simula TTS com voz clonada (áudio audível como fala)"""
        logger.info(f"🎵 MOCK TTS with cloned voice: '{text[:50]}...'")
        
        sample_rate = 24000
        
        # Usa embedding para variar pitch (simula características da voz clonada)
        if voice_embedding is not None and len(voice_embedding) > 0:
            # Extrai "características" do embedding
            embedding_factor = (voice_embedding[0] % 1.0)  # 0.0 a 1.0
            
            # Mapeia para range de pitch (100-300 Hz)
            base_pitch = 100 + embedding_factor * 200
            pitch_variation = 20 + embedding_factor * 30
            
            logger.info(f"  Cloned voice pitch: {base_pitch:.1f} Hz (from embedding)")
        else:
            base_pitch = 180
            pitch_variation = 40
            logger.info(f"  Default pitch: {base_pitch} Hz")
        
        # Segmentação em sílabas (mesmo approach do tts)
        words = text.split()
        syllable_count = sum(len(word) // 3 + 1 for word in words)  # Estimativa
        syllable_duration = 0.15  # 150ms por sílaba
        pause_duration = 0.05     # 50ms entre sílabas
        
        logger.info(f"  Syllable structure: {syllable_count} syllables, {syllable_duration}s each")
        
        segments = []
        
        logger.info(f"  🔊 Starting syllable generation:")
        logger.info(f"     - Total syllables: {syllable_count}")
        logger.info(f"     - Base pitch: {base_pitch:.1f} Hz")
        logger.info(f"     - Pitch variation: ±{pitch_variation:.1f} Hz")
        
        for i in range(syllable_count):
            # Pitch variável (simula prosódia)
            syllable_pitch = base_pitch + np.random.uniform(-pitch_variation, pitch_variation)
            
            # Amplitude variável (tônica vs átona)
            is_tonic = (i % 3 == 0)  # A cada 3 sílabas uma é tônica
            amplitude = 0.7 if is_tonic else 0.5
            
            if i < 3 or i >= syllable_count - 3:
                logger.debug(f"     [Syl {i+1:02d}] pitch={syllable_pitch:.1f}Hz, amp={amplitude:.2f}, tonic={is_tonic}")
            
            # Gera segmento de áudio para esta sílaba
            n_samples = int(syllable_duration * sample_rate)
            t = np.linspace(0, syllable_duration, n_samples, False)
            
            # Síntese com harmônicos - AMPLITUDES REBALANCEADAS
            syllable_audio = np.zeros(n_samples)
            
            # Fundamental + harmônicos - REDUZIDOS
            fundamental = 0.25 * np.sin(2 * np.pi * syllable_pitch * t)
            harmonic2 = 0.12 * np.sin(2 * np.pi * syllable_pitch * 2 * t)
            harmonic3 = 0.06 * np.sin(2 * np.pi * syllable_pitch * 3 * t)
            harmonic4 = 0.03 * np.sin(2 * np.pi * syllable_pitch * 4 * t)
            
            if i < 3 or i >= syllable_count - 3:
                logger.debug(f"        Harmonics: F={syllable_pitch:.0f}Hz@0.25, 2F={syllable_pitch*2:.0f}Hz@0.12, 3F={syllable_pitch*3:.0f}Hz@0.06")
            
            # Formantes - AUMENTADOS!
            formant1_freq = 700 + np.random.uniform(0, 400)   # 700-1100 Hz
            formant2_freq = 1200 + np.random.uniform(0, 600)  # 1200-1800 Hz
            formant1 = 0.6 * np.sin(2 * np.pi * formant1_freq * t)
            formant2 = 0.4 * np.sin(2 * np.pi * formant2_freq * t)
            
            # Ruído de respiração
            breath_noise = 0.015 * np.random.randn(n_samples)
            
            # Vibrato
            vibrato_freq = 5.5
            vibrato_depth = 0.025
            vibrato = 1 + vibrato_depth * np.sin(2 * np.pi * vibrato_freq * t)
            
            if i < 3 or i >= syllable_count - 3:
                logger.debug(f"        Formants: F1={formant1_freq:.0f}Hz@0.6, F2={formant2_freq:.0f}Hz@0.4 [DOMINANTES]")
            
            # Combina todas as frequências
            syllable_audio = fundamental + harmonic2 + harmonic3 + harmonic4 + formant1 + formant2 + breath_noise
            
            # Aplica vibrato
            syllable_audio *= vibrato
            
            # Envelope ADSR mais natural
            attack = int(0.015 * sample_rate)   # 15ms - ataque mais suave
            decay = int(0.025 * sample_rate)    # 25ms
            sustain_end = int(n_samples * 0.65)  # 65%
            release = n_samples - sustain_end    # Resto
            
            envelope = np.ones(n_samples)
            
            # Attack: 0.2 → 1.0
            if attack > 0:
                envelope[:attack] = np.linspace(0.2, 1.0, attack)
            
            # Decay: 1.0 → 0.85
            if decay > 0 and attack + decay < n_samples:
                envelope[attack:attack+decay] = np.linspace(1.0, 0.85, decay)
            
            # Sustain: mantém em 0.85
            if sustain_end > attack + decay:
                envelope[attack+decay:sustain_end] = 0.85
            
            # Release: 0.85 → 0.05
            if release > 0:
                envelope[sustain_end:] = np.linspace(0.85, 0.05, release)
            
            syllable_audio *= envelope
            
            # Análise da sílaba
            syl_rms = np.sqrt(np.mean(syllable_audio**2))
            syl_peak = np.abs(syllable_audio).max()
            
            if i < 3 or i >= syllable_count - 3:
                logger.debug(f"        Envelope: attack={attack}, decay={decay}, release={release}")
                logger.debug(f"        Result: RMS={syl_rms:.4f}, peak={syl_peak:.4f}, samples={len(syllable_audio)}")
            
            segments.append(syllable_audio)
            
            # Pausa entre sílabas
            if i < syllable_count - 1:
                pause_samples = int(pause_duration * sample_rate)
                pause = np.zeros(pause_samples)
                segments.append(pause)
                if i < 2:
                    logger.debug(f"        Added pause: {pause_samples} samples ({pause_duration*1000:.0f}ms)")
        
        # Concatena todas as sílabas
        audio_data = np.concatenate(segments)
        
        # Normalização suave (60% + soft clipping)
        max_val = np.abs(audio_data).max()
        if max_val > 0:
            audio_data = audio_data / max_val * 0.6
        
        # Soft clipping para suavizar picos
        audio_data = np.tanh(audio_data * 1.2) * 0.8
        
        # Logs detalhados
        duration = len(audio_data) / sample_rate
        rms = np.sqrt(np.mean(audio_data**2))
        non_zero = np.count_nonzero(np.abs(audio_data) > 0.01)
        
        # Análise FFT
        fft_samples = min(sample_rate, len(audio_data))
        fft = np.fft.fft(audio_data[:fft_samples])
        freqs = np.fft.fftfreq(fft_samples, 1/sample_rate)
        magnitudes = np.abs(fft)
        
        positive_mask = freqs > 0
        top_indices = np.argsort(magnitudes[positive_mask])[-5:][::-1]
        top_freqs = freqs[positive_mask][top_indices]
        top_mags = magnitudes[positive_mask][top_indices]
        
        logger.info(f"🎵 Cloned audio generated:")
        logger.info(f"  - Duration: {duration:.2f}s ({len(audio_data)} samples)")
        logger.info(f"  - Amplitude: [{audio_data.min():.3f}, {audio_data.max():.3f}]")
        logger.info(f"  - RMS: {rms:.3f}")
        logger.info(f"  - Non-zero: {non_zero}/{len(audio_data)} ({non_zero/len(audio_data)*100:.1f}%)")
        logger.info(f"  - Base pitch: {base_pitch:.1f} Hz")
        logger.info(f"  - Top frequencies (first 1s):")
        for freq, mag in zip(top_freqs, top_mags):
            logger.info(f"      {freq:.1f} Hz (magnitude: {mag:.0f})")
        logger.info(f"  - First 10 samples: {audio_data[:10]}")
        logger.info(f"  - Last 10 samples: {audio_data[-10:]}")
        
        chunks = np.array_split(audio_data, 10)
        chunk_rms = [np.sqrt(np.mean(c**2)) for c in chunks]
        logger.info(f"  - RMS by chunk (10 chunks): {[f'{x:.3f}' for x in chunk_rms]}")
        
        return audio_data
    
    def extract_voice_embedding(self, audio_path: str, language: str) -> np.ndarray:
        """Simula extração de embedding de voz"""
        logger.info(f"MOCK extract voice embedding from {audio_path}")
        
        # Em produção real, analisaria o áudio para extrair características
        # Aqui geramos embedding determinístico baseado no path para consistência
        import hashlib
        path_hash = hashlib.md5(audio_path.encode()).hexdigest()
        seed = int(path_hash[:8], 16)
        np.random.seed(seed)
        
        # Retorna embedding de exemplo (vetor de 256 dimensões)
        embedding = np.random.randn(256).astype(np.float32)
        
        # Normaliza para melhor estabilidade
        embedding = embedding / np.linalg.norm(embedding)
        
        logger.debug(f"Generated embedding: shape={embedding.shape}, norm={np.linalg.norm(embedding):.3f}")
        
        return embedding


class OpenVoiceClient:
    """
    Cliente para OpenVoice - Dublagem e Clonagem de Voz
    
    Responsabilidades:
    - Inicializar modelos OpenVoice
    - Gerar áudio dublado a partir de texto
    - Clonar vozes a partir de amostras
    - Sintetizar fala com vozes clonadas
    """
    
    def __init__(self, device: Optional[str] = None):
        """
        Inicializa cliente OpenVoice
        
        Args:
            device: 'cpu' ou 'cuda' (auto-detecta se None)
        """
        self.settings = get_settings()
        openvoice_config = self.settings['openvoice']
        
        # Device
        if device is None:
            self.device = openvoice_config['device']
            if self.device == 'cuda' and not torch.cuda.is_available():
                logger.warning("CUDA not available, falling back to CPU")
                self.device = 'cpu'
        else:
            self.device = device
        
        logger.info(f"Initializing OpenVoice client on device: {self.device}")
        
        # Paths
        self.model_path = Path(openvoice_config['model_path'])
        self.model_path.mkdir(exist_ok=True, parents=True)
        
        # Modelos (carregados sob demanda)
        self._tts_model = None
        self._converter_model = None
        self._models_loaded = False
        
        # Parâmetros padrão
        self.sample_rate = openvoice_config['sample_rate']
        self.default_speed = openvoice_config['default_speed']
        self.default_pitch = openvoice_config['default_pitch']
        
        # Preload se configurado
        if openvoice_config['preload_models']:
            try:
                self._load_models()
            except Exception as e:
                logger.error(f"Failed to preload models: {e}")
    
    def _load_models(self):
        """Carrega modelos OpenVoice"""
        if self._models_loaded:
            return
        
        try:
            logger.info("Loading OpenVoice models...")
            
            # ===== PRODUÇÃO: Substituir por código real =====
            # from openvoice import se_extractor
            # from openvoice.api import ToneColorConverter, BaseSpeakerTTS
            # 
            # self._tts_model = BaseSpeakerTTS(
            #     model_path=str(self.model_path / "base_speakers"),
            #     device=self.device
            # )
            # 
            # self._converter_model = ToneColorConverter(
            #     model_path=str(self.model_path / "converter"),
            #     device=self.device
            # )
            # ===== FIM PRODUÇÃO =====
            
            # MOCK para desenvolvimento
            self._tts_model = MockOpenVoiceModel(device=self.device)
            self._converter_model = MockOpenVoiceModel(device=self.device)
            
            self._models_loaded = True
            logger.info("✅ OpenVoice models loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load OpenVoice models: {e}")
            raise OpenVoiceException(f"Model loading failed: {str(e)}")
    
    def unload_models(self):
        """Descarrega modelos da memória (economia de recursos)"""
        if self._models_loaded:
            self._tts_model = None
            self._converter_model = None
            self._models_loaded = False
            
            # Limpa cache CUDA se aplicável
            if self.device == 'cuda':
                torch.cuda.empty_cache()
            
            logger.info("OpenVoice models unloaded")
    
    async def generate_dubbing(
        self,
        text: str,
        language: str,
        voice_preset: Optional[str] = None,
        voice_profile: Optional[VoiceProfile] = None,
        speed: float = 1.0,
        pitch: float = 1.0
    ) -> Tuple[bytes, float]:
        """
        Gera áudio dublado a partir de texto
        
        Args:
            text: Texto para dublar
            language: Idioma de síntese
            voice_preset: Voz genérica (ex: 'female_generic')
            voice_profile: Perfil de voz clonada (alternativa a voice_preset)
            speed: Velocidade da fala (0.5-2.0)
            pitch: Tom de voz (0.5-2.0)
        
        Returns:
            (audio_bytes, duration): Bytes do áudio WAV e duração em segundos
        """
        try:
            self._load_models()
            
            logger.info(f"🎙️ === GENERATE_DUBBING START ===")
            logger.info(f"  Text: '{text}'")
            logger.info(f"  Text length: {len(text)} chars")
            logger.info(f"  Language: {language}")
            logger.info(f"  Voice preset: {voice_preset}")
            logger.info(f"  Voice profile: {voice_profile.id if voice_profile else 'None'}")
            logger.info(f"  Speed: {speed}, Pitch: {pitch}")
            
            # Valida parâmetros
            if not text or len(text.strip()) == 0:
                raise InvalidAudioException("Text cannot be empty")
            
            # Modo: voz genérica ou clonada
            if voice_profile:
                # Usa voz clonada
                logger.info(f"  → Using CLONED voice: {voice_profile.id}")
                audio_data = await self._synthesize_with_cloned_voice(
                    text=text,
                    voice_profile=voice_profile,
                    speed=speed,
                    pitch=pitch
                )
            else:
                # Usa voz genérica
                speaker = voice_preset or 'default_female'
                logger.info(f"  → Using PRESET voice: {speaker}")
                audio_data = await self._synthesize_with_preset(
                    text=text,
                    speaker=speaker,
                    language=language,
                    speed=speed,
                    pitch=pitch
                )
            
            logger.info(f"  Audio data received: {len(audio_data)} samples, dtype={audio_data.dtype}")
            logger.info(f"  Audio range: [{audio_data.min():.6f}, {audio_data.max():.6f}]")
            logger.info(f"  Audio RMS: {np.sqrt(np.mean(audio_data**2)):.6f}")
            
            # Converte para WAV bytes
            logger.info(f"  Converting to WAV bytes...")
            audio_bytes, duration = self._audio_to_wav_bytes(audio_data, self.sample_rate)
            
            logger.info(f"✅ Dubbing generated: {duration:.2f}s, {len(audio_bytes)/(1024*1024):.2f}MB")
            logger.info(f"🎙️ === GENERATE_DUBBING END ===")
            
            return audio_bytes, duration
            
        except Exception as e:
            logger.error(f"Error generating dubbing: {e}")
            raise OpenVoiceException(f"Dubbing generation failed: {str(e)}")
    
    async def _synthesize_with_preset(
        self,
        text: str,
        speaker: str,
        language: str,
        speed: float,
        pitch: float
    ) -> np.ndarray:
        """Sintetiza com voz genérica"""
        try:
            logger.info(f"  🔊 _synthesize_with_preset:")
            logger.info(f"     text='{text}'")
            logger.info(f"     speaker={speaker}, language={language}")
            logger.info(f"     speed={speed}, pitch={pitch}")
            
            # ===== PRODUÇÃO: Substituir por código real =====
            # audio_data = self._tts_model.tts(
            #     text=text,
            #     speaker=speaker,
            #     language=language,
            #     speed=speed,
            #     pitch=pitch
            # )
            # ===== FIM PRODUÇÃO =====
            
            # MOCK
            logger.info(f"     Calling MOCK tts()...")
            audio_data = self._tts_model.tts(
                text=text,
                speaker=speaker,
                language=language,
                speed=speed,
                pitch=pitch
            )
            
            logger.info(f"     MOCK tts() returned: {len(audio_data)} samples")
            
            return audio_data
            
        except Exception as e:
            raise OpenVoiceException(f"TTS synthesis failed: {str(e)}")
    
    async def _synthesize_with_cloned_voice(
        self,
        text: str,
        voice_profile: VoiceProfile,
        speed: float,
        pitch: float
    ) -> np.ndarray:
        """Sintetiza com voz clonada"""
        try:
            # Carrega embedding do perfil
            voice_embedding = self._load_voice_embedding(voice_profile.profile_path)
            
            # ===== PRODUÇÃO: Substituir por código real =====
            # audio_data = self._tts_model.tts_with_voice(
            #     text=text,
            #     voice_embedding=voice_embedding,
            #     speed=speed,
            #     pitch=pitch
            # )
            # ===== FIM PRODUÇÃO =====
            
            # MOCK
            audio_data = self._tts_model.tts_with_voice(
                text=text,
                voice_embedding=voice_embedding,
                speed=speed,
                pitch=pitch
            )
            
            # Incrementa uso do perfil
            voice_profile.increment_usage()
            
            return audio_data
            
        except Exception as e:
            raise OpenVoiceException(f"Cloned voice synthesis failed: {str(e)}")
    
    async def clone_voice(
        self,
        audio_path: str,
        language: str,
        voice_name: str,
        description: Optional[str] = None
    ) -> VoiceProfile:
        """
        Clona voz a partir de amostra de áudio
        
        Args:
            audio_path: Caminho para amostra de áudio
            language: Idioma base da voz
            voice_name: Nome do perfil
            description: Descrição opcional
        
        Returns:
            VoiceProfile com embedding extraído
        """
        try:
            self._load_models()
            
            # Validação crítica: audio_path não pode ser None ou vazio
            if not audio_path:
                error_msg = (
                    f"Audio path is required for voice cloning. "
                    f"Received: {repr(audio_path)} (type: {type(audio_path).__name__})"
                )
                logger.error(f"❌ Validation failed: {error_msg}")
                raise InvalidAudioException(error_msg)
            
            # Validação: arquivo deve existir
            from pathlib import Path
            if not Path(audio_path).exists():
                error_msg = (
                    f"Audio file not found: {audio_path}. "
                    f"Please verify the file path is correct and accessible in the container."
                )
                logger.error(f"❌ File not found: {error_msg}")
                raise InvalidAudioException(error_msg)
            
            logger.info(f"Cloning voice from {audio_path} language={language}")
            
            # Valida áudio
            audio_info = self._validate_audio_for_cloning(audio_path)
            
            # Extrai embedding de voz
            voice_embedding = await self._extract_voice_embedding(audio_path, language)
            
            # Salva embedding
            voice_profiles_dir = Path(self.settings['voice_profiles_dir'])
            voice_profiles_dir.mkdir(exist_ok=True, parents=True)
            
            # Cria perfil temporário para gerar ID
            temp_profile = VoiceProfile.create_new(
                name=voice_name,
                language=language,
                source_audio_path=audio_path,
                profile_path="",  # Será preenchido abaixo
                description=description,
                duration=audio_info['duration'],
                sample_rate=audio_info['sample_rate']
            )
            
            # Salva embedding
            profile_path = voice_profiles_dir / f"{temp_profile.id}.pkl"
            self._save_voice_embedding(voice_embedding, str(profile_path))
            
            # Atualiza perfil com caminho
            temp_profile.profile_path = str(profile_path)
            
            logger.info(f"✅ Voice cloned successfully: {temp_profile.id}")
            
            return temp_profile
            
        except Exception as e:
            logger.error(f"Error cloning voice: {e}")
            raise OpenVoiceException(f"Voice cloning failed: {str(e)}")
    
    async def _extract_voice_embedding(self, audio_path: str, language: str) -> np.ndarray:
        """Extrai embedding de voz do áudio"""
        try:
            # ===== PRODUÇÃO: Substituir por código real =====
            # from openvoice import se_extractor
            # 
            # embedding = se_extractor.get_se(
            #     audio_path=audio_path,
            #     language=language,
            #     device=self.device
            # )
            # ===== FIM PRODUÇÃO =====
            
            # MOCK
            embedding = self._converter_model.extract_voice_embedding(audio_path, language)
            
            return embedding
            
        except Exception as e:
            raise OpenVoiceException(f"Voice embedding extraction failed: {str(e)}")
    
    def _validate_audio_for_cloning(self, audio_path: str) -> Dict[str, Any]:
        """Valida áudio para clonagem"""
        try:
            # Carrega áudio
            waveform, sample_rate = torchaudio.load(audio_path)
            
            # Duração
            duration = waveform.shape[1] / sample_rate
            
            # Validações
            min_duration = self.settings['openvoice']['min_clone_duration_sec']
            max_duration = self.settings['openvoice']['max_clone_duration_sec']
            
            if duration < min_duration:
                raise InvalidAudioException(f"Audio too short: {duration:.1f}s (min: {min_duration}s)")
            
            if duration > max_duration:
                raise InvalidAudioException(f"Audio too long: {duration:.1f}s (max: {max_duration}s)")
            
            # Sample rate mínimo
            if sample_rate < 16000:
                raise InvalidAudioException(f"Sample rate too low: {sample_rate}Hz (min: 16000Hz)")
            
            return {
                'duration': duration,
                'sample_rate': sample_rate,
                'channels': waveform.shape[0],
                'samples': waveform.shape[1]
            }
            
        except Exception as e:
            if isinstance(e, InvalidAudioException):
                raise
            raise InvalidAudioException(f"Invalid audio file: {str(e)}")
    
    def _save_voice_embedding(self, embedding: np.ndarray, path: str):
        """Salva embedding de voz em arquivo"""
        try:
            with open(path, 'wb') as f:
                pickle.dump(embedding, f)
            logger.debug(f"Voice embedding saved to {path}")
        except Exception as e:
            raise OpenVoiceException(f"Failed to save voice embedding: {str(e)}")
    
    def _load_voice_embedding(self, path: str) -> np.ndarray:
        """Carrega embedding de voz de arquivo"""
        try:
            with open(path, 'rb') as f:
                embedding = pickle.load(f)
            return embedding
        except Exception as e:
            raise OpenVoiceException(f"Failed to load voice embedding: {str(e)}")
    
    def _audio_to_wav_bytes(self, audio_data: np.ndarray, sample_rate: int) -> Tuple[bytes, float]:
        """
        Converte array numpy para bytes WAV
        
        Returns:
            (wav_bytes, duration)
        """
        try:
            import io
            import wave
            
            # Normaliza áudio para int16
            if audio_data.dtype != np.int16:
                # Assume float32 em [-1, 1]
                audio_int16 = (audio_data * 32767).astype(np.int16)
            else:
                audio_int16 = audio_data
            
            # Duração
            duration = len(audio_int16) / sample_rate
            
            # Cria WAV em memória
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_int16.tobytes())
            
            wav_bytes = wav_buffer.getvalue()
            
            return wav_bytes, duration
            
        except Exception as e:
            raise OpenVoiceException(f"Failed to convert audio to WAV: {str(e)}")
