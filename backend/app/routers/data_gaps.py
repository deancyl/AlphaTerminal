"""
Data Gaps Radar Router - Monitor and backfill missing market data

Provides endpoints for:
- Scanning missing data dates (gaps)
- Calendar heatmap visualization
- One-click backfill functionality
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from app.db.database import _get_conn, _db_path
from app.utils.response import success_response
from app.routers.admin import verify_admin_key

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="data_gaps_")

router = APIRouter(prefix="/data_gaps", tags=["data_gaps"])


# ═══════════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════════

class GapInfo(BaseModel):
    """Information about a data gap"""
    date: str
    weekday: str
    is_trading_day: bool = True
    reason: Optional[str] = None  # e.g., "Holiday", "Weekend"


class AnomalyInfo(BaseModel):
    """Price anomaly (>20% change)"""
    date: str
    symbol: str
    change_pct: float
    close: float
    volume: Optional[float] = None


class ScanResult(BaseModel):
    """Result of gap scan"""
    symbol: str
    data_type: str
    start_date: str
    end_date: str
    total_days: int
    trading_days: int
    missing_dates: List[GapInfo]
    anomaly_dates: List[AnomalyInfo]
    coverage_pct: float


class BackfillRequest(BaseModel):
    """Request to backfill missing data"""
    symbol: str
    dates: List[str]
    data_type: str = "kline"


class BackfillResult(BaseModel):
    """Result of backfill operation"""
    symbol: str
    data_type: str
    total_requested: int
    success_count: int
    failed_count: int
    failed_dates: List[str]
    message: str


class CalendarDay(BaseModel):
    """Single day in calendar heatmap"""
    date: str
    gap_count: int
    has_data: bool


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

# Chinese holidays 2024 (simplified list)
CN_HOLIDAYS_2024 = {
    "2024-01-01", "2024-02-10", "2024-02-11", "2024-02-12",
    "2024-02-13", "2024-02-14", "2024-02-15", "2024-02-16", "2024-02-17",
    "2024-04-04", "2024-04-05", "2024-04-06",
    "2024-05-01", "2024-05-02", "2024-05-03", "2024-05-04", "2024-05-05",
    "2024-06-08", "2024-06-09", "2024-06-10",
    "2024-09-15", "2024-09-16", "2024-09-17",
    "2024-10-01", "2024-10-02", "2024-10-03", "2024-10-04", "2024-10-05",
    "2024-10-06", "2024-10-07",
}

# Chinese holidays 2025 (simplified list)
CN_HOLIDAYS_2025 = {
    "2025-01-01",
    "2025-01-28", "2025-01-29", "2025-01-30", "2025-01-31",
    "2025-02-01", "2025-02-02", "2025-02-03", "2025-02-04",
    "2025-04-04", "2025-04-05", "2025-04-06",
    "2025-05-01", "2025-05-02", "2025-05-03", "2025-05-04", "2025-05-05",
    "2025-05-31", "2025-06-01", "2025-06-02",
    "2025-10-01", "2025-10-02", "2025-10-03", "2025-10-04",
    "2025-10-05", "2025-10-06", "2025-10-07", "2025-10-08",
}


def is_trading_day(date: datetime) -> tuple[bool, str]:
    """
    Check if a date is a trading day.
    Returns (is_trading_day, reason_if_not)
    """
    # Weekend check
    if date.weekday() >= 5:  # Saturday=5, Sunday=6
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return False, f"周末({weekday_names[date.weekday()]})"
    
    # Holiday check
    date_str = date.strftime("%Y-%m-%d")
    if date_str in CN_HOLIDAYS_2024 or date_str in CN_HOLIDAYS_2025:
        return False, "节假日"
    
    return True, ""


def get_weekday_name(date: datetime) -> str:
    """Get Chinese weekday name"""
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return weekday_names[date.weekday()]


def _scan_kline_gaps_sync(symbol: str, start_date: str, end_date: str) -> dict:
    """
    Synchronous function to scan K-line data gaps.
    Runs in thread pool to avoid blocking event loop.
    """
    conn = _get_conn()
    
    try:
        # Clean symbol (remove prefix)
        clean_symbol = symbol.replace("sh", "").replace("sz", "").replace("bj", "")
        
        # Query existing dates
        cursor = conn.execute("""
            SELECT DISTINCT date 
            FROM market_data_daily 
            WHERE symbol = ? 
            AND date >= ? 
            AND date <= ?
            ORDER BY date
        """, (clean_symbol, start_date, end_date))
        
        existing_dates = {row[0] for row in cursor.fetchall()}
        
        # Generate all trading days in range
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        all_dates = []
        trading_days = []
        missing_dates = []
        
        current = start_dt
        while current <= end_dt:
            date_str = current.strftime("%Y-%m-%d")
            is_trading, reason = is_trading_day(current)
            
            all_dates.append(date_str)
            
            if is_trading:
                trading_days.append(date_str)
                if date_str not in existing_dates:
                    missing_dates.append({
                        "date": date_str,
                        "weekday": get_weekday_name(current),
                        "is_trading_day": True,
                        "reason": None
                    })
            
            current += timedelta(days=1)
        
        # Check for anomalies (>20% price change)
        cursor = conn.execute("""
            SELECT date, close, volume,
                   (close - LAG(close) OVER (ORDER BY date)) * 100.0 / LAG(close) OVER (ORDER BY date) as change_pct
            FROM market_data_daily 
            WHERE symbol = ? 
            AND date >= ? 
            AND date <= ?
            ORDER BY date
        """, (clean_symbol, start_date, end_date))
        
        anomaly_dates = []
        for row in cursor.fetchall():
            if row[3] is not None and abs(row[3]) > 20:
                anomaly_dates.append({
                    "date": row[0],
                    "symbol": symbol,
                    "change_pct": round(row[3], 2),
                    "close": row[1],
                    "volume": row[2]
                })
        
        # Calculate coverage
        coverage = (len(trading_days) - len(missing_dates)) / len(trading_days) * 100 if trading_days else 0
        
        return {
            "symbol": symbol,
            "data_type": "kline",
            "start_date": start_date,
            "end_date": end_date,
            "total_days": len(all_dates),
            "trading_days": len(trading_days),
            "missing_dates": missing_dates,
            "anomaly_dates": anomaly_dates,
            "coverage_pct": round(coverage, 2)
        }
        
    except Exception as e:
        logger.error(f"[DataGaps] Scan failed for {symbol}: {e}", exc_info=True)
        raise


def _backfill_kline_sync(symbol: str, dates: List[str]) -> dict:
    """
    Synchronous function to backfill K-line data.
    Runs in thread pool to avoid blocking event loop.
    """
    import akshare as ak
    
    conn = _get_conn()
    clean_symbol = symbol.replace("sh", "").replace("sz", "").replace("bj", "")
    
    success_count = 0
    failed_dates = []
    
    try:
        # Fetch data from akshare
        df = ak.stock_zh_a_hist(
            symbol=clean_symbol,
            period="daily",
            start_date=dates[0].replace("-", ""),
            end_date=dates[-1].replace("-", ""),
            adjust=""
        )
        
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                try:
                    date_val = row['日期']
                    if hasattr(date_val, 'strftime'):
                        date_str = date_val.strftime("%Y-%m-%d")
                    else:
                        date_str = str(date_val)[:10]
                    
                    conn.execute("""
                        INSERT OR REPLACE INTO market_data_daily 
                        (symbol, date, open, high, low, close, volume, amount)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        clean_symbol,
                        date_str,
                        float(row['开盘']) if row['开盘'] is not None else 0.0,
                        float(row['最高']) if row['最高'] is not None else 0.0,
                        float(row['最低']) if row['最低'] is not None else 0.0,
                        float(row['收盘']) if row['收盘'] is not None else 0.0,
                        float(row['成交量']) if row['成交量'] is not None else 0.0,
                        float(row['成交额']) if row['成交额'] is not None else 0.0
                    ))
                    
                    if date_str in dates:
                        success_count += 1
                        
                except Exception as e:
                    current_date = date_str if 'date_str' in dir() else 'unknown'
                    logger.warning(f"[DataGaps] Failed to insert {current_date}: {e}")
                    if 'date_str' in dir() and date_str in dates:
                        failed_dates.append(date_str)
            
            conn.commit()
            
    except Exception as e:
        logger.error(f"[DataGaps] Backfill failed for {symbol}: {e}", exc_info=True)
        # Mark all as failed
        failed_dates = dates
    
    return {
        "symbol": symbol,
        "data_type": "kline",
        "total_requested": len(dates),
        "success_count": success_count,
        "failed_count": len(failed_dates),
        "failed_dates": failed_dates,
        "message": f"成功回填 {success_count}/{len(dates)} 天数据" if success_count > 0 else "回填失败"
    }


