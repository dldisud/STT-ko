from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping, Optional


def _to_srt_ts(seconds: float) -> str:
    total_ms = int(max(seconds, 0.0) * 1000)
    hours = total_ms // 3_600_000
    total_ms %= 3_600_000
    minutes = total_ms // 60_000
    total_ms %= 60_000
    secs = total_ms // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def save_srt(
    segments: Iterable[Mapping[str, object]],
    output_path: str,
    fallback_text: Optional[str] = None,
) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    idx = 1

    for seg in segments:
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        start = float(seg.get("start", 0.0) or 0.0)
        end = float(seg.get("end", start + 2.0) or (start + 2.0))
        if end <= start:
            end = start + 2.0

        lines.append(str(idx))
        lines.append(f"{_to_srt_ts(start)} --> {_to_srt_ts(end)}")
        lines.append(text)
        lines.append("")
        idx += 1

    if not lines and fallback_text:
        lines = [
            "1",
            "00:00:00,000 --> 00:00:10,000",
            fallback_text.strip(),
            "",
        ]

    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)
