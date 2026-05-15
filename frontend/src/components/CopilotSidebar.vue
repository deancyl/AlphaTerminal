<template>
  <div class="flex flex-col h-full bg-theme-secondary border-l border-agent-blue/20">
    <CopilotHeader :session-id="currentSessionId" @new-conversation="startNewConversation" />
    <CopilotQuickCommands :commands="quickCommands" :is-loading="isLoading" @execute="executeQuickCommand" />
    <CopilotContextSelector
      v-model:ctxMarket="ctxMarket"
      v-model:ctxRates="ctxRates"
      v-model:ctxNews="ctxNews"
      v-model:ctxPortfolio="ctxPortfolio"
      v-model:ctxHistorical="ctxHistorical"
      v-model:selectedProvider="selectedProvider"
      v-model:selectedModel="selectedModel"
      :providers="providers"
      :currentModels="currentModels"
      :portfolioList="portfolioList"
      :isLoadingPortfolio="isLoadingPortfolio"
      v-model:selectedPortfolioId="selectedPortfolioId"
    />
    <CopilotMessageList ref="messageListRef" :messages="messages" @retry="handleRetry" />
    <CopilotInput
      v-model:inputText="inputText"
      :is-loading="isLoading"
      :message-count="messages.length"
      :streaming-progress="streamingProgress"
      :show-timeout-warning="showTimeoutWarning"
      @send="sendMessage"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { mdRender } from '../composables/useCopilotMarkdown.js'
import { showMarket, showSectors, showNorthFlow, showLimitUp, showLimitDown, showUnusual } from '../composables/useCopilotData.js'
import { parseCommand } from '../composables/useCopilotCommands.js'
import { analyzeStock, openStock, compareStocks } from '../composables/useCopilotStock.js'
import { sendToLLM, getSessionId, clearSessionId } from '../composables/useCopilotChat.js'
import { clearCache, searchStock, getTopSectors, getNorthFlowRanking } from '../services/copilotData.js'
import { formatHelp, formatTopSectors, formatNorthFlowRanking } from '../services/copilotResponse.js'
import { logger } from '../utils/logger.js'
import { useMarketStore } from '../stores/market.js'
import { apiFetch } from '../utils/api.js'
import CopilotHeader from './copilot/CopilotHeader.vue'
import CopilotQuickCommands from './copilot/CopilotQuickCommands.vue'
import CopilotContextSelector from './copilot/CopilotContextSelector.vue'
import CopilotMessageList from './copilot/CopilotMessageList.vue'
import CopilotInput from './copilot/CopilotInput.vue'

// State
const messages = ref([])
const inputText = ref('')
const isLoading = ref(false)
const isLoadingPortfolio = ref(false)
const messageListRef = ref(null)
const ctxMarket = ref(true)
const ctxRates = ref(false)
const ctxNews = ref(false)
const ctxPortfolio = ref(false)
const ctxHistorical = ref(false)
const selectedPortfolioId = ref(null)
const portfolioList = ref([])
const currentSessionId = ref(getSessionId())
const streamingProgress = ref(0)
const showTimeoutWarning = ref(false)
let timeoutWarningTimer = null

// Model selection
const selectedProvider = ref('deepseek')
const providers = [
  { label: 'DeepSeek', id: 'deepseek' },
  { label: '硅基流动', id: 'siliconflow' },
  { label: '通义千问', id: 'qianwen' },
  { label: 'OpenAI', id: 'openai' },
  { label: 'OpenCode', id: 'opencode' },
  { label: 'Mock', id: 'mock' },
]
const allModels = {
  deepseek: [
    { label: 'DeepSeek-V3（推荐）', value: 'deepseek-chat' },
    { label: 'DeepSeek-R1（思维链）', value: 'deepseek-reasoner' },
  ],
  siliconflow: [
    { label: 'DeepSeek-V3', value: 'deepseek-ai/DeepSeek-V3' },
    { label: 'DeepSeek-R1', value: 'deepseek-ai/DeepSeek-R1' },
  ],
  qianwen: [{ label: 'Qwen Plus', value: 'qwen-plus' }],
  openai: [{ label: 'GPT-3.5 Turbo', value: 'gpt-3.5-turbo' }],
  opencode: [{ label: 'OpenCode Chat', value: 'opencode-chat' }],
  mock: [{ label: '本地模拟', value: '' }],
}
const selectedModel = ref('deepseek-chat')
const currentModels = computed(() => allModels[selectedProvider.value] || [])

// Quick commands
const quickCommands = [
  { cmd: '大盘', label: '大盘', icon: '📊', action: 'showMarket' },
  { cmd: '板块', label: '板块', icon: '🔥', action: 'showSectors' },
  { cmd: '北向', label: '北向', icon: '🌊', action: 'showNorthFlow' },
  { cmd: '涨停', label: '涨停', icon: '🚀', action: 'showLimitUp' },
  { cmd: '异动', label: '异动', icon: '⚡', action: 'showUnusual' },
  { cmd: '帮助', label: '帮助', icon: '❓', action: 'showHelp' },
]

