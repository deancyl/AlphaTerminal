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
import traceback
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
         price, change_pct, volume, data_type: str = "index",
         amount=None, turnover=None) -> dict:
    return {
        "symbol":     symbol,
        "name":       name,
        "market":     market,
        "price":      float(price) if price not in (None, "", "NA", "NaN") else None,
        "change_pct": float(change_pct) if change_pct not in (None, "", "NA", "NaN") else None,
        "volume":     float(volume) if volume not in (None, "", "NA", "NaN") else None,
        "amount":     float(amount) if amount not in (None, "", "NA", "NaN") else None,
        "turnover":   float(turnover) if turnover not in (None, "", "NA", "NaN") else None,
        "timestamp":  int(time.time()),
        "data_type":  data_type,
    }


def _parse_sina_hq(raw: str) -> dict | None:
    """
    解析 Sina HQ 格式: var hq_str_s_sh000001="上证指数,3923.2869,9.5631,0.24,5955894,83982243";
    完整34字段个股:
      [0]名称 [1]当前价 [2]昨收 [3]开盘 [4]最高 [5]最低
      [6]买一价 [7]卖一价
      [8]成交量(股) [9]成交额(元) [10]换手率(%)
      [11-33]盘口
    """
    m = re.search(r'"([^"]+)"', raw)
    if not m:
        return None
    parts = m.group(1).split(",")
    if len(parts) < 11:
        return None
    try:
        return {
            "name":       parts[0],
            "price":      float(parts[1]),
            "change":     float(parts[2]),
            "change_pct": float(parts[3]),
            "volume":     float(parts[8]) if len(parts) > 8 else 0,   # 成交量(股)
            "amount":     float(parts[9]) if len(parts) > 9 else 0,   # 成交额(元)
            "turnover":   float(parts[10]) if len(parts) > 10 else 0, # 换手率(%)
        }
    except (ValueError, IndexError):
        return None


