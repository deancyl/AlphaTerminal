<template>
  <div class="code-preview" role="region" aria-label="代码预览">
    <div class="flex items-center justify-between mb-2">
      <div class="text-[10px] text-theme-accent font-bold">📝 代码预览</div>
      <div class="flex gap-1.5">
        <button
          @click="copyCode"
          class="min-h-[28px] px-2 py-1 text-[9px] rounded border border-theme-secondary text-theme-secondary hover:border-[var(--color-info-border)] hover:text-[var(--color-info)] transition-colors"
          type="button"
          :aria-label="copied ? '已复制' : '复制代码'"
        >
          {{ copied ? '✓ 已复制' : '📋 复制' }}
        </button>
        <button
          @click="toggleExpand"
          class="min-h-[28px] px-2 py-1 text-[9px] rounded border border-theme-secondary text-theme-secondary hover:border-[var(--color-info-border)] hover:text-[var(--color-info)] transition-colors"
          type="button"
          :aria-expanded="expanded"
          :aria-label="expanded ? '收起代码' : '展开代码'"
        >
          {{ expanded ? '▲ 收起' : '▼ 展开' }}
        </button>
      </div>
    </div>
    
    <div
      v-show="expanded"
      class="code-container relative rounded-sm border border-theme overflow-hidden"
    >
      <pre
        ref="codeRef"
        class="p-3 text-[10px] font-mono leading-relaxed overflow-x-auto bg-terminal-bg/80"
        :class="{ 'max-h-[200px] overflow-y-auto': !fullHeight }"
      ><code>{{ formattedCode }}</code></pre>
      
      <!-- Syntax highlight overlay (optional visual enhancement) -->
      <div class="absolute top-2 right-2 flex gap-1">
        <button
          v-if="!fullHeight"
          @click="fullHeight = true"
          class="text-[9px] text-theme-muted hover:text-[var(--color-info)]"
          type="button"
          aria-label="全高显示"
        >
          ⛶
        </button>
        <button
          v-else
          @click="fullHeight = false"
          class="text-[9px] text-theme-muted hover:text-[var(--color-info)]"
          type="button"
          aria-label="折叠显示"
        >
          ⛉
        </button>
      </div>
    </div>
    
    <!-- Code stats -->
    <div v-if="expanded" class="flex gap-3 mt-1.5 text-[9px] text-theme-muted">
      <span>{{ lineCount }} 行</span>
      <span>{{ charCount }} 字符</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  code: {
    type: String,
    default: ''
  },
  template: {
    type: Object,
    default: null
  },
  params: {
    type: Object,
    default: () => ({})
  }
})

const codeRef = ref(null)
const expanded = ref(true)
const fullHeight = ref(false)
const copied = ref(false)

const formattedCode = computed(() => {
  if (!props.code && !props.template) return '# 请选择策略或配置条件'
  
  if (props.template?.code) {
    let code = props.template.code
    // Replace parameter placeholders with actual values
    if (props.params) {
      Object.entries(props.params).forEach(([key, value]) => {
        const regex = new RegExp(`\\b${key}\\b`, 'g')
        code = code.replace(regex, String(value))
      })
    }
    return code
  }
  
  return props.code
})

const lineCount = computed(() => {
  return formattedCode.value.split('\n').length
})

const charCount = computed(() => {
  return formattedCode.value.length
})

async function copyCode() {
  try {
    await navigator.clipboard.writeText(formattedCode.value)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (err) {
    console.error('Failed to copy:', err)
  }
}

function toggleExpand() {
  expanded.value = !expanded.value
}

defineExpose({
  getCode: () => formattedCode.value,
  copyCode
})
</script>

<style scoped>
.code-container pre {
  color: var(--text-primary);
}

.code-container code {
  color: inherit;
}
</style>
