from __future__ import annotations

import shutil
import threading
from pathlib import Path
from typing import Callable, Optional, Tuple

from settings import MODEL_DIR_NAMES, MODEL_REPO_IDS, model_status

_download_lock = threading.Lock()


def _huggingface_hub_available() -> bool:
    try:
        import huggingface_hub  # noqa: F401
        return True
    except ImportError:
        return False


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
        target_dir = models_dir / dir_name

        free_space = shutil.disk_usage(models_dir).free
        min_space = 6_000_000_000 if model_name == "qwen3" else 300_000_000
        if free_space < min_space:
            return False, f"디스크 공간이 부족합니다. 최소 {min_space // 1_000_000_000}GB 필요 (현재 {free_space // 1_000_000_000}GB 남음)"

        if progress_callback:
            progress_callback(f"{repo_id} 다운로드 시작...")

        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=repo_id,
            local_dir=str(target_dir),
        )

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
