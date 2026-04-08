<template>
  <div class="flex flex-col h-full">

    <!-- 标题区 -->
    <div class="p-4 border-b border-gray-800 shrink-0">
      <h2 class="text-terminal-accent font-bold text-base flex items-center gap-2">
        🧠 AlphaTerminal Copilot
      </h2>
      <p class="text-terminal-dim text-xs mt-0.5">智能投研助手 · 输入命令快速执行</p>
    </div>

    <!-- 快捷命令按钮 -->
    <div class="px-4 py-2 border-b border-gray-800">
      <div class="text-[10px] text-terminal-dim mb-2">💡 快捷命令</div>
      <div class="flex flex-wrap gap-1.5">
        <button
          v-for="cmd in quickCommands"
          :key="cmd.cmd"
          class="px-2 py-1 text-[10px] rounded bg-terminal-bg border border-gray-700
                 text-terminal-dim hover:border-terminal-accent/50 hover:text-terminal-accent
                 transition-colors whitespace-nowrap"
          @click="executeQuickCommand(cmd)"
        >
          {{ cmd.icon }} {{ cmd.label }}
        </button>
      </div>
    </div>

    <!-- 上下文勾选框 -->
    <div class="px-4 py-2 border-b border-gray-800 flex flex-wrap gap-3 text-xs shrink-0">
      <label class="flex items-center gap-1.5 cursor-pointer select-none">
        <input type="checkbox" v-model="ctxMarket" class="accent-terminal-accent w-3.5 h-3.5 rounded">
        <span :class="ctxMarket ? 'text-terminal-accent' : 'text-terminal-dim'">📊 大盘指数</span>
      </label>
      <label class="flex items-center gap-1.5 cursor-pointer select-none">
        <input type="checkbox" v-model="ctxRates" class="accent-terminal-accent w-3.5 h-3.5 rounded">
        <span :class="ctxRates ? 'text-terminal-accent' : 'text-terminal-dim'">💰 利率数据</span>
      </label>
      <label class="flex items-center gap-1.5 cursor-pointer select-none">
        <input type="checkbox" v-model="ctxNews" class="accent-terminal-accent w-3.5 h-3.5 rounded">
        <span :class="ctxNews ? 'text-terminal-accent' : 'text-terminal-dim'">📰 快讯摘要</span>
      </label>
    </div>

    <!-- 对话历史 -->
    <div ref="historyEl" class="flex-1 overflow-y-auto p-4 space-y-4">
      <div v-if="messages.length === 0" class="text-center mt-12">
        <div class="text-4xl mb-3">💬</div>
        <p class="text-terminal-dim text-sm">开始一场投研对话</p>
        <div class="mt-4 text-xs text-terminal-dim/70 space-y-1">
          <p>💡 试试说：「分析上证指数」</p>
          <p>💡 或点击上面的快捷命令</p>
        </div>
      </div>

      <!-- 命令执行结果卡片 -->
      <div v-if="lastCommandResult" class="rounded-lg p-3 bg-terminal-accent/10 border border-terminal-accent/30 mr-4">
        <div class="text-[10px] mb-2 text-terminal-accent">⚡ 命令执行结果</div>
        <div class="text-gray-200 text-sm whitespace-pre-wrap">{{ lastCommandResult }}</div>
      </div>

      <div v-for="(msg, i) in messages" :key="i"
           class="rounded-lg p-3 text-sm whitespace-pre-wrap"
           :class="msg.role === 'user'
             ? 'bg-terminal-accent/10 border border-terminal-accent/30 text-gray-100 ml-8'
             : 'bg-terminal-bg border border-gray-700 mr-4'">
        <div class="text-[10px] mb-1"
             :class="msg.role === 'user' ? 'text-terminal-accent' : 'text-terminal-dim'">
          {{ msg.role === 'user' ? '你' : '🤖 AlphaTerminal' }}
        </div>
        <!-- 用户消息 -->
        <div v-if="msg.role === 'user'" class="text-gray-100">{{ msg.content }}</div>
        <!-- AI 消息：打字机效果 -->
        <div v-else class="text-gray-200">
          <span>{{ msg.displayedContent }}</span>
          <span v-if="msg.streaming" class="animate-pulse text-terminal-accent">▌</span>
        </div>
      </div>

      <!-- 加载指示器 -->
      <div v-if="isLoading && messages[messages.length - 1]?.streaming"
           class="bg-terminal-bg border border-gray-700 rounded-lg p-3 mr-4">
        <div class="text-terminal-dim text-xs flex items-center gap-2">
          <span class="inline-block w-2 h-2 rounded-full bg-terminal-accent animate-ping"></span>
          AI 正在思考...
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="p-4 border-t border-gray-800 shrink-0">
      <div class="relative">
        <textarea
          ref="inputEl"
          v-model="inputText"
          class="w-full bg-terminal-bg border border-gray-700 rounded-lg px-3 py-2.5 pr-12
                 text-sm text-gray-100 resize-none
                 focus:outline-none focus:border-terminal-accent/60
                 placeholder:text-terminal-dim/50"
          rows="3"
          placeholder="输入命令或问题... (Shift+Enter 换行)"
          :disabled="isLoading"
          @keydown.enter.exact.prevent="sendMessage"
        ></textarea>
        <button
          class="absolute right-2 bottom-2 w-8 h-8 rounded flex items-center justify-center
                 transition-colors"
          :class="isLoading || !inputText.trim()
            ? 'bg-terminal-bg text-terminal-dim/30 cursor-not-allowed'
            : 'bg-terminal-accent/20 text-terminal-accent hover:bg-terminal-accent/30'"
          :disabled="isLoading || !inputText.trim()"
          @click="sendMessage"
        >
          <svg v-if="!isLoading" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z"/>
          </svg>
          <span v-else class="w-4 h-4 border-2 border-terminal-accent/40 border-t-terminal-accent rounded-full animate-spin"></span>
        </button>
      </div>
      <div class="flex justify-between mt-1.5 text-[10px] text-terminal-dim/50">
        <span>Enter 发送 · Shift+Enter 换行</span>
        <span>{{ messages.length }} 条对话</span>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, nextTick, computed } from 'vue'

