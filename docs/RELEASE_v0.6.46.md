# AlphaTerminal v0.6.46 Release Notes

**Release Date**: 2026-05-18

## Summary

This release fixes critical issues in the bond module: Thundering Herd cache stampede prevention and API parameter format correction.

## Bug Fixes

### Bond Module - Backend
- **fix(bond)**: Add asyncio.Lock to prevent Thundering Herd cache stampede
  - Implemented double-checked locking pattern for cache protection
  - Prevents multiple concurrent requests from triggering simultaneous akshare data fetches
  - File: `backend/app/routers/bond.py`

- **fix(bond)**: Filter treasury bond curve data
  - Added filtering for "国债" (treasury bond) keyword to prevent mixed credit bond data
  - Sort by date for correct chart rendering
  - Prevents historical chart data points from becoming severely disordered
  - File: `backend/app/routers/bond.py`

### Bond Module - Frontend
- **fix(frontend)**: Correct BondDashboard API call parameter format
  - Changed `apiFetch` timeout parameter from number (`10000`) to object format (`{ timeoutMs: 25000, retries: 0 }`)
  - Increased timeout to 25 seconds to accommodate slow akshare data fetches
  - Disabled retries to prevent timeout retry loop
  - File: `frontend/src/components/BondDashboard.vue`

## Technical Details

### Thundering Herd Prevention

Before this fix, when multiple components simultaneously requested bond history data:
1. Each request would check the cache and find it empty
2. All requests would simultaneously call `ak.bond_china_yield()`
3. The data source (Sina/EastMoney) would be overwhelmed and cut off responses
4. Threads would hang, causing the entire system to freeze

After this fix:
1. First request acquires the asyncio.Lock
2. Other requests wait at the lock
3. First request fetches data and populates cache
4. Other requests perform double-check and find cached data
5. No redundant API calls, no thread pool exhaustion

### Treasury Bond Filtering

The akshare `bond_china_yield()` API returns data for multiple bond types:
- 中债国债收益率曲线
- 中债商业银行普通债收益率曲线
- 中债中短期票据收益率曲线
- etc.

Without filtering, the historical chart would mix data from different bond types, causing severe rendering errors.

## API Changes

No API endpoint changes. All changes are internal improvements.

## Verification Commands

```bash
# Test bond history API (should return ~246 records)
curl "http://localhost:60100/api/v1/bond/history?tenor=10年&period=1Y" | jq '.data.history | length'

# Test concurrent requests (should not cause timeout)
curl "http://localhost:60100/api/v1/bond/history?tenor=10年&period=1Y" &
curl "http://localhost:60100/api/v1/bond/history?tenor=3年&period=1Y" &
wait
```

## File Changes Summary

| File | Changes |
|------|---------|
| `backend/app/routers/bond.py` | +52 lines, -21 lines |
| `frontend/src/components/BondDashboard.vue` | +2 lines, -2 lines |

## Contributors

- Sisyphus (AI Agent)

---

**Previous Release**: [v0.6.45](./RELEASE_v0.6.45.md)