// Props & Emits
const props = defineProps({
  marketOverview: { type: Object, default: null },
  watchList: { type: Array, default: () => [] },
})
const emit = defineEmits([
  'open-chart', 'show-sector', 'show-north-flow',
  'show-limit-up', 'show-limit-down', 'show-unusual', 'show-watchlist',
])
const { currentSymbol } = useMarketStore()

async function loadPortfolioList() {
  isLoadingPortfolio.value = true
  try {
    const res = await apiFetch('/api/v1/portfolio/')
    portfolioList.value = res.portfolios || []
    if (portfolioList.value.length > 0 && !selectedPortfolioId.value) {
      selectedPortfolioId.value = portfolioList.value[0].id
    }
  } catch (e) {
    logger.debug('[Copilot] Failed to load portfolio list:', e.message)
  } finally {
    isLoadingPortfolio.value = false
  }
}

onMounted(() => loadPortfolioList())

function startNewConversation() {
  clearSessionId()
  currentSessionId.value = getSessionId()
  messages.value = []
}

function scrollToBottom() {
  nextTick(() => {
    if (messageListRef.value?.historyEl) {
      messageListRef.value.historyEl.scrollTop = messageListRef.value.historyEl.scrollHeight
    }
  })
}

function addUserMessage(content) {
  messages.value.push({ role: 'user', content, displayedContent: content, streaming: false })
  scrollToBottom()
}

function addAssistantMessage(content) {
  messages.value.push({ role: 'assistant', content, displayedContent: content, renderedContent: mdRender(content), streaming: false })
  scrollToBottom()
}

function addErrorMessage(content, errorType = 'generic') {
  messages.value.push({ role: 'assistant', content, displayedContent: content, streaming: false, isError: true, errorType })
  scrollToBottom()
}

// Retry last user message
function handleRetry(messageIndex) {
  // Find the last user message before the error message
  const errorIndex = messageIndex !== undefined ? messageIndex : messages.value.length - 1
  
  // Find the last user message before this error
  let lastUserMessage = null
  for (let i = errorIndex - 1; i >= 0; i--) {
    if (messages.value[i].role === 'user') {
      lastUserMessage = messages.value[i]
      break
    }
  }
  
  if (!lastUserMessage) {
    logger.warn('[Copilot] No previous user message to retry')
    return
  }
  
  // Remove the error message
  if (messageIndex !== undefined) {
    messages.value.splice(messageIndex, 1)
  } else {
    messages.value.pop()
  }
  
  // Re-execute the last user message
  const cmd = parseCommand(lastUserMessage.content)
  executeCommand(cmd, lastUserMessage.content)
}

// Quick command execution
async function executeQuickCommand(cmd) {
  addUserMessage(cmd.label)
  isLoading.value = true
  
  try {
    let text = ''
    switch (cmd.action) {
      case 'showMarket':
        text = await showMarket()
        break
      case 'showSectors':
        text = await showSectors()
        break
      case 'showNorthFlow':
        text = await showNorthFlow()
        break
      case 'showLimitUp':
        text = await showLimitUp()
        break
      case 'showUnusual':
        text = await showUnusual()
        break
      case 'showHelp':
        text = formatHelp()
        break
      default:
        text = '未知命令'
    }
    addAssistantMessage(text)
  } catch (e) {
    addErrorMessage(`获取数据失败: ${e.message}`, 'network')
  } finally {
    isLoading.value = false
  }
}

// Send message
async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || isLoading.value) return
  
  inputText.value = ''
  const cmd = parseCommand(text)
  await executeCommand(cmd, text)
}

// Execute command
async function executeCommand(cmd, originalText) {
  isLoading.value = true
  
  try {
    const actions = {
      help: () => formatHelp(),
      refresh: () => { clearCache(); return '🔄 数据缓存已刷新' },
      market: () => showMarket(),
      sectors: () => showSectors(),
      northFlow: () => showNorthFlow(),
      limitUp: () => showLimitUp(),
      limitDown: () => showLimitDown(),
      unusual: () => showUnusual(),
      topSector: async () => '🔥 【今日最强板块】\n\n' + formatTopSectors({ top: (await getTopSectors(5)).top }),
      bottomSector: async () => '❄️ 【今日最弱板块】\n\n' + formatTopSectors({ bottom: (await getTopSectors(5)).bottom }),
      northFlowTopBuy: async () => formatNorthFlowRanking(await getNorthFlowRanking()),
    }
    
    if (actions[cmd.type]) {
      const result = await actions[cmd.type]()
      addAssistantMessage(result)
    } else if (cmd.type === 'watchlist') {
      await showWatchlist()
    } else if (cmd.type === 'analyze' || cmd.type === 'search') {
      addUserMessage(originalText)
      const result = await analyzeStock(cmd.keyword)
      result.success ? addAssistantMessage(result.data) : addErrorMessage(result.error)
    } else if (cmd.type === 'open') {
      addUserMessage(originalText)
      const result = await openStock(cmd.keyword)
      if (result.success) { emit('open-chart', result.data); addAssistantMessage(result.message) }
      else addErrorMessage(result.error)
    } else if (cmd.type === 'compare') {
      addUserMessage(originalText)
      const result = await compareStocks(cmd.keywords)
      if (result.success) {
        addAssistantMessage(result.data.text)
        if (result.data.stocks.length === 2) emit('open-chart', { symbols: result.data.symbols, mode: 'compare' })
      } else addErrorMessage(result.error)
    } else if (cmd.type === 'addWatch') {
      await addToWatch(cmd.keyword)
    } else if (cmd.type === 'removeWatch') {
      addAssistantMessage(`🗑️ 已从自选股中移除「${cmd.keyword}」`)
    } else {
      await handleLLMChat(originalText)
    }
  } catch (e) {
    addErrorMessage(`执行失败: ${e.message}`, 'generic')
  } finally {
    isLoading.value = false
  }
}

