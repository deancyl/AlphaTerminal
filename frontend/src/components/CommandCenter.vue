<template>
  <!-- Spotlight-style Trigger -->
  <div
    class="command-trigger flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 border border-white/10 backdrop-blur-sm text-gray-400 hover:border-agent-blue/40 hover:text-gray-200 transition-all cursor-pointer select-none"
    :class="isOpen ? 'border-agent-blue/50 text-white bg-agent-blue/10' : ''"
    @click="open"
    title="搜索标的"
  >
    <svg class="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
    <span class="text-sm text-gray-500">搜索股票、指数、基金...</span>
    <kbd class="ml-auto text-[11px] px-2 py-0.5 rounded bg-white/10 text-gray-400 border border-white/10 font-mono">
      {{ isMac ? '⌘K' : 'Ctrl+K' }}
    </kbd>
  </div>

  <!-- Command Palette Overlay -->
  <Teleport to="body">
    <Transition name="spotlight">
      <div v-if="isOpen" class="fixed inset-0 z-[200] flex items-start justify-center pt-[15vh]" @mousedown.self="close">
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm"></div>
        
        <!-- Palette -->
        <div class="relative w-full max-w-[600px] max-h-[70vh] flex flex-col rounded-xl border border-white/10 bg-terminal-bg/95 backdrop-blur-xl shadow-2xl overflow-hidden">
          <!-- Search Input -->
          <div class="flex items-center gap-3 px-5 py-4 border-b border-white/10 shrink-0">
            <svg class="w-5 h-5 text-gray-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              ref="inputRef"
              v-model="query"
              class="flex-1 bg-transparent text-white text-base outline-none placeholder-gray-600"
              placeholder="输入代码、拼音或名称搜索..."
              @keydown="onKeydown"
            />
            <kbd class="text-[11px] px-2 py-1 rounded bg-white/10 text-gray-500 border border-white/10 font-mono">ESC</kbd>
          </div>

          <!-- Results -->
          <div class="flex-1 overflow-y-auto" ref="listRef">
            <!-- No Results -->
            <div v-if="query && filtered.length === 0" class="py-12 text-center text-gray-600 text-sm">
              未找到「{{ query }}」相关标的
            </div>

            <!-- Search Results -->
            <template v-else-if="filtered.length > 0">
              <template v-for="(group, gKey) in groupedResults" :key="gKey">
                <div class="px-5 py-2 text-[11px] text-gray-600 uppercase tracking-wider bg-white/5 sticky top-0">
                  {{ gKey }}
                </div>
                <div
                  v-for="(item, idx) in group"
                  :key="item.symbol"
                  class="flex items-center gap-4 px-5 py-3 cursor-pointer transition-colors"
                  :class="getGlobalIndex(item.symbol) === activeIndex
                    ? 'bg-agent-blue/10 text-white'
                    : 'text-gray-300 hover:bg-white/5'"
                  @click="select(item)"
                  @mouseenter="activeIndex = getGlobalIndex(item.symbol)"
                >
                  <!-- Type Badge -->
                  <span class="shrink-0 text-[10px] px-2 py-0.5 rounded-full border text-[10px] font-medium"
                    :class="typeClass(item.type)"
                  >{{ item.type }}</span>
                  <!-- Code -->
                  <span class="w-16 font-mono text-xs text-gray-500 shrink-0 tabular-nums">{{ item.code }}</span>
                  <!-- Name -->
                  <span class="flex-1 text-sm truncate">{{ item.name }}</span>
                  <!-- Pinyin -->
                  <span class="text-[10px] text-gray-600 shrink-0">{{ item.pinyin }}</span>
                </div>
              </template>
            </template>

            <!-- Default Items -->
            <template v-else>
              <div class="px-5 py-2 text-[11px] text-gray-600 uppercase tracking-wider bg-white/5 sticky top-0">
                常用指数
              </div>
              <div
                v-for="(item, idx) in defaultItems"
                :key="item.symbol"
                class="flex items-center gap-4 px-5 py-3 cursor-pointer transition-colors"
                :class="activeIndex === idx
                  ? 'bg-agent-blue/10 text-white'
                  : 'text-gray-300 hover:bg-white/5'"
                @click="select(item)"
                @mouseenter="activeIndex = idx"
              >
                <span class="shrink-0 text-[10px] px-2 py-0.5 rounded-full border text-[10px] font-medium"
                  :class="typeClass(item.type)"
                >{{ item.type }}</span>
                <span class="w-16 font-mono text-xs text-gray-500 shrink-0 tabular-nums">{{ item.code }}</span>
                <span class="flex-1 text-sm truncate">{{ item.name }}</span>
                <span class="text-[10px] text-gray-600 shrink-0">{{ item.pinyin }}</span>
              </div>
            </template>
          </div>

          <!-- Footer -->
          <div class="flex items-center justify-between gap-4 px-5 py-3 border-t border-white/10 text-[11px] text-gray-600 shrink-0 bg-white/5">
            <div class="flex items-center gap-4">
              <span class="flex items-center gap-1">
                <kbd class="px-1.5 py-0.5 bg-white/10 rounded text-[10px]">↑</kbd>
                <kbd class="px-1.5 py-0.5 bg-white/10 rounded text-[10px]">↓</kbd>
                <span class="ml-1">导航</span>
              </span>
              <span class="flex items-center gap-1">
                <kbd class="px-1.5 py-0.5 bg-white/10 rounded text-[10px]">Enter</kbd>
                <span class="ml-1">选中</span>
              </span>
              <span class="flex items-center gap-1">
                <kbd class="px-1.5 py-0.5 bg-white/10 rounded text-[10px]">Esc</kbd>
                <span class="ml-1">关闭</span>
              </span>
            </div>
            <!-- Data Source Status -->
            <div class="flex items-center gap-1.5" :title="message || statusText[status]">
              <span class="text-[11px]">{{ statusIcon[status] ?? '🟢' }}</span>
              <span
                class="text-[10px] transition-colors"
                :class="{
                  'text-green-400': status === 'ok',
                  'text-yellow-400': status === 'degraded',
                  'text-red-400': status === 'down',
                }"
              >{{ statusText[status] ?? '数据源正常' }}</span>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Degraded Toast -->
    <Transition name="toast">
      <div
        v-if="toastVisible && status !== 'ok'"
        class="fixed bottom-6 left-1/2 -translate-x-1/2 z-[300] flex items-center gap-2 px-4 py-2 rounded-lg border text-xs shadow-lg backdrop-blur-sm"
        :class="{
          'bg-yellow-500/10 border-yellow-500/30 text-yellow-400': status === 'degraded',
          'bg-red-500/10 border-red-500/30 text-red-400': status === 'down',
        }"
      >
        <span>{{ statusIcon[status] }} {{ toastMsg || statusText[status] }}</span>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import Fuse from 'fuse.js'
