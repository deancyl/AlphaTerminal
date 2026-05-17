import { z } from 'zod'

// ── Yield Curve Data Point Schema ─────────────────────────────────────

export const YieldCurvePointSchema = z.object({
  tenor: z.string(), // 期限，如 "1Y", "5Y", "10Y"
  yield: z.number().nullable(), // 收益率 (%)
})

// ── Bond Curve Response Schema ────────────────────────────────────────

export const BondCurveResponseSchema = z.object({
  yield_curve: z.array(YieldCurvePointSchema), // 当前收益率曲线
  yield_curve_1m: z.array(YieldCurvePointSchema).optional(), // 1个月前曲线
  yield_curve_1y: z.array(YieldCurvePointSchema).optional(), // 1年前曲线
  comm_yield: z.array(YieldCurvePointSchema).optional(), // 商业银行AAA收益率
  spreads_bps: z.record(z.number().nullable()).optional(), // 利差(bps)
  update_time: z.string().nullable(), // 更新时间
  source: z.string().optional(), // 数据来源
})

// ── Yield Curve Only Response Schema ──────────────────────────────────

export const YieldCurveResponseSchema = z.object({
  yield_curve: z.array(YieldCurvePointSchema),
  update_time: z.string().nullable(),
  source: z.string().optional(),
})

// ── Active Bond Schema ────────────────────────────────────────────────

export const ActiveBondSchema = z.object({
  code: z.string(), // 债券代码
  name: z.string(), // 债券名称
  rate: z.number().nullable(), // 票面利率 (%)
  ytm: z.number().nullable(), // 到期收益率 (%)
  change_bps: z.number().nullable(), // 变动基点 (bps)
  type: z.string().optional(), // 债券类型
})

export const ActiveBondsResponseSchema = z.object({
  bonds: z.array(ActiveBondSchema),
})

// ── Bond History Data Point Schema ────────────────────────────────────

export const BondHistoryPointSchema = z.object({
  date: z.string(), // 日期
  yield: z.number().nullable(), // 收益率 (%)
})

export const BondHistoryResponseSchema = z.object({
  tenor: z.string(), // 期限
  current: z.number().nullable(), // 当前收益率
  percentile: z.number().nullable().optional(), // 历史分位数
  history: z.array(BondHistoryPointSchema), // 历史数据
})

// ── Spread Matrix Schema ──────────────────────────────────────────────

export const SpreadMatrixSchema = z.object({
  tenor: z.string(), // 期限
  treasury: z.number().nullable(), // 国债收益率
  policy_bank: z.number().nullable().optional(), // 政策性金融债
  commercial_aaa: z.number().nullable().optional(), // 商业银行AAA
  spread_treasury_policy: z.number().nullable().optional(), // 国开-国债利差
  spread_treasury_comm: z.number().nullable().optional(), // 商A-国债利差
})

export const SpreadMatrixResponseSchema = z.object({
  matrix: z.array(SpreadMatrixSchema),
  update_time: z.string().nullable(),
  source: z.string().optional(),
})

// ── Term Spread Schema (10Y-2Y) ───────────────────────────────────────

export const TermSpreadPointSchema = z.object({
  date: z.string(),
  spread_bps: z.number().nullable(), // 期限利差 (bps)
  inverted: z.boolean().optional(), // 是否倒挂
})

export const TermSpreadResponseSchema = z.object({
  data: z.array(TermSpreadPointSchema),
  current_spread: z.number().nullable().optional(),
  is_inverted: z.boolean().optional(),
  update_time: z.string().nullable(),
})
