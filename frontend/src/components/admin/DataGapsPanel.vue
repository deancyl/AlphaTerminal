<template>
  <div class="space-y-6">
    <h2 class="text-lg font-bold text-theme-primary">📡 数据缺口雷达</h2>
    <p class="text-xs text-theme-muted">监控缺失的市场数据，一键回填补全</p>

    <div class="p-4 bg-[var(--info-bg)] border border-[var(--color-info-border)] rounded-sm">
      <h3 class="text-sm font-bold text-[var(--color-info)] mb-2">💡 这个功能是做什么的？</h3>
      <p class="text-xs text-theme-secondary leading-relaxed">
        扫描数据库中<strong class="text-terminal-accent">缺失的交易日数据</strong>，检测价格异常波动（&gt;20%），
        并支持从数据源一键回填补全。确保历史数据的完整性。
      </p>
    </div>

    <!-- 扫描控制面板 -->
    <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
      <h3 class="text-sm font-bold text-theme-primary mb-4">🔍 扫描设置</h3>
      
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div>
          <label class="block text-xs text-theme-muted mb-1">股票代码</label>
          <input
            v-model="symbol"
            type="text"
            placeholder="sh600519"
            class="w-full px-3 py-2 bg-theme-base border border-theme rounded-sm text-sm text-theme-primary focus:outline-none focus:border-terminal-accent"
          />
        </div>
        
        <div>
          <label class="block text-xs text-theme-muted mb-1">开始日期</label>
          <input
            v-model="startDate"
            type="date"
            class="w-full px-3 py-2 bg-theme-base border border-theme rounded-sm text-sm text-theme-primary focus:outline-none focus:border-terminal-accent"
          />
        </div>
        
        <div>
          <label class="block text-xs text-theme-muted mb-1">结束日期</label>
          <input
            v-model="endDate"
            type="date"
            class="w-full px-3 py-2 bg-theme-base border border-theme rounded-sm text-sm text-theme-primary focus:outline-none focus:border-terminal-accent"
          />
        </div>
        
        <div>
          <label class="block text-xs text-theme-muted mb-1">数据类型</label>
          <select
            v-model="dataType"
            class="w-full px-3 py-2 bg-theme-base border border-theme rounded-sm text-sm text-theme-primary focus:outline-none focus:border-terminal-accent"
          >
            <option value="kline">K线数据</option>
            <option value="macro">宏观数据</option>
            <option value="futures">期货数据</option>
          </select>
        </div>
      </div>
      
      <div class="mt-4 flex gap-3">
        <button
          class="px-4 py-2 bg-terminal-accent/20 text-terminal-accent rounded-sm text-sm disabled:opacity-50"
          :disabled="scanning || !symbol"
          @click="scanGaps"
        >
          {{ scanning ? '扫描中...' : '🔍 扫描缺口' }}
        </button>
        
        <button
          v-if="scanResult && scanResult.missing_dates?.length > 0"
          class="px-4 py-2 bg-[var(--color-success-bg)] text-[var(--color-success)] rounded-sm text-sm disabled:opacity-50"
          :disabled="backfilling"
          @click="backfillAll"
        >
          {{ backfilling ? '回填中...' : '📥 一键回填' }}
        </button>
      </div>
    </div>

    <!-- 扫描结果 -->
    <div v-if="scanResult" class="space-y-4">
      <!-- 统计卡片 -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
          <div class="text-[10px] text-theme-muted mb-1">扫描范围</div>
          <div class="text-xl font-bold text-terminal-accent">{{ scanResult.total_days }}</div>
          <div class="text-[10px] text-theme-muted">自然日</div>
        </div>
        
        <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
          <div class="text-[10px] text-theme-muted mb-1">交易日</div>
          <div class="text-xl font-bold text-terminal-accent">{{ scanResult.trading_days }}</div>
          <div class="text-[10px] text-theme-muted">天</div>
        </div>
        
        <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
          <div class="text-[10px] text-theme-muted mb-1">缺失数据</div>
          <div class="text-xl font-bold" :class="scanResult.missing_dates?.length > 0 ? 'text-[var(--color-warning)]' : 'text-[var(--color-success)]'">
            {{ scanResult.missing_dates?.length || 0 }}
          </div>
          <div class="text-[10px] text-theme-muted">天</div>
        </div>
        
        <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
          <div class="text-[10px] text-theme-muted mb-1">数据覆盖率</div>
          <div class="text-xl font-bold" :class="scanResult.coverage_pct >= 95 ? 'text-[var(--color-success)]' : 'text-[var(--color-warning)]'">
            {{ scanResult.coverage_pct }}%
          </div>
          <div class="text-[10px] text-theme-muted">完整度</div>
        </div>
      </div>

      <!-- 价格异常警告 -->
      <div v-if="scanResult.anomaly_dates?.length > 0" class="p-4 bg-[var(--color-warning-bg)] border border-[var(--color-warning-border)] rounded-sm">
        <h3 class="text-sm font-bold text-[var(--color-warning)] mb-3">⚠️ 价格异常波动 (变化 &gt; 20%)</h3>
        <div class="overflow-x-auto">
          <table class="theme-table w-full text-xs">
            <thead>
              <tr class="border-b border-theme">
                <th class="px-3 py-2 text-left text-theme-muted">日期</th>
                <th class="px-3 py-2 text-right text-theme-muted">涨跌幅</th>
                <th class="px-3 py-2 text-right text-theme-muted">收盘价</th>
                <th class="px-3 py-2 text-right text-theme-muted">成交量</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="anomaly in scanResult.anomaly_dates" :key="anomaly.date" class="border-b border-theme/50 hover:bg-theme-hover">
                <td class="px-3 py-2 text-theme-primary">{{ anomaly.date }}</td>
                <td class="px-3 py-2 text-right font-bold" :class="anomaly.change_pct > 0 ? 'text-bull' : 'text-bear'">
                  {{ anomaly.change_pct > 0 ? '+' : '' }}{{ anomaly.change_pct }}%
                </td>
                <td class="px-3 py-2 text-right text-theme-primary">{{ anomaly.close?.toFixed(2) }}</td>
                <td class="px-3 py-2 text-right text-theme-secondary">{{ formatVolume(anomaly.volume) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 缺失数据列表 -->
      <div v-if="scanResult.missing_dates?.length > 0" class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-bold text-theme-primary">📅 缺失数据日期</h3>
          <span class="text-xs text-theme-muted">共 {{ scanResult.missing_dates.length }} 天</span>
        </div>
        
        <div class="max-h-60 overflow-y-auto">
          <div class="grid grid-cols-4 md:grid-cols-7 gap-2">
            <div
              v-for="gap in scanResult.missing_dates"
              :key="gap.date"
              class="p-2 bg-theme-base border border-theme rounded text-center text-xs"
              :class="{ 'opacity-50': !gap.is_trading_day }"
            >
              <div class="text-theme-primary font-medium">{{ gap.date.slice(5) }}</div>
              <div class="text-theme-muted text-[10px]">{{ gap.weekday }}</div>
              <div v-if="gap.reason" class="text-[var(--color-warning)] text-[10px]">{{ gap.reason }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 无缺失提示 -->
      <div v-else class="p-4 bg-[var(--color-success-bg)] border border-[var(--color-success-border)] rounded-sm">
        <p class="text-sm text-[var(--color-success)]">✓ 数据完整，无缺失日期</p>
      </div>
    </div>

    <!-- 日历热力图 -->
    <div class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-sm font-bold text-theme-primary">📆 月度缺口热力图</h3>
        <div class="flex items-center gap-2">
          <button
            class="px-2 py-1 bg-theme-base border border-theme rounded text-xs text-theme-secondary hover:border-terminal-accent"
            @click="prevMonth"
          >
            ◀
          </button>
          <span class="text-sm text-theme-primary font-medium">{{ currentYear }}年{{ currentMonth }}月</span>
          <button
            class="px-2 py-1 bg-theme-base border border-theme rounded text-xs text-theme-secondary hover:border-terminal-accent"
            @click="nextMonth"
          >
            ▶
          </button>
        </div>
      </div>
      
      <div ref="calendarChartRef" class="h-64"></div>
    </div>

    <!-- 回填结果 -->
    <div v-if="backfillResult" class="p-4 bg-theme-secondary/20 rounded-sm border border-theme">
      <h3 class="text-sm font-bold text-theme-primary mb-3">📥 回填结果</h3>
      <div class="grid grid-cols-3 gap-4 mb-4">
        <div class="text-center">
          <div class="text-xl font-bold text-terminal-accent">{{ backfillResult.success_count }}</div>
          <div class="text-xs text-theme-muted">成功</div>
        </div>
        <div class="text-center">
          <div class="text-xl font-bold text-[var(--color-danger)]">{{ backfillResult.failed_count }}</div>
          <div class="text-xs text-theme-muted">失败</div>
        </div>
        <div class="text-center">
          <div class="text-xl font-bold text-theme-secondary">{{ backfillResult.total_requested }}</div>
          <div class="text-xs text-theme-muted">总计</div>
        </div>
      </div>
      
      <div v-if="backfillResult.failed_dates?.length > 0" class="text-xs text-theme-muted">
        <span class="text-[var(--color-warning)]">失败日期：</span>
        {{ backfillResult.failed_dates.join(', ') }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, onDeactivated, onActivated, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { apiFetch } from '@/utils/api.js'
import { toast } from '@/composables/useToast.js'

const symbol = ref('sh600519')
const startDate = ref('')
const endDate = ref('')
const dataType = ref('kline')

const scanning = ref(false)
const backfilling = ref(false)
const scanResult = ref(null)
const backfillResult = ref(null)

const currentYear = ref(new Date().getFullYear())
const currentMonth = ref(new Date().getMonth() + 1)
const calendarChartRef = ref(null)
let calendarChart = null

function initDates() {
  const now = new Date()
  endDate.value = now.toISOString().slice(0, 10)
  const yearAgo = new Date(now.getFullYear() - 1, now.getMonth(), now.getDate())
  startDate.value = yearAgo.toISOString().slice(0, 10)
}

async function scanGaps() {
  if (!symbol.value) {
    toast.warning('请输入股票代码')
    return
  }
  
  scanning.value = true
  scanResult.value = null
  backfillResult.value = null
  
  try {
    const res = await apiFetch(`/api/v1/data_gaps/scan?symbol=${symbol.value}&start_date=${startDate.value}&end_date=${endDate.value}&data_type=${dataType.value}`, {
      timeoutMs: 30000
    })
    
    if (res.code === 0) {
      scanResult.value = res.data
      if (res.data.missing_dates?.length === 0) {
        toast.success('数据完整，无缺失')
      } else {
        toast.info(`发现 ${res.data.missing_dates.length} 天缺失数据`)
      }
    } else {
      toast.error(res.message || '扫描失败')
    }
  } catch (e) {
    toast.error('扫描失败: ' + e.message)
  } finally {
    scanning.value = false
  }
}

async function backfillAll() {
  if (!scanResult.value?.missing_dates?.length) return
  
  backfilling.value = true
  backfillResult.value = null
  
  const dates = scanResult.value.missing_dates.map(g => g.date)
  
  try {
    const res = await apiFetch('/api/v1/data_gaps/backfill', {
      method: 'POST',
      body: JSON.stringify({
        symbol: symbol.value,
        dates: dates,
        data_type: dataType.value
      }),
      timeoutMs: 60000
    })
    
    if (res.code === 0) {
      backfillResult.value = res.data
      if (res.data.success_count > 0) {
        toast.success(`成功回填 ${res.data.success_count} 天数据`)
        await scanGaps()
      } else {
        toast.warning('回填失败，请检查网络连接')
      }
    } else {
      toast.error(res.message || '回填失败')
    }
  } catch (e) {
    toast.error('回填失败: ' + e.message)
  } finally {
    backfilling.value = false
  }
}

function formatVolume(vol) {
  if (!vol) return '-'
  if (vol >= 1e8) return (vol / 1e8).toFixed(2) + '亿'
  if (vol >= 1e4) return (vol / 1e4).toFixed(2) + '万'
  return vol.toString()
}

function prevMonth() {
  if (currentMonth.value === 1) {
    currentMonth.value = 12
    currentYear.value--
  } else {
    currentMonth.value--
  }
}

function nextMonth() {
  if (currentMonth.value === 12) {
    currentMonth.value = 1
    currentYear.value++
  } else {
    currentMonth.value++
  }
}

async function loadCalendarData() {
  try {
    const res = await apiFetch(`/api/v1/data_gaps/calendar?year=${currentYear.value}&month=${currentMonth.value}`, {
      timeoutMs: 15000
    })
    
    if (res.code === 0) {
      renderCalendarChart(res.data)
    }
  } catch (e) {
    console.error('Failed to load calendar data:', e)
  }
}

function renderCalendarChart(data) {
  if (!calendarChartRef.value) return
  
  if (!calendarChart) {
    calendarChart = echarts.init(calendarChartRef.value)
  }
  
  const calendarData = (data.calendar || []).map(d => [d.date, d.gap_count])
  
  const option = {
    tooltip: {
      formatter: function(params) {
        return `${params.value[0]}<br/>缺口: ${params.value[1]} 只股票`
      }
    },
    visualMap: {
      min: 0,
      max: Math.max(10, data.total_stocks || 10),
      type: 'piecewise',
      orient: 'horizontal',
      left: 'center',
      top: 0,
      inRange: {
        color: ['#22c55e', '#fbbf24', '#ef4444']
      },
      textStyle: {
        color: '#9ca3af'
      }
    },
    calendar: {
      top: 60,
      left: 30,
      right: 30,
      cellSize: ['auto', 20],
      range: `${currentYear.value}-${String(currentMonth.value).padStart(2, '0')}`,
      itemStyle: {
        borderWidth: 0.5,
        borderColor: '#374151'
      },
      yearLabel: { show: false },
      monthLabel: { show: true, color: '#9ca3af' },
      dayLabel: {
        firstDay: 1,
        color: '#9ca3af',
        nameMap: ['日', '一', '二', '三', '四', '五', '六']
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: '#374151',
          width: 1
        }
      }
    },
    series: [{
      type: 'heatmap',
      coordinateSystem: 'calendar',
      data: calendarData
    }]
  }
  
  calendarChart.setOption(option, true)
}

watch([currentYear, currentMonth], () => {
  loadCalendarData()
})

onMounted(() => {
  initDates()
  nextTick(() => {
    loadCalendarData()
  })
})

// P0: KeepAlive cleanup
onBeforeUnmount(() => {
  if (calendarChart) {
    calendarChart.dispose()
    calendarChart = null
  }
})

onDeactivated(() => {
  // Clear chart to free memory
  if (calendarChart) {
    calendarChart.clear()
  }
})

onActivated(() => {
  // Re-render chart if container exists
  if (calendarChartRef.value) {
    nextTick(() => loadCalendarData())
  }
})
</script>
