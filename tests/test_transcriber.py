from pathlib import Path
from types import SimpleNamespace

import transcriber
from transcriber import (
    Qwen3Transcriber,
    _normalize_output,
    clear_transcriber_cache,
    duration_based_segments,
    get_transcriber,
    merge_caption_segments,
    segments_from_timestamps,
)


def test_normalize_uses_audio_duration_instead_of_ten_seconds():
    result = _normalize_output({"text": "한 문장만 있습니다."}, duration=42.0)
    assert result["segments"][0]["end"] == 42.0
    assert result["segments"][0]["text"] == "한 문장만 있습니다."


def test_normalize_splits_sentences_across_duration():
    result = _normalize_output(
        {"text": "첫 문장입니다. 둘째 문장입니다."},
        duration=10.0,
    )
    assert len(result["segments"]) == 2
    assert result["segments"][0]["start"] == 0.0
    assert result["segments"][-1]["end"] == 10.0
    assert "첫" in result["segments"][0]["text"]
    assert "둘째" in result["segments"][1]["text"]


def test_qwen_word_timestamps_are_merged_for_premiere():
    words = [
        SimpleNamespace(text="오늘", start_time=0.0, end_time=0.3),
        SimpleNamespace(text="하이라이트", start_time=0.3, end_time=0.8),
        SimpleNamespace(text="보자", start_time=0.8, end_time=1.1),
        SimpleNamespace(text="다음", start_time=4.0, end_time=4.2),
        SimpleNamespace(text="장면", start_time=4.2, end_time=4.6),
    ]
    segs = merge_caption_segments(segments_from_timestamps(words))
    assert len(segs) >= 2
    assert segs[0]["start"] == 0.0
    assert "오늘" in segs[0]["text"]


def test_duration_based_segments_empty_text():
    assert duration_based_segments("  ", 5.0) == []


def test_get_transcriber_caches_and_rejects_unknown(tmp_path: Path, monkeypatch):
    clear_transcriber_cache()
    paths = SimpleNamespace(
        moonshine_model_dir=tmp_path / "moon",
        qwen3_model_dir=tmp_path / "qwen",
    )
    first = get_transcriber("moonshine", paths)
    second = get_transcriber("moonshine", paths)
    assert first is second
    try:
        get_transcriber("nope", paths)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "Unsupported" in str(exc)
    clear_transcriber_cache()


def test_qwen_transcriber_uses_qwen_asr_not_pipeline(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(transcriber.torch.cuda, "is_available", lambda: True)

    class FakeModel:
        def __init__(self):
            self.calls = []

        def transcribe(self, audio, language=None):
            self.calls.append({"audio": audio, "language": language})
            return [SimpleNamespace(text="팀 파이트 좋습니다.", time_stamps=None)]

    fake = FakeModel()

    class FakeQwenMod:
        class Qwen3ASRModel:
            @staticmethod
            def from_pretrained(*_args, **_kwargs):
                return fake

    monkeypatch.setitem(__import__("sys").modules, "qwen_asr", FakeQwenMod)
    inst = Qwen3Transcriber(tmp_path)
    monkeypatch.setattr(transcriber, "wav_duration_seconds", lambda _p: 8.0)
    out = inst.transcribe("clip.wav")
    assert fake.calls[0]["language"] == "Korean"
    assert out["text"] == "팀 파이트 좋습니다."
    assert out["segments"][0]["end"] == 8.0
