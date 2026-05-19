<template>
  <div class="factor-sandbox">
    <div class="factor-sandbox__header">
      <div class="factor-sandbox__title">
        <span class="factor-sandbox__title-icon">🎯</span>
        <span>因子筛选沙盒</span>
      </div>
      <div class="factor-sandbox__actions">
        <select
          v-model="universe"
          class="factor-sandbox__select"
        >
          <option value="all">全市场</option>
          <option value="hs300">沪深300</option>
          <option value="zz500">中证500</option>
          <option value="cyb50">创业板50</option>
        </select>
        <button
          @click="handleScreen"
          :disabled="selectedFactors.length === 0 || screeningLoading"
          class="factor-sandbox__btn"
          :class="{ 'factor-sandbox__btn--loading': screeningLoading }"
        >
          {{ screeningLoading ? '筛选中...' : '开始筛选' }}
        </button>
      </div>
    </div>

    <div class="factor-sandbox__body">
      <div class="factor-sandbox__library">
        <div class="factor-sandbox__library-header">
          <span class="factor-sandbox__library-title">因子库</span>
          <input
            v-model="factorSearch"
            type="text"
            placeholder="搜索因子..."
            class="factor-sandbox__search"
          />
        </div>
        <div class="factor-sandbox__library-content">
          <div
            v-for="category in filteredCategories"
            :key="category.id"
            class="factor-sandbox__category"
          >
            <div class="factor-sandbox__category-header">
              <span class="factor-sandbox__category-icon">{{ category.icon }}</span>
              <span class="factor-sandbox__category-name">{{ category.name }}</span>
              <span class="factor-sandbox__category-count">
                {{ getFactorsByCategory(category.id).length }}
              </span>
            </div>
            <div class="factor-sandbox__category-factors">
              <FactorDragItem
                v-for="factor in getFactorsByCategory(category.id)"
                :key="factor.id"
                :factor="factor"
                :selected="isFactorSelected(factor.id)"
                @click="toggleFactor"
              />
            </div>
          </div>
        </div>
      </div>

      <div class="factor-sandbox__funnel">
        <FactorFunnel
          :factors="selectedFactors"
          @remove="removeFactor"
          @reorder="reorderFactors"
          @add="addFactor"
        />
      </div>

      <div class="factor-sandbox__results">
        <div class="factor-sandbox__results-header">
          <span class="factor-sandbox__results-title">
            筛选结果
            <span v-if="screenedStocks.length > 0" class="factor-sandbox__results-count">
              ({{ screenedStocks.length }})
            </span>
          </span>
        </div>
        
        <div v-if="error" class="factor-sandbox__error">
          <span class="factor-sandbox__error-icon">⚠️</span>
          <span>{{ error }}</span>
        </div>
        
        <div v-else-if="screeningLoading" class="factor-sandbox__loading">
          <div class="factor-sandbox__loading-spinner"></div>
          <span>正在筛选...</span>
        </div>
        
        <div v-else-if="screenedStocks.length === 0" class="factor-sandbox__empty">
          <span class="factor-sandbox__empty-icon">📊</span>
          <span>选择因子后点击筛选</span>
        </div>
        
        <div v-else class="factor-sandbox__stock-list">
          <div
            v-for="stock in screenedStocks"
            :key="stock.symbol"
            class="factor-sandbox__stock-item"
            :class="{ 'factor-sandbox__stock-item--selected': selectedStock?.symbol === stock.symbol }"
            @click="selectStock(stock)"
          >
            <div class="factor-sandbox__stock-info">
              <div class="factor-sandbox__stock-name">{{ stock.name || stock.symbol }}</div>
              <div class="factor-sandbox__stock-symbol">{{ stock.symbol }}</div>
            </div>
            <div class="factor-sandbox__stock-score">
              <div class="factor-sandbox__score-value" :class="getScoreClass(stock.score)">
                {{ stock.score?.toFixed(2) ?? 'N/A' }}
              </div>
              <div class="factor-sandbox__score-label">综合得分</div>
            </div>
          </div>
        </div>

        <div v-if="selectedStock" class="factor-sandbox__preview">
          <div class="factor-sandbox__preview-header">
            <span>回测预览: {{ selectedStock.name || selectedStock.symbol }}</span>
          </div>
          <div ref="previewChartRef" class="factor-sandbox__preview-chart"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useFactorSandbox } from '@/composables/useFactorSandbox.js'
