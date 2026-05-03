<template>
  <aside
    v-if="isOpen"
    class="flex-shrink-0 flex flex-col bg-terminal-panel border-r border-theme-secondary overflow-hidden h-full w-[220px]"
  >
    <!-- 顶部：Logo + 关闭按钮 -->
    <div class="flex items-center justify-between h-12 border-b border-theme-secondary shrink-0 px-4"
    >
      <span class="text-theme-primary font-bold text-sm whitespace-nowrap">AlphaTerminal</span>
      <button
        class="w-10 h-10 flex items-center justify-center rounded-sm text-theme-tertiary hover:text-terminal-accent hover:bg-theme-hover transition-colors"
        @click="$emit('close')"
        title="关闭侧边栏"
      >
        <span class="text-sm">◀</span>
      </button>
    </div>

    <!-- 导航列表 -->
    <nav class="flex-1 overflow-y-auto py-2 w-full">
      <div class="px-3 py-1.5 text-[10px] text-theme-tertiary uppercase tracking-wider">📂 市场行情</div>

      <button
        v-for="item in mainNavItems"
        :key="item.id"
        class="w-full flex items-center gap-2.5 px-3 py-2.5 transition-all duration-200 relative group mx-2 my-0.5 rounded-sm"
        :class="[
          activeId === item.id
            ? 'bg-theme-hover text-theme-primary border-r-2 border-theme-secondary'
            : 'text-theme-secondary hover:bg-theme-hover hover:text-theme-primary border-r-transparent'
        ]"
        @click="handleClick(item)"
      >
        <span class="text-base">{{ item.icon }}</span>
        <span class="whitespace-nowrap text-xs">{{ item.label }}</span>
      </button>
    </nav>

    <!-- 主题切换区域 -->
    <div class="px-3 py-3 border-t border-theme shrink-0 w-full">
      <div class="text-[10px] text-theme-tertiary uppercase tracking-wider mb-2">🎨 主题切换</div>
      <div class="grid grid-cols-4 gap-1">
        <button
          v-for="t in themeList"
          :key="t.key"
          class="flex flex-col items-center justify-center py-2 px-1 rounded-sm text-[10px] transition-all duration-200"
          :class="currentTheme === t.key
            ? 'bg-theme-accent/20 text-theme-accent border border-theme-accent/50'
            : 'bg-theme-secondary/50 text-theme-secondary border border-transparent hover:bg-theme-hover hover:text-theme-primary'"
          @click="setTheme(t.key)"
          :title="t.name"
        >
          <span class="text-base mb-0.5">{{ t.icon }}</span>
          <span class="scale-90">{{ t.shortName }}</span>
        </button>
      </div>
    </div>

    <!-- 系统管理 -->
    <div class="border-t border-theme shrink-0 px-3 py-2 w-full">
      <button
        v-for="item in adminNavItems"
        :key="item.id"
        class="w-full flex items-center gap-2.5 px-3 py-2 transition-colors border-r-2 rounded-sm relative group"
        :class="[
          activeId === item.id
            ? 'bg-[var(--color-danger-bg)] text-[var(--color-danger)] border-r-2 border-[var(--color-danger)]'
            : 'text-theme-secondary hover:bg-[var(--color-danger-bg)] hover:text-[var(--color-danger)] border-r-transparent'
        ]"
        @click="handleClick(item)"
      >
        <span class="text-base">{{ item.icon }}</span>
        <span class="whitespace-nowrap text-xs">{{ item.label }}</span>
      </button>
    </div>
  </aside>
</template>

<script setup>
import { useTheme, THEMES, THEME_NAMES, THEME_ICONS } from '../composables/useTheme.js'

const props = defineProps({
  isOpen:   { type: Boolean, default: false },
  activeId: { type: String,  default: 'stock' },
})
const emit = defineEmits(['navigate', 'close'])

const { theme: currentTheme, setTheme } = useTheme()

const mainNavItems = [
  { id: 'stock',     label: '股票行情',   icon: '📊' },
  { id: 'portfolio', label: '投资组合',   icon: '💰' },
  { id: 'fund',      label: '基金分析',   icon: '📈' },
  { id: 'bond',      label: '债券行情',   icon: '📉' },
  { id: 'futures',   label: '期货行情',   icon: '🛢️' },
  { id: 'macro',     label: '宏观经济',   icon: '🌍' },
  { id: 'options',   label: '期权分析',   icon: '⚡' },
  { id: 'global-index', label: '全球指数',  icon: '🌐' },
  { id: 'backtest',  label: '回测实验室', icon: '🔬' },
]

const adminNavItems = [
  { id: 'admin',     label: '系统管理',   icon: '⚙️' },
]

const themeList = [
  { key: THEMES.DARK,  name: THEME_NAMES[THEMES.DARK],  shortName: '深色', icon: THEME_ICONS[THEMES.DARK] },
  { key: THEMES.BLACK, name: THEME_NAMES[THEMES.BLACK], shortName: '全黑', icon: THEME_ICONS[THEMES.BLACK] },
  { key: THEMES.WIND,  name: THEME_NAMES[THEMES.WIND],  shortName: 'Wind', icon: THEME_ICONS[THEMES.WIND] },
  { key: THEMES.LIGHT, name: THEME_NAMES[THEMES.LIGHT], shortName: '亮色', icon: THEME_ICONS[THEMES.LIGHT] },
]

function handleClick(item) {
  emit('navigate', item.id)
  emit('close')
}
</script>