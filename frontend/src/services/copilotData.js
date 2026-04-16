/**
 * CopilotDataService - 适配 AlphaTerminal 实际 API
 * 
 * 真实数据源:
 * - /api/v1/market/overview - 大盘指数
 * - /api/v1/market/sectors - 板块数据
 * - /api/v1/market/macro - 宏观数据
 * - /api/v1/stocks/limit_up - 涨停股票 (akshare)
 * - /api/v1/stocks/limit_down - 跌停股票 (akshare)
 * - /api/v1/stocks/unusual - 异动股票 (akshare)
 * - /api/v1/stocks/quote - 实时行情 (腾讯)
 * - /api/v1/stocks/search - 股票搜索 (akshare)
 */

import { apiFetch } from '../utils/api.js'
import { logger } from '../utils/logger.js'

const API_BASE = ''

// 30秒缓存
const cache = {}
function getCached(key, fetchFn, ttl = 30000) {
  const now = Date.now()
  if (cache[key] && (now - cache[key].time) < ttl) {
    return Promise.resolve(cache[key].data)
  }
  return fetchFn().then(data => {
    cache[key] = { data, time: now }
    return data
  }).catch(e => {
    if (cache[key]) return cache[key].data
    throw e
  })
}

// ========== 主要数据 API ==========

/**
 * 获取大盘指数
 */
export async function getMarketOverview() {
  return getCached('marketOverview', async () => {
    const res = await apiFetch(`${API_BASE}/api/v1/market/overview`, { timeoutMs: 10000 })
    const wind = res?.wind || {}
    
    // 实际返回: { wind: {'000001': {name, price, change_pct, volume, status, market}, meta: {...} }
    const indices = Object.values(wind)
      .filter(v => v && v.price !== undefined && v.market !== 'HK')
      .slice(0, 10)
    
    // 按市场惯例排序: 上证 → 沪深 → 深证 → 创业板
    const ORDER = { 'AShare_sh': 0, 'IF': 1, 'IC': 2, 'IM': 3 }
    indices.sort((a, b) => {
      // 将 sh000, sz399 等符号标准化排序
      const keyA = (a.market || '') + (a.symbol || '')
      const keyB = (b.market || '') + (b.symbol || '')
      return (ORDER[keyA] ?? 99) - (ORDER[keyB] ?? 99)
    })
    
    return {
      indices,
      meta: res?.meta || {},
    }
  })
}

/**
 * 获取板块数据
 */
export async function getSectors() {
  return getCached('sectors', async () => {
    const res = await apiFetch(`${API_BASE}/api/v1/market/sectors`, { timeoutMs: 10000 })
    const sectors = Array.isArray(res) ? res : (res?.sectors || [])
    return sectors
  })
}

/**
 * 获取宏观数据
 */
export async function getMacroData() {
  return getCached('macro', async () => {
    const res = await apiFetch(`${API_BASE}/api/v1/market/macro`, { timeoutMs: 10000 })
    return Array.isArray(res) ? res : (res?.macro || [])
  })
}

/**
 * 获取大盘样本股票
 */
export async function getChinaStocks() {
  return getCached('chinaStocks', async () => {
    const res = await apiFetch(`${API_BASE}/api/v1/market/china_all`, { timeoutMs: 10000 })
    const stocks = Array.isArray(res) ? res : (res?.china_all || [])
    return stocks
  }, 15000)
}

// ========== 涨停/跌停/异动 (真实数据) ==========

/**
 * 获取涨停股票 - 真实数据
 */
export async function getLimitUpStocks() {
  return getCached('limitUp', async () => {
    try {
      const res = await apiFetch(`${API_BASE}/api/v1/stocks/limit_up`, { timeoutMs: 15000 })
      const data = res?.limit_up || res || []
      return data
    } catch (e) {
      logger.warn('[CopilotData] limit_up failed:', e.message)
      return []
    }
  }, 60000) // 1分钟缓存
}

/**
 * 获取跌停股票 - 真实数据
 */
export async function getLimitDownStocks() {
  return getCached('limitDown', async () => {
    try {
      const res = await apiFetch(`${API_BASE}/api/v1/stocks/limit_down`, { timeoutMs: 15000 })
      const data = res?.limit_down || res || []
      return data
    } catch (e) {
      logger.warn('[CopilotData] limit_down failed:', e.message)
      return []
    }
  }, 60000)
}