// Handle LLM chat
async function handleLLMChat(text) {
  addUserMessage(text)
  const aiMsgIndex = messages.value.length
  messages.value.push({ role: 'assistant', content: '', displayedContent: '🧠 正在思考...', streaming: true, fromCache: false })
  
  // Reset progress and start timeout warning timer
  streamingProgress.value = 0
  showTimeoutWarning.value = false
  timeoutWarningTimer = setTimeout(() => {
    showTimeoutWarning.value = true
  }, 30000) // 30 seconds
  
  await sendToLLM(text, {
    ctxMarket: ctxMarket.value, ctxRates: ctxRates.value, ctxNews: ctxNews.value,
    ctxPortfolio: ctxPortfolio.value, ctxHistorical: ctxHistorical.value,
    selectedProvider: selectedProvider.value, selectedModel: selectedModel.value,
    portfolioId: selectedPortfolioId.value, currentSymbol: currentSymbol.value
  }, {
    onMessage: (content) => {
      messages.value[aiMsgIndex].renderedContent = mdRender(content)
      messages.value[aiMsgIndex].content = content
      scrollToBottom()
    },
    onProgress: (charCount) => {
      streamingProgress.value = charCount
    },
    onComplete: () => { 
      messages.value[aiMsgIndex].streaming = false
      streamingProgress.value = 0
      showTimeoutWarning.value = false
      if (timeoutWarningTimer) {
        clearTimeout(timeoutWarningTimer)
        timeoutWarningTimer = null
      }
    },
    onError: (err) => {
      messages.value[aiMsgIndex].content = `❌ 请求失败: ${err.message}`
      messages.value[aiMsgIndex].isError = true
      messages.value[aiMsgIndex].streaming = false
      messages.value[aiMsgIndex].errorType = err.type || 'network'
      messages.value[aiMsgIndex].error = err.message
      streamingProgress.value = 0
      showTimeoutWarning.value = false
      if (timeoutWarningTimer) {
        clearTimeout(timeoutWarningTimer)
        timeoutWarningTimer = null
      }
    },
    onCached: (cached) => {
      messages.value[aiMsgIndex].displayedContent = cached
      messages.value[aiMsgIndex].content = cached
      messages.value[aiMsgIndex].renderedContent = mdRender(cached)
      messages.value[aiMsgIndex].streaming = false
      messages.value[aiMsgIndex].fromCache = true
      streamingProgress.value = 0
      showTimeoutWarning.value = false
      if (timeoutWarningTimer) {
        clearTimeout(timeoutWarningTimer)
        timeoutWarningTimer = null
      }
      scrollToBottom()
    }
  })
}

// Watchlist helpers
async function showWatchlist() {
  const list = props.watchList || []
  if (list.length === 0) return addAssistantMessage('⭐ 自选股列表为空\n\n💡 输入「添加自选 股票名」来添加自选股')
  const lines = [`📋 我的自选 (${list.length}只)`, '─'.repeat(40), ...list.map(s => `${s.symbol || ''} ${s.name || ''}`)]
  addAssistantMessage(lines.join('\n'))
}

async function addToWatch(keyword) {
  const results = await searchStock(keyword)
  if (results.length === 0) return addAssistantMessage(`❓ 未找到「${keyword}」`)
  const stock = results[0]
  emit('open-chart', { symbol: stock.symbol, name: stock.name, addToWatch: true })
  addAssistantMessage(`⭐ 已添加「${stock.name}(${stock.symbol})」到自选股`)
}
// Lifecycle cleanup
onUnmounted(() => {
  if (timeoutWarningTimer) {
    clearTimeout(timeoutWarningTimer)
    timeoutWarningTimer = null
  }
})
</script>

<style src="../styles/copilot-markdown.css"></style>
