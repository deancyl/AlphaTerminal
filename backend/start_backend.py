import signal
import sys
import os

# ── 优雅关停：捕获 SIGTERM 后通知 uvicorn 退出 ──────────────────────
_server = None

def _sigterm_handler(signum, frame):
    """SIGTERM 信号处理：优雅关停而非被 SIGKILL"""
    import logging
    logging.getLogger(__name__).info("[SIGTERM] 收到终止信号，正在优雅关停...")
    if _server and hasattr(_server, 'should_exit'):
        _server.should_exit = True

signal.signal(signal.SIGTERM, _sigterm_handler)

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
            if _key in ("HTTP_PROXY", "HTTPS_PROXY"):
                _lower_key = _key.lower()
                os.environ[_key] = _val
                if _lower_key not in os.environ:
                    os.environ[_lower_key] = _val
            elif _key in ("http_proxy", "https_proxy"):
                os.environ[_key] = _val
                _upper_key = _key.upper()
                if _upper_key not in os.environ:
                    os.environ[_upper_key] = _val

import uvicorn

if __name__ == "__main__":
    config = uvicorn.Config(
        "app.main:app",
        host="0.0.0.0",
        port=8002,
        log_level="info",
    )
    global _server
    _server = uvicorn.Server(config)
    _server.run()