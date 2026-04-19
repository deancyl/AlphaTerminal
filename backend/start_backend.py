import signal
import sys
import os

signal.signal(signal.SIGTERM, signal.SIG_IGN)

# ── 读取 .env 文件并设置代理环境变量 ─────────────────────────────
_env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(_env_file):
    for _line in open(_env_file):
        _line = _line.strip()
        if not _line or _line.startswith("#"):
            continue
        if "=" in _line:
            _key, _val = _line.split("=", 1)
            _key = _key.strip()
            _val = _val.strip().strip('"').strip("'")
            if _key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
                os.environ[_key] = _val
                os.environ.setdefault("http_proxy",  _val if "http://" in _val else f"http://{_val}")
                os.environ.setdefault("https_proxy", _val if "http://" in _val else f"http://{_val}")

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8002,
        reload=False,
        log_level="info",
    )
