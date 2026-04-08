/**
 * CopilotResponse - 响应格式化
 */

/**
 * 格式化大盘指数
 */
export function formatMarketOverview(data) {
  if (!data || !data.indices || data.indices.length === 0) {
    return '📊 【大盘指数】\n暂无数据'
  }
  
  const lines = ['📊 【大盘指数】\n']
  lines.push('─'.repeat(40))
  
  for (const idx of data.indices) {
    const name = (idx.name || idx.symbol).padEnd(10)
    const price = idx.price?.toFixed(2)?.padStart(10) || '     N/A'
    const change = formatChangeStr(idx.change_pct)
    lines.push(`${name}  ${price}  ${change}`)
  }
  
  return lines.join('\n')
}

/**
 * 格式化板块列表
 */
export function formatSectorList(sectors, title = '板块列表') {
  if (!sectors || sectors.length === 0) {
    return `📊 ${title}\n暂无数据`
  }
  
  const lines = [`📊 【${title}】\n`]
  lines.push('─'.repeat(35))
  
  for (const s of sectors.slice(0, 15)) {
    const name = (s.name || s.symbol || '').padEnd(12)
    const change = formatChangeStr(s.change_pct)
    const topStock = s.top_stock ? `→${s.top_stock.name}` : ''
    lines.push(`${name}  ${change}  ${topStock}`)
  }
  
  if (sectors.length > 15) {
    lines.push(`... 还有 ${sectors.length - 15} 个板块`)
  }
  
  return lines.join('\n')
}

/**
 * 格式化涨停板
 */
export function formatLimitUp(stocks) {
  if (!stocks || stocks.length === 0) {
    return '🚀 【今日涨停】\n暂无涨停数据'
  }
  
  const lines = ['🚀 【今日涨停】\n']
  lines.push('─'.repeat(35))
  
  for (const s of stocks.slice(0, 10)) {
    const name = (s.name || s.symbol || '').padEnd(10)
    const price = s.price?.toFixed(2)?.padStart(8) || '     N/A'
    lines.push(`${name}  ${price}  🔴${'10.00%'.padStart(8)}`)
  }
  
  if (stocks.length > 10) {
    lines.push(`... 还有 ${stocks.length - 10} 只涨停`)
  }
  
  lines.push('')
  lines.push('💡 涨停股代表市场最强热点')
  
  return lines.join('\n')
}

/**
 * 格式化跌停板
 */
export function formatLimitDown(stocks) {
  if (!stocks || stocks.length === 0) {
    return '💥 【今日跌停】\n暂无跌停数据'
  }
  
  const lines = ['💥 【今日跌停】\n']
  lines.push('─'.repeat(35))
  
  for (const s of stocks.slice(0, 10)) {
    const name = (s.name || s.symbol || '').padEnd(10)
    const price = s.price?.toFixed(2)?.padStart(8) || '     N/A'
    lines.push(`${name}  ${price}  🟢${'-10.00%'.padStart(8)}`)
  }
  
  if (stocks.length > 10) {
    lines.push(`... 还有 ${stocks.length - 10} 只跌停`)
  }
  
  lines.push('')
  lines.push('⚠️ 跌停股代表市场最弱板块')
  
  return lines.join('\n')
}

/**
 * 格式化异动股票
 */
export function formatUnusualStocks(stocks) {
  if (!stocks || stocks.length === 0) {
    return '⚡ 【盘中异动】\n暂无异动数据'
  }
  
  const lines = ['⚡ 【盘中异动】\n']
  lines.push('─'.repeat(40))
  lines.push('代码      名称         涨跌幅    量比')
  lines.push('─'.repeat(40))
  
  for (const s of stocks.slice(0, 10)) {
    const symbol = (s.symbol || '').replace('sh', '').replace('sz', '').padEnd(8)
    const name = (s.name || '').padEnd(10)
    const change = formatChangeStr(s.change_pct)
    const volRatio = s.volume_ratio ? `×${s.volume_ratio}` : '-'
    lines.push(`${symbol}${name}${change}  ${volRatio}`)
  }
  
  lines.push('')
  lines.push('💡 量比>2表示成交量异常放大')
  
  return lines.join('\n')
}

