from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import webview

from audio_utils import check_ffmpeg, extract_audio
from model_downloader import download_model
from settings import AppPaths, ensure_runtime_dirs, model_status
from subtitle_utils import save_srt
from transcriber import get_transcriber


def gpu_vram_text(device_props: Any, memory_allocated: int) -> str:
    total = getattr(device_props, "total_memory", None)
    if total is None:
        total = getattr(device_props, "total_mem", None)
    if total is None:
        return "-"
    return f"{memory_allocated / 1e9:.1f} / {total / 1e9:.0f} GB"


def extract_drop_path(event: Any) -> Optional[str]:
    if event is None:
        return None
    if isinstance(event, Path):
        return str(event.resolve()) if event.is_file() else None
    if isinstance(event, str):
        path = Path(event)
        return str(path.resolve()) if path.is_file() else None
    if isinstance(event, (list, tuple)):
        for item in event:
            found = extract_drop_path(item)
            if found:
                return found
        return None
    if isinstance(event, dict):
        if "dataTransfer" in event:
            found = extract_drop_path(event.get("dataTransfer"))
            if found:
                return found
        if "files" in event:
            found = extract_drop_path(event.get("files"))
            if found:
                return found
        for key in ("path", "file", "filename"):
            value = event.get(key)
            if value:
                found = extract_drop_path(value)
                if found:
                    return found
        return None
    for attr in ("files", "dataTransfer", "path"):
        if hasattr(event, attr):
            found = extract_drop_path(getattr(event, attr))
            if found:
                return found
    return None


def file_info(path: str) -> Dict[str, str]:
    p = Path(path)
    size = p.stat().st_size
    if size >= 1_000_000_000:
        meta = f"{size / 1_000_000_000:.1f} GB"
    elif size >= 1_000_000:
        meta = f"{size / 1_000_000:.0f} MB"
    else:
        meta = f"{size / 1000:.0f} KB"
    return {"path": str(p.resolve()), "name": p.name, "meta": meta}


