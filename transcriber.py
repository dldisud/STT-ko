from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
from transformers import pipeline

from audio_utils import wav_duration_seconds
from settings import AppPaths

_TRANSCRIBER_CACHE: Dict[str, "BaseTranscriber"] = {}
_SENTENCE_SPLIT = re.compile(r"(?<=[\.!?。！？])\s+|\n+")


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
        result = _run_asr_pipeline(self._pipe, audio_path)
        duration = wav_duration_seconds(audio_path)
        return _normalize_output(result, duration=duration)


class Qwen3Transcriber(BaseTranscriber):
    def __init__(self, model_dir: Path) -> None:
        if not torch.cuda.is_available():
            raise RuntimeError("Qwen3 requires NVIDIA GPU (CUDA).")
        super().__init__(model_dir)
        self._model = None

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from qwen_asr import Qwen3ASRModel
        except ImportError as exc:
            raise RuntimeError(
                "qwen-asr 패키지가 설치되어 있지 않습니다. pip install qwen-asr 을 실행하세요."
            ) from exc

        self._model = Qwen3ASRModel.from_pretrained(
            str(self.model_dir),
            device_map="cuda:0",
            max_new_tokens=4096,
        )
        return self._model

    def transcribe(self, audio_path: str) -> Dict[str, Any]:
        model = self._ensure_model()
        try:
            results = model.transcribe(audio=audio_path, language="Korean")
        except Exception:
            results = model.transcribe(audio=audio_path)

        result = results[0] if isinstance(results, list) and results else results
        text = str(getattr(result, "text", "") or "").strip()
        if not text and isinstance(result, dict):
            text = str(result.get("text", "")).strip()

        duration = wav_duration_seconds(audio_path)
        stamps = getattr(result, "time_stamps", None)
        if stamps is None and isinstance(result, dict):
            stamps = result.get("time_stamps") or result.get("chunks")
        segments = segments_from_timestamps(stamps)
        if not segments:
            segments = duration_based_segments(text, duration)
        else:
            segments = merge_caption_segments(segments)
        return {"text": text, "segments": segments}


def _run_asr_pipeline(pipe: Any, audio_path: str) -> Any:
    attempts: List[Dict[str, Any]] = [
        {"return_timestamps": True, "chunk_length_s": 30, "stride_length_s": 5},
        {"return_timestamps": True},
        {},
    ]
    last_exc: Optional[Exception] = None
    for kwargs in attempts:
        try:
            return pipe(audio_path, **kwargs)
        except (TypeError, ValueError) as exc:
            last_exc = exc
    if last_exc is not None:
        raise last_exc
    return pipe(audio_path)


def split_text_chunks(text: str) -> List[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(cleaned) if p.strip()]
    if len(parts) <= 1 and len(cleaned) > 42:
        return [cleaned[i : i + 42].strip() for i in range(0, len(cleaned), 42) if cleaned[i : i + 42].strip()]
    return parts or [cleaned]


def duration_based_segments(text: str, duration: Optional[float]) -> List[Dict[str, Any]]:
    chunks = split_text_chunks(text)
    if not chunks:
        return []
    total = float(duration) if duration and duration > 0 else max(2.0, len(chunks) * 2.0)
    weights = [max(len(chunk), 1) for chunk in chunks]
    weight_sum = float(sum(weights))
    segments: List[Dict[str, Any]] = []
    cursor = 0.0
    for index, (chunk, weight) in enumerate(zip(chunks, weights)):
        span = total * (weight / weight_sum)
        start = cursor
        end = total if index == len(chunks) - 1 else cursor + span
        if end <= start:
            end = start + 0.5
        segments.append({"start": start, "end": end, "text": chunk})
        cursor = end
    return segments


