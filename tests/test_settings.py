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

    monkeypatch.setattr(settings, "discover_ffmpeg_exe", lambda app_root, extra_roots=None: ff)
    paths = resolve_app_paths(base_dir=tmp_path, frozen=False)
    assert paths.app_root == tmp_path
    assert paths.models_dir == tmp_path
    assert paths.ffmpeg_exe == ff


def test_resolve_app_paths_frozen_mode(tmp_path: Path, monkeypatch):
    fake_exe = tmp_path / "bundle" / "KoreanSTT.exe"
    fake_exe.parent.mkdir(parents=True, exist_ok=True)
    fake_exe.write_text("x", encoding="utf-8")

    monkeypatch.setattr(settings, "discover_ffmpeg_exe", lambda app_root, extra_roots=None: None)
    monkeypatch.setattr(settings, "resolve_data_root", lambda app_root, frozen: app_root)
    paths = resolve_app_paths(frozen=True, executable_path=fake_exe)
    assert paths.app_root == fake_exe.parent
    assert paths.temp_dir == fake_exe.parent / "temp"
    assert paths.ffmpeg_exe is None


def test_discover_ffmpeg_from_pyinstaller_internal(tmp_path: Path, monkeypatch):
    bundled = tmp_path / "_internal" / "ffmpeg" / "bin" / "ffmpeg.exe"
    bundled.parent.mkdir(parents=True, exist_ok=True)
    bundled.write_bytes(b"x")
    monkeypatch.setattr(settings.shutil, "which", lambda _: None)
    found = discover_ffmpeg_exe(tmp_path)
    assert found == bundled.resolve()


def test_discover_ffmpeg_from_meipass_extra_root(tmp_path: Path, monkeypatch):
    meipass = tmp_path / "meipass"
    bundled = meipass / "ffmpeg" / "bin" / "ffmpeg.exe"
    bundled.parent.mkdir(parents=True, exist_ok=True)
    bundled.write_bytes(b"x")
    monkeypatch.setattr(settings.shutil, "which", lambda _: None)
    found = discover_ffmpeg_exe(tmp_path / "app", extra_roots=[meipass])
    assert found == bundled.resolve()


def test_frozen_unwritable_app_root_uses_user_data(tmp_path: Path, monkeypatch):
    app_root = tmp_path / "Program Files" / "KoreanSTT"
    app_root.mkdir(parents=True)
    user_dir = tmp_path / "Local" / "KoreanSTT"
    monkeypatch.setattr(settings, "_dir_is_writable", lambda _path: False)
    monkeypatch.setattr(settings, "user_data_root", lambda: user_dir)
    monkeypatch.setattr(settings, "discover_ffmpeg_exe", lambda app_root, extra_roots=None: None)
    paths = resolve_app_paths(base_dir=app_root, frozen=True)
    assert paths.models_dir == user_dir
    assert paths.temp_dir == user_dir / "temp"


def test_resolve_resource_dir_prefers_meipass(tmp_path: Path):
    meipass = tmp_path / "_MEIPASS"
    meipass.mkdir()
    found = settings.resolve_resource_dir(
        frozen=True,
        executable_path=tmp_path / "KoreanSTT.exe",
        meipass=meipass,
    )
    assert found == meipass.resolve()
