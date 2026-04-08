/**
 * CopilotDataService - 适配 AlphaTerminal 实际 API
 */

import { apiFetch } from '../utils/api.js'

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
    // 实际返回结构: { wind: {...}, meta: {...} }
    const wind = res?.wind || {}
    const indices = Object.values(wind).filter(v => v && v.index !== undefined && v.market !== 'HK').slice(0, 10)
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
    // 实际返回: { sectors: [...] } 或直接是数组
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
    // 实际返回: { macro: [...] }
    return Array.isArray(res) ? res : (res?.macro || [])
  })
}

/**
 * 获取大盘样本股票（仅10只）
 */
export async function getChinaStocks() {
  return getCached('chinaStocks', async () => {
    const res = await apiFetch(`${API_BASE}/api/v1/market/china_all`, { timeoutMs: 10000 })
    // 实际返回: { china_all: [...] }
    const stocks = Array.isArray(res) ? res : (res?.china_all || [])
    return stocks
  }, 15000) // 15秒缓存
}

// ========== 股票代码数据库 ==========
// AlphaTerminal 没有全市场股票数据，使用主要股票代码作为备选

const STOCK_DB = {
  // 沪深主要指数
  'sh000001': { name: '上证指数', market: 'sh' },
  'sz399001': { name: '深证成指', market: 'sz' },
  'sz399006': { name: '创业板指', market: 'sz' },
  'sh000300': { name: '沪深300', market: 'sh' },
  'sh000016': { name: '上证50', market: 'sh' },
  'sh000688': { name: '科创50', market: 'sh' },
  'sh000905': { name: '中证500', market: 'sh' },
  'sh000852': { name: '中证1000', market: 'sh' },
  
  // 蓝筹股
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
  
  // 深市
  'sz000001': { name: '平安银行', market: 'sz' },
  'sz000002': { name: '万科A', market: 'sz' },
  'sz000333': { name: '美的集团', market: 'sz' },
  'sz000338': { name: '潍柴动力', market: 'sz' },
  'sz000651': { name: '格力电器', market: 'sz' },
  'sz000858': { name: '五粮液', market: 'sz' },
  'sz000876': { name: '新希望', market: 'sz' },
  'sz000895': { name: '双汇发展', market: 'sz' },
  'sz000938': { name: '紫光股份', market: 'sz' },
  'sz000001': { name: '平安银行', market: 'sz' },
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
}

/**
 * 根据代码或名称搜索股票
 */
export async function searchStock(keyword) {
  const k = keyword.trim().toLowerCase()
  
  // 1. 先尝试在 STOCK_DB 中搜索
  const dbResults = []
  for (const [sym, info] of Object.entries(STOCK_DB)) {
    if (sym.includes(k) || info.name.toLowerCase().includes(k)) {
      dbResults.push({
        symbol: sym,
        name: info.name,
        market: info.market,
        price: null,
        change_pct: null,
      })
    }
  }
  
  // 2. 再尝试从 china_all API 搜索
  const stocks = await getChinaStocks()
  if (stocks && stocks.length > 0) {
    for (const s of stocks) {
      if (!dbResults.find(r => r.symbol === s.symbol)) {
        if ((s.symbol || '').toLowerCase().includes(k) || 
            (s.name || '').toLowerCase().includes(k)) {
          dbResults.push({
            symbol: s.symbol,
            name: s.name,
            market: s.market,
            price: s.price,
            change_pct: s.change_pct,
          })
        }
      }
    }
  }
  
  return dbResults.slice(0, 10)
}

/**
 * 获取股票详细信息（需要后端支持实时行情）
 */
export async function getStockQuote(symbol) {
  // 尝试从 market overview 获取指数数据
  if (symbol.startsWith('sh000') || symbol.startsWith('sz399')) {
    const overview = await getMarketOverview()
    const idx = overview?.indices?.find(i => i.symbol === symbol)
    if (idx) return idx
  }
  
  // 从 china_all 获取
  const stocks = await getChinaStocks()
  return stocks.find(s => s.symbol === symbol) || null
}

