from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional


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


def _ffmpeg_names() -> tuple[str, ...]:
    if sys.platform == "win32":
        return ("ffmpeg.exe",)
    return ("ffmpeg.exe", "ffmpeg")


def _looks_like_ffmpeg(path: Path) -> bool:
    return path.exists() and path.is_file()


def _search_ffmpeg_under(root: Path) -> Optional[Path]:
    root = root.resolve()
    for name in _ffmpeg_names():
        direct = root / "ffmpeg" / "bin" / name
        if _looks_like_ffmpeg(direct):
            return direct

        nested = root / "bin" / name
        if _looks_like_ffmpeg(nested):
            return nested

    for name in _ffmpeg_names():
        candidates = list(root.glob(f"ffmpeg-*/bin/{name}"))
        if candidates:
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return candidates[0]
    return None


def discover_ffmpeg_exe(
    app_root: Path,
    extra_roots: Optional[Iterable[Path]] = None,
) -> Optional[Path]:
    app_root = app_root.resolve()
    roots: list[Path] = [app_root]

    internal = app_root / "_internal"
    if internal.exists():
        roots.append(internal)

    if extra_roots:
        for extra in extra_roots:
            if extra is None:
                continue
            roots.append(Path(extra))

    seen: set[Path] = set()
    for root in roots:
        try:
            resolved = root.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        found = _search_ffmpeg_under(resolved)
        if found:
            return found

    from_path = shutil.which("ffmpeg")
    if from_path:
        return Path(from_path).resolve()

    return None


def resolve_resource_dir(
    frozen: Optional[bool] = None,
    executable_path: Optional[Path] = None,
    meipass: Optional[Path] = None,
) -> Path:
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if not frozen:
        return Path(__file__).resolve().parent

    if meipass is None:
        raw = getattr(sys, "_MEIPASS", None)
        if raw:
            meipass = Path(raw)
    if meipass is not None:
        return Path(meipass).resolve()

    exe_parent = (executable_path or Path(sys.executable)).resolve().parent
    internal = exe_parent / "_internal"
    if internal.exists():
        return internal
    return exe_parent


def _dir_is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".korean_stt_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def user_data_root() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "KoreanSTT"
    return Path.home() / ".korean-stt"


def resolve_data_root(app_root: Path, frozen: bool) -> Path:
    if not frozen:
        return app_root
    if _dir_is_writable(app_root):
        return app_root
    return user_data_root()


def _pick_model_dir(app_root: Path, data_root: Path, dirname: str, model_name: str) -> Path:
    bundled = app_root / dirname
    preferred = data_root / dirname
    if bundled.exists() and model_ready(model_name, bundled):
        return bundled
    if preferred.exists() and model_ready(model_name, preferred):
        return preferred
    if bundled.exists() and not preferred.exists():
        return bundled
    return preferred


def resolve_app_paths(
    base_dir: Optional[Path] = None,
    frozen: Optional[bool] = None,
    executable_path: Optional[Path] = None,
    meipass: Optional[Path] = None,
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

    data_root = resolve_data_root(app_root, frozen)
    extra_roots: list[Path] = []
    if meipass is None and frozen:
        raw = getattr(sys, "_MEIPASS", None)
        if raw:
            meipass = Path(raw)
    if meipass is not None:
        extra_roots.append(Path(meipass))

    models_dir = data_root
    ffmpeg_exe = discover_ffmpeg_exe(app_root, extra_roots=extra_roots)
    temp_dir = data_root / "temp"
    moonshine_model_dir = _pick_model_dir(
        app_root, data_root, MODEL_DIR_NAMES["moonshine"], "moonshine"
    )
    qwen3_model_dir = _pick_model_dir(
        app_root, data_root, MODEL_DIR_NAMES["qwen3"], "qwen3"
    )

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
    paths.models_dir.mkdir(parents=True, exist_ok=True)
