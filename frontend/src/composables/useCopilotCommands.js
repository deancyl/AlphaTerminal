/**
 * useCopilotCommands.js
 * Command parsing logic for Copilot sidebar
 */

/**
 * Parse user input into command object
 * @param {string} text - User input text
 * @returns {Object} Command object with type and params
 */
export function parseCommand(text) {
  const t = text.trim()
  
  // 帮助
  if (/^(帮助|help|\?)$/i.test(t)) {
    return { type: 'help' }
  }
  
  // 刷新
  if (/^(刷新|reload|refresh)$/i.test(t)) {
    return { type: 'refresh' }
  }
  
  // 大盘/指数
  if (/^(大盘|指数|市场|整体|a股|a股市场)$/i.test(t)) {
    return { type: 'market' }
  }
  
  // 板块
  if (/^(板块|行业|板块排行)$/i.test(t)) {
    return { type: 'sectors' }
  }
  
  // 北向资金
  if (/^(北向|北向资金|外资|north)$/i.test(t)) {
    return { type: 'northFlow' }
  }
  
  // 涨停
  if (/^(涨停|涨停板|今日涨停)$/i.test(t)) {
    return { type: 'limitUp' }
  }
  
  // 跌停
  if (/^(跌停|跌停板|今日跌停)$/i.test(t)) {
    return { type: 'limitDown' }
  }
  
  // 异动
  if (/^(异动|盘中异动|大幅波动)$/i.test(t)) {
    return { type: 'unusual' }
  }
  
  // 自选
  if (/^(自选|自选股|我的自选|我的股票)$/i.test(t)) {
    return { type: 'watchlist' }
  }
  
  // 分析 [股票]
  const analyzeMatch = t.match(/^(?:分析?|技术分析?|看一?下|诊断)(.+)/)
  if (analyzeMatch) {
    return { type: 'analyze', keyword: analyzeMatch[1].trim() }
  }
  
  // 打开 [股票]
  const openMatch = t.match(/^(?:打开?|查看|显示|找)(.+)/)
  if (openMatch) {
    return { type: 'open', keyword: openMatch[1].trim() }
  }
  
  // 对比 [股票1] [和/和/,] [股票2]
  const compareMatch = t.match(/^(?:对比|比较)(.+)/)
  if (compareMatch) {
    const parts = compareMatch[1].split(/[和与,]/)
    return { type: 'compare', keywords: parts.map(p => p.trim()) }
  }
  
  // 添加自选 [股票]
  const addWatchMatch = t.match(/^(?:添加?自选|加自选|加入自选|自选)(.+)/)
  if (addWatchMatch) {
    return { type: 'addWatch', keyword: addWatchMatch[1].trim() }
  }
  
  // 移除自选 [股票]
  const removeWatchMatch = t.match(/^(?:删除?自选|移除自选|取消自选)(.+)/)
  if (removeWatchMatch) {
    return { type: 'removeWatch', keyword: removeWatchMatch[1].trim() }
  }
  
  // 今日最强/最弱
  if (/^(今日最强|最强板块|涨幅最大)/.test(t)) {
    return { type: 'topSector' }
  }
  
  if (/^(今日最弱|最弱板块|跌幅最大)/.test(t)) {
    return { type: 'bottomSector' }
  }
  
  // 北向净买入/净卖出
  if (/^(北向净买入|北向净买入前)/.test(t)) {
    return { type: 'northFlowTopBuy' }
  }
  
  // 默认：作为股票搜索
  if (/^[\d]{6}$/.test(t) || /^[\u4e00-\u9fa5]{2,}/.test(t)) {
    return { type: 'search', keyword: t }
  }
  
  // 其他：通用对话
  return { type: 'chat', text: t }
}

/**
 * Quick command definitions
 */
export const quickCommands = [
  { text: '大盘', desc: '查看市场概况' },
  { text: '板块', desc: '板块排行' },
  { text: '北向', desc: '北向资金' },
  { text: '涨停', desc: '涨停板' },
  { text: '跌停', desc: '跌停板' },
  { text: '异动', desc: '盘中异动' },
  { text: '自选', desc: '我的自选' },
  { text: '刷新', desc: '刷新缓存' },
]