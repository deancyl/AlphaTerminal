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
}
