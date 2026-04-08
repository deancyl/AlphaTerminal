/**
 * CopilotDataService - 统一数据服务
 * 
 * 为 Copilot 提供所有平台数据的统一访问接口
 * 包括：大盘、板块、个股、期货、债券、宏观等数据
 */

import { apiFetch } from '../utils/api.js'

// API 基础路径
const API_BASE = ''

// 缓存配置
const CACHE_TTL = 30000 // 30秒缓存

// 内存缓存
const cache = {
  overview: { data: null, time: 0 },
  sectors: { data: null, time: 0 },
  stocks: { data: null, time: 0 },
  macro: { data: null, time: 0 },
  futures: { data: null, time: 0 },
  northFlow: { data: null, time: 0 },
}

function isCacheValid(key) {
  return cache[key].data && (Date.now() - cache[key].time) < CACHE_TTL
}

// ========== 公开 API ==========

/**
 * 获取大盘概览数据
 */
export async function getMarketOverview() {
  if (isCacheValid('overview')) return cache.overview.data
  try {
    const res = await apiFetch(`${API_BASE}/api/v1/market/overview`, { timeoutMs: 10000 })
    cache.overview = { data: res, time: Date.now() }
    return res
  } catch (e) {
    console.warn('[CopilotData] market overview failed:', e.message)
    return cache.overview.data || null
  }
}

/**
 * 获取板块数据
 */
export async function getSectors() {
  if (isCacheValid('sectors')) return cache.sectors.data
  try {
    const res = await apiFetch(`${API_BASE}/api/v1/market/sectors`, { timeoutMs: 10000 })
    cache.sectors = { data: res, time: Date.now() }
    return res
  } catch (e) {
    console.warn('[CopilotData] sectors failed:', e.message)
    return cache.sectors.data || null
  }
}

/**
 * 获取沪深A股列表（带涨跌幅）
 */
export async function getChinaStocks() {
  if (isCacheValid('stocks')) return cache.stocks.data
  try {
    const res = await apiFetch(`${API_BASE}/api/v1/market/china_all`, { timeoutMs: 15000 })
    cache.stocks = { data: res, time: Date.now() }
    return res
  } catch (e) {
    console.warn('[CopilotData] china stocks failed:', e.message)
    return cache.stocks.data || null
  }
}

/**
 * 获取宏观数据
 */
export async function getMacroData() {
  if (isCacheValid('macro')) return cache.macro.data
  try {
    const res = await apiFetch(`${API_BASE}/api/v1/market/macro`, { timeoutMs: 10000 })
    cache.macro = { data: res, time: Date.now() }
    return res
  } catch (e) {
    console.warn('[CopilotData] macro failed:', e.message)
    return cache.macro.data || null
  }
}

/**
 * 获取期货数据
 */
export async function getFutures() {
  if (isCacheValid('futures')) return cache.futures.data
  try {
    const res = await apiFetch(`${API_BASE}/api/v1/futures/main_indexes`, { timeoutMs: 10000 })
    cache.futures = { data: res, time: Date.now() }
    return res
  } catch (e) {
    console.warn('[CopilotData] futures failed:', e.message)
    return cache.futures.data || null
  }
}

/**
 * 获取北向资金数据（如果有专门的API）
 */
export async function getNorthFlow() {
  if (isCacheValid('northFlow')) return cache.northFlow.data
  try {
    // 尝试从宏观数据中获取北向资金
    const macro = await getMacroData()
    if (macro && macro.north_flow !== undefined) {
      cache.northFlow = { data: macro.north_flow, time: Date.now() }
      return cache.northFlow.data
    }
    return null
  } catch (e) {
    return null
  }
}

/**
 * 搜索股票
 */
