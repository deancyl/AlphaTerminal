import { reactive } from 'vue'

const ui = reactive({
  klineFullscreen: false,
  sidebarCollapsed: false,
  sidebarWidth: '240px',
  copilotOpen: false,
  currentView: 'chart',
  fullscreenSymbol: 'sh000001',
  fullscreenName: '上证指数',
})

export function useUiStore() {
  function openKlineFullscreen({ symbol, name }) {
    ui.fullscreenSymbol = symbol || 'sh000001'
    ui.fullscreenName = name || '上证指数'
    ui.klineFullscreen = true
  }
  return { ui, openKlineFullscreen }
}