def segments_from_timestamps(stamps: Any) -> List[Dict[str, Any]]:
    if stamps is None:
        return []

    items: List[Any]
    if isinstance(stamps, dict):
        items = [stamps]
    elif isinstance(stamps, (list, tuple)):
        items = list(stamps)
    else:
        try:
            items = list(stamps)
        except TypeError:
            items = [stamps]

    if items and isinstance(items[0], (list, tuple)):
        flat: List[Any] = []
        for group in items:
            if isinstance(group, (list, tuple)):
                flat.extend(group)
            else:
                flat.append(group)
        items = flat

    segments: List[Dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            text = str(item.get("text", "")).strip()
            start = item.get("start_time", item.get("start", 0.0))
            end = item.get("end_time", item.get("end", 0.0))
            ts = item.get("timestamp")
            if isinstance(ts, (tuple, list)) and len(ts) == 2:
                start = ts[0]
                end = ts[1]
        else:
            text = str(getattr(item, "text", "")).strip()
            start = getattr(item, "start_time", getattr(item, "start", 0.0))
            end = getattr(item, "end_time", getattr(item, "end", 0.0))
        if not text:
            continue
        try:
            start_f = float(start or 0.0)
            end_f = float(end or 0.0)
        except (TypeError, ValueError):
            continue
        segments.append({"start": start_f, "end": end_f, "text": text})
    return segments


def merge_caption_segments(
    segments: List[Dict[str, Any]],
    max_duration: float = 3.5,
    max_chars: int = 36,
) -> List[Dict[str, Any]]:
    if len(segments) <= 3:
        return segments
    avg_chars = sum(len(str(seg.get("text", ""))) for seg in segments) / len(segments)
    if avg_chars > 8:
        return segments

    merged: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for seg in segments:
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        start = float(seg.get("start", 0.0) or 0.0)
        end = float(seg.get("end", start) or start)
        if current is None:
            current = {"start": start, "end": end, "text": text}
            continue
        next_text = f"{current['text']} {text}".strip()
        too_long = (end - current["start"]) > max_duration or len(next_text) > max_chars
        if too_long:
            merged.append(current)
            current = {"start": start, "end": end, "text": text}
        else:
            current["end"] = max(end, float(current["end"]))
            current["text"] = next_text
    if current:
        merged.append(current)
    return merged or segments


def _looks_like_placeholder(segments: List[Dict[str, Any]]) -> bool:
    if not segments:
        return True
    if len(segments) == 1:
        end = float(segments[0].get("end", 0.0) or 0.0)
        start = float(segments[0].get("start", 0.0) or 0.0)
        return start == 0.0 and end in {0.0, 10.0}
    return all(
        float(seg.get("start", 0.0) or 0.0) == 0.0
        and float(seg.get("end", 0.0) or 0.0) <= 2.0
        for seg in segments
    )


def _normalize_output(result: Any, duration: Optional[float] = None) -> Dict[str, Any]:
    text = ""
    segments: List[Dict[str, Any]] = []

    if isinstance(result, dict):
        text = str(result.get("text", "")).strip()
        chunks = result.get("chunks")
        segments = segments_from_timestamps(chunks)

    if not text and isinstance(result, str):
        text = result.strip()

    if (not segments or _looks_like_placeholder(segments)) and text:
        segments = duration_based_segments(text, duration)
    if not segments and text:
        fallback_end = float(duration) if duration and duration > 0 else 10.0
        segments = [{"start": 0.0, "end": fallback_end, "text": text}]

    return {"text": text, "segments": segments}


def get_transcriber(model_name: str, paths: AppPaths) -> BaseTranscriber:
    model_key = model_name.strip().lower()
    cached = _TRANSCRIBER_CACHE.get(model_key)
    if cached is not None:
        return cached

    if model_key in {"moonshine", "moonshine-tiny-ko"}:
        inst: BaseTranscriber = MoonshineTranscriber(paths.moonshine_model_dir)
    elif model_key in {"qwen3", "qwen3-asr", "qwen"}:
        inst = Qwen3Transcriber(paths.qwen3_model_dir)
    else:
        raise ValueError(f"Unsupported model: {model_name}")

    _TRANSCRIBER_CACHE[model_key] = inst
    return inst


def clear_transcriber_cache() -> None:
    _TRANSCRIBER_CACHE.clear()
