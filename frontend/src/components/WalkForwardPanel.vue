<template>
  <div class="flex flex-col w-full h-full overflow-hidden bg-terminal-panel">
    
    <!-- ═══════════════ Header Section ═══════════════ -->
    <div class="shrink-0 border-b border-theme p-3">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2">
          <h2 class="text-sm font-bold text-theme-primary">🔄 Walk-Forward 分析</h2>
          <span class="text-[10px] text-theme-muted">检测策略是否"死记硬背"历史数据</span>
        </div>
        <div class="flex items-center gap-2">
          <button @click="showHelp = true" 
            class="w-5 h-5 rounded-full border border-theme-secondary text-theme-muted text-[10px] hover:border-[var(--color-info-border)] hover:text-[var(--color-info)] transition-colors cursor-help"
            title="查看 Walk-Forward 分析说明">
            ?
          </button>
          <div class="flex items-center gap-2">
            <span class="text-[10px] text-theme-muted">模式:</span>
            <select v-model="mode" class="bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-[10px] text-theme-primary">
              <option value="rolling">滚动窗口</option>
              <option value="anchored">锚定窗口</option>
            </select>
          </div>
        </div>
      </div>
      
      <!-- ═══════════════ Quick Presets Section ═══════════════ -->
      <div class="mb-3 px-2 py-2 rounded border border-theme bg-terminal-bg/50">
        <div class="text-[10px] text-theme-accent font-bold mb-2">🎯 快速预设</div>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="preset in walkForwardPresets" :key="preset.name"
            @click="applyPreset(preset)"
            class="min-h-[36px] px-3 py-1.5 text-[10px] rounded-sm border transition-colors"
            :class="isPresetActive(preset)
              ? 'bg-[var(--color-info-bg)] border-[var(--color-info-border)] text-[var(--color-info)]'
              : 'border-theme-secondary text-theme-secondary hover:border-[var(--color-info-border)] hover:text-[var(--color-info-light)]'"
            type="button"
          >
            {{ preset.icon }} {{ preset.name }}
          </button>
          <button
            @click="getSmartParams"
            :disabled="smartParamsLoading"
            class="min-h-[36px] px-3 py-1.5 text-[10px] rounded-sm border transition-colors"
            :class="smartParamsLoading
              ? 'bg-[var(--color-neutral-bg)] border-theme-secondary text-theme-muted cursor-not-allowed'
              : 'border-[var(--color-accent-border)] text-[var(--color-accent)] hover:bg-[var(--color-accent-bg)]/30'"
            type="button"
          >
            {{ smartParamsLoading ? '⏳ 推荐中...' : '🤖 智能推荐' }}
          </button>
        </div>
      </div>
      
      <!-- ═══════════════ Parameter Section with Hints ═══════════════ -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-[10px]">
        <div class="flex flex-col">
          <span class="text-theme-muted mb-1">标的</span>
          <input v-model="symbol" type="text" 
            class="bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-theme-primary"
            placeholder="sh600519" />
          <span class="text-[9px] text-theme-tertiary mt-0.5">股票代码，如茅台</span>
        </div>
        <div class="flex flex-col">
          <span class="text-theme-muted mb-1">策略</span>
          <select v-model="strategyType" 
            class="bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-theme-primary">
            <option value="ma_crossover">双均线</option>
            <option value="rsi_oversold">RSI超卖</option>
            <option value="bollinger_bands">布林带</option>
          </select>
          <span class="text-[9px] text-theme-tertiary mt-0.5">{{ strategyHint }}</span>
        </div>
        <div class="flex flex-col">
          <span class="text-theme-muted mb-1 cursor-help" title="训练窗口：用这段时间的历史数据寻找最优参数">训练窗口</span>
          <input v-model.number="trainWindowDays" type="number" 
            class="bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-theme-primary" />
          <span class="text-[9px] text-theme-tertiary mt-0.5">用这段时间找最优参数</span>
        </div>
        <div class="flex flex-col">
          <span class="text-theme-muted mb-1 cursor-help" title="测试窗口：用训练后的数据验证参数是否真的有效，模拟'未来'表现">测试窗口</span>
          <input v-model.number="testWindowDays" type="number" 
            class="bg-terminal-bg border border-theme-secondary rounded px-2 py-1 text-theme-primary" />
          <span class="text-[9px] text-theme-tertiary mt-0.5">验证参数是否真的有效</span>
        </div>
      </div>
      
      <!-- ═══════════════ Smart Params Reasoning ═══════════════ -->
      <div v-if="smartParamsReasoning" class="mt-2 px-3 py-2 rounded-sm bg-[var(--color-info-bg)]/20 border border-[var(--color-info-border)] text-[10px]">
        <span class="text-[var(--color-info)] font-medium">💡 智能推荐理由：</span>
        <span class="text-theme-secondary">{{ smartParamsReasoning }}</span>
      </div>
      
      <!-- ═══════════════ Info Box ═══════════════ -->
      <div class="mt-3 px-3 py-2 rounded-sm bg-[var(--color-info-bg)] border border-[var(--color-info-border)] text-[10px] leading-snug">
        <span class="text-[var(--color-info-light)] font-medium">💡 Walk-Forward 原理：</span>
        <span class="text-[var(--color-info-light)]/70">用过去数据训练策略 → </span>
        <span class="text-[var(--color-info-light)]/70">"穿越"到未来验证 → </span>
        <span class="text-[var(--color-info-light)]/70">如果训练好但测试差 = </span>
        <span class="text-[var(--color-danger)]">"死记硬背"（过拟合）</span>
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
    
    <!-- ═══════════════ Help Modal ═══════════════ -->
    <div v-if="showHelp" class="fixed inset-0 z-50 flex items-center justify-center" @click.self="showHelp = false">
      <div class="absolute inset-0 bg-black/60 backdrop-blur-sm"></div>
      <div class="relative bg-terminal-panel border border-theme rounded-lg p-4 max-w-md mx-4 shadow-xl">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-bold text-theme-primary">🔄 Walk-Forward 分析说明</h3>
          <button @click="showHelp = false" class="text-theme-muted hover:text-theme-primary text-lg">×</button>
        </div>
        <div class="text-[11px] text-theme-secondary space-y-2 leading-relaxed">
          <p><strong class="text-theme-primary">什么是 Walk-Forward 分析？</strong></p>
          <p>Walk-Forward 是一种检测策略是否过拟合的方法。它模拟"真实交易"场景：用历史数据训练策略，然后在"未来"数据上验证。</p>
          <p><strong class="text-theme-primary">为什么重要？</strong></p>
          <p>很多策略在历史数据上表现很好，但实盘却亏损。这通常是因为策略"死记硬背"了历史数据（过拟合），而不是真正理解市场规律。</p>
          <p><strong class="text-theme-primary">如何解读结果？</strong></p>
          <ul class="list-disc list-inside space-y-1 ml-2">
            <li><span class="text-[var(--color-success)]">✅ 无过拟合</span>：训练和测试表现接近，策略稳健</li>
            <li><span class="text-[var(--color-warning)]">⚡ 轻度过拟合</span>：测试表现略差于训练，需关注</li>
            <li><span class="text-[var(--color-danger)]">❌ 严重过拟合</span>：测试表现远差于训练，策略不可靠</li>
          </ul>
        </div>
      </div>
    </div>
    
    <div v-if="error" class="shrink-0 border-b border-theme bg-[var(--color-danger-bg)]/20 p-3">
      <div class="text-[11px] text-[var(--color-danger)]">❌ {{ error }}</div>
    </div>
    
    <!-- Anomaly Warnings -->
    <div v-if="anomalyWarnings.length > 0" class="shrink-0 border-b border-theme p-3">
      <div class="text-[11px] font-bold text-theme-primary mb-2">⚠️ 检测到以下问题</div>
      <div class="space-y-1.5">
        <div v-for="(warning, idx) in anomalyWarnings" :key="idx"
          class="flex items-start gap-2 px-2 py-1.5 rounded text-[10px]"
          :class="{
            'bg-[var(--color-warning-bg)]/20 border border-[var(--color-warning-border)]': warning.level === 'warning',
            'bg-[var(--color-info-bg)]/20 border border-[var(--color-info-border)]': warning.level === 'info'
          }">
          <span v-if="warning.level === 'warning'" class="text-[var(--color-warning)]">⚠️</span>
          <span v-else class="text-[var(--color-info)]">ℹ️</span>
          <div class="flex-1">
            <span class="text-theme-primary">{{ warning.message }}</span>
            <span class="text-theme-muted ml-1">— {{ warning.suggestion }}</span>
          </div>
        </div>
      </div>
    </div>
    
    <div v-if="result" class="flex-1 overflow-y-auto p-3">
      
      <div class="mb-4 p-3 rounded border border-theme bg-terminal-bg">
        <div class="text-[11px] font-bold text-theme-primary mb-2">📊 核心指标</div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div class="flex flex-col">
            <span class="text-[10px] text-theme-muted cursor-help" title="样本外平均收益：所有测试窗口的平均收益率，代表策略在'未知'数据上的真实表现">样本外平均收益</span>
            <span class="text-sm font-mono font-bold" 
              :class="result.avg_test_return_pct >= 0 ? 'text-bullish' : 'text-bearish'">
              {{ result.avg_test_return_pct >= 0 ? '+' : '' }}{{ result.avg_test_return_pct.toFixed(2) }}%
            </span>
          </div>
          <div class="flex flex-col">
            <span class="text-[10px] text-theme-muted cursor-help" title="样本外夏普：测试窗口的夏普比率平均值，衡量风险调整后收益。>1为良好，>2为优秀">样本外夏普</span>
            <span class="text-sm font-mono" 
              :class="result.avg_test_sharpe >= 1 ? 'text-bullish' : 'text-theme-muted'">
              {{ result.avg_test_sharpe.toFixed(2) }}
            </span>
          </div>
          <div class="flex flex-col">
            <span class="text-[10px] text-theme-muted cursor-help" title="过拟合程度：根据训练-测试收益差距判断策略是否'死记硬背'历史数据">过拟合程度</span>
            <span class="text-sm font-mono font-bold" :class="overfittingClass">
              {{ overfittingText }}
            </span>
          </div>
          <div class="flex flex-col">
            <span class="text-[10px] text-theme-muted cursor-help" title="一致性得分：训练和测试表现的一致性，越高说明策略越稳健">一致性得分</span>
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
            <span class="text-theme-muted cursor-help" title="训练-测试收益差：训练期收益与测试期收益的差距，差距越大说明过拟合越严重">训练-测试收益差</span>
            <span class="font-mono" :class="result.avg_return_gap > 10 ? 'text-[var(--color-danger)]' : 'text-theme-primary'">
              {{ result.avg_return_gap.toFixed(2) }}%
            </span>
          </div>
          <div class="flex flex-col">
            <span class="text-theme-muted cursor-help" title="过拟合窗口数：测试表现明显差于训练的窗口数量">过拟合窗口数</span>
            <span class="font-mono">
              {{ result.overfitting_windows }} / {{ result.total_windows }}
              <span class="text-theme-muted">({{ (result.overfitting_ratio * 100).toFixed(0) }}%)</span>
            </span>
          </div>
          <div class="flex flex-col">
            <span class="text-theme-muted cursor-help" title="置信度：分析结果的可信程度，取决于窗口数量和数据质量">置信度</span>
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
      
      <!-- AI Analysis Button -->
      <div class="flex justify-end mb-4">
        <button @click="showAIAnalysis" 
          class="px-3 py-1.5 text-[10px] rounded border border-[var(--color-accent-border)] text-[var(--color-accent)] hover:bg-[var(--color-accent-bg)]/30 transition-colors flex items-center gap-1"
          type="button">
          <span>🤖</span>
          AI深度解读
        </button>
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
                <th class="px-2 py-1.5 text-right text-theme-muted cursor-help" title="收益差：训练收益与测试收益的差距">收益差</th>
                <th class="px-2 py-1.5 text-center text-theme-muted cursor-help" title="过拟合：测试收益明显低于训练收益">过拟合</th>
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
    
    <!-- ═══════════════ Improved Empty State ═══════════════ -->
    <div v-else-if="!running" class="flex-1 flex flex-col items-center justify-center text-theme-muted text-[11px] gap-2 p-4">
      <span class="text-3xl">🔄</span>
      <span class="text-theme-primary font-medium">Walk-Forward 分析</span>
      <span>选择预设或配置参数，点击开始分析</span>
      <span class="text-[10px] text-theme-tertiary text-center max-w-xs">💡 这个工具帮你检测策略是否真的有效，而不是"看起来有效"</span>
    </div>
    
    <div v-if="running" class="absolute inset-0 z-10 flex flex-col items-center justify-center"
      style="background: rgba(15,23,42,0.85); backdrop-filter: blur(2px);">
      <div class="text-[var(--color-info)] text-xs font-mono">⏳ Walk-Forward 分析中...</div>
      <div class="text-[10px] text-theme-muted mt-2">正在优化参数并测试样本外表现</div>
    </div>
    
    <!-- AI Analysis Modal -->
    <div v-if="showAIModal" class="fixed inset-0 z-50 flex items-center justify-center" @click.self="showAIModal = false">
      <div class="absolute inset-0 bg-black/60 backdrop-blur-sm"></div>
      <div class="relative bg-terminal-panel border border-theme rounded-lg p-4 max-w-2xl mx-4 shadow-xl max-h-[80vh] overflow-y-auto">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-bold text-theme-primary">🤖 AI深度解读</h3>
          <button @click="showAIModal = false" class="text-theme-muted hover:text-theme-primary text-lg" type="button">×</button>
        </div>
        
        <div v-if="aiAnalysisLoading" class="flex items-center justify-center py-8">
          <span class="animate-spin text-2xl">⏳</span>
          <span class="ml-2 text-theme-muted text-[11px]">AI分析中...</span>
        </div>
        
        <div v-else-if="aiAnalysisError" class="text-[var(--color-danger)] text-[11px]">
          {{ aiAnalysisError }}
        </div>
        
        <div v-else class="text-[11px] text-theme-secondary leading-relaxed whitespace-pre-wrap">
          {{ aiAnalysisContent }}
        </div>
      </div>
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
const showHelp = ref(false)
const smartParamsLoading = ref(false)
const smartParamsReasoning = ref('')

