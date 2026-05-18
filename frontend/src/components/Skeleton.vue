<template>
  <div class="skeleton-wrapper" :class="wrapperClass">
    <!-- 圆形骨架（头像、图标） -->
    <div
      v-if="shape === 'circle'"
      class="skeleton-circle animate-pulse"
      :style="{ width: size || width, height: size || width }"
      role="status"
      aria-busy="true"
      :aria-label="ariaLabel"
    >
      <span class="sr-only">{{ ariaLabel }}</span>
    </div>

    <!-- 卡片骨架 -->
    <div v-else-if="shape === 'card'" class="skeleton-card">
      <div class="skeleton-card-header animate-pulse" :style="{ height: headerHeight }"></div>
      <div class="skeleton-card-body">
        <div
          v-for="i in bodyLines"
          :key="i"
          class="skeleton-line animate-pulse"
          :style="{ width: bodyWidths[i - 1] || '100%', height: lineHeight }"
        ></div>
      </div>
      <span class="sr-only">{{ ariaLabel }}</span>
    </div>

    <!-- 表格行骨架 -->
    <div
      v-else-if="shape === 'table-row'"
      class="skeleton-table-row"
      role="status"
      aria-busy="true"
      :aria-label="ariaLabel"
    >
      <div
        v-for="i in columns"
        :key="i"
        class="skeleton-cell animate-pulse"
        :style="{ width: columnWidths[i - 1] || 'auto' }"
      ></div>
      <span class="sr-only">{{ ariaLabel }}</span>
    </div>

    <!-- 文本块骨架（多行） -->
    <div
      v-else-if="shape === 'text'"
      class="skeleton-text-block"
      role="status"
      aria-busy="true"
      :aria-label="ariaLabel"
    >
      <div
        v-for="i in lines"
        :key="i"
        class="skeleton-line animate-pulse"
        :style="{ width: i === lines ? '60%' : '100%', height: lineHeight }"
      ></div>
      <span class="sr-only">{{ ariaLabel }}</span>
    </div>

    <!-- 表格骨架（完整表格） -->
    <div v-else-if="type === 'table'" class="skeleton-table">
      <!-- 表头 -->
      <div class="skeleton-table-header">
        <div
          v-for="i in columns"
          :key="i"
          class="skeleton-cell animate-pulse"
          :style="{ width: columnWidths[i - 1] || 'auto' }"
        ></div>
      </div>
      <!-- 表格行 -->
      <div
        v-for="row in rows"
        :key="row"
        class="skeleton-table-row"
      >
        <div
          v-for="col in columns"
          :key="col"
          class="skeleton-cell animate-pulse"
          :style="{ width: columnWidths[col - 1] || 'auto' }"
        ></div>
      </div>
      <span class="sr-only">{{ ariaLabel }}</span>
    </div>

    <!-- 行骨架（多列） -->
    <div v-else-if="type === 'row'" class="skeleton-row">
      <div
        v-for="i in count"
        :key="i"
        class="skeleton-item animate-pulse"
        :style="{ width: widths[i - 1] || defaultWidth, height: height }"
      ></div>
      <span class="sr-only">{{ ariaLabel }}</span>
    </div>

    <!-- 默认单行骨架 -->
    <div
      v-else
      class="skeleton-item animate-pulse"
      :style="{ width: width, height: height }"
      role="status"
      aria-busy="true"
      :aria-label="ariaLabel"
    >
      <span class="sr-only">{{ ariaLabel }}</span>
    </div>
  </div>
</template>

<script setup>
/**
 * Skeleton - 骨架屏组件
 *
 * 用于数据加载时显示占位符，提供更好的用户体验
 *
 * @example
 * // 线条骨架（默认）
 * <Skeleton width="100px" height="16px" />
 *
 * // 圆形骨架（头像）
 * <Skeleton shape="circle" size="40px" />
 *
 * // 卡片骨架
 * <Skeleton shape="card" width="200px" />
 *
 * // 表格行骨架
 * <Skeleton shape="table-row" :columns="4" />
 *
 * // 文本块骨架
 * <Skeleton shape="text" :lines="3" />
 */
