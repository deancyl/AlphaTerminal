<template>
  <div class="virtualized-table-container h-full flex flex-col">
    <!-- Sticky Header -->
    <div class="shrink-0 overflow-x-auto scrollbar-hide">
      <table class="w-full text-xs whitespace-nowrap">
        <thead class="bg-terminal-panel sticky top-0 z-10 shadow-sm">
          <tr class="text-terminal-dim border-b border-theme">
            <th
              v-for="col in columns"
              :key="col.key"
              :class="[
                'px-2 py-1.5 font-normal',
                col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left',
                col.sortable !== false ? 'cursor-pointer select-none hover:text-theme-accent transition-colors' : ''
              ]"
              :style="{ width: col.width }"
              @click="col.sortable !== false && handleSort(col.key)"
            >
              <div class="flex items-center gap-1" :class="col.align === 'right' ? 'justify-end' : col.align === 'center' ? 'justify-center' : 'justify-start'">
                <span>{{ col.label }}</span>
                <span v-if="col.sortable !== false && sortKey === col.key" class="text-theme-accent">
                  {{ sortDir === 'asc' ? '▲' : '▼' }}
                </span>
              </div>
            </th>
          </tr>
        </thead>
      </table>
    </div>

    <!-- Virtualized Body -->
    <div class="flex-1 min-h-0 overflow-auto">
      <RecycleScroller
        ref="scrollerRef"
        class="virtualized-scroller h-full"
        :items="sortedItems"
        :item-size="itemSize"
        key-field="id"
        :buffer="buffer"
        v-slot="{ item, index }"
      >
        <div
          :class="[
            'table-row border-b border-theme-secondary/30 hover:bg-theme-secondary/20 transition-colors cursor-pointer',
            { 'bg-terminal-accent/10': selectedId === item.id },
            rowClass
          ]"
          @click="$emit('row-click', { item, index })"
          @dblclick="$emit('row-dblclick', { item, index })"
          @contextmenu.prevent="$emit('row-contextmenu', $event, item)"
        >
          <div class="flex items-center text-xs" :style="{ height: `${itemSize}px` }">
            <div
              v-for="col in columns"
              :key="col.key"
              :class="[
                'px-2 py-1.5 truncate',
                col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'
              ]"
              :style="{ width: col.width, flex: col.width ? 'none' : 1 }"
            >
              <slot :name="`cell-${col.key}`" :item="item" :index="index">
                <span :class="col.cellClass">{{ formatValue(item[col.key], col) }}</span>
              </slot>
            </div>
          </div>
        </div>
      </RecycleScroller>

      <!-- Empty State -->
      <div v-if="!items.length && !loading" class="flex flex-col items-center justify-center h-full text-theme-muted text-sm">
        <slot name="empty">
          <span class="text-2xl mb-2">📭</span>
          <span>{{ emptyText }}</span>
        </slot>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="absolute inset-0 bg-terminal-bg/50 backdrop-blur-sm flex items-center justify-center z-20">
        <div class="text-theme-accent text-xs">加载中...</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  },
  columns: {
    type: Array,
    required: true
    // [{ key, label, width, align, sortable, format, cellClass }]
  },
  itemSize: {
    type: Number,
    default: 36
  },
  buffer: {
    type: Number,
    default: 200
  },
  loading: {
    type: Boolean,
    default: false
  },
  emptyText: {
    type: String,
    default: '暂无数据'
  },
  selectedId: {
    type: [String, Number],
    default: null
  },
  rowClass: {
    type: [String, Array, Object],
    default: ''
  },
  defaultSortKey: {
    type: String,
    default: ''
  },
  defaultSortDir: {
    type: String,
    default: 'desc'
  }
})

const emit = defineEmits(['row-click', 'row-dblclick', 'row-contextmenu', 'sort'])

const scrollerRef = ref(null)
const sortKey = ref(props.defaultSortKey)
const sortDir = ref(props.defaultSortDir)

// Sorted items
const sortedItems = computed(() => {
  if (!sortKey.value) return props.items

  const col = props.columns.find(c => c.key === sortKey.value)
  const format = col?.format

  return [...props.items].sort((a, b) => {
    let valA = a[sortKey.value]
    let valB = b[sortKey.value]

    // Apply format if it's a value transformer
    if (typeof format === 'function') {
      valA = format(valA, a)
      valB = format(valB, b)
    }

    // Handle null/undefined
    if (valA == null) return 1
    if (valB == null) return -1

    // Compare
    let cmp = 0
    if (typeof valA === 'number' && typeof valB === 'number') {
      cmp = valA - valB
    } else {
      cmp = String(valA).localeCompare(String(valB))
    }

    return sortDir.value === 'asc' ? cmp : -cmp
  })
})

// Handle sort
function handleSort(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'desc'
  }
  emit('sort', { key: sortKey.value, dir: sortDir.value })
}

// Format value
function formatValue(value, col) {
  if (col.format) {
    if (typeof col.format === 'function') {
      return col.format(value)
    }
    // String format type
    switch (col.format) {
      case 'number':
        return value != null ? Number(value).toLocaleString() : '-'
      case 'percent':
        return value != null ? `${value >= 0 ? '+' : ''}${Number(value).toFixed(2)}%` : '-'
      case 'price':
        return value != null ? Number(value).toFixed(2) : '-'
      case 'date':
        return value || '-'
      default:
        return value ?? '-'
    }
  }
  return value ?? '-'
}

// Scroll to item
function scrollToItem(index) {
  scrollerRef.value?.scrollToItem(index)
}

// Scroll to top
function scrollToTop() {
  scrollerRef.value?.scrollToItem(0)
}

// Expose methods
defineExpose({
  scrollToItem,
  scrollToTop,
  scrollerRef
})

// Reset sort when items change significantly
watch(() => props.defaultSortKey, (newKey) => {
  sortKey.value = newKey
})

watch(() => props.defaultSortDir, (newDir) => {
  sortDir.value = newDir
})
</script>

<style scoped>
.virtualized-table-container {
  position: relative;
}

.virtualized-scroller {
  overflow-anchor: none;
}

.virtualized-scroller :deep(.vue-recycle-scroller__item-wrapper) {
  overflow-anchor: none;
}

.table-row {
  overflow-anchor: none;
}
</style>
