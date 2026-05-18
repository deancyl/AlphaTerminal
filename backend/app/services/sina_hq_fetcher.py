"""
Sina HQ 行情抓取器 v3 - Phase 3
数据源：腾讯 qt.gtimg.cn（个股）+ 新浪行业板块 Sina Industry Board
"""
import logging
import time as time_module
from datetime import datetime

import httpx
logger = logging.getLogger(__name__)


def _get_hs300_pool() -> list[str]:
    """
    Task 4: 沪深300成分股抓取（熔断优化：限制最大股票数以防卡死）
    返回格式: ["sh600519", "sz000858", ...]
    最多取 100 只（熔断上限），覆盖 HS300 核心蓝筹
    """
    try:
        import akshare as ak
        # 尝试 index_stock_cons樣本（含中文）
        func_names = ["index_stock_cons樣本", "index_stock_cons"]
        df = None
        for fname in func_names:
            try:
                func = getattr(ak, fname, None)
                if func:
                    df = func(symbol="000300")
                    if df is not None and not df.empty:
                        logger.info(f"[SinaHQ] HS300 via {fname}: {len(df)} rows")
                        break
            except Exception as e:
                logger.warning(f"[SinaHQ] HS300 fetch via {fname} failed: {type(e).__name__}: {e}")
                continue

        if df is None or df.empty:
            logger.warning("[SinaHQ] 所有 HS300 接口均无数据，使用 FOCUS_STOCKS")
            return []

        codes = []
        for _, row in df.iterrows():
            try:
                code = str(row.get("品种代码", "") or "")
                if not code:
                    continue
                prefix = "sh" if code.startswith(("6", "5")) else "sz"
                codes.append(f"{prefix}{code}")
            except Exception as e:
                logger.warning(f"[SinaHQ] Failed to parse HS300 row: {e}")
                continue
        logger.info(f"[SinaHQ] HS300 成分股: {len(codes)} 只")
        return codes[:100]  # 熔断上限 100 只
    except Exception as e:
        logger.warning(f"[SinaHQ] HS300 获取失败: {type(e).__name__}: {e}")
    return []


# ── 沪深300成分股（Task 4: 熔断优化）────────────────────────────────
_HS300_POOL = _get_hs300_pool()

# ── 重点关注股票池（50只，覆盖各行业龙头）─────────────────────────────
# 核心股票池（第一批 15 只，最重要的蓝筹，足够展示分布）
FOCUS_STOCKS = [
    # 白酒/消费
    "sh600519", "sz000858", "sh600887",
    # 银行
    "sh601318", "sh600036", "sh601166",
    # 保险/券商
    "sh601628", "sh600030", "sh601688",
    # 科技/新能源
    "sh600585", "sz002594", "sz300750",
    # 医药
    "sh600276", "sz000538", "sh600196",
]


def get_stock_pool() -> list[str]:
    """
    Task 4: 获取实际使用的股票池
    优先用 HS300（最多100只），备选 FOCUS_STOCKS（15只）
    """
    if _HS300_POOL:
        return _HS300_POOL
    return FOCUS_STOCKS


def fetch_hq_batch(codes: list[str]) -> list[dict]:
    """
    批量获取股票实时行情（腾讯 qt.gtimg.cn）
    格式: v_sh600519="1~贵州茅台~600519~1450.00~..."
    parts[0]=未知, parts[1]=名称, parts[2]=6位代码, parts[3]=当前价, parts[4]=昨收, ...
    """
    if not codes:
        return []

    batch_size = 45
    all_rows = []

    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        joined = ",".join(batch)
        try:
            r = httpx.get(
                f"https://qt.gtimg.cn/q={joined}",
                headers={
                    "Referer": "https://gu.qq.com",
                    "User-Agent": "Mozilla/5.0",
                },
                timeout=15,
            )
            text = r.text
            for line in text.strip().split("\n"):
                if "=" not in line or "v_" not in line:
                    continue
                try:
                    inner = line.split("=", 1)[1].strip().strip('"')
                    parts = inner.split("~")
                    if len(parts) < 33:
                        continue

                    raw_code = parts[0].strip()
                    name     = parts[1].strip()
                    code     = parts[2].strip()        # ← 真正的 6 位代码
                    price    = float(parts[3]) if parts[3] else 0.0
                    y_close  = float(parts[4]) if parts[4] else price
                    open_p   = float(parts[5]) if parts[5] else price
                    volume   = float(parts[6]) if parts[6] else 0.0
                    chg_pct  = float(parts[32]) if parts[32] else 0.0
                    chg_val  = round(price - y_close, 2) if y_close else 0.0
                    # 腾讯字段：[37]=成交额(元) [38]=换手率(%)
                    amount   = float(parts[37]) if (len(parts) > 37 and parts[37]) else 0.0  # 已是元，无需 *10000
                    turnover = float(parts[38]) if (len(parts) > 38 and parts[38]) else 0.0   # 换手率(%)

                    if not name or price <= 0 or not code:
                        continue

                    # 判断市场
                    if raw_code.startswith("sh") or code[0] in ("6", "5"):
                        market = "SH"
                    elif raw_code.startswith("sz") or code[0] in ("0", "1", "3"):
                        market = "SZ"
                    else:
                        market = "OTHER"

                    all_rows.append({
                        "code":     code,
                        "name":     name,
                        "price":    round(price, 2),
                        "yesterday": round(y_close, 2),
                        "open":     round(open_p, 2),
                        "volume":   round(volume, 0),
                        "chg":      chg_val,
                        "chg_pct":  round(chg_pct, 2),
                        "turnover": round(turnover, 2),
                        "amount":   round(amount, 0),   # 成交额(元)
                        "market":   market,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    })
                except ValueError as e:
                    logger.warning(f"[SinaHQ] Invalid value in stock data: {e}")
                    continue
                except IndexError as e:
                    logger.warning(f"[SinaHQ] Malformed stock data: {e}")
                    continue

            time_module.sleep(0.05)

        except httpx.TimeoutException as e:
            logger.warning(f"[SinaHQ] Batch timeout: {e}")
            continue
        except httpx.HTTPStatusError as e:
            logger.warning(f"[SinaHQ] HTTP {e.response.status_code}: {e}")
            continue
        except Exception as e:
            logger.error(f"[SinaHQ] Unexpected error: {type(e).__name__}: {e}", exc_info=True)
            continue

    logger.info(f"[SinaHQ] fetched {len(all_rows)} stocks")
    return all_rows


