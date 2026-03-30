<template>
  <div class="flex flex-col h-full">

    <!-- 标题区 -->
    <div class="p-4 border-b border-gray-800 shrink-0">
      <h2 class="text-terminal-accent font-bold text-base flex items-center gap-2">
        🧠 AlphaTerminal Copilot
      </h2>
      <p class="text-terminal-dim text-xs mt-0.5">由 OpenClaw 驱动的智能投研助手</p>
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
      <div v-if="messages.length === 0" class="text-center mt-16">
        <div class="text-4xl mb-3">💬</div>
        <p class="text-terminal-dim text-sm">开始一场投研对话</p>
        <p class="text-terminal-dim text-xs mt-1">例如：「分析今日 A 股市场资金流向」</p>
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
          placeholder="输入投研问题... (Shift+Enter 换行)"
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
import { ref, nextTick } from 'vue'

const messages       = ref([])
const inputText      = ref('')
const isLoading      = ref(false)
const historyEl      = ref(null)
const inputEl        = ref(null)

// 上下文勾选
const ctxMarket = ref(true)
const ctxRates  = ref(true)
const ctxNews   = ref(false)

// 接收父组件传入的市场数据
const props = defineProps({
  marketOverview: { type: Object, default: null },
  ratesData:      { type: Array,  default: () => [] },
  newsData:       { type: Array,  default: () => [] },
})

function scrollToBottom() {
  nextTick(() => {
    if (historyEl.value) {
      historyEl.value.scrollTop = historyEl.value.scrollHeight
    }
  })
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

  // 添加用户消息
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
    const response = await fetch('http://localhost:8002/api/v1/chat', {
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
