<template>
  <div class="flex flex-col gap-2">

    <!-- ── A股温度计 ────────────────────────────────────────────── -->
    <div class="bg-terminal-bg rounded border border-gray-700 p-3">
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs text-terminal-dim">📊 A股市场情绪</span>
        <span class="text-[10px] font-mono text-terminal-dim">{{ data.timestamp || '--' }}</span>
      </div>

      <!-- 温度计进度条 -->
      <div class="relative h-5 rounded-full overflow-hidden flex mb-1.5"
           style="background: #1a1a2e;">
        <!-- 上涨（红） -->
        <div class="relative flex items-center justify-center transition-all duration-500"
             :style="{ width: `${upPct}%`, minWidth: upPct > 0 ? '2px' : '0' }">
          <span v-if="upPct > 12"
                class="text-[9px] font-mono font-bold text-white whitespace-nowrap drop-shadow">
            {{ data.advance || 0 }}
          </span>
          <div class="absolute right-0 top-0 bottom-0 w-px bg-black/30"></div>
        </div>
        <!-- 下跌（绿） -->
        <div class="flex-1 flex items-center justify-center"
             :style="{ minWidth: downPct > 0 ? '2px' : '0' }">
          <span v-if="downPct > 12 && data.decline"
                class="text-[9px] font-mono font-bold text-white whitespace-nowrap drop-shadow">
            {{ data.decline || 0 }}
          </span>
        </div>
      </div>

      <!-- 标签行 -->
      <div class="flex justify-between text-[9px] text-terminal-dim px-0.5">
        <span class="flex items-center gap-1">
          <span class="inline-block w-2 h-2 rounded-full bg-red-500/80"></span>
          涨 {{ data.advance || 0 }}
        </span>
        <span class="flex items-center gap-1">
          <span class="inline-block w-2 h-2 rounded-full bg-[#1a1a2e] border border-gray-700"></span>
          平 {{ data.unchanged || 0 }}
        </span>
        <span class="flex items-center gap-1">
          <span class="inline-block w-2 h-2 rounded-full bg-green-500/80"></span>
          跌 {{ data.decline || 0 }}
        </span>
      </div>

      <!-- 涨停/跌停统计 -->
      <div class="flex justify-between mt-2 text-[9px]">
        <span class="text-red-400">🔴 涨停 {{ data.limit_up || 0 }}</span>
        <span class="text-green-400">🟢 跌停 {{ data.limit_down || 0 }}</span>
        <span class="text-terminal-dim">合计 {{ data.total || 0 }} 只</span>
      </div>
    </div>

    <!-- ── 简版行情列表 ─────────────────────────────────────────── -->
    <div class="overflow-auto flex-1">
      <table class="w-full text-xs">
        <thead>
          <tr class="text-terminal-dim border-b border-gray-700">
            <th class="text-left py-1">指数</th>
            <th class="text-right py-1">最新价</th>
            <th class="text-right py-1">涨跌幅</th>
            <th class="text-right py-1">状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, key) in windItems" :key="key"
              class="border-b border-gray-800 hover:bg-white/5 cursor-pointer transition-colors"
              @click="$emit('symbol-click', key, item.name, '#fbbf24')">
            <td class="py-1.5 text-gray-300">{{ item.name }}</td>
            <td class="py-1.5 text-right font-mono">{{ formatPrice(item.index) }}</td>
            <td class="py-1.5 text-right font-mono"
                :class="(item.change_pct || 0) >= 0 ? 'text-red-400' : 'text-green-400'">
              {{ (item.change_pct || 0) >= 0 ? '+' : '' }}{{ (item.change_pct || 0).toFixed(2) }}%
            </td>
            <td class="py-1.5 text-right">
              <span class="px-1 py-0.5 rounded text-[9px]"
                    :class="item.status === '交易中' ? 'bg-green-500/20 text-green-400' : 'bg-gray-600/30 text-gray-400'">
                {{ item.status }}
              </span>
            </td>
          </tr>
          <tr v-if="!windItems.length">
            <td colspan="4" class="py-4 text-center text-terminal-dim text-xs">暂无数据</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  windItems: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['symbol-click'])

const data    = ref({})
const loading  = ref(true)
let timer     = null

const upPct   = computed(() => {
  const t = props.windItems?.total || (data.value.total || 0)
  if (!t) return 50
  return Math.round((data.value.advance || 0) / t * 100)
})
const downPct = computed(() => 100 - upPct.value)

function formatPrice(v) {
  if (v == null || isNaN(v)) return '--'
  return Number(v).toLocaleString('en-US', { maximumFractionDigits: 2 })
}

async function fetchSentiment() {
  try {
    const res = await fetch('/api/v1/market/sentiment')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const d = await res.json()
    data.value = d
  } catch (e) {
    console.warn('[SentimentGauge]', e.message)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchSentiment()
  // 每 3 分钟刷新一次
  timer = setInterval(fetchSentiment, 3 * 60 * 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>
