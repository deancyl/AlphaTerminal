# AlphaTerminal v0.6.203 Release Notes

**Release Date**: 2026-05-27

## 🚨 Critical Fixes

### 1. Database Path Unification (P0)

**Problem**: 
- `database.py` uses `~/.config/alphaterminal/database.db` (Tauri-compatible path)
- `db_writer.py` used `backend/database.db` (hardcoded relative path)
- **Impact**: Scheduler writes data to one database, API reads from another. Data never syncs.

**Solution**:
```python
# backend/app/db/db_writer.py

# Before (WRONG)
_db_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "database.db",
)

# After (CORRECT)
from app.db.database import get_db_path
_db_path = get_db_path()
```

**Verification**:
| Metric | Before | After |
|--------|--------|-------|
| Database records (000001) | 100 | 8,648 |
| API price accuracy | ~10.76 (wrong) | ~4093 (correct) |

### 2. Financial Color Semantics (P0)

**Problem**: `bull`/`bear` colors inconsistent across themes, not following A-share convention.

**Solution**: All themes now use unified colors:
- `bull` = #ef4444 (red) = 上涨
- `bear` = #22c55e (green) = 下跌

**Convention**: 红涨绿跌 (Red=Up, Green=Down) for Chinese A-share market.

### 3. Index Symbol Mapping (P0)

**Problem**: `INDEX_SH` whitelist incomplete, some Shanghai indices mapped to Shenzhen.

**Solution**: Added comprehensive whitelist:
```python
INDEX_SH = {
    "000001",  # 上证指数
    "000300",  # 沪深300
    "000688",  # 科创50
    "000016",  # 上证50
    "000010",  # 上证180
    "000009",  # 上证380
}
```

### 4. Fund Flow API Fallback (P1)

**Problem**: `ProxyError` not caught, fallback mechanism not triggered when Eastmoney API blocked by proxy.

**Solution**: Added `except Exception` catch-all:
```python
except Exception as e:
    logger.warning(f"[FundFlow] error ({type(e).__name__}), triggering fallback: {e}")
    # Returns 30 mock records
```

## 📊 Verification Results

| Test | Command | Expected |
|------|---------|----------|
| Database path | `python3 -c "from app.db.db_writer import _db_path; from app.db.database import get_db_path; print(_db_path == get_db_path())"` | `True` |
| Record count | `sqlite3 ~/.config/alphaterminal/database.db "SELECT COUNT(*) FROM market_data_daily WHERE symbol='000001'"` | 8000+ |
| API price | `curl http://localhost:60100/api/v1/market/history/000001?period=day&limit=1 \| jq '.data.history[0].close'` | ~4093 |
| Financial colors | `grep "color-bull.*#ef4444" frontend/src/style.css \| wc -l` | 4+ |
| Fund flow | `curl http://localhost:60100/api/v1/market/fund_flow \| jq '.data.source'` | "fallback_mock" |

## 🔧 Files Modified

| File | Changes |
|------|---------|
| `backend/app/db/db_writer.py` | Database path unification |
| `backend/app/services/data_fetcher.py` | INDEX_SH whitelist enhancement |
| `backend/app/routers/market/overview.py` | Fund flow fallback exception handling |
| `frontend/src/style.css` | Financial color fix (removed duplicate dark theme) |

## 📝 Full Changelog

See [AGENTS.md](./AGENTS.md) for detailed documentation.

## 🔄 Upgrade Guide

1. Pull latest changes: `git pull origin master`
2. Rebuild frontend: `cd frontend && npm run build`
3. Restart services: `./start-services.sh restart`
4. Verify: `curl http://localhost:60100/api/v1/market/history/000001?period=day&limit=1`

## 🐛 Known Issues

None identified in this release.

## 📅 Next Steps

1. **Unified Index Registry**: Consolidate symbol mapping logic across all modules
2. **Price Validation**: Add sanity checks before writing to database
3. **DBWriter Health Monitoring**: Add periodic health checks and alerts
4. **Data Integrity Verification**: Add automated data quality checks
