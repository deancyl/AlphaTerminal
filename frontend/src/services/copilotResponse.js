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
  lines.push('─'.repeat(44))
  lines.push('代码       名称          最新点位        涨跌幅')
  lines.push('─'.repeat(44))
  
  for (const idx of data.indices) {
    const code = (idx.symbol || '').padEnd(10)
    const name = (idx.name || '').padEnd(10)
    const price = idx.price?.toFixed(2)?.padStart(12) || '         N/A'
    const change = formatChangeStr(idx.change_pct)
    lines.push(`${code}${name}${price}  ${change}`)
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
  lines.push('─'.repeat(40))
  
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
export function formatLimitUp(stocks, summary = null) {
  if (!stocks || stocks.length === 0) {
    return '🚀 【今日涨停】\n暂无涨停数据（可能已休市）'
  }
  
  const lines = ['🚀 【今日涨停】\n']
  
  // 市场情绪
  if (summary?.market_sentiment) {
    lines.push(`市场情绪: ${summary.market_sentiment}`)
    lines.push('')
  }
  
  lines.push(`共 ${stocks.length} 只涨停\n`)
  lines.push('─'.repeat(45))
  lines.push('代码       名称            涨停时间    换手率')
  lines.push('─'.repeat(45))
  
  for (const s of stocks.slice(0, 12)) {
    const code = (s.code || s.symbol?.replace('sh','').replace('sz','') || '').padEnd(10)
    const name = (s.name || '').padEnd(12)
    const sealTime = s.first_seal_time ? s.first_seal_time.slice(0,5) : '-'
    const turnover = s.turnover_rate?.toFixed(1) + '%' || '-'
    lines.push(`${code}${name}${sealTime.padStart(10)}  ${turnover.padStart(6)}`)
  }
  
  if (stocks.length > 12) {
    lines.push(`... 还有 ${stocks.length - 12} 只涨停`)
  }
  
  // 涨停原因
  if (stocks[0]?.industry) {
    lines.push('')
    lines.push(`💡 今日涨停涉及: ${[...new Set(stocks.slice(0, 8).map(s => s.industry))].join('、')}`)
  }
  
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
  lines.push(`共 ${stocks.length} 只跌停\n`)
  lines.push('─'.repeat(40))
  
  for (const s of stocks.slice(0, 10)) {
    const code = (s.code || s.symbol?.replace('sh','').replace('sz','') || '').padEnd(10)
    const name = (s.name || '').padEnd(10)
    const industry = s.industry || '-'
    lines.push(`${code}${name}  ${industry}`)
  }
  
  if (stocks.length > 10) {
    lines.push(`... 还有 ${stocks.length - 10} 只跌停`)
  }
  
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
  lines.push(`共 ${stocks.length} 只异动\n`)
  lines.push('─'.repeat(45))
  lines.push('代码       名称           涨跌幅     换手率    量比')
  lines.push('─'.repeat(45))
  
  for (const s of stocks.slice(0, 12)) {
    const code = (s.code || s.symbol?.replace('sh','').replace('sz','') || '').padEnd(10)
    const name = (s.name || '').padEnd(12)
    const change = formatChangeStr(s.change_pct)
    const turnover = s.turnover_rate ? s.turnover_rate.toFixed(1) + '%' : '-'
    const volRatio = s.volume_ratio || '-'
    lines.push(`${code}${name}${change}  ${turnover.padStart(6)}  ×${volRatio}`)
  }
  
  if (stocks.length > 12) {
    lines.push(`... 还有 ${stocks.length - 12} 只`)
  }
  
  lines.push('')
  lines.push('💡 换手率>5%或涨停股为异动热点')
  
  return lines.join('\n')
}

/**
 * 格式化个股分析报告
 */
export function formatAnalysisReport(report) {
  if (!report) return '📈 【个股分析】\n暂无数据'
  
  const lines = ['📈 【个股分析报告】\n']
  
  // 基础信息
  const b = report.basic || {}
  if (b.name) lines.push(`📌 ${b.name}`)
  if (b.symbol) lines.push(`代码: ${b.symbol}`)
  lines.push('')
  
  // 实时行情
  if (report.quote && report.quote.price) {
    const q = report.quote
    lines.push('【实时行情】')
    lines.push(`最新价: ¥${q.price?.toFixed(2) || 'N/A'}`)
    lines.push(`涨跌额: ${(q.change_pct >= 0 ? '+' : '') + (q.change_pct?.toFixed(2) || 'N/A')}%`)
    if (q.open) lines.push(`今开: ¥${q.open.toFixed(2)}`)
    if (q.high) lines.push(`最高: ¥${q.high.toFixed(2)}`)
    if (q.low) lines.push(`最低: ¥${q.low.toFixed(2)}`)
    if (q.volume) lines.push(`成交量: ${formatVolume(q.volume)}`)
    if (q.amount) lines.push(`成交额: ${formatAmount(q.amount)}`)
    lines.push('')
  }
  
  // 趋势分析
  if (report.trend) {
    const t = report.trend
    lines.push('【技术分析】')
    lines.push(`走势方向: ${t.direction}`)
    lines.push(`上涨力度: ${t.strength}`)
    lines.push(`市场评价: ${t.verdict}`)
    lines.push('')
  }
  
  // 市场情绪
  if (report.market) {
    const m = report.market
    lines.push('【市场背景】')
    lines.push(`整体氛围: ${m.sentiment || '分析中...'}`)
    lines.push(`大盘平均涨跌: ${m.avgChange?.toFixed(2) || 'N/A'}%`)
    lines.push('')
  }
  
  // 投资建议
  if (report.suggestion) {
    lines.push('【综合建议】')
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
  if (!data) return ''
  
  const lines = ['📊 【市场情绪分析】\n']
  
  const m = data.market || data
  const score = m.score ?? 0
  const avgChange = m.avgChange ?? 0
  
  // 情绪指示器
  const indicator = score >= 60 ? '🔥' : score >= 30 ? '📈' : score >= 0 ? '➡️' : score >= -30 ? '➡️' : '📉'
  
  lines.push(`整体氛围: ${indicator} ${m.sentiment || '分析中...'}`)
  lines.push(`综合评分: ${score > 0 ? '+' : ''}${score} 分`)
  lines.push(`大盘平均涨跌: ${avgChange >= 0 ? '+' : ''}${avgChange.toFixed(2)}%`)
  
  if (m.description) {
    lines.push(`市场描述: ${m.description}`)
  }
  
  lines.push('')
  
  // 操作建议
  if (score >= 30) {
    lines.push('✅ 操作建议: 适度参与，关注强势板块')
  } else if (score <= -30) {
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
  
  const lines = ['📊 【板块涨跌排行】\n']
  
  if (data.top && data.top.length > 0) {
    lines.push('🔥 【涨幅前五】')
    lines.push('─'.repeat(38))
    for (const s of data.top.slice(0, 5)) {
      const name = (s.name || '').padEnd(14)
      const change = formatChangeStr(s.change_pct)
      const leader = s.top_stock?.name ? ` ↑${s.top_stock.name}` : ''
      lines.push(`${name}  ${change}${leader}`)
    }
    lines.push('')
  }
  
  if (data.bottom && data.bottom.length > 0) {
    lines.push('❄️ 【跌幅前五】')
    lines.push('─'.repeat(38))
    for (const s of data.bottom.slice(0, 5)) {
      const name = (s.name || '').padEnd(14)
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
  
  if (data.note) {
    lines.push(data.note)
    lines.push('')
  }
  
  if (data.topBuy && data.topBuy.length > 0) {
    lines.push('📈 【净买入 TOP5】')
    lines.push('─'.repeat(28))
    for (const s of data.topBuy.slice(0, 5)) {
      const name = (s.name || s.symbol || '').padEnd(10)
      const amount = `${s.amount >= 0 ? '+' : ''}${s.amount.toFixed(1)}亿`.padStart(10)
      lines.push(`${name}  ${amount}`)
    }
    lines.push('')
  }
  
  if (data.topSell && data.topSell.length > 0) {
    lines.push('📉 【净卖出 TOP5】')
    lines.push('─'.repeat(28))
    for (const s of data.topSell.slice(0, 5)) {
      const name = (s.name || s.symbol || '').padEnd(10)
      const amount = `${s.amount.toFixed(1)}亿`.padStart(10)
      lines.push(`${name}  ${amount}`)
    }
  }
  
  return lines.join('\n')
}

/**
 * 格式化股票搜索结果
 */
export function formatSearchResults(stocks, keyword) {
  if (!stocks || stocks.length === 0) {
    return `🔍 【搜索「${keyword}」】\n\n未找到相关股票，请尝试其他关键词`
  }
  
  const lines = [`🔍 【搜索「${keyword}」结果】\n`]
  lines.push(`共找到 ${stocks.length} 只股票\n`)
  lines.push('─'.repeat(35))
  
  for (const s of stocks.slice(0, 12)) {
    const symbol = (s.symbol || '').padEnd(10)
    const name = (s.name || '').padEnd(10)
    const price = s.price ? `¥${s.price.toFixed(2)}` : ''
    lines.push(`${symbol}${name}${price}`)
  }
  
  if (stocks.length > 12) {
    lines.push(`... 还有 ${stocks.length - 12} 只`)
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

📊 市场数据 (真实数据源):
• 大盘 - 显示主要指数实时数据 ← 真实
• 板块 - 显示板块涨跌排行 ← 真实
• 涨停 - 今日涨停股票一览 ← 真实(akshare)
• 跌停 - 今日跌停股票一览 ← 真实(akshare)
• 异动 - 成交量异常放大股票 ← 真实(akshare)

📈 股票分析:
• 分析 股票名/代码 - 获取详细分析报告
  示例: 分析 贵州茅台 / 分析 600519
• 打开 股票名/代码 - 打开K线图
  示例: 打开 宁德时代 / 打开 300750
• 对比 股票1 和 股票2 - 对比分析
  示例: 对比 茅台 和 平安

💡 其他:
• 刷新 - 强制刷新数据缓存
• 帮助 - 显示此帮助

⚠️ 注意: 北向资金数据仅供参考，实际需接入港交所接口`
}

// ========== 工具函数 ==========

function formatChangeStr(pct) {
  if (pct === undefined || pct === null) return '     N/A '
  const sign = pct >= 0 ? '+' : ''
  const arrow = pct > 2 ? '🔺' : pct > 0 ? '▲' : pct < -2 ? '🔻' : pct < 0 ? '▼' : '─'
  return `${arrow}${sign}${pct.toFixed(2)}%`.padStart(10)
}

function formatVolume(vol) {
  if (!vol) return 'N/A'
  if (vol >= 100000000) return (vol / 100000000).toFixed(2) + '亿股'
  if (vol >= 10000) return (vol / 10000).toFixed(0) + '万股'
  return vol.toFixed(0) + '股'
}

function formatAmount(amount) {
  if (!amount) return 'N/A'
  if (amount >= 100000000) return (amount / 100000000).toFixed(2) + '亿'
  if (amount >= 10000) return (amount / 10000).toFixed(0) + '万'
  return amount.toFixed(0)
}
