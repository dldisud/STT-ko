from pathlib import Path

import audio_utils


def test_ffmpeg_prefers_bundled(monkeypatch, tmp_path: Path):
    bundled = tmp_path / "ffmpeg.exe"
    bundled.write_bytes(b"x")

    monkeypatch.setattr(audio_utils.shutil, "which", lambda _: "C:/Windows/ffmpeg.exe")
    cmd = audio_utils._resolve_ffmpeg_command(bundled)
    assert Path(cmd) == bundled.resolve()


def test_ffmpeg_falls_back_to_path(monkeypatch):
    monkeypatch.setattr(audio_utils.shutil, "which", lambda _: "C:/Windows/ffmpeg.exe")
    cmd = audio_utils._resolve_ffmpeg_command("D:/not-found/ffmpeg.exe")
    assert str(Path(cmd)).lower().endswith(str(Path("C:/Windows/ffmpeg.exe")).lower())
