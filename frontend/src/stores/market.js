/**
 * stores/market.js — Pinia 全局市场状态
 * 替代原 useMarketStore.js（模块级单例 → Pinia Store）
 * 统一管理 currentSymbol / symbolRegistry / 行情缓存池
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { normalizeSymbol, isAShare, isIntradayPeriod } from '../utils/symbols.js'

export const SYMBOL_OPTIONS = [
  { symbol: 'sh000001', code: '000001', name: '上证指数',   color: '#f87171', market: 'AShare' },
  { symbol: 'sh000300', code: '000300', name: '沪深300',    color: '#60a5fa', market: 'AShare' },
  { symbol: 'sz399001', code: '399001', name: '深证成指',   color: '#fbbf24', market: 'AShare' },
  { symbol: 'sz399006', code: '399006', name: '创业板指',  color: '#a78bfa', market: 'AShare' },
  { symbol: 'sh000688', code: '000688', name: '科创50',    color: '#34d399', market: 'AShare' },
  { symbol: 'usNDX',    code: 'NDX',    name: '纳斯达克100', color: '#60a5fa', market: 'US'     },
  { symbol: 'usSPX',   code: 'SPX',    name: '标普500',    color: '#f87171', market: 'US'     },
  { symbol: 'usDJI',   code: 'DJI',    name: '道琼斯',    color: '#a78bfa', market: 'US'     },
  { symbol: 'hkHSI',   code: 'HSI',    name: '恒生指数',   color: '#fbbf24', market: 'HK'     },
  { symbol: 'jpN225',  code: 'N225',   name: '日经225',   color: '#f472b6', market: 'JP'     },
]

export const useMarketStore = defineStore('market', () => {
  // ── 状态 ────────────────────────────────────────────────────
  const currentSymbol     = ref('sh000001')
  const currentSymbolName  = ref('上证指数')
  const currentColor       = ref('#f87171')
  const currentMarket      = ref('AShare')

  // 搜索索引
  const symbolRegistry = ref([])
  const registryLoaded = ref(false)

  // 行情缓存池（key=symbol, value=最新行情对象）
  const quoteCache = ref({})

  // ── 计算属性 ────────────────────────────────────────────────
  const currentNorm = computed(() => normalizeSymbol(currentSymbol.value))
  const isAShareMarket = computed(() => currentMarket.value === 'AShare')

  // ── 方法 ────────────────────────────────────────────────────
  function setSymbol(symbol, name, color, market = 'AShare') {
    const norm = normalizeSymbol(symbol)
    currentSymbol.value     = norm
    currentSymbolName.value = name || norm
    currentColor.value      = color || '#00ff88'
    currentMarket.value     = market
  }

  function getSymbolOption(symbol) {
    const norm = normalizeSymbol(symbol)
    return SYMBOL_OPTIONS.find(s => s.symbol === norm) || SYMBOL_OPTIONS[0]
  }

  async function loadSymbolRegistry() {
    if (registryLoaded.value) return
    try {
      const res = await fetch('/api/v1/market/symbols')
      if (!res.ok) throw new Error('failed')
      const data = await res.json()
      symbolRegistry.value = data.symbols || []
      registryLoaded.value = true
    } catch {
      // 网络失败时使用本地兜底
      symbolRegistry.value = SYMBOL_OPTIONS
      registryLoaded.value = true
    }
  }

  function cacheQuote(symbol, quote) {
    quoteCache.value[symbol] = { ...quote, _ts: Date.now() }
  }

  function getCachedQuote(symbol) {
    return quoteCache.value[symbol] || null
  }

  return {
    // 状态
    currentSymbol, currentSymbolName, currentColor, currentMarket,
    symbolRegistry, registryLoaded, quoteCache,
    // 计算
    currentNorm, isAShareMarket,
    // 方法
    setSymbol, getSymbolOption, loadSymbolRegistry,
    cacheQuote, getCachedQuote,
    normalizeSymbol, isAShare, isIntradayPeriod,
    SYMBOL_OPTIONS,
  }
})
