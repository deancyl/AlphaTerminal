import { z } from 'zod'

export const MacroIndicatorSchema = z.object({
  name: z.string(),
  value: z.number(),
  unit: z.string().optional(),
  period: z.string().optional(),
  change: z.number().optional(),
  changePercent: z.number().optional(),
})

export const MacroOverviewSchema = z.object({
  indicators: z.array(MacroIndicatorSchema),
  lastUpdate: z.string().optional(),
})

export const MacroCalendarEventSchema = z.object({
  date: z.string(),
  event: z.string(),
  importance: z.enum(['high', 'medium', 'low']).optional(),
  forecast: z.number().optional(),
  actual: z.number().optional(),
  previous: z.number().optional(),
})

export const MacroCalendarSchema = z.array(MacroCalendarEventSchema)

export const MacroTimeSeriesSchema = z.object({
  date: z.string(),
  value: z.number(),
})

export const MacroDataSchema = z.object({
  indicator: z.string(),
  unit: z.string().optional(),
  data: z.array(MacroTimeSeriesSchema),
})
