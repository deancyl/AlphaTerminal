/**
 * CopilotResponse - 响应格式化
 * 
 * 生成格式化的富文本响应
 */

/**
 * 格式化股票列表
 */
export function formatStockList(stocks, title = '股票列表') {
  if (!stocks || stocks.length === 0) {
    return `📋 ${title}\n暂无数据`
  }
  
  const lines = [`📋 【${title}】共 ${stocks.length} 只\n`]
  
  // 表头
  lines.push('代码      名称        价格      涨跌幅')
  lines.push('─'.repeat(45))
  
  // 数据行
  for (const s of stocks.slice(0, 15)) {
    const symbol = (s.symbol || '').padEnd(8)
    const name = (s.name || '').padEnd(10)
    const price = s.price?.toFixed(2)?.padStart(8) || '     N/A'
    const change = formatChangePct(s.change_pct)
    lines.push(`${symbol}${name}${price}  ${change}`)
  }
  
  if (stocks.length > 15) {
    lines.push(`... 还有 ${stocks.length - 15} 只`)
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
  
  for (const s of sectors.slice(0, 10)) {
    const name = (s.name || '').padEnd(12)
    const change = formatChangePct(s.change_pct)
    lines.push(`${name}  ${change}`)
  }
  
  return lines.join('\n')
}

/**
 * 格式化大盘指数
 */
export function formatMarketOverview(overview) {
  if (!overview) return '📊 大盘数据\n暂无数据'
  
  const markets = overview.markets || {}
  const lines = ['📊 【大盘指数】\n']
  
  for (const [key, m] of Object.entries(markets)) {
    if (m.index) {
      const name = (m.name || key).padEnd(10)
      const index = m.index?.toLocaleString()?.padStart(10) || '     N/A'
      const change = formatChangePct(m.change_pct)
      lines.push(`${name}  ${index}  ${change}`)
    }
  }
  
  return lines.join('\n')
}

/**
 * 格式化涨停板
 */
export function formatLimitUp(stocks) {
  if (!stocks || stocks.length === 0) {
    return '🚀 涨停板\n今日无涨停股票'
  }
  
  const lines = [`🚀 【今日涨停】共 ${stocks.length} 只\n`]
  
  for (const s of stocks.slice(0, 10)) {
    const name = (s.name || s.symbol || '').padEnd(8)
    const price = s.price?.toFixed(2) || 'N/A'
    const change = formatChangePct(s.change_pct)
    lines.push(`${name}  ${price.padStart(8)}  ${change}`)
  }
  
  if (stocks.length > 10) {
    lines.push(`\n... 还有 ${stocks.length - 10} 只涨停`)
  }
  
  return lines.join('\n')
}

/**
 * 格式化跌停板
 */
export function formatLimitDown(stocks) {
  if (!stocks || stocks.length === 0) {
    return '💥 跌停板\n今日无跌停股票'
  }
  
  const lines = [`💥 【今日跌停】共 ${stocks.length} 只\n`]
  
  for (const s of stocks.slice(0, 10)) {
    const name = (s.name || s.symbol || '').padEnd(8)
    const price = s.price?.toFixed(2) || 'N/A'
    const change = formatChangePct(s.change_pct)
    lines.push(`${name}  ${price.padStart(8)}  ${change}`)
  }
  
  return lines.join('\n')
}

/**
 * 格式化异动股票
 */
export function formatUnusualStocks(stocks) {
  if (!stocks || stocks.length === 0) {
    return '⚡ 盘中异动\n暂无异动股票'
  }
  
  const lines = [`⚡ 【盘中异动】共 ${stocks.length} 只\n`]
  
  for (const s of stocks.slice(0, 10)) {
    const name = (s.name || s.symbol || '').padEnd(8)
    const change = formatChangePct(s.change_pct)
    const volRatio = s.volume_ratio ? `量×${s.volume_ratio}` : ''
    lines.push(`${name}  ${change}  ${volRatio}`)
  }
  
  return lines.join('\n')
}

/**
 * 格式化分析报告
 */
export function formatAnalysisReport(report) {
  if (!report) return '📈 分析报告\n暂无数据'
  
  const lines = ['📈 【个股分析】\n']
  
  // 基础信息
  const b = report.basic
  lines.push(`股票名称: ${b.name}`)
  lines.push(`股票代码: ${b.symbol}`)
  lines.push(`当前价格: ${b.price}`)
  lines.push(`涨跌幅: ${b.change}`)
  lines.push(`成交量: ${b.volume}`)
  lines.push(`成交额: ${b.amount}`)
  lines.push('')
  
  // 技术分析
  if (report.trend) {
    const t = report.trend
    lines.push('【趋势分析】')
    lines.push(`短期趋势: ${t.direction}`)
    lines.push(`动量: ${t.momentum}`)
    lines.push(`强度: ${t.strength}`)
    lines.push('')
  }
  
  if (report.sr) {
    const sr = report.sr
    lines.push('【支撑压力】')
    lines.push(`支撑位: ${sr.support}`)
    lines.push(`压力位: ${sr.resistance}`)
    lines.push(`振幅: ${sr.range}`)
    lines.push('')
  }
  
  if (report.rsi) {
    const rsi = report.rsi
    lines.push('【RSI 指标】')
    lines.push(`当前值: ${rsi.current.toFixed(1)}`)
    lines.push(`信号: ${rsi.signal === 'overbought' ? '超买 ⚠️' : rsi.signal === 'oversold' ? '超卖 📈' : '中性'}`)
    lines.push('')
  }
  
  // 综合判断
  lines.push('【综合判断】')
  lines.push(report.position || '')
  lines.push('')
  lines.push('【分析摘要】')
  lines.push(report.summary || '')
  
  return lines.join('\n')
}

/**
 * 格式化市场统计
 */
export function formatMarketStats(stats) {
  if (!stats) return ''
  
  const lines = ['📊 【市场概况】\n']
  lines.push(`上涨: ${stats.rising} 只 🔺`)
  lines.push(`下跌: ${stats.falling} 只 🔻`)
  lines.push(`平盘: ${stats.flat} 只`)
  lines.push(`涨停: ${stats.limitUp} 只 🚀`)
  lines.push(`跌停: ${stats.limitDown} 只 💥`)
  lines.push(`平均涨跌: ${stats.avgChange}`)
  lines.push(`市场情绪: ${stats.marketBreadth}`)
  
  return lines.join('\n')
}

/**
 * 格式化大盘对比
 */
export function formatCompareStocks(stocks, title = '对比分析') {
  if (!stocks || stocks.length < 2) {
    return '📊 对比分析\n需要至少2只股票'
  }
  
  const lines = [`📊 【${title}】\n`]
  
  // 表头
  lines.push('代码      名称        价格      涨跌幅')
  lines.push('─'.repeat(50))
  
  for (const s of stocks) {
    const symbol = (s.symbol || '').padEnd(8)
    const name = (s.name || '').padEnd(10)
    const price = s.price?.toFixed(2)?.padStart(8) || '     N/A'
    const change = formatChangePct(s.change_pct)
    lines.push(`${symbol}${name}${price}  ${change}`)
  }
  
  // 对比分析
  lines.push('')
  lines.push('【对比结论】')
  
  const sorted = [...stocks].sort((a, b) => (b.change_pct || 0) - (a.change_pct || 0))
  const best = sorted[0]
  const worst = sorted[sorted.length - 1]
  
  if (best.change_pct > worst.change_pct + 2) {
    lines.push(`相对强弱: ${best.name} 走势最强，${worst.name} 相对较弱`)
  } else {
    lines.push('今日走势较为一致，无明显分化')
  }
  
  return lines.join('\n')
}

/**
 * 格式化北向资金排名
 */
export function formatNorthFlowRanking(data) {
  if (!data) return '🌊 北向资金\n暂无数据'
  
  const lines = ['🌊 【北向资金】\n']
  
  if (data.topBuy?.length > 0) {
    lines.push('净买入 TOP10:')
    for (const s of data.topBuy.slice(0, 5)) {
      const name = (s.name || s.symbol || '').padEnd(8)
      const amount = s.amount ? (s.amount / 100000000).toFixed(2) + '亿' : 'N/A'
      lines.push(`  ${name}  ${amount}`)
    }
  }
  
  return lines.join('\n')
}

/**
 * 格式化最强/最弱板块
 */
export function formatTopSectors(data) {
  if (!data) return '📊 板块数据\n暂无数据'
  
  const lines = ['📊 【板块排行】\n']
  
  if (data.top?.length > 0) {
    lines.push('🔥 涨幅前五:')
    for (const s of data.top) {
      const name = (s.name || '').padEnd(10)
      lines.push(`  ${name}  ${formatChangePct(s.change_pct)}`)
    }
    lines.push('')
  }
  
  if (data.bottom?.length > 0) {
    lines.push('❄️ 跌幅前五:')
    for (const s of data.bottom) {
      const name = (s.name || '').padEnd(10)
      lines.push(`  ${name}  ${formatChangePct(s.change_pct)}`)
    }
  }
  
  return lines.join('\n')
}

// ========== 工具函数 ==========

function formatChangePct(pct) {
  if (pct === undefined || pct === null) return '     N/A '
  const sign = pct >= 0 ? '+' : ''
  const color = pct > 0 ? '🔺' : pct < 0 ? '🔻' : '  '
  return `${color}${sign}${pct.toFixed(2)}% `
}

/**
 * 格式化帮助信息
 */
export function formatHelp() {
  return `🤖 【AlphaTerminal Copilot 使用指南】

📊 快捷命令:
• 大盘 / 指数 - 显示大盘指数
• 板块 - 显示板块涨跌排行
• 北向 / 北向资金 - 显示北向资金

📈 个股分析:
• 分析 [股票名/代码] - 分析个股
• 打开 [股票名/代码] - 打开K线图
• 对比 [股票1] 和 [股票2] - 对比分析

🚀 市场机会:
• 涨停 / 涨停板 - 今日涨停股票
• 跌停 / 跌停板 - 今日跌停股票
• 异动 / 盘中异动 - 异动股票

⭐ 自选管理:
• 自选 / 我的自选 - 查看自选股
• 添加自选 [股票] - 添加到自选
• 移除自选 [股票] - 从自选移除

💡 其他:
• 帮助 - 显示此帮助
• 刷新 - 刷新数据缓存`
}
