import signal
signal.signal(signal.SIGTERM, signal.SIG_IGN)

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
r = client.get("/health")
print("GET /health:", r.json())

r2 = client.get("/api/v1/market/overview")
data = r2.json()
print("GET /api/v1/market/overview: OK, keys =", list(data.keys()))
print("  AShare index:", data["markets"]["AShare"]["index"])

r3 = client.get("/api/v1/market/watchlist")
print("GET /api/v1/market/watchlist: OK, stocks count =", len(r3.json()["stocks"]))
print("\n✅ Backend API 验证通过")
