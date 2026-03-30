import signal
import sys
signal.signal(signal.SIGTERM, signal.SIG_IGN)

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8002,
        reload=False,
        log_level="info",
    )
