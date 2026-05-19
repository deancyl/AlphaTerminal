<template>
  <div class="factor-sandbox" :class="{ 'factor-sandbox--mobile': isMobile }">
    <!-- Desktop Header -->
    <div v-if="!isMobile" class="factor-sandbox__header">
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
          aria-label="开始筛选股票"
        >
          {{ screeningLoading ? '筛选中...' : '开始筛选' }}
        </button>
      </div>
    </div>

    <!-- Mobile Header with Tab Navigation -->
    <div v-else class="factor-sandbox__mobile-header">
      <div class="factor-sandbox__mobile-title">
        <span class="factor-sandbox__title-icon">🎯</span>
        <span>因子筛选</span>
      </div>
      <div class="factor-sandbox__mobile-tabs">
        <button
          class="factor-sandbox__mobile-tab"
          :class="{ 'factor-sandbox__mobile-tab--active': activeMobileTab === 'funnel' }"
          @click="activeMobileTab = 'funnel'"
        >
          漏斗
          <span v-if="selectedFactors.length > 0" class="factor-sandbox__tab-badge">{{ selectedFactors.length }}</span>
        </button>
        <button
          class="factor-sandbox__mobile-tab"
          :class="{ 'factor-sandbox__mobile-tab--active': activeMobileTab === 'library' }"
          @click="activeMobileTab = 'library'"
        >
          因子库
        </button>
        <button
          class="factor-sandbox__mobile-tab"
          :class="{ 'factor-sandbox__mobile-tab--active': activeMobileTab === 'results' }"
          @click="activeMobileTab = 'results'"
        >
          结果
          <span v-if="screenedStocks.length > 0" class="factor-sandbox__tab-badge">{{ screenedStocks.length }}</span>
        </button>
      </div>
      <div class="factor-sandbox__mobile-actions">
        <select
          v-model="universe"
          class="factor-sandbox__select factor-sandbox__select--mobile"
        >
          <option value="all">全市场</option>
          <option value="hs300">沪深300</option>
          <option value="zz500">中证500</option>
          <option value="cyb50">创业板50</option>
        </select>
        <button
          @click="handleScreen"
          :disabled="selectedFactors.length === 0 || screeningLoading"
          class="factor-sandbox__btn factor-sandbox__btn--mobile"
          :class="{ 'factor-sandbox__btn--loading': screeningLoading }"
          aria-label="开始筛选股票"
        >
          {{ screeningLoading ? '筛选中...' : '筛选' }}
        </button>
      </div>
    </div>

    <!-- Desktop: 3-column layout -->
    <div v-if="!isMobile" class="factor-sandbox__body">
      <div class="factor-sandbox__library">
        <div class="factor-sandbox__library-header">
          <span class="factor-sandbox__library-title">因子库</span>
          <input
            v-model="factorSearch"
            type="text"
            placeholder="搜索因子..."
            class="factor-sandbox__search"
            aria-label="搜索因子"
          />
        </div>
        <div class="factor-sandbox__library-content" role="listbox" aria-label="因子列表">
          <!-- Skeleton loading state -->
          <div v-if="factorsLoading" class="factor-sandbox__loading-state">
            <Skeleton v-for="i in 6" :key="i" class="factor-sandbox__skeleton" />
          </div>
          <!-- Factor categories -->
          <template v-else>
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
                  @touchdrop="addFactor"
                />
              </div>
            </div>
          </template>
        </div>
      </div>

      <div class="factor-sandbox__funnel">
        <FactorFunnel
          :factors="selectedFactors"
          @remove="removeFactor"
          @reorder="reorderFactors"
          @add="addFactor"
          @configure="openParamModal"
        />
      </div>

      <div class="factor-sandbox__results">
        <div class="factor-sandbox__results-header">
          <span class="factor-sandbox__results-title">
            筛选结果
            <span v-if="screenedStocks.length > 0" class="factor-sandbox__results-count" aria-live="polite">
              ({{ screenedStocks.length }})
            </span>
          </span>
          <span v-if="screeningProgress" class="factor-sandbox__progress-info" aria-live="polite">
            已筛选 {{ screeningProgress.screened_stocks }}/{{ screeningProgress.total_stocks }}
          </span>
        </div>
        
        <div v-if="error" class="factor-sandbox__error">
          <span class="factor-sandbox__error-icon">⚠️</span>
          <span>筛选失败，请检查因子参数或稍后重试</span>
          <button @click="handleScreen" class="ml-2 px-2 py-1 text-xs bg-primary text-white rounded">
            重试
          </button>
        </div>
        
        <div v-else-if="screeningLoading" class="factor-sandbox__loading">
          <div class="factor-sandbox__loading-spinner"></div>
          <span>正在筛选 {{ universe === 'all' ? '全市场' : universe }}...</span>
          
          <!-- Progress bar -->
          <div v-if="screeningProgress && screeningProgress.total_stocks > 0" class="factor-sandbox__progress-bar-container">
            <div class="factor-sandbox__progress-bar">
              <div 
                class="factor-sandbox__progress-fill" 
                :style="{ width: progressPercent + '%' }"
              ></div>
            </div>
            <span class="factor-sandbox__progress-text">
              {{ screeningProgress.screened_stocks }} / {{ screeningProgress.total_stocks }}
              ({{ progressPercent.toFixed(0) }}%)
            </span>
          </div>
          
          <button @click="cancelScreening" class="factor-sandbox__cancel-btn" aria-label="取消筛选">
            取消
          </button>
        </div>
        
        <div v-else-if="screenedStocks.length === 0" class="factor-sandbox__empty">
          <span class="factor-sandbox__empty-icon">📊</span>
          <span>拖拽左侧因子到筛选漏斗，或点击因子卡片快速添加。组合多个因子可提高筛选准确度</span>
        </div>
        
        <div v-else class="factor-sandbox__stock-list">
          <VirtualizedTable
            :items="stockTableItems"
            :columns="stockColumns"
            :selected-id="selectedStock?.symbol"
            item-size="56"
            @row-click="({ item }) => selectStock(screenedStocks.find(s => s.symbol === item.id))"
          >
            <template #cell-name="{ item }">
              <span class="factor-sandbox__stock-name">{{ item.name }}</span>
            </template>
            <template #cell-score="{ item }">
              <span class="factor-sandbox__score-value" :class="getScoreClass(item.score)">
                {{ item.score?.toFixed(2) ?? 'N/A' }}
              </span>
            </template>
          </VirtualizedTable>
        </div>

        <div v-if="selectedStock" class="factor-sandbox__preview">
          <div class="factor-sandbox__preview-header">
            <span>回测预览: {{ selectedStock.name || selectedStock.symbol }}</span>
          </div>
          <div ref="previewChartRef" class="factor-sandbox__preview-chart"></div>
        </div>
      </div>
    </div>

    <!-- Mobile: Single column with tab switching -->
    <div v-else class="factor-sandbox__mobile-body">
      <!-- Mobile: Funnel View (default) -->
      <div v-show="activeMobileTab === 'funnel'" class="factor-sandbox__mobile-funnel">
        <FactorFunnel
          :factors="selectedFactors"
          @remove="removeFactor"
          @reorder="reorderFactors"
          @add="addFactor"
          @configure="openParamModal"
        />
        <div v-if="selectedFactors.length === 0" class="factor-sandbox__mobile-empty">
          <span class="factor-sandbox__empty-icon">📊</span>
          <span>点击"因子库"添加因子</span>
        </div>
      </div>

      <!-- Mobile: Factor Library View -->
      <div v-show="activeMobileTab === 'library'" class="factor-sandbox__mobile-library">
        <div class="factor-sandbox__library-header">
          <input
            v-model="factorSearch"
            type="text"
            placeholder="搜索因子..."
            class="factor-sandbox__search factor-sandbox__search--mobile"
            aria-label="搜索因子"
          />
        </div>
        <div class="factor-sandbox__library-content" role="listbox" aria-label="因子列表">
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
                @touchdrop="addFactor"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- Mobile: Results View -->
      <div v-show="activeMobileTab === 'results'" class="factor-sandbox__mobile-results">
        <div v-if="error" class="factor-sandbox__error">
          <span class="factor-sandbox__error-icon">⚠️</span>
          <span>筛选失败，请检查因子参数或稍后重试</span>
          <button @click="handleScreen" class="ml-2 px-2 py-1 text-xs bg-primary text-white rounded">
            重试
          </button>
        </div>
        
        <div v-else-if="screeningLoading" class="factor-sandbox__loading">
          <div class="factor-sandbox__loading-spinner"></div>
          <span>正在筛选...</span>
          
          <!-- Progress bar for mobile -->
          <div v-if="screeningProgress && screeningProgress.total_stocks > 0" class="factor-sandbox__progress-bar-container">
            <div class="factor-sandbox__progress-bar">
              <div 
                class="factor-sandbox__progress-fill" 
                :style="{ width: progressPercent + '%' }"
              ></div>
            </div>
            <span class="factor-sandbox__progress-text">
              {{ screeningProgress.screened_stocks }} / {{ screeningProgress.total_stocks }}
            </span>
          </div>
        </div>
        
        <div v-else-if="screenedStocks.length === 0" class="factor-sandbox__empty">
          <span class="factor-sandbox__empty-icon">📊</span>
          <span>拖拽左侧因子到筛选漏斗，或点击因子卡片快速添加。组合多个因子可提高筛选准确度</span>
        </div>
        
        <div v-else class="factor-sandbox__stock-list">
          <VirtualizedTable
            :items="stockTableItems"
            :columns="stockColumns"
            :selected-id="selectedStock?.symbol"
            item-size="60"
            row-class="factor-sandbox__stock-item--mobile"
            @row-click="({ item }) => selectStock(screenedStocks.find(s => s.symbol === item.id))"
          >
            <template #cell-name="{ item }">
              <span class="factor-sandbox__stock-name">{{ item.name }}</span>
            </template>
            <template #cell-score="{ item }">
              <span class="factor-sandbox__score-value" :class="getScoreClass(item.score)">
                {{ item.score?.toFixed(2) ?? 'N/A' }}
              </span>
            </template>
          </VirtualizedTable>
        </div>

        <!-- Mobile: Preview in BottomSheet -->
        <BottomSheet
          v-if="selectedStock"
          :model-value="!!selectedStock"
          @update:model-value="selectedStock = null"
          title="回测预览"
        >
          <div class="factor-sandbox__preview factor-sandbox__preview--mobile">
            <div class="factor-sandbox__preview-header">
              <span>{{ selectedStock.name || selectedStock.symbol }}</span>
            </div>
            <div ref="previewChartRef" class="factor-sandbox__preview-chart factor-sandbox__preview-chart--mobile"></div>
          </div>
        </BottomSheet>
      </div>
    </div>
    
    <!-- Parameter Configuration Modal -->
    <FactorParamModal
      :show="showParamModal"
      :factor="configuringFactor"
      @close="closeParamModal"
      @apply="applyFactorParams"
    />
  </div>
