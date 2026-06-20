"""Health checker functions — SRP: verificações de saúde de componentes do sistema."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any


def check_disk_space(path: str) -> dict[str, Any]:
    """Verifica espaço em disco disponível. Retorna status ok/warning/error."""
    try:
        Path(path).mkdir(exist_ok=True, parents=True)
        stat = shutil.disk_usage(path)
        free_gb = stat.free / (1024**3)
        total_gb = stat.total / (1024**3)
        percent_free = (stat.free / stat.total) * 100

        if percent_free <= 5:
            status = "error"
        elif percent_free <= 10:
            status = "warning"
        else:
            status = "ok"

        return {
            "status": status,
            "free_gb": round(free_gb, 2),
            "total_gb": round(total_gb, 2),
            "percent_free": round(percent_free, 2),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def check_ffmpeg() -> dict[str, Any]:
    """Verifica se ffmpeg está instalado e funcional."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            return {"status": "ok", "version": version_line}
        return {"status": "warning", "message": "ffmpeg not responding"}
    except FileNotFoundError:
        return {"status": "warning", "message": "ffmpeg not installed"}
    except Exception as e:
        return {"status": "warning", "message": str(e)}


def check_whisper_model(processor: Any, cfg: dict[str, Any]) -> dict[str, Any]:
    """Verifica status do modelo Whisper (carregado/não carregado)."""
    try:
        model_name = cfg.get("whisper_model", "base")
        is_loaded = processor.model is not None
        return {
            "status": "ok",
            "model": model_name,
            "loaded": is_loaded,
            "message": (
                "Model loaded" if is_loaded else "Model will be loaded on first use"
            ),
        }
    except Exception as e:
        return {"status": "ok", "message": f"Check skipped: {e}"}
