/**
 * Data freshness utility for determining staleness of cached data
 */

const THRESHOLDS = {
  FRESH: { ms: 60 * 1000, icon: '🟢', label: 'Fresh', color: '#22c55e' },
  RECENT: { ms: 5 * 60 * 1000, icon: '🟡', label: 'Recent', color: '#eab308' },
  STALE: { ms: 60 * 60 * 1000, icon: '🟠', label: 'Stale', color: '#f97316' },
  EXPIRED: { ms: Infinity, icon: '🔴', label: 'Expired', color: '#ef4444' }
};

/**
 * Format age in milliseconds to human-readable text
 * @param {number} ms - Age in milliseconds
 * @returns {string} Human-readable age text
 */
export function formatAge(ms) {
  if (ms == null || ms < 0) return 'unknown';
  
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  
  if (days > 0) return `${days}d ${hours % 24}h ago`;
  if (hours > 0) return `${hours}h ${minutes % 60}m ago`;
  if (minutes > 0) return `${minutes}m ago`;
  if (seconds > 0) return `${seconds}s ago`;
  return 'just now';
}

/**
 * Get freshness status for a timestamp
 * @param {number|string|Date|null|undefined} timestamp - The timestamp to check
 * @returns {{ status: string, icon: string, label: string, color: string, ageMs: number, ageText: string }}
 */
export function getFreshness(timestamp) {
  if (timestamp == null) {
    return {
      status: 'UNKNOWN',
      icon: '⚪',
      label: 'Unknown',
      color: '#6b7280',
      ageMs: -1,
      ageText: 'no data'
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
      icon: '⚪',
      label: 'Unknown',
      color: '#6b7280',
      ageMs: -1,
      ageText: 'invalid'
    };
  }
  
  if (isNaN(ts)) {
    return {
      status: 'UNKNOWN',
      icon: '⚪',
      label: 'Unknown',
      color: '#6b7280',
      ageMs: -1,
      ageText: 'invalid'
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
  
  return {
    status: threshold === THRESHOLDS.EXPIRED ? 'EXPIRED' : 
            threshold === THRESHOLDS.STALE ? 'STALE' :
            threshold === THRESHOLDS.RECENT ? 'RECENT' : 'FRESH',
    icon: threshold.icon,
    label: threshold.label,
    color: threshold.color,
    ageMs,
    ageText: formatAge(ageMs)
  };
}
