import os
import asyncio
import tempfile
import numpy as np
import logging
import subprocess
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


class AudioProcessor:
    def __init__(self):
        self.job_store = None  # Will be injected
        self._load_config()
    
    def _load_config(self):
        """Carrega configurações do .env"""
        from .config import get_settings
        settings = get_settings()
        
        self.config = {
            'temp_dir': settings['temp_dir'],
            'streaming_threshold_mb': settings['audio_chunking']['streaming_threshold_mb'],
            'chunking_enabled': settings['audio_chunking']['enabled'],
            'chunk_size_mb': settings['audio_chunking']['chunk_size_mb'],
            'chunk_duration_sec': settings['audio_chunking']['chunk_duration_sec'],
            'chunk_overlap_sec': settings['audio_chunking']['chunk_overlap_sec'],
            'noise_reduction_max_duration': settings['noise_reduction']['max_duration_sec'],
            'noise_reduction_sample_rate': settings['noise_reduction']['sample_rate'],
            'noise_reduction_chunk_size': settings['noise_reduction']['chunk_size_sec'],
            'vocal_isolation_max_duration': settings['vocal_isolation']['max_duration_sec'],
            'vocal_isolation_sample_rate': settings['vocal_isolation']['sample_rate'],
            'highpass_cutoff_hz': settings['highpass_filter']['cutoff_hz'],
            'highpass_order': settings['highpass_filter']['order'],
        }
        
        logger.info(f"🔧 Config carregada: chunking={self.config['chunking_enabled']}, chunk_size={self.config['chunk_size_mb']}MB, streaming_threshold={self.config['streaming_threshold_mb']}MB")
    
    def _check_disk_space(self, file_path: str, temp_dir: Path) -> bool:
        """Verifica se há espaço em disco suficiente para processar o arquivo."""
        try:
            import shutil
            
            # Obtém tamanho do arquivo de entrada
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            
            # Estima espaço necessário: 3x o tamanho do arquivo (margem de segurança)
            estimated_space_needed = file_size * 3
            
            # Verifica espaço disponível
            stat = shutil.disk_usage(temp_dir)
            available_space = stat.free
            available_space_mb = available_space / (1024 * 1024)
            
            logger.info(f"💾 Espaço em disco - Disponível: {available_space_mb:.2f}MB, Necessário: {estimated_space_needed/(1024*1024):.2f}MB")
            
            if available_space < estimated_space_needed:
                logger.error(f"❌ Espaço em disco insuficiente! Disponível: {available_space_mb:.2f}MB, Necessário: {estimated_space_needed/(1024*1024):.2f}MB")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Não foi possível verificar espaço em disco: {e}")
            # Em caso de erro na verificação, prossegue (fail-open)
            return True
    
    def _is_video_file(self, file_path: str) -> bool:
        """Detecta se arquivo é vídeo usando ffprobe"""
        try:
            cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                file_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.warning(f"⚠️ ffprobe falhou: {result.stderr}")
                return False
            
            import json
            data = json.loads(result.stdout)
            streams = data.get('streams', [])
            
            # Verifica se há stream de vídeo
            has_video = any(s.get('codec_type') == 'video' for s in streams)
            has_audio = any(s.get('codec_type') == 'audio' for s in streams)
            
            if has_video:
                logger.info(f"🎬 Vídeo detectado (video: {has_video}, audio: {has_audio})")
            
            return has_video
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao detectar tipo de arquivo: {e}")
            # Fallback: verifica extensão
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v']
            return any(file_path.lower().endswith(ext) for ext in video_extensions)
    
    async def _extract_audio_from_video(self, video_path: str, temp_dir: Path) -> str:
        """Extrai áudio de arquivo de vídeo"""
        try:
            logger.info(f"🎬 Extraindo áudio do vídeo: {video_path}")
            
            # Cria arquivo de saída
            audio_path = temp_dir / f"extracted_audio_{Path(video_path).stem}.wav"
            
            # Comando ffmpeg para extrair áudio
            cmd = [
                "ffmpeg", "-i", video_path,
                "-vn",  # Sem vídeo
                "-acodec", "pcm_s16le",  # Codec compatível
                "-ar", "44100",  # Sample rate
                "-ac", "2",  # Stereo
                "-y",  # Sobrescrever
                str(audio_path)
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise AudioNormalizationException(
                    f"Falha ao extrair áudio do vídeo: {stderr.decode()}"
                )
            
            if not audio_path.exists():
                raise AudioNormalizationException(
                    "Arquivo de áudio não foi criado após extração"
                )
            
            logger.info(f"✅ Áudio extraído: {audio_path} ({audio_path.stat().st_size / 1024 / 1024:.2f} MB)")
            return str(audio_path)
            
        except Exception as e:
            logger.error(f"❌ Erro ao extrair áudio: {e}")
            raise AudioNormalizationException(f"Falha na extração de áudio: {str(e)}")
    
    def _should_use_streaming_processing(self, file_path: str) -> bool:
        """Verifica se o processamento via streaming deve ser usado com base no tamanho do arquivo."""
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        threshold_mb = self.config['streaming_threshold_mb']
        
        if file_size_mb > threshold_mb:
            logger.info(f"📦 Arquivo grande detectado ({file_size_mb:.2f}MB > {threshold_mb}MB). Usando processamento via streaming.")
            return True
        return False

    def _should_use_chunking(self, audio: AudioSegment) -> bool:
        """Verifica se deve usar processamento em chunks"""
        if not self.config['chunking_enabled']:
            return False
        
        # Calcula tamanho do áudio em MB
        audio_size_mb = len(audio.raw_data) / (1024 * 1024)
        duration_sec = len(audio) / 1000  # pydub usa milissegundos
        
        # Usa chunks se exceder limites
        should_chunk = (
            audio_size_mb > self.config['chunk_size_mb'] or
            duration_sec > self.config['chunk_duration_sec']
        )
        
        if should_chunk:
            logger.info(f"📦 Processamento em CHUNKS habilitado: {audio_size_mb:.1f}MB, {duration_sec:.1f}s")
        
        return should_chunk
    
    def _split_audio_into_chunks(self, audio: AudioSegment) -> list:
        """
        Divide áudio em chunks com overlap para processamento
        
        Returns:
            List de tuplas (start_ms, end_ms, chunk_audio)
        """
        chunk_duration_ms = self.config['chunk_duration_sec'] * 1000
        overlap_ms = self.config['chunk_overlap_sec'] * 1000
        audio_duration_ms = len(audio)
        
        chunks = []
        start_ms = 0
        
        while start_ms < audio_duration_ms:
            end_ms = min(start_ms + chunk_duration_ms, audio_duration_ms)
            chunk = audio[start_ms:end_ms]
            chunks.append((start_ms, end_ms, chunk))
            
            # Próximo chunk começa com overlap
            start_ms = end_ms - overlap_ms
            
            if start_ms >= audio_duration_ms - overlap_ms:
                break
        
        logger.info(f"📦 Áudio dividido em {len(chunks)} chunks de ~{chunk_duration_ms/1000}s cada")
        return chunks
    
    def _merge_processed_chunks(self, chunk_paths: list) -> AudioSegment:
        """Mescla múltiplos arquivos de áudio (chunks) em um único AudioSegment."""
        if not chunk_paths:
            raise AudioNormalizationException("Nenhum chunk processado para mesclar.")

        logger.info(f"🔗 Mesclando {len(chunk_paths)} chunks processados...")
        
        # Carrega o primeiro chunk
        final_audio = AudioSegment.from_file(chunk_paths[0])

        # Concatena os chunks restantes
        for chunk_path in chunk_paths[1:]:
            chunk_audio = AudioSegment.from_file(chunk_path)
            final_audio += chunk_audio
        
        logger.info(f"✅ Chunks mesclados com sucesso. Duração final: {len(final_audio)/1000:.1f}s")
        return final_audio

    def _merge_chunks(self, chunks: list, overlap_ms: int) -> AudioSegment:
        """
        Mescla chunks processados de volta em um único áudio
        
        Args:
            chunks: Lista de AudioSegments
            overlap_ms: Overlap em milissegundos
            
        Returns:
            AudioSegment mesclado
        """
        if len(chunks) == 1:
            return chunks[0]
        
        logger.info(f"🔗 Mesclando {len(chunks)} chunks...")
        
        # Primeiro chunk completo
        merged = chunks[0]
        
        # Mescla chunks seguintes com crossfade no overlap
        for i in range(1, len(chunks)):
            if overlap_ms > 0 and len(merged) > overlap_ms:
                # Aplica crossfade suave no overlap
                merged = merged.append(chunks[i], crossfade=overlap_ms)
            else:
                # Simplesmente concatena
                merged = merged + chunks[i]
        
        logger.info(f"✅ Chunks mesclados: duração final = {len(merged)/1000:.1f}s")
        return merged
    
    def _load_openunmix_model(self):
        """Carrega modelo openunmix para isolamento vocal com suporte a GPU"""
        if not OPENUNMIX_AVAILABLE:
            raise AudioNormalizationException("OpenUnmix não está disponível - instale com: pip install openunmix-pytorch")
            
        if self._openunmix_model is None:
            try:
                logger.info(f"🎵 Carregando modelo OpenUnmix no {self.device.upper()}...")
                
                # ESTRATÉGIA 1: API oficial do OpenUnmix (openunmix-pytorch)
                try:
                    import openunmix
                    
                    # Modelo UMX (Universal Music eXtractor)
                    # Carrega modelo no dispositivo detectado (CUDA ou CPU)
                    self._openunmix_model = openunmix.umx.load_pretrained(
                        target='vocals',  # Apenas vocais
                        device=self.device,  # Usa dispositivo detectado
                        pretrained=True
                    )
                    
                    self._openunmix_model.eval()  # Modo de inferência
                    
                    # Testa GPU se disponível
                    if self.device == 'cuda':
                        self._test_gpu()
                    
                    logger.info(f"✅ Modelo OpenUnmix carregado com sucesso no {self.device.upper()}")
                    
                except AttributeError:
                    # API alternativa para versões antigas
                    logger.info("⚠️ API oficial não disponível, tentando API alternativa...")
                    
                    from openunmix.predict import separate
                    # Usa função de separação diretamente
                    self._openunmix_model = separate
                    logger.info("✅ OpenUnmix carregado via API de separação")
                    
            except Exception as e:
                logger.error(f"❌ Erro ao carregar modelo OpenUnmix: {e}")
                # Fallback para CPU se GPU falhar
                if self.device == 'cuda':
                    logger.warning("⚠️ Tentando novamente com CPU...")
                    self.device = 'cpu'
                    return self._load_openunmix_model()
                raise AudioNormalizationException(
                    f"Falha ao carregar OpenUnmix. Erro: {str(e)}. "
                    f"Certifique-se de que 'openunmix-pytorch' está instalado."
                )
                    
        return self._openunmix_model
    
    async def process_audio_job(self, job: Job):
        """
        Processa um job de áudio, decidindo entre carregamento direto ou streaming.
        Suporta vídeos (extrai áudio automaticamente).
        """
        temp_audio_path = None
        temp_dir_for_extraction = None
        
        try:
            logger.info(f"Iniciando processamento do job: {job.id}")
            job.status = JobStatus.PROCESSING
            job.progress = 2.0
            if self.job_store: self.job_store.update_job(job)

            logger.info(f"Processando arquivo: {job.input_file}")
            
            # 🎬 NOVO: Detecta e extrai áudio de vídeos
            file_to_process = job.input_file
            is_video = self._is_video_file(job.input_file)
            
            if is_video:
                logger.info("🎬 Arquivo de vídeo detectado - extraindo áudio...")
                
                # Cria diretório temporário para extração
                base_temp_dir = Path(self.config['temp_dir'])
                base_temp_dir.mkdir(exist_ok=True, parents=True)
                temp_dir_for_extraction = base_temp_dir / f"video_extraction_{job.id}"
                temp_dir_for_extraction.mkdir(exist_ok=True, parents=True)
                
                # Extrai áudio
                temp_audio_path = await self._extract_audio_from_video(
                    job.input_file, 
                    temp_dir_for_extraction
                )
                file_to_process = temp_audio_path
                logger.info(f"✅ Usando áudio extraído: {file_to_process}")
                
                job.progress = 5.0
                if self.job_store: self.job_store.update_job(job)
            else:
                logger.info("🎵 Arquivo de áudio detectado - processando diretamente")

            job.progress = 8.0
            if self.job_store: self.job_store.update_job(job)

            # DECISÃO CRÍTICA: Usar streaming ou carregar na memória?
            file_info = {'has_audio': True, 'has_video': is_video}
            if self._should_use_streaming_processing(file_to_process):
                processed_audio = await self._process_audio_with_streaming(job, file_info, file_to_process)
            else:
                processed_audio = await self._process_audio_in_memory(job, file_info, file_to_process)

            # CRÍTICO: Salva arquivo processado SEMPRE como .webm
            output_dir = Path("./processed")
            output_dir.mkdir(exist_ok=True, parents=True)
            
            operations_suffix = f"_{job.processing_operations}" if job.processing_operations != "none" else ""
            output_path = output_dir / f"{job.id}{operations_suffix}.webm"
            
            logger.info(f"Salvando arquivo processado como WebM: {output_path}")
            processed_audio.export(
                str(output_path), 
                format="webm",
                codec="libopus",
                parameters=["-strict", "-2"]
            )
            logger.info(f"Arquivo WebM salvo com sucesso. Tamanho: {output_path.stat().st_size} bytes")

            # Finaliza job
            job.output_file = str(output_path)
            job.status = JobStatus.COMPLETED
            job.progress = 100.0
            job.file_size_output = output_path.stat().st_size
            job.completed_at = datetime.now()
            if self.job_store: self.job_store.update_job(job)
            
            logger.info(f"Job {job.id} processado com sucesso. Output: {output_path.name}")

        except AudioNormalizationException:
            raise
        except Exception as e:
            error_msg = f"Erro inesperado no processamento: {str(e)}"
            logger.error(f"Job {job.id} falhou: {error_msg}", exc_info=True)
            job.status = JobStatus.FAILED
            job.error_message = error_msg
            if self.job_store: self.job_store.update_job(job)
            raise AudioNormalizationException(error_msg)
        
        finally:
            # Limpa áudio extraído de vídeo
            if temp_audio_path and Path(temp_audio_path).exists():
                try:
                    Path(temp_audio_path).unlink()
                    logger.info(f"🧹 Áudio temporário removido: {temp_audio_path}")
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao remover áudio temporário: {e}")
            
            # Limpa diretório de extração
            if temp_dir_for_extraction and temp_dir_for_extraction.exists():
                try:
                    import shutil
                    shutil.rmtree(temp_dir_for_extraction, ignore_errors=True)
                    logger.info(f"🧹 Diretório de extração removido")
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao remover diretório de extração: {e}")

    async def _process_audio_in_memory(self, job: Job, file_info: dict, file_path: str = None) -> AudioSegment:
        """Carrega o áudio inteiro na memória e o processa."""
        logger.info("🧠 Processando áudio em memória (arquivo pequeno).")
        
        # Usa file_path fornecido ou job.input_file
        audio_file = file_path or job.input_file
        
        try:
            logger.info(f"Carregando arquivo: {audio_file}")
            # Sempre carrega como áudio (vídeo já foi extraído se necessário)
            audio = AudioSegment.from_file(audio_file)
            logger.info(f"Áudio carregado com sucesso. Formato: {Path(audio_file).suffix}")
        except Exception as e:
            logger.error(f"Erro ao carregar arquivo: {e}")
            raise AudioNormalizationException(f"Não foi possível carregar o arquivo: {str(e)}")

        job.progress = 10.0
        if self.job_store: self.job_store.update_job(job)

        any_operation = (job.remove_noise or job.convert_to_mono or 
                       job.apply_highpass_filter or job.set_sample_rate_16k or 
                       job.isolate_vocals)
        
        if not any_operation:
            logger.info("Nenhuma operação solicitada.")
            job.progress = 90.0
        else:
            logger.info(f"Aplicando operações: {job.processing_operations}")
            audio = await self._apply_processing_operations(audio, job)
        
        if self.job_store: self.job_store.update_job(job)
        return audio

    async def _process_audio_with_streaming(self, job: Job, file_info: dict, file_path: str = None) -> AudioSegment:
        """Processa o áudio em chunks lidos do disco para economizar memória."""
        logger.info("🌊 Processando áudio via streaming (arquivo grande).")
        
        # Usa file_path fornecido ou job.input_file
        audio_file = file_path or job.input_file
        
        # Usa diretório temporário configurado
        base_temp_dir = Path(self.config['temp_dir'])
        base_temp_dir.mkdir(exist_ok=True, parents=True)
        
        # Verifica espaço em disco antes de começar
        if not self._check_disk_space(audio_file, base_temp_dir):
            raise AudioNormalizationException(
                "Espaço em disco insuficiente para processar o arquivo. "
                "Por favor, libere espaço ou tente novamente mais tarde."
            )
        
        # Cria subdiretório para este job
        temp_dir = base_temp_dir / f"job_{job.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        temp_dir.mkdir(exist_ok=True, parents=True)
        logger.info(f"📁 Diretório temporário criado: {temp_dir}")
        
        chunk_paths = []
        processed_chunk_paths = []

        try:
            # 1. Dividir o arquivo em chunks usando ffmpeg
            logger.info(f"Dividindo {audio_file} em chunks de {self.config['chunk_duration_sec']}s...")
            
            # 🔧 CORRIGIDO: Usa WAV ao invés de WebM (compatível com todos os formatos)
            chunk_filename_pattern = str(temp_dir / "chunk_%04d.wav")
            
            ffmpeg_cmd = [
                "ffmpeg", "-i", str(audio_file),
                "-f", "segment",
                "-segment_time", str(self.config['chunk_duration_sec']),
                "-vn",  # Remove vídeo se houver
                "-acodec", "pcm_s16le",  # Codec WAV
                "-ar", "44100",  # Sample rate
                "-ac", "2",  # Stereo
                chunk_filename_pattern
            ]
            
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise AudioNormalizationException(f"Falha ao segmentar áudio com ffmpeg: {stderr.decode()}")

            # 🔧 CORRIGIDO: Procura arquivos WAV
            chunk_paths = sorted(list(temp_dir.glob("chunk_*.wav")))
            if not chunk_paths:
                raise AudioNormalizationException("Nenhum chunk de áudio foi criado pelo ffmpeg.")
            
            logger.info(f"Áudio dividido em {len(chunk_paths)} chunks.")
            job.progress = 20.0
            if self.job_store: self.job_store.update_job(job)

            # 2. Processar cada chunk individualmente
            total_chunks = len(chunk_paths)
            for i, chunk_path in enumerate(chunk_paths):
                progress = 20.0 + (i / total_chunks) * 70.0
                job.progress = progress
                logger.info(f"🔄 Processando chunk {i+1}/{total_chunks} [{progress:.1f}%]...")
                
                try:
                    chunk_audio = AudioSegment.from_file(chunk_path)
                    
                    # Aplica as mesmas operações, mas no chunk
                    processed_chunk = await self._apply_processing_operations(chunk_audio, job, is_chunk=True)
                    
                    # Salva o chunk processado em WAV
                    processed_chunk_path = chunk_path.with_name(f"processed_{chunk_path.name}")
                    processed_chunk.export(processed_chunk_path, format="wav")
                    processed_chunk_paths.append(processed_chunk_path)

                except Exception as e:
                    logger.error(f"Erro ao processar o chunk {chunk_path}: {e}")
                    # Se um chunk falhar, podemos decidir pular ou parar. Por segurança, vamos parar.
                    raise AudioNormalizationException(f"Falha no processamento do chunk {i+1}: {e}")
            
            job.progress = 90.0
            if self.job_store: self.job_store.update_job(job)

            # 3. Mesclar os chunks processados
            if not processed_chunk_paths:
                raise AudioNormalizationException("Nenhum chunk foi processado com sucesso.")
            
            final_audio = self._merge_processed_chunks(processed_chunk_paths)
            return final_audio

        finally:
            # 4. Limpeza dos arquivos temporários (SEMPRE executa)
            import shutil
            try:
                if temp_dir.exists():
                    logger.info(f"🧹 Limpando diretório temporário: {temp_dir}")
                    shutil.rmtree(temp_dir, ignore_errors=False)
                    logger.info(f"✅ Diretório temporário removido com sucesso")
            except Exception as cleanup_error:
                logger.error(f"⚠️ Erro ao limpar diretório temporário {temp_dir}: {cleanup_error}")
                # Tenta remover arquivos individualmente
                try:
                    for file_path in temp_dir.glob("*"):
                        try:
                            file_path.unlink()
                            logger.info(f"   🗑️ Arquivo removido: {file_path.name}")
                        except Exception as file_error:
                            logger.warning(f"   ⚠️ Falha ao remover {file_path.name}: {file_error}")
                except Exception as final_error:
                    logger.error(f"❌ Falha crítica na limpeza: {final_error}")
    
    async def _apply_processing_operations(self, audio: AudioSegment, job: Job, is_chunk: bool = False) -> AudioSegment:
        """Aplica operações de processamento condicionalmente com tratamento robusto de erros"""
        operations_count = sum([
            job.remove_noise, job.convert_to_mono, job.apply_highpass_filter,
            job.set_sample_rate_16k, job.isolate_vocals
        ])
        
        if operations_count == 0:
            return audio
        
        # Se for um chunk, o progresso é gerenciado pelo loop de streaming
        if not is_chunk:
            progress_step = 80.0 / operations_count
            current_progress = 10.0
        
        # 1. Isolamento vocal (primeiro, pois pode afetar outras operações)
        if job.isolate_vocals:
            try:
                logger.info("Aplicando isolamento vocal...")
                audio = await self._isolate_vocals(audio)
                if not is_chunk:
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
                if not is_chunk:
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
                if not is_chunk:
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
                if not is_chunk:
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
                if not is_chunk:
                    current_progress += progress_step
                    job.progress = current_progress
                    if self.job_store:
                        self.job_store.update_job(job)
            except Exception as e:
                logger.error(f"Erro ao ajustar sample rate: {e}")
                raise AudioNormalizationException(f"Falha ao ajustar sample rate: {str(e)}")
        
        return audio
    
    async def _isolate_vocals(self, audio: AudioSegment) -> AudioSegment:
        """Isola vocais usando OpenUnmix com PROCESSAMENTO EM CHUNKS e proteção total contra OOM"""
        if not OPENUNMIX_AVAILABLE:
            logger.error("❌ OpenUnmix não disponível")
            raise AudioNormalizationException("OpenUnmix não está instalado. Use: pip install openunmix-pytorch")
        
        try:
            logger.info(f"🎤 Iniciando isolamento vocal - duração: {len(audio)}ms, canais: {audio.channels}")
            
            # PROTEÇÃO 1: Verifica se deve usar chunking
            if self._should_use_chunking(audio):
                logger.info("📦 Processando vocal isolation em CHUNKS")
                return await self._isolate_vocals_chunked(audio)
            
            # PROTEÇÃO 2: Limita duração para evitar OOM (OpenUnmix é pesado)
            max_duration_ms = self.config['vocal_isolation_max_duration'] * 1000
            original_duration = len(audio)
            if original_duration > max_duration_ms:
                logger.warning(f"⚠️ Áudio muito longo ({original_duration}ms), cortando para {max_duration_ms}ms")
                audio = audio[:max_duration_ms]
            
            # PROTEÇÃO 3: Prepara áudio no formato correto
            original_sample_rate = audio.frame_rate
            target_sample_rate = self.config['vocal_isolation_sample_rate']
            
            if audio.frame_rate != target_sample_rate:
                logger.info(f"🔄 Ajustando sample rate de {audio.frame_rate} para {target_sample_rate}")
                audio = audio.set_frame_rate(target_sample_rate)
            
            # PROTEÇÃO 4: Garante que é estéreo (OpenUnmix precisa de estéreo)
            original_channels = audio.channels
            if audio.channels == 1:
                logger.info("🔄 Convertendo mono para estéreo (OpenUnmix requer estéreo)")
                audio = audio.set_channels(2)
            
            # PROTEÇÃO 5: Converte para numpy array
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
            
            # PROTEÇÃO 6: Carrega modelo
            try:
                model = self._load_openunmix_model()
            except Exception as model_err:
                logger.error(f"💥 Erro ao carregar modelo: {model_err}")
                raise AudioNormalizationException(f"Failed to load OpenUnmix model: {str(model_err)}")
            
            # PROTEÇÃO 7: Aplica isolamento vocal
            try:
                logger.info("🎯 Aplicando separação de fontes com OpenUnmix...")
                
                # Converte para tensor PyTorch (channels x samples)
                audio_tensor = torch.from_numpy(samples_float.T).unsqueeze(0)
                logger.info(f"📊 Tensor criado: shape={audio_tensor.shape}")
                
                # Inferência sem gradientes (economia de memória)
                with torch.no_grad():
                    # Aplica modelo
                    if hasattr(model, '__call__') and hasattr(model, '__name__') and model.__name__ == 'separate':
                        # É a função separate() - precisa de outros parâmetros
                        logger.info("🎯 Usando openunmix.predict.separate()")
                        # separate() retorna dict com todas as fontes
                        result = model(
                            audio_tensor,
                            rate=target_sample_rate,
                            device='cpu'
                        )
                        # Extrai apenas vocais
                        vocals_tensor = result.get('vocals', audio_tensor) if isinstance(result, dict) else result
                    else:
                        # É um modelo (callable direto)
                        logger.info("🎯 Usando modelo OpenUnmix direto")
                        vocals_tensor = model(audio_tensor)
                    
                    logger.info(f"📊 Tensor de saída: shape={vocals_tensor.shape}")
                    
                    # Extrai apenas vocais e converte para numpy
                    vocals_np = vocals_tensor.squeeze(0).cpu().numpy()
                
                logger.info("✅ Separação concluída")
                
            except Exception as openunmix_err:
                logger.error(f"💥 OpenUnmix falhou: {openunmix_err}", exc_info=True)
                raise AudioNormalizationException(f"Vocal isolation failed: {str(openunmix_err)}")
            
            # PROTEÇÃO 8: Converte resultado de volta para AudioSegment
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
    
    async def _isolate_vocals_chunked(self, audio: AudioSegment) -> AudioSegment:
        """
        Isola vocais processando áudio em chunks
        Usado para áudios muito grandes que causariam OOM com OpenUnmix
        """
        logger.info("📦 Iniciando vocal isolation em CHUNKS")
        
        # Divide em chunks
        chunks = self._split_audio_into_chunks(audio)
        processed_chunks = []
        
        for i, (start_ms, end_ms, chunk) in enumerate(chunks):
            logger.info(f"🔄 Processando chunk {i+1}/{len(chunks)} ({start_ms/1000:.1f}s - {end_ms/1000:.1f}s)")
            
            try:
                # Processa chunk individualmente
                original_chunking = self.config['chunking_enabled']
                self.config['chunking_enabled'] = False
                
                processed_chunk = await self._isolate_vocals(chunk)
                
                self.config['chunking_enabled'] = original_chunking
                
                processed_chunks.append(processed_chunk)
                
            except Exception as chunk_err:
                logger.error(f"💥 Erro ao processar chunk {i+1}: {chunk_err}")
                # Se um chunk falhar, usa chunk original
                processed_chunks.append(chunk)
        
        # Mescla chunks
        overlap_ms = self.config['chunk_overlap_sec'] * 1000
        merged_audio = self._merge_chunks(processed_chunks, overlap_ms)
        
        logger.info("✅ Vocal isolation em chunks concluída")
        return merged_audio
    
    async def _remove_noise(self, audio: AudioSegment) -> AudioSegment:
        """Remove ruído usando noisereduce com PROCESSAMENTO EM CHUNKS e proteção total"""
        try:
            logger.info(f"🔇 Iniciando remoção de ruído - duração: {len(audio)}ms, canais: {audio.channels}, sample_rate: {audio.frame_rate}")
            
            # PROTEÇÃO 1: Verifica se deve usar chunking
            if self._should_use_chunking(audio):
                logger.info("📦 Processando noise reduction em CHUNKS")
                return await self._remove_noise_chunked(audio)
            
            # PROTEÇÃO 2: Limita duração para processamento direto
            max_duration_ms = self.config['noise_reduction_max_duration'] * 1000
            original_duration = len(audio)
            if original_duration > max_duration_ms:
                logger.warning(f"⚠️ Áudio muito longo ({original_duration}ms), cortando para {max_duration_ms}ms")
                audio = audio[:max_duration_ms]
            
            # PROTEÇÃO 3: Converte para mono para reduzir uso de memória
            original_channels = audio.channels
            if audio.channels > 1:
                logger.info("🔄 Convertendo para mono temporariamente para economizar memória")
                audio_mono = audio.set_channels(1)
            else:
                audio_mono = audio
            
            # PROTEÇÃO 4: Reduz sample rate se muito alto
            target_sample_rate = self.config['noise_reduction_sample_rate']
            original_sample_rate = audio_mono.frame_rate
            if audio_mono.frame_rate > target_sample_rate:
                logger.info(f"🔄 Reduzindo sample rate de {audio_mono.frame_rate} para {target_sample_rate}")
                audio_mono = audio_mono.set_frame_rate(target_sample_rate)
            
            # PROTEÇÃO 5: Converte para numpy com tipo correto
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
                
                # PROTEÇÃO 6: Verifica se tem valores válidos
                if np.isnan(samples_float).any() or np.isinf(samples_float).any():
                    logger.error("❌ Array contém NaN ou Inf após normalização")
                    raise ValueError("Audio array contains invalid values (NaN or Inf)")
                
            except Exception as array_err:
                logger.error(f"💥 Erro ao preparar array para noise reduction: {array_err}")
                raise AudioNormalizationException(f"Failed to prepare audio array: {str(array_err)}")
            
            logger.info(f"🎯 Aplicando noisereduce em {len(samples_float)} samples @ {audio_mono.frame_rate}Hz")
            
            # PROTEÇÃO 7: Aplica redução de ruído com parâmetros conservadores e try/except
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
            
            # PROTEÇÃO 8: Valida output e converte de volta para int16
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
            
            # PROTEÇÃO 9: Cria AudioSegment processado
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
    
    async def _remove_noise_chunked(self, audio: AudioSegment) -> AudioSegment:
        """
        Remove ruído processando áudio em chunks
        Usado para áudios muito grandes que não cabem na memória
        """
        logger.info("📦 Iniciando noise reduction em CHUNKS")
        
        # Divide em chunks
        chunks = self._split_audio_into_chunks(audio)
        processed_chunks = []
        
        for i, (start_ms, end_ms, chunk) in enumerate(chunks):
            logger.info(f"🔄 Processando chunk {i+1}/{len(chunks)} ({start_ms/1000:.1f}s - {end_ms/1000:.1f}s)")
            
            try:
                # Processa chunk individualmente (recursivamente chama método sem chunking)
                # Temporariamente desabilita chunking para processar chunk individual
                original_chunking = self.config['chunking_enabled']
                self.config['chunking_enabled'] = False
                
                processed_chunk = await self._remove_noise(chunk)
                
                # Restaura setting
                self.config['chunking_enabled'] = original_chunking
                
                processed_chunks.append(processed_chunk)
                
            except Exception as chunk_err:
                logger.error(f"💥 Erro ao processar chunk {i+1}: {chunk_err}")
                # Se um chunk falhar, usa chunk original
                processed_chunks.append(chunk)
        
        # Mescla chunks
        overlap_ms = self.config['chunk_overlap_sec'] * 1000
        merged_audio = self._merge_chunks(processed_chunks, overlap_ms)
        
        logger.info("✅ Noise reduction em chunks concluída")
        return merged_audio
    
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