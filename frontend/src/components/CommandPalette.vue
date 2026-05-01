<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition-all duration-150 ease-in"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="visible"
        class="fixed inset-0 z-[900] flex items-start justify-center pt-[15vh]"
        @click="handleBackdropClick"
      >
        <!-- 半透明遮罩 -->
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm"></div>

        <!-- 命令面板 -->
        <div
          class="relative w-full max-w-[560px] mx-4 rounded-lg shadow-2xl overflow-hidden flex flex-col max-h-[60vh]"
          style="background: var(--bg-glass); backdrop-filter: blur(12px);"
          @click.stop
        >
          <!-- 搜索输入框 -->
          <div class="flex items-center gap-3 px-4 py-3 border-b border-[var(--border-primary)]">
            <span class="text-[var(--text-tertiary)] text-lg">🔍</span>
            <input
              ref="inputRef"
              v-model="query"
              type="text"
              placeholder="输入代码/名称/拼音首字母，或输入命令（如 :F9）"
              class="flex-1 bg-transparent text-[var(--text-primary)] text-sm outline-none placeholder-[var(--text-placeholder)]"
              @keydown="handleInputKeydown"
            />
            <span class="text-[10px] text-[var(--text-muted)] px-2 py-1 rounded border border-[var(--border-secondary)]">ESC</span>
          </div>

          <!-- 搜索结果 -->
          <div class="flex-1 overflow-y-auto">
            <!-- 最近搜索 -->
            <div v-if="!query && recentSearches.length > 0" class="py-2">
              <div class="px-4 py-1 text-[10px] text-[var(--text-muted)] uppercase tracking-wider">最近搜索</div>
              <div
                v-for="(item, index) in recentSearches"
                :key="item.id"
                class="px-4 py-2 flex items-center gap-3 cursor-pointer transition-colors"
                :class="selectedIndex === index ? 'bg-[var(--color-primary-bg)]' : 'hover:bg-[var(--bg-hover)]'"
                @click="executeItem(item)"
                @mouseenter="selectedIndex = index"
              >
                <span class="text-base">{{ item.icon }}</span>
                <div class="flex-1 min-w-0">
                  <div class="text-sm text-[var(--text-primary)]">{{ item.name }}</div>
                  <div class="text-[10px] text-[var(--text-muted)]">{{ item.desc }}</div>
                </div>
                <button
                  class="text-[var(--text-muted)] hover:text-[var(--text-primary)] px-1"
                  @click.stop="removeRecent(item)"
                >
                  ✕
                </button>
              </div>
            </div>

            <!-- 搜索结果分类 -->
            <template v-if="query">
              <!-- 股票结果 -->
              <div v-if="stockResults.length > 0" class="py-2">
                <div class="px-4 py-1 text-[10px] text-[var(--text-muted)] uppercase tracking-wider">股票</div>
                <div
                  v-for="(item, index) in stockResults"
                  :key="item.symbol"
                  class="px-4 py-2 flex items-center gap-3 cursor-pointer transition-colors"
                  :class="selectedIndex === getGlobalIndex('stock', index) ? 'bg-[var(--color-primary-bg)]' : 'hover:bg-[var(--bg-hover)]'"
                  @click="executeItem(item)"
                  @mouseenter="selectedIndex = getGlobalIndex('stock', index)"
                >
                  <span class="text-base">📈</span>
                  <div class="flex-1 min-w-0">
                    <div class="text-sm text-[var(--text-primary)]">
                      <span class="font-mono">{{ item.symbol }}</span>
                      <span class="ml-2">{{ item.name }}</span>
                    </div>
                    <div class="text-[10px] text-[var(--text-muted)]">{{ item.pinyin }}</div>
                  </div>
                </div>
              </div>

              <!-- 功能命令 -->
              <div v-if="commandResults.length > 0" class="py-2">
                <div class="px-4 py-1 text-[10px] text-[var(--text-muted)] uppercase tracking-wider">命令</div>
                <div
                  v-for="(item, index) in commandResults"
                  :key="item.cmd"
                  class="px-4 py-2 flex items-center gap-3 cursor-pointer transition-colors"
                  :class="selectedIndex === getGlobalIndex('command', index) ? 'bg-[var(--color-primary-bg)]' : 'hover:bg-[var(--bg-hover)]'"
                  @click="executeItem(item)"
                  @mouseenter="selectedIndex = getGlobalIndex('command', index)"
                >
                  <span class="text-base">{{ item.icon }}</span>
                  <div class="flex-1 min-w-0">
                    <div class="text-sm text-[var(--text-primary)]">{{ item.name }}</div>
                    <div class="text-[10px] text-[var(--text-muted)]">{{ item.desc }}</div>
                  </div>
                  <span class="text-[10px] text-[var(--text-muted)] px-2 py-0.5 rounded border border-[var(--border-secondary)]">{{ item.shortcut }}</span>
                </div>
              </div>

              <!-- 视图切换 -->
              <div v-if="viewResults.length > 0" class="py-2">
                <div class="px-4 py-1 text-[10px] text-[var(--text-muted)] uppercase tracking-wider">视图</div>
                <div
                  v-for="(item, index) in viewResults"
                  :key="item.id"
                  class="px-4 py-2 flex items-center gap-3 cursor-pointer transition-colors"
                  :class="selectedIndex === getGlobalIndex('view', index) ? 'bg-[var(--color-primary-bg)]' : 'hover:bg-[var(--bg-hover)]'"
                  @click="executeItem(item)"
                  @mouseenter="selectedIndex = getGlobalIndex('view', index)"
                >
                  <span class="text-base">{{ item.icon }}</span>
                  <div class="flex-1 min-w-0">
                    <div class="text-sm text-[var(--text-primary)]">{{ item.name }}</div>
                  </div>
                  <span class="text-[10px] text-[var(--text-muted)]">{{ item.shortcut }}</span>
                </div>
              </div>

              <!-- 无结果 -->
              <div v-if="totalResults === 0" class="py-8 text-center">
                <div class="text-2xl mb-2">🔍</div>
                <div class="text-sm text-[var(--text-muted)]">未找到匹配结果</div>
                <div class="text-[10px] text-[var(--text-muted)] mt-1">尝试输入股票代码或命令</div>
              </div>
            </template>

            <!-- 提示信息 -->
            <div v-if="!query && recentSearches.length === 0" class="py-8 text-center">
              <div class="text-2xl mb-2">⌨️</div>
              <div class="text-sm text-[var(--text-muted)]">输入代码、名称或命令</div>
              <div class="text-[10px] text-[var(--text-muted)] mt-2">
                例如：<span class="text-[var(--color-primary)]">000001</span> 或 <span class="text-[var(--color-primary)]">:F9</span> 或 <span class="text-[var(--color-primary)]">上证指数</span>
              </div>
            </div>
          </div>

          <!-- 底部快捷键提示 -->
          <div class="px-4 py-2 border-t border-[var(--border-primary)] flex items-center gap-4 text-[10px] text-[var(--text-muted)]">
            <span><kbd class="px-1 py-0.5 rounded border border-[var(--border-secondary)]">↑↓</kbd> 选择</span>
            <span><kbd class="px-1 py-0.5 rounded border border-[var(--border-secondary)]">Enter</kbd> 执行</span>
            <span><kbd class="px-1 py-0.5 rounded border border-[var(--border-secondary)]">ESC</kbd> 关闭</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { logger } from '../utils/logger.js'

