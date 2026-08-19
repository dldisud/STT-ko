import wave
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


def test_ffmpeg_run_kwargs_use_utf8_and_replace():
    kwargs = audio_utils._ffmpeg_run_kwargs()
    assert kwargs["encoding"] == "utf-8"
    assert kwargs["errors"] == "replace"
    assert kwargs["text"] is True


def test_extract_audio_raises_when_ffmpeg_missing(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(audio_utils, "_resolve_ffmpeg_command", lambda _exe=None: None)
    try:
        audio_utils.extract_audio(tmp_path / "in.mp4", tmp_path / "out.wav")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "ffmpeg" in str(exc)


def test_extract_audio_includes_stderr_on_failure(monkeypatch, tmp_path: Path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    dst = tmp_path / "out.wav"
    fake_ff = tmp_path / "ffmpeg.exe"
    fake_ff.write_bytes(b"x")
    monkeypatch.setattr(audio_utils, "_resolve_ffmpeg_command", lambda _exe=None: str(fake_ff))

    class FakeProc:
        returncode = 1
        stderr = "한글 경로 오류"

    monkeypatch.setattr(audio_utils.subprocess, "run", lambda *_a, **_k: FakeProc())
    try:
        audio_utils.extract_audio(src, dst)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "한글 경로 오류" in str(exc)


def test_wav_duration_seconds(tmp_path: Path):
    path = tmp_path / "tone.wav"
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 8000)
    assert abs(audio_utils.wav_duration_seconds(path) - 0.5) < 0.01
    assert audio_utils.wav_duration_seconds(tmp_path / "missing.wav") == 0.0
