from __future__ import annotations

import webview

from api import Api, extract_drop_path
from settings import ensure_runtime_dirs, resolve_app_paths, resolve_resource_dir


def ui_html_path() -> str:
    return str(resolve_resource_dir() / "ui" / "index.html")


def _bind_native_drop(window: webview.Window, api: Api) -> None:
    events = getattr(window, "events", None)
    drop = getattr(events, "drop", None)
    if drop is None:
        return

    def on_drop(event=None) -> None:
        path = extract_drop_path(event)
        if not path:
            return
        try:
            info = api._file_info(path)
        except OSError:
            return
        api.notify_file_selected(info)

    try:
        drop += on_drop
    except Exception:
        pass


def main() -> None:
    paths = resolve_app_paths()
    ensure_runtime_dirs(paths)

    api = Api(paths)
    window = webview.create_window(
        "Korean STT",
        ui_html_path(),
        js_api=api,
        width=1280,
        height=860,
        min_size=(900, 600),
    )
    api.set_window(window)
    _bind_native_drop(window, api)
    webview.start()


if __name__ == "__main__":
    main()
