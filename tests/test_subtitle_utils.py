from pathlib import Path

from subtitle_utils import _to_srt_ts, save_srt


def test_srt_timestamp_rounds_float_tenths():
    assert _to_srt_ts(0.1) == "00:00:00,100"
    assert _to_srt_ts(1.001) == "00:00:01,001"
    assert _to_srt_ts(-1) == "00:00:00,000"
    assert _to_srt_ts(float("nan")) == "00:00:00,000"


def test_save_srt_writes_utf8_bom(tmp_path: Path):
    out = tmp_path / "ko.srt"
    save_srt(
        [{"start": 0.1, "end": 1.5, "text": "안녕하세요"}],
        str(out),
    )
    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = out.read_text(encoding="utf-8-sig")
    assert "00:00:00,100 --> 00:00:01,500" in text
    assert "안녕하세요" in text


def test_save_srt_extends_inverted_times(tmp_path: Path):
    out = tmp_path / "fix.srt"
    save_srt([{"start": 3.0, "end": 1.0, "text": "뒤바뀜"}], str(out))
    text = out.read_text(encoding="utf-8-sig")
    assert "00:00:03,000 --> 00:00:05,000" in text
