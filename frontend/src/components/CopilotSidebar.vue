<template>
  <div class="flex flex-col h-full">

    <!-- 标题区 -->
    <div class="p-4 border-b border-gray-800 shrink-0">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-terminal-accent font-bold text-base flex items-center gap-2">
            🧠 AlphaTerminal Copilot
          </h2>
          <p class="text-terminal-dim text-xs mt-0.5">智能投研助手 · 数据驱动分析</p>
        </div>
        <!-- 模式切换按钮 -->
        <button
          class="flex items-center gap-1.5 px-2 py-1 rounded text-[10px] border transition"
          :class="llmMode === 'webllm'
            ? 'border-green-500/50 bg-green-500/10 text-green-400'
            : 'border-purple-500/50 bg-purple-500/10 text-purple-400'"
          @click="toggleLlmMode"
          :disabled="isWebllmLoading"
        >
          <span v-if="isWebllmLoading" class="w-3 h-3 border border-green-400/50 border-t-green-400 rounded-full animate-spin"></span>
          <span v-else>{{ llmMode === 'webllm' ? '🌐 WebLLM' : '🤖 云端' }}</span>
        </button>
      </div>
      <!-- WebLLM 状态提示 -->
      <div v-if="llmMode === 'webllm'" class="mt-2 text-[10px]">
        <span v-if="webllmReady" class="text-green-400">✓ 模型已加载</span>
        <span v-else-if="isWebllmLoading" class="text-yellow-400">⏳ 加载中...</span>
        <span v-else class="text-red-400">✗ 点击切换到 WebLLM 模式</span>
      </div>
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
          :disabled="isLoading"
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
        <span :class="ctxMarket ? 'text-terminal-accent' : 'text-terminal-dim'">📊 大盘</span>
      </label>
      <label class="flex items-center gap-1.5 cursor-pointer select-none">
        <input type="checkbox" v-model="ctxRates" class="accent-terminal-accent w-3.5 h-3.5 rounded">
        <span :class="ctxRates ? 'text-terminal-accent' : 'text-terminal-dim'">💰 利率</span>
      </label>
      <label class="flex items-center gap-1.5 cursor-pointer select-none">
        <input type="checkbox" v-model="ctxNews" class="accent-terminal-accent w-3.5 h-3.5 rounded">
        <span :class="ctxNews ? 'text-terminal-accent' : 'text-terminal-dim'">📰 快讯</span>
      </label>
    </div>

    <!-- 对话历史 -->
    <div ref="historyEl" class="flex-1 overflow-y-auto p-4 space-y-3">
      <div v-if="messages.length === 0" class="text-center mt-12">
        <div class="text-4xl mb-3">💬</div>
        <p class="text-terminal-dim text-sm">开始一场投研对话</p>
        <div class="mt-4 text-xs text-terminal-dim/70 space-y-1">
          <p>💡 试试：「分析上证指数」</p>
          <p>💡 或：「今日涨停有哪些」</p>
          <p>💡 或：「打开贵州茅台」</p>
        </div>
      </div>

      <div v-for="(msg, i) in messages" :key="i"
           class="rounded-lg p-3 text-sm whitespace-pre-wrap leading-relaxed"
           :class="msg.role === 'user'
             ? 'bg-terminal-accent/10 border border-terminal-accent/30 text-gray-100 ml-8'
             : msg.isError
               ? 'bg-red-500/10 border border-red-500/30 text-red-300 mr-4'
               : 'bg-terminal-bg border border-gray-700 mr-4'">
        <div class="text-[10px] mb-1.5"
             :class="msg.role === 'user' ? 'text-terminal-accent' : 'text-terminal-dim'">
          {{ msg.role === 'user' ? '你' : '🤖 AlphaTerminal' }}
        </div>
        <!-- 用户消息 -->
        <div v-if="msg.role === 'user'" class="text-gray-100">{{ msg.content }}</div>
        <!-- AI 消息 -->
        <div v-else class="text-gray-200">
          <span>{{ msg.displayedContent }}</span>
          <span v-if="msg.streaming" class="animate-pulse text-terminal-accent">▌</span>
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
import { ref, nextTick, onMounted } from 'vue'
import {
  getMarketOverview,
  getSectors,
  getChinaStocks,
  searchStock,
  getLimitUpStocks,
  getLimitDownStocks,
  getUnusualStocks,
  getTopSectors,
  getNorthFlowRanking,
  getLimitSummary,
  clearCache,
} from '../services/copilotData.js'
import {
  generateAnalysisReport,
  analyzeMarketSentiment,
} from '../services/copilotAnalysis.js'
import {
  formatMarketOverview,
  formatSectorList,
  formatLimitUp,
  formatLimitDown,
  formatUnusualStocks,
  formatAnalysisReport,
  formatMarketSentiment,
  formatTopSectors,
  formatNorthFlowRanking,
  formatSearchResults,
  formatHelp,
} from '../services/copilotResponse.js'

