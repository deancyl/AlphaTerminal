# Release v0.6.51

## Summary

This release addresses a critical P0 incident (Bond/Futures/Macro modules crashing), fixes 10 QA/UX vulnerabilities, and adds 5 new admin panel features.

## P0 Incident Fix

### Problem
Bond, Futures, and Macro modules were experiencing crashes and timeouts due to:
- Shared default thread pool causing resource contention
- No request coalescing leading to thundering herd problem
- Event loop anti-pattern causing deadlocks
- Aggressive timeouts (5s) for slow akshare APIs

### Solution
1. **Thread Pool Isolation**: Created dedicated ThreadPoolExecutor for bond (8 workers) and futures (10 workers)
2. **Request Coalescing**: Migrated to `cache.get_or_set_async()` for automatic request deduplication
3. **Event Loop Fix**: Removed `asyncio.new_event_loop()` in sync context
4. **Timeout Adjustment**: Increased futures timeout from 5s to 15s
5. **Singleflight Utility**: Production-grade request deduplication with asyncio.shield()
6. **Bond Pre-fetch**: Added scheduler job to pre-warm bond data cache

## QA Audit Fixes

| Issue | Severity | Solution |
|-------|----------|----------|
| KeepAlive no :max limit | HIGH | Added `:max="10"` to limit cached components |
| ECharts context exhaustion | HIGH | Added `onDeactivated` cleanup to 6 components |
| Large JSON blocks event loop | HIGH | Configured orjson as default response class |
| Rate limiter multi-worker bypass | HIGH | Implemented SQLite-backed rate limiter with WAL mode |
| Deep pagination spike | HIGH | Implemented keyset pagination for audit logs |

## New Admin Features

### 1. Data Gap Radar
- Calendar heatmap showing missing market data
- One-click backfill for missing dates
- Price anomaly detection (>20% change alerts)

### 2. LLM Cost Attribution
- Sankey diagram for cost flow visualization
- Prompt tree viewer for session analysis
- Cost breakdown by workflow, model, or session

### 3. Backtest Sandbox Monitor
- Real-time CPU/memory metrics for running backtests
- Kill button for runaway processes
- WebSocket streaming for live updates

### 4. Source Switchboard
- Visual topology of data sources
- Circuit breaker status indicators
- Manual fallback switching

### 5. Audit Playback
- Diff view of configuration changes
- Time-travel rollback capability
- Hash chain verification

## Files Changed

- **Backend**: 21 files modified, 8 files created
- **Frontend**: 12 files modified, 4 files created
- **Tests**: 11 new unit tests for Singleflight

## API Endpoints Added

| Endpoint | Description |
|----------|-------------|
| `/api/v1/data_gaps/*` | Data gap scanning and backfill |
| `/api/v1/cost_attribution/*` | LLM cost attribution analysis |
| `/api/v1/backtest_monitor/*` | Backtest worker monitoring |
| `/api/v1/audit_playback/*` | Audit trail playback and rollback |
| `/api/v1/admin/sources/topology` | Data source topology |

## Upgrade Notes

1. **orjson dependency**: Run `pip install orjson>=3.9.0`
2. **Database migration**: New `rate_limits` table created automatically
3. **Scheduler update**: Bond polling job added (60s interval)

## Verification

```bash
# Check thread pool isolation
grep "_executor = ThreadPoolExecutor" backend/app/routers/bond.py backend/app/routers/futures.py

# Check Singleflight
pytest backend/tests/unit/test_utils/test_singleflight.py -v

# Check new endpoints
curl http://localhost:60100/api/v1/data_gaps/health
curl http://localhost:60100/api/v1/cost_attribution/health
curl http://localhost:60100/api/v1/backtest_monitor/metrics
curl http://localhost:60100/api/v1/audit_playback/stats
```

## Contributors

- Sisyphus (Orchestrator)
- Metis (Plan Consultant)
- Sisyphus-Junior (Implementation)

## Release Date

2026-05-19
