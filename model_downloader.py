from __future__ import annotations

import inspect
import shutil
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from settings import MODEL_DIR_NAMES, MODEL_REPO_IDS, model_status

_download_lock = threading.Lock()

_MIN_FREE_BYTES = {
    "moonshine": 300_000_000,
    "qwen3": 6_000_000_000,
}


def _huggingface_hub_available() -> bool:
    try:
        import huggingface_hub  # noqa: F401
        return True
    except ImportError:
        return False


def _format_bytes(num_bytes: int) -> str:
    if num_bytes >= 1_000_000_000:
        gb = num_bytes / 1_000_000_000
        if gb >= 10:
            return f"{gb:.0f}GB"
        text = f"{gb:.1f}GB"
        return text.replace(".0GB", "GB")
    return f"{max(num_bytes, 0) // 1_000_000}MB"


def _snapshot_download_kwargs(repo_id: str, target_dir: Path) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "repo_id": repo_id,
        "local_dir": str(target_dir),
    }
    try:
        from huggingface_hub import snapshot_download

        params = inspect.signature(snapshot_download).parameters
        # Older hub versions symlink large files; that breaks on Windows
        # without Developer Mode and leaves "ready" files that cannot load.
        if "local_dir_use_symlinks" in params:
            kwargs["local_dir_use_symlinks"] = False
    except Exception:
        pass
    return kwargs


def download_model(
    model_name: str,
    models_dir: Path,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, str]:
    """Download a model from HuggingFace Hub.

    Returns (success, message).
    """
    repo_id = MODEL_REPO_IDS.get(model_name)
    dir_name = MODEL_DIR_NAMES.get(model_name)
    if not repo_id or not dir_name:
        return False, f"알 수 없는 모델: {model_name}"

    if not _huggingface_hub_available():
        return False, "huggingface_hub 패키지가 설치되어 있지 않습니다. pip install huggingface_hub 을 실행하세요."

    if not _download_lock.acquire(blocking=False):
        return False, "다른 모델을 다운로드 중입니다. 완료 후 다시 시도하세요."

    try:
        try:
            models_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return False, f"모델 폴더를 만들 수 없습니다: {exc}"

        target_dir = models_dir / dir_name

        try:
            free_space = shutil.disk_usage(models_dir).free
        except OSError as exc:
            return False, f"디스크 공간을 확인할 수 없습니다: {exc}"

        min_space = _MIN_FREE_BYTES.get(model_name, 300_000_000)
        if free_space < min_space:
            return False, (
                f"디스크 공간이 부족합니다. 최소 {_format_bytes(min_space)} 필요 "
                f"(현재 {_format_bytes(free_space)} 남음)"
            )

        if progress_callback:
            progress_callback(f"{repo_id} 다운로드 시작...")

        from huggingface_hub import snapshot_download

        snapshot_download(**_snapshot_download_kwargs(repo_id, target_dir))

        if progress_callback:
            progress_callback("다운로드 완료. 무결성 검증 중...")

        ok, reason = model_status(model_name, target_dir)
        if not ok:
            return False, f"다운로드된 모델 검증 실패: {reason}"

        return True, f"{model_name} 모델 다운로드 완료!"

    except Exception as exc:
        return False, f"다운로드 실패: {exc}"
    finally:
        _download_lock.release()