const props = defineProps({
  /** 形状类型：line(默认), circle, card, table-row, text */
  shape: {
    type: String,
    default: 'line',
    validator: (v) => ['line', 'circle', 'card', 'table-row', 'text'].includes(v)
  },

  /** 旧版类型兼容：default, row, card, table */
  type: { type: String, default: 'default' },

  /** 宽度 */
  width: { type: String, default: '100%' },

  /** 高度 */
  height: { type: String, default: '16px' },

  /** 圆形尺寸（宽高相等） */
  size: { type: String, default: null },

  /** 行数量（type='row'时有效） */
  count: { type: Number, default: 3 },

  /** 各列宽度数组 */
  widths: { type: Array, default: () => [] },

  /** 默认列宽 */
  defaultWidth: { type: String, default: '100%' },

  /** 容器额外类名 */
  wrapperClass: { type: String, default: '' },

  // Card shape
  /** 卡片头部高度 */
  headerHeight: { type: String, default: '20px' },

  /** 卡片内容行数 */
  bodyLines: { type: Number, default: 3 },

  /** 卡片内容行宽度数组 */
  bodyWidths: { type: Array, default: () => ['100%', '75%', '50%'] },

  /** 行高 */
  lineHeight: { type: String, default: '12px' },

  // Table shape
  /** 表格列数 */
  columns: { type: Number, default: 4 },

  /** 表格行数 */
  rows: { type: Number, default: 5 },

  /** 各列宽度 */
  columnWidths: { type: Array, default: () => [] },

  // Text shape
  /** 文本行数 */
  lines: { type: Number, default: 3 },

  /** 无障碍标签 */
  ariaLabel: { type: String, default: '加载中...' }
})
</script>

<style scoped>
.skeleton-wrapper {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 基础骨架项 - 使用设计系统变量 */
.skeleton-item {
  background: var(--bg-surface-hover, rgba(255, 255, 255, 0.1));
  border-radius: var(--radius-sm, 4px);
}

/* 圆形骨架 */
.skeleton-circle {
  background: var(--bg-surface-hover, rgba(255, 255, 255, 0.1));
  border-radius: 50%;
  flex-shrink: 0;
}

/* 行骨架 */
.skeleton-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* 卡片骨架 */
.skeleton-card {
  background: var(--bg-surface, rgba(30, 30, 40, 0.8));
  border: 1px solid var(--border-base, #30363D);
  border-radius: var(--radius-lg, 8px);
  padding: 16px;
}

.skeleton-card-header {
  background: var(--bg-base, rgba(0, 0, 0, 0.5));
  border-radius: var(--radius-sm, 4px);
  margin-bottom: 12px;
}

.skeleton-card-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 文本块骨架 */
.skeleton-text-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 骨架线条 */
.skeleton-line {
  background: var(--bg-base, rgba(0, 0, 0, 0.5));
  border-radius: var(--radius-sm, 4px);
}

/* 表格骨架 */
.skeleton-table {
  width: 100%;
}

.skeleton-table-header {
  display: flex;
  gap: 8px;
  padding: 8px;
  background: var(--bg-surface, rgba(30, 30, 40, 0.5));
  border-radius: var(--radius-sm, 4px) var(--radius-sm, 4px) 0 0;
}

.skeleton-table-row {
  display: flex;
  gap: 8px;
  padding: 8px;
  border-bottom: 1px solid var(--border-light, rgba(48, 54, 61, 0.3));
}

.skeleton-cell {
  background: var(--bg-base, rgba(0, 0, 0, 0.3));
  border-radius: var(--radius-sm, 4px);
  height: 16px;
  flex: 1;
}

/* 屏幕阅读器专用 */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}
</style>
