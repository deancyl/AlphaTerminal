import { reactive } from 'vue'

const ui = reactive({
  klineFullscreen: false,
  sidebarCollapsed: false,
  sidebarWidth: '240px',
  copilotOpen: false,
  currentView: 'chart',
})

export function useUiStore() {
  return { ui }
}
