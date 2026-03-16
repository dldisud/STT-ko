from pathlib import Path

import settings
from settings import model_status


def _write_sparse_nonzero(path: Path, size: int, write_middle: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.truncate(size)
        f.seek(0)
        f.write(b"\x01")
        if write_middle:
            f.seek(size // 2)
            f.write(b"\x02")
        f.seek(size - 1)
        f.write(b"\x03")


def test_model_status_valid(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        settings,
        "MODEL_FILE_RULES",
        {"moonshine": {"model.safetensors": {"min_size": 1000}}},
    )

    model_dir = tmp_path / "moonshine-tiny-ko"
    _write_sparse_nonzero(model_dir / "model.safetensors", 20_000)

    ok, reason = model_status("moonshine", model_dir)
    assert ok is True
    assert reason == "model available"


def test_model_status_zero_filled(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        settings,
        "MODEL_FILE_RULES",
        {"moonshine": {"model.safetensors": {"min_size": 1000}}},
    )

    model_dir = tmp_path / "moonshine-tiny-ko"
    target = model_dir / "model.safetensors"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as f:
        f.truncate(20_000)

    ok, reason = model_status("moonshine", model_dir)
    assert ok is False
    assert "zero-filled" in reason


def test_model_status_partial_damage(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        settings,
        "MODEL_FILE_RULES",
        {"moonshine": {"model.safetensors": {"min_size": 1000}}},
    )

    model_dir = tmp_path / "moonshine-tiny-ko"
    _write_sparse_nonzero(model_dir / "model.safetensors", 20_000, write_middle=False)

    ok, reason = model_status("moonshine", model_dir)
    assert ok is False
    assert "zero-filled" in reason
