<template>
  <div class="space-y-4">
    <h2 class="text-lg font-bold text-terminal-accent">财务摘要</h2>

    <LoadingSpinner v-if="loading" text="加载财务数据..." />

    <ErrorDisplay
      v-else-if="error"
      :error="error"
      :retry="onRetry"
    />

    <div v-else-if="data && data.latest" class="space-y-4">
      <!-- 关键指标卡片 -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <InfoCard
          title="ROE (净资产收益率)"
          :value="data.latest['净资产收益率(%)']"
          unit="%"
          format="number"
        />
        <InfoCard
          title="EPS (每股收益)"
          :value="data.latest['摊薄每股收益(元)']"
          unit="元"
          format="number"
        />
        <InfoCard
          title="营收增长率"
          :value="data.latest['主营业务收入增长率(%)']"
          unit="%"
          format="number"
        />
        <InfoCard
          title="净利润增长率"
          :value="data.latest['净利润增长率(%)']"
          unit="%"
          format="number"
        />
      </div>

      <!-- 趋势图表 -->
      <div v-if="data.trend && data.trend.length > 0" class="space-y-3">
        <h3 class="text-sm font-bold text-terminal-primary">关键指标趋势（近8个季度）</h3>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3">
            <TrendChart
              :data="getTrendChartData('摊薄每股收益(元)')"
              title="每股收益 (EPS)"
              type="line"
            />
          </div>
          <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3">
            <TrendChart
              :data="getTrendChartData('净资产收益率(%)')"
              title="ROE (%)"
              type="line"
            />
          </div>
          <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3">
            <TrendChart
              :data="getTrendChartData('主营业务收入增长率(%)')"
              title="营收增长率 (%)"
              type="bar"
            />
          </div>
          <div class="bg-terminal-panel rounded-lg border border-theme-secondary p-3">
            <TrendChart
              :data="getTrendChartData('净利润增长率(%)')"
              title="净利润增长率 (%)"
              type="bar"
            />
          </div>
        </div>
      </div>

      <!-- 完整指标表格 -->
      <div>
        <h3 class="text-sm font-bold text-terminal-primary mb-3">完整财务指标</h3>
        <DataTable
          :columns="tableColumns"
          :data="data.indicators"
        />
      </div>
    </div>

    <div v-else class="text-center py-8 text-terminal-dim">
      请输入股票代码查询财务数据
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import LoadingSpinner from '../f9/LoadingSpinner.vue'
import ErrorDisplay from '../f9/ErrorDisplay.vue'
import InfoCard from '../f9/InfoCard.vue'
import DataTable from '../f9/DataTable.vue'
import TrendChart from '../f9/TrendChart.vue'

const props = defineProps({
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' }
})

const emit = defineEmits(['retry'])

const tableColumns = [
  { key: '日期', label: '日期', format: 'date' },
  { key: '摊薄每股收益(元)', label: '每股收益', format: 'number' },
  { key: '净资产收益率(%)', label: 'ROE', format: 'percentage' },
  { key: '销售毛利率(%)', label: '毛利率', format: 'percentage' },
  { key: '销售净利率(%)', label: '净利率', format: 'percentage' },
  { key: '主营业务收入增长率(%)', label: '营收增长', format: 'percentage' },
  { key: '净利润增长率(%)', label: '利润增长', format: 'percentage' },
  { key: '每股净资产_调整后(元)', label: '每股净资产', format: 'number' },
  { key: '流动比率', label: '流动比率', format: 'number' },
  { key: '资产负债率(%)', label: '资产负债率', format: 'percentage' }
]

function getTrendChartData(metric) {
  if (!props.data || !props.data.trend) return []
  return props.data.trend
    .filter(item => item[metric] != null)
    .reverse()
    .map(item => ({
      date: item['日期'] || '',
      value: item[metric]
    }))
}

function onRetry() {
  emit('retry')
}
</script>
