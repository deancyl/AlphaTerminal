"""
数据导出路由 - CSV/Excel/JSON 导出功能
支持导出：持仓、回测结果、筛选器结果
"""
import io
import csv
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import pandas as pd

from ..db.database import get_conn

router = APIRouter(prefix="/export", tags=["export"])


def _generate_csv(data: List[Dict[str, Any]], filename: str) -> StreamingResponse:
    """生成CSV响应"""
    if not data:
        raise HTTPException(status_code=404, detail="No data to export")
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}.csv"}
    )


def _generate_excel(data: List[Dict[str, Any]], filename: str) -> StreamingResponse:
    """生成Excel响应"""
    if not data:
        raise HTTPException(status_code=404, detail="No data to export")
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"}
    )


def _generate_json(data: List[Dict[str, Any]], filename: str) -> StreamingResponse:
    """生成JSON响应"""
    if not data:
        raise HTTPException(status_code=404, detail="No data to export")
    
    output = io.StringIO()
    json.dump(data, output, ensure_ascii=False, indent=2, default=str)
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}.json"}
    )


@router.get("/portfolio/{portfolio_id}")
async def export_portfolio(
    portfolio_id: int,
    format: str = Query("csv", regex="^(csv|excel|json)$"),
    include_history: bool = Query(False, description="包含历史快照数据")
):
    """
    导出投资组合数据
    
    - **format**: 导出格式 (csv/excel/json)
    - **include_history**: 是否包含历史净值快照
    """
    try:
        with get_conn() as conn:
            # 获取组合基本信息
            portfolio = conn.execute(
                "SELECT * FROM portfolios WHERE id = ?",
                (portfolio_id,)
            ).fetchone()
            
            if not portfolio:
                raise HTTPException(status_code=404, detail="Portfolio not found")
            
            # 获取持仓数据
            positions = conn.execute(
                """SELECT 
                    p.symbol,
                    p.shares,
                    p.avg_cost,
                    s.name as stock_name,
                    s.price as current_price,
                    s.mktcap
                FROM positions p
                LEFT JOIN market_all_stocks s ON p.symbol = s.symbol
                WHERE p.portfolio_id = ?
                ORDER BY p.shares * p.avg_cost DESC""",
                (portfolio_id,)
            ).fetchall()
            
            # 转换为字典列表
            data = []
            for pos in positions:
                # 计算衍生字段
                shares = pos[1] or 0
                avg_cost = pos[2] or 0
                current_price = pos[4] or 0  # current_price is at index 4
                market_value = shares * current_price
                cost_basis = shares * avg_cost
                unrealized_pnl = market_value - cost_basis if shares > 0 else 0
                unrealized_pnl_pct = (unrealized_pnl / cost_basis) if cost_basis > 0 else 0
                
                data.append({
                    "组合ID": portfolio_id,
                    "组合名称": portfolio[1],
                    "股票代码": pos[0],
                    "股票名称": pos[3] or "",  # stock_name is at index 3
                    "持仓数量": shares,
                    "平均成本": avg_cost,
                    "当前价格": current_price,
                    "市值": market_value,
                    "浮动盈亏": round(unrealized_pnl, 2),
                    "盈亏比例(%)": round(unrealized_pnl_pct * 100, 2),
                    "导出时间": datetime.now().isoformat()
                })
            
            # 添加汇总行
            if data:
                total_value = sum(item["市值"] for item in data)
                total_pnl = sum(item["浮动盈亏"] for item in data)
                total_cost = sum(item["持仓数量"] * item["平均成本"] for item in data if item["持仓数量"])
                data.append({
                    "组合ID": portfolio_id,
                    "组合名称": f"{portfolio[1]} - 汇总",
                    "股票代码": "",
                    "股票名称": "",
                    "持仓数量": "",
                    "平均成本": "",
                    "当前价格": "",
                    "市值": total_value,
                    "浮动盈亏": total_pnl,
                    "盈亏比例(%)": round(total_pnl / total_cost * 100, 2) if total_cost > 0 else 0,
                    "导出时间": datetime.now().isoformat()
                })
            
            filename = f"portfolio_{portfolio_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            if format == "csv":
                return _generate_csv(data, filename)
            elif format == "excel":
                return _generate_excel(data, filename)
            else:
                return _generate_json(data, filename)
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/backtest/result")
async def export_backtest_result(
    request: Dict[str, Any],
    format: str = Query("excel", regex="^(csv|excel|json)$")
):
    """
    导出回测结果（从前端传入的完整结果数据）
    
    - **request**: 包含回测结果的完整数据
    - **format**: 导出格式 (csv/excel/json)
    """
    try:
        result = request.get("result", {})
        strategy_type = request.get("strategy_type", "unknown")
        symbol = request.get("symbol", "")
        start_date = request.get("start_date", "")
        end_date = request.get("end_date", "")
        
        if not result:
            raise HTTPException(status_code=400, detail="No backtest result data provided")
        
        # 构建数据
        data = []
        
        # 添加回测概览
        data.append({
            "类型": "回测概览",
            "策略类型": strategy_type,
            "标的代码": symbol,
            "回测区间": f"{start_date} ~ {end_date}",
            "初始资金": result.get("initial_capital", 0),
            "最终资金": result.get("final_capital", 0),
            "总收益率(%)": round(result.get("total_return_pct", 0) * 100, 2),
            "年化收益率(%)": round(result.get("annualized_return_pct", 0) * 100, 2) if result.get("annualized_return_pct") else 0,
            "最大回撤(%)": round(result.get("max_drawdown_pct", 0) * 100, 2) if result.get("max_drawdown_pct") else 0,
            "夏普比率": round(result.get("sharpe_ratio", 0), 2) if result.get("sharpe_ratio") else 0,
            "胜率(%)": round(result.get("win_rate", 0) * 100, 2) if result.get("win_rate") else 0,
            "交易次数": result.get("trades_count", 0),
            "基准收益率(%)": round(result.get("benchmark_return_pct", 0) * 100, 2) if result.get("benchmark_return_pct") else 0,
            "导出时间": datetime.now().isoformat()
        })
        
        # 添加交易记录
        trades = result.get("trades", [])
        if trades:
            for trade in trades:
                data.append({
                    "类型": "交易记录",
                    "策略类型": strategy_type,
                    "标的代码": symbol,
                    "交易日期": trade.get("date", ""),
                    "操作": trade.get("action", ""),
                    "成交价格": trade.get("price", 0),
                    "成交数量": trade.get("shares", 0),
                    "成交金额": trade.get("value", 0),
                    "盈亏": trade.get("pnl", 0) if trade.get("pnl") else 0,
                    "导出时间": datetime.now().isoformat()
                })
        
        filename = f"backtest_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if format == "csv":
            return _generate_csv(data, filename)
        elif format == "excel":
            return _generate_excel(data, filename)
        else:
            return _generate_json(data, filename)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/backtest/{backtest_id}")
