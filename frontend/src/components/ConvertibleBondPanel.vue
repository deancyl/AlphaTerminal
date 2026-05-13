<template>
  <div class="flex flex-col h-full overflow-auto gap-2 p-3">
    <!-- Header -->
    <div class="terminal-panel border border-theme-secondary rounded-sm p-3 shrink-0">
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs text-terminal-dim">🔄 可转债行情</span>
        <div class="flex items-center gap-2">
          <span class="text-[10px] px-1.5 py-0.5 rounded-sm border border-[var(--color-info-border)] text-[var(--color-info)]/70">
            {{ totalBonds }} 只
          </span>
          <span class="text-[10px] text-terminal-dim">{{ updateTime }}</span>
        </div>
      </div>
      <!-- Search -->
      <input 
        v-model="searchQuery" 
        placeholder="搜索债券名称/代码/正股..." 
        class="w-full px-2 py-1.5 text-xs bg-terminal-bg border border-theme rounded-sm text-theme-primary placeholder-terminal-dim focus:outline-none focus:border-theme-secondary"
      />
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex-1 flex items-center justify-center">
      <div class="text-terminal-dim text-xs">加载中...</div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="flex-1 flex items-center justify-center">
      <div class="text-bearish text-xs">{{ error }}</div>
    </div>

    <!-- Bond Table -->
    <div v-else class="flex-1 overflow-auto terminal-panel border border-theme-secondary rounded-sm">
      <table class="w-full text-xs">
        <thead class="sticky top-0 bg-terminal-panel">
          <tr class="border-b border-theme">
            <th class="py-2 px-2 text-left text-terminal-dim font-medium">代码</th>
            <th class="py-2 px-2 text-left text-terminal-dim font-medium">名称</th>
            <th class="py-2 px-2 text-left text-terminal-dim font-medium hidden sm:table-cell">正股</th>
            <th class="py-2 px-2 text-right text-terminal-dim font-medium">转股价</th>
            <th class="py-2 px-2 text-right text-terminal-dim font-medium">转股价值</th>
            <th class="py-2 px-2 text-right text-terminal-dim font-medium">债券价格</th>
            <th class="py-2 px-2 text-right text-terminal-dim font-medium">溢价率</th>
            <th class="py-2 px-2 text-center text-terminal-dim font-medium hidden md:table-cell">评级</th>
          </tr>
        </thead>
        <tbody>
          <tr 
            v-for="bond in paginatedBonds" 
            :key="bond.code" 
            class="border-b border-theme hover:bg-theme-hover cursor-pointer transition-colors"
            @click="showDetail(bond)"
          >
            <td class="py-1.5 px-2 text-theme-primary font-mono">{{ bond.code }}</td>
            <td class="py-1.5 px-2">{{ bond.name }}</td>
            <td class="py-1.5 px-2 text-terminal-dim hidden sm:table-cell">{{ bond.underlying_name }}</td>
            <td class="py-1.5 px-2 text-right font-mono">{{ bond.conversion_price?.toFixed(2) || '--' }}</td>
            <td class="py-1.5 px-2 text-right font-mono">{{ bond.conversion_value?.toFixed(2) || '--' }}</td>
            <td class="py-1.5 px-2 text-right font-mono">{{ bond.bond_price?.toFixed(2) || '--' }}</td>
            <td class="py-1.5 px-2 text-right font-mono" :class="getPremiumClass(bond.conversion_premium)">
              {{ bond.conversion_premium != null ? bond.conversion_premium.toFixed(2) + '%' : '--' }}
            </td>
            <td class="py-1.5 px-2 text-center hidden md:table-cell">
              <span class="px-1 py-0.5 rounded text-[10px]" :class="getRatingClass(bond.credit_rating)">
                {{ bond.credit_rating || '--' }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
      
      <!-- Empty State -->
      <div v-if="filteredBonds.length === 0" class="py-8 text-center text-terminal-dim text-xs">
        {{ searchQuery ? '未找到匹配的可转债' : '暂无数据' }}
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="filteredBonds.length > 0" class="flex justify-between items-center py-2 px-1">
      <span class="text-[10px] text-terminal-dim">
        显示 {{ (page - 1) * pageSize + 1 }}-{{ Math.min(page * pageSize, filteredBonds.length) }} / {{ filteredBonds.length }} 只
      </span>
      <div class="flex gap-1">
        <button 
          @click="prevPage" 
          :disabled="page === 1"
          class="px-2 py-1 text-[10px] rounded border border-theme disabled:opacity-50 disabled:cursor-not-allowed hover:bg-theme-hover"
        >
          上一页
        </button>
        <span class="px-2 py-1 text-[10px] text-terminal-dim">{{ page }} / {{ totalPages }}</span>
        <button 
          @click="nextPage" 
          :disabled="page >= totalPages"
          class="px-2 py-1 text-[10px] rounded border border-theme disabled:opacity-50 disabled:cursor-not-allowed hover:bg-theme-hover"
        >
          下一页
        </button>
      </div>
    </div>

    <!-- Detail Modal -->
    <Teleport to="body">
      <div 
        v-if="detailModalVisible" 
        class="fixed inset-0 z-[9999] flex items-center justify-center"
        style="background: rgba(0,0,0,0.65); backdrop-filter: blur(3px);"
        @click.self="detailModalVisible = false"
      >
        <div class="terminal-panel border border-theme rounded-sm p-4 w-full max-w-[600px] max-h-[80vh] overflow-auto">
          <div class="flex items-center justify-between mb-3">
            <div>
              <span class="text-sm font-semibold text-theme-primary">{{ selectedBond?.name }}</span>
              <span class="text-xs text-terminal-dim ml-2">{{ selectedBond?.code }}</span>
            </div>
            <button @click="detailModalVisible = false" class="text-terminal-dim hover:text-theme-primary">✕</button>
          </div>
          
          <div class="grid grid-cols-2 gap-3 text-xs mb-4">
            <div class="flex flex-col">
              <span class="text-terminal-dim">正股</span>
              <span class="text-theme-primary">{{ selectedBond?.underlying_name }} ({{ selectedBond?.underlying_code }})</span>
            </div>
            <div class="flex flex-col">
              <span class="text-terminal-dim">正股价</span>
              <span class="font-mono">{{ selectedBond?.underlying_price?.toFixed(2) }}</span>
            </div>
            <div class="flex flex-col">
              <span class="text-terminal-dim">转股价</span>
              <span class="font-mono">{{ selectedBond?.conversion_price?.toFixed(2) }}</span>
            </div>
            <div class="flex flex-col">
              <span class="text-terminal-dim">转股价值</span>
              <span class="font-mono">{{ selectedBond?.conversion_value?.toFixed(2) }}</span>
            </div>
            <div class="flex flex-col">
              <span class="text-terminal-dim">债券价格</span>
              <span class="font-mono">{{ selectedBond?.bond_price?.toFixed(2) }}</span>
            </div>
            <div class="flex flex-col">
              <span class="text-terminal-dim">转股溢价率</span>
              <span class="font-mono" :class="getPremiumClass(selectedBond?.conversion_premium)">
                {{ selectedBond?.conversion_premium?.toFixed(2) }}%
              </span>
            </div>
            <div class="flex flex-col">
              <span class="text-terminal-dim">信用评级</span>
              <span>{{ selectedBond?.credit_rating || '--' }}</span>
            </div>
            <div class="flex flex-col">
              <span class="text-terminal-dim">发行规模(亿)</span>
              <span class="font-mono">{{ selectedBond?.issue_size || '--' }}</span>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { apiFetch } from '../utils/api.js'
import { logger } from '../utils/logger.js'

// State
const bonds = ref([])
const loading = ref(false)
const error = ref('')
const searchQuery = ref('')
const page = ref(1)
const pageSize = 20
const updateTime = ref('')
const totalBonds = ref(0)
const detailModalVisible = ref(false)
const selectedBond = ref(null)

let refreshTimer = null

// Computed
const filteredBonds = computed(() => {
  if (!searchQuery.value) return bonds.value
  const q = searchQuery.value.toLowerCase()
  return bonds.value.filter(b => 
    b.name?.toLowerCase().includes(q) || 
    b.code?.includes(q) ||
    b.underlying_name?.toLowerCase().includes(q) ||
    b.underlying_code?.includes(q)
  )
})

const totalPages = computed(() => Math.ceil(filteredBonds.value.length / pageSize) || 1)

const paginatedBonds = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredBonds.value.slice(start, start + pageSize)
})

