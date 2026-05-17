import { z } from 'zod'

// ── Individual Quote Schema ─────────────────────────────────────────────

/**
 * Single forex quote from EastMoney real-time feed
 */
export const ForexQuoteSchema = z.object({
  symbol: z.string().describe('Currency pair code, e.g., USDCNH'),
  name: z.string().describe('Currency pair name, e.g., 美元兑离岸人民币'),
  latest: z.number().nullable().describe('Latest price'),
  bid: z.number().nullable().optional().describe('Bid price'),
  ask: z.number().nullable().optional().describe('Ask price'),
  spread: z.number().nullable().optional().describe('Bid-ask spread'),
  change: z.number().nullable().describe('Price change amount'),
  change_pct: z.number().nullable().describe('Price change percentage'),
  open: z.number().nullable().describe('Opening price'),
  high: z.number().nullable().describe('High price'),
  low: z.number().nullable().describe('Low price'),
  prev_close: z.number().nullable().describe('Previous close price'),
  source: z.string().optional().describe('Data source: akshare, cfets, mock'),
  timestamp: z.union([z.string(), z.number()]).nullable().optional().describe('Quote timestamp'),
})

// ── Circuit Breaker Status Schema ───────────────────────────────────────

/**
 * Circuit breaker status for forex data fetching
 */
export const CircuitBreakerSchema = z.object({
  is_available: z.boolean().describe('Whether data source is available'),
  state: z.enum(['closed', 'open', 'half_open']).describe('Circuit breaker state'),
  consecutive_failures: z.number().describe('Number of consecutive failures'),
})

// ── Spot Quotes Response Schema ──────────────────────────────────────────

/**
 * Response from GET /api/v1/forex/spot
 */
export const ForexSpotResponseSchema = z.object({
  quotes: z.array(ForexQuoteSchema).describe('Array of forex quotes'),
  total: z.number().describe('Total number of quotes'),
  source: z.string().describe('Data source: akshare, cfets, fallback'),
  data_source: z.string().optional().describe('Data source type: live, fallback'),
  status: z.string().optional().describe('Data status: ready, loading'),
  last_update_time: z.string().optional().describe('Last update timestamp'),
  update_time: z.string().optional().describe('Update timestamp'),
  circuit_breaker: CircuitBreakerSchema.optional().describe('Circuit breaker status'),
})

// ── Cross-Rate Matrix Schemas ───────────────────────────────────────────

/**
 * Single rate cell in cross-rate matrix
 */
export const ForexMatrixRateSchema = z.object({
  rate: z.number().nullable().describe('Exchange rate value'),
  change_pct: z.number().nullable().describe('Change percentage'),
  is_base: z.boolean().describe('Whether this is base currency (diagonal)'),
  is_calculated: z.boolean().describe('Whether rate is calculated (triangular)'),
})

/**
 * Single row in cross-rate matrix
 */
export const ForexMatrixRowSchema = z.object({
  base_currency: z.string().describe('Base currency code'),
  rates: z.array(ForexMatrixRateSchema).describe('Array of rates for this base currency'),
})

/**
 * Response from GET /api/v1/forex/matrix
 */
export const ForexMatrixResponseSchema = z.object({
  currencies: z.array(z.string()).describe('List of currency codes'),
  matrix: z.array(ForexMatrixRowSchema).describe('Cross-rate matrix rows'),
  last_update: z.string().optional().describe('Last update timestamp'),
  source: z.string().optional().describe('Data source'),
  status: z.string().optional().describe('Data status'),
})

// ── History K-Line Schemas ──────────────────────────────────────────────

/**
 * Single K-line data point
 */
export const ForexHistoryDataPointSchema = z.object({
  date: z.string().describe('Date in YYYY-MM-DD format'),
  open: z.number().nullable().describe('Opening price'),
  close: z.number().nullable().describe('Closing price'),
  high: z.number().nullable().describe('High price'),
  low: z.number().nullable().describe('Low price'),
  amplitude: z.number().nullable().optional().describe('Amplitude percentage'),
})

/**
 * Response from GET /api/v1/forex/history/{symbol}
 */
export const ForexHistoryResponseSchema = z.object({
  symbol: z.string().describe('Currency pair symbol'),
  name: z.string().describe('Currency pair name'),
  period: z.string().describe('Period: daily, weekly, monthly'),
  data: z.array(ForexHistoryDataPointSchema).describe('Array of K-line data'),
  total: z.number().optional().describe('Total number of data points'),
  source: z.string().optional().describe('Data source: akshare, mock'),
  status: z.string().optional().describe('Data status'),
  last_update_time: z.string().optional().describe('Last update timestamp'),
})

