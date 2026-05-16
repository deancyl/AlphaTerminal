import { z } from 'zod'

// ── Overview Schemas ─────────────────────────────────────────────────

export const GdpOverviewSchema = z.object({
  period: z.string().nullable(),
  value: z.number().nullable(),
  yoy: z.number().nullable(),
  unit: z.string().optional(),
})

export const CpiOverviewSchema = z.object({
  period: z.string().nullable(),
  value: z.number().nullable(),
  yoy: z.number().nullable(),
  mom: z.number().nullable(),
})

export const PpiOverviewSchema = z.object({
  period: z.string().nullable(),
  value: z.number().nullable(),
  yoy: z.number().nullable(),
})

export const PmiOverviewSchema = z.object({
  period: z.string().nullable(),
  manufacturing: z.number().nullable(),
  non_manufacturing: z.number().nullable(),
})

export const M2OverviewSchema = z.object({
  period: z.string().nullable(),
  value: z.number().nullable(),
  yoy: z.number().nullable(),
  unit: z.string().optional(),
})

export const SocialFinancingOverviewSchema = z.object({
  period: z.string().nullable(),
  total: z.number().nullable(),
  yoy: z.number().nullable(),
  unit: z.string().optional(),
})

export const IndustrialProductionOverviewSchema = z.object({
  period: z.string().nullable(),
  yoy: z.number().nullable(),
  unit: z.string().optional(),
})

export const UnemploymentOverviewSchema = z.object({
  period: z.string().nullable(),
  rate: z.number().nullable(),
  unit: z.string().optional(),
})

export const MacroOverviewSchema = z.object({
  overview: z.object({
    gdp: GdpOverviewSchema.nullable(),
    cpi: CpiOverviewSchema.nullable(),
    ppi: PpiOverviewSchema.nullable(),
    pmi: PmiOverviewSchema.nullable(),
    m2: M2OverviewSchema.nullable(),
    social_financing: SocialFinancingOverviewSchema.nullable(),
    industrial_production: IndustrialProductionOverviewSchema.nullable(),
    unemployment: UnemploymentOverviewSchema.nullable(),
  }),
  last_update: z.string(),
})

// ── Time Series Data Point Schemas ───────────────────────────────────

export const GdpDataPointSchema = z.object({
  quarter: z.string(),
  gdp_absolute: z.number().nullable(),
  gdp_yoy: z.number().nullable(),
  primary_yoy: z.number().nullable().optional(),
  secondary_yoy: z.number().nullable().optional(),
  tertiary_yoy: z.number().nullable().optional(),
})

export const CpiDataPointSchema = z.object({
  month: z.string(),
  nation_current: z.number().nullable(),
  nation_yoy: z.number().nullable(),
  nation_mom: z.number().nullable(),
  city_yoy: z.number().nullable().optional(),
  rural_yoy: z.number().nullable().optional(),
})

export const PpiDataPointSchema = z.object({
  month: z.string(),
  yoy: z.number().nullable(),
})

export const PmiDataPointSchema = z.object({
  month: z.string(),
  manufacturing_index: z.number().nullable(),
  non_manufacturing_index: z.number().nullable(),
})

export const M2DataPointSchema = z.object({
  month: z.string(),
  m2_yoy: z.number().nullable(),
})

export const SocialFinancingDataPointSchema = z.object({
  month: z.string(),
  total: z.number().nullable(),
})

export const IndustrialProductionDataPointSchema = z.object({
  month: z.string(),
  yoy: z.number().nullable(),
})

export const UnemploymentDataPointSchema = z.object({
  month: z.string(),
  rate: z.number().nullable(),
})

// ── API Response Wrapper Schemas ─────────────────────────────────────

export const MacroApiResponseSchema = z.object({
  indicator: z.string(),
  name: z.string().optional(),
  unit: z.string().optional(),
  frequency: z.string().optional(),
  data: z.array(z.record(z.any())),
  last_update: z.string(),
})

export const GdpResponseSchema = MacroApiResponseSchema.extend({
  data: z.array(GdpDataPointSchema),
})

export const CpiResponseSchema = MacroApiResponseSchema.extend({
  data: z.array(CpiDataPointSchema),
})

export const PpiResponseSchema = MacroApiResponseSchema.extend({
  data: z.array(PpiDataPointSchema),
})

export const PmiResponseSchema = MacroApiResponseSchema.extend({
  data: z.array(PmiDataPointSchema),
})

export const M2ResponseSchema = MacroApiResponseSchema.extend({
  data: z.array(M2DataPointSchema),
})

export const SocialFinancingResponseSchema = MacroApiResponseSchema.extend({
  data: z.array(SocialFinancingDataPointSchema),
})

export const IndustrialProductionResponseSchema = MacroApiResponseSchema.extend({
  data: z.array(IndustrialProductionDataPointSchema),
})

export const UnemploymentResponseSchema = MacroApiResponseSchema.extend({
  data: z.array(UnemploymentDataPointSchema),
})

// ── Calendar Schema ──────────────────────────────────────────────────

export const MacroCalendarEventSchema = z.object({
  date: z.string(),
  name: z.string(),
  status: z.enum(['released', 'pending']).optional(),
  value: z.number().nullable().optional(),
  unit: z.string().optional(),
})

export const MacroCalendarResponseSchema = z.object({
  calendar: z.array(MacroCalendarEventSchema),
  last_update: z.string().optional(),
})

// ── BFF Dashboard Response Schema ─────────────────────────────────────

export const MacroDashboardResponseSchema = z.object({
  overview: z.object({
    gdp: z.object({
      quarter: z.string().nullable(),
      value: z.number().nullable(),
      yoy: z.number().nullable(),
    }).nullable(),
    cpi: z.object({
      month: z.string().nullable(),
      yoy: z.number().nullable(),
      mom: z.number().nullable(),
    }).nullable(),
    ppi: z.object({
      month: z.string().nullable(),
      yoy: z.number().nullable(),
    }).nullable(),
    pmi: z.object({
      month: z.string().nullable(),
      value: z.number().nullable(),
    }).nullable(),
    m2: z.object({
      month: z.string().nullable(),
      yoy: z.number().nullable(),
    }).nullable(),
  }).nullable(),
  last_update: z.string().nullable(),
  calendar: z.array(z.object({
    date: z.string(),
    event: z.string(),
    importance: z.string(),
  })).nullable(),
  gdp: z.object({
    data: z.array(z.any()),
    unit: z.string(),
    frequency: z.string(),
  }).nullable(),
  cpi: z.object({
    data: z.array(z.any()),
    unit: z.string(),
    frequency: z.string(),
  }).nullable(),
  ppi: z.object({
    data: z.array(z.any()),
    unit: z.string(),
    frequency: z.string(),
  }).nullable(),
  pmi: z.object({
    data: z.array(z.any()),
    unit: z.string(),
    frequency: z.string(),
  }).nullable(),
  m2: z.object({
    data: z.array(z.any()),
    unit: z.string(),
    frequency: z.string(),
  }).nullable(),
  social_financing: z.object({
    data: z.array(z.any()),
    unit: z.string(),
    frequency: z.string(),
  }).nullable(),
  industrial_production: z.object({
    data: z.array(z.any()),
    unit: z.string(),
    frequency: z.string(),
  }).nullable(),
  unemployment: z.object({
    data: z.array(z.any()),
    unit: z.string(),
    frequency: z.string(),
  }).nullable(),
})
