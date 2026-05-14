"""
F9 深度数据接口
数据来源: akshare
覆盖: 财务数据、股东信息、机构调研、资金流向等深度数据

Timeout Behavior:
    All akshare calls wrapped with asyncio.wait_for() timeout protection.
    Returns 504 Gateway Timeout when external data source is slow.
"""
import logging
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from fastapi import APIRouter
from typing import Any, Dict, Optional
from app.utils.response import success_response, error_response, ErrorCode
from app.services.circuit_breaker import CircuitBreakerOpen
from app.services.data_fetcher import akshare_breaker
from app.config.timeout import AKSHARE_TIMEOUT

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/f9", tags=["f9_deep_data"])

_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="f9_")

_cache: Dict[str, Any] = {}
_cache_ttl: Dict[str, float] = {}
CACHE_DURATION = 300


def normalize_f9_symbol(symbol: str) -> str:
    """
    标准化股票代码，去除前缀
    
    Args:
        symbol: 股票代码，可能带前缀（如 sh600519, sz000001, hk00700, usAAPL）
    
    Returns:
        纯股票代码（如 600519, 000001, 00700, AAPL）
    """
    if not symbol:
        return symbol
    
    # 转小写用于匹配
    symbol_lower = symbol.lower()
    
    # 常见前缀列表
    prefixes = ['sh', 'sz', 'hk', 'us']
    
    for prefix in prefixes:
        if symbol_lower.startswith(prefix):
            # 返回去除前缀后的原始大小写（保留数字部分）
            return symbol[len(prefix):]
    
    # 无前缀，直接返回
    return symbol


def get_cached(key: str) -> Optional[Any]:
    """获取缓存数据，如果过期则返回 None"""
    if key not in _cache:
        return None
    
    if key not in _cache_ttl:
        return None
    
    if time.time() - _cache_ttl[key] > CACHE_DURATION:
        # 缓存过期，删除
        del _cache[key]
        del _cache_ttl[key]
        return None
    
    return _cache[key]


def set_cached(key: str, value: Any) -> None:
    """设置缓存数据"""
    _cache[key] = value
    _cache_ttl[key] = time.time()


def check_akshare_circuit() -> bool:
    if not akshare_breaker.is_available():
        logger.warning("[F9] AkShare circuit breaker OPEN, skipping request")
        return False
    return True


async def run_with_timeout(coro, timeout: float = AKSHARE_TIMEOUT):
    """
    Execute coroutine with timeout protection.
    
    Raises:
        asyncio.TimeoutError: When timeout is exceeded
    """
    return await asyncio.wait_for(coro, timeout=timeout)


# ── API 端点 ─────────────────────────────────────────────────────

# ── 健康检查端点 ─────────────────────────────────────────────────
@router.get("/health")
async def health_check():
    """
    F9 深度数据服务健康检查
    """
    return success_response({"status": "ok"})


