from pathlib import Path

import settings
from app_logic import determine_available_models
from settings import AppPaths


def _write_sparse_nonzero(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.truncate(size)
        f.seek(0)
        f.write(b"\x01")
        f.seek(size // 2)
        f.write(b"\x02")
        f.seek(size - 1)
        f.write(b"\x03")


def _mk_paths(tmp_path: Path) -> AppPaths:
    moon = tmp_path / "moonshine-tiny-ko"
    qwen = tmp_path / "Qwen3-ASR-1.7B"

    _write_sparse_nonzero(moon / "model.safetensors", 12_000)
    _write_sparse_nonzero(qwen / "model-00001-of-00002.safetensors", 20_000)
    _write_sparse_nonzero(qwen / "model-00002-of-00002.safetensors", 16_000)

    return AppPaths(
        app_root=tmp_path,
        models_dir=tmp_path,
        ffmpeg_exe=tmp_path / "ffmpeg" / "bin" / "ffmpeg.exe",
        temp_dir=tmp_path / "temp",
        moonshine_model_dir=moon,
        qwen3_model_dir=qwen,
    )


def test_qwen_hidden_without_gpu(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        settings,
        "MODEL_FILE_RULES",
        {
            "moonshine": {"model.safetensors": {"min_size": 1000}},
            "qwen3": {
                "model-00001-of-00002.safetensors": {"min_size": 1000},
                "model-00002-of-00002.safetensors": {"min_size": 1000},
            },
        },
    )
    paths = _mk_paths(tmp_path)
    models = determine_available_models(paths, gpu_enabled=False)
    assert "moonshine" in models
    assert "qwen3" not in models


def test_qwen_visible_with_gpu(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        settings,
        "MODEL_FILE_RULES",
        {
            "moonshine": {"model.safetensors": {"min_size": 1000}},
            "qwen3": {
                "model-00001-of-00002.safetensors": {"min_size": 1000},
                "model-00002-of-00002.safetensors": {"min_size": 1000},
            },
        },
    )
    paths = _mk_paths(tmp_path)
    models = determine_available_models(paths, gpu_enabled=True)
    assert "moonshine" in models
    assert "qwen3" in models
