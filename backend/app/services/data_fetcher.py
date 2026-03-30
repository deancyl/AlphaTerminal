"""
实时行情拉取 - Phase 3
- A股指数：新浪/腾讯实时行情API（push2.eastmoney.com 已确认不可用，换用 Sina HQ）
- 利率：akshare.macro_china_shibor_all（可用）
关键：国内域名不走代理（NO_PROXY）
"""
import os
import re
import time
import logging
import httpx

logger = logging.getLogger(__name__)

# ── 国内金融域名不走代理 ─────────────────────────────────────────────────
NO_PROXY_DOMESTIC = (
    "localhost,127.0.0.1,::1,"
    "hq.sinajs.cn,finance.sina.com.cn,sinajs.cn,sina.com.cn,"
    "qt.gtimg.cn,gu.qq.com,"
    "eastmoney.com,eastmoney.cn,push2.eastmoney.com,datacenter.eastmoney.com,"
    "cninfo.com.cn,csrc.gov.cn,"
    "chinamoney.com.cn,shibor.org,"
    "nanjing.gov.cn,gov.cn"
)
os.environ.setdefault("NO_PROXY", NO_PROXY_DOMESTIC)
os.environ.setdefault("no_proxy", NO_PROXY_DOMESTIC)

SINA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn",
}


def _row(symbol: str, name: str, market: str,
         price, change_pct, volume, data_type: str = "index") -> dict:
    return {
        "symbol":     symbol,
        "name":       name,
        "market":     market,
        "price":      float(price) if price not in (None, "", "NA", "NaN") else None,
        "change_pct": float(change_pct) if change_pct not in (None, "", "NA", "NaN") else None,
        "volume":     float(volume) if volume not in (None, "", "NA", "NaN") else None,
        "timestamp":  int(time.time()),
        "data_type":  data_type,
    }


def _parse_sina_hq(raw: str) -> dict | None:
    """
    解析 Sina HQ 格式: var hq_str_s_sh000001="上证指数,3923.2869,9.5631,0.24,5955894,83982243";
    字段: 名称, 当前价, 涨跌额, 涨跌幅%, 成交量(手), 成交额(元)
    """
    m = re.search(r'"([^"]+)"', raw)
    if not m:
        return None
    parts = m.group(1).split(",")
    if len(parts) < 6:
        return None
    try:
        return {
            "name":       parts[0],
            "price":      float(parts[1]),
            "change":     float(parts[2]),
            "change_pct": float(parts[3]),
            "volume":     float(parts[4]) * 100,  # 手→股
            "turnover":   float(parts[5]),
        }
    except (ValueError, IndexError):
        return None


# ── A 股指数 ─────────────────────────────────────────────────────────────
def fetch_china_indices() -> list[dict]:
    """
    通过新浪实时行情 API 获取 A 股核心指数（上证、沪深300、深证、创业板）
    格式: s_sh000001 (sh=上证, sz=深证)
    """
    rows = []
    codes = "s_sh000001,s_sh000300,s_sz399001,s_sz399006"
    sym_map = {
        "s_sh000001": ("000001", "上证指数",  "AShare"),
        "s_sh000300": ("000300", "沪深300",  "AShare"),
        "s_sz399001": ("399001", "深证成指",  "AShare"),
        "s_sz399006": ("399006", "创业板指",  "AShare"),
    }

    try:
        r = httpx.get(
            f"https://hq.sinajs.cn/list={codes}",
            headers=SINA_HEADERS,
            timeout=10,
        )
        if r.status_code != 200:
            raise RuntimeError(f"Sina 返回状态码 {r.status_code}")

        lines = r.text.strip().split("\n")
        for line in lines:
            key_m = re.search(r"hq_str_s_(sh\d+|sz\d+)=", line)
            if not key_m:
                continue
            code_key = "s_" + key_m.group(1)
            if code_key not in sym_map:
                continue
            sym, display_name, market = sym_map[code_key]
            parsed = _parse_sina_hq(line)
            if parsed:
                rows.append(_row(
                    symbol=sym, name=display_name, market=market,
                    price=parsed["price"],
                    change_pct=parsed["change_pct"],
                    volume=parsed["volume"],
                ))
                logger.info(f"[Sina] {display_name}: {parsed['price']} "
                            f"({parsed['change_pct']:+.2f}%)")
            else:
                logger.warning(f"[Sina] 解析失败: {line[:80]}")
    except Exception as e:
        logger.error(f"[Sina] fetch_china_indices 失败: {type(e).__name__}: {e}", exc_info=True)

    return rows


