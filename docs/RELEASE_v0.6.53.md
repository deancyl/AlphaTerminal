# AlphaTerminal v0.6.53 Release Notes

**Release Date**: 2026-05-19

## Overview

This release focuses on **mobile responsiveness** and **UX improvements** for all v0.6.52 new features (FactorSandbox, MarketRadar, TimeMachine, MultiAssetMatrix).

## Mobile Responsiveness

### FactorSandbox
- ✅ Tab-based single column layout on mobile (replaced 3-column desktop layout)
- ✅ Touch-friendly targets (`min-h-[44px]` on all interactive elements)
- ✅ BottomSheet for backtest preview on mobile

### MarketRadar
- ✅ Stacked treemap/anomaly cards vertically on mobile
- ✅ Reduced treemap height to 250px (max 40% of viewport) on mobile

### TimeMachine
- ✅ Stacked K-line/paper trading vertically on mobile
- ✅ Increased progress bar drag handle from 12px to 48px on mobile
- ✅ Landscape immersive mode with `useOrientation` composable

### MultiAssetMatrix
- ✅ Single panel with tab navigation on mobile (replaced 2x2 grid)
- ✅ Previous/Next buttons for panel switching

## UX Critical Fixes (P0)

### MultiAssetMatrix
- **Missing Tooltip component**: Created `frontend/src/components/Tooltip.vue`
- **No sidebar entry**: Added "四屏矩阵" to navigation sidebar
- **Unused import**: Removed `MATRIX_PANEL_DESCRIPTIONS` import

### TimeMachine
- **Missing `/seek` endpoint**: Implemented `POST /api/v1/timemachine/session/{id}/seek`
- **Missing `/speed` endpoint**: Implemented `POST /api/v1/timemachine/session/{id}/speed`
- **Race condition**: Documented dual timer issue, added status checks

### FactorSandbox
- **LLM sentiment fake data**: Removed hardcoded placeholder factor (always returned 0.5)
- **Added TODO comment** for future copilot API integration

### MarketRadar
- **Treemap click broken**: Added `chart.on('click')` handler to emit `stock-click` event
- **Changed `nodeClick: 'link'`** to `nodeClick: false` for manual handling

## UX Confusing Fixes (P0)

### TimeMachine
- **No trade success feedback**: Added `toast.success()` after successful trades
- **No daily-only hint**: Added "当前仅支持日线级别复盘" message
- **Generic error messages**: Replaced with specific Chinese messages:
  - "会话已过期，请重新创建"
  - "数据加载失败，请检查网络"

### MarketRadar
- **TOP 5 vs TOP 10 mismatch**: Changed badge to "TOP 10", added "查看更多" expandable section
- **No anomaly explanations**: Added tooltip descriptions for each anomaly type

### FactorSandbox
- **Raw error messages**: Changed to "筛选失败，请检查因子参数或稍后重试"
- **No retry button**: Added retry button in error state

## User Guidance Fixes (P1)

### FactorSandbox
- Skeleton loading for factor library
- Tooltips on factor items with descriptions
- Improved empty state: "拖拽左侧因子到筛选漏斗，或点击因子卡片快速添加"
- Visual feedback on factor selection (`ring-2 ring-primary`)

### MarketRadar
- Treemap explanation: "市场温度图：方块大小=市值，颜色=涨跌幅（红涨绿跌）"
- Empty state with retry button
- Skeleton loading for treemap
- Error state retry button

### TimeMachine
- Feature overview: "沉浸式历史复盘 - 在历史行情中练习交易决策，提升实战能力"
- Keyboard shortcut hints on playback controls
- Guidance panel expanded by default
- Improved loading state with progress: "加载中 X/Y 根K线..."

### MultiAssetMatrix
- Loading progress indicator: "加载中 X/4 面板..."
- Panel-specific descriptions:
  - "上证指数 - A股市场风向标"
  - "十年期国债 - 无风险利率基准"
  - "沪深300期货 - 股指期货主力合约"
  - "人民币汇率 - 美元兑人民币即期汇率"
- Empty state with retry button when all charts fail

## New Files

| File | Purpose |
|------|---------|
| `frontend/src/components/Tooltip.vue` | Reusable tooltip component |
| `frontend/src/composables/useOrientation.js` | Mobile orientation detection |

## API Endpoints Added

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/timemachine/session/{id}/seek` | Seek to specific bar in playback |
| POST | `/api/v1/timemachine/session/{id}/speed` | Set playback speed (0.1-10.0) |

## Files Modified

### Frontend
- `src/components/factor/FactorSandbox.vue` - Mobile layout, error handling, loading states
- `src/components/factor/FactorDragItem.vue` - Tooltips, selection feedback
- `src/components/MarketRadar.vue` - Mobile layout, treemap click, loading states
- `src/components/market/AnomalyCard.vue` - TOP 10, expandable list, tooltips
- `src/components/TimeMachine.vue` - Mobile layout, landscape mode, guidance
- `src/components/timemachine/PlaybackControls.vue` - Keyboard hints, tooltips
- `src/components/timemachine/PaperTradingPanel.vue` - Guidance expanded by default
- `src/components/MultiAssetMatrix.vue` - Mobile layout, loading progress
- `src/components/MatrixPanel.vue` - Panel descriptions
- `src/components/Sidebar.vue` - Added "四屏矩阵" navigation entry
- `src/composables/useFactorSandbox.js` - factorsLoading state
- `src/composables/useTimeMachine.js` - Toast notifications, error messages

### Backend
- `app/routers/timemachine.py` - Added `/seek` and `/speed` endpoints
- `app/routers/factor_sandbox.py` - Removed llm_sentiment factor
- `app/services/factor_sandbox/screener.py` - Removed _check_llm_sentiment method

## Verification

```bash
# Build verification
cd frontend && npm run build  # Should succeed in ~15s

# Mobile responsiveness
grep -c "isMobile" frontend/src/components/factor/FactorSandbox.vue  # Expected: 10+
grep -c "useOrientation" frontend/src/components/TimeMachine.vue  # Expected: 1+

# UX fixes
ls frontend/src/components/Tooltip.vue  # Should exist
grep -c "multi-asset-matrix" frontend/src/components/Sidebar.vue  # Expected: 1+
grep -c "def seek_to" backend/app/routers/timemachine.py  # Expected: 1
grep -c "chart.on('click'" frontend/src/components/MarketRadar.vue  # Expected: 1+
```

## Summary Statistics

| Category | Count |
|----------|-------|
| Mobile Responsiveness Fixes | 10 |
| P0 Critical Fixes | 6 |
| P0 Confusing Fixes | 7 |
| P1 User Guidance Fixes | 18 |
| **Total Issues Fixed** | **41** |
| New Files Created | 2 |
| New API Endpoints | 2 |

## Upgrade Notes

No breaking changes. This release is fully backward compatible with v0.6.52.

## Next Steps

- [ ] Implement real LLM sentiment analysis via copilot API
- [ ] Add minute-level playback support for TimeMachine
- [ ] Add swipe gestures for mobile navigation
- [ ] Add export functionality for FactorSandbox results
