<template>
  <div class="condition-selector" role="group" aria-label="条件选择器">
    <div class="text-[10px] text-theme-accent font-bold mb-2">🔗 条件组合</div>
    
    <!-- Entry Rules -->
    <div class="rules-section mb-3">
      <div class="flex items-center gap-2 mb-1.5">
        <span class="text-[10px] text-[var(--color-success)] font-medium">买入条件</span>
        <select v-model="entryLogic" class="text-[9px] bg-terminal-bg border border-theme-secondary rounded px-1 py-0.5">
          <option value="AND">全部满足 (AND)</option>
          <option value="OR">任一满足 (OR)</option>
        </select>
      </div>
      
      <div class="conditions-list space-y-1">
        <div
          v-for="(cond, idx) in entryConditions"
          :key="'entry-' + idx"
          class="condition-item flex items-center gap-2 p-1.5 rounded-sm bg-terminal-bg/40 border border-theme/30"
        >
          <select v-model="cond.indicator" class="flex-1 text-[10px] bg-transparent border-0 focus:outline-none">
            <option v-for="ind in availableIndicators" :key="ind.id" :value="ind.id">
              {{ ind.icon }} {{ ind.name }}
            </option>
          </select>
          <select v-model="cond.operator" class="w-16 text-[10px] bg-transparent border-0 focus:outline-none">
            <option v-for="op in operators" :key="op.value" :value="op.value">{{ op.label }}</option>
          </select>
          <input
            v-model.number="cond.value"
            type="number"
            class="w-16 text-[10px] bg-terminal-bg border border-theme-secondary rounded px-1 py-0.5 text-center"
          />
          <button
            @click="removeCondition('entry', idx)"
            class="text-[10px] text-[var(--color-danger)] hover:text-[var(--color-danger-light)]"
            type="button"
            aria-label="删除条件"
          >
            ✕
          </button>
        </div>
      </div>
      
      <button
        @click="addCondition('entry')"
        class="mt-1.5 w-full min-h-[36px] text-[10px] text-[var(--color-info)] border border-dashed border-[var(--color-info-border)] rounded-sm hover:bg-[var(--color-info-bg)] transition-colors"
        type="button"
      >
        + 添加买入条件
      </button>
    </div>

    <!-- Exit Rules -->
    <div class="rules-section mb-3">
      <div class="flex items-center gap-2 mb-1.5">
        <span class="text-[10px] text-[var(--color-danger)] font-medium">卖出条件</span>
        <select v-model="exitLogic" class="text-[9px] bg-terminal-bg border border-theme-secondary rounded px-1 py-0.5">
          <option value="AND">全部满足 (AND)</option>
          <option value="OR">任一满足 (OR)</option>
        </select>
      </div>
      
      <div class="conditions-list space-y-1">
        <div
          v-for="(cond, idx) in exitConditions"
          :key="'exit-' + idx"
          class="condition-item flex items-center gap-2 p-1.5 rounded-sm bg-terminal-bg/40 border border-theme/30"
        >
          <select v-model="cond.indicator" class="flex-1 text-[10px] bg-transparent border-0 focus:outline-none">
            <option v-for="ind in availableIndicators" :key="ind.id" :value="ind.id">
              {{ ind.icon }} {{ ind.name }}
            </option>
          </select>
          <select v-model="cond.operator" class="w-16 text-[10px] bg-transparent border-0 focus:outline-none">
            <option v-for="op in operators" :key="op.value" :value="op.value">{{ op.label }}</option>
          </select>
          <input
            v-model.number="cond.value"
            type="number"
            class="w-16 text-[10px] bg-terminal-bg border border-theme-secondary rounded px-1 py-0.5 text-center"
          />
          <button
            @click="removeCondition('exit', idx)"
            class="text-[10px] text-[var(--color-danger)] hover:text-[var(--color-danger-light)]"
            type="button"
            aria-label="删除条件"
          >
            ✕
          </button>
        </div>
      </div>
      
      <button
        @click="addCondition('exit')"
        class="mt-1.5 w-full min-h-[36px] text-[10px] text-[var(--color-info)] border border-dashed border-[var(--color-info-border)] rounded-sm hover:bg-[var(--color-info-bg)] transition-colors"
        type="button"
      >
        + 添加卖出条件
      </button>
    </div>

    <!-- Visual Preview -->
    <div class="preview-section p-2 rounded-sm bg-[var(--color-info-bg)] border border-[var(--color-info-border)]">
      <div class="text-[9px] text-theme-muted mb-1">规则预览</div>
      <div class="text-[10px] text-[var(--color-info-light)] font-mono leading-relaxed">
        <div class="text-[var(--color-success)]">
          买入: {{ formatConditionsPreview(entryConditions, entryLogic) }}
        </div>
        <div class="text-[var(--color-danger)] mt-1">
          卖出: {{ formatConditionsPreview(exitConditions, exitLogic) }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({
      entry: [],
      exit: [],
      entryLogic: 'AND',
      exitLogic: 'OR'
    })
  }
})

