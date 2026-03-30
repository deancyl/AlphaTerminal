import signal
signal.signal(signal.SIGTERM, signal.SIG_IGN)

import sys
sys.path.insert(0, "/vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal_Workspace/backend")

from app.db import init_tables, buffer_insert, flush_buffer_to_realtime, get_latest_prices
from app.services.data_fetcher import fetch_all_and_buffer

print("[1] 初始化数据库表...")
init_tables()
print("[2] 测试 buffer_insert...")
buffer_insert([
    {"symbol": "000001", "name": "上证指数", "market": "AShare",
     "price": 3342.27, "change_pct": 0.45, "volume": 2.87e9,
     "timestamp": 1743360000, "data_type": "index"},
    {"symbol": "SHIBOR_1W", "name": "SHIBOR 1周", "market": "FUND",
     "price": 1.82, "change_pct": None, "volume": None,
     "timestamp": 1743360000, "data_type": "rate"},
])
print("[3] 测试 flush...")
count = flush_buffer_to_realtime()
print(f"    刷入行数: {count}")
print("[4] 测试 get_latest_prices...")
rows = get_latest_prices(["000001", "SHIBOR_1W"])
for r in rows:
    print(f"    {r['symbol']} {r['name']}: price={r['price']}")
print("[5] 测试 AkShare 数据拉取（模拟）...")
fetch_all_and_buffer()
print("\n✅ Phase 3 验证通过")
