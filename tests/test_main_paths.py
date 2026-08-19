from pathlib import Path

import main
from settings import resolve_resource_dir


def test_ui_html_path_uses_resource_dir(tmp_path: Path, monkeypatch):
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(main, "resolve_resource_dir", lambda: tmp_path)
    assert main.ui_html_path() == str(tmp_path / "ui" / "index.html")


def test_resource_dir_frozen_internal_fallback(tmp_path: Path):
    exe = tmp_path / "KoreanSTT.exe"
    exe.write_text("x", encoding="utf-8")
    internal = tmp_path / "_internal"
    internal.mkdir()
    found = resolve_resource_dir(frozen=True, executable_path=exe, meipass=None)
    assert found == internal.resolve()