const messages       = ref([])
const inputText      = ref('')
const isLoading      = ref(false)
const historyEl      = ref(null)
const inputEl        = ref(null)
const lastCommandResult = ref('')

// 上下文勾选
const ctxMarket = ref(true)
const ctxRates  = ref(true)
const ctxNews   = ref(false)

// 快捷命令列表
const quickCommands = [
  { cmd: '大盘', label: '大盘', icon: '📊', action: 'showMarket' },
  { cmd: '北向', label: '北向资金', icon: '🌊', action: 'showNorthFlow' },
  { cmd: '涨停', label: '涨停板', icon: '🚀', action: 'showLimitUp' },
  { cmd: '跌停', label: '跌停板', icon: '💥', action: 'showLimitDown' },
  { cmd: '异动', label: '盘中异动', icon: '⚡', action: 'showUnusual' },
  { cmd: '自选', label: '我的自选', icon: '⭐', action: 'showWatchlist' },
]

// 接收父组件传入的市场数据
const props = defineProps({
  marketOverview: { type: Object, default: null },
  ratesData:      { type: Array,  default: () => [] },
  newsData:       { type: Array,  default: () => [] },
  watchList:      { type: Array,  default: () => [] },
})

// 事件发射
const emit = defineEmits([
  'open-chart',      // 打开图表 { symbol, name }
  'show-sector',     // 显示板块
  'show-north-flow', // 北向资金
  'show-limit-up',   // 涨停板
  'show-limit-down', // 跌停板
  'show-unusual',    // 盘中异动
  'show-watchlist',  // 自选股
])

// 提取股票代码/名称的正则
const STOCK_PATTERN = /(?:(\d{6})|([\u4e00-\u9fa5]{2,8}(?:[A-Za-z]?股票?|股份)?))/

function scrollToBottom() {
  nextTick(() => {
    if (historyEl.value) {
      historyEl.value.scrollTop = historyEl.value.scrollHeight
    }
  })
}

// 执行快捷命令
function executeQuickCommand(cmd) {
  const action = cmd.action
  let result = ''

  switch (action) {
    case 'showMarket':
      result = buildMarketSummary()
      break
    case 'showNorthFlow':
      result = '🌊 正在加载北向资金数据...'
      emit('show-north-flow')
      break
    case 'showLimitUp':
      result = '🚀 正在加载涨停板数据...'
      emit('show-limit-up')
      break
    case 'showLimitDown':
      result = '💥 正在加载跌停板数据...'
      emit('show-limit-down')
      break
    case 'showUnusual':
      result = '⚡ 正在加载盘中异动数据...'
      emit('show-unusual')
      break
    case 'showWatchlist':
      result = buildWatchlistSummary()
      break
    default:
      result = '未知命令'
  }

  if (result && !['showNorthFlow', 'showLimitUp', 'showLimitDown', 'showUnusual'].includes(action)) {
    lastCommandResult.value = result
    messages.value.push({
      role: 'assistant',
      content: result,
      displayedContent: result,
      streaming: false,
    })
    scrollToBottom()
  }
}

