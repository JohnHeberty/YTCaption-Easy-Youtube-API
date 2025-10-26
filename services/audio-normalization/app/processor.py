import os
import asyncio
import tempfile
import numpy as np
import logging
from datetime import datetime
from pathlib import Path
from pydub import AudioSegment
from pydub.effects import normalize, high_pass_filter
import noisereduce as nr
import soundfile as sf
import librosa
from .models import Job, JobStatus
from .exceptions import AudioNormalizationException

logger = logging.getLogger(__name__)

# Para isolamento vocal com openunmix
try:
    import torch
    import openunmix
    OPENUNMIX_AVAILABLE = True
    logger.info("OpenUnmix disponível para isolamento vocal")
except ImportError:
    OPENUNMIX_AVAILABLE = False
    logger.warning("OpenUnmix não disponível. Isolamento vocal será desabilitado")


class AudioProcessor:
    def __init__(self):
        self.job_store = None  # Will be injected
        self._openunmix_model = None
    
    def _load_openunmix_model(self):
        """Carrega modelo openunmix para isolamento vocal - API CORRIGIDA"""
        if not OPENUNMIX_AVAILABLE:
            raise AudioNormalizationException("OpenUnmix não está disponível")
            
        if self._openunmix_model is None:
            try:
                logger.info("Carregando modelo OpenUnmix...")
                
                # API CORRETA do OpenUnmix
                from openunmix import umx
                
                # Carrega modelo UMX (default)
                self._openunmix_model = umx.load_model(
                    model_name='umx',
                    device='cpu',
                    targets=['vocals', 'drums', 'bass', 'other']
                )
                
                logger.info("Modelo OpenUnmix carregado com sucesso")
            except Exception as e:
                logger.error(f"Erro ao carregar modelo OpenUnmix: {e}")
                
                # Fallback: tenta API alternativa
                try:
                    import openunmix.model
                    self._openunmix_model = openunmix.model.load_model(device='cpu')
                    logger.info("Modelo OpenUnmix carregado via API alternativa")
                except Exception as e2:
                    logger.error(f"Fallback também falhou: {e2}")
                    raise AudioNormalizationException(f"Falha ao carregar OpenUnmix - APIs testadas: {str(e)} / {str(e2)}")
                    
        return self._openunmix_model
    
    async def process_audio_job(self, job: Job):
        """
        Processa um job de áudio com operações condicionais.
        IMPORTANTE: Aceita QUALQUER formato de entrada e SEMPRE salva como .webm
        """
        try:
            logger.info(f"Iniciando processamento do job: {job.id}")
            
            # Atualiza status para processando
            job.status = JobStatus.PROCESSING
            job.progress = 2.0
            if self.job_store:
                self.job_store.update_job(job)
            
            # VALIDAÇÃO COM FFPROBE (a verdadeira validação)
            try:
                from .security import validate_audio_content_with_ffprobe
                logger.info(f"Validando arquivo com ffprobe: {job.input_file}")
                file_info = validate_audio_content_with_ffprobe(job.input_file)
                logger.info(f"Arquivo válido - Áudio: {file_info['has_audio']}, Vídeo: {file_info['has_video']}")
            except Exception as e:
                logger.error(f"Validação ffprobe falhou: {e}")
                raise AudioNormalizationException(str(e))
            
            job.progress = 5.0
            if self.job_store:
                self.job_store.update_job(job)
            
            # Carrega arquivo - com extração automática de áudio se for vídeo
            try:
                logger.info(f"Carregando arquivo: {job.input_file}")
                
                # Se contém vídeo, extrai apenas o áudio automaticamente
                if file_info['has_video']:
                    logger.info("Arquivo contém vídeo - extraindo stream de áudio automaticamente")
                    # pydub automaticamente extrai áudio usando ffmpeg
                    audio = AudioSegment.from_file(job.input_file, parameters=["-vn"])
                else:
                    # Arquivo só de áudio
                    audio = AudioSegment.from_file(job.input_file)
                
                logger.info(f"Áudio carregado com sucesso. Formato: {Path(job.input_file).suffix}")
                
            except Exception as e:
                logger.error(f"Erro ao carregar arquivo: {e}")
                raise AudioNormalizationException(f"Não foi possível carregar o arquivo: {str(e)}")
            
            job.progress = 10.0
            if self.job_store:
                self.job_store.update_job(job)
            
            # Verifica se alguma operação foi solicitada
            any_operation = (job.remove_noise or job.convert_to_mono or 
                           job.apply_highpass_filter or job.set_sample_rate_16k or 
                           job.isolate_vocals)
            
            if not any_operation:
                logger.info("Nenhuma operação solicitada - salvando arquivo sem modificações")
                job.progress = 50.0
                if self.job_store:
                    self.job_store.update_job(job)
            else:
                logger.info(f"Aplicando operações: {job.processing_operations}")
                
                try:
                    # Aplicar operações condicionalmente
                    processed_audio = await self._apply_processing_operations(audio, job)
                    audio = processed_audio
                except Exception as e:
                    logger.error(f"Erro durante processamento de áudio: {e}")
                    raise AudioNormalizationException(f"Falha no processamento: {str(e)}")
            
            # CRÍTICO: Salva arquivo processado SEMPRE como .webm
            output_dir = Path("./processed")
            try:
                output_dir.mkdir(exist_ok=True, parents=True)
            except Exception as e:
                logger.error(f"Erro ao criar diretório de saída: {e}")
                raise AudioNormalizationException(f"Não foi possível criar diretório: {str(e)}")
            
            # Nome do arquivo baseado nas operações
            operations_suffix = f"_{job.processing_operations}" if job.processing_operations != "none" else ""
            output_path = output_dir / f"{job.id}{operations_suffix}.webm"
            
            try:
                logger.info(f"Salvando arquivo processado como WebM: {output_path}")
                # SEMPRE exporta como .webm com codec opus
                audio.export(
                    str(output_path), 
                    format="webm",
                    codec="libopus",
                    parameters=["-strict", "-2"]
                )
                logger.info(f"Arquivo WebM salvo com sucesso. Tamanho: {output_path.stat().st_size} bytes")
            except Exception as e:
                logger.error(f"Erro ao salvar arquivo WebM: {e}")
                raise AudioNormalizationException(f"Falha ao salvar arquivo de saída: {str(e)}")
            
            # Finaliza job
            job.output_file = str(output_path)
            job.status = JobStatus.COMPLETED
            job.progress = 100.0
            job.file_size_output = output_path.stat().st_size
            job.completed_at = datetime.now()
            
            if self.job_store:
                self.job_store.update_job(job)
            
            logger.info(f"Job {job.id} processado com sucesso. Output: {output_path.name}")
            
        except AudioNormalizationException:
            # Re-raise exceções específicas
            raise
        except Exception as e:
            # Captura qualquer erro inesperado
            error_msg = f"Erro inesperado no processamento: {str(e)}"
            logger.error(f"Job {job.id} falhou: {error_msg}", exc_info=True)
            
            job.status = JobStatus.FAILED
            job.error_message = error_msg
            
            if self.job_store:
                self.job_store.update_job(job)
            
            raise AudioNormalizationException(error_msg)
    
    async def _apply_processing_operations(self, audio: AudioSegment, job: Job) -> AudioSegment:
        """Aplica operações de processamento condicionalmente com tratamento robusto de erros"""
        operations_count = sum([
            job.remove_noise, job.convert_to_mono, job.apply_highpass_filter,
            job.set_sample_rate_16k, job.isolate_vocals
        ])
        
        if operations_count == 0:
            return audio
            
        progress_step = 80.0 / operations_count
        current_progress = 10.0
        
        # 1. Isolamento vocal (primeiro, pois pode afetar outras operações)
        if job.isolate_vocals:
            try:
                logger.info("Aplicando isolamento vocal...")
                audio = await self._isolate_vocals(audio)
                current_progress += progress_step
                job.progress = current_progress
                if self.job_store:
                    self.job_store.update_job(job)
            except Exception as e:
                logger.error(f"Erro no isolamento vocal: {e}")
                raise AudioNormalizationException(f"Falha no isolamento vocal: {str(e)}")
        
        # 2. Remoção de ruído
        if job.remove_noise:
            try:
                logger.info("Removendo ruído...")
                audio = await self._remove_noise(audio)
                current_progress += progress_step
                job.progress = current_progress
                if self.job_store:
                    self.job_store.update_job(job)
            except Exception as e:
                logger.error(f"Erro na remoção de ruído: {e}")
                raise AudioNormalizationException(f"Falha na remoção de ruído: {str(e)}")
        
        # 3. Converter para mono
        if job.convert_to_mono:
            try:
                logger.info("Convertendo para mono...")
                audio = audio.set_channels(1)
                current_progress += progress_step
                job.progress = current_progress
                if self.job_store:
                    self.job_store.update_job(job)
            except Exception as e:
                logger.error(f"Erro ao converter para mono: {e}")
                raise AudioNormalizationException(f"Falha na conversão para mono: {str(e)}")
        
        # 4. Aplicar filtro high-pass
        if job.apply_highpass_filter:
            try:
                logger.info("Aplicando filtro high-pass...")
                audio = await self._apply_highpass_filter(audio)
                current_progress += progress_step
                job.progress = current_progress
                if self.job_store:
                    self.job_store.update_job(job)
            except Exception as e:
                logger.error(f"Erro no filtro high-pass: {e}")
                raise AudioNormalizationException(f"Falha no filtro high-pass: {str(e)}")
        
        # 5. Reduzir sample rate para 16kHz
        if job.set_sample_rate_16k:
            try:
                logger.info("Reduzindo sample rate para 16kHz...")
                audio = audio.set_frame_rate(16000)
                current_progress += progress_step
                job.progress = current_progress
                if self.job_store:
                    self.job_store.update_job(job)
            except Exception as e:
                logger.error(f"Erro ao ajustar sample rate: {e}")
                raise AudioNormalizationException(f"Falha ao ajustar sample rate: {str(e)}")
        
        return audio
    
    async def _isolate_vocals(self, audio: AudioSegment) -> AudioSegment:
        """Isola vocais usando OpenUnmix com tratamento robusto de erros"""
        if not OPENUNMIX_AVAILABLE:
            logger.warning("OpenUnmix não disponível - pulando isolamento vocal")
            raise AudioNormalizationException("OpenUnmix não está instalado")
        
        try:
            # Converte para numpy array
            samples = np.array(audio.get_array_of_samples())
            if audio.channels == 2:
                samples = samples.reshape((-1, 2))
            
            # Converte para float32 e normaliza
            samples = samples.astype(np.float32) / (2**15)
            
            # Se for mono, duplica para stereo (openunmix precisa de stereo)
            if len(samples.shape) == 1:
                samples = np.column_stack((samples, samples))
            
            # Aplica openunmix
            model = self._load_openunmix_model()
            
            # Converte para tensor
            audio_tensor = torch.from_numpy(samples.T).unsqueeze(0)
            
            with torch.no_grad():
                estimates = model(audio_tensor)
                vocals = estimates['vocals'].squeeze(0).cpu().numpy()
            
            # Converte de volta para pydub
            vocals = vocals.T
            if vocals.shape[1] == 2:
                vocals = vocals.flatten()
            
            # Normaliza e converte para int16
            vocals = (vocals * 2**15).astype(np.int16)
            
            # Cria novo AudioSegment
            processed_audio = AudioSegment(
                vocals.tobytes(),
                frame_rate=audio.frame_rate,
                sample_width=2,
                channels=1 if len(vocals.shape) == 1 else 2
            )
            
            logger.info("Isolamento vocal aplicado com sucesso")
            return processed_audio
            
        except Exception as e:
            logger.error(f"Erro crítico no isolamento vocal: {e}", exc_info=True)
            raise AudioNormalizationException(f"Erro no isolamento vocal: {str(e)}")
    
    async def _remove_noise(self, audio: AudioSegment) -> AudioSegment:
        """Remove ruído usando noisereduce com PROTEÇÃO CONTRA MEMORY ERROR"""
        try:
            logger.info(f"🔇 Iniciando remoção de ruído - duração: {len(audio)}ms, canais: {audio.channels}")
            
            # PROTEÇÃO 1: Limita duração para evitar OOM
            max_duration_ms = 300000  # 5 minutos máximo
            if len(audio) > max_duration_ms:
                logger.warning(f"⚠️ Áudio muito longo ({len(audio)}ms), cortando para {max_duration_ms}ms")
                audio = audio[:max_duration_ms]
            
            # PROTEÇÃO 2: Converte para mono para reduzir uso de memória
            if audio.channels > 1:
                logger.info("🔄 Convertendo para mono para economizar memória")
                audio_mono = audio.set_channels(1)
            else:
                audio_mono = audio
            
            # PROTEÇÃO 3: Reduz sample rate se muito alto
            target_sample_rate = 22050  # 22kHz é suficiente para noise reduction
            if audio_mono.frame_rate > target_sample_rate:
                logger.info(f"🔄 Reduzindo sample rate de {audio_mono.frame_rate} para {target_sample_rate}")
                audio_mono = audio_mono.set_frame_rate(target_sample_rate)
            
            # Converte para numpy de forma eficiente
            samples = np.array(audio_mono.get_array_of_samples(), dtype=np.float32)
            
            # Normaliza para [-1, 1]
            max_val = np.max(np.abs(samples))
            if max_val > 0:
                samples = samples / max_val
            
            logger.info(f"📊 Processando {len(samples)} samples para noise reduction")
            
            # PROTEÇÃO 4: Aplica redução de ruído com parâmetros conservadores
            reduced_noise = nr.reduce_noise(
                y=samples, 
                sr=audio_mono.frame_rate,
                stationary=True,  # Mais eficiente em memória
                prop_decrease=0.5,  # Redução mais conservadora
                n_jobs=1  # Força single-thread para controlar memória
            )
            
            # Converte de volta para int16
            if max_val > 0:
                reduced_noise = reduced_noise * max_val
            
            reduced_noise = np.clip(reduced_noise, -32768, 32767).astype(np.int16)
            
            # Cria AudioSegment processado
            processed_audio = AudioSegment(
                reduced_noise.tobytes(),
                frame_rate=audio_mono.frame_rate,
                sample_width=2,
                channels=1  # Sempre retorna mono após noise reduction
            )
            
            # Restaura características originais se possível
            if audio.channels > 1 and processed_audio.channels == 1:
                # Se áudio original era estéreo, duplica canal para compatibilidade
                processed_audio = processed_audio.set_channels(audio.channels)
                logger.info("🔄 Restaurado para estéreo")
            
            # Restaura sample rate original se foi alterado
            if processed_audio.frame_rate != audio.frame_rate:
                processed_audio = processed_audio.set_frame_rate(audio.frame_rate)
                logger.info(f"🔄 Sample rate restaurado para {audio.frame_rate}")
            
            logger.info("✅ Remoção de ruído aplicada com sucesso")
            return processed_audio
            
        except MemoryError as mem_err:
            logger.error(f"💾 MEMORY ERROR na remoção de ruído: {mem_err}")
            raise AudioNormalizationException(f"Áudio muito grande para remoção de ruído: {str(mem_err)}")
        except Exception as e:
            logger.error(f"💥 Erro crítico na remoção de ruído: {e}", exc_info=True)
            raise AudioNormalizationException(f"Erro na remoção de ruído: {str(e)}")
    
    async def _apply_highpass_filter(self, audio: AudioSegment) -> AudioSegment:
        """Aplica filtro high-pass com tratamento robusto de erros"""
        try:
            # Frequência de corte: 80Hz (remove frequências muito baixas)
            cutoff_freq = 80
            filtered_audio = high_pass_filter(audio, cutoff_freq)
            logger.info("Filtro high-pass aplicado com sucesso")
            return filtered_audio
        except Exception as e:
            logger.error(f"Erro crítico no filtro high-pass: {e}", exc_info=True)
            raise AudioNormalizationException(f"Erro no filtro high-pass: {str(e)}")