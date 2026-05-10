export const RETRY_CONFIG = {
  '/api/v1/macro/overview': { retries: 3, timeoutMs: 30000 },
  '/api/v1/macro/calendar': { retries: 2, timeoutMs: 30000 },
  '/api/v1/macro/gdp': { retries: 2, timeoutMs: 30000 },
  '/api/v1/macro/cpi': { retries: 2, timeoutMs: 30000 },
  '/api/v1/macro/pmi': { retries: 2, timeoutMs: 30000 },
  '/api/v1/macro/ppi': { retries: 2, timeoutMs: 30000 },
  '/api/v1/macro/m2': { retries: 2, timeoutMs: 30000 },
  '/api/v1/macro/social_financing': { retries: 2, timeoutMs: 30000 },
  '/api/v1/macro/industrial_production': { retries: 2, timeoutMs: 30000 },
  '/api/v1/macro/unemployment': { retries: 2, timeoutMs: 30000 },
  
  '/api/v1/market/overview': { retries: 2, timeoutMs: 10000 },
  '/api/v1/market/sectors': { retries: 2, timeoutMs: 10000 },
  '/api/v1/market/stocks/search': { retries: 1, timeoutMs: 5000 },
  
  '/api/v1/f9/': { retries: 2, timeoutMs: 15000 },
  
  '/api/v1/news/flash': { retries: 1, timeoutMs: 5000 },
  '/api/v1/news/force_refresh': { retries: 0, timeoutMs: 10000 },
  
  '/api/v1/portfolio/': { retries: 1, timeoutMs: 10000 },
  '/api/v1/backtest/run': { retries: 0, timeoutMs: 60000 },
  
  '/api/v1/copilot/': { retries: 1, timeoutMs: 30000 },
}

export const DEFAULT_RETRY_CONFIG = {
  retries: 0,
  timeoutMs: 8000,
}

export function getRetryConfig(url) {
  for (const [pattern, config] of Object.entries(RETRY_CONFIG)) {
    if (url.startsWith(pattern)) {
      return config
    }
  }
  return DEFAULT_RETRY_CONFIG
}