<template>
  <div class="flex flex-col w-full h-full overflow-hidden">
    <div class="shrink-0 flex items-center gap-2 px-3 py-1.5 border-b border-theme bg-terminal-panel/80">
      <span class="text-[10px] text-theme-muted">多因子归因沙盒</span>
      <input
        v-model="symbolInput"
        type="text"
        placeholder="股票代码 (如 sh600519)"
        class="flex-1 max-w-[200px] bg-theme-tertiary/30 border border-theme rounded-sm px-2 py-0.5 text-[10px] text-theme-primary"
      />
      <input
        v-model="startDate"
        type="date"
        class="bg-theme-tertiary/30 border border-theme rounded-sm px-2 py-0.5 text-[10px] text-theme-primary"
      />
      <input
        v-model="endDate"
        type="date"
        class="bg-theme-tertiary/30 border border-theme rounded-sm px-2 py-0.5 text-[10px] text-theme-primary"
      />
      <button
        @click="runAttribution"
        :disabled="loading || selectedFactors.length === 0"
        class="px-3 py-0.5 rounded-sm text-[10px] font-medium transition-colors"
        :class="loading || selectedFactors.length === 0
          ? 'bg-gray-600/40 text-theme-muted cursor-not-allowed'
          : 'bg-agent-blue/20 text-agent-blue hover:bg-agent-blue/30 border border-agent-blue/30'"
      >{{ loading ? '⏳ 计算中...' : '▶ 运行归因' }}</button>
    </div>

    <div class="flex-1 min-h-0 flex gap-2 p-2 overflow-hidden">
      <div class="w-[200px] shrink-0 flex flex-col border border-theme/30 rounded-sm overflow-hidden">
        <div class="shrink-0 px-2 py-1 border-b border-theme/30 bg-terminal-panel/60">
          <input
            v-model="factorSearch"
            type="text"
            placeholder="搜索因子..."
            class="w-full bg-theme-tertiary/30 border border-theme rounded-sm px-2 py-0.5 text-[10px] text-theme-primary"
          />
        </div>
        <div class="flex-1 min-h-0 overflow-y-auto p-1">
          <div
            v-for="cat in filteredCategories"
            :key="cat.id"
            class="mb-2"
          >
            <div class="text-[9px] text-theme-muted px-1 mb-1 flex items-center gap-1">
              <span>{{ cat.icon }}</span>
              <span>{{ cat.name }}</span>
            </div>
            <div
              v-for="factor in getFactorsByCategory(cat.id)"
              :key="factor.id"
              draggable="true"
              @dragstart="onDragStart($event, factor)"
              @click="toggleFactor(factor)"
              class="px-2 py-1 mb-0.5 rounded-sm text-[10px] cursor-pointer transition-colors"
              :class="isFactorSelected(factor.id)
                ? 'bg-agent-blue/20 text-agent-blue border border-agent-blue/30'
                : 'bg-theme-tertiary/20 text-theme-secondary hover:bg-theme-tertiary/40 border border-transparent'"
            >
              <span class="font-medium">{{ factor.name }}</span>
              <span class="text-[8px] text-theme-muted ml-1">{{ factor.unit }}</span>
            </div>
          </div>
        </div>
      </div>

      <div
        class="flex-1 min-w-0 flex flex-col border border-theme/30 rounded-sm overflow-hidden"
        @dragover.prevent
        @drop="onDrop"
      >
        <div class="shrink-0 px-2 py-1 border-b border-theme/30 bg-terminal-panel/60 text-[10px] text-theme-muted">
          已选因子 ({{ selectedFactors.length }}) - 拖拽添加或点击移除
        </div>
        <div v-if="selectedFactors.length === 0" class="flex-1 flex items-center justify-center text-[10px] text-theme-muted">
          从左侧拖拽因子到此处
        </div>
        <div v-else class="flex-1 min-h-0 overflow-y-auto p-2">
          <div class="flex flex-wrap gap-2">
            <div
              v-for="(factor, idx) in selectedFactors"
              :key="factor.id"
              class="px-2 py-1 rounded-sm bg-agent-blue/10 border border-agent-blue/30 text-[10px] text-agent-blue flex items-center gap-2"
            >
              <span class="font-medium">{{ factor.name }}</span>
              <input
                type="number"
                v-model.number="factorWeights[factor.id]"
                min="0"
                max="100"
                step="1"
                class="w-[50px] bg-theme-tertiary/30 border border-theme rounded-sm px-1 py-0.5 text-[9px] text-theme-primary"
              />
              <span class="text-[8px] text-theme-muted">%</span>
              <button
                @click="removeFactor(idx)"
                class="text-theme-muted hover:text-bearish"
              >✕</button>
            </div>
          </div>
        </div>
      </div>

      <div class="w-[300px] shrink-0 flex flex-col border border-theme/30 rounded-sm overflow-hidden">
        <div class="shrink-0 px-2 py-1 border-b border-theme/30 bg-terminal-panel/60 text-[10px] text-theme-muted">
          归因结果
        </div>
        <div v-if="!result" class="flex-1 flex items-center justify-center text-[10px] text-theme-muted">
          点击"运行归因"查看结果
        </div>
        <div v-else class="flex-1 min-h-0 overflow-y-auto p-2">
          <div class="grid grid-cols-2 gap-2 mb-3">
            <div class="rounded-sm border border-theme/30 bg-terminal-panel/60 px-2 py-1">
              <div class="text-[9px] text-theme-muted">总收益率</div>
              <div class="text-[11px] font-mono font-bold" :class="result.total_return >= 0 ? 'text-bullish' : 'text-bearish'">
                {{ result.total_return >= 0 ? '+' : '' }}{{ (result.total_return * 100).toFixed(2) }}%
              </div>
            </div>
            <div class="rounded-sm border border-theme/30 bg-terminal-panel/60 px-2 py-1">
              <div class="text-[9px] text-theme-muted">R²</div>
              <div class="text-[11px] font-mono font-bold text-theme-primary">
                {{ (result.r_squared * 100).toFixed(1) }}%
              </div>
            </div>
          </div>

          <div class="text-[9px] text-theme-muted mb-1">因子贡献</div>
          <div ref="chartEl" class="h-[150px] mb-2"></div>

          <div class="text-[9px] text-theme-muted mb-1">因子明细</div>
          <div class="overflow-x-auto border border-theme/20 rounded-sm">
            <table class="w-full text-[9px]">
              <thead class="bg-terminal-panel sticky top-0">
                <tr class="text-theme-muted border-b border-theme/20">
                  <th class="px-1 py-0.5 text-left">因子</th>
                  <th class="px-1 py-0.5 text-right">贡献</th>
                  <th class="px-1 py-0.5 text-right">暴露</th>
                  <th class="px-1 py-0.5 text-right">t值</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="fc in result.factor_contributions"
                  :key="fc.factor_id"
                  class="border-b border-theme/10"
                >
                  <td class="px-1 py-0.5 text-theme-primary">{{ fc.factor_name }}</td>
                  <td class="px-1 py-0.5 text-right font-mono" :class="fc.contribution >= 0 ? 'text-bullish' : 'text-bearish'">
                    {{ fc.contribution >= 0 ? '+' : '' }}{{ (fc.contribution * 100).toFixed(2) }}%
                  </td>
                  <td class="px-1 py-0.5 text-right font-mono text-theme-secondary">
                    {{ fc.exposure.toFixed(3) }}
                  </td>
                  <td class="px-1 py-0.5 text-right font-mono" :class="Math.abs(fc.t_statistic) > 2 ? 'text-agent-blue' : 'text-theme-muted'">
                    {{ fc.t_statistic.toFixed(2) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="mt-2 text-[9px] text-theme-muted">
            残差: {{ (result.residual * 100).toFixed(2) }}% |
            观测数: {{ result.num_observations }} |
            F统计量: {{ result.f_statistic.toFixed(2) }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { apiFetch } from '../../utils/api.js'
import { logger } from '../../utils/logger.js'
import { safeDispose } from '../../utils/chartManager.js'
import { getDynamicMarketColors } from '../../utils/echartsTheme.js'

const symbolInput = ref('sh600519')
const startDate = ref('2023-01-01')
const endDate = ref('2024-01-01')
const factorSearch = ref('')
const loading = ref(false)
const result = ref(null)
const chartEl = ref(null)
let chart = null

const allFactors = ref([])
const allCategories = ref([])
const selectedFactors = ref([])
const factorWeights = ref({})

const filteredCategories = computed(() => {
  if (!factorSearch.value) return allCategories.value
  return allCategories.value.filter(cat => {
    const factors = getFactorsByCategory(cat.id)
    return factors.some(f => f.name.toLowerCase().includes(factorSearch.value.toLowerCase()))
  })
})

function getFactorsByCategory(categoryId) {
  return allFactors.value.filter(f => f.category === categoryId)
}

function isFactorSelected(factorId) {
  return selectedFactors.value.some(f => f.id === factorId)
}

function toggleFactor(factor) {
  const idx = selectedFactors.value.findIndex(f => f.id === factor.id)
  if (idx >= 0) {
    selectedFactors.value.splice(idx, 1)
    delete factorWeights.value[factor.id]
  } else {
    selectedFactors.value.push({ ...factor })
    factorWeights.value[factor.id] = Math.round(100 / (selectedFactors.value.length))
  }
}

function removeFactor(idx) {
  const factor = selectedFactors.value[idx]
  selectedFactors.value.splice(idx, 1)
  delete factorWeights.value[factor.id]
}

function onDragStart(event, factor) {
  event.dataTransfer.setData('text/plain', JSON.stringify(factor))
}

function onDrop(event) {
  const data = event.dataTransfer.getData('text/plain')
  if (data) {
    try {
      const factor = JSON.parse(data)
      if (!isFactorSelected(factor.id)) {
        selectedFactors.value.push(factor)
        factorWeights.value[factor.id] = Math.round(100 / selectedFactors.value.length)
      }
    } catch (e) {
      logger.error('[FactorSandbox] Drop parse error:', e)
    }
  }
}

async function loadFactors() {
  try {
    const [factorsRes, categoriesRes] = await Promise.all([
      apiFetch('/api/v1/attribution/factors'),
      apiFetch('/api/v1/attribution/factors/categories'),
    ])
    allFactors.value = factorsRes?.data?.factors || []
    allCategories.value = categoriesRes?.data?.categories || []
  } catch (e) {
    logger.error('[FactorSandbox] Load factors error:', e)
  }
}

async function runAttribution() {
  if (loading.value || selectedFactors.value.length === 0) return
  loading.value = true
  result.value = null

  try {
    const resp = await apiFetch('/api/v1/attribution/sandbox', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbols: [symbolInput.value],
        factors: selectedFactors.value.map(f => f.id),
        start_date: startDate.value,
        end_date: endDate.value,
      }),
    })

    if (resp?.data?.results?.[0]) {
      result.value = resp.data.results[0].attribution
      await nextTick()
      renderChart()
    }
  } catch (e) {
    logger.error('[FactorSandbox] Run attribution error:', e)
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (!chartEl.value || !result.value?.factor_contributions?.length) return
  if (chart) { safeDispose(chart); chart = null }

  const fc = result.value.factor_contributions
  const marketColors = getDynamicMarketColors()

  chart = window.echarts.init(chartEl.value, 'dark')
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#1e2130',
      borderColor: '#374151',
      textStyle: { color: '#d1d5db', fontSize: 10 },
    },
    grid: { top: 4, bottom: 20, left: 4, right: 4, containLabel: true },
    xAxis: {
      type: 'category',
      data: fc.map(f => f.factor_name),
      axisLabel: { color: '#6b7280', fontSize: 8, rotate: 30, interval: 0 },
      axisLine: { lineStyle: { color: '#374151' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#6b7280', fontSize: 8, formatter: v => (v * 100).toFixed(1) + '%' },
      splitLine: { lineStyle: { color: '#1f2937' } },
    },
    series: [{
      type: 'bar',
      data: fc.map(f => ({
        value: f.contribution,
        itemStyle: { color: f.contribution >= 0 ? marketColors.UP : marketColors.DOWN },
      })),
      barMaxWidth: 24,
    }],
  })
}

onMounted(() => {
  loadFactors()
})

onBeforeUnmount(() => {
  safeDispose(chart)
  chart = null
})
</script>
