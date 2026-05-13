/**
 * Data freshness utility for determining staleness of cached data
 */

const THRESHOLDS = {
  FRESH: { ms: 5 * 1000, icon: '●', label: '实时', labelEn: 'Live', color: 'var(--color-success)' },
  RECENT: { ms: 30 * 1000, icon: '●', label: '近期', labelEn: 'Recent', color: 'var(--color-warning)' },
  STALE: { ms: 60 * 1000, icon: '●', label: '稍旧', labelEn: 'Stale', color: 'var(--color-warning)' },
  EXPIRED: { ms: Infinity, icon: '●', label: '过期', labelEn: 'Expired', color: 'var(--color-danger)' }
};

/**
 * Format age in milliseconds to Chinese human-readable text
 * @param {number} ms - Age in milliseconds
 * @returns {string} Human-readable age text in Chinese
 */
export function formatAge(ms) {
  if (ms == null || ms < 0) return '无数据';
  
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  
  if (days > 0) return `${days}天前`;
  if (hours > 0) return `${hours}小时前`;
  if (minutes > 0) return `${minutes}分钟前`;
  if (seconds > 0) return `${seconds}秒前`;
  return '刚刚';
}

/**
 * Get freshness status for a timestamp
 * @param {number|string|Date|null|undefined} timestamp - The timestamp to check
 * @returns {{ status: string, icon: string, label: string, color: string, ageMs: number, ageText: string, isLive: boolean }}
 */
export function getFreshness(timestamp) {
  if (timestamp == null) {
    return {
      status: 'UNKNOWN',
      icon: '●',
      label: '无数据',
      labelEn: 'No data',
      color: 'var(--text-tertiary)',
      ageMs: -1,
      ageText: '无数据',
      isLive: false
    };
  }
  
  const now = Date.now();
  let ts;
  
  if (timestamp instanceof Date) {
    ts = timestamp.getTime();
  } else if (typeof timestamp === 'string') {
    ts = new Date(timestamp).getTime();
  } else if (typeof timestamp === 'number') {
    ts = timestamp;
  } else {
    return {
      status: 'UNKNOWN',
      icon: '●',
      label: '无数据',
      labelEn: 'Invalid',
      color: 'var(--text-tertiary)',
      ageMs: -1,
      ageText: '无效',
      isLive: false
    };
  }
  
  if (isNaN(ts)) {
    return {
      status: 'UNKNOWN',
      icon: '●',
      label: '无数据',
      labelEn: 'Invalid',
      color: 'var(--text-tertiary)',
      ageMs: -1,
      ageText: '无效',
      isLive: false
    };
  }
  
  const ageMs = now - ts;
  
  let threshold;
  if (ageMs < THRESHOLDS.FRESH.ms) {
    threshold = THRESHOLDS.FRESH;
  } else if (ageMs < THRESHOLDS.RECENT.ms) {
    threshold = THRESHOLDS.RECENT;
  } else if (ageMs < THRESHOLDS.STALE.ms) {
    threshold = THRESHOLDS.STALE;
  } else {
    threshold = THRESHOLDS.EXPIRED;
  }
  
  const status = threshold === THRESHOLDS.EXPIRED ? 'EXPIRED' : 
                 threshold === THRESHOLDS.STALE ? 'STALE' :
                 threshold === THRESHOLDS.RECENT ? 'RECENT' : 'FRESH';
  
  return {
    status,
    icon: threshold.icon,
    label: threshold.label,
    labelEn: threshold.labelEn,
    color: threshold.color,
    ageMs,
    ageText: formatAge(ageMs),
    isLive: status === 'FRESH'
  };
}
