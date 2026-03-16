from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import torch
from transformers import pipeline

from settings import AppPaths


class BaseTranscriber:
    def __init__(self, model_dir: Path) -> None:
        self.model_dir = model_dir
        self._pipe = None

    def _ensure_pipeline(self, device: int) -> None:
        if self._pipe is not None:
            return
        self._pipe = pipeline(
            "automatic-speech-recognition",
            model=str(self.model_dir),
            trust_remote_code=True,
            device=device,
        )

    def transcribe(self, audio_path: str) -> Dict[str, Any]:
        raise NotImplementedError


class MoonshineTranscriber(BaseTranscriber):
    def __init__(self, model_dir: Path) -> None:
        super().__init__(model_dir)
        self._device = 0 if torch.cuda.is_available() else -1

    def transcribe(self, audio_path: str) -> Dict[str, Any]:
        self._ensure_pipeline(self._device)
        result = self._pipe(
            audio_path,
            return_timestamps=True,
            chunk_length_s=30,
            stride_length_s=5,
        )
        return _normalize_output(result)


class Qwen3Transcriber(BaseTranscriber):
    def __init__(self, model_dir: Path) -> None:
        if not torch.cuda.is_available():
            raise RuntimeError("Qwen3 requires NVIDIA GPU (CUDA).")
        super().__init__(model_dir)

    def transcribe(self, audio_path: str) -> Dict[str, Any]:
        self._ensure_pipeline(device=0)
        result = self._pipe(
            audio_path,
            return_timestamps=True,
            chunk_length_s=30,
            stride_length_s=5,
        )
        return _normalize_output(result)


def _normalize_output(result: Any) -> Dict[str, Any]:
    text = ""
    segments: List[Dict[str, Any]] = []

    if isinstance(result, dict):
        text = str(result.get("text", "")).strip()

        chunks = result.get("chunks")
        if isinstance(chunks, list):
            for ch in chunks:
                if not isinstance(ch, dict):
                    continue
                ts = ch.get("timestamp")
                start = 0.0
                end = 0.0
                if isinstance(ts, (tuple, list)) and len(ts) == 2:
                    start = float(ts[0] or 0.0)
                    end = float(ts[1] or 0.0)
                seg_text = str(ch.get("text", "")).strip()
                if seg_text:
                    segments.append({"start": start, "end": end, "text": seg_text})

    if not text and isinstance(result, str):
        text = result.strip()

    if not segments and text:
        segments = [{"start": 0.0, "end": 10.0, "text": text}]

    return {"text": text, "segments": segments}


def get_transcriber(model_name: str, paths: AppPaths) -> BaseTranscriber:
    model_key = model_name.strip().lower()
    if model_key in {"moonshine", "moonshine-tiny-ko"}:
        return MoonshineTranscriber(paths.moonshine_model_dir)

    if model_key in {"qwen3", "qwen3-asr", "qwen"}:
        return Qwen3Transcriber(paths.qwen3_model_dir)

    raise ValueError(f"Unsupported model: {model_name}")
