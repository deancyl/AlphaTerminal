# AlphaTerminal v0.6.45 Release Notes

**Release Date**: 2026-05-17

## Summary

This release includes critical bug fixes for bond yield spread chart, options analysis, forex and futures modules, along with a new ML strategy module and significant infrastructure improvements.

## Bug Fixes

### Bond Module
- **fix(bond)**: Resolve yield spread chart 10Y-2Y data issue
  - Changed from 10Y-2Y to 10Y-3Y spread because akshare `bond_china_yield()` API does not return "2年" column
  - Available columns: 1年, 3年, 5年, 7年, 10年, 30年
  - Files: `YieldSpreadChart.vue`, `BondDashboard.vue`

### Options Module
- **fix(options)**: Resolve OptionsAnalysis double nested data access
  - Fixed accessing `data.data.data` instead of `data.data` for options chain display
  - Files: `OptionsAnalysis.vue`

### Forex Module
- **fix(forex)**: Add timeout protection and HTTP polling fallback
  - Added `asyncio.wait_for` timeout protection to forex endpoints
  - Implemented HTTP polling fallback after 3 WebSocket reconnect failures
  - Files: `forex.py`, `useMarketStream.js`

### Futures Module
- **fix(futures)**: Add real data support and fix color attributes
  - Added real-time data fetch from akshare for index futures
  - Fixed FundFlowPanel color attribute names (`color` -> `backgroundColor`)
  - Files: `futures.py`, `FundFlowPanel.vue`

## New Features

### Macro Module
- **feat(macro)**: Add BFF endpoint for single API call
  - Added `/api/v1/macro/dashboard` BFF endpoint
  - Reduced frontend API calls from 10 to 1
  - Improved error handling with safe column access
  - Files: `macro.py`, `MacroDashboard.vue`, `macro.js`

### Global Index
- **feat(global-index)**: Expand coverage from 8 to 27 global indices
  - Added 19 new global indices including Asia, Europe, Americas, and commodities
  - Improved layout with responsive grid
  - Files: `GlobalIndex.vue`

### ML Strategy Module (NEW)
- **feat(ml)**: Add ML strategy module with Qlib integration
  - **Supported Models**: LightGBM, HIST, GATE, GRU, LSTM, MLP, XGBoost, CatBoost
  - **Feature Sets**: Alpha158 (158 features), Alpha360 (360 features)
  - **Portfolio Optimization**: MVO, GMV, Risk Parity, Inverse Volatility
  - **API Endpoints**:
    - `GET/POST /api/v1/ml/models` - Model CRUD
    - `POST /api/v1/ml/train` - Train ML model
    - `POST /api/v1/ml/predict` - Generate predictions
    - `POST /api/v1/ml/optimize` - Portfolio optimization
    - `POST /api/v1/ml/factors` - Factor analysis
    - `POST /api/v1/ml/risk-metrics` - Risk metrics calculation
  - **Frontend Components**: `MLStrategyPanel.vue`, `MLModelManager.vue`, `MLTrainingPanel.vue`, `MLPredictionPanel.vue`, `MLPortfolioOptimizer.vue`, `MLFactorAnalysis.vue`

### Backend Infrastructure
- **feat(backend)**: Add infrastructure improvements and documentation
  - Data cache with TTL and LRU eviction
  - Adaptive circuit breaker with state machine
  - Unified fetcher with source priority
  - Source health monitoring
  - Copilot context assembler and query classifier
  - K-line gap detector and incremental fetcher
  - New schemas: `bond.js`, `forex.js`, `futures.js`, `ml.js`

## API Changes

### New Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/macro/dashboard` | BFF endpoint for all macro data |
| GET/POST | `/api/v1/ml/models` | ML model management |
| POST | `/api/v1/ml/train` | Train ML model |
| POST | `/api/v1/ml/predict` | Generate predictions |
| POST | `/api/v1/ml/optimize` | Portfolio optimization |
| POST | `/api/v1/ml/factors` | Factor analysis |
| POST | `/api/v1/ml/risk-metrics` | Risk metrics calculation |

## File Changes Summary

| Category | Files Changed |
|----------|---------------|
| Frontend Components | 15 |
| Backend Routers | 8 |
| Backend Services | 20+ |
| Tests | 10 |
| Documentation | 2 |

## Upgrade Notes

1. **Bond Yield Spread**: The yield spread chart now displays 10Y-3Y instead of 10Y-2Y
2. **ML Strategy**: New ML strategy module requires Qlib installation for full functionality
3. **Macro BFF**: Frontend now uses single BFF endpoint instead of 10 separate API calls

## Verification Commands

```bash
# Bond yield spread
curl "http://localhost:60100/api/v1/bond/history?tenor=10年&period=1Y" | jq '.data.history | length'
curl "http://localhost:60100/api/v1/bond/history?tenor=3年&period=1Y" | jq '.data.history | length'

# ML endpoints
curl "http://localhost:60100/api/v1/ml/health"
curl "http://localhost:60100/api/v1/ml/methods"

# Macro BFF
curl "http://localhost:60100/api/v1/macro/dashboard" | jq '.data | keys'
```

## Contributors

- Sisyphus (AI Agent)

---

**Previous Release**: [v0.6.44](./RELEASE_v0.6.44.md)