def _get_calendar_data_sync(year: int, month: int) -> dict:
    """
    Synchronous function to get calendar heatmap data.
    Runs in thread pool to avoid blocking event loop.
    """
    conn = _get_conn()
    
    # Calculate month range
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    
    try:
        # Simplified approach: count total stocks and missing per day
        cursor = conn.execute("""
            SELECT COUNT(DISTINCT symbol) as total_stocks FROM market_data_daily
        """)
        total_stocks = cursor.fetchone()[0] or 0
        
        # Get dates with data
        cursor = conn.execute("""
            SELECT date, COUNT(DISTINCT symbol) as stock_count
            FROM market_data_daily
            WHERE date >= ? AND date < ?
            GROUP BY date
            ORDER BY date
        """, (start_date, end_date))
        
        calendar_data = {}
        for row in cursor.fetchall():
            date_str = row[0]
            stock_count = row[1]
            gap_count = max(0, total_stocks - stock_count)
            calendar_data[date_str] = {
                "date": date_str,
                "gap_count": gap_count,
                "has_data": stock_count > 0
            }
        
        # Fill in missing dates
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        current = start_dt
        while current < end_dt:
            date_str = current.strftime("%Y-%m-%d")
            if date_str not in calendar_data:
                is_trading, _ = is_trading_day(current)
                calendar_data[date_str] = {
                    "date": date_str,
                    "gap_count": total_stocks if is_trading else 0,
                    "has_data": False
                }
            current += timedelta(days=1)
        
        return {
            "year": year,
            "month": month,
            "total_stocks": total_stocks,
            "calendar": list(calendar_data.values())
        }
        
    except Exception as e:
        logger.error(f"[DataGaps] Calendar query failed: {e}", exc_info=True)
        return {
            "year": year,
            "month": month,
            "total_stocks": 0,
            "calendar": []
        }


