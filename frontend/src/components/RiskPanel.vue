<template>
  <div class="flex flex-col w-full h-full overflow-hidden">
    <!-- 顶部控制栏 -->
    <div class="shrink-0 flex items-center gap-2 px-3 py-1.5 border-b border-theme bg-terminal-panel/80">
      <span class="text-[10px] text-theme-muted">置信水平</span>
      <select
        v-model="confidence"
        class="bg-theme-tertiary/30 border border-theme rounded-sm px-1.5 py-0.5 text-[10px] text-theme-primary"
      >
        <option :value="0.90">90%</option>
        <option :value="0.95">95%</option>
        <option :value="0.99">99%</option>
      </select>
      <span class="text-[10px] text-theme-muted ml-2">持有期</span>
      <select
        v-model="horizon"
        class="bg-theme-tertiary/30 border border-theme rounded-sm px-1.5 py-0.5 text-[10px] text-theme-primary"
      >
        <option :value="1">1天</option>
        <option :value="5">5天</option>
        <option :value="10">10天</option>
        <option :value="20">20天</option>
      </select>
      <button
        @click="loadRisk"
        :disabled="loading"
        class="ml-auto px-3 py-0.5 rounded-sm text-[10px] font-medium transition-colors"
        :class="loading
          ? 'bg-gray-600/40 text-theme-muted cursor-not-allowed'
          : 'bg-[var(--color-info-bg)] text-[var(--color-info)] hover:bg-[var(--color-info-bg)] border border-[var(--color-info-border)]'"
      >{{ loading ? '⏳ 计算中...' : '🔄 刷新' }}</button>
    </div>

    <!-- 主内容区 -->
    <div v-if="risk" class="flex-1 min-h-0 overflow-y-auto p-2 space-y-3">
      
      <!-- VaR 指标 -->
      <div class="rounded-sm border border-theme bg-terminal-panel/40 p-3">
        <div class="text-[10px] text-theme-muted font-bold mb-2">⚠️ 风险价值 (VaR)</div>
        <div class="grid grid-cols-2 md:grid-cols-3 gap-2">
          <div class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2">
            <div class="text-[10px] text-theme-muted">历史模拟法 VaR</div>
            <div class="text-[14px] font-mono font-bold text-bearish">-{{ risk.var_historical_pct }}%</div>
            <div class="text-[10px] text-theme-muted">≈ ¥{{ fmtYuan(risk.var_historical_amount) }}</div>
          </div>
          
          <div class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2">
            <div class="text-[10px] text-theme-muted">参数法 VaR</div>
            <div class="text-[14px] font-mono font-bold text-bearish">-{{ risk.var_parametric_pct }}%</div>
            <div class="text-[10px] text-theme-muted">≈ ¥{{ fmtYuan(risk.var_parametric_amount) }}</div>
          </div>
          
          <div class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2">
            <div class="text-[10px] text-theme-muted">{{ risk.horizon_days }}日 VaR</div>
            <div class="text-[14px] font-mono font-bold text-bearish">-{{ risk.var_horizon_pct }}%</div>
            <div class="text-[10px] text-theme-muted">≈ ¥{{ fmtYuan(risk.var_horizon_amount) }}</div>
          </div>
        </div>
        <div class="text-[10px] text-theme-muted mt-2">
          💡 含义：在 {{ confidence*100 }}% 置信水平下，{{ risk.horizon_days }} 天内最大损失不超过 {{ risk.var_horizon_pct }}%
        </div>
      </div>

      <!-- CVaR 指标 -->
      <div class="rounded-sm border border-theme bg-terminal-panel/40 p-3">
        <div class="text-[10px] text-theme-muted font-bold mb-2">🔥 条件风险价值 (CVaR / Expected Shortfall)</div>
        <div class="grid grid-cols-2 md:grid-cols-3 gap-2">
          <div class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2">
            <div class="text-[10px] text-theme-muted">历史模拟法 CVaR</div>
            <div class="text-[14px] font-mono font-bold text-bearish">-{{ risk.cvar_historical_pct }}%</div>
            <div class="text-[10px] text-theme-muted">≈ ¥{{ fmtYuan(risk.cvar_historical_amount) }}</div>
          </div>
          
          <div class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2">
            <div class="text-[10px] text-theme-muted">参数法 CVaR</div>
            <div class="text-[14px] font-mono font-bold text-bearish">-{{ risk.cvar_parametric_pct }}%</div>
            <div class="text-[10px] text-theme-muted">≈ ¥{{ fmtYuan(risk.cvar_parametric_amount) }}</div>
          </div>
          
          <div class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2">
            <div class="text-[10px] text-theme-muted">{{ risk.horizon_days }}日 CVaR</div>
            <div class="text-[14px] font-mono font-bold text-bearish">-{{ risk.cvar_horizon_pct }}%</div>
            <div class="text-[10px] text-theme-muted">≈ ¥{{ fmtYuan(risk.cvar_horizon_amount) }}</div>
          </div>
        </div>
        <div class="text-[10px] text-theme-muted mt-2">
          💡 含义：当损失超过 VaR 时，平均损失为 {{ risk.cvar_horizon_pct }}%（比 VaR 更悲观）
        </div>
      </div>

      <!-- 统计指标 -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
        <div class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2">
          <div class="text-[10px] text-theme-muted">日均波动率</div>
          <div class="text-[14px] font-mono font-bold">{{ risk.daily_volatility_pct }}%</div>
        </div>
        
        <div class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2">
          <div class="text-[10px] text-theme-muted">年化波动率</div>
          <div class="text-[14px] font-mono font-bold">{{ risk.annual_volatility_pct }}%</div>
        </div>
        
        <div class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2">
          <div class="text-[10px] text-theme-muted">最差单日</div>
          <div class="text-[14px] font-mono font-bold text-bearish">{{ risk.worst_day_pct }}%</div>
        </div>
        
        <div class="rounded-sm border border-theme bg-terminal-panel/60 px-3 py-2">
          <div class="text-[10px] text-theme-muted">最佳单日</div>
          <div class="text-[14px] font-mono font-bold text-bullish">+{{ risk.best_day_pct }}%</div>
        </div>
      </div>

      <!-- 指标说明 -->
      <div class="rounded-sm border border-theme bg-terminal-panel/40 px-3 py-2 space-y-1">
        <div class="text-[10px] text-theme-muted font-bold mb-1">📊 指标说明</div>
        <div class="text-[10px] text-theme-muted leading-relaxed">
          <span class="text-theme-primary">VaR</span>: 在给定置信水平下，特定持有期内可能的最大损失 |
          <span class="text-theme-primary">CVaR</span>: 当损失超过VaR时的平均损失，反映尾部风险 |
          <span class="text-theme-primary">历史模拟法</span>: 基于历史数据直接排序，不假设分布 |
          <span class="text-theme-primary">参数法</span>: 假设正态分布，用均值和标准差计算
        </div>
      </div>

      <!-- 统计周期 -->
      <div class="text-center">
        <span class="text-[10px] text-theme-muted">📅 {{ period }} | 共 {{ risk.total_days }} 个交易日 | 当前资产 ¥{{ fmtYuan(risk.current_asset) }}</span>
      </div>
    </div>

    <!-- 空状态 -->
    <div
      v-else-if="!loading"
      class="flex-1 flex flex-col items-center justify-center text-theme-muted text-[11px] gap-2"
    >
      <span class="text-xl">⚠️</span>
      <span>{{ errorMsg || '点击"刷新"计算风险价值指标' }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { apiFetch } from '../utils/api.js'
import { logger } from '../utils/logger.js'

const props = defineProps({
  portfolioId: { type: Number, required: true },
})

const confidence = ref(0.95)
const horizon = ref(1)
const loading = ref(false)
const risk = ref(null)
const period = ref('')
const errorMsg = ref('')

function fmtYuan(v) {
  if (v == null) return '--'
  v = Math.abs(v)
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return v.toFixed(2)
}

async function loadRisk() {
  if (loading.value) return
  loading.value = true
  errorMsg.value = ''
  try {
    const resp = await apiFetch(
      `/api/v1/portfolio/${props.portfolioId}/risk?confidence=${confidence.value}&horizon=${horizon.value}`
    )
    if (resp?.risk) {
      risk.value = resp.risk
      period.value = resp.period || ''
    } else if (resp?.message) {
      errorMsg.value = resp.message
      risk.value = null
    }
  } catch (e) {
    logger.error('[RiskPanel] loadRisk error:', e)
    errorMsg.value = '加载失败'
  } finally {
    loading.value = false
  }
}

watch(() => props.portfolioId, () => {
  risk.value = null
  loadRisk()
}, { immediate: true })

watch([confidence, horizon], () => {
  loadRisk()
})
</script>