class Api:
    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths
        self._window: webview.Window | None = None

    def set_window(self, window: webview.Window) -> None:
        self._window = window

    def _js(self, func_name: str, *args: Any) -> None:
        if not self._window:
            return
        payload = ", ".join(json.dumps(arg, ensure_ascii=False) for arg in args)
        self._window.evaluate_js(f"{func_name}({payload})")

    def notify_file_selected(self, info: Dict[str, str]) -> None:
        self._js("window.setFileFromPython", info)

    # ── File Selection ──

    def select_file(self) -> Dict[str, str] | None:
        if not self._window:
            return None
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=(
                "Media Files (*.mp4;*.mkv;*.avi;*.mov;*.wav;*.mp3;*.flac;*.m4a)",
                "All Files (*.*)",
            ),
        )
        if not result:
            return None
        path = result[0] if isinstance(result, (list, tuple)) else result
        try:
            return file_info(str(path))
        except OSError:
            return None

    def handle_drop(self, path_or_name: str) -> Dict[str, str] | None:
        found = extract_drop_path(path_or_name)
        if not found:
            return None
        try:
            return file_info(found)
        except OSError:
            return None

    def _file_info(self, path: str) -> Dict[str, str]:
        return file_info(path)

    # ── Models ──

    def get_models(self) -> List[Dict[str, Any]]:
        import torch

        gpu = False
        try:
            gpu = torch.cuda.is_available()
        except Exception:
            pass

        moon_ok, _ = model_status("moonshine", self.paths.moonshine_model_dir)
        qwen_ok, _ = model_status("qwen3", self.paths.qwen3_model_dir)

        return [
            {
                "name": "moonshine",
                "label": "Moonshine",
                "desc": "빠른 속도, 한국어 특화 경량 모델",
                "tags": ["CPU / GPU", "~105 MB"],
                "installed": moon_ok,
                "ready": moon_ok,
            },
            {
                "name": "qwen3",
                "label": "Qwen3-ASR",
                "desc": "고품질 다국어 음성 인식 모델",
                "tags": ["GPU 전용", "~4.5 GB"],
                "installed": qwen_ok,
                "ready": qwen_ok and gpu,
            },
        ]

    def download_model(self, model_name: str) -> Dict[str, Any]:
        def on_progress(msg: str) -> None:
            self._js("window.addLog", f"[DL] {msg}")

        ok, msg = download_model(
            model_name, self.paths.models_dir, progress_callback=on_progress
        )
        return {"success": ok, "message": msg}

    # ── System Status ──

    def get_system_status(self) -> Dict[str, Any]:
        import torch

        gpu_available = False
        gpu_name = "Not available"
        vram = "-"
        try:
            gpu_available = bool(torch.cuda.is_available())
            if gpu_available:
                gpu_name = torch.cuda.get_device_name(0)
                vram = gpu_vram_text(
                    torch.cuda.get_device_properties(0),
                    torch.cuda.memory_allocated(0),
                )
        except Exception:
            pass

        ff_ok, _ = check_ffmpeg(self.paths.ffmpeg_exe)
        moon_ok, _ = model_status("moonshine", self.paths.moonshine_model_dir)
        qwen_ok, _ = model_status("qwen3", self.paths.qwen3_model_dir)

        return {
            "gpu_available": gpu_available,
            "gpu_name": gpu_name,
            "vram": vram,
            "ffmpeg": ff_ok,
            "moonshine_ready": moon_ok,
            "qwen_ready": qwen_ok,
        }

    # ── Transcription ──

    def transcribe(self, file_path: str, model_name: str) -> Dict[str, Any]:
        wav_path: Optional[Path] = None
        try:
            input_path = Path(file_path)
            if not input_path.is_file():
                return {"success": False, "message": f"파일을 찾을 수 없습니다: {file_path}"}

            ensure_runtime_dirs(self.paths)
            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            wav_path = self.paths.temp_dir / f"audio_{now}.wav"
            srt_path = self.paths.temp_dir / f"{input_path.stem}_{now}.srt"

            self._js("window.updateProgress", 10, "오디오 추출 중...", "extract")
            extract_audio(input_path, wav_path, ffmpeg_exe=self.paths.ffmpeg_exe)

            self._js("window.updateProgress", 30, "모델 로딩 중...", "load")
            transcriber = get_transcriber(model_name, self.paths)

            self._js("window.updateProgress", 50, "트랜스크립션 진행 중...", "transcribe")
            result = transcriber.transcribe(str(wav_path))

            self._js("window.updateProgress", 90, "SRT 생성 중...", "srt")
            text = str(result.get("text", "")).strip()
            segments = result.get("segments", [])
            out_srt = save_srt(segments, str(srt_path), fallback_text=text)

            self._js("window.updateProgress", 100, "완료!", "srt")

            srt_text = Path(out_srt).read_text(encoding="utf-8-sig")
            return {
                "success": True,
                "srt_text": srt_text,
                "srt_path": out_srt,
            }
        except Exception as exc:
            return {"success": False, "message": str(exc)}
        finally:
            if wav_path is not None:
                try:
                    wav_path.unlink(missing_ok=True)
                except OSError:
                    pass

    # ── Save SRT ──

    def save_srt_dialog(self, source_path: str) -> Dict[str, Any]:
        if not self._window:
            return {"success": False, "message": "창이 준비되지 않았습니다"}
        src = Path(source_path)
        if not src.is_file():
            return {"success": False, "message": f"SRT 파일을 찾을 수 없습니다: {source_path}"}
        result = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=src.name,
            file_types=("SRT Files (*.srt)", "All Files (*.*)"),
        )
        if not result:
            return {"success": False, "message": "cancelled"}
        dest = result if isinstance(result, str) else result[0]
        try:
            shutil.copy2(source_path, dest)
        except OSError as exc:
            return {"success": False, "message": str(exc)}
        return {"success": True, "path": dest}