# ── 股东研究端点 ─────────────────────────────────────────────────
@router.get("/{symbol}/shareholder")
async def get_shareholder_data(symbol: str):
    """
    股东研究数据
    - Top 10 股东
    - 股本变动记录
    - 流通股东变化
    """
    symbol = normalize_f9_symbol(symbol)
    cache_key = f"shareholder_{symbol}"
    cached = get_cached(cache_key)
    if cached:
        logger.info(f"[shareholder] Cache hit for {symbol}")
        return success_response(cached)
    
    if not check_akshare_circuit():
        return error_response("数据源暂时不可用，请稍后重试", code=503)
    
    try:
        import akshare as ak
        from datetime import datetime, timedelta
        
        loop = asyncio.get_event_loop()
        
        # 1. 获取流通股东 Top 10
        async def fetch_circulate_holders():
            def _fetch():
                try:
                    with akshare_breaker:
                        df = ak.stock_circulate_stock_holder(symbol=symbol)
                    # 获取最新一期数据
                    latest_date = df['截止日期'].max()
                    latest_df = df[df['截止日期'] == latest_date].head(10)
                    return {
                        'date': str(latest_date),
                        'holders': latest_df[['股东名称', '持股数量', '占流通股比例', '股本性质']].to_dict('records')
                    }
                except CircuitBreakerOpen as e:
                    logger.warning(f"[shareholder] Circuit breaker OPEN: {e}")
                    return None
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"[shareholder] Data processing error in circulate holders: {e}")
                    return None
                except Exception as e:
                    logger.warning(f"[shareholder] Failed to fetch circulate holders: {e}")
                    return None
            return await loop.run_in_executor(_executor, _fetch)
        
        # 2. 获取股本变动记录（最近365天）
        async def fetch_share_changes():
            def _fetch():
                try:
                    end_date = datetime.now().strftime('%Y%m%d')
                    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
                    with akshare_breaker:
                        df = ak.stock_share_change_cninfo(symbol=symbol, start_date=start_date, end_date=end_date)
                    
                    changes = []
                    for _, row in df.iterrows():
                        change = {
                            'date': str(row.get('变动日期', '')),
                            'reason': str(row.get('变动原因', '')),
                            'totalShares': float(row.get('总股本', 0)) if pd.notna(row.get('总股本')) else 0,
                            'circulateShares': float(row.get('已流通股份', 0)) if pd.notna(row.get('已流通股份')) else 0,
                            'restrictedShares': float(row.get('流通受限股份', 0)) if pd.notna(row.get('流通受限股份')) else 0,
                        }
                        changes.append(change)
                    
                    return changes
                except CircuitBreakerOpen as e:
                    logger.warning(f"[shareholder] Circuit breaker OPEN: {e}")
                    return []
                except (KeyError, ValueError, TypeError, AttributeError) as e:
                    logger.warning(f"[shareholder] Data processing error in share changes: {e}")
                    return []
                except Exception as e:
                    logger.warning(f"[shareholder] Failed to fetch share changes: {e}")
                    return []
            return await loop.run_in_executor(_executor, _fetch)
        
        # 3. 获取股东变动记录
        async def fetch_holder_changes():
            def _fetch():
                try:
                    with akshare_breaker:
                        df = ak.stock_shareholder_change_ths(symbol=symbol)
                    changes = []
                    for _, row in df.iterrows():
                        change = {
                            'date': str(row.get('公告日期', '')),
                            'holder': str(row.get('变动股东', '')),
                            'changeAmount': str(row.get('变动数量', '')),
                            'avgPrice': str(row.get('交易均价', '')),
                            'remainingShares': str(row.get('剩余股份总数', '')),
                            'period': str(row.get('变动期间', '')),
                            'channel': str(row.get('变动途径', '')),
                        }
                        changes.append(change)
                    return changes[:20]  # 最近20条
                except CircuitBreakerOpen as e:
                    logger.warning(f"[shareholder] Circuit breaker OPEN: {e}")
                    return []
                except (KeyError, ValueError, TypeError, AttributeError) as e:
                    logger.warning(f"[shareholder] Data processing error in holder changes: {e}")
                    return []
                except Exception as e:
                    logger.warning(f"[shareholder] Failed to fetch holder changes: {e}")
                    return []
            return await loop.run_in_executor(_executor, _fetch)
        
        # 并行获取数据（带超时保护）
        import pandas as pd
        circulate_holders, share_changes, holder_changes = await asyncio.wait_for(
            asyncio.gather(
                fetch_circulate_holders(),
                fetch_share_changes(),
                fetch_holder_changes()
            ),
            timeout=AKSHARE_TIMEOUT
        )
        
        result = {
            'circulateHolders': circulate_holders,
            'shareChanges': share_changes,
            'holderChanges': holder_changes
        }
        
        set_cached(cache_key, result)
        logger.info(f"[shareholder] Successfully fetched data for {symbol}")
        return success_response(result)
        
    except asyncio.TimeoutError:
        logger.warning(f"[shareholder] Timeout for {symbol}")
        return error_response("请求超时，请稍后重试", code=504)
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"[shareholder] Data processing error for {symbol}: {e}")
        return error_response(f"数据处理失败: {str(e)}")
    except Exception as e:
        logger.error(f"[shareholder] Error fetching data for {symbol}: {e}")
        return error_response(f"获取股东数据失败: {str(e)}")