// WebLLM 状态
const llmMode = ref('cloud')  // 'cloud' | 'webllm'
const webllmReady = ref(false)
const isWebllmLoading = ref(false)
let webllmChat = null

// 初始化 WebLLM（懒加载）
async function initWebllm() {
  if (webllmReady.value || isWebllmLoading.value) return
  
  isWebllmLoading.value = true
  addAssistantMessage('⏳ 正在加载 WebLLM 模型，请稍候...')
  
  try {
    const { ChatModule } = await import('@mlc-ai/web-llm')
    
    webllmChat = new ChatModule()
    
    // 使用较小的模型以保证兼容性
    const initProgressCallback = (progress) => {
      console.log('[WebLLM] Loading:', (progress * 100).toFixed(1) + '%')
    }
    
    await webllmChat.reload('Llama-3.1-8B-Instruct-q4f32_1-MLC', initProgressCallback)
    
    webllmReady.value = true
    isWebllmLoading.value = false
    
    // 移除加载提示，添加成功提示
    messages.value = messages.value.filter(m => !m.content.includes('正在加载 WebLLM'))
    addAssistantMessage('✅ WebLLM 模型加载成功！现在可以使用本地 AI 进行对话。')
    
  } catch (err) {
    console.error('[WebLLM] Init error:', err)
    isWebllmLoading.value = false
    addAssistantMessage(`❌ WebLLM 加载失败: ${err.message}\n请确保浏览器支持 WebGPU 或尝试使用云端模式。`)
  }
}

// 切换 LLM 模式
async function toggleLlmMode() {
  if (llmMode.value === 'cloud') {
    // 切换到 WebLLM 模式
    llmMode.value = 'webllm'
    await initWebllm()
  } else {
    // 切换回云端模式
    llmMode.value = 'cloud'
    webllmReady.value = false
    addAssistantMessage('已切换回云端模式（Mock AI）。如需使用本地 AI，请点击切换到 WebLLM。')
  }
}

// 使用 WebLLM 生成回复
async function generateWithWebllm(prompt, context) {
  if (!webllmReady.value || !webllmChat) {
    throw new Error('WebLLM 未就绪')
  }
  
  // 构建完整提示词
  let fullPrompt = `你是一个专业的金融投研助手AlphaTerminal，专门为中国A股投资者提供数据分析、市场解读和投资建议。当前时间：2026年4月。请用中文回答，保持专业但不要过于正式。`
  
  if (context) {
    fullPrompt += `\n\n参考数据：\n${context}`
  }
  
  fullPrompt += `\n\n用户问题：${prompt}`
  
  const chunks = []
  await webllmChat.generate(fullPrompt, (chunk) => {
    chunks.push(chunk)
    // 实时更新显示
    const lastMsg = messages.value[messages.value.length - 1]
    if (lastMsg && lastMsg.role === 'assistant' && lastMsg.streaming) {
      lastMsg.displayedContent = chunks.join('')
      lastMsg.content = chunks.join('')
      scrollToBottom()
    }
  })
  
  return chunks.join('')
}

const messages       = ref([])
const inputText      = ref('')
const isLoading      = ref(false)
const historyEl      = ref(null)
const inputEl        = ref(null)

const ctxMarket = ref(true)
const ctxRates  = ref(false)
const ctxNews   = ref(false)

// 快捷命令
const quickCommands = [
  { cmd: '大盘', label: '大盘', icon: '📊', action: 'showMarket' },
  { cmd: '板块', label: '板块', icon: '🔥', action: 'showSectors' },
  { cmd: '北向', label: '北向', icon: '🌊', action: 'showNorthFlow' },
  { cmd: '涨停', label: '涨停', icon: '🚀', action: 'showLimitUp' },
  { cmd: '异动', label: '异动', icon: '⚡', action: 'showUnusual' },
  { cmd: '帮助', label: '帮助', icon: '❓', action: 'showHelp' },
]

