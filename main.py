from __future__ import annotations

import sys
from pathlib import Path

import webview

from api import Api
from settings import ensure_runtime_dirs, resolve_app_paths


def _ui_path() -> str:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent
    return str(base / "ui" / "index.html")


def main() -> None:
    paths = resolve_app_paths()
    ensure_runtime_dirs(paths)

    api = Api(paths)
    window = webview.create_window(
        "Korean STT",
        _ui_path(),
        js_api=api,
        width=1280,
        height=860,
        min_size=(900, 600),
    )
    api.set_window(window)
    webview.start()


if __name__ == "__main__":
    main()