def _parse_sina_index(raw: str) -> dict | None:
    """
    解析 Sina 指数格式（s_sh000001/s_sz399006 等）
    字段: [name, current, prev_close, open, high, low, ?, ?, amount, amount2, ..., date, time, ?]
    change_pct = (current - prev_close) / prev_close * 100
    """
    m = re.search(r'"([^"]+)"', raw)
    if not m:
        return None
    parts = m.group(1).split(",")
    if len(parts) < 6:   # Sina指数=6字段, 腾讯qt=78字段, 都满足
        return None
    try:
        current    = float(parts[1])    # 当前价
        prev_close = float(parts[2])    # 昨收
        chg_pct    = float(parts[3]) if parts[3] else 0.0   # Sina指数直接提供涨跌幅%
        return {
            "name":       parts[0],
            "price":      current,
            "change":     round(current - prev_close, 3),
            "change_pct": round(chg_pct, 2),
            "volume":     0,
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
            parsed = _parse_sina_index(line)  # 用指数专用解析器（字段顺序不同）
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
        logger.error(f"[Sina] fetch_china_indices 失败: {type(e).__name__}: {e}")
        traceback.print_exc()

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
            logger.error(f"[AkShare] LPR 获取失败: {type(e).__name__}: {e}")
            traceback.print_exc()

    except Exception as e:
        logger.error(f"[AkShare] fetch_shibor 失败: {type(e).__name__}: {e}")
        traceback.print_exc()

    return rows


# ── Phase 6: 全球市场指数 ───────────────────────────────────────────────
def fetch_global_indices() -> list[dict]:
    """
    获取全球核心指数：恒生(HSI)、道琼斯(DJI)、纳斯达克(IXIC)、标普500(SPX)
    策略1：腾讯财经 qt.gtimg.cn（直连，不走代理）
    策略2：Sina 国际行情（退补）
    """
    rows = []

    # 策略A：腾讯财经（主要数据源，直连）
    try:
        import subprocess
        codes = "hkHSI,usIXIC,usDJI,usSPX"
        raw = subprocess.check_output(
            ["curl", "-s", "--max-time", "8",
             f"https://qt.gtimg.cn/q={codes}",
             "-H", "Referer: https://gu.qq.com",
             "-H", "User-Agent: Mozilla/5.0"],
            stderr=subprocess.DEVNULL
        )
        text = raw.decode("GBK", errors="replace")
        logger.info(f"[Tencent] 全球指数响应: {text[:150]}")

        sym_map = {
            "hkHSI":  ("HSI",  "恒生指数",   "HK"),
            "usIXIC": ("IXIC", "纳斯达克",   "US"),
            "usDJI":  ("DJI",  "道琼斯",     "US"),
            "usSPX":  ("SPX",  "标普500",    "US"),
        }
        for line in text.strip().split("\n"):
            m = re.search(r'v_(\w+)="([^"]+)"', line)
            if not m:
                continue
            code_key = m.group(1)
            if code_key not in sym_map:
                continue
            sym, disp, mkt = sym_map[code_key]
            parts = m.group(2).split("~")
            if len(parts) < 6:
                continue
            try:
                price   = float(parts[3]) if parts[3] else None
                chg_pct = float(parts[32]) if len(parts) > 32 and parts[32] else 0.0
                if price:
                    rows.append(_row(sym, disp, mkt, price, chg_pct, None, "global"))
                    logger.info(f"[Tencent] {disp}: {price} ({chg_pct:+.2f}%)")
            except (ValueError, IndexError) as e:
                logger.warning(f"[Tencent] 解析 {disp} 失败: {e}")
        if rows:
            logger.info(f"[Tencent] 全球指数拉取成功 {len(rows)} 只")
            return rows
    except Exception as e:
        logger.warning(f"[Tencent] 全球指数失败，退补Sina: {type(e).__name__}: {e}")
        traceback.print_exc()

    # 策略B（退补）：Sina 国际行情
    try:
        codes_map = {
            "int_hf_HSI":  ("HSI",  "恒生指数",  "HK"),
            "int_hf_DJI":  ("DJI",  "道琼斯",    "US"),
            "int_hf_IXIC": ("IXIC", "纳斯达克",   "US"),
            "int_hf_SPX":  ("SPX",  "标普500",   "US"),
            "int_hf_N225": ("N225", "日经225",   "JP"),
        }
        codes = ",".join(codes_map.keys())
        r = httpx.get(f"https://hq.sinajs.cn/list={codes}", headers=SINA_HEADERS, timeout=8)
        if r.status_code == 200:
            for line in r.text.strip().split("\n"):
                m = re.search(r'hq_str_int_hf_(\w+)="([^"]+)"', line)
                if not m:
                    continue
                key = m.group(1)
                if key not in codes_map:
                    continue
                sym, disp, mkt = codes_map[key]
                parts = m.group(2).split(",")
                if len(parts) >= 4 and parts[3]:
                    try:
                        price = float(parts[3])
                        prev  = float(parts[2]) if parts[2] else price
                        chg   = (price - prev) / prev * 100 if prev else 0
                        rows.append(_row(sym, disp, mkt, price, chg, None, "global"))
                        logger.info(f"[Sina] {disp}: {price} ({chg:+.2f}%)")
                    except (ValueError, IndexError):
                        pass
    except Exception as e:
        logger.warning(f"[Sina] 全局指数退补失败: {type(e).__name__}: {e}")

    return rows


# ── Phase 6: 行业板块 Top 5 ─────────────────────────────────────────────
def fetch_industry_sectors() -> list[dict]:
    """
    获取当天涨幅 Top5 行业板块
    通过新浪 vip.stock.finance.sina.com.cn（直连，不走代理，无 encoding 问题）
    格式: hangye_XX,行业名,股票数,点位,涨跌额,涨跌幅%
    """
    try:
        import requests, re, json
        r = requests.get(
            "https://vip.stock.finance.sina.com.cn/q/view/newFLJK.php",
            params={"param": "class=hy", "type": "1"},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer": "https://finance.sina.com.cn",
                "Accept-Encoding": "gzip, deflate",
            },
            timeout=10,
        )
        r.encoding = "gbk"
        text = r.text

        # 解析 var S_Finance_bankuai_class=hy = {"hangye_XX":"..."}
        board_list = []
        for m in re.finditer(r'hangye_(\w+)":"([^"]+)"', text):
            code = m.group(1)
            fields = m.group(2).split(",")
            if len(fields) < 6:
                continue
            try:
                bname = fields[1].strip()
                chg_pct = float(fields[5])
                board_list.append({"name": bname, "change_pct": round(chg_pct, 2)})
            except (ValueError, IndexError):
                continue

        # 按涨幅降序取 Top5
        board_list.sort(key=lambda x: x["change_pct"], reverse=True)
        top5 = board_list[:5]
        board_json = json.dumps(top5, ensure_ascii=False)
        logger.info(f"[Sina] 行业板块Top5: {top5}")
        return [{
            "symbol":    "board_top5",
            "name":      "行业板块Top5",
            "market":    "BOARD",
            "price":     board_json,
            "change_pct": None,
            "volume":    None,
            "timestamp": int(time.time()),
            "data_type": "board_top5",
        }]
    except Exception as e:
        logger.error(f"[Sina] fetch_industry_sectors 失败: {type(e).__name__}: {e}")
        traceback.print_exc()
    return []


