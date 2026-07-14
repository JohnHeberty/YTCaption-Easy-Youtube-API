from __future__ import annotations

import os
import time
from pathlib import Path

from common.log_utils import get_logger

logger = get_logger(__name__)

REPO_ID = "ResembleAI/Chatterbox-Multilingual-pt-br"
BASE_REPO_ID = "ResembleAI/chatterbox"
T3_FILENAME = "t3_pt_br.safetensors"
S3GEN_FILENAME = "s3gen_v3.pt"
REQUIRED_FILES = ["ve.pt", "grapheme_mtl_merged_expanded_v1.json", "conds.pt", T3_FILENAME, S3GEN_FILENAME]


def download_chatterbox_model(
    model_dir: Path,
    *,
    do_login: bool = True,
) -> Path:
    """Download Chatterbox model files from HuggingFace if not already present.

    Args:
        model_dir: Directory to store model files.
        do_login: Whether to call ``huggingface_hub.login()`` when a token is found.

    Returns:
        The *model_dir* path (ensured to exist).
    """
    existing = [f for f in REQUIRED_FILES if (model_dir / f).exists()]
    if len(existing) == len(REQUIRED_FILES):
        logger.info("All %d model files found in %s", len(REQUIRED_FILES), model_dir)
        return model_dir

    token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
    if do_login and token and not token.startswith("hf_your_token"):
        from huggingface_hub import login
        login(token=token)

    model_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading model to %s...", model_dir)

    from huggingface_hub import snapshot_download, hf_hub_download

    t0 = time.time()
    base_files = ["ve.pt", "grapheme_mtl_merged_expanded_v1.json", "conds.pt"]
    snapshot_download(
        repo_id=BASE_REPO_ID,
        repo_type="model",
        revision="main",
        allow_patterns=base_files,
        token=token,
        local_dir=str(model_dir),
        local_dir_use_symlinks=False,
    )
    logger.info("Base model files downloaded in %.1fs", time.time() - t0)

    t1 = time.time()
    for filename in (T3_FILENAME, S3GEN_FILENAME):
        dest = model_dir / filename
        if not dest.exists():
            hf_hub_download(
                repo_id=REPO_ID,
                filename=filename,
                repo_type="model",
                token=token,
                local_dir=str(model_dir),
                local_dir_use_symlinks=False,
            )
    logger.info("PT-BR model files downloaded in %.1fs", time.time() - t1)

    return model_dir
