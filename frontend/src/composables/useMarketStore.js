/**
 * useMarketStore.js — 全局市场状态（跨组件共享）
 * Phase 2: 打破信息孤岛，全局联动
 */
import { ref } from 'vue'

// ── 模块级单例（uvicorn 进程内唯一）────────────────────────────────
const currentSymbol     = ref('000001')
const currentSymbolName = ref('上证指数')
const currentColor     = ref('#f87171')

// ── 预定义可选标的（与后端 Symbol 完全对齐）────────────────────────
export const SYMBOL_OPTIONS = [
  // A股指数
  { symbol: '000001', name: '上证指数',   color: '#f87171', market: 'AShare' },
  { symbol: '000300', name: '沪深300',   color: '#60a5fa', market: 'AShare' },
  { symbol: '399001', name: '深证成指',   color: '#fbbf24', market: 'AShare' },
  { symbol: '399006', name: '创业板指',   color: '#a78bfa', market: 'AShare' },
  { symbol: '000688', name: '科创50',     color: '#34d399', market: 'AShare' },
  // 全球
  { symbol: 'ndx',    name: '纳斯达克',   color: '#60a5fa', market: 'US' },
  { symbol: 'spx',    name: '标普500',    color: '#f87171', market: 'US' },
  { symbol: 'dji',    name: '道琼斯',     color: '#a78bfa', market: 'US' },
  { symbol: 'hsi',    name: '恒生指数',   color: '#fbbf24', market: 'HK' },
  { symbol: 'nikkei', name: '日经225',   color: '#f472b6', market: 'JP' },
]

export function useMarketStore() {
  function setSymbol(symbol, name, color) {
    currentSymbol.value      = symbol
    currentSymbolName.value  = name || symbol
    currentColor.value       = color || '#00ff88'
  }

  function getSymbolOption(symbol) {
    return SYMBOL_OPTIONS.find(s => s.symbol === symbol) || SYMBOL_OPTIONS[0]
  }

  return {
    currentSymbol,
    currentSymbolName,
    currentColor,
    setSymbol,
    getSymbolOption,
    SYMBOL_OPTIONS,
  }
}