// 构建大盘总结
function buildMarketSummary() {
  const m = props.marketOverview?.markets || {}
  const lines = Object.values(m)
    .filter(v => v.index)
    .map(v => {
      const pct = v.change_pct || 0
      const sign = pct >= 0 ? '🔴' : '🟢'
      return `${v.name}: ${v.index?.toLocaleString()} ${sign}${Math.abs(pct).toFixed(2)}%`
    })
  
  if (lines.length === 0) {
    return '📊 暂无大盘数据'
  }
  
  return `📊 【大盘指数】\n${lines.join('\n')}`
}

// 构建自选股总结
function buildWatchlistSummary() {
  const list = props.watchList || []
  if (list.length === 0) {
    return '⭐ 暂无自选股'
  }
  
  const lines = list.slice(0, 10).map(s => {
    const pct = s.change_pct || 0
    const sign = pct >= 0 ? '🔴' : '🟢'
    return `${s.name || s.symbol}: ${sign}${Math.abs(pct).toFixed(2)}%`
  })
  
  return `⭐ 【我的自选】(${list.length}只)\n${lines.join('\n')}`
}

// 解析命令
function parseCommand(text) {
  const t = text.trim()
  
  // 1. 分析命令
  const analyzeMatch = t.match(/^(?:分析?|看|查|看一?下)(.+)/)
  if (analyzeMatch) {
    const target = analyzeMatch[1].trim()
    return { type: 'analyze', target }
  }
  
  // 2. 打开/查看命令
  const openMatch = t.match(/^(?:打开?|看|显示|查看)(.+)/)
  if (openMatch) {
    const target = openMatch[1].trim()
    return { type: 'open', target }
  }
  
  // 3. 添加自选命令
  const addWatchMatch = t.match(/^(?:添加?自选|加自选|加入自选)(.+)/)
  if (addWatchMatch) {
    const target = addWatchMatch[1].trim()
    return { type: 'addWatch', target }
  }
  
  // 4. 对比命令
  const compareMatch = t.match(/^(?:对比|比较)(.+)/)
  if (compareMatch) {
    const targets = compareMatch[1].split(/[和与,]/)
    return { type: 'compare', targets: targets.map(t => t.trim()) }
  }
  
  // 5. 移除自选命令
  const removeWatchMatch = t.match(/^(?:删除?自选|移除自选)(.+)/)
  if (removeWatchMatch) {
    const target = removeWatchMatch[1].trim()
    return { type: 'removeWatch', target }
  }
  
  // 6. 北向资金
  if (/北向|北向资金|外资/.test(t)) {
    return { type: 'northFlow' }
  }
  
  // 7. 涨停板
  if (/涨停|涨停板|今日涨停/.test(t)) {
    return { type: 'limitUp' }
  }
  
  // 8. 跌停板
  if (/跌停|跌停板/.test(t)) {
    return { type: 'limitDown' }
  }
  
  // 9. 异动
  if (/异动|盘中异动|大幅波动/.test(t)) {
    return { type: 'unusual' }
  }
  
  // 10. 大盘/指数
  if (/大盘|指数|市场|整体/.test(t)) {
    return { type: 'market' }
  }
  
  // 11. 自选股
  if (/自选|自选股|我的股票/.test(t)) {
    return { type: 'watchlist' }
  }
  
  // 默认：通用对话
  return { type: 'chat', text: t }
}

// 执行命令
function executeCommand(cmd) {
  switch (cmd.type) {
    case 'analyze':
      return executeAnalyze(cmd.target)
    case 'open':
      return executeOpen(cmd.target)
    case 'addWatch':
      return executeAddWatch(cmd.target)
    case 'removeWatch':
      return executeRemoveWatch(cmd.target)
    case 'compare':
      return executeCompare(cmd.targets)
    case 'northFlow':
      emit('show-north-flow')
      return '🌊 正在加载北向资金数据...'
    case 'limitUp':
      emit('show-limit-up')
      return '🚀 正在加载涨停板数据...'
    case 'limitDown':
      emit('show-limit-down')
      return '💥 正在加载跌停板数据...'
    case 'unusual':
      emit('show-unusual')
      return '⚡ 正在加载盘中异动数据...'
    case 'market':
      return buildMarketSummary()
    case 'watchlist':
      return buildWatchlistSummary()
    default:
      return null // 交给 LLM 处理
  }
}

// 分析命令
function executeAnalyze(target) {
  // 尝试提取股票代码
  const stockMatch = target.match(/(\d{6})|([\u4e00-\u9fa5]+)/)
  if (stockMatch) {
    const symbol = stockMatch[1] || stockMatch[2]
    // 这里可以调用分析 API
    return `📈 【${target} 分析】\n\n正在获取${target}的技术分析数据...\n\n请稍候，或直接说「打开 ${target}」查看详细图表。`
  }
  return `📈 正在分析「${target}」...\n\n请稍候。`
}

