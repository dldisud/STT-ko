from __future__ import annotations

import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import webview

from audio_utils import check_ffmpeg, extract_audio
from model_downloader import download_model
from settings import AppPaths, ensure_runtime_dirs, model_status, resolve_app_paths
from subtitle_utils import save_srt
from transcriber import get_transcriber


class Api:
    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths
        self._window: webview.Window | None = None

    def set_window(self, window: webview.Window) -> None:
        self._window = window

    def _js(self, code: str) -> None:
        if self._window:
            self._window.evaluate_js(code)

    # ── File Selection ──

    def select_file(self) -> Dict[str, str] | None:
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
        return self._file_info(path)

    def handle_drop(self, name: str) -> Dict[str, str] | None:
        return None

    def _file_info(self, path: str) -> Dict[str, str]:
        p = Path(path)
        size = p.stat().st_size
        if size > 1_000_000_000:
            meta = f"{size / 1_000_000_000:.1f} GB"
        else:
            meta = f"{size / 1_000_000:.0f} MB"
        return {"path": str(p), "name": p.name, "meta": meta}

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
                "ready": moon_ok,
            },
            {
                "name": "qwen3",
                "label": "Qwen3-ASR",
                "desc": "고품질 다국어 음성 인식 모델",
                "tags": ["GPU 전용", "~4.5 GB"],
                "ready": qwen_ok and gpu,
            },
        ]

    def download_model(self, model_name: str) -> Dict[str, Any]:
        def on_progress(msg: str):
            safe = msg.replace("'", "\\'")
            self._js(f"window.addLog('[DL] {safe}')")

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
            gpu_available = torch.cuda.is_available()
            if gpu_available:
                gpu_name = torch.cuda.get_device_name(0)
                total = torch.cuda.get_device_properties(0).total_mem
                used = torch.cuda.memory_allocated(0)
                vram = f"{used / 1e9:.1f} / {total / 1e9:.0f} GB"
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
        try:
            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            input_path = Path(file_path)
            wav_path = self.paths.temp_dir / f"audio_{now}.wav"
            srt_path = self.paths.temp_dir / f"{input_path.stem}_{now}.srt"

            # Step 1: Extract audio
            self._js("window.updateProgress(10, '오디오 추출 중...', 'extract')")
            extract_audio(input_path, wav_path, ffmpeg_exe=self.paths.ffmpeg_exe)

            # Step 2: Load model
            self._js("window.updateProgress(30, '모델 로딩 중...', 'load')")
            transcriber = get_transcriber(model_name, self.paths)

            # Step 3: Transcribe
            self._js("window.updateProgress(50, '트랜스크립션 진행 중...', 'transcribe')")
            result = transcriber.transcribe(str(wav_path))

            # Step 4: Generate SRT
            self._js("window.updateProgress(90, 'SRT 생성 중...', 'srt')")
            text = str(result.get("text", "")).strip()
            segments = result.get("segments", [])
            out_srt = save_srt(segments, str(srt_path), fallback_text=text)

            self._js("window.updateProgress(100, '완료!', 'srt')")

            srt_text = Path(out_srt).read_text(encoding="utf-8-sig")
            return {
                "success": True,
                "srt_text": srt_text,
                "srt_path": out_srt,
            }
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    # ── Save SRT ──

    def save_srt_dialog(self, source_path: str) -> None:
        result = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=Path(source_path).name,
            file_types=("SRT Files (*.srt)", "All Files (*.*)"),
        )
        if result:
            dest = result if isinstance(result, str) else result[0]
            shutil.copy2(source_path, dest)
