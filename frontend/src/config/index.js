/**
 * Frontend Configuration System
 * 
 * Runtime configuration support with environment-based defaults.
 * All hardcoded values should be moved here for centralized management.
 */

const isDev = import.meta.env.DEV
const isProd = import.meta.env.PROD

export const config = {
  env: {
    isDev,
    isProd,
    mode: import.meta.env.MODE,
  },

  api: {
    baseUrl: import.meta.env.VITE_API_BASE_URL || '',
    timeout: parseInt(import.meta.env.VITE_API_TIMEOUT) || 8000,
    quoteTimeout: parseInt(import.meta.env.VITE_API_QUOTE_TIMEOUT) || 5000,
    macroTimeout: parseInt(import.meta.env.VITE_API_MACRO_TIMEOUT) || 30000,
    retries: parseInt(import.meta.env.VITE_API_RETRIES) || 0,
  },

  backend: {
    host: import.meta.env.VITE_BACKEND_HOST || '127.0.0.1',
    port: parseInt(import.meta.env.VITE_BACKEND_PORT) || 8002,
    get httpUrl() {
      return `http://${this.host}:${this.port}`
    },
    get wsUrl() {
      return `ws://${this.host}:${this.port}`
    },
  },

  frontend: {
    host: import.meta.env.VITE_FRONTEND_HOST || '0.0.0.0',
    port: parseInt(import.meta.env.VITE_FRONTEND_PORT) || 60100,
  },

  ws: {
    heartbeatInterval: parseInt(import.meta.env.VITE_WS_HEARTBEAT_INTERVAL) || 25000,
    pongTimeout: parseInt(import.meta.env.VITE_WS_PONG_TIMEOUT) || 10000,
    maxMissedPongs: parseInt(import.meta.env.VITE_WS_MAX_MISSED_PONGS) || 3,
    reconnectBase: parseInt(import.meta.env.VITE_WS_RECONNECT_BASE) || 2000,
    reconnectMax: parseInt(import.meta.env.VITE_WS_RECONNECT_MAX) || 30000,
    healthCheckInterval: parseInt(import.meta.env.VITE_WS_HEALTH_CHECK_INTERVAL) || 30000,
  },

  cache: {
    quoteTtl: parseInt(import.meta.env.VITE_QUOTE_CACHE_TTL) || 5000,
    quoteDetailTtl: parseInt(import.meta.env.VITE_QUOTE_DETAIL_CACHE_TTL) || 30000,
    symbolsTtl: parseInt(import.meta.env.VITE_SYMBOLS_CACHE_TTL) || 3600000,
    sectorsTtl: parseInt(import.meta.env.VITE_SECTORS_CACHE_TTL) || 300000,
  },

  debounce: {
    resize: parseInt(import.meta.env.VITE_DEBOUNCE_RESIZE) || 150,
    search: parseInt(import.meta.env.VITE_DEBOUNCE_SEARCH) || 300,
  },

  debug: {
    enabled: import.meta.env.VITE_DEBUG_MODE === 'true' || isDev,
    logLevel: import.meta.env.VITE_LOG_LEVEL || (isDev ? 'debug' : 'info'),
  },

  features: {
    enableWebLLM: import.meta.env.VITE_ENABLE_WEB_LLM !== 'false',
    enableCopilot: import.meta.env.VITE_ENABLE_COPILOT !== 'false',
    enableBacktest: import.meta.env.VITE_ENABLE_BACKTEST !== 'false',
  },
}

export function getApiUrl(path) {
  const base = config.api.baseUrl
  if (!base) return path
  return `${base}${path}`
}

export function getWsUrl(path) {
  return `${config.backend.wsUrl}${path}`
}

export function isDebugEnabled() {
  return config.debug.enabled
}

export function isFeatureEnabled(feature) {
  return config.features[feature] === true
}

export default config
