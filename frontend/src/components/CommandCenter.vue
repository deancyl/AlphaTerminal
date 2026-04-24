<template>
  <!-- 触发区域（左下角搜索入口） -->
  <div
    class="command-trigger flex items-center gap-2 px-3 py-1.5 rounded border border-theme bg-terminal-panel/90 text-theme-secondary hover:border-terminal-accent/40 hover:text-terminal-accent transition-colors cursor-pointer select-none"
    :class="isOpen ? 'border-terminal-accent/50 text-terminal-accent' : ''"
    @click="open"
    title="搜索标的 (Ctrl+K)"
  >
    <span class="text-[11px]">🔍</span>
    <span class="text-[11px]">搜索股票/指数/基金...</span>
    <kbd class="ml-2 text-[9px] px-1 py-0.5 rounded bg-theme-secondary border border-theme-secondary">Ctrl+K</kbd>
  </div>

  <!-- 命令面板（fixed overlay） -->
  <Teleport to="body">
    <div v-if="isOpen" class="fixed inset-0 z-[200] flex items-start justify-center pt-[15vh]" @mousedown.self="close">
      <div class="w-full max-w-[560px] max-h-[70vh] flex flex-col rounded-lg border border-theme bg-terminal-panel shadow-2xl overflow-hidden">
        <!-- 搜索框 -->
        <div class="flex items-center gap-2 px-4 py-3 border-b border-theme shrink-0">
          <span class="text-theme-secondary">🔍</span>
          <input
            ref="inputRef"
            v-model="query"
            class="flex-1 bg-transparent text-theme-primary text-sm outline-none placeholder-gray-500"
            placeholder="输入代码、拼音缩写或中文名称..."
            @keydown="onKeydown"
          />
          <kbd class="text-[9px] px-1.5 py-0.5 rounded bg-theme-secondary border border-theme-secondary text-theme-secondary">ESC</kbd>
        </div>

        <!-- 结果列表 -->
        <div class="flex-1 overflow-y-auto" ref="listRef">
          <!-- 无结果 -->
          <div v-if="query && filtered.length === 0" class="py-8 text-center text-theme-tertiary text-xs">
            未找到「{{ query }}」相关标的
          </div>

          <!-- 搜索结果 -->
          <template v-else-if="filtered.length > 0">
            <!-- 按市场分组 -->
            <template v-for="(group, gKey) in groupedResults" :key="gKey">
              <div class="px-4 py-1.5 text-[9px] text-theme-tertiary uppercase tracking-wider bg-theme-secondary/50 sticky top-0">
                {{ gKey }}
              </div>
              <div
                v-for="(item, idx) in group"
                :key="item.symbol"
                class="flex items-center gap-3 px-4 py-2 cursor-pointer transition-colors"
                :class="getGlobalIndex(item.symbol) === activeIndex
                  ? 'bg-terminal-accent/15 text-theme-primary'
                  : 'text-theme-primary hover:bg-theme-tertiary/50'"
                @click="select(item)"
                @mouseenter="activeIndex = getGlobalIndex(item.symbol)"
              >
                <!-- 类型标签 -->
                <span class="shrink-0 text-[9px] px-1 py-0.5 rounded border text-[9px]"
                  :class="typeClass(item.type)"
                >{{ item.type }}</span>
                <!-- 代码 -->
                <span class="w-20 font-mono text-[11px] text-theme-secondary shrink-0">{{ item.code }}</span>
                <!-- 名称 -->
                <span class="flex-1 text-[12px] truncate">{{ item.name }}</span>
                <!-- 拼音 -->
                <span class="text-[10px] text-theme-tertiary shrink-0">{{ item.pinyin }}</span>
              </div>
            </template>
          </template>

          <!-- 默认展示（无搜索词时） -->
          <template v-else>
            <div class="px-4 py-1.5 text-[9px] text-theme-tertiary uppercase tracking-wider bg-theme-secondary/50 sticky top-0">
              常用指数
            </div>
            <div
              v-for="(item, idx) in defaultItems"
              :key="item.symbol"
              class="flex items-center gap-3 px-4 py-2 cursor-pointer transition-colors"
              :class="activeIndex === idx
                ? 'bg-terminal-accent/15 text-theme-primary'
                : 'text-theme-primary hover:bg-theme-tertiary/50'"
              @click="select(item)"
              @mouseenter="activeIndex = idx"
            >
              <span class="shrink-0 text-[9px] px-1 py-0.5 rounded border text-[9px]"
                :class="typeClass(item.type)"
              >{{ item.type }}</span>
              <span class="w-20 font-mono text-[11px] text-theme-secondary shrink-0">{{ item.code }}</span>
              <span class="flex-1 text-[12px] truncate">{{ item.name }}</span>
              <span class="text-[10px] text-theme-tertiary shrink-0">{{ item.pinyin }}</span>
            </div>
          </template>
        </div>

        <!-- 底部状态栏 -->
        <div class="flex items-center justify-between gap-3 px-4 py-2 border-t border-theme text-[10px] text-theme-tertiary shrink-0">
          <div class="flex items-center gap-3">
            <span><kbd class="px-1 py-0.5 bg-theme-secondary rounded">↑↓</kbd> 导航</span>
            <span><kbd class="px-1 py-0.5 bg-theme-secondary rounded">Enter</kbd> 选中</span>
            <span><kbd class="px-1 py-0.5 bg-theme-secondary rounded">Esc</kbd> 关闭</span>
          </div>
          <!-- 数据源健康度指示灯 -->
          <div class="flex items-center gap-1.5 cursor-default" :title="message || statusText[status]">
            <span class="text-[11px]">{{ statusIcon[status] ?? '🟢' }}</span>
            <span
              class="text-[10px] transition-colors"
              :class="{
                'text-green-400':   status === 'ok',
                'text-yellow-400':  status === 'degraded',
                'text-red-400':     status === 'down',
              }"
            >{{ statusText[status] ?? '数据源正常' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 降级 Toast（非侵入提示） -->
    <Transition name="toast">
      <div
        v-if="toastVisible && status !== 'ok'"
        class="fixed bottom-6 left-1/2 -translate-x-1/2 z-[300] flex items-center gap-2 px-4 py-2 rounded-lg border text-xs shadow-xl"
        :class="{
          'bg-yellow-950/90 border-yellow-600/50 text-yellow-300': status === 'degraded',
          'bg-red-950/90 border-red-600/50 text-red-300': status === 'down',
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

// ── 数据源健康状态（由 api.js 拦截器驱动）──────────────────────
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

// ── Fuse.js 搜索实例 ───────────────────────────────────────────
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

// ── 默认展示项目 ────────────────────────────────────────────────
const defaultItems = computed(() => {
  return symbolRegistry.value
    .filter(s => s.type === 'index')
    .slice(0, 8)
})

// ── 分组结果 ──────────────────────────────────────────────────
const groupedResults = computed(() => {
  const groups = {}
  for (const item of filtered.value) {
    const g = marketLabel(item.market)
    if (!groups[g]) groups[g] = []
    groups[g].push(item)
  }
  return groups
})

// ── 全局 index 计算 ────────────────────────────────────────────
function getGlobalIndex(symbol) {
  const all = filtered.value
  const idx = all.findIndex(s => s.symbol === symbol)
  return idx >= 0 ? idx : 0
}

// ── 市场标签 ───────────────────────────────────────────────────
function marketLabel(market) {
  const labels = { AShare: 'A股', US: '美股', HK: '港股', JP: '日股', Macro: '宏观' }
  return labels[market] || market
}

// ── 类型样式 ───────────────────────────────────────────────────
function typeClass(type) {
  const map = {
    index:  'border-cyan-500/40 text-cyan-400',
    stock:  'border-green-500/40 text-bearish',
    fund:   'border-amber-500/40 text-amber-400',
    forex:  'border-purple-500/40 text-purple-400',
    commodity: 'border-orange-500/40 text-orange-400',
  }
  return map[type] || 'border-theme-secondary text-theme-secondary'
}

// ── 键盘事件 ───────────────────────────────────────────────────
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
    const el = listRef.value?.querySelector('.bg-terminal-accent\\/15')
    el?.scrollIntoView({ block: 'nearest' })
  })
}

// ── 选中标的 ───────────────────────────────────────────────────
function select(item) {
  setSymbol(item.symbol, item.name, '#00ff88', item.market)
  emit('select', item)
  close()
}

// ── 开关 ───────────────────────────────────────────────────────
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

// ── 全局键盘隐式触发 ───────────────────────────────────────────
function onGlobalKeydown(e) {
  // 隐式触发：未聚焦输入框时敲字母/数字
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

// 重置 activeIndex 当搜索词变化时
watch(query, () => { activeIndex.value = 0 })
</script>

<style scoped>
/* Toast 淡入淡出动画 */
.toast-enter-active, .toast-leave-active { transition: opacity 0.3s, transform 0.3s; }
.toast-enter-from  { opacity: 0; transform: translate(-50%, 8px); }
.toast-leave-to    { opacity: 0; transform: translate(-50%, -4px); }
</style>
