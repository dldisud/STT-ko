from __future__ import annotations

import sys
from unittest.mock import MagicMock

for _name in ("torch", "transformers", "webview"):
    if _name not in sys.modules:
        try:
            __import__(_name)
        except ImportError:
            sys.modules[_name] = MagicMock()

_torch = sys.modules.get("torch")
if _torch is not None and hasattr(_torch, "cuda"):
    try:
        _torch.cuda.is_available.return_value = False
    except Exception:
        pass

_webview = sys.modules.get("webview")
if _webview is not None:
    if not isinstance(getattr(_webview, "OPEN_DIALOG", None), int):
        _webview.OPEN_DIALOG = 10
    if not isinstance(getattr(_webview, "SAVE_DIALOG", None), int):
        _webview.SAVE_DIALOG = 20