const props = defineProps({
  visible: { type: Boolean, default: false }
})

const emit = defineEmits(['close', 'select-stock', 'change-view', 'open-f9'])

// ── 状态 ──
const query = ref('')
const inputRef = ref(null)
const selectedIndex = ref(0)
const recentSearches = ref([])
const stockData = ref([]) // 从API加载的股票数据
const isLoadingStocks = ref(false)

// ── 加载股票列表 ──
async function loadStockList() {
  if (stockData.value.length > 0) return // 已加载
  
  isLoadingStocks.value = true
  try {
    const response = await fetch('/api/v1/market/symbols')
    const data = await response.json()
    if (data?.data?.symbols) {
      stockData.value = data.data.symbols.map(s => ({
        symbol: s.code || s.symbol,
        name: s.name,
        pinyin: s.pinyin || generatePinyin(s.name)
      }))
      logger.log(`[CommandPalette] Loaded ${stockData.value.length} stocks`)
    }
  } catch (error) {
    logger.error('[CommandPalette] Failed to load stock list:', error)
    // 使用备用数据
    stockData.value = STOCK_DATA
  } finally {
    isLoadingStocks.value = false
  }
}

// ── 简单拼音首字母生成（备用）──
function generatePinyin(name) {
  // 这是一个简化版本，实际应该使用完整的拼音库
  return name.split('').map(c => {
    const code = c.charCodeAt(0)
    if (code >= 0x4e00 && code <= 0x9fa5) {
      // 简单映射（实际应该使用pinyin库）
      return 'X'
    }
    return c
  }).join('')
}

