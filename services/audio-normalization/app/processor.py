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
        """Carrega modelo openunmix para isolamento vocal - API CORRIGIDA e ROBUSTA"""
        if not OPENUNMIX_AVAILABLE:
            raise AudioNormalizationException("OpenUnmix não está disponível - instale com: pip install openunmix-pytorch")
            
        if self._openunmix_model is None:
            try:
                logger.info("🎵 Carregando modelo OpenUnmix...")
                
                # ESTRATÉGIA 1: API oficial do OpenUnmix (openunmix-pytorch)
                try:
                    import openunmix
                    
                    # Modelo UMX (Universal Music eXtractor)
                    # Carrega modelo pré-treinado em CPU para evitar OOM
                    self._openunmix_model = openunmix.umx.load_pretrained(
                        target='vocals',  # Apenas vocais
                        device='cpu',  # Força CPU para controle de memória
                        pretrained=True
                    )
                    
                    self._openunmix_model.eval()  # Modo de inferência
                    logger.info("✅ Modelo OpenUnmix carregado com sucesso (API oficial)")
                    
                except AttributeError:
                    # API alternativa para versões antigas
                    logger.info("⚠️ API oficial não disponível, tentando API alternativa...")
                    
                    from openunmix import predict
                    # Usa função de predição diretamente
                    self._openunmix_model = predict
                    logger.info("✅ OpenUnmix carregado via API de predição")
                    
            except Exception as e:
                logger.error(f"❌ Erro ao carregar modelo OpenUnmix: {e}")
                raise AudioNormalizationException(
                    f"Falha ao carregar OpenUnmix. Erro: {str(e)}. "
                    f"Certifique-se de que 'openunmix-pytorch' está instalado."
                )
                    
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
        """Isola vocais usando OpenUnmix com PROTEÇÃO TOTAL contra erros e OOM"""
        if not OPENUNMIX_AVAILABLE:
            logger.error("❌ OpenUnmix não disponível")
            raise AudioNormalizationException("OpenUnmix não está instalado. Use: pip install openunmix-pytorch")
        
        try:
            logger.info(f"🎤 Iniciando isolamento vocal - duração: {len(audio)}ms, canais: {audio.channels}")
            
            # PROTEÇÃO 1: Limita duração para evitar OOM (OpenUnmix é pesado)
            max_duration_ms = 180000  # 3 minutos máximo para vocal isolation
            original_duration = len(audio)
            if original_duration > max_duration_ms:
                logger.warning(f"⚠️ Áudio muito longo ({original_duration}ms), cortando para {max_duration_ms}ms")
                audio = audio[:max_duration_ms]
            
            # PROTEÇÃO 2: Prepara áudio no formato correto
            original_sample_rate = audio.frame_rate
            target_sample_rate = 44100  # OpenUnmix funciona melhor com 44.1kHz
            
            if audio.frame_rate != target_sample_rate:
                logger.info(f"🔄 Ajustando sample rate de {audio.frame_rate} para {target_sample_rate}")
                audio = audio.set_frame_rate(target_sample_rate)
            
            # PROTEÇÃO 3: Garante que é estéreo (OpenUnmix precisa de estéreo)
            original_channels = audio.channels
            if audio.channels == 1:
                logger.info("🔄 Convertendo mono para estéreo (OpenUnmix requer estéreo)")
                audio = audio.set_channels(2)
            
            # PROTEÇÃO 4: Converte para numpy array
            try:
                samples = np.array(audio.get_array_of_samples())
                
                # Reshape para estéreo (samples x 2)
                if audio.channels == 2:
                    samples = samples.reshape((-1, 2))
                
                # Converte para float32 e normaliza para [-1, 1]
                samples_float = samples.astype(np.float32) / 32768.0
                
                logger.info(f"📊 Array preparado: shape={samples_float.shape}, dtype={samples_float.dtype}")
                
            except Exception as array_err:
                logger.error(f"💥 Erro ao preparar array: {array_err}")
                raise AudioNormalizationException(f"Failed to prepare audio for vocal isolation: {str(array_err)}")
            
            # PROTEÇÃO 5: Carrega modelo
            try:
                model = self._load_openunmix_model()
            except Exception as model_err:
                logger.error(f"💥 Erro ao carregar modelo: {model_err}")
                raise AudioNormalizationException(f"Failed to load OpenUnmix model: {str(model_err)}")
            
            # PROTEÇÃO 6: Aplica isolamento vocal
            try:
                logger.info("🎯 Aplicando separação de fontes com OpenUnmix...")
                
                # Converte para tensor PyTorch (channels x samples)
                audio_tensor = torch.from_numpy(samples_float.T).unsqueeze(0)
                logger.info(f"📊 Tensor criado: shape={audio_tensor.shape}")
                
                # Inferência sem gradientes (economia de memória)
                with torch.no_grad():
                    # Aplica modelo
                    if callable(model):
                        # Se é função predict
                        vocals_tensor = model(audio_tensor, rate=target_sample_rate)
                        if isinstance(vocals_tensor, dict):
                            vocals_tensor = vocals_tensor.get('vocals', audio_tensor)
                    else:
                        # Se é modelo
                        vocals_tensor = model(audio_tensor)
                    
                    logger.info(f"📊 Tensor de saída: shape={vocals_tensor.shape}")
                    
                    # Extrai apenas vocais e converte para numpy
                    vocals_np = vocals_tensor.squeeze(0).cpu().numpy()
                
                logger.info("✅ Separação concluída")
                
            except Exception as openunmix_err:
                logger.error(f"💥 OpenUnmix falhou: {openunmix_err}", exc_info=True)
                raise AudioNormalizationException(f"Vocal isolation failed: {str(openunmix_err)}")
            
            # PROTEÇÃO 7: Converte resultado de volta para AudioSegment
            try:
                # Transpõe de volta (samples x channels)
                vocals_np = vocals_np.T
                
                # Clip para [-1, 1]
                vocals_np = np.clip(vocals_np, -1.0, 1.0)
                
                # Converte para int16
                vocals_int16 = (vocals_np * 32767).astype(np.int16)
                
                # Flatten se for estéreo
                if vocals_int16.shape[1] == 2:
                    vocals_bytes = vocals_int16.flatten().tobytes()
                    channels = 2
                else:
                    vocals_bytes = vocals_int16.tobytes()
                    channels = 1
                
                # Cria AudioSegment
                processed_audio = AudioSegment(
                    vocals_bytes,
                    frame_rate=target_sample_rate,
                    sample_width=2,
                    channels=channels
                )
                
                logger.info(f"✅ AudioSegment criado: {len(processed_audio)}ms, {channels} canais")
                
            except Exception as convert_err:
                logger.error(f"💥 Erro ao converter resultado: {convert_err}")
                raise AudioNormalizationException(f"Failed to convert isolated vocals: {str(convert_err)}")
            
            # RESTAURAÇÃO: Tenta restaurar sample rate original
            try:
                if processed_audio.frame_rate != original_sample_rate:
                    processed_audio = processed_audio.set_frame_rate(original_sample_rate)
                    logger.info(f"🔄 Sample rate restaurado para {original_sample_rate}Hz")
                
                # Mantém estéreo ou converte para mono conforme original
                if original_channels == 1 and processed_audio.channels == 2:
                    # OPCIONAL: Converte de volta para mono se original era mono
                    # processed_audio = processed_audio.set_channels(1)
                    # logger.info("🔄 Convertido de volta para mono")
                    pass  # Mantém estéreo para melhor qualidade dos vocais
                    
            except Exception as restore_err:
                logger.warning(f"⚠️ Falha ao restaurar características: {restore_err}")
            
            logger.info("✅ Isolamento vocal concluído com sucesso")
            return processed_audio
            
        except MemoryError as mem_err:
            logger.error(f"💾 OUT OF MEMORY no isolamento vocal: {mem_err}")
            raise AudioNormalizationException(
                f"Out of memory during vocal isolation. Audio too large for ML model. "
                f"Try reducing duration or use a smaller audio file."
            )
        except AudioNormalizationException:
            raise
        except Exception as e:
            logger.error(f"💥 Erro crítico inesperado no isolamento vocal: {e}", exc_info=True)
            raise AudioNormalizationException(f"Critical error in vocal isolation: {str(e)}")
    
    async def _remove_noise(self, audio: AudioSegment) -> AudioSegment:
        """Remove ruído usando noisereduce com PROTEÇÃO TOTAL contra erros de formato e memória"""
        try:
            logger.info(f"🔇 Iniciando remoção de ruído - duração: {len(audio)}ms, canais: {audio.channels}, sample_rate: {audio.frame_rate}")
            
            # PROTEÇÃO 1: Limita duração para evitar OOM
            max_duration_ms = 300000  # 5 minutos máximo
            original_duration = len(audio)
            if original_duration > max_duration_ms:
                logger.warning(f"⚠️ Áudio muito longo ({original_duration}ms), cortando para {max_duration_ms}ms")
                audio = audio[:max_duration_ms]
            
            # PROTEÇÃO 2: Converte para mono para reduzir uso de memória
            original_channels = audio.channels
            if audio.channels > 1:
                logger.info("🔄 Convertendo para mono temporariamente para economizar memória")
                audio_mono = audio.set_channels(1)
            else:
                audio_mono = audio
            
            # PROTEÇÃO 3: Reduz sample rate se muito alto
            target_sample_rate = 22050  # 22kHz é suficiente para noise reduction
            original_sample_rate = audio_mono.frame_rate
            if audio_mono.frame_rate > target_sample_rate:
                logger.info(f"🔄 Reduzindo sample rate de {audio_mono.frame_rate} para {target_sample_rate}")
                audio_mono = audio_mono.set_frame_rate(target_sample_rate)
            
            # PROTEÇÃO 4: Converte para numpy com tipo correto
            try:
                # Obtém samples como array
                samples = np.array(audio_mono.get_array_of_samples())
                logger.info(f"📊 Array shape inicial: {samples.shape}, dtype: {samples.dtype}")
                
                # Converte para float32 e normaliza para [-1, 1]
                # CRÍTICO: noisereduce espera float32 ou float64 com valores em [-1, 1]
                if samples.dtype == np.int16:
                    samples_float = samples.astype(np.float32) / 32768.0
                elif samples.dtype == np.int32:
                    samples_float = samples.astype(np.float32) / 2147483648.0
                else:
                    # Já é float, normaliza se necessário
                    samples_float = samples.astype(np.float32)
                    max_val = np.max(np.abs(samples_float))
                    if max_val > 1.0:
                        samples_float = samples_float / max_val
                
                logger.info(f"📊 Array após normalização: shape={samples_float.shape}, dtype={samples_float.dtype}, range=[{samples_float.min():.3f}, {samples_float.max():.3f}]")
                
                # PROTEÇÃO 5: Verifica se tem valores válidos
                if np.isnan(samples_float).any() or np.isinf(samples_float).any():
                    logger.error("❌ Array contém NaN ou Inf após normalização")
                    raise ValueError("Audio array contains invalid values (NaN or Inf)")
                
            except Exception as array_err:
                logger.error(f"💥 Erro ao preparar array para noise reduction: {array_err}")
                raise AudioNormalizationException(f"Failed to prepare audio array: {str(array_err)}")
            
            logger.info(f"🎯 Aplicando noisereduce em {len(samples_float)} samples @ {audio_mono.frame_rate}Hz")
            
            # PROTEÇÃO 6: Aplica redução de ruído com parâmetros conservadores e try/except
            try:
                reduced_noise = nr.reduce_noise(
                    y=samples_float,
                    sr=audio_mono.frame_rate,
                    stationary=True,  # Mais eficiente em memória
                    prop_decrease=0.8,  # Redução agressiva mas controlada
                    freq_mask_smooth_hz=500,  # Suavização de frequência
                    time_mask_smooth_ms=50,  # Suavização temporal
                    n_std_thresh_stationary=1.5,  # Threshold para ruído estacionário
                    n_jobs=1  # Força single-thread para controlar memória
                )
                
                logger.info(f"✅ noisereduce concluído. Output shape: {reduced_noise.shape}, dtype: {reduced_noise.dtype}")
                
            except Exception as nr_err:
                logger.error(f"💥 noisereduce falhou: {nr_err}", exc_info=True)
                raise AudioNormalizationException(f"Noise reduction algorithm failed: {str(nr_err)}")
            
            # PROTEÇÃO 7: Valida output e converte de volta para int16
            try:
                # Verifica se output é válido
                if np.isnan(reduced_noise).any() or np.isinf(reduced_noise).any():
                    logger.error("❌ noisereduce retornou NaN ou Inf")
                    raise ValueError("Noise reduction produced invalid values")
                
                # Clip para garantir que está em [-1, 1]
                reduced_noise = np.clip(reduced_noise, -1.0, 1.0)
                
                # Converte para int16
                reduced_noise_int16 = (reduced_noise * 32767).astype(np.int16)
                
                logger.info(f"📊 Array final: shape={reduced_noise_int16.shape}, dtype={reduced_noise_int16.dtype}")
                
            except Exception as convert_err:
                logger.error(f"💥 Erro ao converter resultado: {convert_err}")
                raise AudioNormalizationException(f"Failed to convert processed audio: {str(convert_err)}")
            
            # PROTEÇÃO 8: Cria AudioSegment processado
            try:
                processed_audio = AudioSegment(
                    reduced_noise_int16.tobytes(),
                    frame_rate=audio_mono.frame_rate,
                    sample_width=2,  # int16 = 2 bytes
                    channels=1  # Sempre retorna mono após noise reduction
                )
                
                logger.info(f"✅ AudioSegment criado: {len(processed_audio)}ms")
                
            except Exception as segment_err:
                logger.error(f"💥 Erro ao criar AudioSegment: {segment_err}")
                raise AudioNormalizationException(f"Failed to create audio segment: {str(segment_err)}")
            
            # RESTAURAÇÃO: Tenta restaurar características originais
            try:
                # Restaura sample rate original se foi alterado
                if processed_audio.frame_rate != original_sample_rate:
                    processed_audio = processed_audio.set_frame_rate(original_sample_rate)
                    logger.info(f"🔄 Sample rate restaurado para {original_sample_rate}Hz")
                
                # Restaura canais se original era estéreo
                if original_channels > 1:
                    processed_audio = processed_audio.set_channels(original_channels)
                    logger.info(f"🔄 Canais restaurados para {original_channels}")
                    
            except Exception as restore_err:
                logger.warning(f"⚠️ Falha ao restaurar características originais: {restore_err}")
                # Continua com áudio processado mesmo se restauração falhar
            
            logger.info("✅ Remoção de ruído concluída com sucesso")
            return processed_audio
            
        except MemoryError as mem_err:
            logger.error(f"💾 MEMORY ERROR na remoção de ruído: {mem_err}")
            raise AudioNormalizationException(f"Out of memory during noise reduction. Audio too large: {str(mem_err)}")
        except AudioNormalizationException:
            raise
        except Exception as e:
            logger.error(f"💥 Erro crítico inesperado na remoção de ruído: {e}", exc_info=True)
            raise AudioNormalizationException(f"Critical error in noise removal: {str(e)}")
    
    async def _apply_highpass_filter(self, audio: AudioSegment) -> AudioSegment:
        """Aplica filtro high-pass com tratamento robusto de erros e múltiplas estratégias"""
        try:
            cutoff_freq = 80  # Frequência de corte: 80Hz
            logger.info(f"🎛️ Aplicando filtro high-pass com cutoff={cutoff_freq}Hz")
            
            # ESTRATÉGIA 1: Tenta usar pydub high_pass_filter
            try:
                filtered_audio = high_pass_filter(audio, cutoff_freq)
                logger.info("✅ Filtro high-pass aplicado via pydub")
                return filtered_audio
            except Exception as pydub_err:
                logger.warning(f"⚠️ pydub high_pass_filter falhou: {pydub_err}")
                
                # ESTRATÉGIA 2: Usa ffmpeg diretamente via export/import
                try:
                    logger.info("🔄 Tentando filtro high-pass via ffmpeg direto")
                    
                    # Cria arquivo temporário
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_in:
                        temp_input_path = temp_in.name
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_out:
                        temp_output_path = temp_out.name
                    
                    try:
                        # Exporta áudio original
                        audio.export(temp_input_path, format="wav")
                        
                        # Aplica filtro via ffmpeg
                        import subprocess
                        ffmpeg_cmd = [
                            "ffmpeg", "-y", "-i", temp_input_path,
                            "-af", f"highpass=f={cutoff_freq}",
                            temp_output_path
                        ]
                        
                        result = subprocess.run(
                            ffmpeg_cmd,
                            capture_output=True,
                            text=True,
                            timeout=60
                        )
                        
                        if result.returncode != 0:
                            raise Exception(f"ffmpeg failed: {result.stderr}")
                        
                        # Carrega áudio filtrado
                        filtered_audio = AudioSegment.from_wav(temp_output_path)
                        logger.info("✅ Filtro high-pass aplicado via ffmpeg direto")
                        return filtered_audio
                        
                    finally:
                        # Limpa arquivos temporários
                        import os
                        try:
                            if os.path.exists(temp_input_path):
                                os.unlink(temp_input_path)
                            if os.path.exists(temp_output_path):
                                os.unlink(temp_output_path)
                        except Exception:
                            pass
                            
                except Exception as ffmpeg_err:
                    logger.warning(f"⚠️ ffmpeg direto também falhou: {ffmpeg_err}")
                    
                    # ESTRATÉGIA 3: Implementa filtro manualmente com scipy
                    try:
                        logger.info("🔄 Tentando filtro high-pass via scipy")
                        from scipy import signal
                        
                        # Converte para numpy
                        samples = np.array(audio.get_array_of_samples())
                        sample_rate = audio.frame_rate
                        
                        # Verifica se é stereo
                        if audio.channels == 2:
                            samples = samples.reshape((-1, 2))
                            is_stereo = True
                        else:
                            is_stereo = False
                        
                        # Normaliza para float
                        samples_float = samples.astype(np.float32) / (2**15)
                        
                        # Cria filtro Butterworth high-pass
                        nyquist = sample_rate / 2
                        normalized_cutoff = cutoff_freq / nyquist
                        b, a = signal.butter(5, normalized_cutoff, btype='high')
                        
                        # Aplica filtro
                        if is_stereo:
                            filtered_left = signal.filtfilt(b, a, samples_float[:, 0])
                            filtered_right = signal.filtfilt(b, a, samples_float[:, 1])
                            filtered_samples = np.column_stack((filtered_left, filtered_right))
                        else:
                            filtered_samples = signal.filtfilt(b, a, samples_float)
                        
                        # Converte de volta para int16
                        filtered_samples = np.clip(filtered_samples * (2**15), -32768, 32767).astype(np.int16)
                        
                        # Cria AudioSegment
                        filtered_audio = AudioSegment(
                            filtered_samples.tobytes(),
                            frame_rate=sample_rate,
                            sample_width=2,
                            channels=audio.channels
                        )
                        
                        logger.info("✅ Filtro high-pass aplicado via scipy")
                        return filtered_audio
                        
                    except Exception as scipy_err:
                        logger.error(f"💥 Todas as estratégias de high-pass falharam. Último erro (scipy): {scipy_err}")
                        raise AudioNormalizationException(
                            f"High-pass filter failed with all strategies. "
                            f"pydub: {str(pydub_err)[:50]}, "
                            f"ffmpeg: {str(ffmpeg_err)[:50]}, "
                            f"scipy: {str(scipy_err)[:50]}"
                        )
                        
        except AudioNormalizationException:
            raise
        except Exception as e:
            logger.error(f"💥 Erro crítico inesperado no filtro high-pass: {e}", exc_info=True)
            raise AudioNormalizationException(f"Critical error in high-pass filter: {str(e)}")