async def export_backtest(
    backtest_id: int,
    format: str = Query("csv", regex="^(csv|excel|json)$"),
    include_trades: bool = Query(True, description="包含交易记录")
):
    """
    导出回测结果
    
    - **format**: 导出格式 (csv/excel/json)
    - **include_trades**: 是否包含详细交易记录
    """
    try:
        with get_conn() as conn:
            # 获取回测基本信息
            backtest = conn.execute(
                "SELECT * FROM backtest_results WHERE id = ?",
                (backtest_id,)
            ).fetchone()
            
            if not backtest:
                raise HTTPException(status_code=404, detail="Backtest not found")
            
            # 获取交易记录
            trades = conn.execute(
                """SELECT 
                    date,
                    action,
                    price,
                    shares,
                    value,
                    pnl
                FROM backtest_trades
                WHERE backtest_id = ?
                ORDER BY date""",
                (backtest_id,)
            ).fetchall()
            
            # 构建数据
            data = []
            
            # 添加回测概览
            data.append({
                "类型": "回测概览",
                "回测ID": backtest_id,
                "策略名称": backtest[1],
                "标的代码": backtest[2],
                "回测区间": f"{backtest[3]} ~ {backtest[4]}",
                "初始资金": backtest[5],
                "最终资金": backtest[6],
                "总收益率(%)": round(backtest[7] * 100, 2),
                "年化收益率(%)": round(backtest[8] * 100, 2) if backtest[8] else 0,
                "最大回撤(%)": round(backtest[9] * 100, 2) if backtest[9] else 0,
                "夏普比率": round(backtest[10], 2) if backtest[10] else 0,
                "胜率(%)": round(backtest[11] * 100, 2) if backtest[11] else 0,
                "交易次数": backtest[12],
                "导出时间": datetime.now().isoformat()
            })
            
            # 添加交易记录
            if include_trades and trades:
                for trade in trades:
                    data.append({
                        "类型": "交易记录",
                        "回测ID": backtest_id,
                        "策略名称": backtest[1],
                        "交易日期": trade[0],
                        "操作": trade[1],
                        "成交价格": trade[2],
                        "成交数量": trade[3],
                        "成交金额": trade[4],
                        "盈亏": trade[5] if trade[5] else 0,
                        "导出时间": datetime.now().isoformat()
                    })
            
            filename = f"backtest_{backtest_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            if format == "csv":
                return _generate_csv(data, filename)
            elif format == "excel":
                return _generate_excel(data, filename)
            else:
                return _generate_json(data, filename)
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/screener")
async def export_screener(
    filters: Dict[str, Any],
    format: str = Query("csv", regex="^(csv|excel|json)$")
):
    """
    导出筛选器结果
    
    - **filters**: 筛选条件
    - **format**: 导出格式 (csv/excel/json)
    """
    try:
        # 这里应该调用筛选逻辑，暂时使用模拟数据
        # 实际实现时需要从market_all_stocks表查询
        data = []
        
        # 示例：根据筛选条件查询
        # 实际实现时需要根据filters构建SQL查询
        
        filename = f"screener_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if format == "csv":
            return _generate_csv(data, filename)
        elif format == "excel":
            return _generate_excel(data, filename)
        else:
            return _generate_json(data, filename)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/market/history/{symbol}")
