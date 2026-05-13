<template>
  <div class="mobile-card-table" role="region" :aria-label="title || '数据列表'">
    <!-- Desktop Table View -->
    <div class="hidden md:block overflow-x-auto">
      <table class="w-full text-sm" role="table">
        <thead>
          <tr class="border-b border-theme-secondary bg-terminal-panel">
            <th
              v-for="col in columns"
              :key="col.key"
              class="px-3 py-2 text-left text-xs font-bold text-terminal-primary cursor-pointer hover:bg-theme-hover transition"
              @click="handleSort(col.key)"
              :aria-sort="sortKey === col.key ? (sortOrder === 'asc' ? 'ascending' : 'descending') : undefined"
              scope="col"
              tabindex="0"
              role="columnheader"
            >
              <div class="flex items-center gap-1">
                <span>{{ col.label }}</span>
                <span v-if="sortKey === col.key" class="text-terminal-accent" aria-hidden="true">
                  {{ sortOrder === 'asc' ? '↑' : '↓' }}
                </span>
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, idx) in paginatedData"
            :key="idx"
            class="border-b border-theme-secondary hover:bg-theme-hover transition"
          >
            <td
              v-for="col in columns"
              :key="col.key"
              class="px-3 py-2 text-xs text-terminal-secondary"
            >
              {{ formatValue(row[col.key], col.format) }}
            </td>
          </tr>
          <tr v-if="paginatedData.length === 0">
            <td :colspan="columns.length" class="px-3 py-8 text-center text-terminal-dim">
              {{ emptyText || '暂无数据' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Mobile Card View -->
    <div class="md:hidden space-y-2">
      <div
        v-for="(row, idx) in paginatedData"
        :key="idx"
        class="bg-terminal-panel rounded-lg border border-theme-secondary p-3"
        role="listitem"
      >
        <div
          v-for="col in columns"
          :key="col.key"
          class="flex justify-between items-start py-1.5 border-b border-theme-secondary last:border-b-0"
        >
          <span class="text-xs text-terminal-dim flex-shrink-0 pr-2">{{ col.label }}</span>
          <span 
            class="text-sm text-terminal-primary text-right break-all"
            :class="getValueClass(row[col.key], col.format)"
          >
            {{ formatValue(row[col.key], col.format) }}
          </span>
        </div>
      </div>
      <div v-if="paginatedData.length === 0" class="bg-terminal-panel rounded-lg border border-theme-secondary p-8 text-center text-terminal-dim">
        {{ emptyText || '暂无数据' }}
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="flex items-center justify-between px-3 py-2 border-t border-theme-secondary mt-2" role="navigation" aria-label="表格分页">
      <div class="text-xs text-terminal-dim" aria-live="polite">
        共 {{ data.length }} 条，第 {{ currentPage }}/{{ totalPages }} 页
      </div>
      <div class="flex items-center gap-1">
        <button
          class="px-3 py-2 text-xs rounded border border-theme-secondary text-terminal-secondary hover:border-terminal-accent hover:text-terminal-accent transition disabled:opacity-50 disabled:cursor-not-allowed"
          style="min-width: 44px; min-height: 44px;"
          :disabled="currentPage === 1"
          @click="currentPage--"
          :aria-label="`第${currentPage - 1}页`"
          type="button"
        >
          上一页
        </button>
        <button
          class="px-3 py-2 text-xs rounded border border-theme-secondary text-terminal-secondary hover:border-terminal-accent hover:text-terminal-accent transition disabled:opacity-50 disabled:cursor-not-allowed"
          style="min-width: 44px; min-height: 44px;"
          :disabled="currentPage === totalPages"
          @click="currentPage++"
          :aria-label="`第${currentPage + 1}页`"
          type="button"
        >
          下一页
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { formatNumber, formatDate } from '../../utils/formatters.js'

const props = defineProps({
  columns: {
    type: Array,
    default: () => []
    // Format: [{ key: 'field', label: '字段名', format: 'number|percentage|date' }]
  },
  data: {
    type: Array,
    default: () => []
  },
  title: {
    type: String,
    default: ''
  },
  emptyText: {
    type: String,
    default: '暂无数据'
  },
  pageSize: {
    type: Number,
    default: 10
  }
})

const currentPage = ref(1)
const sortKey = ref('')
const sortOrder = ref('asc') // 'asc' | 'desc'

// Sorting
const sortedData = computed(() => {
  if (!sortKey.value) return props.data
  
  return [...props.data].sort((a, b) => {
    const aVal = a[sortKey.value]
    const bVal = b[sortKey.value]
    
    if (aVal == null) return 1
    if (bVal == null) return -1
    
    const result = aVal > bVal ? 1 : aVal < bVal ? -1 : 0
    return sortOrder.value === 'asc' ? result : -result
  })
})

// Pagination
const totalPages = computed(() => Math.ceil(sortedData.value.length / props.pageSize))
const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * props.pageSize
  return sortedData.value.slice(start, start + props.pageSize)
})

function handleSort(key) {
  if (sortKey.value === key) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortOrder.value = 'asc'
  }
  currentPage.value = 1
}

// Formatters
function formatValue(value, format) {
  if (value == null) return '--'
  
  switch (format) {
    case 'number':
      return formatNumber(value)
    case 'percentage':
      return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
    case 'date':
      return formatDate(value)
    default:
      return value
  }
}

// Value class for color coding
function getValueClass(value, format) {
  if (format === 'percentage' && value != null) {
    if (value > 0) return 'text-green-400'
    if (value < 0) return 'text-red-400'
  }
  return ''
}
</script>

<style scoped>
.mobile-card-table {
  @apply bg-terminal-panel rounded-lg border border-theme-secondary;
}
</style>