// Anomaly warnings
const anomalyWarnings = ref([])

// AI Analysis
const showAIModal = ref(false)
const aiAnalysisLoading = ref(false)
const aiAnalysisError = ref('')
const aiAnalysisContent = ref('')

// ═══════════════ Quick Presets ═══════════════
const walkForwardPresets = [
  {
    name: '标准型',
    icon: '📊',
    desc: '适合大多数策略验证',
    train: 252,
    test: 63,
    window: '2y'
  },
  {
    name: '保守型',
    icon: '🛡️',
    desc: '长期稳定性测试',
    train: 504,
    test: 126,
    window: '3y'
  },
  {
    name: '激进型',
    icon: '⚡',
    desc: '快速检测过拟合',
    train: 126,
    test: 42,
    window: '1y'
  }
]

function applyPreset(preset) {
  trainWindowDays.value = preset.train
  testWindowDays.value = preset.test
  windowPreset.value = preset.window
}

function isPresetActive(preset) {
  return trainWindowDays.value === preset.train &&
         testWindowDays.value === preset.test &&
         windowPreset.value === preset.window
}

// ═══════════════ Strategy Hints ═══════════════
const strategyHint = computed(() => {
  switch (strategyType.value) {
    case 'ma_crossover':
      return '快线穿越慢线时买卖'
    case 'rsi_oversold':
      return 'RSI超卖买入，超买卖出'
    case 'bollinger_bands':
      return '触下轨买入，触上轨卖出'
    default:
      return ''
  }
})

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
  anomalyWarnings.value = []
  
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
    
    // Capture anomaly warnings
    if (resp?.data?.anomaly_warnings) {
      anomalyWarnings.value = resp.data.anomaly_warnings
    } else if (resp?.anomaly_warnings) {
      anomalyWarnings.value = resp.anomaly_warnings
    }
  } catch (e) {
    error.value = e.message || '分析失败'
  } finally {
    running.value = false
  }
}

