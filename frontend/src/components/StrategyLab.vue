<template>
  <div class="flex flex-col w-full h-full overflow-hidden">
    <div class="flex items-center justify-between px-4 py-3 border-b border-theme bg-terminal-panel/80">
      <div class="flex items-center gap-3">
        <h2 class="text-lg font-bold text-theme-primary">策略实验室</h2>
        <span class="px-2 py-0.5 text-xs rounded bg-purple-500/20 text-purple-400 border border-purple-500/30">Beta</span>
      </div>
      <div class="flex items-center gap-2">
        <button @click="saveStrategy" :disabled="!strategyCode" class="px-3 py-1.5 text-xs rounded-lg border border-blue-500/30 bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 transition flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed">
          💾 保存
        </button>
        <button @click="runBacktest" :disabled="isRunning || !strategyCode" class="px-4 py-1.5 text-sm rounded-lg bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white font-medium transition flex items-center gap-2">
          <span v-if="isRunning" class="animate-spin">⏳</span>
          <span v-else>▶</span>
          {{ isRunning ? '运行中...' : '运行回测' }}
        </button>
      </div>
    </div>

    <div class="flex-1 grid grid-cols-1 xl:grid-cols-4 gap-4 overflow-hidden p-4">
      <div class="xl:col-span-1 flex flex-col gap-4 overflow-auto">
        <div class="bg-terminal-panel border border-theme rounded-lg p-4">
          <h3 class="text-sm font-semibold text-theme-primary mb-3 flex items-center gap-2">
            <span>🎯</span> 策略列表
          </h3>
          <div class="mb-3">
            <input v-model="searchQuery" type="text" placeholder="搜索策略..." class="w-full bg-terminal-bg border border-theme rounded-lg px-3 py-2 text-xs text-theme-primary focus:outline-none focus:border-blue-500/50" />
          </div>
          <div v-if="strategiesLoading" class="text-xs text-theme-muted text-center py-4">加载中...</div>
          <div v-else-if="filteredStrategies.length === 0" class="text-xs text-theme-muted text-center py-4">暂无策略</div>
          <div v-else class="space-y-2 max-h-48 overflow-y-auto">
            <div v-for="s in filteredStrategies" :key="s.id" @click="loadStrategy(s)" class="p-2 rounded-lg border cursor-pointer transition-all" :class="selectedStrategy?.id === s.id ? 'bg-blue-500/20 border-blue-500/50 text-blue-400' : 'bg-terminal-bg border-theme-secondary hover:border-blue-500/30 text-theme-secondary'">
              <div class="text-xs font-medium">{{ s.name }}</div>
              <div class="text-[10px] text-theme-muted mt-0.5">{{ s.market }}</div>
            </div>
          </div>
        </div>

        <div class="bg-terminal-panel border border-theme rounded-lg p-4">
          <h3 class="text-sm font-semibold text-theme-primary mb-3 flex items-center gap-2">
            <span>📋</span> 选择模板
          </h3>
          <div class="grid grid-cols-2 gap-2">
            <button
              v-for="tpl in templateList"
              :key="tpl.id"
              @click="selectTemplate(tpl)"
              class="p-3 rounded-lg border transition-all text-left"
              :class="selectedTemplate?.id === tpl.id
                ? 'bg-blue-500/20 border-blue-500/50 text-blue-400'
                : 'bg-terminal-bg border-theme-secondary text-theme-secondary hover:border-blue-500/30 hover:text-theme-primary'"
            >
              <div class="text-lg mb-1">{{ tpl.icon }}</div>
              <div class="text-xs font-medium">{{ tpl.name }}</div>
              <div class="text-[10px] opacity-60 mt-0.5">{{ TEMPLATE_CATEGORIES[tpl.category]?.name || tpl.category }}</div>
            </button>
          </div>
        </div>

        <div class="bg-terminal-panel border border-theme rounded-lg p-4">
          <h3 class="text-sm font-semibold text-theme-primary mb-3 flex items-center gap-2">
            <span>⚙️</span> 策略元数据
          </h3>
          <div class="space-y-3">
            <div>
              <label class="text-xs text-theme-muted block mb-1.5">策略名称</label>
              <input v-model="strategyName" type="text" class="w-full bg-terminal-bg border border-theme rounded-lg px-3 py-2 text-sm text-theme-primary focus:outline-none focus:border-blue-500/50" placeholder="输入策略名称" />
            </div>
            <div>
              <label class="text-xs text-theme-muted block mb-1.5">描述</label>
              <textarea v-model="strategyDescription" rows="2" class="w-full bg-terminal-bg border border-theme rounded-lg px-3 py-2 text-sm text-theme-primary focus:outline-none focus:border-blue-500/50 resize-none" placeholder="策略描述"></textarea>
            </div>
            <div>
              <label class="text-xs text-theme-muted block mb-1.5">市场</label>
              <select v-model="strategyMarket" class="w-full bg-terminal-bg border border-theme rounded-lg px-3 py-2 text-sm text-theme-primary focus:outline-none focus:border-blue-500/50">
                <option v-for="m in MARKET_OPTIONS" :key="m.value" :value="m.value">{{ m.icon }} {{ m.label }}</option>
              </select>
            </div>
          </div>
        </div>

        <div class="bg-terminal-panel border border-theme rounded-lg p-4">
          <h3 class="text-sm font-semibold text-theme-primary mb-3 flex items-center gap-2">
            <span>🛡️</span> 风险设置
          </h3>
          <div class="space-y-3">
            <div>
              <label class="text-xs text-theme-muted block mb-1.5">止损 %</label>
              <input v-model.number="stopLossPct" type="number" step="0.5" min="0" max="20" class="w-full bg-terminal-bg border border-theme rounded-lg px-3 py-2 text-sm text-theme-primary focus:outline-none focus:border-blue-500/50" />
            </div>
            <div>
              <label class="text-xs text-theme-muted block mb-1.5">止盈 %</label>
              <input v-model.number="takeProfitPct" type="number" step="0.5" min="0" max="50" class="w-full bg-terminal-bg border border-theme rounded-lg px-3 py-2 text-sm text-theme-primary focus:outline-none focus:border-blue-500/50" />
            </div>
          </div>
        </div>

        <div class="bg-terminal-panel border border-theme rounded-lg p-4">
          <h3 class="text-sm font-semibold text-theme-primary mb-3 flex items-center gap-2">
            <span>📊</span> 回测参数
          </h3>
          <div class="space-y-3">
            <div>
              <label class="text-xs text-theme-muted block mb-1.5">标的代码</label>
              <input v-model="symbol" type="text" class="w-full bg-terminal-bg border border-theme rounded-lg px-3 py-2 text-sm text-theme-primary focus:outline-none focus:border-blue-500/50" placeholder="sh000001" />
            </div>
            <div>
              <label class="text-xs text-theme-muted block mb-1.5">时间范围</label>
              <div class="grid grid-cols-2 gap-2">
                <input v-model="startDate" type="date" class="bg-terminal-bg border border-theme rounded-lg px-3 py-2 text-sm text-theme-primary focus:outline-none focus:border-blue-500/50" />
                <input v-model="endDate" type="date" class="bg-terminal-bg border border-theme rounded-lg px-3 py-2 text-sm text-theme-primary focus:outline-none focus:border-blue-500/50" />
              </div>
            </div>
            <div>
              <label class="text-xs text-theme-muted block mb-1.5">初始资金</label>
              <div class="flex items-center gap-2">
                <input v-model.number="initialCapital" type="number" class="flex-1 bg-terminal-bg border border-theme rounded-lg px-3 py-2 text-sm text-theme-primary focus:outline-none focus:border-blue-500/50" />
                <span class="text-xs text-theme-muted">元</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="xl:col-span-3 flex flex-col gap-4 overflow-auto">
        <div class="bg-terminal-panel border border-theme rounded-lg p-4 flex-1 flex flex-col">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-semibold text-theme-primary flex items-center gap-2">
              <span>📝</span> 策略代码
            </h3>
            <div class="flex items-center gap-2 text-xs text-theme-muted">
              <span v-if="selectedTemplate">模板: {{ selectedTemplate.name }}</span>
              <span v-else>自定义策略</span>
            </div>
          </div>
          <textarea v-model="strategyCode" class="flex-1 w-full bg-terminal-bg border border-theme rounded-lg p-3 text-xs font-mono text-theme-primary focus:outline-none focus:border-blue-500/50 resize-none" placeholder="# @name 策略名称&#10;# @description 策略描述&#10;# @param param_name type default 描述&#10;&#10;output = {&#10;    'indicators': {},&#10;    'signals': {'buy': ..., 'sell': ...}&#10;}"></textarea>
          <div v-if="strategyError" class="mt-2 px-3 py-2 text-xs text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg">
            {{ strategyError }}
          </div>
          <div v-if="parsedMetadata && Object.keys(parsedMetadata.parameters).length > 0" class="mt-3 p-3 bg-terminal-bg/50 rounded-lg border border-theme">
            <div class="text-xs text-theme-muted mb-2">检测到的参数:</div>
            <div class="grid grid-cols-2 gap-2">
              <div v-for="(param, key) in parsedMetadata.parameters" :key="key" class="flex items-center justify-between text-xs">
                <span class="text-theme-secondary">{{ key }}</span>
                <span class="text-theme-muted">{{ param.type }} = {{ param.default }}</span>
              </div>
            </div>
          </div>
        </div>

        <div v-if="backtestResult" class="bg-terminal-panel border border-theme rounded-lg p-4">
          <h3 class="text-sm font-semibold text-theme-primary mb-3 flex items-center gap-2">
            <span>📊</span> 回测结果
          </h3>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div class="bg-terminal-bg/50 rounded-lg p-3">
              <div class="text-[10px] text-theme-muted mb-1">总收益率</div>
              <div class="text-lg font-bold" :class="backtestResult.total_return?.includes('-') ? 'text-red-400' : 'text-green-400'">
                {{ backtestResult.total_return }}
              </div>
            </div>
            <div class="bg-terminal-bg/50 rounded-lg p-3">
              <div class="text-[10px] text-theme-muted mb-1">夏普比率</div>
              <div class="text-lg font-bold" :class="Number(backtestResult.sharpe_ratio) >= 1 ? 'text-green-400' : 'text-yellow-400'">
                {{ backtestResult.sharpe_ratio }}
              </div>
            </div>
            <div class="bg-terminal-bg/50 rounded-lg p-3">
              <div class="text-[10px] text-theme-muted mb-1">最大回撤</div>
              <div class="text-lg font-bold text-red-400">
                {{ backtestResult.max_drawdown }}
              </div>
            </div>
            <div class="bg-terminal-bg/50 rounded-lg p-3">
              <div class="text-[10px] text-theme-muted mb-1">胜率</div>
              <div class="text-lg font-bold text-blue-400">
                {{ backtestResult.win_rate }}
              </div>
            </div>
          </div>

          <div v-if="backtestResult.regime" class="mt-4 pt-4 border-t border-theme">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div class="bg-terminal-bg/30 rounded-lg p-3">
                <div class="text-[10px] text-theme-muted mb-2">市场状态</div>
                <div class="flex items-center gap-2">
                  <span class="text-2xl">{{ regimeIcon }}</span>
                  <div>
                    <div class="text-sm font-medium text-theme-primary">{{ regimeName }}</div>
                    <div class="text-[10px] text-theme-muted">置信度: {{ (backtestResult.regime.confidence * 100).toFixed(0) }}%</div>
                  </div>
                </div>
              </div>
              <div class="bg-terminal-bg/30 rounded-lg p-3">
                <div class="text-[10px] text-theme-muted mb-2">趋势指标</div>
                <div class="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span class="text-theme-muted">趋势:</span>
                    <span class="text-theme-primary ml-1">{{ (backtestResult.regime.indicators.trend_strength * 100).toFixed(1) }}%</span>
                  </div>
                  <div>
                    <span class="text-theme-muted">波动:</span>
                    <span class="text-theme-primary ml-1">{{ (backtestResult.regime.indicators.volatility_ratio * 100).toFixed(0) }}%</span>
                  </div>
                </div>
              </div>
              <div class="bg-terminal-bg/30 rounded-lg p-3">
                <div class="text-[10px] text-theme-muted mb-2">交易统计</div>
                <div class="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span class="text-theme-muted">交易次数:</span>
                    <span class="text-theme-primary ml-1">{{ backtestResult.trades_count || 0 }}</span>
                  </div>
                  <div>
                    <span class="text-theme-muted">年化:</span>
                    <span class="text-theme-primary ml-1">{{ backtestResult.annual_return }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="!backtestResult" class="flex-1 flex items-center justify-center">
          <div class="text-center">
            <div class="text-4xl mb-3 opacity-30">📈</div>
            <div class="text-theme-muted text-sm">点击「运行回测」开始分析</div>
            <div class="text-theme-muted/50 text-xs mt-1">选择左侧模板或编写自定义策略</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { apiFetch } from '../utils/api.js'
import { logger } from '../utils/logger.js'
import { useToast } from '../composables/useToast.js'
import { parseAnnotations, validateStrategy } from '../utils/strategyParser.js'
import { STRATEGY_TEMPLATES, TEMPLATE_CATEGORIES, MARKET_OPTIONS } from '../templates/strategyTemplates.js'

const { success: toastSuccess, error: toastError, info: toastInfo } = useToast()

const templateList = Object.values(STRATEGY_TEMPLATES)
const selectedTemplate = ref(null)
const selectedStrategy = ref(null)
const strategyCode = ref('')
const strategyError = ref('')
const isRunning = ref(false)

const strategyName = ref('')
const strategyDescription = ref('')
const strategyMarket = ref('AStock')
const stopLossPct = ref(2.0)
const takeProfitPct = ref(6.0)

const symbol = ref('sh000001')
const startDate = ref('2024-01-01')
const endDate = ref('2024-12-31')
const initialCapital = ref(100000)

const backtestResult = ref(null)

const strategies = ref([])
const strategiesLoading = ref(false)
const searchQuery = ref('')

const parsedMetadata = computed(() => {
  if (!strategyCode.value) return null
  try {
    return parseAnnotations(strategyCode.value)
  } catch (e) {
    return null
  }
})

const filteredStrategies = computed(() => {
  if (!searchQuery.value) return strategies.value
  const query = searchQuery.value.toLowerCase()
  return strategies.value.filter(s => 
    s.name.toLowerCase().includes(query) || 
    s.market.toLowerCase().includes(query)
  )
})

const regimeIcon = computed(() => {
  if (!backtestResult.value?.regime) return '❓'
  const icons = { bull: '🐂', bear: '🐻', trending_up: '📈', trending_down: '📉', ranging: '➡️', volatile: '🌪️', unknown: '❓' }
  return icons[backtestResult.value.regime.regime] || '❓'
})

const regimeName = computed(() => {
  if (!backtestResult.value?.regime) return ''
  const names = { bull: '牛市', bear: '熊市', trending_up: '上涨趋势', trending_down: '下跌趋势', ranging: '震荡', volatile: '高波动', unknown: '未知' }
  return names[backtestResult.value.regime.regime] || '未知'
})

function selectTemplate(tpl) {
  selectedTemplate.value = tpl
  selectedStrategy.value = null
  strategyCode.value = tpl.code
  strategyName.value = tpl.name
  strategyDescription.value = tpl.description
  strategyMarket.value = tpl.market[0]
  stopLossPct.value = tpl.riskSettings.stopLossPct
  takeProfitPct.value = tpl.riskSettings.takeProfitPct
  strategyError.value = ''
  toastInfo('模板已加载', `已选择 ${tpl.name} 策略模板`)
}

async function loadStrategy(s) {
  try {
    const data = await apiFetch(`/api/v1/strategy/strategies/${s.id}`)
    if (data) {
      selectedStrategy.value = data
      selectedTemplate.value = null
      strategyCode.value = data.code
      strategyName.value = data.name
      strategyDescription.value = data.description
      strategyMarket.value = data.market
      stopLossPct.value = data.stop_loss_pct
      takeProfitPct.value = data.take_profit_pct
      strategyError.value = ''
      toastInfo('策略已加载', `已加载 ${data.name}`)
    }
  } catch (err) {
    logger.error('[StrategyLab] Load strategy failed:', err)
    toastError('加载失败', err.message || '无法加载策略')
  }
}

async function fetchStrategies() {
  strategiesLoading.value = true
  try {
    const data = await apiFetch('/api/v1/strategy/strategies')
    strategies.value = data?.strategies || []
  } catch (err) {
    logger.error('[StrategyLab] Fetch strategies failed:', err)
  } finally {
    strategiesLoading.value = false
  }
}

async function saveStrategy() {
  if (!strategyCode.value) {
    toastError('保存失败', '策略代码不能为空')
    return
  }

  const validation = validateStrategy(strategyCode.value)
  if (!validation.valid) {
    toastError('验证失败', validation.errors[0])
    return
  }

  try {
    const payload = {
      name: strategyName.value || parsedMetadata.value?.name || '未命名策略',
      description: strategyDescription.value || parsedMetadata.value?.description || '',
      code: strategyCode.value,
      market: strategyMarket.value,
      parameters: parsedMetadata.value?.parameters || {},
      stop_loss_pct: stopLossPct.value,
      take_profit_pct: takeProfitPct.value
    }

    if (selectedStrategy.value?.id) {
      await apiFetch(`/api/v1/strategy/strategies/${selectedStrategy.value.id}`, {
        method: 'PUT',
        body: payload
      })
      toastSuccess('更新成功', '策略已更新')
    } else {
      const result = await apiFetch('/api/v1/strategy/strategies', {
        method: 'POST',
        body: payload
      })
      toastSuccess('保存成功', '策略已保存')
      if (result?.id) {
        selectedStrategy.value = { id: result.id, ...payload }
      }
    }
    fetchStrategies()
  } catch (err) {
    logger.error('[StrategyLab] Save strategy failed:', err)
    toastError('保存失败', err.message || '无法保存策略')
  }
}

async function runBacktest() {
  if (isRunning.value || !strategyCode.value) return
  
  const validation = validateStrategy(strategyCode.value)
  if (!validation.valid) {
    strategyError.value = validation.errors[0]
    return
  }

  isRunning.value = true
  strategyError.value = ''
  backtestResult.value = null

  try {
    const response = await apiFetch('/api/v1/strategy/backtest', {
      method: 'POST',
      body: {
        code: strategyCode.value,
        symbol: symbol.value,
        start_date: startDate.value,
        end_date: endDate.value,
        initial_capital: initialCapital.value,
      },
    })

    if (response) {
      backtestResult.value = response
      toastSuccess('回测完成', `完成 ${response.trades_count || 0} 笔交易`)
    }
  } catch (err) {
    logger.error('[StrategyLab] Backtest failed:', err)
    strategyError.value = err.message || '回测失败'
    toastError('回测失败', err.message || '请检查策略代码')
  } finally {
    isRunning.value = false
  }
}

watch(strategyCode, () => {
  strategyError.value = ''
})

fetchStrategies()
</script>