// ── Currency Conversion Schemas ──────────────────────────────────────────

/**
 * Response from POST /api/v1/forex/convert or GET /api/v1/forex/convert
 */
export const ForexConvertResponseSchema = z.object({
  from_currency: z.string().describe('Source currency code'),
  to_currency: z.string().describe('Target currency code'),
  amount: z.number().describe('Original amount'),
  rate: z.number().describe('Exchange rate used'),
  result: z.number().describe('Converted amount'),
  rate_source: z.string().optional().describe('Rate source: direct, triangular, fallback'),
  path: z.array(z.string()).optional().describe('Conversion path for triangular arbitrage'),
  timestamp: z.string().optional().describe('Conversion timestamp'),
})

// ── CFETS Quote Schemas ─────────────────────────────────────────────────

/**
 * CFETS interbank quote
 */
export const ForexCFETSQuoteSchema = z.object({
  pair: z.string().describe('Currency pair, e.g., USD/CNY'),
  bid: z.number().nullable().describe('Bid price'),
  ask: z.number().nullable().describe('Ask price'),
  spread: z.number().nullable().describe('Bid-ask spread'),
  mid: z.number().nullable().describe('Mid price'),
  timestamp: z.union([z.string(), z.number()]).nullable().optional().describe('Quote timestamp'),
})

/**
 * Response from GET /api/v1/forex/cfets
 */
export const ForexCFETSResponseSchema = z.object({
  rmb_pairs: z.array(ForexCFETSQuoteSchema).describe('RMB currency pairs'),
  cross_pairs: z.array(ForexCFETSQuoteSchema).describe('Cross currency pairs'),
  last_update: z.string().describe('Last update timestamp'),
  source: z.string().describe('Data source: cfets'),
})

// ── Official Rate Schemas ────────────────────────────────────────────────

/**
 * Official rate from SAFE (State Administration of Foreign Exchange)
 */
export const ForexOfficialRateSchema = z.object({
  date: z.string().describe('Date'),
  usd: z.number().nullable().optional().describe('USD rate'),
  eur: z.number().nullable().optional().describe('EUR rate'),
  jpy: z.number().nullable().optional().describe('JPY rate (100 JPY)'),
  gbp: z.number().nullable().optional().describe('GBP rate'),
  hkd: z.number().nullable().optional().describe('HKD rate'),
  aud: z.number().nullable().optional().describe('AUD rate'),
  cad: z.number().nullable().optional().describe('CAD rate'),
  chf: z.number().nullable().optional().describe('CHF rate'),
})

/**
 * Response from GET /api/v1/forex/official
 */
export const ForexOfficialRateResponseSchema = z.object({
  rates: z.array(ForexOfficialRateSchema).describe('Official rates array'),
  total: z.number().describe('Total number of rates'),
  source: z.string().describe('Data source: safe'),
})

// ── Health Check Schema ──────────────────────────────────────────────────

/**
 * Response from GET /api/v1/forex/health
 */
export const ForexHealthResponseSchema = z.object({
  status: z.string().describe('Service status: ok, error'),
  service: z.string().describe('Service name: forex'),
  cache_size: z.number().optional().describe('Cache entry count'),
  cache_hit_rate: z.number().optional().describe('Cache hit rate'),
  cache_memory_mb: z.number().optional().describe('Cache memory usage in MB'),
  supported_pairs: z.array(z.string()).optional().describe('Supported currency pairs'),
  supported_currencies: z.array(z.string()).optional().describe('Supported currencies'),
  circuit_breaker: z.object({
    is_available: z.boolean(),
    state: z.string(),
    consecutive_failures: z.number(),
  }).optional().describe('Circuit breaker status'),
})

// ── Index Barrel Export ─────────────────────────────────────────────────

export const forexSchemas = {
  // Quote schemas
  ForexQuoteSchema,
  ForexSpotResponseSchema,
  
  // Matrix schemas
  ForexMatrixRateSchema,
  ForexMatrixRowSchema,
  ForexMatrixResponseSchema,
  
  // History schemas
  ForexHistoryDataPointSchema,
  ForexHistoryResponseSchema,
  
  // Conversion schemas
  ForexConvertResponseSchema,
  
  // CFETS schemas
  ForexCFETSQuoteSchema,
  ForexCFETSResponseSchema,
  
  // Official rate schemas
  ForexOfficialRateSchema,
  ForexOfficialRateResponseSchema,
  
  // Utility schemas
  CircuitBreakerSchema,
  ForexHealthResponseSchema,
}

export default forexSchemas