</template>

<script setup>
import { ref, shallowRef, computed, onMounted, onBeforeUnmount, onDeactivated, nextTick, watch } from 'vue'
import { useBreakpoints, breakpointsTailwind } from '@vueuse/core'
import { useFactorSandbox } from '@/composables/useFactorSandbox.js'
import { safeDispose } from '@/utils/chartManager.js'
import { getDynamicMarketColors } from '@/utils/echartsTheme.js'
import FactorDragItem from './FactorDragItem.vue'
import FactorFunnel from './FactorFunnel.vue'
import FactorParamModal from './FactorParamModal.vue'
import BottomSheet from '@/components/BottomSheet.vue'
import Skeleton from '@/components/Skeleton.vue'

const breakpoints = useBreakpoints(breakpointsTailwind)
const isMobile = breakpoints.smaller('md')

const showFactorLibrary = ref(false)
const showResultsPanel = ref(false)
const activeMobileTab = ref('funnel')

const {
  factors,
  categories,
  selectedFactors,
  screenedStocks,
  screeningLoading,
  factorsLoading,
  error,
  screeningProgress,
  universe,
  isFactorSelected,
  fetchFactors,
  addFactor,
  removeFactor,
  toggleFactor,
  reorderFactors,
  updateFactorParams,
  runScreening,
  cancelScreening,
  getBacktestPreview,
} = useFactorSandbox()