/**
 * 获取涨停股票
 * 由于没有全市场数据，生成模拟涨停数据
 */
export async function getLimitUpStocks() {
  // 模拟涨停股票（实际需要全市场数据支持）
  const mockLimitUp = [
    { symbol: 'sh601899', name: '紫金矿业', price: 18.88, change_pct: 10.00 },
    { symbol: 'sz300750', name: '宁德时代', price: 215.50, change_pct: 9.99 },
    { symbol: 'sh600519', name: '贵州茅台', price: 1680.00, change_pct: 9.86 },
    { symbol: 'sz000002', name: '万科A', price: 8.92, change_pct: 9.99 },
    { symbol: 'sh601012', name: '隆基绿能', price: 22.15, change_pct: 10.01 },
    { symbol: 'sz002594', name: '比亚迪', price: 268.00, change_pct: 9.95 },
    { symbol: 'sh600036', name: '招商银行', price: 35.20, change_pct: 9.88 },
    { symbol: 'sz300059', name: '东方财富', price: 18.50, change_pct: 10.02 },
    { symbol: 'sh601318', name: '中国平安', price: 48.50, change_pct: 9.92 },
    { symbol: 'sz000333', name: '美的集团', price: 62.80, change_pct: 9.97 },
  ]
  
  // 随机返回3-8只，模拟真实感
  const count = Math.floor(Math.random() * 5) + 3
  return mockLimitUp.slice(0, count)
}

/**
 * 获取跌停股票
 */
export async function getLimitDownStocks() {
  // 模拟跌停股票
  const mockLimitDown = [
    { symbol: 'sh600010', name: '包钢股份', price: 2.15, change_pct: -10.00 },
    { symbol: 'sz300104', name: '乐视退', price: 0.38, change_pct: -9.95 },
    { symbol: 'sh600792', name: '云煤能源', price: 4.28, change_pct: -10.01 },
    { symbol: 'sz300156', name: '神雾环保', price: 0.55, change_pct: -9.84 },
    { symbol: 'sh600212', name: '江泉实业', price: 3.85, change_pct: -10.00 },
  ]
  
  const count = Math.floor(Math.random() * 3) + 2
  return mockLimitDown.slice(0, count)
}

/**
 * 获取异动股票（涨幅或成交量异常）
 */
export async function getUnusualStocks() {
  // 模拟异动股票
  const mockUnusual = [
    { symbol: 'sh601899', name: '紫金矿业', price: 18.88, change_pct: 10.00, volume_ratio: 4.2 },
    { symbol: 'sz300750', name: '宁德时代', price: 215.50, change_pct: 9.99, volume_ratio: 3.8 },
    { symbol: 'sh600519', name: '贵州茅台', price: 1680.00, change_pct: 7.25, volume_ratio: 2.5 },
    { symbol: 'sz002594', name: '比亚迪', price: 268.00, change_pct: 6.50, volume_ratio: 3.2 },
    { symbol: 'sh601012', name: '隆基绿能', price: 22.15, change_pct: 5.80, volume_ratio: 2.8 },
    { symbol: 'sh600036', name: '招商银行', price: 35.20, change_pct: 5.20, volume_ratio: 2.1 },
    { symbol: 'sz300059', name: '东方财富', price: 18.50, change_pct: 4.90, volume_ratio: 3.5 },
    { symbol: 'sh601318', name: '中国平安', price: 48.50, change_pct: 4.50, volume_ratio: 1.8 },
  ]
  
  return mockUnusual
}

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
 * 获取北向资金排名
 */
export async function getNorthFlowRanking() {
  // 模拟北向资金数据
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
  }
  
  return mockData
}

/**
 * 清除缓存
 */
export function clearCache() {
  Object.keys(cache).forEach(key => delete cache[key])
}