// Props
const props = defineProps({
  marketOverview: { type: Object, default: null },
  ratesData:     { type: Array,  default: () => [] },
  newsData:      { type: Array,  default: () => [] },
  watchList:     { type: Array,  default: () => [] },
})

// Emits
const emit = defineEmits([
  'open-chart',
  'show-sector',
  'show-north-flow',
  'show-limit-up',
  'show-limit-down',
  'show-unusual',
  'show-watchlist',
])

function scrollToBottom() {
  nextTick(() => {
    if (historyEl.value) {
      historyEl.value.scrollTop = historyEl.value.scrollHeight
    }
  })
}

// 快速命令执行
async function executeQuickCommand(cmd) {
  const action = cmd.action
  
  addUserMessage(cmd.label)
  
  switch (action) {
    case 'showMarket':
      await showMarket()
      break
    case 'showSectors':
      await showSectors()
      break
    case 'showNorthFlow':
      await showNorthFlow()
      break
    case 'showLimitUp':
      await showLimitUp()
      break
    case 'showUnusual':
      await showUnusual()
      break
    case 'showHelp':
      showHelp()
      break
    default:
      addAssistantMessage('未知命令')
  }
}

// ========== 数据获取函数 ==========

async function showMarket() {
  isLoading.value = true
  try {
    // 同时获取多个数据源
    const [overview, sectors, limitSummary] = await Promise.all([
      getMarketOverview(),
      getSectors(),
      getLimitSummary(),
    ])
    
    const text = formatMarketOverview(overview)
    
    // 市场情绪分析
    const sentiment = analyzeMarketSentiment(overview?.indices, sectors)
    const sentimentText = formatMarketSentiment({ market: sentiment })
    
    // 涨停汇总
    let limitText = ''
    if (limitSummary && (limitSummary.zt_count > 0 || limitSummary.dt_count > 0)) {
      limitText = `\n📌 【涨跌停汇总】\n` +
        `涨停: ${limitSummary.zt_count} 只\n` +
        `跌停: ${limitSummary.dt_count} 只\n` +
        `市场情绪: ${limitSummary.market_sentiment || '分析中'}`
    }
    
    // 板块排行
    const topSectors = await getTopSectors(3)
    const sectorsText = formatTopSectors(topSectors)
    
    addAssistantMessage(text + '\n\n' + sentimentText + limitText + '\n\n' + sectorsText)
  } catch (e) {
    addErrorMessage(`获取大盘数据失败: ${e.message}`)
  } finally {
    isLoading.value = false
  }
}

async function showSectors() {
  isLoading.value = true
  try {
    const [sectors, limitSummary] = await Promise.all([
      getSectors(),
      getLimitSummary(),
    ])
    
    const lines = []
    lines.push(formatTopSectors({ top: sectors, bottom: sectors }))
    
    // 添加涨停板块分布
    if (limitSummary?.zt_industry) {
      const topInd = Object.entries(limitSummary.zt_industry).slice(0, 3)
      if (topInd.length > 0) {
        lines.push('')
        lines.push('🏆 【涨停集中板块】')
        for (const [ind, count] of topInd) {
          lines.push(`  ${ind}: ${count}只涨停`)
        }
      }
    }
    
    addAssistantMessage(lines.join('\n'))
  } catch (e) {
    addErrorMessage(`获取板块数据失败: ${e.message}`)
  } finally {
    isLoading.value = false
  }
}

async function showNorthFlow() {
  isLoading.value = true
  try {
    const data = await getNorthFlowRanking()
    addAssistantMessage(formatNorthFlowRanking(data))
  } catch (e) {
    addErrorMessage(`获取北向资金数据失败: ${e.message}`)
  } finally {
    isLoading.value = false
  }
}

async function showLimitUp() {
  isLoading.value = true
  try {
    const [stocks, summary] = await Promise.all([
      getLimitUpStocks(),
      getLimitSummary(),
    ])
    addAssistantMessage(formatLimitUp(stocks, summary))
  } catch (e) {
    addErrorMessage(`获取涨停数据失败: ${e.message}`)
  } finally {
    isLoading.value = false
  }
}