import { safeDispose } from '@/utils/chartManager.js'
import { getDynamicMarketColors } from '@/utils/echartsTheme.js'
import FactorDragItem from './FactorDragItem.vue'
import FactorFunnel from './FactorFunnel.vue'

const {
  factors,
  categories,
  selectedFactors,
  screenedStocks,
  screeningLoading,
  error,
  universe,
  isFactorSelected,
  fetchFactors,
  addFactor,
  removeFactor,
  toggleFactor,
  reorderFactors,
  runScreening,
  getBacktestPreview,
} = useFactorSandbox()

const factorSearch = ref('')
const selectedStock = ref(null)
const previewChartRef = ref(null)
let previewChart = null

const filteredCategories = computed(() => {
  if (!factorSearch.value) return categories.value
  return categories.value.filter(cat => {
    const catFactors = getFactorsByCategory(cat.id)
    return catFactors.some(f => 
      f.name.toLowerCase().includes(factorSearch.value.toLowerCase())
    )
  })
})

function getFactorsByCategory(categoryId) {
  return factors.value.filter(f => f.category === categoryId)
}

async function handleScreen() {
  await runScreening()
}

function selectStock(stock) {
  selectedStock.value = stock
  loadBacktestPreview()
}

async function loadBacktestPreview() {
  if (!selectedStock.value) return
  
  const endDate = new Date().toISOString().split('T')[0]
  const startDate = new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
  
  const results = await getBacktestPreview([selectedStock.value.symbol], startDate, endDate)
  
  if (results && results.length > 0) {
    await nextTick()
    renderPreviewChart(results[0])
  }
}

function renderPreviewChart(data) {
  if (!previewChartRef.value || !data) return
  
  if (previewChart) {
    safeDispose(previewChart)
    previewChart = null
  }
  
  const marketColors = getDynamicMarketColors()
  
  previewChart = window.echarts.init(previewChartRef.value, 'dark')
  previewChart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'var(--bg-surface)',
      borderColor: 'var(--border-base)',
      textStyle: { color: 'var(--text-primary)', fontSize: 10 },
    },
    grid: { top: 10, bottom: 30, left: 10, right: 10, containLabel: true },
    xAxis: {
      type: 'category',
      data: ['收益率', '最大回撤', '波动率'],
      axisLabel: { color: 'var(--text-muted)', fontSize: 10 },
      axisLine: { lineStyle: { color: 'var(--border-base)' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { 
        color: 'var(--text-muted)', 
        fontSize: 10,
        formatter: v => v.toFixed(1) + '%'
      },
      splitLine: { lineStyle: { color: 'var(--border-light)', type: 'dashed' } },
    },
    series: [{
      type: 'bar',
      data: [
        {
          value: data.total_return_pct,
          itemStyle: { color: data.total_return_pct >= 0 ? marketColors.UP : marketColors.DOWN },
        },
        {
          value: -data.max_drawdown_pct,
          itemStyle: { color: marketColors.DOWN },
        },
        {
          value: data.volatility_pct,
          itemStyle: { color: 'var(--color-warning)' },
        },
      ],
      barMaxWidth: 20,
    }],
  })
}

function getScoreClass(score) {
  if (score === null || score === undefined) return ''
  if (score >= 70) return 'factor-sandbox__score--high'
  if (score >= 40) return 'factor-sandbox__score--medium'
  return 'factor-sandbox__score--low'
}

onMounted(() => {
  fetchFactors()
})

onBeforeUnmount(() => {
  if (previewChart) {
    safeDispose(previewChart)
    previewChart = null
  }
})
</script>

<style scoped>
.factor-sandbox {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: var(--bg-base);
}

.factor-sandbox__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-sm) var(--space-md);
  background-color: var(--bg-surface);
  border-bottom: 1px solid var(--border-base);
}

