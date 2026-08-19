from __future__ import annotations

import shutil
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any, Dict, Optional, Union

PathLike = Union[str, Path]


def _ffmpeg_run_kwargs() -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return kwargs


def _resolve_ffmpeg_command(ffmpeg_exe: Optional[PathLike] = None) -> Optional[str]:
    if ffmpeg_exe:
        bundled = Path(ffmpeg_exe)
        if bundled.exists() and bundled.is_file():
            return str(bundled.resolve())

    from_path = shutil.which("ffmpeg")
    if from_path:
        return str(Path(from_path).resolve())

    return None


def check_ffmpeg(ffmpeg_exe: Optional[PathLike] = None) -> tuple[bool, str]:
    cmd = _resolve_ffmpeg_command(ffmpeg_exe)
    if not cmd:
        return False, "ffmpeg not found"

    try:
        version_kwargs = _ffmpeg_run_kwargs()
        version_kwargs["stdout"] = subprocess.DEVNULL
        version_kwargs["stderr"] = subprocess.DEVNULL
        version_kwargs.pop("capture_output", None)
        subprocess.run(
            [cmd, "-version"],
            check=True,
            **version_kwargs,
        )
        return True, cmd
    except Exception:
        return False, "ffmpeg command failed"


def extract_audio(
    input_media: PathLike,
    output_wav: PathLike,
    sample_rate: int = 16000,
    ffmpeg_exe: Optional[PathLike] = None,
) -> str:
    cmd = _resolve_ffmpeg_command(ffmpeg_exe)
    if not cmd:
        raise RuntimeError("ffmpeg is not available")

    src = str(Path(input_media))
    dst = str(Path(output_wav))
    Path(dst).parent.mkdir(parents=True, exist_ok=True)

    args = [
        cmd,
        "-y",
        "-i",
        src,
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "wav",
        dst,
    ]

    proc = subprocess.run(args, **_ffmpeg_run_kwargs())
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise RuntimeError(f"audio extraction failed: {stderr}")

    return dst


def wav_duration_seconds(path: PathLike) -> float:
    try:
        with wave.open(str(path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
        if rate <= 0 or frames <= 0:
            return 0.0
        return frames / float(rate)
    except Exception:
        return 0.0
