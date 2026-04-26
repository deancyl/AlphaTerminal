<template>
  <div class="flex flex-col w-full h-full overflow-hidden">
    <!-- 顶部栏 -->
    <div class="shrink-0 flex items-center justify-between px-2 py-1 border-b border-theme bg-terminal-panel/80">
      <span class="text-[10px] text-cyan-400 font-bold">⚖️ 对账审计</span>
      <div class="flex items-center gap-1">
        <span class="text-[8px]" :class="ok ? 'text-bullish' : 'text-bearish'">
          {{ ok ? '✅ 平衡' : '❌ 偏差' }}
        </span>
        <span class="text-[8px] text-theme-muted">{{ lastUpdate }}</span>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading && !data" class="flex-1 flex items-center justify-center text-theme-muted text-[10px]">
      ⏳ 加载对账数据...
    </div>

    <!-- 错误 -->
    <div v-else-if="error" class="flex-1 flex items-center justify-center text-bearish text-[10px]">
      ⚠️ {{ error }}
    </div>

    <!-- 数据内容 -->
    <div v-else-if="data" class="flex-1 min-h-0 overflow-y-auto px-2 py-1 space-y-1">

      <!-- 主账户汇总 -->
      <div class="bg-theme-tertiary/20 rounded border border-theme/20 p-1.5">
        <div class="text-[9px] text-cyan-400 font-bold mb-0.5">{{ data.parent_name }} (主账户)</div>
        <div class="grid grid-cols-3 gap-x-1 gap-y-0.5 text-[9px]">
          <span class="text-theme-muted">现金</span>
          <span class="text-right font-mono text-theme-primary">{{ fmt(data.parent.cash) }}</span>
          <span class="text-right text-theme-muted">元</span>
          <span class="text-theme-muted">持仓市值</span>
          <span class="text-right font-mono text-theme-primary">{{ fmt(data.parent.position_value) }}</span>
          <span class="text-right text-theme-muted">元</span>
          <span class="text-theme-muted font-bold">合计</span>
          <span class="text-right font-mono font-bold text-cyan-400">{{ fmt(data.parent.total) }}</span>
          <span class="text-right text-theme-muted">元</span>
        </div>
      </div>

      <!-- 子账户列表 -->
      <div v-if="data.children && data.children.length" class="space-y-0.5">
        <div class="text-[8px] text-theme-muted font-bold">子账户 ({{ data.children.length }})</div>
        <div
          v-for="child in data.children"
          :key="child.id"
          class="flex items-center justify-between bg-theme-tertiary/10 rounded px-1.5 py-0.5 text-[9px]"
        >
          <span class="text-theme-primary truncate flex-1">{{ child.name }}</span>
          <span class="font-mono text-theme-primary ml-1">{{ fmt(child.cash) }}</span>
        </div>
      </div>

      <!-- 守恒校验结果 -->
      <div
        class="mt-1 rounded p-1.5 border text-[9px]"
        :class="ok ? 'border-bullish/30 bg-bullish/5' : 'border-bearish/30 bg-bearish/5'"
      >
        <div class="flex items-center justify-between mb-0.5">
          <span class="font-bold" :class="ok ? 'text-bullish' : 'text-bearish'">
            {{ ok ? '✅ 资金守恒定律通过' : '❌ 资金守恒定律偏差' }}
          </span>
          <span class="font-mono" :class="ok ? 'text-bullish' : 'text-bearish'">
            Δ {{ fmt(data.conservation_delta) }}
          </span>
        </div>
        <div class="grid grid-cols-2 gap-x-1 gap-y-0.5 text-[8px] text-theme-muted">
          <span>子账户现金</span>
          <span class="text-right font-mono">{{ fmt(data.children_cash) }}</span>
          <span>子账户持仓</span>
          <span class="text-right font-mono">{{ fmt(data.children_position_value) }}</span>
          <span>子账户合计</span>
          <span class="text-right font-mono">{{ fmt(data.children_total) }}</span>
          <span class="font-bold">总计</span>
          <span class="text-right font-mono font-bold text-cyan-400">{{ fmt(data.grand_total) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { apiFetch } from '../utils/api.js'

const props = defineProps({
  portfolioId: { type: Number, default: 1 },
})

const data = ref(null)
const loading = ref(false)
const error = ref(null)
const lastUpdate = ref('')
let refreshTimer = null

const ok = computed(() => data.value?.conservation_ok ?? false)

function fmt(v) {
  if (v === null || v === undefined) return '--'
  return Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function fetchConservation() {
  loading.value = true
  try {
    const json = await apiFetch(`/api/v1/portfolio/${props.portfolioId}/conservation`, { timeoutMs: 5000 })
    if (json?.code === 0) {
      data.value = json.data
      error.value = null
    } else {
      error.value = json?.message || '获取失败'
      data.value = null
    }
    lastUpdate.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  } catch (e) {
    error.value = e.message
    data.value = null
  } finally {
    loading.value = false
  }
}

function safeRefresh() {
  try {
    fetchConservation()
  } catch (e) {
    console.error('[ConservationAuditCard] refresh error:', e)
  }
}

watch(() => props.portfolioId, () => { fetchConservation() })

onMounted(() => {
  fetchConservation()
  refreshTimer = setInterval(safeRefresh, 10000)
})

onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>
