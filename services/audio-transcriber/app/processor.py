import os
import asyncio
from pathlib import Path
import logging
import torch
from pydub import AudioSegment
from .models import Job, JobStatus, TranscriptionSegment
from .exceptions import AudioTranscriptionException
from .config import get_settings
from .faster_whisper_manager import FasterWhisperModelManager
import time

logger = logging.getLogger(__name__)


class TranscriptionProcessor:
    def __init__(self, output_dir=None, model_dir=None):
        self.job_store = None  # Will be injected
        self.settings = get_settings()
        self.output_dir = output_dir or self.settings.get('transcription_dir', './transcriptions')
        self.model_dir = model_dir or self.settings.get('whisper_download_root', './models')
        
        # Usa FasterWhisperModelManager
        self.model_manager = FasterWhisperModelManager(model_dir=Path(self.model_dir))
        self.model = None  # Para compatibilidade
        self.device = None
        self.model_loaded = False
    
    def _check_disk_space(self, file_path: str, output_dir: str) -> bool:
        """Verifica se há espaço em disco suficiente para transcrição."""
        try:
            import shutil
            
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            
            # Estima espaço necessário: 2x o tamanho do arquivo (transcripts são pequenos, mas previne)
            estimated_space_needed = file_size * 2
            
            stat = shutil.disk_usage(output_dir)
            available_space = stat.free
            available_space_mb = available_space / (1024 * 1024)
            
            logger.info(f"💾 Espaço em disco - Disponível: {available_space_mb:.2f}MB, Estimado necessário: {estimated_space_needed/(1024*1024):.2f}MB")
            
            if available_space < estimated_space_needed:
                logger.error(f"❌ Espaço em disco insuficiente! Disponível: {available_space_mb:.2f}MB")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Não foi possível verificar espaço em disco: {e}")
            return True  # fail-open
    
    def _detect_device(self):
        """Detecta dispositivo (delegado para FasterWhisperModelManager)"""
        # Faster-whisper detecta automaticamente
        return self.model_manager.device
    
    def _load_model(self):
        """Carrega modelo usando FasterWhisperModelManager"""
        if not self.model_loaded:
            logger.info("📦 Carregando Faster-Whisper...")
            self.model_manager.load_model()
            self.device = self.model_manager.device
            self.model_loaded = True
            logger.info(f"✅ Faster-Whisper carregado no {self.device.upper()}")

    def _test_gpu(self):
        """Legacy method - faster-whisper handles GPU automatically"""
        pass
    
    def unload_model(self) -> dict:
        """
        Descarrega modelo Whisper da memória/GPU para economia de recursos.
        
        Libera:
        - Memória RAM (~500MB - 3GB dependendo do modelo)
        - Memória GPU/VRAM (se CUDA disponível)
        - Reduz consumo energético
        - Reduz pegada de carbono
        
        Returns:
            dict: Relatório com memória liberada e status
        """
        try:
            report = {
                "success": False,
                "message": "",
                "memory_freed": {
                    "ram_mb": 0.0,
                    "vram_mb": 0.0
                },
                "device_was": None,
                "model_name": self.settings.get('whisper_model', 'base')
            }
            
            if self.model is None or not self.model_loaded:
                report["message"] = "Modelo já estava descarregado"
                report["success"] = True
                logger.info("ℹ️ Modelo Whisper já estava descarregado")
                return report
            
            # Captura informações antes de descarregar
            report["device_was"] = self.device
            
            # Se está na GPU, captura uso de memória ANTES
            vram_before = 0.0
            if self.device == 'cuda' and torch.cuda.is_available():
                vram_before = torch.cuda.memory_allocated(0) / 1024**2  # MB
                logger.info(f"📊 VRAM antes do unload: {vram_before:.2f} MB")
            
            # Remove modelo
            logger.warning(f"🔥 Descarregando modelo Whisper '{report['model_name']}' do {self.device}...")
            
            del self.model
            self.model = None
            self.model_loaded = False
            self.device = None
            
            # Força garbage collection
            import gc
            gc.collect()
            
            # Se estava na GPU, limpa cache CUDA
            if report["device_was"] == 'cuda' and torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()  # Aguarda operações GPU finalizarem
                
                # Captura memória APÓS
                vram_after = torch.cuda.memory_allocated(0) / 1024**2  # MB
                report["memory_freed"]["vram_mb"] = round(vram_before - vram_after, 2)
                
                logger.info(f"📊 VRAM depois do unload: {vram_after:.2f} MB")
                logger.info(f"✅ VRAM liberada: {report['memory_freed']['vram_mb']} MB")
            
            # Estima RAM liberada baseado no modelo
            # tiny: ~75MB, base: ~150MB, small: ~500MB, medium: ~1.5GB, large: ~3GB
            model_sizes = {
                'tiny': 75,
                'base': 150,
                'small': 500,
                'medium': 1500,
                'large': 3000
            }
            report["memory_freed"]["ram_mb"] = model_sizes.get(report['model_name'], 150)
            
            report["success"] = True
            report["message"] = (
                f"✅ Modelo '{report['model_name']}' descarregado com sucesso do {report['device_was'].upper()}. "
                f"Recursos liberados para economia de energia e redução de pegada de carbono. "
                f"Modelo será recarregado automaticamente quando houver nova task."
            )
            
            logger.warning(f"♻️ Modelo Whisper DESCARREGADO - Economia de recursos ativada")
            logger.info(f"   └─ RAM liberada (estimado): ~{report['memory_freed']['ram_mb']} MB")
            if report["memory_freed"]["vram_mb"] > 0:
                logger.info(f"   └─ VRAM liberada: {report['memory_freed']['vram_mb']} MB")
            logger.info(f"   └─ Dispositivo anterior: {report['device_was'].upper()}")
            
            return report
            
        except Exception as e:
            error_msg = f"Erro ao descarregar modelo: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "message": error_msg,
                "memory_freed": {"ram_mb": 0.0, "vram_mb": 0.0}
            }
    
    def load_model_explicit(self) -> dict:
        """
        Carrega modelo Whisper explicitamente na memória/GPU.
        
        Útil para:
        - Pré-carregar modelo antes de processar batch de tasks
        - Reduzir latência da primeira transcrição
        - Preparar sistema após unload manual
        
        Returns:
            dict: Relatório com memória usada e status
        """
        try:
            report = {
                "success": False,
                "message": "",
                "memory_used": {
                    "ram_mb": 0.0,
                    "vram_mb": 0.0
                },
                "device": None,
                "model_name": self.settings.get('whisper_model', 'base')
            }
            
            if self.model is not None and self.model_loaded:
                report["success"] = True
                report["device"] = self.device
                report["message"] = f"Modelo já estava carregado no {self.device.upper()}"
                logger.info(f"ℹ️ Modelo Whisper já carregado no {self.device}")
                return report
            
            logger.info(f"🚀 Carregando modelo Whisper '{report['model_name']}' explicitamente...")
            
            # Captura memória GPU ANTES (se disponível)
            vram_before = 0.0
            if torch.cuda.is_available():
                vram_before = torch.cuda.memory_allocated(0) / 1024**2  # MB
            
            # Carrega modelo (usa _load_model que já tem lógica de retry e device detection)
            self._load_model()
            
            report["success"] = True
            report["device"] = self.device
            
            # Captura memória GPU DEPOIS
            if self.device == 'cuda' and torch.cuda.is_available():
                vram_after = torch.cuda.memory_allocated(0) / 1024**2  # MB
                report["memory_used"]["vram_mb"] = round(vram_after - vram_before, 2)
                logger.info(f"📊 VRAM usada: {report['memory_used']['vram_mb']} MB")
            
            # Estima RAM usada baseado no modelo
            model_sizes = {
                'tiny': 75,
                'base': 150,
                'small': 500,
                'medium': 1500,
                'large': 3000
            }
            report["memory_used"]["ram_mb"] = model_sizes.get(report['model_name'], 150)
            
            report["message"] = (
                f"✅ Modelo '{report['model_name']}' carregado com sucesso no {self.device.upper()}. "
                f"Sistema pronto para transcrições de baixa latência."
            )
            
            logger.info(f"✅ Modelo carregado explicitamente")
            logger.info(f"   └─ Dispositivo: {self.device.upper()}")
            logger.info(f"   └─ RAM usada (estimado): ~{report['memory_used']['ram_mb']} MB")
            if report["memory_used"]["vram_mb"] > 0:
                logger.info(f"   └─ VRAM usada: {report['memory_used']['vram_mb']} MB")
            
            return report
            
        except Exception as e:
            error_msg = f"Erro ao carregar modelo: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "message": error_msg,
                "memory_used": {"ram_mb": 0.0, "vram_mb": 0.0}
            }
    
    def get_model_status(self) -> dict:
        """
        Retorna status atual do modelo.
        
        Returns:
            dict: Status do modelo (loaded/unloaded, device, memory, etc)
        """
        status = {
            "loaded": self.model_loaded and self.model is not None,
            "model_name": self.settings.get('whisper_model', 'base'),
            "device": self.device if self.model_loaded else None,
            "memory": {
                "vram_mb": 0.0,
                "cuda_available": torch.cuda.is_available()
            }
        }
        
        # Se modelo está carregado na GPU, mostra uso de VRAM
        if status["loaded"] and self.device == 'cuda' and torch.cuda.is_available():
            status["memory"]["vram_mb"] = round(torch.cuda.memory_allocated(0) / 1024**2, 2)
            status["memory"]["vram_reserved_mb"] = round(torch.cuda.memory_reserved(0) / 1024**2, 2)
            
            # Informações da GPU
            status["gpu_info"] = {
                "name": torch.cuda.get_device_name(0),
                "device_count": torch.cuda.device_count(),
                "cuda_version": torch.version.cuda
            }
        
        return status
    
    def transcribe_audio(self, job: Job) -> Job:
        """
        Método síncrono para Celery task processar transcrição
        Converte o processamento assíncrono em síncrono
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(self.process_transcription_job(job))
        return job
    
    async def process_transcription_job(self, job: Job):
        """Processa um job de transcrição"""
        try:
            logger.info(f"Iniciando processamento do job: {job.id}")
            
            # Define current_job_id para permitir atualizações de progresso durante chunking
            self.current_job_id = job.id
            
            # ==========================================
            # VALIDAÇÃO CRÍTICA: Verifica se arquivo existe
            # ==========================================
            input_path = Path(job.input_file)
            
            # Tenta encontrar arquivo em múltiplos caminhos possíveis
            possible_paths = [
                input_path,  # Caminho original
                Path("/app") / job.input_file if not input_path.is_absolute() else input_path,  # /app/uploads/...
                Path("/app/uploads") / input_path.name,  # /app/uploads/filename
                Path("./uploads") / input_path.name,  # ./uploads/filename
            ]
            
            actual_file_path = None
            for path in possible_paths:
                if path.exists() and path.is_file():
                    actual_file_path = path
                    logger.info(f"✅ Arquivo encontrado em: {path}")
                    break
                else:
                    logger.debug(f"⚠️ Arquivo NÃO encontrado em: {path}")
            
            if actual_file_path is None:
                error_msg = (
                    f"Arquivo de entrada não encontrado! "
                    f"Procurado em: {[str(p) for p in possible_paths]}. "
                    f"Verifique se o arquivo foi enviado corretamente."
                )
                logger.error(f"❌ {error_msg}")
                raise AudioTranscriptionException(error_msg)
            
            # Valida que o arquivo não está vazio
            file_size = actual_file_path.stat().st_size
            if file_size == 0:
                raise AudioTranscriptionException(
                    f"Arquivo de entrada está vazio (0 bytes): {actual_file_path}"
                )
            
            logger.info(f"📁 Arquivo validado: {actual_file_path} ({file_size / (1024*1024):.2f} MB)")
            
            # Atualiza job com caminho correto e absoluto
            job.input_file = str(actual_file_path.absolute())
            job.file_size_input = file_size
            
            # Verifica espaço em disco
            if not self._check_disk_space(job.input_file, self.output_dir):
                raise AudioTranscriptionException(
                    "Espaço em disco insuficiente para transcrição. "
                    "Libere espaço ou tente novamente mais tarde."
                )
            
            # Atualiza status para processando
            job.status = JobStatus.PROCESSING
            if self.job_store:
                self.job_store.update_job(job)
            
            logger.info(f"🎵 Processando arquivo: {job.input_file}")
            
            # Carrega modelo se necessário
            self._load_model()
            
            # Atualiza progresso
            job.progress = 25.0
            if self.job_store:
                self.job_store.update_job(job)
            
            # Decide se usa chunking baseado nas configurações e duração do áudio
            enable_chunking = self.settings.get('enable_chunking', False)
            
            if enable_chunking:
                # Verifica duração do áudio para decidir se vale a pena usar chunks
                audio = AudioSegment.from_file(job.input_file)
                duration_seconds = len(audio) / 1000.0
                
                # Usa chunking apenas para áudios longos (configurável, padrão 5 min = 300s)
                min_duration_for_chunks = int(self.settings.get('whisper_min_duration_for_chunks', 300))
                
                if duration_seconds > min_duration_for_chunks:
                    logger.info(f"Áudio longo detectado ({duration_seconds:.1f}s), usando chunking")
                    result = await self._transcribe_with_chunking(job.input_file, job.language_in, job.language_out, audio)
                else:
                    logger.info(f"Áudio curto ({duration_seconds:.1f}s), transcrição direta")
                    result = self._transcribe_direct(job.input_file, job.language_in, job.language_out)
            else:
                logger.info("Chunking desabilitado, transcrição direta")
                result = self._transcribe_direct(job.input_file, job.language_in, job.language_out)
            
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
            transcription_dir = Path(self.output_dir)
            transcription_dir.mkdir(parents=True, exist_ok=True)
            
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
            
            # Armazena idioma detectado pelo Whisper (se disponível)
            if "language" in result:
                job.language_detected = result["language"]
                logger.info(f"Idioma detectado pelo Whisper: {result['language']}")
            
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
    
    def _transcribe_direct(self, audio_file: str, language_in: str = "auto", language_out: str = None):
        """
        Transcrição ou tradução direta sem chunking
        
        Args:
            audio_file: Caminho do arquivo de áudio
            language_in: Idioma de entrada ("auto" para detecção automática)
            language_out: Idioma de saída para tradução (None = apenas transcrever)
        
        Returns:
            dict: Resultado com 'text', 'segments' e 'language' detectado
        """
        logger.info(f"🎙️ Transcrevendo diretamente: {audio_file}")
        
        # Valida que arquivo existe ANTES de processar
        audio_path = Path(audio_file)
        if not audio_path.exists():
            raise AudioTranscriptionException(
                f"Arquivo de áudio não encontrado para transcrição: {audio_file}"
            )
        
        # Valida que arquivo não está vazio
        if audio_path.stat().st_size == 0:
            raise AudioTranscriptionException(
                f"Arquivo de áudio está vazio: {audio_file}"
            )
        
        # Se language_out for especificado e diferente de language_in, usa translate
        needs_translation = language_out is not None and language_out != language_in and language_in != ''
        
        if needs_translation:
            logger.info(f"Traduzindo de {language_in} para {language_out}")
            # Whisper translate() sempre traduz para inglês
            # Se language_out não for inglês, teremos que fazer em 2 etapas
            if language_out.lower() not in ['en', 'english']:
                logger.warning(f"Whisper só traduz para inglês. Tradução para {language_out} não suportada diretamente.")
                # Fallback: apenas transcreve no idioma original
                needs_translation = False
        
        ##############################################################
        # CONFIGURAÇÃO DE OPÇÕES DO WHISPER
        ##############################################################
        base_options = {
            "fp16": self.settings.get('whisper_fp16', False),
            #"beam_size": self.settings.get('whisper_beam_size', 5),
            #"best_of": self.settings.get('whisper_best_of', 5),
            #"temperature": self.settings.get('whisper_temperature', 0.0)
        }
        
        # Retry com backoff exponencial para lidar com problemas temporários
        max_retries = 3
        retry_delay = 2.0
        last_error = None
        
        for attempt in range(max_retries):
            try:
                if needs_translation:
                    # Traduzir para inglês usando task="translate" explicitamente
                    logger.info(f"🌐 Usando Faster-Whisper task='translate' para traduzir para inglês (tentativa {attempt + 1}/{max_retries})")
                    result = self.model_manager.transcribe(
                        Path(audio_file),
                        language=None if language_in == "auto" else language_in,
                        task="translate",
                        **base_options
                    )
                    logger.info(f"✅ Tradução concluída. Idioma detectado: {result.get('language', 'unknown')}")
                else:
                    # Transcrever no idioma original usando task="transcribe" explicitamente
                    logger.info(f"📝 Usando Faster-Whisper task='transcribe' para transcrever em {language_in} (tentativa {attempt + 1}/{max_retries})")
                    result = self.model_manager.transcribe(
                        Path(audio_file),
                        language=None if language_in == "auto" else language_in,
                        task="transcribe",
                        **base_options
                    )
                    logger.info(f"✅ Transcrição concluída. Idioma: {result.get('language', language_in)}")
                
                return result
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                logger.error(f"❌ Erro na transcrição (tentativa {attempt + 1}/{max_retries}): {error_msg}")
                
                # Se é o último retry, lança exceção
                if attempt == max_retries - 1:
                    logger.error(f"❌ Todas as tentativas falharam. Último erro: {error_msg}")
                    raise AudioTranscriptionException(f"Falha após {max_retries} tentativas: {error_msg}")
                
                # Aguarda antes de tentar novamente (backoff exponencial)
                sleep_time = retry_delay * (2 ** attempt)
                logger.info(f"⏳ Aguardando {sleep_time}s antes de tentar novamente...")
                time.sleep(sleep_time)
        
        # Nunca deve chegar aqui, mas por segurança
        raise AudioTranscriptionException(f"Falha inesperada na transcrição: {last_error}")
    
    async def _transcribe_with_chunking(self, audio_file: str, language_in: str, language_out: str = None, audio: AudioSegment = None):
        """
        Transcreve ou traduz áudio longo usando chunking para acelerar o processamento
        
        Args:
            audio_file: Caminho do arquivo de áudio
            language_in: Idioma de entrada para transcrição ("auto" para detecção)
            language_out: Idioma de saída para tradução (None = apenas transcrever)
            audio: AudioSegment já carregado (opcional, para evitar recarregar)
        
        Returns:
            dict: Resultado com 'text' e 'segments' no formato Whisper
        """
        try:
            # Valida que arquivo existe
            audio_path = Path(audio_file)
            if not audio_path.exists():
                raise AudioTranscriptionException(
                    f"Arquivo de áudio não encontrado para chunking: {audio_file}"
                )
            
            # Carrega áudio se não foi fornecido
            if audio is None:
                logger.info(f"🎵 Carregando áudio para chunking: {audio_file}")
                try:
                    audio = AudioSegment.from_file(str(audio_path))
                except Exception as e:
                    raise AudioTranscriptionException(
                        f"Erro ao carregar arquivo de áudio com pydub: {str(e)}"
                    )
            
            duration_ms = len(audio)
            duration_seconds = duration_ms / 1000.0
            
            # Configurações de chunking
            chunk_length_seconds = self.settings.get('chunk_length_seconds', 30)
            overlap_seconds = self.settings.get('chunk_overlap_seconds', 1.0)
            
            chunk_length_ms = chunk_length_seconds * 1000
            overlap_ms = overlap_seconds * 1000
            
            logger.info(f"Processando áudio de {duration_seconds:.1f}s em chunks de {chunk_length_seconds}s com overlap de {overlap_seconds}s")
            
            # Divide áudio em chunks com overlap
            chunks = []
            current_position = 0
            chunk_number = 0
            
            while current_position < duration_ms:
                # Define limites do chunk
                end_position = min(current_position + chunk_length_ms, duration_ms)
                
                # Extrai chunk
                chunk = audio[current_position:end_position]
                chunks.append({
                    'audio': chunk,
                    'start_time': current_position / 1000.0,
                    'number': chunk_number
                })
                
                chunk_number += 1
                
                # Move para próximo chunk (com overlap)
                current_position += chunk_length_ms - overlap_ms
            
            logger.info(f"Áudio dividido em {len(chunks)} chunks")
            
            # Processa cada chunk
            all_segments = []
            full_text_parts = []
            
            temp_dir = Path(self.settings.get('temp_dir', './temp'))
            temp_dir.mkdir(exist_ok=True)
            
            for i, chunk_data in enumerate(chunks):
                # Salva chunk temporariamente
                chunk_file = temp_dir / f"chunk_{i}.wav"
                chunk_data['audio'].export(chunk_file, format="wav")
                
                logger.info(f"Processando chunk {i+1}/{len(chunks)} (offset: {chunk_data['start_time']:.1f}s)")
                
                # Transcreve ou traduz chunk
                chunk_result = self._transcribe_direct(str(chunk_file), language_in, language_out)
                
                # Ajusta timestamps dos segmentos com o offset do chunk
                for segment in chunk_result['segments']:
                    adjusted_segment = segment.copy()
                    adjusted_segment['start'] += chunk_data['start_time']
                    adjusted_segment['end'] += chunk_data['start_time']
                    all_segments.append(adjusted_segment)
                
                full_text_parts.append(chunk_result['text'])
                
                # Remove arquivo temporário
                chunk_file.unlink()
                
                # Atualiza progresso (25% inicial + 50% durante chunks)
                if self.job_store and hasattr(self, 'current_job_id'):
                    try:
                        progress = 25.0 + (50.0 * (i + 1) / len(chunks))
                        job = self.job_store.get_job(self.current_job_id)
                        if job:
                            job.progress = progress
                            self.job_store.update_job(job)
                            logger.info(f"✅ Progresso atualizado: {progress:.1f}% (chunk {i+1}/{len(chunks)})")
                    except Exception as e:
                        logger.error(f"❌ Erro ao atualizar progresso: {e}")
            
            # Mescla segmentos sobrepostos (remove duplicatas no overlap)
            merged_segments = self._merge_overlapping_segments(all_segments, overlap_seconds)
            
            # Combina texto completo
            full_text = " ".join(full_text_parts)
            
            logger.info(f"Chunking concluído: {len(merged_segments)} segmentos finais")
            
            return {
                "text": full_text,
                "segments": merged_segments
            }
            
        except Exception as e:
            logger.error(f"Erro no chunking: {e}")
            raise AudioTranscriptionException(f"Falha no chunking: {str(e)}")
    
    def _merge_overlapping_segments(self, segments: list, overlap_seconds: float) -> list:
        """
        Mescla segmentos sobrepostos removendo duplicatas
        
        Args:
            segments: Lista de segmentos com timestamps
            overlap_seconds: Duração do overlap em segundos
        
        Returns:
            list: Segmentos mesclados sem duplicatas
        """
        if not segments:
            return []
        
        # Ordena por tempo de início
        sorted_segments = sorted(segments, key=lambda s: s['start'])
        
        merged = []
        for segment in sorted_segments:
            # Se não há overlap com o último segmento adicionado, adiciona normalmente
            if not merged or segment['start'] >= merged[-1]['end']:
                merged.append(segment)
            else:
                # Há overlap - verifica se é texto duplicado
                last_text = merged[-1]['text'].strip()
                current_text = segment['text'].strip()
                
                # Se textos são muito similares (>80% igual), ignora o segmento duplicado
                if self._text_similarity(last_text, current_text) > 0.8:
                    # Atualiza apenas o tempo de fim se necessário
                    if segment['end'] > merged[-1]['end']:
                        merged[-1]['end'] = segment['end']
                else:
                    # Textos diferentes, adiciona o segmento
                    merged.append(segment)
        
        return merged
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calcula similaridade simples entre dois textos (0.0 a 1.0)"""
        if not text1 or not text2:
            return 0.0
        
        # Similaridade baseada em palavras em comum
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
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