async def export_market_history(
    symbol: str,
    period: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    format: str = Query("csv", regex="^(csv|excel|json)$"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)")
):
    """
    导出历史行情数据
    
    - **symbol**: 股票代码
    - **period**: 周期 (daily/weekly/monthly)
    - **format**: 导出格式 (csv/excel/json)
    - **start_date**: 开始日期
    - **end_date**: 结束日期
    """
    try:
        with get_conn() as conn:
            # 根据周期选择表
            table_map = {
                "daily": "market_data_daily",
                "weekly": "market_data_weekly",
                "monthly": "market_data_monthly"
            }
            table = table_map.get(period, "market_data_daily")
            
            # 构建查询
            query = f"""SELECT 
                date,
                open,
                high,
                low,
                close,
                volume,
                amount
            FROM {table}
            WHERE symbol = ?"""
            
            params = [symbol]
            
            if start_date:
                query += " AND date >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND date <= ?"
                params.append(end_date)
            
            query += " ORDER BY date"
            
            rows = conn.execute(query, params).fetchall()
            
            if not rows:
                raise HTTPException(status_code=404, detail="No historical data found")
            
            data = []
            for row in rows:
                data.append({
                    "股票代码": symbol,
                    "日期": row[0],
                    "开盘价": row[1],
                    "最高价": row[2],
                    "最低价": row[3],
                    "收盘价": row[4],
                    "成交量": row[5],
                    "成交额": row[6],
                    "导出时间": datetime.now().isoformat()
                })
            
            filename = f"history_{symbol}_{period}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            if format == "csv":
                return _generate_csv(data, filename)
            elif format == "excel":
                return _generate_excel(data, filename)
            else:
                return _generate_json(data, filename)
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