# ═══════════════════════════════════════════════════════════════
# API Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/scan")
async def scan_data_gaps(
    symbol: str = Query(..., description="Stock symbol (e.g., sh600519)"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    data_type: str = Query("kline", description="Data type: kline, macro, futures"),
    _: bool = Depends(verify_admin_key)
):
    """
    Scan for missing data dates.
    
    Returns:
    - List of missing trading days
    - Price anomalies (>20% change)
    - Coverage percentage
    """
    try:
        # Validate dates
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
        
        if data_type != "kline":
            # For now, only kline is fully implemented
            return success_response({
                "symbol": symbol,
                "data_type": data_type,
                "message": f"{data_type} gap scanning not yet implemented",
                "missing_dates": [],
                "anomaly_dates": [],
                "coverage_pct": 100
            })
        
        # Run scan in thread pool
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            _executor,
            _scan_kline_gaps_sync,
            symbol,
            start_date,
            end_date
        )
        
        return success_response(result)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        logger.error(f"[DataGaps] Scan error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backfill")
async def backfill_data_gaps(
    request: BackfillRequest,
    _: bool = Depends(verify_admin_key)
):
    """
    One-click backfill missing data.
    
    Fetches data from akshare and inserts into database.
    """
    try:
        if not request.dates:
            raise HTTPException(status_code=400, detail="No dates provided for backfill")
        
        if request.data_type != "kline":
            return success_response({
                "symbol": request.symbol,
                "data_type": request.data_type,
                "message": f"{request.data_type} backfill not yet implemented",
                "total_requested": len(request.dates),
                "success_count": 0,
                "failed_count": len(request.dates),
                "failed_dates": request.dates
            })
        
        # Run backfill in thread pool
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            _executor,
            _backfill_kline_sync,
            request.symbol,
            request.dates
        )
        
        return success_response(result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[DataGaps] Backfill error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calendar")
async def get_data_gaps_calendar(
    year: int = Query(..., ge=2020, le=2030, description="Year"),
    month: int = Query(..., ge=1, le=12, description="Month"),
    _: bool = Depends(verify_admin_key)
):
    """
    Get calendar heatmap data for visualization.
    
    Returns gap count for each day in the specified month.
    """
    try:
        # Run calendar query in thread pool
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            _executor,
            _get_calendar_data_sync,
            year,
            month
        )
        
        return success_response(result)
        
    except Exception as e:
        logger.error(f"[DataGaps] Calendar error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return success_response({
        "status": "ok",
        "service": "data_gaps",
        "db_path": _db_path
    })