/**
 * 获取异动股票 - 真实数据
 */
export async function getUnusualStocks() {
  return getCached('unusual', async () => {
    try {
      const res = await apiFetch(`${API_BASE}/api/v1/stocks/unusual`, { timeoutMs: 15000 })
      const data = res?.unusual || res || []
      return data
    } catch (e) {
      logger.warn('[CopilotData] unusual failed:', e.message)
      return []
    }
  }, 60000)
}

/**
 * 获取涨跌停汇总
 */
export async function getLimitSummary() {
  return getCached('limitSummary', async () => {
    try {
      const res = await apiFetch(`${API_BASE}/api/v1/stocks/limit_summary`, { timeoutMs: 15000 })
      return res || {}
    } catch (e) {
      logger.warn('[CopilotData] limit_summary failed:', e.message)
      return {}
    }
  }, 60000)
}

// ========== 股票搜索 ==========

/**
 * 搜索股票
 */
export async function searchStock(keyword) {
  if (!keyword || keyword.length < 1) return []
  
  const k = keyword.trim().toLowerCase()
  
  // 1. 先在本地数据库搜索
  const dbResults = []
  for (const [sym, info] of Object.entries(STOCK_DB)) {
    if (sym.toLowerCase().includes(k) || info.name.toLowerCase().includes(k)) {
      dbResults.push({
        symbol: sym,
        name: info.name,
        market: info.market,
        price: null,
        change_pct: null,
      })
    }
  }
  
  // 2. 从后端搜索真实股票
  try {
    const res = await apiFetch(`${API_BASE}/api/v1/stocks/search?q=${encodeURIComponent(k)}`, { timeoutMs: 10000 })
    const stocks = Array.isArray(res) ? res : (res?.stocks || [])
    for (const s of stocks) {
      const sym = (s.code?.startsWith('6') ? 'sh' : 'sz') + s.code
      if (!dbResults.find(r => r.symbol === sym)) {
        dbResults.push({
          symbol: sym,
          name: s.name,
          market: s.code?.startsWith('6') ? 'sh' : 'sz',
          price: null,
          change_pct: null,
        })
      }
    }
  } catch (e) {
    logger.warn('[CopilotData] search failed:', e.message)
  }
  
  return dbResults.slice(0, 15)
}

/**
 * 获取股票实时行情
 */
export async function getStockQuote(symbol) {
  // 先检查缓存 (10秒)
  const cacheKey = `quote_${symbol}`
  if (cache[cacheKey] && (Date.now() - cache[cacheKey].time) < 10000) {
    return cache[cacheKey].data
  }
  
  try {
    const res = await apiFetch(`${API_BASE}/api/v1/stocks/quote?symbol=${encodeURIComponent(symbol)}`, { timeoutMs: 8000 })
    if (res && res.price !== undefined) {
      cache[cacheKey] = { data: res, time: Date.now() }
      return res
    }
  } catch (e) {
    logger.warn('[CopilotData] quote failed for', symbol, e.message)
  }
  return null
}

/**
 * 获取股票分析报告
 */
export async function getStockAnalysis(symbol, name) {
  const quote = await getStockQuote(symbol)
  const overview = await getMarketOverview()
  const sectors = await getSectors()
  
  return {
    symbol,
    name,
    quote,
    overview,
    sectors,
    timestamp: Date.now(),
  }
}

// ========== 北向资金 ==========

/**
 * 获取最强/最弱板块
 */
export async function getTopSectors(limit = 5) {
  const sectors = await getSectors()
  if (!sectors || sectors.length === 0) {
    return { top: [], bottom: [] }
  }
  
  const sorted = [...sectors].sort((a, b) => (b.change_pct || 0) - (a.change_pct || 0))
  
  return {
    top: sorted.slice(0, limit),
    bottom: sorted.slice(-limit).reverse(),
  }
}

/**
 * 获取北向资金数据（暂无真实API，用SHIBOR替代或模拟）
 */