# ── 融资融券端点 ─────────────────────────────────────────────────
@router.get("/{symbol}/margin")
async def get_margin_data(symbol: str):
    """
    获取个股融资融券数据（最近30天）
    数据来源: akshare stock_margin_detail_sse / stock_margin_detail_szse
    """
    symbol = normalize_f9_symbol(symbol)
    cache_key = f"margin_{symbol}"
    cached = get_cached(cache_key)
    if cached:
        logger.info(f"[Margin] Cache hit for {symbol}")
        return success_response(cached)

    if not check_akshare_circuit():
        return error_response("数据源暂时不可用，请稍后重试", code=503)

    def fetch_margin_data():
        """在线程池中执行 akshare 调用"""
        import akshare as ak
        from datetime import datetime, timedelta

        # 判断交易所：6开头为上交所，其他为深交所
        exchange = "sse" if symbol.startswith("6") else "szse"

        # 获取最近30天的日期列表
        end_date = datetime.now()
        dates = []
        for i in range(45):  # 多获取几天以确保有30个交易日
            check_date = end_date - timedelta(days=i)
            if check_date.weekday() < 5:  # 只保留工作日
                dates.append(check_date.strftime("%Y%m%d"))

        all_data = []
        symbol_code = symbol  # 纯代码，不带前缀

        # 尝试获取数据（从最近的日期开始）
        for date in dates[:15]:  # 尝试最近15个工作日
            try:
                with akshare_breaker:
                    if exchange == "sse":
                        df = ak.stock_margin_detail_sse(date=date)
                    else:
                        df = ak.stock_margin_detail_szse(date=date)

                if df is not None and len(df) > 0:
                    # 查找对应股票的数据
                    # 代码列可能是"证券代码"或"代码"
                    code_col = None
                    for col in df.columns:
                        if "代码" in str(col):
                            code_col = col
                            break

                    if code_col:
                        stock_row = df[df[code_col].astype(str) == symbol_code]
                        if len(stock_row) > 0:
                            row = stock_row.iloc[0]
                            record = {
                                "date": date,
                                "financing_balance": float(row.get("融资余额", 0) or 0),
                                "financing_buy": float(row.get("融资买入额", 0) or 0),
                                "financing_repay": float(row.get("融资偿还额", 0) or 0),
                                "lending_balance": float(row.get("融券余额", 0) or 0),
                                "lending_volume": float(row.get("融券余量", 0) or 0),
                                "lending_sell": float(row.get("融券卖出量", 0) or 0),
                                "lending_repay": float(row.get("融券偿还量", 0) or 0),
                                "total_balance": float(row.get("融资融券余额", 0) or 0),
                            }
                            all_data.append(record)
                            logger.info(f"[Margin] Found data for {symbol} on {date}")

                            if len(all_data) >= 30:
                                break
            except CircuitBreakerOpen as e:
                logger.warning(f"[Margin] Circuit breaker OPEN: {e}")
                break
            except (KeyError, ValueError, TypeError) as e:
                logger.debug(f"[Margin] Data processing error for {symbol} on {date}: {e}")
                continue
            except Exception as e:
                logger.debug(f"[Margin] No data for {symbol} on {date}: {e}")
                continue

        return all_data

    try:
        loop = asyncio.get_event_loop()
        trend_data = await asyncio.wait_for(
            loop.run_in_executor(_executor, fetch_margin_data),
            timeout=AKSHARE_TIMEOUT
        )

        if not trend_data:
            logger.warning(f"[Margin] No margin data found for {symbol}")
            return error_response(f"未找到 {symbol} 的融资融券数据", code=404)

        trend_data.sort(key=lambda x: x["date"])

        result = {
            "current": trend_data[-1] if trend_data else None,
            "trend": trend_data
        }

        set_cached(cache_key, result)

        logger.info(f"[Margin] Successfully fetched {len(trend_data)} days data for {symbol}")
        return success_response(result)

    except asyncio.TimeoutError:
        logger.warning(f"[Margin] Timeout for {symbol}")
        return error_response("请求超时，请稍后重试", code=504)
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"[Margin] Data processing error for {symbol}: {e}")
        return error_response(f"数据处理失败: {str(e)}", code=500)
    except Exception as e:
        logger.error(f"[Margin] Error fetching margin data for {symbol}: {e}")
        return error_response(f"获取融资融券数据失败: {str(e)}", code=500)


