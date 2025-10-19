"""
Pool de workers persistentes para transcrição paralela com Whisper.
Cada worker carrega o modelo UMA VEZ e fica aguardando tarefas via fila.
"""
from pathlib import Path
from typing import Optional, Dict, Any, List
import multiprocessing as mp
from queue import Empty, Full
import time

from loguru import logger


class PersistentWorkerPool:
    """
    Pool de workers persistentes que mantêm modelo Whisper carregado em memória.
    
    Arquitetura:
    - Workers são processos separados (multiprocessing.Process)
    - Cada worker carrega modelo Whisper UMA VEZ no início
    - Workers ficam em loop aguardando tarefas via Queue
    - Tarefas: (session_id, chunk_path, chunk_idx, language)
    - Resultados retornados via Queue de saída
    
    Vantagens:
    - Modelo carregado 1x por worker (vs carregar N vezes)
    - Evita overhead de spawn de processos
    - Processamento paralelo eficiente
    - Isolamento de memória entre workers
    """
    
    def __init__(
        self,
        model_name: str = "base",
        device: str = "cpu",
        num_workers: Optional[int] = None
    ):
        """
        Inicializa pool de workers (NÃO inicia ainda).
        
        Args:
            model_name: Nome do modelo Whisper (tiny, base, small, medium, large)
            device: Dispositivo (cpu ou cuda)
            num_workers: Número de workers (None = auto-detect)
        """
        self.model_name = model_name
        self.device = device
        
        # Auto-detect número de workers
        if num_workers is None:
            cpu_count = mp.cpu_count() or 4
            self.num_workers = max(2, min(cpu_count - 1, 4))  # Entre 2 e 4
        else:
            self.num_workers = max(1, num_workers)
        
        # Filas para comunicação entre processos
        self.task_queue: Optional[mp.Queue] = None
        self.result_queue: Optional[mp.Queue] = None
        
        # Lista de processos workers
        self.workers: List[mp.Process] = []
        self.running = False
        
        logger.info(
            f"Persistent worker pool configured: "
            f"model={model_name}, device={device}, workers={self.num_workers}"
        )
    
    def start(self):
        """
        Inicia workers persistentes (chamado no startup da aplicação).
        
        Cada worker:
        1. Carrega modelo Whisper
        2. Entra em loop aguardando tarefas
        3. Processa chunks e retorna resultados
        """
        if self.running:
            logger.warning("Worker pool already running")
            return
        
        logger.info(f"[WORKER POOL] Starting {self.num_workers} persistent workers...")
        
        # Criar filas
        self.task_queue = mp.Queue(maxsize=self.num_workers * 10)
        self.result_queue = mp.Queue()
        
        # Criar e iniciar workers
        for worker_id in range(self.num_workers):
            worker = mp.Process(
                target=self._worker_loop,
                args=(
                    worker_id,
                    self.model_name,
                    self.device,
                    self.task_queue,
                    self.result_queue
                ),
                daemon=True,
                name=f"WhisperWorker-{worker_id}"
            )
            worker.start()
            self.workers.append(worker)
            logger.info(f"[WORKER POOL] Started worker {worker_id} (PID: {worker.pid})")
        
        self.running = True
        logger.info(f"[WORKER POOL] All {self.num_workers} workers started and ready")
    
    def stop(self, timeout: int = 10):
        """
        Para workers persistentes (chamado no shutdown da aplicação).
        
        Args:
            timeout: Tempo máximo de espera em segundos
        """
        if not self.running:
            logger.warning("Worker pool not running")
            return
        
        logger.info(f"[WORKER POOL] Stopping {self.num_workers} workers...")
        
        # Enviar sinais de parada (None) para cada worker
        for _ in range(self.num_workers):
            try:
                self.task_queue.put(None, timeout=1)
            except Exception as e:
                logger.error(f"Failed to send stop signal: {e}")
        
        # Aguardar workers terminarem
        for worker in self.workers:
            worker.join(timeout=timeout)
            
            if worker.is_alive():
                logger.warning(f"Worker {worker.name} did not stop gracefully, terminating...")
                worker.terminate()
                worker.join(timeout=2)
        
        # Limpar filas
        if self.task_queue:
            self.task_queue.close()
            self.task_queue.join_thread()
        
        if self.result_queue:
            self.result_queue.close()
            self.result_queue.join_thread()
        
        self.workers.clear()
        self.running = False
        
        logger.info("[WORKER POOL] All workers stopped")
    
    def submit_task(
        self,
        session_id: str,
        chunk_path: Path,
        chunk_idx: int,
        language: str = "auto",
        timeout: int = 5
    ):
        """
        Envia tarefa para fila de processamento.
        
        Args:
            session_id: ID da sessão
            chunk_path: Caminho do chunk de áudio
            chunk_idx: Índice do chunk
            language: Idioma ou "auto"
            timeout: Timeout para adicionar à fila
        """
        if not self.running:
            raise RuntimeError("Worker pool is not running")
        
        task = {
            "session_id": session_id,
            "chunk_path": str(chunk_path),
            "chunk_idx": chunk_idx,
            "language": language
        }
        
        start = time.time()
        # Attempt to put task with simple backoff if queue is full. Avoids
        # raising a generic exception with an empty message when the
        # underlying exception (e.g. queue.Full) has no str().
        while True:
            try:
                # Use a small per-attempt timeout so we can retry with backoff
                self.task_queue.put(task, timeout=min(1, max(0.1, timeout)))
                return
            except Full as e:
                elapsed = time.time() - start
                # Log type and repr to avoid empty messages
                logger.warning(
                    f"Task queue full while submitting chunk {chunk_idx} for session {session_id}: "
                    f"elapsed={elapsed:.2f}s, queue_size={self.task_queue.qsize() if self.task_queue else 'N/A'}, "
                    f"exc={type(e).__name__}: {repr(e)}"
                )
                if elapsed >= timeout:
                    logger.error(
                        f"Failed to submit task after {elapsed:.2f}s (timeout={timeout}s)."
                    )
                    raise
                # brief backoff before retrying
                time.sleep(0.25)
            except Exception as e:
                # Catch-all: log exception type and repr to avoid empty messages
                logger.error(
                    f"Failed to submit task (unexpected error) for chunk {chunk_idx} in session {session_id}: "
                    f"{type(e).__name__}: {repr(e)}"
                )
                raise
    
    def get_result(self, timeout: int = 600) -> Dict[str, Any]:
        """
        Obtém resultado da fila de resultados.
        
        Args:
            timeout: Timeout em segundos (default: 10min por chunk)
            
        Returns:
            Dict com resultado do worker
        """
        if not self.running:
            raise RuntimeError("Worker pool is not running")
        
        try:
            return self.result_queue.get(timeout=timeout)
        except Empty:
            raise TimeoutError(f"No result received within {timeout}s")
    
    @staticmethod
    def _worker_loop(
        worker_id: int,
        model_name: str,
        device: str,
        task_queue: mp.Queue,
        result_queue: mp.Queue
    ):
        """
        Loop principal do worker (roda em processo separado).
        
        IMPORTANTE: Modelo é carregado UMA VEZ no início e reutilizado!
        
        Args:
            worker_id: ID do worker
            model_name: Nome do modelo Whisper
            device: Dispositivo (cpu/cuda)
            task_queue: Fila de entrada de tarefas
            result_queue: Fila de saída de resultados
        """
        import whisper
        from loguru import logger
        
        # Configurar logging no processo worker
        logger.add(
            f"logs/worker_{worker_id}.log",
            rotation="10 MB",
            retention="7 days",
            level="INFO"
        )
        
        logger.info(f"[WORKER {worker_id}] Process started (PID: {mp.current_process().pid})")
        
        # ===== CARREGAR MODELO UMA ÚNICA VEZ =====
        logger.info(f"[WORKER {worker_id}] Loading Whisper model '{model_name}' on {device}...")
        start_load = time.time()
        
        try:
            model = whisper.load_model(model_name, device=device)
            load_time = time.time() - start_load
            logger.info(
                f"[WORKER {worker_id}] Model loaded successfully in {load_time:.2f}s. "
                f"Ready to process chunks!"
            )
        except Exception as e:
            logger.error(f"[WORKER {worker_id}] FATAL: Failed to load model: {e}")
            return
        
        # ===== LOOP INFINITO PROCESSANDO TAREFAS =====
        processed_count = 0
        
        while True:
            try:
                # Pegar tarefa da fila (blocking com timeout)
                task = task_queue.get(timeout=1)
                
                # Sinal de parada
                if task is None:
                    logger.info(f"[WORKER {worker_id}] Received stop signal. Exiting...")
                    break
                
                # Processar chunk
                session_id = task["session_id"]
                chunk_path = Path(task["chunk_path"])
                chunk_idx = task["chunk_idx"]
                language = task["language"]
                
                logger.info(
                    f"[WORKER {worker_id}] Processing chunk {chunk_idx} "
                    f"for session {session_id} ({chunk_path.name})"
                )
                
                start_time = time.time()
                
                try:
                    # Transcrever chunk (modelo JÁ ESTÁ CARREGADO!)
                    result = model.transcribe(
                        str(chunk_path),
                        language=language if language != "auto" else None,
                        task="transcribe",
                        verbose=False
                    )
                    
                    processing_time = time.time() - start_time
                    processed_count += 1
                    
                    # Ajustar timestamps dos segmentos (relativo ao chunk)
                    # Nota: timestamps já vêm corretos do Whisper
                    
                    logger.info(
                        f"[WORKER {worker_id}] Chunk {chunk_idx} completed in {processing_time:.2f}s "
                        f"({len(result['segments'])} segments, lang={result.get('language')})"
                    )
                    
                    # Retornar resultado
                    result_queue.put({
                        "session_id": session_id,
                        "chunk_idx": chunk_idx,
                        "segments": result["segments"],
                        "language": result.get("language"),
                        "processing_time": processing_time,
                        "error": None,
                        "worker_id": worker_id
                    })
                
                except Exception as e:
                    processing_time = time.time() - start_time
                    
                    logger.error(
                        f"[WORKER {worker_id}] Failed to process chunk {chunk_idx} "
                        f"for session {session_id}: {e}"
                    )
                    
                    # Retornar erro
                    result_queue.put({
                        "session_id": session_id,
                        "chunk_idx": chunk_idx,
                        "segments": [],
                        "language": None,
                        "processing_time": processing_time,
                        "error": str(e),
                        "worker_id": worker_id
                    })
            
            except Empty:
                # Timeout normal, continuar aguardando
                continue
            
            except Exception as e:
                logger.error(f"[WORKER {worker_id}] Unexpected error in loop: {e}")
        
        logger.info(
            f"[WORKER {worker_id}] Shutting down. "
            f"Processed {processed_count} chunks total."
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas do pool.
        
        Returns:
            Dict com estatísticas
        """
        alive_workers = sum(1 for w in self.workers if w.is_alive())
        
        return {
            "running": self.running,
            "num_workers": self.num_workers,
            "alive_workers": alive_workers,
            "model_name": self.model_name,
            "device": self.device,
            "task_queue_size": self.task_queue.qsize() if self.task_queue else 0,
            "result_queue_size": self.result_queue.qsize() if self.result_queue else 0
        }
