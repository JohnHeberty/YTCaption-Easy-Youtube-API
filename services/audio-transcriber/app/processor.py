import os
import asyncio
from pathlib import Path
import whisper
import torch
import logging
from pydub import AudioSegment
from .models import Job, JobStatus, TranscriptionSegment
from .exceptions import AudioTranscriptionException
from .config import get_settings
import time

logger = logging.getLogger(__name__)


class TranscriptionProcessor:
    def __init__(self, output_dir=None, model_dir=None):
        self.job_store = None  # Will be injected
        self.model = None  # Lazy loading
        self.settings = get_settings()
        self.output_dir = output_dir or self.settings.get('transcription_dir', './transcriptions')
        self.model_dir = model_dir or self.settings.get('whisper_download_root', './models')
        self.device = None  # Will be set in _load_model
    
    def _detect_device(self):
        """Detecta e valida dispositivo (CUDA/CPU) disponível"""
        requested_device = self.settings.get('whisper_device', 'cpu').lower()
        
        # Verifica disponibilidade de CUDA
        cuda_available = torch.cuda.is_available()
        
        if cuda_available:
            device_count = torch.cuda.device_count()
            device_name = torch.cuda.get_device_name(0)
            cuda_version = torch.version.cuda
            logger.info(f"🎮 CUDA DISPONÍVEL!")
            logger.info(f"   └─ GPUs detectadas: {device_count}")
            logger.info(f"   └─ GPU 0: {device_name}")
            logger.info(f"   └─ CUDA Version: {cuda_version}")
            logger.info(f"   └─ PyTorch Version: {torch.__version__}")
        else:
            logger.warning("⚠️ CUDA NÃO DISPONÍVEL - usando CPU")
            logger.info(f"   └─ PyTorch Version: {torch.__version__}")
            logger.info(f"   └─ CUDA Built: {torch.version.cuda}")
        
        # Decide qual dispositivo usar
        if requested_device == 'cuda':
            if cuda_available:
                device = 'cuda'
                logger.info(f"✅ Usando GPU (CUDA)")
            else:
                device = 'cpu'
                logger.warning(f"⚠️ CUDA solicitado mas não disponível. Fallback para CPU.")
        else:
            device = 'cpu'
            logger.info(f"ℹ️ Usando CPU (conforme configuração)")
        
        return device
    
    def _load_model(self):
        """Carrega modelo Whisper (lazy loading) com detecção de GPU"""
        if self.model is None:
            try:
                model_name = self.settings.get('whisper_model', 'base')
                tries = int(self.settings.get('model_load_retries', 3))
                delay = float(self.settings.get('model_load_backoff', 2.0))
                download_root = self.model_dir
                last_err = None
                
                for i in range(tries):
                    try:
                        
                        # Detecta dispositivo disponível
                        self.device = self._detect_device()
                        
                        logger.info(f"📦 Carregando modelo Whisper: {model_name}")
                        logger.info(f"   └─ Dispositivo: {self.device}")
                        logger.info(f"   └─ Diretório: {download_root}")
                        
                        # Garante que o diretório existe
                        Path(download_root).mkdir(parents=True, exist_ok=True)
                        
                        # Testa GPU se disponível
                        if self.device == 'cuda':
                            try:
                                self._test_gpu()
                            except Exception:
                                self.logger.warning("Falha no teste da GPU, trocando para CPU…")
                                self.device = 'cpu'
                                
                        # Carrega modelo
                        self.model = whisper.load_model(model_name, device=self.device, download_root=download_root)
                        
                        logger.info(f"✅ Modelo Whisper carregado com sucesso no {self.device.upper()}")
                            
                        return
                    except Exception as e:
                        last_err = e
                        logger.error(f"❌ Falha ao carregar modelo (tentativa {i+1}/{tries}): {e}")
                        if i < tries - 1:
                            time_sleep = delay * (2 ** i)
                            logger.info(f"⏳ Retentando em {time_sleep} segundos...")
                            time.sleep(time_sleep)
            except Exception as e:
                logger.error(f"❌ Erro ao carregar modelo Whisper: {e}")
                raise AudioTranscriptionException(f"Falha ao carregar modelo após {tries} tentativas: {last_err}")

    def _test_gpu(self):
        """Testa se GPU está realmente funcionando"""
        try:
            # Cria tensor de teste na GPU
            test_tensor = torch.randn(1000, 1000).to('cuda')
            result = test_tensor @ test_tensor.T
            
            # Verifica memória GPU
            memory_allocated = torch.cuda.memory_allocated(0) / 1024**2  # MB
            memory_reserved = torch.cuda.memory_reserved(0) / 1024**2    # MB
            
            logger.info(f"🔥 GPU funcionando corretamente!")
            logger.info(f"   └─ Memória Alocada: {memory_allocated:.2f} MB")
            logger.info(f"   └─ Memória Reservada: {memory_reserved:.2f} MB")
            
            # Limpa tensor de teste
            del test_tensor, result
            torch.cuda.empty_cache()
            
        except Exception as e:
            logger.error(f"⚠️ Erro ao testar GPU: {e}")
            logger.warning("GPU pode não estar funcionando corretamente")
    
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
        logger.info(f"Transcrevendo diretamente: {audio_file}")
        
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
        #############################################################
        ##########################################################
        base_options = {
            "fp16": self.settings.get('whisper_fp16', False),
            #"beam_size": self.settings.get('whisper_beam_size', 5),
            #"best_of": self.settings.get('whisper_best_of', 5),
            #"temperature": self.settings.get('whisper_temperature', 0.0)
        }
        
        if needs_translation:
            # Traduzir para inglês usando task="translate" explicitamente
            transcribe_options = base_options.copy()
            transcribe_options["task"] = "translate"  # Força tradução para inglês
            # Não especifica language para deixar Whisper detectar automaticamente
            logger.info("Usando Whisper com task='translate' para traduzir para inglês")
            result = self.model.transcribe(audio_file, **transcribe_options)
            logger.info(f"Tradução concluída. Idioma detectado: {result.get('language', 'unknown')}")
        else:
            # Transcrever no idioma original usando task="transcribe" explicitamente
            transcribe_options = base_options.copy()
            transcribe_options["task"] = "transcribe"  # Força transcrição no idioma original
            transcribe_options["language"] = None if language_in == "auto" else language_in
            logger.info(f"Usando Whisper com task='transcribe' para transcrever em {language_in}")
            result = self.model.transcribe(audio_file, **transcribe_options)
            logger.info(f"Transcrição concluída. Idioma: {result.get('language', language_in)}")
        
        return result
    
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
            # Carrega áudio se não foi fornecido
            if audio is None:
                audio = AudioSegment.from_file(audio_file)
            
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
                if self.job_store:
                    progress = 25.0 + (50.0 * (i + 1) / len(chunks))
                    job = self.job_store.get_job(self.current_job_id) if hasattr(self, 'current_job_id') else None
                    if job:
                        job.progress = progress
                        self.job_store.update_job(job)
            
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