# ── 财务摘要端点 ─────────────────────────────────────────────────
@router.get("/{symbol}/financial")
async def get_financial_data(symbol: str):
    """
    获取股票财务指标数据
    数据来源: akshare.stock_financial_analysis_indicator
    """
    symbol = normalize_f9_symbol(symbol)
    cache_key = f"financial_{symbol}"

    # 检查缓存
    cached = get_cached(cache_key)
    if cached:
        logger.info(f"[F9] Cache hit for financial: {symbol}")
        return success_response(cached)

    if not check_akshare_circuit():
        return error_response("数据源暂时不可用，请稍后重试", code=503)

    try:
        # 在线程池中执行同步的 akshare 调用
        loop = asyncio.get_event_loop()

        def fetch_financial():
            import akshare as ak
            import pandas as pd

            # 获取财务指标数据
            with akshare_breaker:
                df = ak.stock_financial_analysis_indicator(symbol=symbol, start_year="2020")

            if df.empty:
                return None

            # 按日期排序（最新的在前）
            df = df.sort_values('日期', ascending=False)

            # 转换为字典列表
            indicators = df.to_dict('records')

            # 处理 NaN 值
            for item in indicators:
                for key, value in item.items():
                    if pd.isna(value):
                        item[key] = None

            # 获取最新季度数据
            latest = indicators[0] if indicators else {}

            # 提取最近8个季度的关键指标趋势
            trend_data = []
            key_metrics = [
                '日期',
                '摊薄每股收益(元)',
                '净资产收益率(%)',
                '主营业务收入增长率(%)',
                '净利润增长率(%)',
                '销售毛利率(%)',
                '销售净利率(%)',
                '每股净资产_调整后(元)'
            ]

            for i, item in enumerate(indicators[:8]):
                trend_item = {}
                for metric in key_metrics:
                    trend_item[metric] = item.get(metric)
                trend_data.append(trend_item)

            return {
                "indicators": indicators,
                "latest": latest,
                "trend": trend_data
            }

        result = await asyncio.wait_for(
            loop.run_in_executor(_executor, fetch_financial),
            timeout=AKSHARE_TIMEOUT
        )

        if not result:
            return error_response("未找到财务数据")

        set_cached(cache_key, result)

        logger.info(f"[F9] Fetched financial data for {symbol}, quarters: {len(result['indicators'])}")
        return success_response(result)

    except asyncio.TimeoutError:
        logger.warning(f"[F9] Timeout for financial {symbol}")
        return error_response("请求超时，请稍后重试", code=504)
    except CircuitBreakerOpen as e:
        logger.warning(f"[F9] Circuit breaker OPEN for financial {symbol}: {e}")
        return error_response("数据源暂时不可用，请稍后重试", code=503)
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"[F9] Data processing error for financial data {symbol}: {e}", exc_info=True)
        return success_response({
            "indicators": [],
            "latest": {},
            "trend": []
        })
    except Exception as e:
        logger.error(f"[F9] Error fetching financial data for {symbol}: {e}", exc_info=True)
        return success_response({
            "indicators": [],
            "latest": {},
            "trend": []
        })


# ── 盈利预测端点 ─────────────────────────────────────────────────
@router.get("/{symbol}/forecast")
async def get_profit_forecast(symbol: str):
    """
    盈利预测数据
    数据来源: akshare stock_profit_forecast_ths
    """
    symbol = normalize_f9_symbol(symbol)
    cache_key = f"forecast_{symbol}"
    
    # 检查缓存
    cached = get_cached(cache_key)
    if cached:
        logger.info(f"[F9] Cache hit for forecast: {symbol}")
        return success_response(cached)
    
    if not check_akshare_circuit():
        return error_response("数据源暂时不可用，请稍后重试", code=503)
    
    try:
        import akshare as ak
        
        # 在线程池中执行同步调用
        loop = asyncio.get_event_loop()
        
        def fetch_eps():
            with akshare_breaker:
                return ak.stock_profit_forecast_ths(symbol=symbol, indicator="预测年报每股收益")
        
        def fetch_institutions():
            with akshare_breaker:
                return ak.stock_profit_forecast_ths(symbol=symbol, indicator="业绩预测详表-机构")
        
        eps_task = loop.run_in_executor(_executor, fetch_eps)
        institution_task = loop.run_in_executor(_executor, fetch_institutions)
        eps_df, institution_df = await asyncio.wait_for(
            asyncio.gather(eps_task, institution_task),
            timeout=AKSHARE_TIMEOUT
        )
        
        eps_forecast = []
        if eps_df is not None and not eps_df.empty:
            eps_forecast = eps_df.to_dict('records')
        
        institutions = []
        if institution_df is not None and not institution_df.empty:
            institutions = institution_df.to_dict('records')
        
        result = {
            "eps_forecast": eps_forecast,
            "institutions": institutions
        }
        
        set_cached(cache_key, result)
        logger.info(f"[F9] Fetched forecast data for {symbol}: {len(eps_forecast)} EPS records, {len(institutions)} institution records")
        
        return success_response(result)
        
    except asyncio.TimeoutError:
        logger.warning(f"[F9] Timeout for forecast {symbol}")
        return error_response("请求超时，请稍后重试", code=504)
    except CircuitBreakerOpen as e:
        logger.warning(f"[F9] Circuit breaker OPEN for forecast {symbol}: {e}")
        return error_response("数据源暂时不可用，请稍后重试", code=503)
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"[F9] Data processing error for forecast {symbol}: {e}")
        return error_response(f"数据处理失败: {str(e)}")
    except Exception as e:
        logger.error(f"[F9] Error fetching forecast for {symbol}: {e}")
        return error_response(f"获取盈利预测数据失败: {str(e)}")