export async function getNorthFlowRanking() {
  // 北向资金需要专门的港交所数据接口，暂时用模拟
  const mockData = {
    topBuy: [
      { symbol: 'sh600519', name: '贵州茅台', amount: 12.5 },
      { symbol: 'sz300750', name: '宁德时代', amount: 8.3 },
      { symbol: 'sh601318', name: '中国平安', amount: 6.2 },
      { symbol: 'sz000333', name: '美的集团', amount: 5.8 },
      { symbol: 'sh600036', name: '招商银行', amount: 4.5 },
    ],
    topSell: [
      { symbol: 'sh601012', name: '隆基绿能', amount: -3.2 },
      { symbol: 'sz002594', name: '比亚迪', amount: -2.8 },
      { symbol: 'sh600028', name: '中国石化', amount: -1.9 },
      { symbol: 'sh600050', name: '中国联通', amount: -1.2 },
      { symbol: 'sz000002', name: '万科A', amount: -0.8 },
    ],
    note: '⚠️ 北向资金数据为参考模拟，实际数据需接入港交所深港通/沪港通专项接口',
  }
  return mockData
}

// ========== 股票代码数据库 (扩展版) ==========
// 覆盖 A 股主要股票，便于离线搜索

const STOCK_DB = {
  // === 指数 ===
  'sh000001': { name: '上证指数', market: 'sh' },
  'sz399001': { name: '深证成指', market: 'sz' },
  'sz399006': { name: '创业板指', market: 'sz' },
  'sh000300': { name: '沪深300', market: 'sh' },
  'sh000016': { name: '上证50', market: 'sh' },
  'sh000688': { name: '科创50', market: 'sh' },
  'sh000905': { name: '中证500', market: 'sh' },
  'sh000852': { name: '中证1000', market: 'sh' },
  
  // === 沪市主板 ===
  'sh600519': { name: '贵州茅台', market: 'sh' },
  'sh601318': { name: '中国平安', market: 'sh' },
  'sh600036': { name: '招商银行', market: 'sh' },
  'sh601398': { name: '工商银行', market: 'sh' },
  'sh601939': { name: '建设银行', market: 'sh' },
  'sh600028': { name: '中国石化', market: 'sh' },
  'sh601857': { name: '中国石油', market: 'sh' },
  'sh600276': { name: '恒瑞医药', market: 'sh' },
  'sh600900': { name: '长江电力', market: 'sh' },
  'sh601166': { name: '兴业银行', market: 'sh' },
  'sh600585': { name: '海螺水泥', market: 'sh' },
  'sh600887': { name: '伊利股份', market: 'sh' },
  'sh601012': { name: '隆基绿能', market: 'sh' },
  'sh600030': { name: '中信证券', market: 'sh' },
  'sh601888': { name: '中国中免', market: 'sh' },
  'sh600050': { name: '中国联通', market: 'sh' },
  'sh601668': { name: '中国建筑', market: 'sh' },
  'sh600048': { name: '保利发展', market: 'sh' },
  'sh600309': { name: '万华化学', market: 'sh' },
  'sh601328': { name: '交通银行', market: 'sh' },
  'sh600837': { name: '海通证券', market: 'sh' },
  'sh600031': { name: '三一重工', market: 'sh' },
  'sh600406': { name: '国电南瑞', market: 'sh' },
  'sh601288': { name: '农业银行', market: 'sh' },
  'sh601628': { name: '中国人寿', market: 'sh' },
  'sh601088': { name: '中国神华', market: 'sh' },
  'sh601899': { name: '紫金矿业', market: 'sh' },
  'sh600089': { name: '特变电工', market: 'sh' },
  'sh601225': { name: '陕西煤业', market: 'sh' },
  'sh600547': { name: '山东黄金', market: 'sh' },
  'sh600104': { name: '上汽集团', market: 'sh' },
  'sh601668': { name: '中国中铁', market: 'sh' },
  'sh600018': { name: '上港集团', market: 'sh' },
  'sh600690': { name: '海尔智家', market: 'sh' },
  'sh600438': { name: '通威股份', market: 'sh' },
  'sh600745': { name: '闻泰科技', market: 'sh' },
  'sh600905': { name: '三峡能源', market: 'sh' },
  'sh601919': { name: '中远海控', market: 'sh' },
  'sh600588': { name: '用友网络', market: 'sh' },
  'sh600089': { name: '特变电工', market: 'sh' },
  'sh601816': { name: '京沪高铁', market: 'sh' },
  'sh601066': { name: '中信建投', market: 'sh' },
  'sh601601': { name: '中国太保', market: 'sh' },
  'sh601336': { name: '新华保险', market: 'sh' },
  'sh600999': { name: '招商证券', market: 'sh' },
  'sh600150': { name: '中国船舶', market: 'sh' },
  'sh601989': { name: '中国重工', market: 'sh' },
  'sh600026': { name: '中远海能', market: 'sh' },
  'sh600009': { name: '上海机场', market: 'sh' },
  'sh600115': { name: '东方航空', market: 'sh' },
  'sh600029': { name: '南方航空', market: 'sh' },
  'sh600111': { name: '北方稀土', market: 'sh' },
  'sh601857': { name: '中国石油', market: 'sh' },
  'sh600028': { name: '中国石化', market: 'sh' },
  'sh600606': { name: '绿地控股', market: 'sh' },
  'sh600383': { name: '金地集团', market: 'sh' },
  'sh600048': { name: '保利发展', market: 'sh' },
  'sh600376': { name: '首开股份', market: 'sh' },
  'sh601155': { name: '新城控股', market: 'sh' },
  
  // === 深市主板 ===
  'sz000001': { name: '平安银行', market: 'sz' },
  'sz000002': { name: '万科A', market: 'sz' },
  'sz000333': { name: '美的集团', market: 'sz' },
  'sz000338': { name: '潍柴动力', market: 'sz' },
  'sz000651': { name: '格力电器', market: 'sz' },
  'sz000858': { name: '五粮液', market: 'sz' },
  'sz000876': { name: '新希望', market: 'sz' },
  'sz000895': { name: '双汇发展', market: 'sz' },
  'sz000002': { name: '平安银行', market: 'sz' },
  'sz002594': { name: '比亚迪', market: 'sz' },
  'sz002415': { name: '海康威视', market: 'sz' },
  'sz002475': { name: '立讯精密', market: 'sz' },
  'sz002230': { name: '科大讯飞', market: 'sz' },
  'sz002352': { name: '顺丰控股', market: 'sz' },
  'sz002236': { name: '大华股份', market: 'sz' },
  'sz002493': { name: '荣盛石化', market: 'sz' },
  'sz002027': { name: '分众传媒', market: 'sz' },
  'sz002460': { name: '赣锋锂业', market: 'sz' },
  'sz002371': { name: '北方华创', market: 'sz' },
  'sz002049': { name: '紫光国微', market: 'sz' },
  'sz300750': { name: '宁德时代', market: 'sz' },
  'sz300059': { name: '东方财富', market: 'sz' },
  'sz300124': { name: '汇川技术', market: 'sz' },
  'sz300122': { name: '智飞生物', market: 'sz' },
  'sz300760': { name: '迈瑞医疗', market: 'sz' },
  'sz300015': { name: '爱尔眼科', market: 'sz' },
  'sz300274': { name: '阳光电源', market: 'sz' },
  'sz300498': { name: '温氏股份', market: 'sz' },
  'sz300142': { name: '沃森生物', market: 'sz' },
  'sz300033': { name: '同花顺', market: 'sz' },
  'sz300059': { name: '东方财富', market: 'sz' },
  'sz300014': { name: '亿纬锂能', market: 'sz' },
  'sz300751': { name: '迈为股份', market: 'sz' },
  'sz300408': { name: '三环集团', market: 'sz' },
  'sz300496': { name: '中科创达', market: 'sz' },
  'sz300662': { name: '科锐国际', market: 'sz' },
  'sz300223': { name: '锐科激光', market: 'sz' },
  'sz300601': { name: '康泰生物', market: 'sz' },
  'sz300347': { name: '泰格医药', market: 'sz' },
  'sz300015': { name: '爱尔眼科', market: 'sz' },
  'sz300003': { name: '乐普医疗', market: 'sz' },
  'sz002466': { name: '天齐锂业', market: 'sz' },
  'sz002304': { name: '洋河股份', market: 'sz' },
  'sz002236': { name: '大华股份', market: 'sz' },
  'sz002563': { name: '森马服饰', market: 'sz' },
  'sz002311': { name: '海大集团', market: 'sz' },
  'sz002601': { name: '龙佰集团', market: 'sz' },
  'sz002601': { name: '德方纳米', market: 'sz' },
  'sz002454': { name: '深南电路', market: 'sz' },
}

/**
 * 清除缓存
 */
export function clearCache() {
  Object.keys(cache).forEach(key => delete cache[key])
}
