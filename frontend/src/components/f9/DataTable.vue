<!--
  DataTable.vue - Reusable Data Table Component
  
  A feature-rich data table component with sorting and pagination capabilities.
  Designed for displaying tabular data in the F9 Deep Analysis panels.
  
  FEATURES:
  - Column-based sorting (click header to sort ascending/descending)
  - Automatic pagination (10 rows per page)
  - Value formatting (number, percentage, date)
  - Empty state handling
  - Accessibility support (ARIA attributes, keyboard navigation)
  
  PROPS:
  - columns: Array<{ key: string, label: string, format?: string }>
    - key: Field name in data object
    - label: Display text for column header
    - format: Optional formatter ('number' | 'percentage' | 'date')
    - Example: [
        { key: 'name', label: '名称' },
        { key: 'value', label: '数值', format: 'number' },
        { key: 'change', label: '涨跌幅', format: 'percentage' }
      ]
  
  - data: Array<Object>
    - Array of row objects, each containing fields matching column keys
    - Example: [
        { name: '贵州茅台', value: 1800000, change: 2.5 },
        { name: '宁德时代', value: 950000, change: -1.2 }
      ]
  
  EMITTED EVENTS:
  - None (component is self-contained)
  
  SORTING BEHAVIOR:
  - Click any column header to sort by that column
  - First click: ascending order (↑)
  - Second click: descending order (↓)
  - Click different column: resets to ascending order
  - Null/undefined values sorted to bottom
  - Sorting resets pagination to page 1
  
  PAGINATION BEHAVIOR:
  - Fixed page size: 10 rows per page
  - Pagination controls: Previous/Next buttons
  - Shows: total count, current page, total pages
  - Pagination only visible when totalPages > 1
  
  USAGE EXAMPLE:
  <DataTable
    :columns="[
      { key: 'date', label: '日期', format: 'date' },
      { key: 'revenue', label: '营收(亿)', format: 'number' },
      { key: 'growth', label: '增长率', format: 'percentage' }
    ]"
    :data="financialData"
  />
  
  DEPENDENCIES:
  - formatNumber, formatDate from '../../utils/formatters.js'
-->
<template>
  <div class="data-table-container" role="region" aria-label="数据表格">
    <!-- Table -->
    <div class="overflow-x-auto">
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
              暂无数据
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="flex items-center justify-between px-3 py-2 border-t border-theme-secondary" role="navigation" aria-label="表格分页">
      <div class="text-xs text-terminal-dim" aria-live="polite">
        共 {{ data.length }} 条，第 {{ currentPage }}/{{ totalPages }} 页
      </div>
      <div class="flex items-center gap-1">
        <button
          class="px-2 py-1 text-xs rounded border border-theme-secondary text-terminal-secondary hover:border-terminal-accent hover:text-terminal-accent transition disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="currentPage === 1"
          @click="currentPage--"
          :aria-label="`第${currentPage - 1}页`"
          type="button"
        >
          上一页
        </button>
        <button
          class="px-2 py-1 text-xs rounded border border-theme-secondary text-terminal-secondary hover:border-terminal-accent hover:text-terminal-accent transition disabled:opacity-50 disabled:cursor-not-allowed"
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
/**
 * DataTable Component
 * 
 * Provides a sortable, paginated table for displaying structured data.
 * Used across F9 Deep Analysis panels for financial data presentation.
 */
import { ref, computed } from 'vue'
import { formatNumber, formatDate } from '../../utils/formatters.js'

/**
 * Component Props
 * @property {Array} columns - Column definitions with key, label, and optional format
 * @property {Array} data - Row data objects matching column keys
 */
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

// ===== Sorting State =====
const currentPage = ref(1)        // Current page number (1-indexed)
const pageSize = 10               // Fixed rows per page
const sortKey = ref('')           // Currently sorted column key
const sortOrder = ref('asc')      // Sort direction: 'asc' | 'desc'

/**
 * Computed: Sorted Data
 * Returns data sorted by current sortKey and sortOrder.
 * Null/undefined values are sorted to the bottom.
 * If no sortKey is set, returns original data order.
 */
const sortedData = computed(() => {
  if (!sortKey.value) return props.data
  
  return [...props.data].sort((a, b) => {
    const aVal = a[sortKey.value]
    const bVal = b[sortKey.value]
    
    // Handle null/undefined - push to bottom
    if (aVal == null) return 1
    if (bVal == null) return -1
    
    // Compare values
    const result = aVal > bVal ? 1 : aVal < bVal ? -1 : 0
    return sortOrder.value === 'asc' ? result : -result
  })
})

/**
 * Computed: Total Pages
 * Calculates total pages based on sorted data length and page size.
 */
const totalPages = computed(() => Math.ceil(sortedData.value.length / pageSize))

/**
 * Computed: Paginated Data
 * Returns the current page's slice of sorted data.
 * Calculates start index from currentPage and pageSize.
 */
const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return sortedData.value.slice(start, start + pageSize)
})

/**
 * Handle column header click for sorting.
 * - If same column: toggle sort order (asc ↔ desc)
 * - If different column: set new sortKey, reset to ascending
 * - Always reset to page 1 after sort change
 * @param {string} key - Column key to sort by
 */
function handleSort(key) {
  if (sortKey.value === key) {
    // Toggle direction for same column
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    // New column: set key and reset to ascending
    sortKey.value = key
    sortOrder.value = 'asc'
  }
  // Reset pagination to first page
  currentPage.value = 1
}

/**
 * Format cell value based on column format type.
 * @param {*} value - Raw cell value
 * @param {string} format - Format type: 'number' | 'percentage' | 'date' | undefined
 * @returns {string} Formatted display value
 */
function formatValue(value, format) {
  // Handle null/undefined
  if (value == null) return '--'
  
  switch (format) {
    case 'number':
      // Format with thousand separators (e.g., 1,234,567)
      return formatNumber(value)
    case 'percentage':
      // Format as percentage with +/- sign (e.g., +2.50%)
      return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
    case 'date':
      // Format date string
      return formatDate(value)
    default:
      // No formatting - return as-is
      return value
  }
}
</script>

<style scoped>
.data-table-container {
  @apply bg-terminal-panel rounded-lg border border-theme-secondary;
}
</style>