# ── 机构持股端点 ─────────────────────────────────────────────────
@router.get("/{symbol}/institution")
async def get_institution_holdings(symbol: str):
    """
    获取机构持股数据
    
    Args:
        symbol: 股票代码（如 600519）
    
    Returns:
        {
            "code": 0,
            "data": {
                "current": [...],  // 当前季度机构持股明细
                "trend": [...]     // 近8季度趋势
            }
        }
    """
    symbol = normalize_f9_symbol(symbol)
    cache_key = f"institution_{symbol}"
    cached = get_cached(cache_key)
    if cached:
        logger.info(f"[Institution] Cache hit for {symbol}")
        return success_response(cached)
    
    if not check_akshare_circuit():
        return error_response("数据源暂时不可用，请稍后重试", code=503)
    
    try:
        import akshare as ak
        
        # 计算当前季度
        now = datetime.now()
        current_year = now.year
        current_quarter = (now.month - 1) // 3 + 1
        current_quarter_str = f"{current_year}{current_quarter}"
        
# 获取当前季度数据（尝试最近4个季度）
        def fetch_current():
            for q_offset in range(4):
                q = current_quarter - q_offset
                y = current_year
                while q <= 0:
                    q += 4
                    y -= 1
                quarter_str = f"{y}{q}"
                
                try:
                    with akshare_breaker:
                        df = ak.stock_institute_hold_detail(stock=symbol, quarter=quarter_str)
                    if df is not None and not df.empty:
                        logger.info(f"[Institution] Found data for quarter {quarter_str}")
                        return df.to_dict('records'), quarter_str
                except CircuitBreakerOpen as e:
                    logger.warning(f"[Institution] Circuit breaker OPEN: {e}")
                    return [], current_quarter_str
                except (KeyError, ValueError, TypeError) as e:
                    logger.debug(f"[Institution] Data processing error for {quarter_str}: {e}")
                    continue
                except Exception as e:
                    logger.debug(f"[Institution] No data for {quarter_str}: {e}")
                    continue
            
            logger.warning(f"[Institution] No current data found for {symbol}")
            return [], current_quarter_str
        
        # 获取历史趋势（最近8个季度）
        def fetch_trend():
            trend_data = []
            for i in range(8):
                q = current_quarter - i
                y = current_year
                while q <= 0:
                    q += 4
                    y -= 1
                quarter_str = f"{y}{q}"
                
                try:
                    with akshare_breaker:
                        df = ak.stock_institute_hold_detail(stock=symbol, quarter=quarter_str)
                    if df is not None and not df.empty:
                        count = len(df)
                        pct_col = None
                        for col in df.columns:
                            if '持股比例' in col or '占比' in col:
                                pct_col = col
                                break
                        
                        total_pct = 0
                        if pct_col:
                            total_pct = df[pct_col].sum()
                        
                        trend_data.append({
                            "quarter": quarter_str,
                            "year": y,
                            "quarter_num": q,
                            "count": count,
                            "total_pct": round(total_pct, 2)
                        })
                except CircuitBreakerOpen as e:
                    logger.warning(f"[Institution] Circuit breaker OPEN: {e}")
                    break
                except (KeyError, ValueError, TypeError) as e:
                    logger.debug(f"[Institution] Data processing error for {quarter_str}: {e}")
                    continue
                except Exception as e:
                    logger.debug(f"[Institution] No data for {quarter_str}: {e}")
                    continue
            
            # 按时间正序排列
            trend_data.reverse()
            return trend_data
        
        loop = asyncio.get_event_loop()
        current_task = loop.run_in_executor(_executor, fetch_current)
        trend_task = loop.run_in_executor(_executor, fetch_trend)
        
        current_result, trend_data = await asyncio.wait_for(
            asyncio.gather(current_task, trend_task),
            timeout=AKSHARE_TIMEOUT
        )
        current_data, actual_quarter = current_result
        
        result = {
            "current": current_data,
            "trend": trend_data,
            "quarter": actual_quarter
        }
        
        set_cached(cache_key, result)
        logger.info(f"[Institution] Successfully fetched data for {symbol}")
        return success_response(result)
        
    except asyncio.TimeoutError:
        logger.warning(f"[Institution] Timeout for {symbol}")
        return error_response("请求超时，请稍后重试", code=504)
    except CircuitBreakerOpen as e:
        logger.warning(f"[Institution] Circuit breaker OPEN for {symbol}: {e}")
        return error_response("数据源暂时不可用，请稍后重试", code=503)
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"[Institution] Data processing error for {symbol}: {e}")
        return error_response(f"数据处理失败: {str(e)}")
    except Exception as e:
        logger.error(f"[Institution] Error fetching data for {symbol}: {e}")
        return error_response(f"获取机构持股数据失败: {str(e)}")