// ── 模拟股票数据（备用）──
const STOCK_DATA = [
  { symbol: '000001', name: '平安银行', pinyin: 'PAYH' },
  { symbol: '000002', name: '万科A', pinyin: 'WKA' },
  { symbol: '000333', name: '美的集团', pinyin: 'MDJT' },
  { symbol: '000858', name: '五粮液', pinyin: 'WLY' },
  { symbol: '002594', name: '比亚迪', pinyin: 'BYD' },
  { symbol: '300750', name: '宁德时代', pinyin: 'NDSD' },
  { symbol: '600000', name: '浦发银行', pinyin: 'PFYH' },
  { symbol: '600036', name: '招商银行', pinyin: 'ZSYH' },
  { symbol: '600519', name: '贵州茅台', pinyin: 'GZMT' },
  { symbol: '601318', name: '中国平安', pinyin: 'ZGPA' },
  { symbol: '601398', name: '工商银行', pinyin: 'GSYH' },
  { symbol: '603288', name: '海天味业', pinyin: 'HTWY' },
  { symbol: '000016', name: '深康佳A', pinyin: 'SKJA' },
  { symbol: '000063', name: '中兴通讯', pinyin: 'ZXTX' },
  { symbol: '000100', name: 'TCL科技', pinyin: 'TCLKJ' },
  { symbol: '600276', name: '恒瑞医药', pinyin: 'HRYY' },
  { symbol: '600900', name: '长江电力', pinyin: 'CJDL' },
  { symbol: '601012', name: '隆基绿能', pinyin: 'LJLN' },
  { symbol: '601888', name: '中国中免', pinyin: 'ZGZM' },
  { symbol: '688981', name: '中芯国际', pinyin: 'ZXGJ' },
]

// ── 功能命令 ──
const COMMANDS = [
  { cmd: ':F9', name: 'F9 深度资料', desc: '打开当前标的的深度资料', icon: '📋', shortcut: 'F9', action: 'f9' },
  { cmd: ':F5', name: '刷新行情', desc: '刷新当前页面数据', icon: '🔄', shortcut: 'F5', action: 'refresh' },
  { cmd: ':EXPORT', name: '导出数据', desc: '导出当前数据到Excel', icon: '📊', shortcut: 'Ctrl+S', action: 'export' },
  { cmd: ':FULLSCREEN', name: '全屏模式', desc: '切换全屏显示', icon: '⛶', shortcut: 'F11', action: 'fullscreen' },
]

// ── 视图列表 ──
const VIEWS = [
  { id: 'stock', name: '股票行情', icon: '📊', shortcut: '1 / 0' },
  { id: 'portfolio', name: '投资组合', icon: '💰', shortcut: 'Ctrl+P' },
  { id: 'fund', name: '基金分析', icon: '📈', shortcut: 'Ctrl+F' },
  { id: 'bond', name: '债券行情', icon: '📉', shortcut: '5 / Ctrl+B' },
  { id: 'futures', name: '期货行情', icon: '🛢️', shortcut: '6' },
  { id: 'macro', name: '宏观经济', icon: '🌍', shortcut: 'Ctrl+M' },
  { id: 'backtest', name: '回测实验室', icon: '🔬', shortcut: 'Ctrl+R' },
]