async function getSmartParams() {
  if (!symbol.value.trim()) {
    error.value = '请输入股票代码'
    return
  }
  
  smartParamsLoading.value = true
  error.value = ''
  
  try {
    const resp = await apiFetch('/api/v1/backtest/walkforward/smart-params', {
      method: 'POST',
      body: {
        symbol: symbol.value.trim(),
        strategy_type: strategyType.value
      }
    })
    
    if (resp?.code !== 0 && resp?.code !== undefined) {
      error.value = resp?.message || '获取推荐参数失败'
      return
    }
    
    const data = resp?.data || resp
    
    // Auto-fill parameters
    trainWindowDays.value = data.train_window_days
    testWindowDays.value = data.test_window_days
    windowPreset.value = data.time_range
    smartParamsReasoning.value = data.reasoning
    
    // Show warnings if any
    if (data.warnings?.length > 0) {
      console.warn('Smart Params Warnings:', data.warnings)
    }
  } catch (e) {
    error.value = e.message || '获取推荐参数失败'
  } finally {
    smartParamsLoading.value = false
  }
}

async function showAIAnalysis() {
  if (!result.value) return
  
  showAIModal.value = true
  aiAnalysisLoading.value = true
  aiAnalysisError.value = ''
  aiAnalysisContent.value = ''
  
  try {
    const resp = await fetch('/api/v1/copilot/analyze-walkforward', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ result: result.value })
    })
    
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      const chunk = decoder.decode(value)
      const lines = chunk.split('\n')
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.content) {
              aiAnalysisContent.value += data.content
            }
            if (data.error) {
              aiAnalysisError.value = data.error
            }
          } catch (e) {
            // Ignore parse errors
          }
        }
      }
    }
  } catch (e) {
    aiAnalysisError.value = e.message || 'AI分析失败'
  } finally {
    aiAnalysisLoading.value = false
  }
}
</script>