export async function searchStock(keyword) {
  const stocks = await getChinaStocks()
  if (!stocks || !Array.isArray(stocks)) return []
  
  const k = keyword.toLowerCase()
  return stocks
    .filter(s => {
      const name = (s.name || '').toLowerCase()
      const symbol = (s.symbol || '').toLowerCase()
      return name.includes(k) || symbol.includes(k) || name.startsWith(k)
    })
    .slice(0, 10)
    .map(s => ({
      symbol: s.symbol,
      name: s.name,
      price: s.price,
      change_pct: s.change_pct,
      volume: s.volume,
      amount: s.amount,
    }))
}

/**
 * 获取涨停股票
 */
export async function getLimitUpStocks() {
  const stocks = await getChinaStocks()
  if (!stocks || !Array.isArray(stocks)) return []
  
  return stocks
    .filter(s => s.change_pct >= 9.5) // 接近涨停
    .sort((a, b) => b.change_pct - a.change_pct)
    .slice(0, 20)
    .map(s => ({
      symbol: s.symbol,
      name: s.name,
      price: s.price,
      change_pct: s.change_pct,
      volume: s.volume,
    }))
}

/**
 * 获取跌停股票
 */
export async function getLimitDownStocks() {
  const stocks = await getChinaStocks()
  if (!stocks || !Array.isArray(stocks)) return []
  
  return stocks
    .filter(s => s.change_pct <= -9.5)
    .sort((a, b) => a.change_pct - b.change_pct)
    .slice(0, 20)
    .map(s => ({
      symbol: s.symbol,
      name: s.name,
      price: s.price,
      change_pct: s.change_pct,
      volume: s.volume,
    }))
}

/**
 * 获取异动股票（涨幅或成交量异常）
 */
export async function getUnusualStocks() {
  const stocks = await getChinaStocks()
  if (!stocks || !Array.isArray(stocks)) return []
  
  // 异动定义：涨幅超过5%或成交量异常放大
  return stocks
    .filter(s => {
      const pct = Math.abs(s.change_pct || 0)
      const volRatio = (s.volume || 0) / (s.avg_volume || 1)
      return pct >= 5 || volRatio >= 3
    })
    .sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct))
    .slice(0, 15)
    .map(s => ({
      symbol: s.symbol,
      name: s.name,
      price: s.price,
      change_pct: s.change_pct,
      volume: s.volume,
      volume_ratio: (s.volume / (s.avg_volume || 1)).toFixed(1),
    }))
}

/**
 * 获取最强/最弱板块
 */
export async function getTopSectors(limit = 5) {
  const sectors = await getSectors()
  if (!sectors || !Array.isArray(sectors)) return { top: [], bottom: [] }
  
  const sorted = [...sectors].sort((a, b) => (b.change_pct || 0) - (a.change_pct || 0))
  
  return {
    top: sorted.slice(0, limit).map(s => ({
      name: s.name,
      change_pct: s.change_pct,
      volume: s.volume,
      stocks: s.stocks || [],
    })),
    bottom: sorted.slice(-limit).reverse().map(s => ({
      name: s.name,
      change_pct: s.change_pct,
      volume: s.volume,
      stocks: s.stocks || [],
    })),
  }
}

/**
 * 获取北向资金净买入/净卖出排名
 */
export async function getNorthFlowRanking() {
  const stocks = await getChinaStocks()
  if (!stocks || !Array.isArray(stocks)) return { topBuy: [], topSell: [] }
  
  // 模拟北向资金数据（实际需要专门的API）
  // 这里用成交量排名作为替代指标
  const sorted = [...stocks]
    .filter(s => s.amount > 0)
    .sort((a, b) => (b.amount || 0) - (a.amount || 0))
  
  return {
    topBuy: sorted.slice(0, 10).map(s => ({
      symbol: s.symbol,
      name: s.name,
      change_pct: s.change_pct,
      amount: s.amount,
    })),
    topSell: sorted.slice(-10).reverse().map(s => ({
      symbol: s.symbol,
      name: s.name,
      change_pct: s.change_pct,
      amount: s.amount,
    })),
  }
}

/**
 * 清除缓存
 */
export function clearCache() {
  Object.keys(cache).forEach(key => {
    cache[key] = { data: null, time: 0 }
  })
}