# ── SHIBOR / LPR 利率 ────────────────────────────────────────────────────
def fetch_shibor() -> list[dict]:
    """
    拉取银行间 SHIBOR 利率（通过 akshare.macro_china_shibor_all）
    返回最新可用日期的数据
    """
    rows = []
    try:
        import akshare as ak
        df = ak.macro_china_shibor_all()
        df.columns = [c.strip() for c in df.columns]

        # 取最新一行
        latest = df.iloc[-1]
        fields = [
            ("O/N-定价", "shibor_1d", "SHIBOR 隔夜"),
            ("1W-定价",  "shibor_1w", "SHIBOR 1周"),
            ("1M-定价",  "shibor_1m", "SHIBOR 1月"),
            ("3M-定价",  "shibor_3m", "SHIBOR 3月"),
            ("1Y-定价",  "shibor_1y", "SHIBOR 1年"),
        ]
        for col_key, sym_key, name in fields:
            val = latest.get(col_key)
            if val is not None and str(val).replace(".", "").replace("-", "").isdigit():
                rows.append({
                    "symbol":    sym_key,
                    "name":      name,
                    "market":    "FUND",
                    "price":     float(val),
                    "change_pct": None,
                    "volume":    None,
                    "timestamp": int(time.time()),
                    "data_type": "rate",
                })
                logger.info(f"[AkShare] {name}: {val}%")
        # LPR
        try:
            df_lpr = ak.macro_china_lpr()
            df_lpr.columns = [c.strip() for c in df_lpr.columns]
            lpr_latest = df_lpr.iloc[-1]
            lpr1y = lpr_lpr1y = None
            for col in lpr_latest.index:
                if "1Y" in str(col) or "一年" in str(col):
                    lpr1y = lpr_latest[col]
                    break
            if lpr1y:
                rows.append({
                    "symbol":    "lpr_1y",
                    "name":      "LPR 1年",
                    "market":    "FUND",
                    "price":     float(lpr1y),
                    "change_pct": None,
                    "volume":    None,
                    "timestamp": int(time.time()),
                    "data_type": "rate",
                })
                logger.info(f"[AkShare] LPR 1年: {lpr1y}%")
        except Exception as e:
            logger.warning(f"[AkShare] LPR 获取失败: {e}")

    except Exception as e:
        logger.error(f"[AkShare] fetch_shibor 失败: {type(e).__name__}: {e}", exc_info=True)

    return rows


def fetch_all_and_buffer():
    """聚合拉取 + 写入 write_buffer（供 APScheduler 调用）"""
    all_rows = []
    idx_rows = fetch_china_indices()
    shibor_rows = fetch_shibor()
    all_rows.extend(idx_rows)
    all_rows.extend(shibor_rows)

    if all_rows:
        from app.db import buffer_insert
        try:
            buffer_insert(all_rows)
            logger.info(f"[DataFetcher] 写入 {len(all_rows)} 条到 write_buffer "
                        f"(指数 {len(idx_rows)} 条, 利率 {len(shibor_rows)} 条)")
        except Exception as e:
            logger.error(f"[DataFetcher] buffer_insert 失败: {e}", exc_info=True)
    else:
        logger.warning("[DataFetcher] 本次未拉到任何数据（所有接口均失败）")