# ── Sina 行业板块 ──────────────────────────────────────────
def fetch_sina_industry_board() -> list[dict]:
    """
    从新浪行业板块接口抓取真实行业数据
    """
    try:
        r = httpx.get(
            "https://vip.stock.finance.sina.com.cn/q/view/newFLJK.php?param=class2",
            headers={
                "Referer": "https://finance.sina.com.cn",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=10,
        )
        text = r.text
        sectors = []

        for line in text.strip().split("\n"):
            if "hangye_" not in line:
                continue
            try:
                _, val = line.split(":", 1)
                parts = val.strip().split(",")
                if len(parts) < 5:
                    continue
                name    = parts[1].strip()
                chg_pct = float(parts[4]) if parts[4] else 0.0
                top_code = parts[8].strip() if len(parts) > 8 and parts[8] else ""
                top_name = parts[12].strip() if len(parts) > 12 and parts[12] else ""
                if not name:
                    continue
                sectors.append({
                    "name":       name,
                    "change_pct": round(chg_pct, 2),
                    "top_stock":  {"name": top_name, "code": top_code} if top_name else None,
                })
            except ValueError as e:
                logger.warning(f"[SinaIndustry] Invalid value: {e}")
                continue
            except IndexError as e:
                logger.warning(f"[SinaIndustry] Malformed data: {e}")
                continue

        sectors.sort(key=lambda x: x["change_pct"], reverse=True)
        logger.info(f"[SinaIndustry] 抓到 {len(sectors)} 个真实行业板块")
        return sectors[:15]
    except Exception as e:
        logger.warning(f"[SinaIndustry] 拉取失败: {type(e).__name__}: {e}")
        return []


def build_histogram_from_rows(rows: list[dict]) -> dict:
    """
    基于股票实时数据构建涨跌分布直方图（11桶）
    """
    BUCKETS = [
        ("跌停",    -1e9,  -9.9),
        ("<-7%",  -9.9,   -7.0),
        ("-7%~-5%", -7.0, -5.0),
        ("-5%~-2%", -5.0, -2.0),
        ("-2%~0%",  -2.0,  0.0),
        ("平盘(0%)",  0.0,  0.0),
        ("0%~2%",    0.0,  2.0),
        ("2%~5%",    2.0,  5.0),
        ("5%~7%",    5.0,  7.0),
        (">7%",      7.0,  9.9),
        ("涨停",      9.9, 1e9),
    ]

    if not rows:
        return {"buckets": [], "total": 0, "advance": 0, "decline": 0,
                "unchanged": 0, "limit_up": 0, "limit_down": 0,
                "up_ratio": 0.0, "timestamp": ""}

    pcts = [float(r["chg_pct"]) for r in rows]
    total = len(rows)
    advance = sum(1 for p in pcts if p > 0)
    decline = sum(1 for p in pcts if p < 0)
    unchanged = sum(1 for p in pcts if p == 0)
    limit_up = sum(1 for p in pcts if p >= 9.9)
    limit_down = sum(1 for p in pcts if p <= -9.9)

    buckets = []
    for label, lo, hi in BUCKETS:
        if label == "平盘(0%)":
            count = sum(1 for p in pcts if p == 0.0)
        else:
            count = sum(1 for p in pcts if lo < p <= hi)
        color = "#14b143" if lo < 0 else "#ef232a" if lo >= 0 else "#6b7280"
        buckets.append({
            "label": label,
            "count": count,
            "pct":   round(count / total * 100, 2) if total > 0 else 0,
            "color": color,
        })

    return {
        "buckets":    buckets,
        "total":      total,
        "advance":    advance,
        "decline":    decline,
        "unchanged":  unchanged,
        "limit_up":   limit_up,
        "limit_down": limit_down,
        "up_ratio":   round(advance / total, 4) if total > 0 else 0,
        "timestamp":  rows[0]["timestamp"] if rows else "",
    }