# ── Phase 6: 期货与大宗商品 ─────────────────────────────────────────────
def fetch_derivatives() -> list[dict]:
    """
    获取大宗商品：黄金（SGE基准价）、原油（国内能源价格）
    退补：尝试 Sina 期货接口 nf_ 格式
    """
    rows = []

    # ① 上海金基准价（SGE）
    try:
        import akshare as ak
        df_gold = ak.spot_golden_benchmark_sge()
        if not df_gold.empty:
            latest = df_gold.iloc[-1]
            price  = float(latest["晚盘价"]) if "晚盘价" in latest and latest["晚盘价"] else None
            if price:
                rows.append({
                    "symbol":    "GC",
                    "name":     "SGE黄金",
                    "market":   "COMEX",
                    "price":    price,
                    "change_pct": None,
                    "volume":   None,
                    "timestamp": int(time.time()),
                    "data_type": "derivative",
                })
                logger.info(f"[SGE] 黄金基准价: {price}")
    except Exception as e:
        logger.warning(f"[SGE] 黄金拉取失败: {type(e).__name__}: {e}")

    # ② 国内能源指数（综合）
    try:
        df_energy = ak.macro_china_energy_index()
        if not df_energy.empty:
            latest = df_energy.iloc[-1]
            val = latest.get("最新值")
            chg = latest.get("涨跌幅", 0)
            if val:
                rows.append({
                    "symbol":    "EC",
                    "name":     "能源指数",
                    "market":   "CHINA",
                    "price":    float(val),
                    "change_pct": float(chg) if chg else None,
                    "volume":   None,
                    "timestamp": int(time.time()),
                    "data_type": "derivative",
                })
                logger.info(f"[能源指数] 最新值: {val} 涨跌幅: {chg}")
    except Exception as e:
        logger.warning(f"[能源指数] 拉取失败: {type(e).__name__}: {e}")

    # ③ Sina 期货（IF期指 / 黄金 / 原油）退补
    try:
        codes_map = {
            "nf_IFL":  ("IF",  "IF当月主力",  "FUTURE"),
            "nf_GCFL": ("GC2", "Sina黄金",    "COMEX"),
            "nf_CLFL": ("CL2", "Sina原油",    "NYMEX"),
        }
        codes = ",".join(codes_map.keys())
        r = httpx.get(f"https://hq.sinajs.cn/list={codes}", headers=SINA_HEADERS, timeout=8)
        if r.status_code == 200:
            for line in r.text.strip().split("\n"):
                m_key = re.search(r'hq_str_nf_(\w+)="([^"]+)"', line)
                if not m_key:
                    continue
                code_key = m_key.group(1)
                if code_key not in codes_map:
                    continue
                sym, disp, mkt = codes_map[code_key]
                fields = m_key.group(2).split(",")
                if len(fields) >= 11 and fields[3]:
                    try:
                        price = float(fields[3])
                        chg   = float(fields[10]) if fields[10] else 0
                        vol   = float(fields[9])  if fields[9]  else None
                        rows.append({
                            "symbol":    sym,
                            "name":     disp,
                            "market":   mkt,
                            "price":    price,
                            "change_pct": chg,
                            "volume":   vol,
                            "timestamp": int(time.time()),
                            "data_type": "derivative",
                        })
                        logger.info(f"[Sina期货] {disp}: {price} ({chg:+.2f}%)")
                    except (ValueError, IndexError):
                        pass
    except Exception as e:
        logger.warning(f"[Sina期货] 退补失败: {type(e).__name__}: {e}")

    return rows


