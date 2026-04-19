"""
fund.py — 国内基金数据路由
支持：ETF K线、实时行情、场外基金排行、货币基金排行、基金重仓股

数据源：
  - ETF K线/实时行情：新浪财经（无需代理）
  - 场外基金/货币基金/重仓股：AkShare 东方财富
"""
import requests
import logging
from fastapi import APIRouter, Query, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fund", tags=["fund"])

SINA_BASE = "https://quotes.sina.cn/cn/api/json_v2.php"
# Sina K线 scale：240=日K，1200=周K（约5日×5），5440=月K（约22日×24）
_ETF_SCALE_MAP = {"daily": 240, "weekly": 1200, "monthly": 5440}

# ══════════════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════════════

def _sina_etf_history(code: str, period: str = "daily", limit: int = 300) -> list:
    """
    通过新浪财经获取 ETF 历史K线（无需代理）。
    返回格式与 /market/history 一致（date/open/high/low/close/volume/amount/change_pct/amplitude）。
    """
    sina_sym = f"sh{code}" if not code.startswith(("sh", "sz")) else code
    scale = _ETF_SCALE_MAP.get(period, 240)

    try:
        params = {"symbol": sina_sym, "scale": scale, "ma": "no", "datalen": limit}
        resp = requests.get(f"{SINA_BASE}/CN_MarketDataService.getKLineData",
                            params=params, timeout=15)
        items = resp.json()
        if not isinstance(items, list):
            return []
    except Exception as e:
        logger.warning(f"[Sina ETF] {code} 请求失败: {e}")
        return []

    rows = []
    for i, r in enumerate(items):
        day   = r.get("day", "")
        open_ = float(r.get("open", 0) or 0)
        close = float(r.get("close", 0) or 0)
        high  = float(r.get("high", 0) or 0)
        low   = float(r.get("low", 0) or 0)
        vol   = float(r.get("volume", 0) or 0)
        amt   = float(r.get("amount", 0) or 0)

        prev_close = rows[i - 1]["close"] if i > 0 else open_
        chg_pct    = round((close - prev_close) / prev_close * 100, 2) if prev_close else 0
        amplitude  = round((high - low) / prev_close * 100, 2) if prev_close else 0

        rows.append({
            "date":       day,
            "open":       round(open_,  3),
            "close":      round(close,  3),
            "high":       round(high,   3),
            "low":        round(low,    3),
            "volume":     round(vol,    0),
            "amount":     round(amt,    2),
            "amplitude":  amplitude,
            "change_pct": chg_pct,
            "change":     round(close - prev_close, 3) if i > 0 else 0,
            "turnover":   0,
        })

    # Sina 数据从旧到新 → 改为从新到旧（与 /market/history 顺序一致）
    rows.reverse()
    return rows


# ══════════════════════════════════════════════════════════════════════
# ETF 历史K线
# ══════════════════════════════════════════════════════════════════════

@router.get("/etf/history")
async def etf_history(
    code:   str = Query(..., description="ETF 代码（6位数字，如 510300）"),
    period: str = Query("daily", description="周期：daily / weekly / monthly"),
    limit:  int = Query(300, description="返回条数上限"),
    offset: int = Query(0,  description="分页偏移"),
):
    """
    获取 ETF 历史K线（新浪财经，无需代理）。

    ETF 代码规则（6位数字）：
      51xxxx — 上交所 ETF
      15xxxx — 深交所 ETF
      56xxxx — 上交所创新型 ETF

    返回格式与 /market/history/{symbol} 完全一致，前端 K 线组件可直接复用。
    """
    code = code.strip()
    if len(code) != 6 or not code.isdigit():
        raise HTTPException(400, f"无效ETF代码: {code}")

    rows = _sina_etf_history(code, period=period, limit=limit + offset + 50)
    total = len(rows)
    rows = rows[offset: offset + limit] if offset else rows[:limit]

    return {
        "code":    0,
        "symbol":  code,
        "period":  period,
        "adjust":  "none",
        "data":    rows,
        "total":   total,
        "offset":  offset,
        "limit":   limit,
        "has_more": (offset + len(rows)) < total,
    }


