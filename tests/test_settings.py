from pathlib import Path
import os

import settings
from settings import discover_ffmpeg_exe, resolve_app_paths


def test_discover_ffmpeg_prefers_direct_folder(tmp_path: Path, monkeypatch):
    direct = tmp_path / "ffmpeg" / "bin" / "ffmpeg.exe"
    direct.parent.mkdir(parents=True, exist_ok=True)
    direct.write_bytes(b"x")

    alt = tmp_path / "ffmpeg-2025-03-10" / "bin" / "ffmpeg.exe"
    alt.parent.mkdir(parents=True, exist_ok=True)
    alt.write_bytes(b"x")

    monkeypatch.setattr(settings.shutil, "which", lambda _: "C:/Windows/ffmpeg.exe")
    found = discover_ffmpeg_exe(tmp_path)
    assert found == direct.resolve()


def test_discover_ffmpeg_uses_newest_pattern_folder(tmp_path: Path, monkeypatch):
    a = tmp_path / "ffmpeg-2025-03-01" / "bin" / "ffmpeg.exe"
    b = tmp_path / "ffmpeg-2025-03-10" / "bin" / "ffmpeg.exe"
    a.parent.mkdir(parents=True, exist_ok=True)
    b.parent.mkdir(parents=True, exist_ok=True)
    a.write_bytes(b"x")
    b.write_bytes(b"x")

    os.utime(a, (1, 1))
    os.utime(b, (2, 2))

    monkeypatch.setattr(settings.shutil, "which", lambda _: None)
    found = discover_ffmpeg_exe(tmp_path)
    assert found == b.resolve()


def test_discover_ffmpeg_falls_back_to_path(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings.shutil, "which", lambda _: str(tmp_path / "ffmpeg_path.exe"))
    found = discover_ffmpeg_exe(tmp_path)
    assert found == (tmp_path / "ffmpeg_path.exe").resolve()


def test_resolve_app_paths_dev_mode(tmp_path: Path, monkeypatch):
    ff = tmp_path / "ffmpeg" / "bin" / "ffmpeg.exe"
    ff.parent.mkdir(parents=True, exist_ok=True)
    ff.write_bytes(b"x")

    monkeypatch.setattr(settings, "discover_ffmpeg_exe", lambda app_root: ff)
    paths = resolve_app_paths(base_dir=tmp_path, frozen=False)
    assert paths.app_root == tmp_path
    assert paths.models_dir == tmp_path
    assert paths.ffmpeg_exe == ff


def test_resolve_app_paths_frozen_mode(tmp_path: Path, monkeypatch):
    fake_exe = tmp_path / "bundle" / "KoreanSTT.exe"
    fake_exe.parent.mkdir(parents=True, exist_ok=True)
    fake_exe.write_text("x", encoding="utf-8")

    monkeypatch.setattr(settings, "discover_ffmpeg_exe", lambda app_root: None)
    paths = resolve_app_paths(frozen=True, executable_path=fake_exe)
    assert paths.app_root == fake_exe.parent
    assert paths.temp_dir == fake_exe.parent / "temp"
    assert paths.ffmpeg_exe is None