import { useMarketStore } from '../stores/market.js'
import { useDataSourceStatus, onDataSourceStatusChange } from '../composables/useDataSourceStatus.js'
import { normalizeSymbol } from '../utils/symbols.js'

const emit = defineEmits(['select'])

const { symbolRegistry, loadSymbolRegistry, setSymbol } = useMarketStore()

const isOpen    = ref(false)
const query     = ref('')
const inputRef  = ref(null)
const listRef   = ref(null)
const activeIndex = ref(0)

const isMac = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform)

const { status, message } = useDataSourceStatus()
const toastMsg    = ref('')
const toastVisible = ref(false)
let   _toastTimer = null

const statusIcon = { ok: '🟢', degraded: '🟡', down: '🔴' }
const statusText  = { ok: '数据源正常', degraded: '备用线路', down: '全线熔断' }

function showToast(msg) {
  toastMsg.value = msg
  toastVisible.value = true
  clearTimeout(_toastTimer)
  _toastTimer = setTimeout(() => { toastVisible.value = false }, 4000)
}

onDataSourceStatusChange((s, msg) => {
  if (s !== 'ok' && msg) showToast(msg)
})

let fuse = null

async function initSearch() {
  await loadSymbolRegistry()
  fuse = new Fuse(symbolRegistry.value, {
    keys: [
      { name: 'code',   weight: 0.4 },
      { name: 'pinyin', weight: 0.35 },
      { name: 'name',   weight: 0.25 },
    ],
    threshold: 0.4,
    includeScore: true,
  })
}

