import os
import time
from pathlib import Path
from typing import Optional

from common.log_utils import get_logger

from app.core.config import get_settings
from app.domain.exceptions import ModelNotAvailable, ResourceExhausted

logger = get_logger(__name__)

REPO_ID = "ResembleAI/Chatterbox-Multilingual-pt-br"
BASE_REPO_ID = "ResembleAI/chatterbox"
T3_FILENAME = "t3_pt_br.safetensors"
S3GEN_FILENAME = "s3gen_v3.pt"
REQUIRED_FILES = ["ve.pt", "grapheme_mtl_merged_expanded_v1.json", "conds.pt", T3_FILENAME, S3GEN_FILENAME]


class ChatterboxModelManager:
    def __init__(self):
        settings = get_settings()
        self._model_name = settings.model_name
        self._model_dir = Path(settings.model_dir)
        self._model_dir.mkdir(parents=True, exist_ok=True)
        self._device = self._resolve_device(settings.device)
        self._model = None
        self._sr = 24000
        self._loaded_at: Optional[float] = None

    @staticmethod
    def _resolve_device(device_str: str) -> str:
        import torch
        if device_str == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        return device_str

    @property
    def device(self) -> str:
        return self._device

    @property
    def sample_rate(self) -> int:
        return self._sr

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _ensure_model_files(self) -> Path:
        """Download model files to model_dir if not already present."""
        existing = [f for f in REQUIRED_FILES if (self._model_dir / f).exists()]
        if len(existing) == len(REQUIRED_FILES):
            logger.info(f"All {len(REQUIRED_FILES)} model files found in {self._model_dir}")
            return self._model_dir

        logger.info(f"Downloading model to {self._model_dir}...")
        token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")

        from huggingface_hub import snapshot_download, hf_hub_download

        t0 = time.time()

        base_files = ["ve.pt", "grapheme_mtl_merged_expanded_v1.json", "conds.pt"]
        base_dir = Path(snapshot_download(
            repo_id=BASE_REPO_ID,
            repo_type="model",
            revision="main",
            allow_patterns=base_files,
            token=token,
            local_dir=str(self._model_dir),
            local_dir_use_symlinks=False,
        ))
        logger.info(f"Base model files downloaded in {time.time() - t0:.1f}s")

        t1 = time.time()
        for filename in (T3_FILENAME, S3GEN_FILENAME):
            dest = self._model_dir / filename
            if not dest.exists():
                src = Path(hf_hub_download(
                    repo_id=REPO_ID,
                    filename=filename,
                    repo_type="model",
                    token=token,
                    local_dir=str(self._model_dir),
                    local_dir_use_symlinks=False,
                ))
                if src != dest and not dest.exists():
                    import shutil
                    shutil.copy2(src, dest)
        logger.info(f"PT-BR model files downloaded in {time.time() - t1:.1f}s")

        return self._model_dir

    def load_model(self) -> None:
        if self._model is not None:
            return

        ckpt_dir = self._ensure_model_files()

        token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
        if token:
            from huggingface_hub import login
            login(token=token)

        logger.info(f"Loading Chatterbox model from {ckpt_dir} on {self._device}...")
        t0 = time.time()

        from chatterbox.src.chatterbox.tts import ChatterboxTTS
        self._model = ChatterboxTTS.from_local(
            ckpt_dir, self._device,
            t3_filename=T3_FILENAME,
            s3gen_filename=S3GEN_FILENAME,
        )
        self._loaded_at = time.time()
        logger.info(f"Chatterbox model loaded on {self._device} in {time.time() - t0:.1f}s")

    def unload_model(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self._loaded_at = None
            logger.info("Chatterbox model unloaded")

    def generate(self, text: str, audio_prompt_path: Optional[str] = None,
                 exaggeration: float = 0.75, temperature: float = 0.8,
                 cfg_weight: float = 0.35):
        self.load_model()
        if self._model is None:
            raise ModelNotAvailable(device=self._device)

        kwargs = dict(
            text=text,
            language_id="pt",
            exaggeration=exaggeration,
            temperature=temperature,
            cfg_weight=cfg_weight,
        )
        if audio_prompt_path:
            kwargs["audio_prompt_path"] = audio_prompt_path

        try:
            wav = self._model.generate(**kwargs)
            return wav
        except Exception as e:
            raise ResourceExhausted(f"Generation failed: {e}") from e

    def get_status(self) -> dict:
        import torch
        model_files = {}
        for f in REQUIRED_FILES:
            p = self._model_dir / f
            model_files[f] = p.exists()

        return {
            "loaded": self.is_loaded,
            "model": self._model_name,
            "device": self._device,
            "sample_rate": self._sr,
            "cuda_available": torch.cuda.is_available(),
            "model_dir": str(self._model_dir),
            "model_files": model_files,
            "all_files_present": all(model_files.values()),
        }
