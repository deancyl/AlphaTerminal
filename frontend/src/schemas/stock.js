import { z } from 'zod'

export const StockQuoteSchema = z.object({
  symbol: z.string(),
  name: z.string(),
  price: z.number().finite(),
  change: z.number().finite(),
  changePercent: z.number().finite(),
  volume: z.number().nonnegative(),
  amount: z.number().nonnegative().optional(),
  high: z.number().finite().optional(),
  low: z.number().finite().optional(),
  open: z.number().finite().optional(),
  prevClose: z.number().finite().optional(),
  turnover: z.number().nonnegative().optional(),
  time: z.string().optional(),
})

export const StockQuoteListSchema = z.array(StockQuoteSchema)

export const MarketOverviewSchema = z.object({
  index: z.string(),
  price: z.number().finite(),
  change: z.number().finite(),
  changePercent: z.number().finite(),
  volume: z.number().nonnegative(),
  amount: z.number().nonnegative(),
})

export const SectorSchema = z.object({
  name: z.string(),
  change: z.number().finite(),
  changePercent: z.number().finite(),
  leadingStock: z.string().optional(),
  leadingStockChange: z.number().finite().optional(),
})

export const SectorListSchema = z.array(SectorSchema)