# ── 同业比较端点 ─────────────────────────────────────────────────
@router.get("/{symbol}/peers")
async def get_peer_comparison(symbol: str):
    """
    获取同业比较数据
    
    Args:
        symbol: 股票代码（如 600519）
    
    Returns:
        {
            "code": 0,
            "data": {
                "industry": "白酒",
                "peers": [
                    {
                        "symbol": "600519",
                        "name": "贵州茅台",
                        "roe": 30.5,
                        "pe": 35.2,
                        "pb": 10.1,
                        "revenue_growth": 15.3
                    },
                    ...
                ]
            }
        }
    """
    symbol = normalize_f9_symbol(symbol)
    cache_key = f"peers_{symbol}"
    cached = get_cached(cache_key)
    if cached:
        logger.info(f"[Peers] Cache hit for {symbol}")
        return success_response(cached)
    
    if not check_akshare_circuit():
        return error_response("数据源暂时不可用，请稍后重试", code=503)
    
    try:
        import akshare as ak
        import pandas as pd
        
        loop = asyncio.get_event_loop()
        
        def fetch_stock_info():
            info_dict = {}
            
            try:
                with akshare_breaker:
                    df = ak.stock_profile_cninfo(symbol=symbol)
                if df is not None and not df.empty:
                    row = df.iloc[0]
                    info_dict['行业'] = row.get('所属行业', '')
                    info_dict['主营业务'] = row.get('主营业务', '')
            except CircuitBreakerOpen as e:
                logger.warning(f"[Peers] Circuit breaker OPEN: {e}")
            except (KeyError, ValueError, TypeError) as e:
                logger.debug(f"[Peers] Data processing error in stock_profile_cninfo: {e}")
            except Exception as e:
                logger.debug(f"[Peers] stock_profile_cninfo failed: {e}")
            
            if not info_dict.get('行业'):
                try:
                    with akshare_breaker:
                        df = ak.stock_individual_info_em(symbol=symbol)
                    if df is not None and not df.empty:
                        for _, row in df.iterrows():
                            if row['item'] not in info_dict or not info_dict[row['item']]:
                                info_dict[row['item']] = row['value']
                except CircuitBreakerOpen as e:
                    logger.warning(f"[Peers] Circuit breaker OPEN: {e}")
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"[Peers] Data processing error in stock_individual_info_em: {e}")
                except Exception as e:
                    logger.warning(f"[Peers] stock_individual_info_em failed: {e}")
            
            return info_dict
        
        def fetch_industry_stocks(symbol_code):
            try:
                import baostock as bs
                import pandas as pd
                
                lg = bs.login()
                if lg.error_code != '0':
                    logger.warning(f"[Peers] BaoStock login failed: {lg.error_msg}")
                    return []
                
                rs = bs.query_stock_industry()
                data_list = []
                while (rs.error_code == '0') & rs.next():
                    data_list.append(rs.get_row_data())
                
                df = pd.DataFrame(data_list, columns=rs.fields)
                bs.logout()
                
                baostock_code = f"sh.{symbol_code}" if symbol_code.startswith('6') else f"sz.{symbol_code}"
                row = df[df['code'] == baostock_code]
                
                if len(row) == 0:
                    logger.warning(f"[Peers] Stock {symbol_code} not found in BaoStock")
                    return []
                
                industry = row.iloc[0]['industry']
                logger.info(f"[Peers] Found industry for {symbol_code}: {industry}")
                
                peers_df = df[df['industry'] == industry]
                
                result = []
                for _, peer_row in peers_df.iterrows():
                    code = peer_row['code']
                    bare_code = code.replace('sh.', '').replace('sz.', '')
                    result.append({
                        '代码': bare_code,
                        '股票代码': bare_code,
                        '名称': peer_row['code_name'],
                        '股票名称': peer_row['code_name']
                    })
                
                logger.info(f"[Peers] Found {len(result)} stocks in industry {industry}")
                return result
                
            except (KeyError, ValueError, TypeError, AttributeError) as e:
                logger.warning(f"[Peers] Data processing error in BaoStock: {e}")
                return []
            except Exception as e:
                logger.warning(f"[Peers] BaoStock failed: {e}")
                return []
        
        def fetch_financial_indicator(stock_symbol):
            try:
                with akshare_breaker:
                    df = ak.stock_financial_analysis_indicator(symbol=stock_symbol, start_year="2023")
                if df is not None and not df.empty:
                    latest = df.iloc[0]
                    return {
                        'roe': latest.get('净资产收益率(%)'),
                        'pe': latest.get('市盈率'),
                        'pb': latest.get('市净率'),
                        'revenue_growth': latest.get('主营业务收入增长率(%)')
                    }
                return None
            except CircuitBreakerOpen as e:
                logger.warning(f"[Peers] Circuit breaker OPEN for {stock_symbol}: {e}")
                return None
            except (KeyError, ValueError, TypeError) as e:
                logger.debug(f"[Peers] Data processing error for financial {stock_symbol}: {e}")
                return None
            except Exception as e:
                logger.debug(f"[Peers] Failed to fetch financial for {stock_symbol}: {e}")
                return None
        
        stock_info = await asyncio.wait_for(
            loop.run_in_executor(_executor, fetch_stock_info),
            timeout=AKSHARE_TIMEOUT
        )
        
        industry_name = stock_info.get('行业') if stock_info else None
        
        if not industry_name:
            logger.info(f"[Peers] No industry from stock_info, using financial data fallback")
            
            financial_result = await asyncio.wait_for(
                loop.run_in_executor(_executor, lambda: fetch_financial_indicator(symbol)),
                timeout=AKSHARE_TIMEOUT
            )
            
            if not financial_result:
                logger.warning(f"[Peers] No financial data for {symbol}")
                return error_response("未找到股票数据")
            
            logger.info(f"[Peers] Using demo data for {symbol} (network issue fallback)")
            
            demo_peers = [
                {
                    'symbol': symbol,
                    'name': '当前股票',
                    'roe': financial_result.get('roe'),
                    'pe': financial_result.get('pe'),
                    'pb': financial_result.get('pb'),
                    'revenue_growth': financial_result.get('revenue_growth')
                }
            ]
            
            for key in ['roe', 'pe', 'pb', 'revenue_growth']:
                val = demo_peers[0][key]
                if val is not None and pd.notna(val):
                    demo_peers[0][key] = round(float(val), 2) if isinstance(val, (int, float)) else val
                else:
                    demo_peers[0][key] = None
            
            result = {
                'industry': '未知行业',
                'peers': demo_peers
            }
            
            set_cached(cache_key, result)
            return success_response(result)
        
        logger.info(f"[Peers] Fetching industry peers for {symbol}")
        
        industry_stocks = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: fetch_industry_stocks(symbol)),
            timeout=AKSHARE_TIMEOUT
        )
        
        if not industry_stocks:
            logger.warning(f"[Peers] No industry stocks found for {industry_name}")
            return error_response(f"未找到 {industry_name} 行业的股票数据")
        
        logger.info(f"[Peers] Found {len(industry_stocks)} stocks in {industry_name}")
        
        peer_tasks = []
        peer_symbols = []
        
        for stock in industry_stocks[:10]:
            peer_symbol = stock.get('代码', stock.get('股票代码'))
            peer_name = stock.get('名称', stock.get('股票名称'))
            
            if peer_symbol:
                peer_symbols.append((peer_symbol, peer_name))
                peer_tasks.append(
                    loop.run_in_executor(_executor, lambda s=peer_symbol: fetch_financial_indicator(s))
                )
        
        financial_results = await asyncio.wait_for(
            asyncio.gather(*peer_tasks),
            timeout=AKSHARE_TIMEOUT
        )
        
        peers = []
        for i, (peer_symbol, peer_name) in enumerate(peer_symbols):
            financial = financial_results[i]
            
            peer_data = {
                'symbol': peer_symbol,
                'name': peer_name,
                'roe': financial.get('roe') if financial else None,
                'pe': financial.get('pe') if financial else None,
                'pb': financial.get('pb') if financial else None,
                'revenue_growth': financial.get('revenue_growth') if financial else None
            }
            
            for key in ['roe', 'pe', 'pb', 'revenue_growth']:
                val = peer_data[key]
                if val is not None and pd.notna(val):
                    peer_data[key] = round(float(val), 2) if isinstance(val, (int, float)) else val
                else:
                    peer_data[key] = None
            
            peers.append(peer_data)
        
        result = {
            'industry': industry_name,
            'peers': peers
        }
        
        set_cached(cache_key, result)
        
        logger.info(f"[Peers] Successfully fetched {len(peers)} peer stocks for {symbol}")
        return success_response(result)
        
    except asyncio.TimeoutError:
        logger.warning(f"[Peers] Timeout for {symbol}")
        return error_response("请求超时，请稍后重试", code=504)
    except CircuitBreakerOpen as e:
        logger.warning(f"[Peers] Circuit breaker OPEN for {symbol}: {e}")
        return error_response("数据源暂时不可用，请稍后重试", code=503)
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"[Peers] Data processing error for peer data {symbol}: {e}", exc_info=True)
        return error_response(f"数据处理失败: {str(e)}")
    except Exception as e:
        logger.error(f"[Peers] Error fetching peer data for {symbol}: {e}", exc_info=True)
        return error_response(f"获取同业比较数据失败: {str(e)}")


