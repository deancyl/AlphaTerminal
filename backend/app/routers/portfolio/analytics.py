"""
Portfolio Analytics Router - Attribution, Performance, Risk, Benchmark

This module contains analytics endpoints extracted from portfolio.py:
- GET /{portfolio_id}/attribution - Asset attribution analysis
- GET /{portfolio_id}/performance - Performance metrics (Sharpe, Sortino, etc.)
- GET /{portfolio_id}/risk - Risk metrics (VaR, CVaR)
- GET /{portfolio_id}/benchmark - Benchmark comparison analysis
"""

import asyncio
import math
import sqlite3
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from statistics import mean, stdev, NormalDist

from app.db.database import _get_conn
from app.utils.response import success_response
from app.middleware import require_api_key

logger = logging.getLogger(__name__)

router = APIRouter(tags=["portfolio-analytics"])

# Timeout constant for all portfolio endpoints
PORTFOLIO_TIMEOUT = 30  # seconds


# ══════════════════════════════════════════════════════════════
#  Helper: Asset Classification
# ══════════════════════════════════════════════════════════════

def _classify_asset(symbol: str, name: str = "") -> dict:
    """
    根据 symbol + name 推断底层资产类型与细分板块。
    返回: { category, sub_category, is_index }
    """
    sym = symbol.strip().lower()
    name_lower = name.lower()
    raw_code = sym.removeprefix("sh").removeprefix("sz").removeprefix("hk").removeprefix("us").removeprefix("jp").removeprefix("bj")

    # ── 固收：国债/国开债/地方债 ────────────────────────────────
    if any(kw in name_lower for kw in ["国债", "国开", "地方债", "政金债", "债券", "债"]):
        return {"category": "bond", "sub_category": "利率债", "is_index": False}

    # ── 商品期货 ────────────────────────────────────────────────
    if raw_code.upper() in ("AU", "AG", "CU", "AL", "ZN", "PB", "NI", "SN",
                             "RU", "RB", "HC", "I", "J", "JM", "焦煤",
                             "原油", "燃油", "沥青", "棕榈", "豆油", "菜油",
                             "棉花", "白糖", "苹果", "红枣"):
        return {"category": "futures", "sub_category": "商品期货", "is_index": False}
    if any(kw in name_lower for kw in ["黄金", "白银", "铜", "铝", "锌", "镍", "螺纹", "铁矿石", "焦炭", "原油"]):
        return {"category": "futures", "sub_category": "商品期货", "is_index": False}

    # ── 货币基金 / 现金管理 ────────────────────────────────────
    if raw_code.startswith("51") and len(raw_code) == 6:
        return {"category": "money_fund", "sub_category": "货币基金", "is_index": False}

    # ── 宽基指数 ETF（代码特征）─────────────────────────────────
    if raw_code.startswith("51") or raw_code.startswith("15") or raw_code.startswith("56"):
        return {"category": "etf", "sub_category": "宽基ETF", "is_index": True}
    if raw_code in ("000001", "000300", "000016", "000688", "000905", "000852",
                    "399001", "399006", "399100", "399005", "399673"):
        return {"category": "index", "sub_category": "A股指数", "is_index": True}

    # ── 港股 ────────────────────────────────────────────────────
    if sym.startswith("hk"):
        return {"category": "hk_stock", "sub_category": "港股", "is_index": False}

    # ── A股（sh6 / sz0,3 开头个股）───────────────────────────────
    if raw_code.startswith("6") or raw_code.startswith("0") or raw_code.startswith("3"):
        return {"category": "a_stock", "sub_category": "A股个股", "is_index": False}

    return {"category": "other", "sub_category": "其他", "is_index": False}


# ══════════════════════════════════════════════════════════════
#  Attribution Analysis
# ══════════════════════════════════════════════════════════════