# ══════════════════════════════════════════════════════════════════════
# ETF 实时行情
# ══════════════════════════════════════════════════════════════════════

@router.get("/etf/info")
async def etf_info(
    code: str = Query(..., description="ETF 代码（6位数字）"),
):
    """
    获取 ETF 实时行情（成交价/涨跌幅/成交量/实时估算净值）。
    数据来源：新浪财经（无需代理）。
    """
    code = code.strip()
    if len(code) != 6 or not code.isdigit():
        raise HTTPException(400, f"无效ETF代码: {code}")

    try:
        sina_sym = f"sh{code}"
        url = f"https://hq.sinajs.cn/list={sina_sym}"
        headers = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        text = resp.text.strip()

        if 'hq_str_' not in text or "," not in text:
            return {"code": 0, "symbol": code, "data": None, "message": "无数据"}

        data_str = text.split('"')[1] if '"' in text else ""
        parts = data_str.split(",")
        if len(parts) < 32:
            return {"code": 0, "symbol": code, "data": None, "message": "数据解析失败"}

        name     = parts[0]
        yclose   = float(parts[2]) if parts[2] else 0
        price    = float(parts[3]) if parts[3] else 0
        high     = float(parts[4]) if parts[4] else 0
        low      = float(parts[5]) if parts[5] else 0
        volume   = float(parts[8]) if parts[8] else 0
        amount   = float(parts[9]) if parts[9] else 0
        chg_pct  = round((price - yclose) / yclose * 100, 2) if yclose else 0
        chg_val  = round(price - yclose, 3) if yclose else 0

        return {
            "code":   0,
            "symbol": code,
            "name":   name,
            "data": {
                "price":      price,
                "prev_close": yclose,
                "change":     chg_val,
                "change_pct": chg_pct,
                "high":       high,
                "low":        low,
                "volume":     round(volume, 0),
                "amount":     round(amount, 2),
            }
        }
    except Exception as e:
        logger.warning(f"[ETF Info] {code} 获取失败: {e}")
        return {"code": 0, "symbol": code, "data": None, "message": str(e)}


# ══════════════════════════════════════════════════════════════════════
# 场外基金 / 货币基金 排行（AkShare，需 HTTP_PROXY）
# ══════════════════════════════════════════════════════════════════════

def _ak_available():
    try:
        import akshare as ak
        return True
    except Exception:
        return False


@router.get("/open/rank")
async def open_fund_rank(
    sort:  str = Query("今年来", description="排序：今年来/近1年/近3年/近6月/近1月/近1周/日增长率"),
    order: str = Query("desc",  description="desc / asc"),
    top:   int = Query(100,    description="返回条数上限（最大500）"),
):
    """场外基金排行（股票型/混合型/债券型/指数型）。需要 HTTP_PROXY。"""
    if not _ak_available():
        return {"code": 1, "data": [], "total": 0,
                "error": "AkShare 不可用，请检查安装"}

    import akshare as ak
    sort_map = {"今年来": "今年来", "近1年": "近1年", "近3年": "近3年",
                "近6月": "近6月", "近1月": "近1月", "近1周": "近1周",
                "日增长率": "日增长率"}
    sf = sort_map.get(sort, "今年来")
    top = min(top, 500)

    try:
        df = ak.fund_open_fund_rank_em(symbol="全部")
        if df is None or df.empty:
            return {"code": 0, "data": [], "total": 0}

        asc = (order == "asc")
        if sf in df.columns:
            df = df.sort_values(by=sf, ascending=asc)
        else:
            df = df.sort_values(by="今年来", ascending=False)
        df = df.head(top)

        rows = []
        for r in df.to_dict("records"):
            def _f(v): return float(v) if v not in (None, "---", "") else None
            rows.append({
                "code":      str(r.get("基金代码", "")),
                "name":      r.get("基金简称", ""),
                "nav_date":  r.get("日期", ""),
                "nav":       _f(r.get("单位净值")),
                "nav_accum": _f(r.get("累计净值")),
                "daily_chg": _f(r.get("日增长率")),
                "chg_1w":    r.get("近1周"),
                "chg_1m":    r.get("近1月"),
                "chg_3m":    r.get("近3月"),
                "chg_6m":    r.get("近6月"),
                "chg_1y":    r.get("近1年"),
                "chg_3y":    r.get("近3年"),
                "chg_ytd":   r.get("今年来"),
                "fee":       str(r.get("手续费", "未知")),
            })
        return {"code": 0, "data": rows, "total": len(rows), "sort_by": sf}

    except Exception as e:
        logger.warning(f"[Fund Open Rank] 获取失败: {e}")
        return {"code": 0, "data": [], "total": 0, "error": str(e),
                "note": "需要 HTTP_PROXY 访问东方财富"}


