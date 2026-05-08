<template>
  <div class="flex flex-col w-full h-full overflow-hidden bg-terminal-panel">
    
    <div class="shrink-0 border-b border-theme p-3">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-sm font-bold text-theme-primary">🔄 Walk-Forward 分析</h2>
        <div class="flex items-center gap-2">
          <span class="text-[10px] text-theme-muted">模式:</span>
          <select v-model="mode" class="bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-[10px] text-theme-primary">
            <option value="rolling">滚动窗口</option>
            <option value="anchored">锚定窗口</option>
          </select>
        </div>
      </div>
      
      <div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-[10px]">
        <div class="flex flex-col">
          <span class="text-theme-muted mb-1">标的</span>
          <input v-model="symbol" type="text" 
            class="bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-theme-primary"
            placeholder="sh600519" />
        </div>
        <div class="flex flex-col">
          <span class="text-theme-muted mb-1">策略</span>
          <select v-model="strategyType" 
            class="bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-theme-primary">
            <option value="ma_crossover">双均线</option>
            <option value="rsi_oversold">RSI超卖</option>
            <option value="bollinger_bands">布林带</option>
          </select>
        </div>
        <div class="flex flex-col">
          <span class="text-theme-muted mb-1">训练窗口</span>
          <input v-model.number="trainWindowDays" type="number" 
            class="bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-theme-primary" />
        </div>
        <div class="flex flex-col">
          <span class="text-theme-muted mb-1">测试窗口</span>
          <input v-model.number="testWindowDays" type="number" 
            class="bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-theme-primary" />
        </div>
      </div>
      
      <div class="flex items-center justify-between mt-3">
        <div class="flex items-center gap-2 text-[10px]">
          <span class="text-theme-muted">时间范围:</span>
          <select v-model="windowPreset" class="bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-theme-primary">
            <option value="1y">近1年</option>
            <option value="2y">近2年</option>
            <option value="3y">近3年</option>
            <option value="5y">近5年</option>
          </select>
        </div>
        <button @click="runAnalysis" :disabled="running"
          class="px-4 py-1.5 rounded text-[11px] font-medium transition-colors"
          :class="running 
            ? 'bg-[var(--color-neutral-bg)] text-theme-muted cursor-not-allowed' 
            : 'bg-[var(--color-info-bg)] text-[var(--color-info)] hover:bg-[var(--color-info-hover)]/30 border border-[var(--color-info-border)]'">
          {{ running ? '⏳ 分析中...' : '▶ 开始分析' }}
        </button>
      </div>
    </div>
    
    <div v-if="error" class="shrink-0 border-b border-theme bg-[var(--color-danger-bg)]/20 p-3">
      <div class="text-[11px] text-[var(--color-danger)]">❌ {{ error }}</div>
    </div>
    
    <div v-if="result" class="flex-1 overflow-y-auto p-3">
      
      <div class="mb-4 p-3 rounded border border-theme bg-terminal-bg">
        <div class="text-[11px] font-bold text-theme-primary mb-2">📊 核心指标</div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div class="flex flex-col">
            <span class="text-[10px] text-theme-muted">样本外平均收益</span>
            <span class="text-sm font-mono font-bold" 
              :class="result.avg_test_return_pct >= 0 ? 'text-bullish' : 'text-bearish'">
              {{ result.avg_test_return_pct >= 0 ? '+' : '' }}{{ result.avg_test_return_pct.toFixed(2) }}%
            </span>
          </div>
          <div class="flex flex-col">
            <span class="text-[10px] text-theme-muted">样本外夏普</span>
            <span class="text-sm font-mono" 
              :class="result.avg_test_sharpe >= 1 ? 'text-bullish' : 'text-theme-muted'">
              {{ result.avg_test_sharpe.toFixed(2) }}
            </span>
          </div>
          <div class="flex flex-col">
            <span class="text-[10px] text-theme-muted">过拟合程度</span>
            <span class="text-sm font-mono font-bold" :class="overfittingClass">
              {{ overfittingText }}
            </span>
          </div>
          <div class="flex flex-col">
            <span class="text-[10px] text-theme-muted">一致性得分</span>
            <span class="text-sm font-mono" 
              :class="result.consistency_score >= 70 ? 'text-bullish' : 'text-[var(--color-warning)]'">
              {{ result.consistency_score.toFixed(1) }}
            </span>
          </div>
        </div>
      </div>
      
      <div class="mb-4 p-3 rounded border border-theme bg-terminal-bg">
        <div class="text-[11px] font-bold text-theme-primary mb-2">🎯 过拟合分析</div>
        <div class="grid grid-cols-3 gap-3 text-[10px]">
          <div class="flex flex-col">
            <span class="text-theme-muted">训练-测试收益差</span>
            <span class="font-mono" :class="result.avg_return_gap > 10 ? 'text-[var(--color-danger)]' : 'text-theme-primary'">
              {{ result.avg_return_gap.toFixed(2) }}%
            </span>
          </div>
          <div class="flex flex-col">
            <span class="text-theme-muted">过拟合窗口数</span>
            <span class="font-mono">
              {{ result.overfitting_windows }} / {{ result.total_windows }}
              <span class="text-theme-muted">({{ (result.overfitting_ratio * 100).toFixed(0) }}%)</span>
            </span>
          </div>
          <div class="flex flex-col">
            <span class="text-theme-muted">置信度</span>
            <span class="font-mono" :class="confidenceClass">{{ confidenceText }}</span>
          </div>
        </div>
      </div>
      
      <div class="mb-4 p-3 rounded border border-theme bg-terminal-bg">
        <div class="text-[11px] font-bold text-theme-primary mb-2">💡 建议</div>
        <div class="text-[10px] text-theme-secondary leading-relaxed">
          {{ result.recommendation }}
        </div>
      </div>
      
      <div class="border border-theme rounded overflow-hidden">
        <div class="p-2 bg-terminal-bg border-b border-theme">
          <div class="text-[11px] font-bold text-theme-primary">📈 窗口详情</div>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-[10px] min-w-[800px]">
            <thead class="bg-terminal-bg sticky top-0">
              <tr class="border-b border-theme">
                <th class="px-2 py-1.5 text-left text-theme-muted">窗口</th>
                <th class="px-2 py-1.5 text-left text-theme-muted">训练期</th>
                <th class="px-2 py-1.5 text-right text-theme-muted">训练收益</th>
                <th class="px-2 py-1.5 text-left text-theme-muted">测试期</th>
                <th class="px-2 py-1.5 text-right text-theme-muted">测试收益</th>
                <th class="px-2 py-1.5 text-right text-theme-muted">收益差</th>
                <th class="px-2 py-1.5 text-center text-theme-muted">过拟合</th>
                <th class="px-2 py-1.5 text-left text-theme-muted">最优参数</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="w in result.windows" :key="w.window_index"
                class="border-b border-theme/30 hover:bg-theme-tertiary/10">
                <td class="px-2 py-1.5 font-mono text-theme-secondary">{{ w.window_index + 1 }}</td>
                <td class="px-2 py-1.5 text-theme-secondary">
                  {{ w.train_start }} ~ {{ w.train_end }}
                </td>
                <td class="px-2 py-1.5 text-right font-mono"
                  :class="w.train_return_pct >= 0 ? 'text-bullish' : 'text-bearish'">
                  {{ w.train_return_pct >= 0 ? '+' : '' }}{{ w.train_return_pct.toFixed(2) }}%
                </td>
                <td class="px-2 py-1.5 text-theme-secondary">
                  {{ w.test_start }} ~ {{ w.test_end }}
                </td>
                <td class="px-2 py-1.5 text-right font-mono"
                  :class="w.test_return_pct >= 0 ? 'text-bullish' : 'text-bearish'">
                  {{ w.test_return_pct >= 0 ? '+' : '' }}{{ w.test_return_pct.toFixed(2) }}%
                </td>
                <td class="px-2 py-1.5 text-right font-mono"
                  :class="w.return_gap > 10 ? 'text-[var(--color-danger)]' : 'text-theme-muted'">
                  {{ w.return_gap.toFixed(2) }}%
                </td>
                <td class="px-2 py-1.5 text-center">
                  <span v-if="w.is_overfitted" class="text-[var(--color-danger)]">⚠️</span>
                  <span v-else class="text-[var(--color-success)]">✓</span>
                </td>
                <td class="px-2 py-1.5 text-theme-secondary">
                  <span v-if="w.best_params">
                    {{ formatParams(w.best_params) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
    
    <div v-else-if="!running" class="flex-1 flex flex-col items-center justify-center text-theme-muted text-[11px] gap-2">
      <span class="text-3xl">🔄</span>
      <span>配置参数后点击"开始分析"</span>
      <span class="text-[10px] text-theme-tertiary">Walk-Forward 分析用于检测策略过拟合</span>
    </div>
    
    <div v-if="running" class="absolute inset-0 z-10 flex flex-col items-center justify-center"
      style="background: rgba(15,23,42,0.85); backdrop-filter: blur(2px);">
      <div class="text-[var(--color-info)] text-xs font-mono">⏳ Walk-Forward 分析中...</div>
      <div class="text-[10px] text-theme-muted mt-2">正在优化参数并测试样本外表现</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { apiFetch } from '../utils/api.js'

const symbol = ref('sh600519')
const strategyType = ref('ma_crossover')
const mode = ref('rolling')
const trainWindowDays = ref(252)
const testWindowDays = ref(63)
const stepDays = ref(63)
const windowPreset = ref('2y')
const initialCapital = 100000

const running = ref(false)
const error = ref('')
const result = ref(null)

const overfittingText = computed(() => {
  if (!result.value) return '—'
  const s = result.value.overfitting_severity
  if (s === 'none') return '✅ 无过拟合'
  if (s === 'mild') return '⚡ 轻度'
  if (s === 'moderate') return '⚠️ 中度'
  return '❌ 严重'
})

const overfittingClass = computed(() => {
  if (!result.value) return 'text-theme-muted'
  const s = result.value.overfitting_severity
  if (s === 'none') return 'text-[var(--color-success)]'
  if (s === 'mild') return 'text-[var(--color-warning)]'
  return 'text-[var(--color-danger)]'
})

const confidenceText = computed(() => {
  if (!result.value) return '—'
  const c = result.value.confidence
  if (c === 'high') return '高'
  if (c === 'medium') return '中'
  return '低'
})

const confidenceClass = computed(() => {
  if (!result.value) return 'text-theme-muted'
  const c = result.value.confidence
  if (c === 'high') return 'text-[var(--color-success)]'
  if (c === 'medium') return 'text-[var(--color-warning)]'
  return 'text-theme-muted'
})

function presetDates(preset) {
  const end = new Date()
  const start = new Date()
  switch (preset) {
    case '1y': start.setFullYear(end.getFullYear() - 1); break
    case '2y': start.setFullYear(end.getFullYear() - 2); break
    case '3y': start.setFullYear(end.getFullYear() - 3); break
    case '5y': start.setFullYear(end.getFullYear() - 5); break
  }
  return { start_date: start.toISOString().slice(0, 10), end_date: end.toISOString().slice(0, 10) }
}

function formatParams(params) {
  if (!params) return '—'
  return Object.entries(params)
    .map(([k, v]) => `${k}=${v}`)
    .join(', ')
}

async function runAnalysis() {
  if (running.value) return
  
  running.value = true
  error.value = ''
  result.value = null
  
  try {
    const { start_date, end_date } = presetDates(windowPreset.value)
    
    const resp = await apiFetch('/api/v1/backtest/walkforward/analyze', {
      method: 'POST',
      body: {
        symbol: symbol.value.trim() || 'sh600519',
        start_date,
        end_date,
        strategy_type: strategyType.value,
        initial_capital: initialCapital,
        train_window_days: trainWindowDays.value,
        test_window_days: testWindowDays.value,
        step_days: stepDays.value,
        mode: mode.value
      }
    })
    
    if (resp?.code !== 0 && resp?.code !== undefined) {
      error.value = resp?.message || '分析失败'
      return
    }
    
    result.value = resp?.data || resp
  } catch (e) {
    error.value = e.message || '分析失败'
  } finally {
    running.value = false
  }
}
</script>