const emit = defineEmits(['update:modelValue', 'code-generated'])

const entryConditions = ref(props.modelValue.entry || [])
const exitConditions = ref(props.modelValue.exit || [])
const entryLogic = ref(props.modelValue.entryLogic || 'AND')
const exitLogic = ref(props.modelValue.exitLogic || 'OR')

const availableIndicators = [
  { id: 'close', name: '收盘价', icon: '💰' },
  { id: 'ma5', name: 'MA5', icon: '📈' },
  { id: 'ma10', name: 'MA10', icon: '📈' },
  { id: 'ma20', name: 'MA20', icon: '📈' },
  { id: 'rsi', name: 'RSI', icon: '📊' },
  { id: 'macd', name: 'MACD', icon: '⚡' },
  { id: 'kdj_k', name: 'KDJ-K', icon: '🎯' },
  { id: 'kdj_d', name: 'KDJ-D', icon: '🎯' },
  { id: 'volume', name: '成交量', icon: '📊' },
  { id: 'boll_upper', name: '布林上轨', icon: '📉' },
  { id: 'boll_lower', name: '布林下轨', icon: '📉' }
]

const operators = [
  { value: '>', label: '>' },
  { value: '<', label: '<' },
  { value: '>=', label: '≥' },
  { value: '<=', label: '≤' },
  { value: '==', label: '=' }
]

function addCondition(type) {
  const newCond = {
    indicator: 'close',
    operator: '>',
    value: 0
  }
  if (type === 'entry') {
    entryConditions.value.push(newCond)
  } else {
    exitConditions.value.push(newCond)
  }
  emitUpdate()
}

function removeCondition(type, idx) {
  if (type === 'entry') {
    entryConditions.value.splice(idx, 1)
  } else {
    exitConditions.value.splice(idx, 1)
  }
  emitUpdate()
}

function formatConditionsPreview(conditions, logic) {
  if (!conditions.length) return '无'
  const parts = conditions.map(c => {
    const ind = availableIndicators.find(i => i.id === c.indicator)
    return `${ind?.name || c.indicator} ${c.operator} ${c.value}`
  })
  return parts.join(` ${logic} `)
}

function generateCode() {
  if (!entryConditions.value.length && !exitConditions.value.length) {
    return null
  }

  const entryCode = entryConditions.value.map(c => {
    return `${c.indicator} ${c.operator} ${c.value}`
  }).join(` ${entryLogic.value.toLowerCase()} `)

  const exitCode = exitConditions.value.map(c => {
    return `${c.indicator} ${c.operator} ${c.value}`
  }).join(` ${exitLogic.value.toLowerCase()} `)

  return `# 自定义条件策略
# 买入条件: ${entryConditions.value.map(c => {
  const ind = availableIndicators.find(i => i.id === c.indicator)
  return `${ind?.name || c.indicator} ${c.operator} ${c.value}`
}).join(` ${entryLogic.value} `)}
# 卖出条件: ${exitConditions.value.map(c => {
  const ind = availableIndicators.find(i => i.id === c.indicator)
  return `${ind?.name || c.indicator} ${c.operator} ${c.value}`
}).join(` ${exitLogic.value} `)}

buy = ${entryCode || 'False'}
sell = ${exitCode || 'False'}
output = {
    'signals': {'buy': buy, 'sell': sell}
}`
}

function emitUpdate() {
  emit('update:modelValue', {
    entry: [...entryConditions.value],
    exit: [...exitConditions.value],
    entryLogic: entryLogic.value,
    exitLogic: exitLogic.value
  })
  emit('code-generated', generateCode())
}

watch([entryConditions, exitConditions, entryLogic, exitLogic], emitUpdate, { deep: true })

defineExpose({
  generateCode,
  getConditions: () => ({
    entry: [...entryConditions.value],
    exit: [...exitConditions.value],
    entryLogic: entryLogic.value,
    exitLogic: exitLogic.value
  })
})
</script>
