/**
 * Centralized Polling Manager
 * 
 * Coordinates all polling tasks across the application to:
 * 1. Prevent request storms when multiple panels open
 * 2. Pause polling when page is hidden (saves resources)
 * 3. Resume with smart scheduling on page visibility
 * 4. Prioritize critical data over less important updates
 * 
 * Priority Levels:
 * - critical: Real-time data (OrderBook, quotes) - 3s default
 * - high: Near real-time (Sentiment intraday) - 15s default
 * - normal: Regular updates (News, sectors) - 60s default
 * - low: Infrequent updates (Historical data) - 300s default
 */

import { ref, computed, watch, onMounted } from 'vue'
import { usePageVisibility } from './usePageVisibility.js'

const PRIORITIES = {
  critical: 3000,
  high: 15000,
  normal: 60000,
  low: 300000
}

const POLLING_STRATEGIES = {
  WS_FIRST: 'ws_first',        // Try WS first, poll on failure
  POLLING_ALWAYS: 'polling',   // Always poll (for non-WS data)
  HYBRID: 'hybrid'            // Both in parallel
}

const tasks = ref(new Map())
const isPaused = ref(false)
const isInitialized = ref(false)
let schedulerTimer = null

export function usePollingManager(options = {}) {
  const {
    strategy = POLLING_STRATEGIES.WS_FIRST,
    wsStatusRef = null
  } = options
  
  const { isVisible, wasHidden } = usePageVisibility()
  
  const isRunning = ref(false)
  
  const shouldPoll = computed(() => {
    if (strategy === POLLING_STRATEGIES.POLLING_ALWAYS) {
      return true
    }
    
    if (strategy === POLLING_STRATEGIES.WS_FIRST && wsStatusRef) {
      const status = wsStatusRef.value
      return status === 'failed' || status === 'disconnected'
    }
    
    return true
  })
  
  function startPolling() {
    if (isRunning.value) return
    isRunning.value = true
    startScheduler()
  }
  
  function stopPolling() {
    if (!isRunning.value) return
    isRunning.value = false
    stopScheduler()
  }
  
  function register(id, fn, priority = 'normal', options = {}) {
    const interval = options.interval || PRIORITIES[priority] || PRIORITIES.normal
    const immediate = options.immediate !== false
    
    const task = {
      id,
      fn,
      priority,
      interval,
      lastRun: 0,
      errorCount: 0,
      registeredAt: Date.now()
    }
    
    tasks.value.set(id, task)
    
    if (immediate && isVisible.value && !isPaused.value) {
      executeTask(task)
    }
    
    return () => unregister(id)
  }
  
  function unregister(id) {
    tasks.value.delete(id)
  }
  
  function executeTask(task) {
    try {
      task.lastRun = Date.now()
      task.fn()
      task.errorCount = 0
    } catch (e) {
      task.errorCount++
      console.error(`[PollingManager] Task "${task.id}" error (count: ${task.errorCount}):`, e)
      
      if (task.errorCount >= 5) {
        console.warn(`[PollingManager] Task "${task.id}" disabled after 5 consecutive errors`)
        unregister(task.id)
      }
    }
  }
  
  function startScheduler() {
    if (schedulerTimer) return
    
    schedulerTimer = setInterval(() => {
      if (isPaused.value || !isVisible.value) return
      
      const now = Date.now()
      const priorityOrder = { critical: 0, high: 1, normal: 2, low: 3 }
      const sortedTasks = Array.from(tasks.value.values())
        .sort((a, b) => priorityOrder[a.priority] - priorityOrder[b.priority])
      
      for (const task of sortedTasks) {
        if (now - task.lastRun >= task.interval) {
          executeTask(task)
        }
      }
    }, 1000)
  }
  
  function stopScheduler() {
    if (schedulerTimer) {
      clearInterval(schedulerTimer)
      schedulerTimer = null
    }
  }
  
  function pauseAll() {
    isPaused.value = true
    stopScheduler()
  }
  
  function resumeAll(executePending = true) {
    isPaused.value = false
    
    if (executePending && isVisible.value) {
      const priorityOrder = { critical: 0, high: 1, normal: 2, low: 3 }
      const sortedTasks = Array.from(tasks.value.values())
        .sort((a, b) => priorityOrder[a.priority] - priorityOrder[b.priority])
      
      for (const task of sortedTasks) {
        executeTask(task)
      }
    }
    
    startScheduler()
  }
  
  function forceExecute(id) {
    const task = tasks.value.get(id)
    if (task) {
      executeTask(task)
    }
  }
  
  function getTaskStatus(id) {
    const task = tasks.value.get(id)
    if (!task) return null
    
    return {
      id: task.id,
      priority: task.priority,
      interval: task.interval,
      lastRun: task.lastRun,
      errorCount: task.errorCount,
      nextRun: task.lastRun + task.interval
    }
  }
  
  function getAllTasks() {
    return Array.from(tasks.value.keys()).map(id => getTaskStatus(id))
  }
  
  if (!isInitialized.value) {
    isInitialized.value = true
    
    watch(isVisible, (visible) => {
      if (visible) {
        resumeAll(true)
      } else {
        pauseAll()
      }
    })
    
    watch(wasHidden, (wasHiddenValue) => {
      if (wasHiddenValue && isVisible.value) {
        resumeAll(true)
      }
    })
    
    if (wsStatusRef) {
      watch(shouldPoll, (poll) => {
        if (poll && !isRunning.value) {
          startPolling()
        } else if (!poll && isRunning.value) {
          stopPolling()
        }
      }, { immediate: true })
    }
  }
  
  onMounted(() => {
    if (isVisible.value && !isPaused.value) {
      startScheduler()
    }
  })
  
  return {
    register,
    unregister,
    pauseAll,
    resumeAll,
    forceExecute,
    getTaskStatus,
    getAllTasks,
    isPaused,
    isVisible,
    PRIORITIES,
    shouldPoll,
    POLLING_STRATEGIES,
    startPolling,
    stopPolling,
    isRunning
  }
}

export { PRIORITIES, POLLING_STRATEGIES }
