import { z } from 'zod'

export const PortfolioHoldingSchema = z.object({
  symbol: z.string(),
  name: z.string().optional(),
  shares: z.number().positive(),
  avgCost: z.number().nonnegative(),
  currentPrice: z.number().nonnegative().optional(),
  marketValue: z.number().nonnegative().optional(),
  profit: z.number().optional(),
  profitPercent: z.number().optional(),
})

export const PortfolioSchema = z.object({
  id: z.string().optional(),
  name: z.string(),
  description: z.string().optional(),
  holdings: z.array(PortfolioHoldingSchema),
  cash: z.number().nonnegative(),
  totalValue: z.number().nonnegative(),
  totalCost: z.number().nonnegative(),
  totalProfit: z.number().optional(),
  totalProfitPercent: z.number().optional(),
  createdAt: z.string().optional(),
  updatedAt: z.string().optional(),
})

export const PortfolioListSchema = z.array(PortfolioSchema)

export const PortfolioSummarySchema = z.object({
  totalValue: z.number().nonnegative(),
  totalCost: z.number().nonnegative(),
  totalProfit: z.number(),
  totalProfitPercent: z.number(),
  holdingsCount: z.number().int().nonnegative(),
  cashRatio: z.number().min(0).max(1).optional(),
})
