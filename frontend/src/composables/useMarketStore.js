/**
 * useMarketStore.js — 全局市场状态（跨组件共享）
 * Phase 2+: 符号规范化（sh/sz/us/hk 前缀）
 */
import { ref, computed } from 'vue'
import { normalizeSymbol, isAShare, isIntradayPeriod } from '../utils/symbols.js'

// ── 模块级单例（uvicorn 进程内唯一）────────────────────────────────
const currentSymbol     = ref('sh000001')   // 规范化格式（含前缀）
const currentSymbolName = ref('上证指数')
const currentColor      = ref('#f87171')
const currentMarket     = ref('AShare')      // AShare | US | HK | JP | Macro

// ── 搜索索引（首次加载后填充）─────────────────────────────────────
const symbolRegistry = ref([])               // [{ symbol, code, name, pinyin, market, type }, ...]
const registryLoaded = ref(false)

// ── 预定义可选标的（与后端 Symbol 完全对齐）────────────────────────
export const SYMBOL_OPTIONS = [
  // A股指数
  { symbol: 'sh000001', code: '000001', name: '上证指数',    color: '#f87171', market: 'AShare' },
  { symbol: 'sh000300', code: '000300', name: '沪深300',    color: '#60a5fa', market: 'AShare' },
  { symbol: 'sz399001', code: '399001', name: '深证成指',    color: '#fbbf24', market: 'AShare' },
  { symbol: 'sz399006', code: '399006', name: '创业板指',   color: '#a78bfa', market: 'AShare' },
  { symbol: 'sh000688', code: '000688', name: '科创50',      color: '#34d399', market: 'AShare' },
  // 全球
  { symbol: 'usNDX',    code: 'NDX',    name: '纳斯达克100', color: '#60a5fa', market: 'US'     },
  { symbol: 'usSPX',   code: 'SPX',    name: '标普500',     color: '#f87171', market: 'US'     },
  { symbol: 'usDJI',   code: 'DJI',    name: '道琼斯',       color: '#a78bfa', market: 'US'     },
  { symbol: 'hkHSI',   code: 'HSI',    name: '恒生指数',     color: '#fbbf24', market: 'HK'     },
  { symbol: 'jpN225',  code: 'N225',   name: '日经225',      color: '#f472b6', market: 'JP'     },
]

// ── 主要指数列表（快速查找）────────────────────────────────────────
export const INDEX_OPTIONS = SYMBOL_OPTIONS.filter(o => o.type !== 'stock')

export function useMarketStore() {
  /**
   * 设置当前标的（自动规范化 symbol 格式）
   */
  function setSymbol(symbol, name, color, market = 'AShare') {
    const norm = normalizeSymbol(symbol)
    currentSymbol.value      = norm
    currentSymbolName.value  = name || norm
    currentColor.value       = color || '#00ff88'
    currentMarket.value      = market
  }

  function getSymbolOption(symbol) {
    const norm = normalizeSymbol(symbol)
    return SYMBOL_OPTIONS.find(s => s.symbol === norm) || SYMBOL_OPTIONS[0]
  }

  /**
   * 加载符号注册表（供 CommandCenter 搜索用）
   */
  async function loadSymbolRegistry() {
    if (registryLoaded.value) return
    try {
      const res = await fetch('/api/v1/market/symbols')
      if (!res.ok) throw new Error('failed')
      const data = await res.json()
      symbolRegistry.value = data.symbols || []
      registryLoaded.value = true
    } catch (e) {
      // 网络失败时使用本地 SYMBOL_OPTIONS 兜底
      symbolRegistry.value = SYMBOL_OPTIONS
      registryLoaded.value = true
    }
  }

  return {
    // 状态
    currentSymbol,
    currentSymbolName,
    currentColor,
    currentMarket,
    symbolRegistry,
    registryLoaded,
    // 方法
    setSymbol,
    getSymbolOption,
    loadSymbolRegistry,
    normalizeSymbol,
    isAShare,
    isIntradayPeriod,
    SYMBOL_OPTIONS,
  }
}