// Methods
async function fetchBonds() {
  loading.value = true
  error.value = ''
  try {
    const data = await apiFetch('/api/v1/bond/convertible/list', 30000)
    if (data?.bonds) {
      bonds.value = data.bonds
      totalBonds.value = data.total || data.bonds.length
      updateTime.value = new Date().toLocaleTimeString()
    }
  } catch (e) {
    logger.warn('[ConvertibleBondPanel] fetch failed:', e)
    error.value = '加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function getPremiumClass(premium) {
  if (premium == null) return 'text-terminal-dim'
  if (premium < 10) return 'text-bullish'
  if (premium > 30) return 'text-bearish'
  return 'text-[var(--color-warning)]'
}

function getRatingClass(rating) {
  if (!rating) return 'text-terminal-dim'
  if (rating.startsWith('AAA')) return 'bg-bullish/20 text-bullish'
  if (rating.startsWith('AA')) return 'bg-[var(--color-info)]/20 text-[var(--color-info)]'
  return 'bg-terminal-dim/20 text-terminal-dim'
}

function showDetail(bond) {
  selectedBond.value = bond
  detailModalVisible.value = true
}

function prevPage() { 
  if (page.value > 1) page.value-- 
}

function nextPage() { 
  if (page.value < totalPages.value) page.value++ 
}

// Lifecycle
onMounted(() => {
  fetchBonds()
  refreshTimer = setInterval(fetchBonds, 5 * 60 * 1000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>