// 打开图表命令
function executeOpen(target) {
  const stockMatch = target.match(/(\d{6})|([\u4e00-\u9fa5]+)/)
  if (stockMatch) {
    const symbol = stockMatch[1] || stockMatch[2]
    emit('open-chart', { symbol, name: target })
    return `📊 正在打开「${target}」的K线图...`
  }
  return `❓ 无法识别股票「${target}」，请输入股票代码或名称。`
}

// 添加自选命令
function executeAddWatch(target) {
  const stockMatch = target.match(/(\d{6})|([\u4e00-\u9fa5]+)/)
  if (stockMatch) {
    const symbol = stockMatch[1] || stockMatch[2]
    emit('open-chart', { symbol, name: target, addToWatch: true })
    return `⭐ 正在添加「${target}」到自选股...`
  }
  return `❓ 无法识别股票「${target}」，请输入股票代码或名称。`
}

// 移除自选命令
function executeRemoveWatch(target) {
  return `🗑️ 正在从自选股中移除「${target}」...`
}

// 对比命令
function executeCompare(targets) {
  if (targets.length < 2) {
    return '❓ 对比需要至少两只股票，例如：「对比 平安 茅台」'
  }
  const symbols = targets.map(t => {
    const m = t.match(/(\d{6})|([\u4e00-\u9fa5]+)/)
    return m ? (m[1] || m[2]) : t
  })
  emit('open-chart', { symbols, mode: 'compare' })
  return `📊 正在打开对比视图：${targets.join(' vs ')}...`
}

function buildContext() {
  const parts = []
  if (ctxMarket.value && props.marketOverview) {
    const m = props.marketOverview.markets || {}
    const idxLines = Object.values(m)
      .filter(v => v.index)
      .map(v => `${v.name} 最新点位 ${v.index?.toLocaleString()}（${(v.change_pct >= 0 ? '+' : '') + (v.change_pct || 0).toFixed(2)}%）`)
    if (idxLines.length) parts.push(`【大盘指数】\n${idxLines.join('\n')}`)
  }
  if (ctxRates.value && props.ratesData?.length) {
    const rateLines = props.ratesData
      .slice(0, 6)
      .map(r => `${r.name} = ${r.rate}%`)
    parts.push(`【利率数据】\n${rateLines.join('\n')}`)
  }
  if (ctxNews.value && props.newsData?.length) {
    const newsLines = props.newsData
      .slice(0, 3)
      .map(n => `[${n.tag}] ${n.title}`)
    parts.push(`【最新快讯】\n${newsLines.join('\n')}`)
  }
  return parts.length ? `\n\n=== 参考上下文 ===\n${parts.join('\n\n')}\n=== 以上为参考信息，请基于此作答 ===\n` : ''
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || isLoading.value) return

  // 解析命令
  const cmd = parseCommand(text)

  // 先尝试执行命令
  const cmdResult = executeCommand(cmd)
  if (cmdResult) {
    // 添加用户消息
    messages.value.push({ role: 'user', content: text, displayedContent: text, streaming: false })
    inputText.value = ''

    // 添加命令结果
    messages.value.push({
      role: 'assistant',
      content: cmdResult,
      displayedContent: cmdResult,
      streaming: false,
    })

    scrollToBottom()
    return
  }

  // 如果不是命令，发送给 LLM
  messages.value.push({ role: 'user', content: text, displayedContent: text, streaming: false })
  inputText.value = ''
  isLoading.value = true
  scrollToBottom()

  // 添加占位 AI 消息
  const aiMsgIndex = messages.value.length
  messages.value.push({ role: 'assistant', content: '', displayedContent: '', streaming: true })

  const context = buildContext()
  const payload = { prompt: text }
  if (context) payload.context = context

  try {
    const response = await fetch('/api/v1/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      body: JSON.stringify(payload),
    })

    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let fullContent = ''

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
          if (data.content !== undefined) {
            fullContent += data.content
            messages.value[aiMsgIndex].displayedContent = fullContent
            messages.value[aiMsgIndex].content = fullContent
            scrollToBottom()
          }
          if (data.done) {
            messages.value[aiMsgIndex].streaming = false
          }
        } catch {}
      }
    }
  } catch (err) {
    messages.value[aiMsgIndex].displayedContent = `❌ 请求失败: ${err.message}`
    messages.value[aiMsgIndex].streaming = false
  } finally {
    isLoading.value = false
    scrollToBottom()
    inputEl.value?.focus()
  }
}
</script>