# ── 公司公告端点 ─────────────────────────────────────────────────
@router.get("/{symbol}/announcements")
async def get_announcements(symbol: str, page: int = 1, page_size: int = 20):
    """
    获取公司公告数据
    数据来源: akshare stock_individual_notice_report
    """
    symbol = normalize_f9_symbol(symbol)
    cache_key = f"announcements_{symbol}_{page}"
    cached = get_cached(cache_key)
    if cached:
        logger.info(f"[Announcements] Cache hit for {symbol} page {page}")
        return success_response(cached)
    
    if not check_akshare_circuit():
        return error_response("数据源暂时不可用，请稍后重试", code=503)
    
    try:
        import akshare as ak
        import pandas as pd
        
        def fetch_announcements():
            try:
                with akshare_breaker:
                    df = ak.stock_individual_notice_report(security=symbol)
                
                if df is None or df.empty:
                    return []
                
                all_announcements = []
                for _, row in df.iterrows():
                    announcement = {
                        "date": str(row.get("公告日期", "") or ""),
                        "title": str(row.get("公告标题", "") or ""),
                        "type": str(row.get("公告类型", "") or ""),
                        "code": str(row.get("代码", "") or ""),
                        "name": str(row.get("名称", "") or ""),
                        "url": str(row.get("网址", "") or ""),
                    }
                    all_announcements.append(announcement)
                
                return all_announcements
            except CircuitBreakerOpen as e:
                logger.warning(f"[Announcements] Circuit breaker OPEN: {e}")
                return []
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"[Announcements] Data processing error for {symbol}: {e}")
                return []
            except Exception as e:
                logger.warning(f"[Announcements] Failed to fetch for {symbol}: {e}")
                return []
        
        loop = asyncio.get_event_loop()
        all_data = await asyncio.wait_for(
            loop.run_in_executor(_executor, fetch_announcements),
            timeout=AKSHARE_TIMEOUT
        )
        
        total = len(all_data)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_data = all_data[start_idx:end_idx]
        
        result = {
            "announcements": paginated_data,
            "total": total,
            "page": page,
            "page_size": page_size
        }
        
        set_cached(cache_key, result)
        
        logger.info(f"[Announcements] Successfully fetched {total} announcements for {symbol}, returning page {page}")
        return success_response(result)
        
    except asyncio.TimeoutError:
        logger.warning(f"[Announcements] Timeout for {symbol}")
        return error_response("请求超时，请稍后重试", code=504)
    except CircuitBreakerOpen as e:
        logger.warning(f"[Announcements] Circuit breaker OPEN for {symbol}: {e}")
        return error_response("数据源暂时不可用，请稍后重试", code=503)
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"[Announcements] Data processing error for {symbol}: {e}")
        return error_response(f"数据处理失败: {str(e)}")
    except Exception as e:
        logger.error(f"[Announcements] Error fetching data for {symbol}: {e}")
        return error_response(f"获取公司公告数据失败: {str(e)}")
