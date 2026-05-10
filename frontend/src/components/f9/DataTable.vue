<template>
  <div class="data-table-container">
    <!-- Table -->
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-theme-secondary bg-terminal-panel">
            <th
              v-for="col in columns"
              :key="col.key"
              class="px-3 py-2 text-left text-xs font-bold text-terminal-primary cursor-pointer hover:bg-theme-hover transition"
              @click="handleSort(col.key)"
            >
              <div class="flex items-center gap-1">
                <span>{{ col.label }}</span>
                <span v-if="sortKey === col.key" class="text-terminal-accent">
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
              暂无数据
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="flex items-center justify-between px-3 py-2 border-t border-theme-secondary">
      <div class="text-xs text-terminal-dim">
        共 {{ data.length }} 条，第 {{ currentPage }}/{{ totalPages }} 页
      </div>
      <div class="flex items-center gap-1">
        <button
          class="px-2 py-1 text-xs rounded border border-theme-secondary text-terminal-secondary hover:border-terminal-accent hover:text-terminal-accent transition disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="currentPage === 1"
          @click="currentPage--"
        >
          上一页
        </button>
        <button
          class="px-2 py-1 text-xs rounded border border-theme-secondary text-terminal-secondary hover:border-terminal-accent hover:text-terminal-accent transition disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="currentPage === totalPages"
          @click="currentPage++"
        >
          下一页
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  columns: {
    type: Array,
    default: () => []
    // Format: [{ key: 'field', label: '字段名', format: 'number|percentage|date' }]
  },
  data: {
    type: Array,
    default: () => []
  }
})

const currentPage = ref(1)
const pageSize = 10
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
const totalPages = computed(() => Math.ceil(sortedData.value.length / pageSize))
const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return sortedData.value.slice(start, start + pageSize)
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

function formatNumber(num) {
  if (num == null) return '--'
  if (Math.abs(num) >= 1e8) return (num / 1e8).toFixed(2) + '亿'
  if (Math.abs(num) >= 1e4) return (num / 1e4).toFixed(2) + '万'
  return num.toFixed(2)
}

function formatDate(date) {
  if (!date) return '--'
  if (typeof date === 'string') return date.slice(0, 10)
  return new Date(date).toISOString().slice(0, 10)
}
</script>

<style scoped>
.data-table-container {
  @apply bg-terminal-panel rounded-lg border border-theme-secondary;
}
</style>