const factorSearch = ref('')
const selectedStock = ref(null)
const previewChartRef = ref(null)
const previewChart = shallowRef(null)
const showParamModal = ref(false)
const configuringFactor = ref(null)

// VirtualizedTable columns for stock list
const stockColumns = [
  { key: 'symbol', label: '代码', width: '80px', sortable: true },
  { key: 'name', label: '名称', width: '120px' },
  { key: 'score', label: '综合得分', width: '100px', align: 'right', sortable: true, format: 'score' },
]

// Prepare items for VirtualizedTable (requires id field)
const stockTableItems = computed(() => {
  return screenedStocks.value.map(stock => ({
    id: stock.symbol,
    symbol: stock.symbol,
    name: stock.name || stock.symbol,
    score: stock.score,
  }))
})

const filteredCategories = computed(() => {
  if (!factorSearch.value) return categories.value
  return categories.value.filter(cat => {
    const catFactors = getFactorsByCategory(cat.id)
    return catFactors.some(f => 
      f.name.toLowerCase().includes(factorSearch.value.toLowerCase())
    )
  })
})

const progressPercent = computed(() => {
  if (!screeningProgress.value || screeningProgress.value.total_stocks === 0) return 0
  return (screeningProgress.value.screened_stocks / screeningProgress.value.total_stocks) * 100
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

function cleanupPreviewChart() {
  if (previewChart.value) {
    safeDispose(previewChart.value)
    previewChart.value = null
  }
}

async function loadBacktestPreview() {
  if (!selectedStock.value) return
  
  cleanupPreviewChart()
  
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
  
  cleanupPreviewChart()
  
  const marketColors = getDynamicMarketColors()
  
  previewChart.value = window.echarts.init(previewChartRef.value, 'dark')
  previewChart.value.setOption({
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

function openParamModal(factor) {
  configuringFactor.value = factor
  showParamModal.value = true
}

function closeParamModal() {
  showParamModal.value = false
  configuringFactor.value = null
}

function applyFactorParams({ factorId, params }) {
  updateFactorParams(factorId, params)
  closeParamModal()
}

onMounted(() => {
  fetchFactors()
})

onBeforeUnmount(() => {
  cleanupPreviewChart()
})

onDeactivated(() => {
  cleanupPreviewChart()
})

watch(selectedStock, (newStock, oldStock) => {
  if (oldStock && newStock?.symbol !== oldStock?.symbol) {
    cleanupPreviewChart()
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

.factor-sandbox__loading-state {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.factor-sandbox__skeleton {
  height: 48px;
  border-radius: var(--radius-sm);
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
  display: flex;
  justify-content: space-between;
  align-items: center;
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

.factor-sandbox__progress-info {
  font-size: 10px;
  color: var(--text-muted);
  padding: 2px 6px;
  background-color: var(--bg-surface);
  border-radius: var(--radius-sm);
}

.factor-sandbox__loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  color: var(--text-muted);
  font-size: 12px;
}

.factor-sandbox__loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--border-base);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.factor-sandbox__progress-bar-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-xs);
  width: 100%;
  max-width: 200px;
}

.factor-sandbox__progress-bar {
  width: 100%;
  height: 6px;
  background-color: var(--bg-surface-hover);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.factor-sandbox__progress-fill {
  height: 100%;
  background-color: var(--color-primary);
  border-radius: var(--radius-full);
  transition: width 0.3s ease;
}

.factor-sandbox__progress-text {
  font-size: 10px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.factor-sandbox__cancel-btn {
  padding: var(--space-xs) var(--space-sm);
  font-size: 11px;
  color: var(--color-danger);
  background-color: var(--color-danger-bg);
  border: 1px solid var(--color-danger-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--easing-default);
}

.factor-sandbox__cancel-btn:hover {
  background-color: var(--color-danger);
  color: var(--text-inverse);
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

/* Mobile-specific styles */
.factor-sandbox--mobile {
  padding-bottom: env(safe-area-inset-bottom, 0);
}

.factor-sandbox__mobile-header {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  padding: var(--space-sm);
  background-color: var(--bg-surface);
  border-bottom: 1px solid var(--border-base);
}

.factor-sandbox__mobile-title {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.factor-sandbox__mobile-tabs {
  display: flex;
  gap: var(--space-xs);
  background-color: var(--bg-surface-hover);
  border-radius: var(--radius-md);
  padding: 4px;
}

.factor-sandbox__mobile-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-xs);
  min-height: 44px;
  padding: var(--space-xs) var(--space-sm);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  background-color: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--easing-default);
}

.factor-sandbox__mobile-tab--active {
  color: var(--color-primary);
  background-color: var(--bg-surface);
}

.factor-sandbox__tab-badge {
  font-size: 10px;
  padding: 1px 5px;
  background-color: var(--color-primary);
  color: var(--text-inverse);
  border-radius: var(--radius-full);
}

.factor-sandbox__mobile-actions {
  display: flex;
  gap: var(--space-sm);
}

.factor-sandbox__select--mobile {
  flex: 1;
  min-height: 44px;
}

.factor-sandbox__btn--mobile {
  flex: 1;
  min-height: 44px;
  font-size: 14px;
}

.factor-sandbox__mobile-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.factor-sandbox__mobile-funnel,
.factor-sandbox__mobile-library,
.factor-sandbox__mobile-results {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.factor-sandbox__mobile-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  color: var(--text-muted);
  font-size: 14px;
  padding: var(--space-lg);
}

.factor-sandbox__mobile-library {
  background-color: var(--bg-surface);
}

.factor-sandbox__search--mobile {
  min-height: 44px;
  font-size: 14px;
}

.factor-sandbox__mobile-results {
  background-color: var(--bg-surface);
}

.factor-sandbox__stock-item--mobile {
  min-height: 60px;
}

.factor-sandbox__preview--mobile {
  padding: var(--space-md);
}

.factor-sandbox__preview-chart--mobile {
  height: 200px;
}
</style>