.factor-sandbox__title {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.factor-sandbox__title-icon {
  font-size: 16px;
}

.factor-sandbox__actions {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.factor-sandbox__select {
  padding: var(--space-xs) var(--space-sm);
  font-size: 12px;
  color: var(--text-primary);
  background-color: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.factor-sandbox__select:focus {
  outline: none;
  border-color: var(--color-primary);
}

.factor-sandbox__btn {
  padding: var(--space-xs) var(--space-md);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-inverse);
  background-color: var(--color-primary);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--easing-default);
}

.factor-sandbox__btn:hover:not(:disabled) {
  background-color: var(--color-primary-hover);
}

.factor-sandbox__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.factor-sandbox__btn--loading {
  position: relative;
  padding-left: 24px;
}

.factor-sandbox__btn--loading::before {
  content: '';
  position: absolute;
  left: 8px;
  top: 50%;
  transform: translateY(-50%);
  width: 10px;
  height: 10px;
  border: 2px solid transparent;
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: translateY(-50%) rotate(360deg); }
}

.factor-sandbox__body {
  display: flex;
  flex: 1;
  min-height: 0;
  gap: var(--space-md);
  padding: var(--space-md);
}

.factor-sandbox__library {
  display: flex;
  flex-direction: column;
  width: 260px;
  flex-shrink: 0;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.factor-sandbox__library-header {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  background-color: var(--bg-surface-hover);
  border-bottom: 1px solid var(--border-base);
}

.factor-sandbox__library-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.factor-sandbox__search {
  width: 100%;
  padding: var(--space-xs) var(--space-sm);
  font-size: 11px;
  color: var(--text-primary);
  background-color: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
}

.factor-sandbox__search:focus {
  outline: none;
  border-color: var(--color-primary);
}

.factor-sandbox__search::placeholder {
  color: var(--text-placeholder);
}

.factor-sandbox__library-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-sm);
}

.factor-sandbox__category {
  margin-bottom: var(--space-md);
}

.factor-sandbox__category-header {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  margin-bottom: var(--space-sm);
  padding: 0 var(--space-xs);
}

.factor-sandbox__category-icon {
  font-size: 12px;
}

.factor-sandbox__category-name {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary);
}

.factor-sandbox__category-count {
  font-size: 10px;
  color: var(--text-muted);
  padding: 1px 6px;
  background-color: var(--bg-surface-hover);
  border-radius: var(--radius-full);
}

.factor-sandbox__category-factors {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.factor-sandbox__funnel {
  flex: 1;
  min-width: 0;
}

.factor-sandbox__results {
  display: flex;
  flex-direction: column;
  width: 320px;
  flex-shrink: 0;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.factor-sandbox__results-header {
  padding: var(--space-sm) var(--space-md);
  background-color: var(--bg-surface-hover);
  border-bottom: 1px solid var(--border-base);
}

.factor-sandbox__results-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.factor-sandbox__results-count {
  font-size: 11px;
  color: var(--text-muted);
  margin-left: var(--space-xs);
}

.factor-sandbox__error,
.factor-sandbox__loading,
.factor-sandbox__empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  color: var(--text-muted);
  font-size: 12px;
}

.factor-sandbox__error-icon,
.factor-sandbox__empty-icon {
  font-size: 24px;
  opacity: 0.5;
}

.factor-sandbox__loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--border-base);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.factor-sandbox__stock-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-sm);
}

.factor-sandbox__stock-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-sm);
  margin-bottom: var(--space-xs);
  background-color: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--easing-default);
}

.factor-sandbox__stock-item:hover {
  background-color: var(--bg-surface-hover);
  border-color: var(--border-hover);
}

.factor-sandbox__stock-item--selected {
  background-color: var(--color-primary-bg);
  border-color: var(--color-primary-border);
}

.factor-sandbox__stock-info {
  flex: 1;
  min-width: 0;
}

.factor-sandbox__stock-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.factor-sandbox__stock-symbol {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 2px;
}

.factor-sandbox__stock-score {
  text-align: right;
}

.factor-sandbox__score-value {
  font-size: 14px;
  font-weight: 600;
  font-family: var(--font-mono);
}

.factor-sandbox__score--high {
  color: var(--color-bull);
}

.factor-sandbox__score--medium {
  color: var(--color-warning);
}

.factor-sandbox__score--low {
  color: var(--color-bear);
}

.factor-sandbox__score-label {
  font-size: 9px;
  color: var(--text-muted);
  margin-top: 2px;
}

.factor-sandbox__preview {
  border-top: 1px solid var(--border-base);
  background-color: var(--bg-surface-hover);
}

.factor-sandbox__preview-header {
  padding: var(--space-sm) var(--space-md);
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-base);
}

.factor-sandbox__preview-chart {
  height: 120px;
}
</style>