@router.get("/money/rank")
async def money_fund_rank(
    sort:  str = Query("7日年化", description="排序：万份收益/7日年化"),
    order: str = Query("desc", description="desc / asc"),
    top:   int = Query(100, description="返回条数上限"),
):
    """货币基金行情排行。需要 HTTP_PROXY。"""
    if not _ak_available():
        return {"code": 1, "data": [], "total": 0,
                "error": "AkShare 不可用"}

    import akshare as ak
    top = min(top, 500)

    try:
        df = ak.fund_money_fund_daily_em()
        if df is None or df.empty:
            return {"code": 0, "data": [], "total": 0}

        yld_col = next((c for c in df.columns if "7日年化" in c), None)
        w_col   = next((c for c in df.columns if "万份收益" in c and "2026" in c), None)

        if yld_col:
            df = df.sort_values(by=yld_col, ascending=(order == "asc"))
        df = df.head(top)

        rows = []
        for _, r in df.iterrows():
            rows.append({
                "code":     str(r.get("基金代码", "")),
                "name":     r.get("基金简称", ""),
                "nav_date": yld_col.replace("-7日年化%", "").replace("2026-", "") if yld_col else "",
                "w_profit": r.get(w_col) if w_col else None,
                "yld_7d":   r.get(yld_col) if yld_col else None,
                "manager":  r.get("基金经理", ""),
                "est_date": r.get("成立日期", ""),
                "fee":      r.get("手续费", "未知"),
            })
        return {"code": 0, "data": rows, "total": len(rows)}

    except Exception as e:
        logger.warning(f"[Fund Money Rank] 获取失败: {e}")
        return {"code": 0, "data": [], "total": 0, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════
# 基金重仓股
# ══════════════════════════════════════════════════════════════════════

@router.get("/portfolio/{code}")
async def fund_top_holdings(code: str):
    """获取基金最新一期前10大重仓股（AkShare，无需额外代理）。"""
    if not _ak_available():
        return {"code": 1, "symbol": code, "data": [], "error": "AkShare 不可用"}

    import akshare as ak
    code = code.strip()
    if len(code) != 6 or not code.isdigit():
        raise HTTPException(400, f"无效基金代码: {code}")

    try:
        df = ak.fund_portfolio_hold_em(symbol=code)
        if df is None or df.empty:
            return {"code": 0, "data": [], "symbol": code}

        quarter = df["季度"].iloc[0] if "季度" in df.columns else ""
        df_q = df[df["季度"] == quarter].head(10)

        rows = []
        for _, r in df_q.iterrows():
            rows.append({
                "symbol":    str(r.get("股票代码", "")),
                "name":      r.get("股票名称", ""),
                "weight":    r.get("占净值比例"),
                "shares":    r.get("持股数"),
                "mkt_value": r.get("持仓市值"),
                "quarter":   r.get("季度", ""),
            })
        return {"code": 0, "symbol": code, "quarter": quarter, "data": rows}

    except Exception as e:
        logger.warning(f"[Fund Portfolio] {code} 获取失败: {e}")
        return {"code": 0, "symbol": code, "data": [], "error": str(e)}
