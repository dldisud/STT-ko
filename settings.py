from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


MODEL_REPO_IDS: Dict[str, str] = {
    "moonshine": "UsefulSensors/moonshine-tiny-ko",
    "qwen3": "Qwen/Qwen3-ASR-1.7B",
}

MODEL_DIR_NAMES: Dict[str, str] = {
    "moonshine": "moonshine-tiny-ko",
    "qwen3": "Qwen3-ASR-1.7B",
}

MODEL_FILE_RULES: Dict[str, Dict[str, Dict[str, int]]] = {
    "moonshine": {
        "model.safetensors": {"min_size": 50_000_000},
    },
    "qwen3": {
        "model-00001-of-00002.safetensors": {"min_size": 3_000_000_000},
        "model-00002-of-00002.safetensors": {"min_size": 300_000_000},
    },
}


@dataclass(frozen=True)
class AppPaths:
    app_root: Path
    models_dir: Path
    ffmpeg_exe: Optional[Path]
    temp_dir: Path
    moonshine_model_dir: Path
    qwen3_model_dir: Path


def _sample_chunk_has_nonzero(path: Path, offset: int, sample_size: int) -> bool:
    with path.open("rb") as f:
        f.seek(max(0, offset))
        chunk = f.read(sample_size)
    return bool(chunk) and any(b != 0 for b in chunk)


def _binary_samples_look_valid(path: Path, sample_size: int = 4096) -> bool:
    if not path.exists() or not path.is_file():
        return False

    size = path.stat().st_size
    if size <= 0:
        return False

    middle = max(0, (size // 2) - (sample_size // 2))
    tail = max(0, size - sample_size)
    offsets = [0, middle, tail]

    return all(_sample_chunk_has_nonzero(path, off, sample_size) for off in offsets)


def model_status(model_name: str, model_dir: Path) -> tuple[bool, str]:
    rules = MODEL_FILE_RULES.get(model_name)
    if not rules:
        return False, f"unknown model: {model_name}"

    if not model_dir.exists():
        return False, "model folder missing"

    for filename, spec in rules.items():
        file_path = model_dir / filename
        if not file_path.exists():
            return False, f"missing file: {filename}"

        size = file_path.stat().st_size
        min_size = int(spec.get("min_size", 1))
        if size < min_size:
            return False, f"file too small: {filename}"

        if not _binary_samples_look_valid(file_path):
            return False, f"zero-filled pattern detected: {filename}"

    return True, "model available"


def model_ready(model_name: str, model_dir: Path) -> bool:
    ok, _ = model_status(model_name, model_dir)
    return ok


def discover_ffmpeg_exe(app_root: Path) -> Optional[Path]:
    app_root = app_root.resolve()

    direct = app_root / "ffmpeg" / "bin" / "ffmpeg.exe"
    if direct.exists() and direct.is_file():
        return direct

    candidates = list(app_root.glob("ffmpeg-*/bin/ffmpeg.exe"))
    if candidates:
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0]

    from_path = shutil.which("ffmpeg")
    if from_path:
        return Path(from_path).resolve()

    return None


def resolve_app_paths(
    base_dir: Optional[Path] = None,
    frozen: Optional[bool] = None,
    executable_path: Optional[Path] = None,
) -> AppPaths:
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))

    if base_dir is not None:
        app_root = base_dir.resolve()
    elif frozen:
        exe_path = executable_path or Path(sys.executable)
        app_root = exe_path.resolve().parent
    else:
        app_root = Path(__file__).resolve().parent

    models_dir = app_root
    ffmpeg_exe = discover_ffmpeg_exe(app_root)
    temp_dir = app_root / "temp"
    moonshine_model_dir = models_dir / "moonshine-tiny-ko"
    qwen3_model_dir = models_dir / "Qwen3-ASR-1.7B"

    return AppPaths(
        app_root=app_root,
        models_dir=models_dir,
        ffmpeg_exe=ffmpeg_exe,
        temp_dir=temp_dir,
        moonshine_model_dir=moonshine_model_dir,
        qwen3_model_dir=qwen3_model_dir,
    )


def ensure_runtime_dirs(paths: AppPaths) -> None:
    paths.temp_dir.mkdir(parents=True, exist_ok=True)
