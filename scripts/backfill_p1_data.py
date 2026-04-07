#!/usr/bin/env python3
"""
P1 数据底座升级脚本：新增 amount, turnover_rate, amplitude

用法:
  python scripts/backfill_p1_data.py

原理:
  1. ALTER TABLE 添加新列（幂等，已存在则跳过）
  2. 重新拉取核心 A 股个股日K（最近 250 个交易日），
     INSERT OR REPLACE 将 amount/turnover_rate/amplitude 回填覆盖

核心标的列表（沪深 300 重点 + 行业龙头）:
  沪市: 600519 601318 600036 600276 600030 600887 601166 600016 600009 601328
  科创: 688981 688599 688041 688012
  深市: 000858 002594 300750 000001 300015 002475 000333 300760
  创业: 300015 300760 300274 300059
"""
import sqlite3
import sys
import os
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# 数据库路径（与 backend/app/db/database.py 保持一致）
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "database.db"
)

# 核心标的（symbol 为纯数字代码，如 "600519"）
KEY_SYMBOLS = [
    # 沪市龙头
    "600519", "601318", "600036", "600276", "600030",
    "600887", "601166", "600016", "600009", "601328",
    "601012", "600028", "600050", "601398", "601288",
    "600031", "601888", "600104", "600690", "600585",
    # 科创板
    "688981", "688599", "688041", "688012", "688111",
    # 深市龙头
    "000858", "002594", "000001", "002475", "000333",
    "300274", "300059", "002415", "002352", "000651",
    # 创业板
    "300750", "300015", "300760", "300124", "300496",
]


def add_missing_columns():
    """ALTER TABLE 添加新列（幂等）"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("PRAGMA table_info(market_data_daily)")
    existing = {row[1] for row in c.fetchall()}

    for col_name, col_type in [
        ("amount",       "REAL DEFAULT 0.0"),
        ("turnover_rate","REAL DEFAULT 0.0"),
        ("amplitude",    "REAL DEFAULT 0.0"),
    ]:
        if col_name not in existing:
            logger.info(f"[DB] 添加列: {col_name}")
            c.execute(f"ALTER TABLE market_data_daily ADD COLUMN {col_name} {col_type}")
        else:
            logger.info(f"[DB] 列已存在跳过: {col_name}")

    conn.commit()
    conn.close()
    logger.info("[DB] 表结构升级完成")


def _akshare_stock_history(symbol: str, start_date: str, end_date: str):
    """
    调用 akshare stock_zh_a_daily，返回含 amount/turnover_rate/amplitude 的行列表
    与 data_fetcher.fetch_stock_history 逻辑一致
    """
    try:
        import akshare as ak, pandas as pd

        # 补前缀
        numeric = symbol.strip().zfill(6)
        prefix = "sh" if numeric.startswith(("6", "9")) else "sz"
        ak_sym = f"{prefix}{numeric}"

        df = ak.stock_zh_a_daily(symbol=ak_sym, start_date=start_date,
                                  end_date=end_date, adjust="qfq")
        if df is None or df.empty:
            return []

        date_col = df.columns[0]
        _pct_col = next(
            (c for c in df.columns
             if 'pct' in c.lower() or 'change' in c.lower()),
            None
        )
        rows = []
        prev_close = None
        for i in range(len(df)):
            try:
                dt     = int(pd.Timestamp(df.iloc[i][date_col]).timestamp())
                open_  = float(df.iloc[i]["open"])
                high   = float(df.iloc[i]["high"])
                low    = float(df.iloc[i]["low"])
                close  = float(df.iloc[i]["close"])
                vol    = float(df.iloc[i]["volume"]) if "volume" in df.columns else 0.0
                pct    = float(df.iloc[i][_pct_col]) if _pct_col and _pct_col in df.columns else 0.0
                amount = float(df.iloc[i]["amount"]) if "amount" in df.columns else 0.0
                raw_to = float(df.iloc[i]["turnover"]) if "turnover" in df.columns else None
                turnover_rate = round(raw_to * 100, 4) if raw_to is not None else 0.0
                if prev_close and prev_close != 0:
                    amplitude = round((high - low) / prev_close * 100, 4)
                else:
                    amplitude = 0.0
                prev_close = close
                rows.append({
                    "symbol":        symbol,
                    "date":          str(df.iloc[i][date_col])[:10],
                    "open":          open_,
                    "high":          high,
                    "low":           low,
                    "close":         close,
                    "volume":        vol,
                    "amount":        amount,
                    "turnover_rate": turnover_rate,
                    "amplitude":     amplitude,
                    "change_pct":    pct,
                    "timestamp":     dt,
                    "data_type":     "daily",
                })
            except Exception as e:
                logger.warning(f"[{symbol}] 第{i}行解析失败: {e}")
                continue
        return rows
    except Exception as e:
        logger.error(f"[{symbol}] AkShare 拉取失败: {e}")
        return []


def backfill():
    """重新拉取核心标的日K，INSERT OR REPLACE 回填"""
    from datetime import datetime, timedelta
    end_date   = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=400)).strftime("%Y%m%d")

    total_ok = total_fail = 0
    for symbol in KEY_SYMBOLS:
        logger.info(f"[{symbol}] 拉取 {start_date}~{end_date} ...")
        rows = _akshare_stock_history(symbol, start_date, end_date)
        if not rows:
            continue

        # 直接写入数据库（INSERT OR REPLACE）
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        ok = fail = 0
        for r in rows:
            try:
                c.execute(
                    "INSERT OR REPLACE INTO market_data_daily "
                    "(symbol, date, open, high, low, close, volume, "
                    "amount, turnover_rate, amplitude, timestamp, data_type) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r["symbol"], r["date"], r["open"], r["high"], r["low"],
                     r["close"], int(r["volume"]), r["amount"],
                     r["turnover_rate"], r["amplitude"],
                     r["timestamp"], r["data_type"])
                )
                ok += 1
            except Exception as e:
                fail += 1
        conn.commit()
        conn.close()
        logger.info(f"[{symbol}] 写入 {ok} 条" + (f"，失败 {fail}" if fail else ""))
        total_ok += ok
        total_fail += fail
        time.sleep(0.5)   # 避免请求过快触发限流

    logger.info(f"[完成] 共写入 {total_ok} 条，失败 {total_fail} 条")


def verify():
    """验证回填结果"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT symbol, date, close, volume, amount, turnover_rate, amplitude
        FROM market_data_daily
        WHERE amount > 0 OR turnover_rate > 0
        ORDER BY date DESC
        LIMIT 10
    """)
    rows = c.fetchall()
    conn.close()
    if rows:
        logger.info(f"[验证] 含 amount/turnover 的记录: {len(rows)} 条（最近10条）")
        for r in rows:
            logger.info(f"  {r[0]} {r[1]} close={r[2]} vol={r[3]} amt={r[4]:.0f} to={r[5]:.2f}% amp={r[6]:.2f}%")
    else:
        logger.warning("[验证] 暂无含 amount/turnover 的记录，请检查回填是否成功")


if __name__ == "__main__":
    logger.info(f"数据库: {DB_PATH}")
    add_missing_columns()
    backfill()
    verify()