/**
 * 格式化个股分析报告
 */
export function formatAnalysisReport(report) {
  if (!report) return '📈 【个股分析】\n暂无数据'
  
  const lines = ['📈 【个股分析】\n']
  
  // 基础信息
  const b = report.basic
  lines.push('【基本信息】')
  lines.push(`股票名称: ${b.name}`)
  lines.push(`股票代码: ${b.symbol}`)
  lines.push(`当前价格: ${b.price}`)
  lines.push(`涨跌幅: ${b.change}`)
  lines.push('')
  
  // 趋势分析
  if (report.trend) {
    const t = report.trend
    lines.push('【短期趋势】')
    lines.push(`走势方向: ${t.direction}`)
    lines.push(`上涨力度: ${t.strength}`)
    lines.push(`市场评价: ${t.verdict}`)
    lines.push('')
  }
  
  // 市场情绪
  if (report.market) {
    const m = report.market
    lines.push('【市场情绪】')
    lines.push(`整体氛围: ${m.sentiment}`)
    lines.push(`大盘平均涨跌: ${m.avgChange?.toFixed(2) || 'N/A'}%`)
    lines.push(`市场描述: ${m.description}`)
    lines.push('')
  }
  
  // 投资建议
  if (report.suggestion) {
    lines.push('【投资建议】')
    lines.push(report.suggestion)
    lines.push('')
  }
  
  lines.push('⚠️ 免责声明')
  lines.push('以上分析仅供参考，不构成投资建议。')
  lines.push('投资有风险，入市需谨慎。')
  
  return lines.join('\n')
}

/**
 * 格式化市场情绪
 */
export function formatMarketSentiment(data) {
  if (!data) return '📊 【市场情绪】\n暂无数据'
  
  const lines = ['📊 【市场情绪分析】\n']
  
  const m = data.market || data
  lines.push(`整体氛围: ${m.sentiment || '分析中...'}`)
  lines.push(`综合评分: ${m.score !== undefined ? (m.score > 0 ? '+' : '') + m.score : 'N/A'}`)
  lines.push('')
  
  if (m.avgChange !== undefined) {
    lines.push(`大盘平均涨跌: ${m.avgChange >= 0 ? '+' : ''}${m.avgChange.toFixed(2)}%`)
  }
  
  if (m.description) {
    lines.push(`市场描述: ${m.description}`)
  }
  
  lines.push('')
  
  if (m.score >= 30) {
    lines.push('✅ 操作建议: 适度参与，关注强势板块')
  } else if (m.score <= -30) {
    lines.push('⚠️ 操作建议: 控制仓位，观望为主')
  } else {
    lines.push('➡️ 操作建议: 轻仓观望，等待方向明确')
  }
  
  return lines.join('\n')
}

/**
 * 格式化最强/最弱板块
 */
export function formatTopSectors(data) {
  if (!data) return '📊 【板块排行】\n暂无数据'
  
  const lines = ['📊 【板块排行】\n']
  
  if (data.top && data.top.length > 0) {
    lines.push('🔥 【涨幅前五】')
    lines.push('─'.repeat(30))
    for (const s of data.top.slice(0, 5)) {
      const name = (s.name || '').padEnd(12)
      const change = formatChangeStr(s.change_pct)
      const topStock = s.top_stock ? ` 龙头:${s.top_stock.name}` : ''
      lines.push(`${name}  ${change}${topStock}`)
    }
    lines.push('')
  }
  
  if (data.bottom && data.bottom.length > 0) {
    lines.push('❄️ 【跌幅前五】')
    lines.push('─'.repeat(30))
    for (const s of data.bottom.slice(0, 5)) {
      const name = (s.name || '').padEnd(12)
      const change = formatChangeStr(s.change_pct)
      lines.push(`${name}  ${change}`)
    }
  }
  
  return lines.join('\n')
}

