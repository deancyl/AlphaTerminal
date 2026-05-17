import { z } from 'zod'

// ── Index Futures Schemas ──────────────────────────────────────────────

export const IndexFutureSchema = z.object({
  symbol: z.string(),
  name: z.string(),
  price: z.number().nullable(),
  change_pct: z.number().nullable(),
  position: z.number().nullable().optional(),
  note: z.string().optional(),
})

export const MainIndexesResponseSchema = z.object({
  index_futures: z.array(IndexFutureSchema),
})

// ── Commodities Schemas ────────────────────────────────────────────────

export const CommoditySchema = z.object({
  symbol: z.string(),
  name: z.string(),
  unit: z.string().optional(),
  price: z.number().nullable(),
  change_pct: z.number().nullable(),
  tick: z.number().optional(),
  sector: z.string().optional(),
})

export const CommoditiesResponseSchema = z.object({
  commodities: z.array(CommoditySchema),
})

// ── Index History Schemas ───────────────────────────────────────────────

export const IndexHistoryPointSchema = z.object({
  date: z.string(),
  open: z.number().nullable(),
  close: z.number().nullable(),
  high: z.number().nullable(),
  low: z.number().nullable(),
  volume: z.number().nullable().optional(),
  hold: z.number().nullable().optional(),
})

export const IndexHistoryResponseSchema = z.object({
  symbol: z.string(),
  period: z.string(),
  history: z.array(IndexHistoryPointSchema),
})

// ── Term Structure Schemas ──────────────────────────────────────────────

export const TermStructurePointSchema = z.object({
  contract: z.string(),
  month: z.string().optional(),
  price: z.number().nullable(),
  oi: z.number().nullable().optional(),
})

export const TermStructureResponseSchema = z.object({
  symbol: z.string(),
  name: z.string().optional(),
  term_structure: z.array(TermStructurePointSchema),
})

// ── API Response Wrapper ────────────────────────────────────────────────

export const FuturesApiResponseSchema = z.object({
  code: z.number().optional(),
  message: z.string().optional(),
  data: z.union([
    MainIndexesResponseSchema,
    CommoditiesResponseSchema,
    IndexHistoryResponseSchema,
    TermStructureResponseSchema,
  ]),
})
