// Cache TTL from environment or defaults
export const CACHE_TTL = {
  QUOTE: parseInt(import.meta.env.VITE_QUOTE_CACHE_TTL) || 5000,      // 5s default
  QUOTE_DETAIL: parseInt(import.meta.env.VITE_QUOTE_DETAIL_CACHE_TTL) || 30000, // 30s default
  SYMBOLS: 3600000,  // 1h
  SECTORS: 300000,   // 5min
}

export const TIMEOUTS = {
  API_DEFAULT: 8000,
  API_QUOTE: 5000,
  API_QUOTE_DETAIL: 10000,
  API_MACRO: 30000,
  WS_HEARTBEAT_INTERVAL: 25000,
  WS_PONG_TIMEOUT: 10000,
  WS_MAX_MISSED_PONGS: 3,
  WS_RECONNECT_BASE: 2000,
  WS_RECONNECT_MAX: 30000,
  WS_HEALTH_CHECK_INTERVAL: 30000,
  DEBOUNCE_RESIZE: 150,
  DEBOUNCE_SEARCH: 300,
}

// HTTP polling endpoints for different symbol types
export const POLLING_ENDPOINTS = {
  DEFAULT: '/api/v1/futures/commodities',
  COMMODITIES: '/api/v1/futures/commodities',
  INDEXES: '/api/v1/futures/main_indexes',
  STOCKS: '/api/v1/market/overview',
}
