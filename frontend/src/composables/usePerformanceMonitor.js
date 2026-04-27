/**
 * usePerformanceMonitor - 前端性能监控
 * 
 * 监控指标:
 * - FPS (帧率)
 * - 内存使用 (如果有 Performance.memory API)
 * - API 响应时间
 * - 组件渲染时间
 * 
 * 用法:
 *   const perf = usePerformanceMonitor()
 *   perf.startMeasure('api-fetch')
 *   await fetchData()
 *   perf.endMeasure('api-fetch')
 */

import { ref, onMounted, onUnmounted } from 'vue'

// 单例模式：所有组件共享同一个监控实例
let globalStats = {
  fps: 0,
  memory: null,
  apiMeasures: {},
  errorCount: 0,
  lastUpdate: Date.now(),
}

let fpsRafId = null
let fpsFrames = 0
let fpsLastTime = performance.now()
let fpsRefCount = 0
const _startTime = Date.now()

function measureFPS() {
  fpsFrames++
  const now = performance.now()
  const elapsed = now - fpsLastTime
  
  if (elapsed >= 1000) {
    globalStats.fps = Math.round((fpsFrames * 1000) / elapsed)
    fpsFrames = 0
    fpsLastTime = now
    globalStats.lastUpdate = Date.now()
  }
  
  fpsRafId = requestAnimationFrame(measureFPS)
}

function startFPSMonitoring() {
  fpsRefCount++
  if (fpsRafId) return
  fpsRafId = requestAnimationFrame(measureFPS)
}

function stopFPSMonitoring() {
  fpsRefCount--
  if (fpsRefCount <= 0) {
    fpsRefCount = 0
    if (fpsRafId) {
      cancelAnimationFrame(fpsRafId)
      fpsRafId = null
    }
  }
}

function getMemoryInfo() {
  if (performance.memory) {
    return {
      usedJSHeapSize: performance.memory.usedJSHeapSize,
      totalJSHeapSize: performance.memory.totalJSHeapSize,
      jsHeapSizeLimit: performance.memory.jsHeapSizeLimit,
      usagePercent: Math.round((performance.memory.usedJSHeapSize / performance.memory.jsHeapSizeLimit) * 100)
    }
  }
  return null
}

function getStats() {
  return {
    fps: globalStats.fps,
    memory: getMemoryInfo(),
    apiMeasures: { ...globalStats.apiMeasures },
    errorCount: globalStats.errorCount,
    uptime: Date.now() - _startTime,
  }
}

export function usePerformanceMonitor() {
  const stats = ref({ ...globalStats })
  let updateInterval = null

  function formatBytes(bytes) {
    if (!bytes) return 'N/A'
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  // 开始测量 API 响应时间
  function startMeasure(name) {
    globalStats.apiMeasures[name] = {
      start: performance.now(),
      pending: true,
    }
  }

  // 结束测量
  function endMeasure(name) {
    const measure = globalStats.apiMeasures[name]
    if (!measure || !measure.pending) return null
    
    const duration = performance.now() - measure.start
    measure.duration = duration
    measure.pending = false
    measure.timestamp = Date.now()
    
    return duration
  }

  // 记录错误
  function recordError() {
    globalStats.errorCount++
  }

  // 性能等级评估
  function getPerformanceLevel() {
    const fps = globalStats.fps
    if (fps >= 55) return 'excellent'
    if (fps >= 45) return 'good'
    if (fps >= 30) return 'fair'
    return 'poor'
  }

  // 性能警告
  function getWarnings() {
    const warnings = []
    const mem = getMemoryInfo()
    
    if (globalStats.fps < 30) {
      warnings.push(`FPS过低: ${globalStats.fps}`)
    }
    
    if (mem && mem.usagePercent > 80) {
      warnings.push(`内存使用率过高: ${mem.usagePercent}%`)
    }
    
    // 检查慢 API 调用 (>3s)
    for (const [name, m] of Object.entries(globalStats.apiMeasures)) {
      if (m.duration > 3000) {
        warnings.push(`慢API: ${name} ${(m.duration/1000).toFixed(1)}s`)
      }
    }
    
    if (globalStats.errorCount > 10) {
      warnings.push(`错误过多: ${globalStats.errorCount}`)
    }
    
    return warnings
  }

  onMounted(() => {
    startFPSMonitoring()
    // 每秒更新一次统计数据
    updateInterval = setInterval(() => {
      stats.value = getStats()
    }, 1000)
  })

  onUnmounted(() => {
    stopFPSMonitoring()
    if (updateInterval) {
      clearInterval(updateInterval)
    }
  })

  return {
    stats,
    getMemoryInfo,
    formatBytes,
    startMeasure,
    endMeasure,
    recordError,
    getStats,
    getPerformanceLevel,
    getWarnings,
  }
}

// 导出全局性能统计（用于调试）
export function getGlobalPerfStats() {
  return getStats()
}