@router.get("/{portfolio_id}/attribution")
async def get_attribution(portfolio_id: int, include_children: bool = Query(False)):
    """
    底层资产归因 + 组合风险（VaR / 波动率估算）。

    分类规则：
      - sh510xxx / sz159xxx → 宽基ETF
      - sh000xxx / sz399xxx → A股指数
      - 国债/国开/债券关键词 → 利率债
      - AU/AG/黄金/白银 等 → 商品期货
      - sh6xxxxx / sz0/3xxxx → A股个股
      - hkxxxxx → 港股

    返回:
      - attribution[]   各底层资产组的权重、收益贡献
      - risk_metrics     日VaR(95%)、年化波动率、夏普比率
      - total_exposure   各 category 的总仓位占比
    """
    async def _inner():
        from app.services.sentiment_engine import SpotCache

        # ── 1. 获取持仓（WAL 模式并发读）────────────────────────────
        conn = _get_conn()
        try:
            if include_children:
                all_ids = [portfolio_id]
                cur = conn.execute("SELECT id FROM portfolios WHERE parent_id=?", (portfolio_id,)).fetchall()
                all_ids += [r[0] for r in cur]
                ph = ','.join(['?'] * len(all_ids))
                rows = conn.execute(
                    f"SELECT symbol, shares, avg_cost FROM positions WHERE portfolio_id IN ({ph})",
                    tuple(all_ids)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT symbol, shares, avg_cost FROM positions WHERE portfolio_id=?",
                    (portfolio_id,)
                ).fetchall()
        finally:
            conn.close()

        if not rows:
            return success_response({"attribution": [], "risk_metrics": None, "total_exposure": []})

        # ── 2. 获取最新价格 ────────────────────────────────────────
        spot = SpotCache.get_stocks()
        price_map = {}
        for s in spot:
            code = s.get("code", "")
            price_map[code] = s
            if len(code) > 2:
                price_map[code[2:]] = s
                price_map[code.lower()] = s
                price_map[code.upper()] = s

        if len(price_map) < 10:
            conn2 = _get_conn()
            try:
                db_rows = conn2.execute(
                    "SELECT symbol, name, price, change_pct FROM market_all_stocks WHERE price > 0"
                ).fetchall()
                for r in db_rows:
                    sym, name, price, chg_pct = r
                    price_map[sym] = {"code": sym, "name": name, "price": float(price or 0), "chg_pct": float(chg_pct or 0)}
                    if len(sym) > 2:
                        price_map[sym[2:]] = price_map[sym]
            finally:
                conn2.close()

        # ── 3. 逐条计算持仓盈亏并分类 ──────────────────────────────
        groups = {}

        for symbol, shares, avg_cost in rows:
            info = price_map.get(symbol, {}) or {}
            if not info and len(symbol) == 6:
                info = price_map.get(f"sh{symbol}", {}) or {}
                if not info:
                    info = price_map.get(f"sz{symbol}", {}) or {}
            if not info:
                info = price_map.get(symbol[2:]) if len(symbol) > 2 else {}

            price        = info.get("price", avg_cost)
            name         = info.get("name", symbol)
            market_value = shares * price
            cost         = shares * avg_cost
            pnl          = market_value - cost
            pnl_pct      = (pnl / cost * 100) if cost > 0 else 0.0

            cls = _classify_asset(symbol, name)
            cat = cls["category"]

            if cat not in groups:
                groups[cat] = {
                    "category":     cat,
                    "sub_category": cls["sub_category"],
                    "is_index":     cls["is_index"],
                    "market_value": 0.0,
                    "cost":         0.0,
                    "pnl":          0.0,
                    "positions":    [],
                }
            groups[cat]["market_value"] += market_value
            groups[cat]["cost"]         += cost
            groups[cat]["pnl"]          += pnl
            groups[cat]["positions"].append({
                "symbol":       symbol,
                "name":         name,
                "shares":       shares,
                "avg_cost":     avg_cost,
                "price":        price,
                "market_value": round(market_value, 2),
                "cost":         round(cost, 2),
                "pnl":          round(pnl, 2),
                "pnl_pct":      round(pnl_pct, 2),
            })

        # ── 4. 汇总计算（防御性容错）──────────────────────────────
        try:
            total_mv    = sum(g["market_value"] for g in groups.values())
            total_cost  = sum(g["cost"]        for g in groups.values())
            total_pnl   = sum(g["pnl"]         for g in groups.values())

            # 极端边界：所有持仓市值和盈亏均为 0（价格全失效），返回空数据避免后续除零
            if total_mv <= 0 and total_pnl == 0:
                return success_response({"attribution": [], "risk_metrics": None, "total_exposure": [],
                            "summary": {"total_market_value": 0, "total_cost": 0, "total_pnl": 0, "total_pnl_pct": 0}})

            attribution = []
            for g in groups.values():
                w  = g["market_value"] / total_mv if total_mv > 0 else 0
                pc = g["pnl"] / total_pnl * 100   if total_pnl != 0 else 0
                attribution.append({
                    "category":        g["category"],
                    "sub_category":    g["sub_category"],
                    "is_index":        g["is_index"],
                    "market_value":    round(g["market_value"], 2),
                    "cost":            round(g["cost"], 2),
                    "pnl":             round(g["pnl"], 2),
                    "weight":          round(w * 100, 2),
                    "pnl_contrib_pct": round(pc, 2),
                    "position_count":  len(g["positions"]),
                    "positions":       g["positions"][:5],
                })

            attribution.sort(key=lambda x: x["market_value"], reverse=True)

            # ── 5. 底层资产配置 ─────────────────────────────────────
            total_exposure = [
                {"name": g["sub_category"], "category": g["category"],
                 "value": round(g["market_value"], 2), "weight": round(g["market_value"] / total_mv * 100, 2)}
                for g in sorted(groups.values(), key=lambda x: x["market_value"], reverse=True)
            ]

            # ── 6. 风险指标 ─────────────────────────────────────────
            risk_metrics = None
            try:
                conn3 = _get_conn()
                try:
                    snap_rows = conn3.execute(
                        "SELECT date, total_asset FROM portfolio_snapshots WHERE portfolio_id=? ORDER BY date ASC LIMIT 60",
                        (portfolio_id,)
                    ).fetchall()
                finally:
                    conn3.close()

                if snap_rows and len(snap_rows) >= 5:
                    assets  = [float(r[1]) for r in snap_rows]
                    returns = [(assets[i] - assets[i-1]) / assets[i-1]
                               for i in range(1, len(assets)) if assets[i-1] > 0]

                    if returns:
                        mean_ret  = sum(returns) / len(returns)
                        variance  = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
                        daily_vol = math.sqrt(variance)
                        ann_vol   = daily_vol * math.sqrt(252)

                        try:
                            z_95 = NormalDist().inv_cdf(0.95)
                        except Exception:
                            logger.debug("[Portfolio Attribution] NormalDist 不可用，使用默认 z_95=1.645")
                            z_95 = 1.645

                        latest_asset = assets[-1]
                        var_daily_95 = latest_asset * z_95 * daily_vol

                        risk_free     = 0.03
                        years         = max(len(assets) / 252, 0.01)
                        total_ret     = (assets[-1] - assets[0]) / assets[0]
                        ann_ret       = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0
                        sharpe        = (ann_ret - risk_free) / ann_vol if ann_vol > 0 else 0

                        risk_metrics = {
                            "var_daily_95":      round(var_daily_95, 2),
                            "var_daily_95_pct": round(var_daily_95 / latest_asset * 100, 2),
                            "annual_volatility": round(ann_vol * 100, 2),
                            "sharpe_ratio":      round(sharpe, 2),
                            "total_return_pct":  round(total_ret * 100, 2),
                            "annual_return_pct": round(ann_ret * 100, 2),
                            "days":              len(assets),
                        }
            except sqlite3.OperationalError as e:
                logger.warning(f"[Attribution] 数据库操作错误，无法读取快照数据: {e}")
            except ValueError as e:
                logger.warning(f"[Attribution] 风险指标计算错误（数据格式问题）: {e}")
            except ZeroDivisionError as e:
                logger.warning(f"[Attribution] 风险指标计算错误（除零）: {e}")
            except Exception as e:
                logger.warning(f"[Attribution] risk_metrics error: {e}")

            return success_response({
                "attribution":    attribution,
                "total_exposure":  total_exposure,
                "risk_metrics":    risk_metrics,
                "summary": {
                    "total_market_value": round(total_mv, 2),
                    "total_cost":        round(total_cost, 2),
                    "total_pnl":         round(total_pnl, 2),
                    "total_pnl_pct":     round((total_pnl / total_cost * 100) if total_cost else 0, 2),
                },
            })

        except sqlite3.OperationalError as e:
            logger.error(f"[Attribution] 数据库操作错误: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="数据库操作失败，请稍后重试")
        except ValueError as e:
            logger.error(f"[Attribution] 数据格式错误: {e}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"数据格式错误: {str(e)}")
        except ZeroDivisionError as e:
            logger.error(f"[Attribution] 计算错误（除零）: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="归因计算时发生除零错误，请检查数据")
        except Exception as e:
            logger.error(f"[Attribution] 计算异常: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="归因计算时发生错误，请检查是否有异常交易数据")
    
    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(504, "Attribution analysis timeout")


# ══════════════════════════════════════════════════════════════
#  Performance Metrics
# ══════════════════════════════════════════════════════════════

@router.get("/{portfolio_id}/performance")
async def get_performance_metrics(portfolio_id: int, benchmark: str = "000300"):
    """
    计算组合的业绩评价指标
    
    - **benchmark**: 基准指数代码（默认000300沪深300）
    
    返回指标：
    - 夏普比率、特雷诺比率、詹森阿尔法
    - 最大回撤、索提诺比率、卡玛比率
    - 胜率、Beta、Alpha
    """
    async def _inner():
        conn = _get_conn()
        try:
            # 1. 获取组合历史净值（最近252个交易日，约1年）
            rows = conn.execute(
                """SELECT date, total_asset FROM portfolio_snapshots 
                   WHERE portfolio_id=? ORDER BY date ASC LIMIT 252""",
                (portfolio_id,)
            ).fetchall()
            
            if not rows or len(rows) < 30:
                return success_response({
                    "metrics": None,
                    "message": "历史数据不足（需要至少30个交易日）",
                    "days": len(rows) if rows else 0
                })
            
            portfolio_dates = [r[0] for r in rows]
            portfolio_assets = [float(r[1]) for r in rows]
            
            # 2. 计算组合日收益率
            portfolio_returns = []
            for i in range(1, len(portfolio_assets)):
                if portfolio_assets[i-1] > 0:
                    portfolio_returns.append((portfolio_assets[i] - portfolio_assets[i-1]) / portfolio_assets[i-1])
            
            # 3. 获取基准历史数据
            benchmark_symbol = f"sh{benchmark}" if benchmark.startswith('000') else f"sz{benchmark}"
            bench_rows = conn.execute(
                """SELECT date, close FROM market_data_daily 
                   WHERE symbol=? AND date >= ? AND date <= ? ORDER BY date ASC""",
                (benchmark_symbol, portfolio_dates[0], portfolio_dates[-1])
            ).fetchall()
            
            # 如果找不到基准数据，使用简化计算（无Beta/Alpha/特雷诺）
            benchmark_returns = []
            if bench_rows and len(bench_rows) >= 30:
                bench_prices = [float(r[1]) for r in bench_rows]
                for i in range(1, len(bench_prices)):
                    if bench_prices[i-1] > 0:
                        benchmark_returns.append((bench_prices[i] - bench_prices[i-1]) / bench_prices[i-1])
            
            # 4. 计算各项指标
            n = len(portfolio_returns)
            if n < 5:
                return success_response({"metrics": None, "message": "收益率数据不足", "days": n})
            
            avg_return = mean(portfolio_returns)
            std_return = stdev(portfolio_returns) if n > 1 else 0
            
            # 年化
            ann_return = avg_return * 252
            ann_volatility = std_return * math.sqrt(252)
            
            # 无风险利率（假设3%）
            risk_free = 0.03 / 252  # 日度
            risk_free_ann = 0.03
            
            # 夏普比率
            sharpe = (ann_return - risk_free_ann) / ann_volatility if ann_volatility > 0 else 0
            
            # 最大回撤
            peak = portfolio_assets[0]
            max_dd = 0
            for asset in portfolio_assets:
                if asset > peak:
                    peak = asset
                dd = (peak - asset) / peak if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd
            
            # 索提诺比率（下行波动率）
            downside_returns = [r for r in portfolio_returns if r < 0]
            downside_std = stdev(downside_returns) * math.sqrt(252) if len(downside_returns) > 1 else 0.0001
            sortino = (ann_return - risk_free_ann) / downside_std if downside_std > 0 else 0
            
            # 卡玛比率
            calmar = ann_return / max_dd if max_dd > 0 else 0
            
            # 胜率（正收益天数占比）
            win_rate = len([r for r in portfolio_returns if r > 0]) / n if n > 0 else 0
            
            metrics = {
                "sharpe_ratio": round(sharpe, 2),
                "sortino_ratio": round(sortino, 2),
                "calmar_ratio": round(calmar, 2),
                "max_drawdown": round(max_dd * 100, 2),  # 百分比
                "annual_return": round(ann_return * 100, 2),  # 百分比
                "annual_volatility": round(ann_volatility * 100, 2),  # 百分比
                "win_rate": round(win_rate * 100, 2),  # 百分比
                "total_days": n,
            }
            
            # 如果有基准数据，计算Beta、Alpha、特雷诺、詹森阿尔法
            if len(benchmark_returns) >= 5:
                min_len = min(len(portfolio_returns), len(benchmark_returns))
                p_rets = portfolio_returns[-min_len:]
                b_rets = benchmark_returns[-min_len:]
                
                # Beta = Cov(p, b) / Var(b)
                b_mean = mean(b_rets)
                p_mean = mean(p_rets)
                
                cov_pb = sum((p - p_mean) * (b - b_mean) for p, b in zip(p_rets, b_rets)) / min_len
                var_b = sum((b - b_mean) ** 2 for b in b_rets) / min_len
                
                beta = cov_pb / var_b if var_b > 0 else 1.0
                
                # 詹森阿尔法 = 组合实际收益 - [无风险收益 + Beta * (基准收益 - 无风险收益)]
                b_ann_return = b_mean * 252
                alpha = ann_return - (risk_free_ann + beta * (b_ann_return - risk_free_ann))
                
                # 特雷诺比率 = (组合年化收益 - 无风险利率) / Beta
                treynor = (ann_return - risk_free_ann) / beta if beta != 0 else 0
                
                # 信息比率
                tracking_errors = [p - b for p, b in zip(p_rets, b_rets)]
                te_std = stdev(tracking_errors) * math.sqrt(252) if len(tracking_errors) > 1 else 0.0001
                info_ratio = (ann_return - b_ann_return) / te_std if te_std > 0 else 0
                
                metrics.update({
                    "beta": round(beta, 2),
                    "alpha": round(alpha * 100, 2),  # 百分比
                    "treynor_ratio": round(treynor, 2),
                    "information_ratio": round(info_ratio, 2),
                    "benchmark_return": round(b_ann_return * 100, 2),  # 百分比
                })
            else:
                metrics.update({
                    "beta": None,
                    "alpha": None,
                    "treynor_ratio": None,
                    "information_ratio": None,
                    "benchmark_return": None,
                })
            
            return success_response({
                "metrics": metrics,
                "portfolio_id": portfolio_id,
                "benchmark": benchmark,
                "period": f"{portfolio_dates[0]} ~ {portfolio_dates[-1]}",
            })
            
        finally:
            conn.close()
    
    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(504, "Performance metrics timeout")
    except sqlite3.OperationalError as e:
        logger.error(f"[Performance] 数据库操作错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"数据库操作失败: {str(e)}")
    except ValueError as e:
        logger.error(f"[Performance] 数据格式错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"数据格式错误: {str(e)}")
    except ZeroDivisionError as e:
        logger.error(f"[Performance] 计算错误（除零）: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="业绩评价计算失败：除零错误")
    except Exception as e:
        logger.error(f"[Performance] 计算异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"业绩评价计算失败: {str(e)}")


# ══════════════════════════════════════════════════════════════
#  Risk Metrics (VaR/CVaR)
# ══════════════════════════════════════════════════════════════

@router.get("/{portfolio_id}/risk")
async def get_risk_metrics(portfolio_id: int, confidence: float = 0.95, horizon: int = 1):
    """
    计算组合的风险价值（VaR）和条件风险价值（CVaR）
    
    - **confidence**: 置信水平（默认0.95，支持0.90/0.95/0.99）
    - **horizon**: 持有期（天数，默认1天）
    
    返回指标：
    - VaR（历史模拟法、参数法、蒙特卡洛法）
    - CVaR（Expected Shortfall）
    - 风险贡献度
    """
    async def _inner():
        conn = _get_conn()
        try:
            # 1. 获取组合历史净值（最近252个交易日）
            rows = conn.execute(
                """SELECT date, total_asset FROM portfolio_snapshots 
                   WHERE portfolio_id=? ORDER BY date ASC LIMIT 252""",
                (portfolio_id,)
            ).fetchall()
            
            if not rows or len(rows) < 30:
                return success_response({
                    "risk": None,
                    "message": "历史数据不足（需要至少30个交易日）",
                    "days": len(rows) if rows else 0
                })
            
            assets = [float(r[1]) for r in rows]
            
            # 2. 计算日收益率
            returns = []
            for i in range(1, len(assets)):
                if assets[i-1] > 0:
                    returns.append((assets[i] - assets[i-1]) / assets[i-1])
            
            if len(returns) < 5:
                return success_response({"risk": None, "message": "收益率数据不足", "days": len(returns)})
            
            n = len(returns)
            current_asset = assets[-1]
            
            # 3. 历史模拟法 VaR
            sorted_returns = sorted(returns)
            var_idx = int(n * (1 - confidence))
            var_historical = sorted_returns[var_idx] if var_idx < n else sorted_returns[0]
            
            # 4. 参数法 VaR（假设正态分布）
            avg_ret = mean(returns)
            std_ret = stdev(returns) if n > 1 else 0
            
            try:
                z_score = NormalDist().inv_cdf(confidence)
            except Exception:
                # 常用置信水平的Z值
                z_map = {0.90: 1.282, 0.95: 1.645, 0.99: 2.326}
                z_score = z_map.get(confidence, 1.645)
            
            var_parametric = -(avg_ret - z_score * std_ret)
            
            # 5. CVaR（条件风险价值）= 超过VaR时的平均损失
            cvar_returns = [r for r in returns if r <= var_historical]
            cvar_historical = mean(cvar_returns) if cvar_returns else var_historical
            
            # 参数法 CVaR
            # CVaR = mu - sigma * phi(z) / (1-alpha)，其中phi(z)是标准正态PDF
            from math import exp, sqrt, pi
            pdf_z = (1 / sqrt(2 * pi)) * exp(-0.5 * z_score ** 2)
            cvar_parametric = -(avg_ret - std_ret * (pdf_z / (1 - confidence)))
            
            # 6. 多期调整（平方根法则）
            horizon_factor = math.sqrt(horizon)
            var_multi_period = var_parametric * horizon_factor
            cvar_multi_period = cvar_parametric * horizon_factor
            
            # 7. 风险指标汇总
            risk = {
                "current_asset": round(current_asset, 2),
                "confidence_level": confidence,
                "horizon_days": horizon,
                "total_days": n,
                
                # VaR
                "var_historical_pct": round(-var_historical * 100, 2),
                "var_historical_amount": round(-var_historical * current_asset, 2),
                "var_parametric_pct": round(var_parametric * 100, 2),
                "var_parametric_amount": round(var_parametric * current_asset, 2),
                
                # 多期VaR
                "var_horizon_pct": round(var_multi_period * 100, 2),
                "var_horizon_amount": round(var_multi_period * current_asset, 2),
                
                # CVaR
                "cvar_historical_pct": round(-cvar_historical * 100, 2),
                "cvar_historical_amount": round(-cvar_historical * current_asset, 2),
                "cvar_parametric_pct": round(cvar_parametric * 100, 2),
                "cvar_parametric_amount": round(cvar_parametric * current_asset, 2),
                
                # 多期CVaR
                "cvar_horizon_pct": round(cvar_multi_period * 100, 2),
                "cvar_horizon_amount": round(cvar_multi_period * current_asset, 2),
                
                # 统计量
                "daily_volatility_pct": round(std_ret * 100, 2),
                "daily_return_avg_pct": round(avg_ret * 100, 2),
                "annual_volatility_pct": round(std_ret * math.sqrt(252) * 100, 2),
                
                # 额外指标
                "worst_day_pct": round(min(returns) * 100, 2),
                "best_day_pct": round(max(returns) * 100, 2),
            }
            
            return success_response({
                "risk": risk,
                "portfolio_id": portfolio_id,
                "period": f"{rows[0][0]} ~ {rows[-1][0]}",
            })
            
        finally:
            conn.close()
    
    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(504, "Risk metrics timeout")
    except sqlite3.OperationalError as e:
        logger.error(f"[Risk] 数据库操作错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"数据库操作失败: {str(e)}")
    except ValueError as e:
        logger.error(f"[Risk] 数据格式错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"数据格式错误: {str(e)}")
    except ZeroDivisionError as e:
        logger.error(f"[Risk] 计算错误（除零）: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="风险价值计算失败：除零错误")
    except Exception as e:
        logger.error(f"[Risk] 计算异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"风险价值计算失败: {str(e)}")


# ══════════════════════════════════════════════════════════════
#  Benchmark Comparison
# ══════════════════════════════════════════════════════════════

@router.get("/{portfolio_id}/benchmark")
async def get_benchmark_comparison(portfolio_id: int, benchmark: str = "000300"):
    """
    组合与基准指数的对比分析
    
    - **benchmark**: 基准指数代码（默认000300沪深300）
    
    返回：
    - 累计收益对比曲线
    - 超额收益走势
    - 跟踪误差
    - 月度/季度收益对比
    """
    async def _inner():
        conn = _get_conn()
        try:
            # 1. 获取组合历史净值
            rows = conn.execute(
                """SELECT date, total_asset FROM portfolio_snapshots 
                   WHERE portfolio_id=? ORDER BY date ASC LIMIT 252""",
                (portfolio_id,)
            ).fetchall()
            
            if not rows or len(rows) < 30:
                return success_response({
                    "comparison": None,
                    "message": "历史数据不足（需要至少30个交易日）",
                    "days": len(rows) if rows else 0
                })
            
            portfolio_dates = [r[0] for r in rows]
            portfolio_assets = [float(r[1]) for r in rows]
            
            # 2. 获取基准历史数据
            benchmark_symbol = f"sh{benchmark}" if benchmark.startswith('000') else f"sz{benchmark}"
            bench_rows = conn.execute(
                """SELECT date, close FROM market_data_daily 
                   WHERE symbol=? AND date >= ? AND date <= ? ORDER BY date ASC""",
                (benchmark_symbol, portfolio_dates[0], portfolio_dates[-1])
            ).fetchall()
            
            if not bench_rows or len(bench_rows) < 30:
                return success_response({
                    "comparison": None,
                    "message": "基准数据不足",
                    "days": 0
                })
            
            # 3. 对齐数据（按日期）
            bench_dict = {r[0]: float(r[1]) for r in bench_rows}
            
            aligned_data = []
            for i, date in enumerate(portfolio_dates):
                if date in bench_dict:
                    aligned_data.append({
                        "date": date,
                        "portfolio_asset": portfolio_assets[i],
                        "benchmark_price": bench_dict[date]
                    })
            
            if len(aligned_data) < 30:
                return success_response({
                    "comparison": None,
                    "message": "对齐后数据不足",
                    "days": len(aligned_data)
                })
            
            # 4. 计算累计收益（以第一天为基准）
            first_portfolio = aligned_data[0]["portfolio_asset"]
            first_benchmark = aligned_data[0]["benchmark_price"]
            
            for item in aligned_data:
                item["portfolio_cum_return"] = (item["portfolio_asset"] - first_portfolio) / first_portfolio
                item["benchmark_cum_return"] = (item["benchmark_price"] - first_benchmark) / first_benchmark
                item["excess_return"] = item["portfolio_cum_return"] - item["benchmark_cum_return"]
            
            # 5. 计算日收益率和跟踪误差
            portfolio_returns = []
            benchmark_returns = []
            excess_returns = []
            
            for i in range(1, len(aligned_data)):
                p_ret = (aligned_data[i]["portfolio_asset"] - aligned_data[i-1]["portfolio_asset"]) / aligned_data[i-1]["portfolio_asset"]
                b_ret = (aligned_data[i]["benchmark_price"] - aligned_data[i-1]["benchmark_price"]) / aligned_data[i-1]["benchmark_price"]
                
                portfolio_returns.append(p_ret)
                benchmark_returns.append(b_ret)
                excess_returns.append(p_ret - b_ret)
            
            n = len(portfolio_returns)
            
            # 跟踪误差 = 超额收益的标准差（年化）
            te = stdev(excess_returns) * math.sqrt(252) if n > 1 else 0
            
            # 信息比率 = 平均超额收益 / 跟踪误差
            avg_excess = mean(excess_returns) if n > 0 else 0
            info_ratio = (avg_excess * 252) / te if te > 0 else 0
            
            # 最终收益对比
            final_portfolio_return = aligned_data[-1]["portfolio_cum_return"]
            final_benchmark_return = aligned_data[-1]["benchmark_cum_return"]
            
            # 月度收益对比（简化：按月份分组）
            monthly_returns = []
            current_month = None
            month_start_portfolio = None
            month_start_benchmark = None
            
            for item in aligned_data:
                month = item["date"][:7]  # YYYY-MM
                if month != current_month:
                    if current_month and month_start_portfolio:
                        monthly_returns.append({
                            "month": current_month,
                            "portfolio_return": round(((item["portfolio_asset"] - month_start_portfolio) / month_start_portfolio) * 100, 2),
                            "benchmark_return": round(((item["benchmark_price"] - month_start_benchmark) / month_start_benchmark) * 100, 2),
                            "excess_return": round(((item["portfolio_asset"] - month_start_portfolio) / month_start_portfolio - (item["benchmark_price"] - month_start_benchmark) / month_start_benchmark) * 100, 2)
                        })
                    current_month = month
                    month_start_portfolio = item["portfolio_asset"]
                    month_start_benchmark = item["benchmark_price"]
            
            return success_response({
                "comparison": {
                    "portfolio_return_pct": round(final_portfolio_return * 100, 2),
                    "benchmark_return_pct": round(final_benchmark_return * 100, 2),
                    "excess_return_pct": round((final_portfolio_return - final_benchmark_return) * 100, 2),
                    "tracking_error_pct": round(te * 100, 2),
                    "information_ratio": round(info_ratio, 2),
                    "correlation": round(
                        sum((p - mean(portfolio_returns)) * (b - mean(benchmark_returns)) for p, b in zip(portfolio_returns, benchmark_returns)) / 
                        (math.sqrt(sum((p - mean(portfolio_returns))**2 for p in portfolio_returns)) * math.sqrt(sum((b - mean(benchmark_returns))**2 for b in benchmark_returns)))
                        if len(portfolio_returns) > 1 else 0, 2
                    ),
                    "total_days": len(aligned_data),
                    "monthly_returns": monthly_returns[-12:] if len(monthly_returns) > 12 else monthly_returns,  # 最近12个月
                    "daily_data": aligned_data[-60:] if len(aligned_data) > 60 else aligned_data,  # 最近60天用于图表
                },
                "portfolio_id": portfolio_id,
                "benchmark": benchmark,
                "period": f"{aligned_data[0]['date']} ~ {aligned_data[-1]['date']}"
            })
            
        finally:
            conn.close()
    
    try:
        return await asyncio.wait_for(_inner(), timeout=PORTFOLIO_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(504, "Benchmark comparison timeout")
    except sqlite3.OperationalError as e:
        logger.error(f"[Benchmark] 数据库操作错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"数据库操作失败: {str(e)}")
    except ValueError as e:
        logger.error(f"[Benchmark] 数据格式错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"数据格式错误: {str(e)}")
    except ZeroDivisionError as e:
        logger.error(f"[Benchmark] 计算错误（除零）: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="基准对比计算失败：除零错误")
    except Exception as e:
        logger.error(f"[Benchmark] 计算异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"基准对比计算失败: {str(e)}")