const filtered = computed(() => {
  if (!query.value.trim()) return []
  if (!fuse) return []
  return fuse.search(query.value).map(r => r.item)
})

const defaultItems = computed(() => {
  return symbolRegistry.value
    .filter(s => s.type === 'index')
    .slice(0, 8)
})

const groupedResults = computed(() => {
  const groups = {}
  for (const item of filtered.value) {
    const g = marketLabel(item.market)
    if (!groups[g]) groups[g] = []
    groups[g].push(item)
  }
  return groups
})

function getGlobalIndex(symbol) {
  const all = filtered.value
  const idx = all.findIndex(s => s.symbol === symbol)
  return idx >= 0 ? idx : 0
}

function marketLabel(market) {
  const labels = { AShare: 'A股', US: '美股', HK: '港股', JP: '日股', Macro: '宏观' }
  return labels[market] || market
}

function typeClass(type) {
  const map = {
    index:  'border-agent-blue/40 text-agent-blue',
    stock:  'border-green-500/40 text-green-400',
    fund:   'border-yellow-500/40 text-yellow-400',
    forex:  'border-purple-500/40 text-purple-400',
    commodity: 'border-orange-500/40 text-orange-400',
  }
  return map[type] || 'border-gray-500/40 text-gray-400'
}

function onKeydown(e) {
  const total = filtered.value.length || defaultItems.value.length
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = Math.min(activeIndex.value + 1, total - 1)
    scrollActiveIntoView()
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = Math.max(activeIndex.value - 1, 0)
    scrollActiveIntoView()
  } else if (e.key === 'Enter') {
    e.preventDefault()
    const list = filtered.value.length > 0 ? filtered.value : defaultItems.value
    if (list[activeIndex.value]) select(list[activeIndex.value])
  } else if (e.key === 'Escape') {
    close()
  }
}

function scrollActiveIntoView() {
  nextTick(() => {
    const el = listRef.value?.querySelector('.bg-agent-blue\\/10')
    el?.scrollIntoView({ block: 'nearest' })
  })
}

function select(item) {
  setSymbol(item.symbol, item.name, '#00ff88', item.market)
  emit('select', item)
  close()
}

function open() {
  isOpen.value = true
  query.value = ''
  activeIndex.value = 0
  nextTick(() => inputRef.value?.focus())
}

function close() {
  isOpen.value = false
  query.value = ''
}

function onGlobalKeydown(e) {
  if (isOpen.value) return
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
  if (e.ctrlKey || e.metaKey || e.altKey) return

  const ch = e.key
  if ((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || (ch >= '0' && ch <= '9')) {
    e.preventDefault()
    open()
    query.value = ch
    nextTick(() => {
      if (inputRef.value) inputRef.value.value = ch
    })
  }
}

function onCtrlK(e) {
  if (e.key === 'k' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault()
    isOpen.value ? close() : open()
  }
}

onMounted(() => {
  initSearch()
  window.addEventListener('keydown', onGlobalKeydown)
  window.addEventListener('keydown', onCtrlK)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onGlobalKeydown)
  window.removeEventListener('keydown', onCtrlK)
})

watch(query, () => { activeIndex.value = 0 })
</script>

<style scoped>
/* Spotlight animation */
.spotlight-enter-active,
.spotlight-leave-active {
  transition: all 0.2s ease;
}
.spotlight-enter-from,
.spotlight-leave-to {
  opacity: 0;
}
.spotlight-enter-from > div:last-child,
.spotlight-leave-to > div:last-child {
  transform: scale(0.95) translateY(-10px);
}

/* Toast animation */
.toast-enter-active, .toast-leave-active {
  transition: opacity 0.3s, transform 0.3s;
}
.toast-enter-from  { opacity: 0; transform: translate(-50%, 8px); }
.toast-leave-to    { opacity: 0; transform: translate(-50%, -4px); }
</style>