// ── 计算属性 ──
const stockResults = computed(() => {
  if (!query.value) return []
  const q = query.value.toLowerCase().trim()
  const dataSource = stockData.value.length > 0 ? stockData.value : STOCK_DATA
  
  return dataSource.filter(s => {
    // 支持代码、名称、拼音首字母搜索
    const symbolMatch = s.symbol.toLowerCase().includes(q)
    const nameMatch = s.name.includes(query.value)
    const pinyinMatch = s.pinyin && s.pinyin.toLowerCase().includes(q)
    
    return symbolMatch || nameMatch || pinyinMatch
  }).slice(0, 10) // 限制显示10条结果
})

const commandResults = computed(() => {
  if (!query.value) return []
  const q = query.value.toLowerCase()
  if (!q.startsWith(':')) return []
  return COMMANDS.filter(c =>
    c.cmd.toLowerCase().includes(q) ||
    c.name.includes(query.value)
  )
})

const viewResults = computed(() => {
  if (!query.value || query.value.startsWith(':')) return []
  const q = query.value.toLowerCase()
  return VIEWS.filter(v =>
    v.name.includes(query.value) ||
    v.id.includes(q)
  )
})

const totalResults = computed(() =>
  stockResults.value.length + commandResults.value.length + viewResults.value.length
)

// ── 方法 ──
function handleBackdropClick() {
  emit('close')
}

function handleInputKeydown(event) {
  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault()
      selectedIndex.value = Math.min(selectedIndex.value + 1, totalResults.value - 1)
      break
    case 'ArrowUp':
      event.preventDefault()
      selectedIndex.value = Math.max(selectedIndex.value - 1, 0)
      break
    case 'Enter':
      event.preventDefault()
      executeSelected()
      break
    case 'Escape':
      event.preventDefault()
      emit('close')
      break
  }
}

function getGlobalIndex(category, index) {
  let offset = 0
  if (category === 'command') {
    offset = stockResults.value.length
  } else if (category === 'view') {
    offset = stockResults.value.length + commandResults.value.length
  }
  return offset + index
}

function executeSelected() {
  const allResults = [
    ...stockResults.value,
    ...commandResults.value,
    ...viewResults.value
  ]
  if (allResults[selectedIndex.value]) {
    executeItem(allResults[selectedIndex.value])
  }
}

function executeItem(item) {
  // 添加到最近搜索
  addToRecent(item)

  if (item.symbol) {
    // 股票
    emit('select-stock', item)
  } else if (item.action) {
    // 命令
    switch (item.action) {
      case 'f9':
        emit('open-f9')
        break
      case 'refresh':
        window.location.reload()
        break
      case 'export':
        logger.log('[Command] Export triggered')
        break
      case 'fullscreen':
        if (document.fullscreenElement) {
          document.exitFullscreen()
        } else {
          document.documentElement.requestFullscreen()
        }
        break
    }
  } else if (item.id) {
    // 视图
    emit('change-view', item.id)
  }

  emit('close')
}

function addToRecent(item) {
  const id = item.symbol || item.cmd || item.id
  recentSearches.value = recentSearches.value.filter(r => r.id !== id)
  recentSearches.value.unshift({ ...item, id })
  if (recentSearches.value.length > 10) {
    recentSearches.value = recentSearches.value.slice(0, 10)
  }
  // 持久化
  localStorage.setItem('alphaterminal-recent-searches', JSON.stringify(recentSearches.value))
}

function removeRecent(item) {
  recentSearches.value = recentSearches.value.filter(r => r.id !== item.id)
  localStorage.setItem('alphaterminal-recent-searches', JSON.stringify(recentSearches.value))
}

// ── 加载最近搜索和股票数据 ──
onMounted(() => {
  try {
    const saved = localStorage.getItem('alphaterminal-recent-searches')
    if (saved) {
      recentSearches.value = JSON.parse(saved)
    }
  } catch (e) {
    logger.warn('[CommandPalette] Failed to load recent searches')
  }
  
  // 预加载股票列表
  loadStockList()
})

// ── 监听visible变化 ──
watch(() => props.visible, (val) => {
  if (val) {
    nextTick(() => {
      inputRef.value?.focus()
      query.value = ''
      selectedIndex.value = 0
    })
  }
})

// ── 监听query变化重置选中 ──
watch(query, () => {
  selectedIndex.value = 0
})
</script>