async function showLimitDown() {
  isLoading.value = true
  try {
    const stocks = await getLimitDownStocks()
    addAssistantMessage(formatLimitDown(stocks))
  } catch (e) {
    addErrorMessage(`获取跌停数据失败: ${e.message}`)
  } finally {
    isLoading.value = false
  }
}

async function showUnusual() {
  isLoading.value = true
  try {
    const [stocks, limitSummary] = await Promise.all([
      getUnusualStocks(),
      getLimitSummary(),
    ])
    const lines = []
    lines.push(formatUnusualStocks(stocks))
    if (limitSummary?.strongest?.length > 0) {
      lines.push('')
      lines.push('🔥 【强势股】换手率最高:')
      for (const s of limitSummary.strongest.slice(0, 3)) {
        lines.push(`  ${s.name}: 换手率${s.turnover_rate?.toFixed(1)}% 涨幅${s.change_pct?.toFixed(2)}%`)
      }
    }
    addAssistantMessage(lines.join('\n'))
  } catch (e) {
    addErrorMessage(`获取异动数据失败: ${e.message}`)
  } finally {
    isLoading.value = false
  }
}

function showHelp() {
  addAssistantMessage(formatHelp())
}

// ========== 股票搜索与分析 ==========

async function analyzeStock(keyword) {
  isLoading.value = true
  try {
    // 搜索股票
    const results = await searchStock(keyword)
    if (results.length === 0) {
      addAssistantMessage(`❓ 未找到「${keyword}」相关的股票，请检查股票名称或代码是否正确`)
      return
    }
    
    // 显示搜索结果
    if (results.length === 1) {
      // 只有一个结果，直接分析
      const stock = results[0]
      // 获取大盘数据作为背景
      const overview = await getMarketOverview()
      const report = generateAnalysisReport(stock, overview)
      addAssistantMessage(formatAnalysisReport(report))
    } else {
      // 多个结果，显示列表
      addAssistantMessage(formatSearchResults(results, keyword))
    }
  } catch (e) {
    addErrorMessage(`分析失败: ${e.message}`)
  } finally {
    isLoading.value = false
  }
}

async function openStock(keyword) {
  isLoading.value = true
  try {
    const results = await searchStock(keyword)
    if (results.length === 0) {
      addAssistantMessage(`❓ 未找到「${keyword}」相关的股票`)
      return
    }
    
    const stock = results[0]
    emit('open-chart', { symbol: stock.symbol, name: stock.name })
    addAssistantMessage(`📊 正在打开「${stock.name}(${stock.symbol})」的K线图...`)
  } catch (e) {
    addErrorMessage(`打开失败: ${e.message}`)
  } finally {
    isLoading.value = false
  }
}

async function compareStocks(keywords) {
  isLoading.value = true
  try {
    const stocks = []
    for (const kw of keywords) {
      const results = await searchStock(kw)
      if (results.length > 0) {
        stocks.push(results[0])
      }
    }
    
    if (stocks.length < 2) {
      addAssistantMessage('❓ 对比需要至少两只股票，请确保输入的股票都能被识别')
      return
    }
    
    addAssistantMessage(formatCompareStocks(stocks, '个股对比'))
    
    // 如果需要，打开对比视图
    if (stocks.length === 2) {
      emit('open-chart', { 
        symbols: stocks.map(s => s.symbol), 
        mode: 'compare' 
      })
    }
  } catch (e) {
    addErrorMessage(`对比失败: ${e.message}`)
  } finally {
    isLoading.value = false
  }
}

// ========== 命令解析 ==========

