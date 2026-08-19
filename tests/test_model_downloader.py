from pathlib import Path
from types import SimpleNamespace

import model_downloader


def test_format_bytes_for_moonshine_space_message():
    assert model_downloader._format_bytes(300_000_000) == "300MB"
    assert "GB" in model_downloader._format_bytes(6_000_000_000)
    assert model_downloader._format_bytes(500_000_000) == "500MB"


def test_unknown_model_rejected(tmp_path: Path):
    ok, msg = model_downloader.download_model("nope", tmp_path)
    assert ok is False
    assert "알 수 없는" in msg


def test_missing_huggingface_hub(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(model_downloader, "_huggingface_hub_available", lambda: False)
    ok, msg = model_downloader.download_model("moonshine", tmp_path)
    assert ok is False
    assert "huggingface_hub" in msg


def test_low_disk_space_message_not_zero_gb(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(model_downloader, "_huggingface_hub_available", lambda: True)
    monkeypatch.setattr(
        model_downloader.shutil,
        "disk_usage",
        lambda _p: SimpleNamespace(free=10_000_000),
    )
    ok, msg = model_downloader.download_model("moonshine", tmp_path)
    assert ok is False
    assert "300MB" in msg
    assert "0GB" not in msg


def test_download_uses_symlink_false_when_parameter_exists(monkeypatch, tmp_path: Path):
    captured = {}
    import sys
    import types

    monkeypatch.setattr(model_downloader, "_huggingface_hub_available", lambda: True)
    monkeypatch.setattr(model_downloader.shutil, "disk_usage", lambda _p: SimpleNamespace(free=10**12))
    monkeypatch.setattr(model_downloader, "model_status", lambda *_a, **_k: (True, "model available"))

    fake_mod = types.ModuleType("huggingface_hub")

    def snapshot_download(repo_id, local_dir, local_dir_use_symlinks=True):
        captured.update(
            {
                "repo_id": repo_id,
                "local_dir": local_dir,
                "local_dir_use_symlinks": local_dir_use_symlinks,
            }
        )
        Path(local_dir).mkdir(parents=True, exist_ok=True)

    fake_mod.snapshot_download = snapshot_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_mod)

    ok, msg = model_downloader.download_model("moonshine", tmp_path)
    assert ok is True
    assert captured["local_dir_use_symlinks"] is False
    assert captured["repo_id"] == "UsefulSensors/moonshine-tiny-ko"


def test_busy_lock(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(model_downloader, "_huggingface_hub_available", lambda: True)
    assert model_downloader._download_lock.acquire(blocking=False)
    try:
        ok, msg = model_downloader.download_model("moonshine", tmp_path)
        assert ok is False
        assert "다른 모델" in msg
    finally:
        model_downloader._download_lock.release()
