from pathlib import Path
from types import SimpleNamespace

from api import Api, extract_drop_path, file_info, gpu_vram_text


def test_gpu_vram_uses_total_memory_not_total_mem():
    props = SimpleNamespace(total_memory=8_589_934_592)
    assert gpu_vram_text(props, 1_073_741_824) == "1.1 / 9 GB"


def test_gpu_vram_falls_back_when_property_missing():
    assert gpu_vram_text(SimpleNamespace(), 0) == "-"


def test_handle_drop_accepts_real_path_and_rejects_name_only(tmp_path: Path):
    media = tmp_path / "오버워치.mp4"
    media.write_bytes(b"x" * 2048)
    api = Api(
        SimpleNamespace(
            models_dir=tmp_path,
            moonshine_model_dir=tmp_path / "m",
            qwen3_model_dir=tmp_path / "q",
            ffmpeg_exe=None,
            temp_dir=tmp_path / "temp",
        )
    )
    info = api.handle_drop(str(media))
    assert info is not None
    assert info["name"] == "오버워치.mp4"
    assert info["path"] == str(media.resolve())
    assert api.handle_drop("오버워치.mp4") is None
    assert api.handle_drop("") is None


def test_extract_drop_path_from_pywebview_event(tmp_path: Path):
    media = tmp_path / "clip.mkv"
    media.write_bytes(b"x")
    event = {
        "dataTransfer": {
            "files": [{"path": str(media), "name": "clip.mkv"}],
        }
    }
    assert extract_drop_path(event) == str(media.resolve())
    assert extract_drop_path([str(media)]) == str(media.resolve())


def test_file_info_uses_kb_for_small_files(tmp_path: Path):
    small = tmp_path / "a.wav"
    small.write_bytes(b"x" * 1500)
    assert file_info(str(small))["meta"].endswith("KB")


def test_transcribe_missing_file(tmp_path: Path):
    api = Api(
        SimpleNamespace(
            models_dir=tmp_path,
            moonshine_model_dir=tmp_path / "m",
            qwen3_model_dir=tmp_path / "q",
            ffmpeg_exe=None,
            temp_dir=tmp_path / "temp",
        )
    )
    result = api.transcribe(str(tmp_path / "missing.mp4"), "moonshine")
    assert result["success"] is False
    assert "찾을 수 없습니다" in result["message"]


def test_transcribe_success_writes_bom_srt(tmp_path: Path, monkeypatch):
    import api as api_mod

    media = tmp_path / "game.mp4"
    media.write_bytes(b"x")
    paths = SimpleNamespace(
        models_dir=tmp_path,
        moonshine_model_dir=tmp_path / "m",
        qwen3_model_dir=tmp_path / "q",
        ffmpeg_exe=None,
        temp_dir=tmp_path / "temp",
    )
    paths.temp_dir.mkdir()

    def fake_extract(src, dst, sample_rate=16000, ffmpeg_exe=None):
        Path(dst).write_bytes(b"RIFF")
        return str(dst)

    class FakeTranscriber:
        def transcribe(self, audio_path):
            return {
                "text": "힐러 집중",
                "segments": [{"start": 0.1, "end": 1.2, "text": "힐러 집중"}],
            }

    monkeypatch.setattr(api_mod, "extract_audio", fake_extract)
    monkeypatch.setattr(api_mod, "get_transcriber", lambda *_a, **_k: FakeTranscriber())
    monkeypatch.setattr(api_mod, "ensure_runtime_dirs", lambda _p: None)

    result = Api(paths).transcribe(str(media), "moonshine")
    assert result["success"] is True
    raw = Path(result["srt_path"]).read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert "00:00:00,100" in result["srt_text"]
    leftover_wavs = list(paths.temp_dir.glob("audio_*.wav"))
    assert leftover_wavs == []


def test_save_srt_dialog_missing_source(tmp_path: Path):
    api = Api(SimpleNamespace())
    api._window = object()
    result = api.save_srt_dialog(str(tmp_path / "no.srt"))
    assert result["success"] is False