function parseCommand(text) {
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

// ========== 命令执行 ==========

async function executeCommand(cmd) {
  switch (cmd.type) {
    case 'help':
      showHelp()
      break
    case 'refresh':
      clearCache()
      addAssistantMessage('🔄 数据缓存已刷新')
      break
    case 'market':
      await showMarket()
      break
    case 'sectors':
      await showSectors()
      break
    case 'northFlow':
      await showNorthFlow()
      break
    case 'limitUp':
      await showLimitUp()
      break
    case 'limitDown':
      await showLimitDown()
      break
    case 'unusual':
      await showUnusual()
      break
    case 'watchlist':
      await showWatchlist()
      break
    case 'analyze':
      await analyzeStock(cmd.keyword)
      break
    case 'open':
      await openStock(cmd.keyword)
      break
    case 'compare':
      await compareStocks(cmd.keywords)
      break
    case 'addWatch':
      await addToWatch(cmd.keyword)
      break
    case 'removeWatch':
      await removeFromWatch(cmd.keyword)
      break
    case 'topSector':
      await showTopSector()
      break
    case 'bottomSector':
      await showBottomSector()
      break
    case 'northFlowTopBuy':
      await showNorthFlowTopBuy()
      break
    case 'search':
      await analyzeStock(cmd.keyword)
      break
    case 'chat':
      await sendToLLM(cmd.text)
      break
    default:
      return false
  }
  return true
}

async function showWatchlist() {
  const list = props.watchList || []
  if (list.length === 0) {
    addAssistantMessage('⭐ 自选股列表为空\n\n💡 输入「添加自选 股票名」来添加自选股')
    return
  }
  
  const text = formatStockList(list, `我的自选 (${list.length}只)`)
  addAssistantMessage(text)
}

async function addToWatch(keyword) {
  const results = await searchStock(keyword)
  if (results.length === 0) {
    addAssistantMessage(`❓ 未找到「${keyword}」`)
    return
  }
  
  const stock = results[0]
  emit('open-chart', { symbol: stock.symbol, name: stock.name, addToWatch: true })
  addAssistantMessage(`⭐ 已添加「${stock.name}(${stock.symbol})」到自选股`)
}

async function removeFromWatch(keyword) {
  addAssistantMessage(`🗑️ 已从自选股中移除「${keyword}」`)
}

async function showTopSector() {
  const data = await getTopSectors(5)
  addAssistantMessage('🔥 【今日最强板块】\n\n' + formatTopSectors({ top: data.top }))
}

async function showBottomSector() {
  const data = await getTopSectors(5)
  addAssistantMessage('❄️ 【今日最弱板块】\n\n' + formatTopSectors({ bottom: data.bottom }))
}

async function showNorthFlowTopBuy() {
  const data = await getNorthFlowRanking()
  addAssistantMessage(formatNorthFlowRanking(data))
}

// ========== LLM 对话 ==========

async function sendToLLM(text) {
  addUserMessage(text)
  isLoading.value = true
  
  // 添加占位
  const aiMsgIndex = messages.value.length
  messages.value.push({ 
    role: 'assistant', 
    content: '', 
    displayedContent: '🧠 正在思考...', 
    streaming: true 
  })
  
  try {
    // 构建上下文
    let context = ''
    if (ctxMarket.value && props.marketOverview) {
      context += formatMarketOverview(props.marketOverview) + '\n'
    }
    
    // 根据模式选择不同的生成方式
    if (llmMode.value === 'webllm' && webllmReady.value && webllmChat) {
      // 使用 WebLLM 本地生成
      await generateWithWebllm(text, context)
      messages.value[aiMsgIndex].streaming = false
    } else {
      // 使用云端 API
      const response = await fetch('/api/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
        body: JSON.stringify({ 
          prompt: text,
          context: context || undefined,
        }),
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
    }
  } catch (err) {
    messages.value[aiMsgIndex].displayedContent = `❌ 请求失败: ${err.message}\n\n💡 您可以尝试直接使用快捷命令查询数据`
    messages.value[aiMsgIndex].isError = true
    messages.value[aiMsgIndex].streaming = false
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}

// ========== 消息工具 ==========

function addUserMessage(content) {
  messages.value.push({ role: 'user', content, displayedContent: content, streaming: false })
  scrollToBottom()
}

function addAssistantMessage(content) {
  messages.value.push({ role: 'assistant', content, displayedContent: content, streaming: false })
  scrollToBottom()
}

function addErrorMessage(content) {
  messages.value.push({ role: 'assistant', content, displayedContent: content, streaming: false, isError: true })
  scrollToBottom()
}

// ========== 发送消息 ==========

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || isLoading.value) return
  
  inputText.value = ''
  
  // 解析并执行命令
  const cmd = parseCommand(text)
  const executed = await executeCommand(cmd)
  
  if (!executed) {
    // 如果命令未被识别，发送到 LLM
    await sendToLLM(text)
  }
  
  inputEl.value?.focus()
}
</script>