# ── Phase 7: 国内全部指数（10+）──────────────────────────────────────────
def fetch_china_all_indices() -> list[dict]:
    """
    通过新浪实时行情获取国内10+核心指数
    对应 CHINA_ALL_SYMBOLS
    """
    rows = []
    # Sina HQ 代码: s_sh=上证, s_sz=深证
    codes = (
        "s_sh000001,s_sh000300,s_sh000688,s_sh000905,s_sh000852,s_sh000016,"  # 上证系
        "s_sz399001,s_sz399006,s_sz000510,s_sz399100"                          # 深证系
    )
    sym_map = {
        "s_sh000001": ("000001", "上证指数",  "AShare"),
        "s_sh000300": ("000300", "沪深300",  "AShare"),
        "s_sh000688": ("000688", "科创50",   "AShare"),
        "s_sh000905": ("000905", "中证500",  "AShare"),
        "s_sh000852": ("000852", "中证1000", "AShare"),
        "s_sh000016": ("000016", "上证50",   "AShare"),
        "s_sz399001": ("399001", "深证成指", "AShare"),
        "s_sz399006": ("399006", "创业板指", "AShare"),
        "s_sz000510": ("000510", "上证380",  "AShare"),
        "s_sz399100": ("399100", "深证A指",  "AShare"),
    }
    try:
        r = httpx.get(f"https://hq.sinajs.cn/list={codes}", headers=SINA_HEADERS, timeout=10)
        if r.status_code != 200:
            raise RuntimeError(f"Sina 返回 {r.status_code}")
        for line in r.text.strip().split("\n"):
            key_m = re.search(r"hq_str_s_(sh\d+|sz\d+)=", line)
            if not key_m:
                continue
            code_key = "s_" + key_m.group(1)
            if code_key not in sym_map:
                continue
            sym, disp, mkt = sym_map[code_key]
            parsed = _parse_sina_hq(line)
            if parsed:
                rows.append(_row(sym, disp, mkt,
                                  parsed["price"], parsed["change_pct"], parsed["volume"],
                                  amount=parsed.get("amount"), turnover=parsed.get("turnover")))
                logger.info(f"[Sina] {disp}: {parsed['price']} ({parsed['change_pct']:+.2f}%)")
    except Exception as e:
        logger.error(f"[Sina] fetch_china_all_indices 失败: {type(e).__name__}: {e}")
    return rows


