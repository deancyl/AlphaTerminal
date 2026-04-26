/**
 * useDataSourceStatus — 全局数据源健康状态
 * 状态广播：
 *   'ok'        — 所有数据源正常
 *   'degraded'  — 主数据源故障，已切换备用
 *   'down'      — 全线熔断，无可用数据源
 *
 * 前端所有 API 拦截器调用 broadcast()，CommandCenter / Navbar 监听状态变化。
 *
 * 用法（组件内）：
 *   const { status, statusLabel, statusClass, init } = useDataSourceStatus()
 *   onMounted(init)
 */
import { ref, readonly } from 'vue'

// ── 模块级单例状态（跨组件共享）────────────────────────────────
const _status  = ref('ok')       // 'ok' | 'degraded' | 'down'
const _message = ref('')
const _since   = ref(null)       // timestamp when last status changed
const _listeners = new Set()
let _listenerLock = false        // 保护迭代时的修改

function _notifyListeners() {
  // 防止迭代时 Set 被修改（组件卸载时可能删除 listener）
  if (_listenerLock) return
  _listenerLock = true
  try {
    // 复制一份避免迭代时修改
    const snapshot = Array.from(_listeners)
    snapshot.forEach(fn => fn(_status.value, _message.value))
  } finally {
    _listenerLock = false
  }
}

/**
 * 广播状态变化
 * @param {'ok'|'degraded'|'down'} newStatus
 * @param {string} msg  human-readable message
 */
export function broadcastDataSourceStatus(newStatus, msg = '') {
  _status.value = newStatus
  _message.value = msg
  _since.value = Date.now()
  _notifyListeners()
  console.debug(`[DataSourceStatus] 🖥️  → ${newStatus}${msg ? ': ' + msg : ''}`)
}

/** 监听状态变化（返回 unlisten fn） */
export function onDataSourceStatusChange(fn) {
  // 等待锁释放（避免在迭代时修改 Set）
  if (_listenerLock) {
    setTimeout(() => onDataSourceStatusChange(fn), 1)
    return () => _listeners.delete(fn)
  }
  _listeners.add(fn)
  return () => {
    if (_listenerLock) {
      setTimeout(() => _listeners.delete(fn), 1)
    } else {
      _listeners.delete(fn)
    }
  }
}

export function useDataSourceStatus() {
  const statusLabel = {
    ok:       '🟢 正常',
    degraded: '🟡 降级',
    down:     '🔴 熔断',
  }

  const statusClass = {
    ok:       'text-green-400',
    degraded: 'text-yellow-400',
    down:     'text-red-400',
  }

  return {
    status:        readonly(_status),
    message:       readonly(_message),
    since:         readonly(_since),
    statusLabel:   statusLabel[_status.value] ?? '🟢 正常',
    statusClass:   statusClass[_status.value] ?? 'text-green-400',
    broadcast:     broadcastDataSourceStatus,
    onStatusChange: onDataSourceStatusChange,
  }
}
