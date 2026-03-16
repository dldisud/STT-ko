from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional, Union

PathLike = Union[str, Path]


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
        subprocess.run(
            [cmd, "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
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

    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise RuntimeError(f"audio extraction failed: {stderr}")

    return dst