# ── Phase 7: A股指数历史K线（周线/月线聚合写入 periodic 表）────────────
def fetch_china_index_history(symbol: str, fill_periodic: bool = True) -> list[dict]:
    """
    拉取A股指数日K线历史（近1年），写入 market_data_daily 表
    AkShare stock_zh_index_daily 返回: ['date','open','high','low','close','volume']
    注意: AkShare DataFrame 列名直接用英文字符串访问
    """
    try:
        import akshare as ak, pandas as pd

        ak_symbol_map = {
            "000001": "sh000001",
            "000300": "sh000300",
            "399001": "sz399001",
            "399006": "sz399006",
            "000688": "sh000688",
        }
        ak_sym = ak_symbol_map.get(symbol)
        if not ak_sym:
            logger.warning(f"[AkShare] 无映射: {symbol}")
            return []

        df = ak.stock_zh_index_daily(symbol=ak_sym)
        if df is None or df.empty:
            return []

        # AkShare 列名就是英文: ['date','open','high','low','close','volume']
        # 直接访问，不需要 rename
        date_col = df.columns[0]  # 'date'
        # 动态匹配涨跌幅列名（akshare 版本差异：可能是 pct_chg / pct_change / 涨跌幅）
        _pct_col = next((c for c in df.columns if 'pct' in c.lower() or 'change' in c.lower() or c == '涨跌幅'), None)

        rows = []
        now_ts = int(time.time())
        for i in range(len(df)):
            try:
                dt     = int(pd.Timestamp(df.iloc[i][date_col]).timestamp())
                open_  = float(df.iloc[i]["open"])
                high   = float(df.iloc[i]["high"])
                low    = float(df.iloc[i]["low"])
                close  = float(df.iloc[i]["close"])   # ← 直接用 df["close"]，不经过任何 swap
                volume = float(df.iloc[i]["volume"]) if "volume" in df.columns else 0.0
                pct    = float(df.iloc[i][_pct_col]) if _pct_col and _pct_col in df.columns else 0.0
                rows.append({
                    "symbol":    symbol,
                    "date":      str(df.iloc[i][date_col])[:10],
                    "open":      open_,
                    "high":      high,
                    "low":       low,
                    "close":     close,
                    "volume":    volume,
                    "change_pct": pct,
                    "timestamp": dt,
                    "data_type": "daily",
                })
            except Exception as e:
                logger.warning(f"[AkShare] 解析第{i}行失败: {e}")
                continue

        if rows:
            from app.db import buffer_insert_daily, buffer_insert_periodic
            buffer_insert_daily(rows)
            logger.info(f"[AkShare] {symbol} 历史K线写入 {len(rows)} 条")

            # ── 周线聚合（从日线计算，不依赖外部 API）────────────────
            if fill_periodic:
                import pandas as pd
                df_d = pd.DataFrame(rows)
                df_d["date"] = pd.to_datetime(df_d["date"])

                # Weekly
                df_d["year_wk"] = df_d["date"].dt.isocalendar().year.astype(str) + "_" + df_d["date"].dt.isocalendar().week.astype(str).str.zfill(2)
                periodic_rows = []
                for yw, grp in df_d.groupby("year_wk", sort=True):
                    open_   = float(grp.iloc[0]["open"])
                    close_  = float(grp.iloc[-1]["close"])
                    high_   = float(grp["high"].max())
                    low_    = float(grp["low"].min())
                    pct     = (close_ - open_) / open_ * 100 if open_ else 0.0
                    dt_str  = str(grp.iloc[0]["date"])[:10]
                    periodic_rows.append({
                        "symbol": symbol, "date": dt_str,
                        "period": "weekly",
                        "open": open_, "high": high_, "low": low_,
                        "close": close_,
                        "volume": float(grp["volume"].sum()),
                        "change_pct": round(pct, 4),
                        "timestamp": int(pd.Timestamp(dt_str).timestamp()),
                    })

                # Monthly
                df_d["ym"] = df_d["date"].dt.to_period("M").astype(str)
                for ym, grp in df_d.groupby("ym", sort=True):
                    open_   = float(grp.iloc[0]["open"])
                    close_  = float(grp.iloc[-1]["close"])
                    high_   = float(grp["high"].max())
                    low_    = float(grp["low"].min())
                    pct     = (close_ - open_) / open_ * 100 if open_ else 0.0
                    dt_str  = str(grp.iloc[0]["date"])[:10]
                    periodic_rows.append({
                        "symbol": symbol, "date": dt_str,
                        "period": "monthly",
                        "open": open_, "high": high_, "low": low_,
                        "close": close_,
                        "volume": float(grp["volume"].sum()),
                        "change_pct": round(pct, 4),
                        "timestamp": int(pd.Timestamp(dt_str).timestamp()),
                    })

                if periodic_rows:
                    buffer_insert_periodic(periodic_rows)
                    logger.info(f"[AkShare] {symbol} 周线+月线写入 {len(periodic_rows)//2} 组")

        return rows[-100:]
    except Exception as e:
        logger.error(f"[AkShare] fetch_china_index_history({symbol}) 失败: {type(e).__name__}: {e}")
        traceback.print_exc()
        return []