/**
 * 格式化北向资金
 */
export function formatNorthFlowRanking(data) {
  if (!data) return '🌊 【北向资金】\n暂无数据'
  
  const lines = ['🌊 【北向资金】\n']
  
  if (data.topBuy && data.topBuy.length > 0) {
    lines.push('📈 【净买入 TOP5】')
    lines.push('─'.repeat(25))
    for (const s of data.topBuy.slice(0, 5)) {
      const name = (s.name || s.symbol || '').padEnd(10)
      const amount = s.amount ? `${s.amount.toFixed(1)}亿`.padStart(8) : '     N/A'
      lines.push(`${name}  ${amount}`)
    }
    lines.push('')
  }
  
  if (data.topSell && data.topSell.length > 0) {
    lines.push('📉 【净卖出 TOP5】')
    lines.push('─'.repeat(25))
    for (const s of data.topSell.slice(0, 5)) {
      const name = (s.name || s.symbol || '').padEnd(10)
      const amount = s.amount ? `${s.amount.toFixed(1)}亿`.padStart(8) : '     N/A'
      lines.push(`${name}  ${amount}`)
    }
  }
  
  lines.push('')
  lines.push('💡 北向资金代表外资动向')
  lines.push('📈 净买入表示看多，📉 净卖出表示看空')
  
  return lines.join('\n')
}

/**
 * 格式化股票搜索结果
 */
export function formatSearchResults(stocks, keyword) {
  if (!stocks || stocks.length === 0) {
    return `🔍 【搜索「${keyword}」】\n\n未找到相关股票`
  }
  
  const lines = [`🔍 【搜索「${keyword}」结果】共 ${stocks.length} 只\n`]
  lines.push('─'.repeat(30))
  
  for (const s of stocks.slice(0, 10)) {
    const symbol = (s.symbol || '').padEnd(10)
    const name = (s.name || '').padEnd(10)
    const price = s.price ? `¥${s.price.toFixed(2)}` : '获取中'
    lines.push(`${symbol}${name}${price}`)
  }
  
  if (stocks.length > 10) {
    lines.push(`... 还有 ${stocks.length - 10} 只`)
  }
  
  lines.push('')
  lines.push('💡 输入「分析 股票名」获取详细分析')
  lines.push('💡 输入「打开 股票名」查看K线图')
  
  return lines.join('\n')
}

/**
 * 格式化帮助信息
 */
export function formatHelp() {
  return `🤖 【AlphaTerminal Copilot 使用指南】

📊 市场数据:
• 大盘 - 显示主要指数实时数据
• 板块 - 显示板块涨跌排行
• 北向 - 显示北向资金动向

📈 股票分析:
• 分析 股票名/代码 - 获取详细分析报告
  示例: 分析 贵州茅台
        分析 sh600519
• 打开 股票名/代码 - 打开K线图
  示例: 打开 宁德时代
• 对比 股票1 和 股票2 - 对比分析
  示例: 对比 茅台和平安

🚀 市场机会:
• 涨停 - 今日涨停股票一览
• 跌停 - 今日跌停股票一览
• 异动 - 成交量异常放大股票

⭐ 快捷命令:
• 刷新 - 刷新数据缓存
• 帮助 - 显示此帮助

💡 提示:
• 支持股票代码(如600519)或名称(如茅台)
• 所有分析仅供参考，不构成投资建议`
}

// ========== 工具函数 ==========

function formatChangeStr(pct) {
  if (pct === undefined || pct === null) return '     N/A '
  const sign = pct >= 0 ? '+' : ''
  const emoji = pct > 2 ? '🔺' : pct > 0 ? '▲' : pct < -2 ? '🔻' : pct < 0 ? '▼' : '─'
  return `${emoji}${sign}${pct.toFixed(2)}%`.padStart(10)
}
