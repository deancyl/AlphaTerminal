import { getCachedResponse, setCachedResponse, cleanCache, useCopilotCacheLifecycle } from './useCopilotCache.js'

let currentController = null

export function useCopilotChat() {
  useCopilotCacheLifecycle()

  return {
    sendToLLM,
    abortCurrentRequest,
    getCurrentAbortController
  }
}

export async function sendToLLM(text, contextOptions, callbacks) {
  const { ctxMarket, ctxRates, ctxNews, ctxPortfolio, ctxHistorical, selectedProvider, selectedModel, portfolioId, currentSymbol } = contextOptions
  const { onStart, onMessage, onComplete, onError, onCached } = callbacks

  cleanCache()
  const cachedResponse = getCachedResponse(text)
  if (onStart) onStart()

  try {
    const contextParts = []
    
    const fetchCtx = async (url, label, formatter) => {
      try {
        const res = await fetch(`${url}?_t=${Date.now()}`)
        if (res.ok) {
          const json = await res.json()
          contextParts.push(formatter(json.data || json))
        }
      } catch (e) { console.debug(`[Copilot] context fetch ${label}:`, e.message) }
    }
    
    if (ctxMarket) await fetchCtx('/api/v1/market/overview', 'market', (data) => {
      const indices = data?.wind?.indices || []
      const lines = indices.slice(0, 8).map(i =>
        `  ${i.name || i.symbol}: ${i.price || i.close} (${i.change_pct >= 0 ? '+' : ''}${i.change_pct?.toFixed(2)}%)`
      ).join('\n')
      return `<context_market>今日大盘数据：\n${lines || '无数据'}\n</context_market>`
    })
    
    if (ctxNews) await fetchCtx('/api/v1/news/flash', 'news', (data) => {
      const news = (data.news || []).slice(0, 5)
      const lines = news.map(n => `  [${n.time}] ${n.title}`).join('\n')
      return `<context_news>最新市场快讯（5条）：\n${lines || '无数据'}\n</context_news>`
    })
    
    if (ctxRates) await fetchCtx('/api/v1/bond/curve', 'bond', (data) => {
      const curve = data.yield_curve || {}
      const lines = Object.entries(curve).map(([k, v]) =>
        `  ${k}: ${(typeof v === 'number' ? v.toFixed(4) : v)}%`
      ).join('\n')
      return `<context_bond>当前国债收益率曲线：\n${lines || '无数据'}\n</context_bond>`
    })
    
    if (ctxPortfolio && portfolioId) {
      try {
        const res = await fetch(`/api/v1/portfolio/${portfolioId}/pnl?_t=${Date.now()}`)
        if (res.ok) {
          const data = await res.json()
          const portfolioData = data.data || data
          const positions = portfolioData.positions || []
          
          if (positions.length > 0) {
            const totalValue = portfolioData.total_value || 0
            const totalPnl = portfolioData.unrealized_pnl || 0
            const positionLines = positions.slice(0, 5).map(p => {
              const arrow = p.unrealized_pnl >= 0 ? '▲' : '▼'
              return `  ${p.symbol} ${p.name || ''}: ${p.shares}股，成本¥${p.avg_cost?.toFixed(2) || 0}，现价¥${p.current_price?.toFixed(2) || 0}，盈亏${arrow}${Math.abs(p.unrealized_pnl_pct || 0).toFixed(2)}%`
            }).join('\n')
            
            contextParts.push(`<context_portfolio>投资组合概况：
  组合名称: ${portfolioData.name || '未命名'}
  总市值: ¥${totalValue.toFixed(2)}
  总盈亏: ${totalPnl >= 0 ? '+' : ''}¥${totalPnl.toFixed(2)} (${((totalPnl / (totalValue - totalPnl)) * 100).toFixed(2)}%)
  持仓明细（前5只）：
${positionLines}
</context_portfolio>`)
          }
        }
      } catch (e) { console.debug('[Copilot] portfolio context fetch failed:', e.message) }
    }
    
    const context = contextParts.join('\n\n')
    
    if (cachedResponse) {
      if (onCached) onCached(cachedResponse)
      return
    }
    
    if (currentController) currentController.abort('New request started')
    currentController = new AbortController()
    
    const response = await fetch('/api/v1/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      body: JSON.stringify({ 
        prompt: text,
        context: context || undefined,
        provider: selectedProvider,
        model: selectedModel || undefined,
        portfolio_id: ctxPortfolio ? portfolioId : undefined,
        include_historical: ctxHistorical,
        hist_symbol: ctxHistorical ? currentSymbol : undefined,
        hist_period: 'daily',
        hist_limit: 60,
      }),
      signal: currentController.signal
    })
    
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let fullContent = ''
    let fullReasoning = ''
    
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      const chunk = decoder.decode(value, { stream: true })
      const lines = chunk.split('\n')
      
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const payload = line.slice(6)
        try {
          const data = JSON.parse(payload)
          if (data.error) throw new Error(data.error)
          
          if (data.reasoning !== undefined) {
            fullReasoning += data.reasoning
            const thinkStart = '\u003Cthink\u003E'
            const thinkEnd = '\u003C/think\u003E'
            const combined = thinkStart + fullReasoning + thinkEnd + '\n' + fullContent
            if (onMessage) onMessage(combined, fullReasoning)
          }
          
          if (data.content !== undefined) {
            fullContent += data.content
            const thinkStart = '\u003Cthink\u003E'
            const thinkEnd = '\u003C/think\u003E'
            const displayText = fullReasoning ? thinkStart + fullReasoning + thinkEnd + '\n' + fullContent : fullContent
            if (onMessage) onMessage(displayText, fullReasoning)
          }
          
          if (data.done) {
            if (fullContent) setCachedResponse(text, fullContent)
            if (onComplete) onComplete(fullContent)
          }
        } catch (e) {
          if (payload && payload.length > 0) {
            console.warn('[Copilot] SSE parse error:', payload.substring(0, 100), e.message)
            if (payload.includes('error') || payload.includes('500') || payload.includes('Error')) {
              if (onError) onError(new Error('后端响应异常: ' + payload.substring(0, 200)))
            }
          }
        }
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') return
    if (onError) onError(err)
  } finally {
    currentController = null
  }
}

export function getCurrentAbortController() {
  return currentController
}

export function abortCurrentRequest() {
  if (currentController) {
    currentController.abort('Request cancelled')
    currentController = null
  }
}