# ── 分时数据：Eastmoney push2his 5分钟K线（直连，不走代理）─────────────
def fetch_index_minute_history(symbol: str, limit: int = 50) -> list[dict]:
    """
    获取 A 股指数 5 分钟 K 线（最近 N 根）
    格式: time, open, close, high, low, volume, amount
    Eastmoney secid: 0=深圳, 1=上海
    注意: 000001 是上证指数（上海），平安银行是 000001（深圳），两者不同！
    """
    # 精确映射表：彻底解决 000001 上证指数 vs 平安银行 的张冠李戴
    # 注意：A 股指数代码（如 000001）不需要大写，但 HSI/DJI 等需要
    #       所以 lookup 时转大写保证兼容
    _INDEX_SECID_MAP = {
        "000001": "1.000001",  # 上证指数（上海）
        "000300": "1.000300",  # 沪深300（上海）
        "399001": "0.399001",  # 深证成指（深圳）
        "399006": "0.399006",  # 创业板指（深圳）
        "000688": "1.000688",  # 科创50（上海）
    }
    secid = _INDEX_SECID_MAP.get(symbol.upper(), _INDEX_SECID_MAP.get(symbol, f"1.{symbol}"))

    import subprocess
    try:
        raw = subprocess.check_output(
            ["curl", "-s", "--noproxy", "*", "--max-time", "10",
             f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
             f"?secid={secid}"
             f"&fields1=f1,f2,f3,f4,f5,f6"
             f"&fields2=f51,f52,f53,f54,f55,f56,f57"
             f"&klt=5&fqt=1&beg=20200101&end=20991231",
             "-H", "Referer: https://quote.eastmoney.com/",
             "-H", "User-Agent: Mozilla/5.0"],
            stderr=subprocess.DEVNULL,
        )
        import json
        obj = json.loads(raw.decode("utf-8", errors="replace"))
        klines = obj.get("data", {}).get("klines", [])
        rows = []
        for kl in klines[-limit:]:  # 最新 N 根
            parts = kl.split(",")
            if len(parts) < 6:
                continue
            try:
                rows.append({
                    "time":       parts[0],                   # "2026-03-30 09:35"
                    "open":       float(parts[1]),
                    "close":      float(parts[2]),
                    "high":       float(parts[3]),
                    "low":        float(parts[4]),
                    "volume":     float(parts[5]),
                    "price":      float(parts[2]),            # close as current price
                    "change_pct": 0.0,
                    "timestamp":   int(
                        __import__("time").mktime(
                            __import__("time").strptime(parts[0], "%Y-%m-%d %H:%M")
                        )
                    ),
                })
            except (ValueError, IndexError, OSError):
                continue
        logger.info(f"[Eastmoney] {symbol} 5分钟K线: {len(rows)} 条")
        return rows
    except Exception as e:
        logger.warning(f"[Eastmoney] fetch_index_minute_history({symbol}) 失败: {type(e).__name__}: {e}")
        return []


def fetch_all_and_buffer():
    """聚合拉取 + 写入 write_buffer（供 APScheduler 调用）"""
    all_rows = []
    idx_rows      = fetch_china_indices()
    china_all_rows = fetch_china_all_indices()   # Phase 7: 国内10+指数
    shibor_rows   = fetch_shibor()
    global_rows   = fetch_global_indices()
    board_rows    = fetch_industry_sectors()
    deriv_rows    = fetch_derivatives()

    all_rows.extend(idx_rows)
    all_rows.extend(china_all_rows)
    all_rows.extend(shibor_rows)
    all_rows.extend(global_rows)
    all_rows.extend(board_rows)
    all_rows.extend(deriv_rows)

    if all_rows:
        from app.db import buffer_insert
        try:
            buffer_insert(all_rows)
            logger.info(f"[DataFetcher] 写入 {len(all_rows)} 条 "
                        f"(A股 {len(idx_rows)}, 国内 {len(china_all_rows)}, "
                        f"利率 {len(shibor_rows)}, 全球 {len(global_rows)}, "
                        f"板块 {len(board_rows)}, 商品 {len(deriv_rows)})")
        except Exception as e:
            logger.error(f"[DataFetcher] buffer_insert 失败: {type(e).__name__}: {e}")
            traceback.print_exc()
    else:
        logger.warning("[DataFetcher] 本次未拉到任何数据（所有接口均失败）")
