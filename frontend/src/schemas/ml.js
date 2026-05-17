/**
 * ML API Validation Schemas (Zod)
 * 
 * Provides type-safe validation for ML-related API requests and responses.
 */
import { z } from 'zod'

// ═══════════════════════════════════════════════════════════════
// Model Schemas
// ═══════════════════════════════════════════════════════════════

export const ModelTypeSchema = z.enum([
  'LightGBM', 'HIST', 'GATE', 'GRU', 'LSTM', 'MLP', 'XGBoost', 'CatBoost', 'Custom'
])

export const ModelProviderSchema = z.enum(['qlib', 'sklearn', 'custom'])

export const FeatureSetSchema = z.enum(['Alpha158', 'Alpha360', 'Custom'])

export const ModelSchema = z.object({
  model_id: z.string().min(1).max(100),
  model_type: ModelTypeSchema,
  provider: ModelProviderSchema,
  feature_set: FeatureSetSchema,
  created_at: z.string(),
  updated_at: z.string(),
  metrics: z.record(z.number()).optional(),
  params: z.record(z.any()).optional(),
  is_loaded: z.boolean(),
})

// ═══════════════════════════════════════════════════════════════
// Training Schemas
// ═══════════════════════════════════════════════════════════════

export const StockSymbolSchema = z.string().regex(
  /^(sh|sz)[0-9]{6}$/,
  '股票代码格式错误，应为 sh/sz + 6位数字（如 sh600519）'
)

export const DateSchema = z.string().regex(
  /^\d{4}-\d{2}-\d{2}$/,
  '日期格式错误，应为 YYYY-MM-DD'
)

export const TrainRequestSchema = z.object({
  model_id: z.string().min(1, '模型ID不能为空'),
  symbol: StockSymbolSchema,
  start_date: DateSchema,
  end_date: DateSchema,
  feature_set: z.enum(['Alpha158', 'Alpha360']).optional().default('Alpha158'),
  target: z.string().optional().default('return_1d'),
  params: z.record(z.any()).optional(),
})

// ═══════════════════════════════════════════════════════════════
// Prediction Schemas
// ═══════════════════════════════════════════════════════════════

export const PredictRequestSchema = z.object({
  model_id: z.string().min(1, '模型ID不能为空'),
  symbol: StockSymbolSchema,
  start_date: DateSchema,
  end_date: DateSchema,
})

export const PredictionResultSchema = z.object({
  date: z.string(),
  close: z.number(),
  prediction: z.number(),
  signal: z.number().min(-1).max(1),
})

// ═══════════════════════════════════════════════════════════════
// Portfolio Optimization Schemas
// ═══════════════════════════════════════════════════════════════

export const OptimizationMethodSchema = z.enum(['gmv', 'mvo', 'rp', 'inv'])

export const PortfolioOptimizeRequestSchema = z.object({
  symbols: z.array(StockSymbolSchema).min(1, '至少需要1个股票').max(50, '最多50个股票'),
  start_date: DateSchema,
  end_date: DateSchema,
  method: OptimizationMethodSchema.optional().default('mvo'),
  risk_aversion: z.number().min(0).max(10).optional().default(1.0),
  turnover_limit: z.number().min(0).max(1).optional().default(0.2),
  target_return: z.number().optional(),
  max_weight: z.number().min(0.01).max(1).optional().default(0.3),
})

export const PortfolioOptimizeResultSchema = z.object({
  weights: z.record(z.number()),
  expected_return: z.number(),
  expected_volatility: z.number(),
  sharpe_ratio: z.number(),
  method: OptimizationMethodSchema,
  symbols_count: z.number(),
  optimization_date: z.string(),
})

// ═══════════════════════════════════════════════════════════════
// Factor Analysis Schemas
// ═══════════════════════════════════════════════════════════════

export const FactorNameSchema = z.enum(['momentum', 'value', 'quality', 'size', 'volatility'])

export const FactorAnalysisRequestSchema = z.object({
  symbol: StockSymbolSchema,
  start_date: DateSchema,
  end_date: DateSchema,
  factors: z.array(FactorNameSchema).optional().default(['momentum', 'value', 'quality', 'size', 'volatility']),
})

export const FactorExposureSchema = z.object({
  beta: z.number(),
  t_stat: z.number(),
  p_value: z.number(),
  r_squared: z.number(),
})

export const FactorICSchema = z.object({
  ic: z.number(),
  rank_ic: z.number(),
})

export const FactorAnalysisResultSchema = z.object({
  symbol: z.string(),
  start_date: z.string(),
  end_date: z.string(),
  exposures: z.record(FactorExposureSchema),
  ic_values: z.record(FactorICSchema),
  data_points: z.number(),
  analysis_date: z.string(),
})

// ═══════════════════════════════════════════════════════════════
// Risk Metrics Schemas
// ═══════════════════════════════════════════════════════════════

export const RiskMetricsRequestSchema = z.object({
  daily_returns: z.array(z.number()).min(10, '至少需要10个收益数据'),
  freq: z.enum(['day', 'week', 'month']).optional().default('day'),
  annual_periods: z.number().min(1).optional().default(252),
})

export const RiskMetricsResultSchema = z.object({
  annualized_return: z.number(),
  annualized_volatility: z.number(),
  sharpe_ratio: z.number(),
  max_drawdown: z.number(),
  win_rate: z.number(),
  total_trades: z.number(),
  freq: z.string(),
})

// ═══════════════════════════════════════════════════════════════
// API Response Wrapper
// ═══════════════════════════════════════════════════════════════

export const APIResponseSchema = <T extends z.ZodTypeAny>(dataSchema: T) =>
  z.object({
    code: z.number(),
    message: z.string().optional(),
    data: dataSchema.optional(),
  })

// ═══════════════════════════════════════════════════════════════
// Helper Functions
// ═══════════════════════════════════════════════════════════════

/**
 * Validate and parse API response with schema
 */
export function validateResponse<T>(schema: z.ZodSchema<T>, response: unknown): T {
  const result = schema.safeParse(response)
  if (!result.success) {
    console.error('[ML Schema] Validation error:', result.error.errors)
    throw new Error(`Validation error: ${result.error.errors[0]?.message || 'Unknown error'}`)
  }
  return result.data
}

/**
 * Validate request body before sending
 */
export function validateRequest<T>(schema: z.ZodSchema<T>, data: unknown): T {
  const result = schema.safeParse(data)
  if (!result.success) {
    throw new Error(`Invalid request: ${result.error.errors[0]?.message || 'Unknown error'}`)
  }
  return result.data
}
