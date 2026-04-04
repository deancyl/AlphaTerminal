#!/usr/bin/env python3
"""
多源历史数据抓取脚本
支持：Alpha Vantage API (美股/港股/全球), AkShare (A股)
"""
import os
import sys
import requests
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 数据库路径
DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database.db')

# Alpha Vantage API 配置
AV_API_KEY = os.environ.get('ALPHA_VANTAGE_API_KEY')
AV_BASE_URL = 'https://www.alphavantage.co/query'

# 支持的指数和股票映射
SYMBOLS_MAP = {
    # A股指数
    '000001': 'sh000001',      # 上证指数
    '000300': 'sh000300',      # 沪深300
    '399001': 'sz399001',      # 深证成指
    '399006': 'sz399006',      # 创业板指
    '000016': 'sh000016',      # 上证50
    '000905': 'sh000905',      # 中证500
    # 美股指数
    '^IXIC': 'usixic',         # 纳斯达克综合指数
    '^NDX': 'usndx',           # 纳斯达克100
    '^GSPC': 'usspx',          # 标普500
    '^DJI': 'usdji',           # 道琼斯
    # 港股指数
    '^HSI': 'hkhsi',           # 恒生指数
    '^HSCEI': 'hkhscei',       # 恒生中国企业指数
    # 宏观商品
    'GC=F': 'gold',            # 黄金期货
    'CL=F': 'wti',             # WTI原油期货
    'SI=F': 'silver',          # 白银期货
    # 外汇
    'DXY': 'dxy',              # 美元指数
    'USDCNH=X': 'cnh',         # 在岸人民币
    # 其他
    '^VIX': 'vix',             # VIX恐慌指数
}

# Alpha Vantage symbol 映射（API 需要的格式）
AV_SYMBOLS = {
    'usixic': 'IXIC',
    'usndx': 'NDX',
    'usspx': 'SPX',
    'usdji': 'DJI',
    'hkhsi': '^HSI',
    'hkhscei': '^HSCEI',
    'gold': 'GLD',             # 使用 GLD ETF 代替黄金期货
    'wti': 'USO',              # 使用 USO ETF 代替原油期货
    'silver': 'SLV',           # 使用 SLV ETF 代替白银期货
    'dxy': 'UUP',              # 使用 UUP ETF 代替美元指数
    'cnh': 'CYB',              # 使用 CYB ETF 代替人民币
    'vix': 'VIXY',             # 使用 VIXY ETF 代替 VIX
}

def fetch_from_alpha_vantage(symbol: str, years: int = 20) -> Optional[pd.DataFrame]:
    """
    从 Alpha Vantage 获取历史数据

    Args:
        symbol: 标准化后的符号（如 'usixic'）
        years: 获取多少年的历史数据

    Returns:
        DataFrame with columns: date, open, high, low, close, volume
    """
    if not AV_API_KEY:
        print(f"[AV] 未配置 API Key，跳过 {symbol}")
        return None

    av_symbol = AV_SYMBOLS.get(symbol)
    if not av_symbol:
        print(f"[AV] 不支持的 symbol: {symbol}")
        return None

    try:
        print(f"[AV] 开始拉取 {symbol} ({av_symbol}) {years}年数据...")

        # Alpha Vantage Daily Adjusted API
        params = {
            'function': 'TIME_SERIES_DAILY_ADJUSTED',
            'symbol': av_symbol,
            'outputsize': 'full',  # 完整历史数据（最多 20+ 年）
            'apikey': AV_API_KEY
        }

        response = requests.get(AV_BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        # 检查 API 限制或错误
        if 'Note' in data:
            print(f"[AV] {symbol} API 限制: {data['Note']}")
            return None
        if 'Error Message' in data:
            print(f"[AV] {symbol} 错误: {data['Error Message']}")
            return None
        if 'Time Series (Daily)' not in data:
            print(f"[AV] {symbol} 无数据返回: {list(data.keys())}")
            return None

        # 解析数据
        time_series = data['Time Series (Daily)']
        rows = []
        for date_str, values in time_series.items():
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d')
                # 只获取指定年数内的数据
                if date < datetime.now() - timedelta(days=years*365):
                    continue

                rows.append({
                    'symbol': symbol,
                    'date': date_str,
                    'open': float(values['1. open']),
                    'high': float(values['2. high']),
                    'low': float(values['3. low']),
                    'close': float(values['4. close']),
                    'volume': int(values['6. volume']),
                    'timestamp': int(date.timestamp()),
                    'data_type': 'daily'
                })
            except (ValueError, KeyError) as e:
                print(f"[AV] {symbol} 解析数据错误 ({date_str}): {e}")
                continue

        if not rows:
            print(f"[AV] {symbol} 没有有效数据")
            return None

        df = pd.DataFrame(rows)
        df = df.sort_values('date')
        print(f"[AV] {symbol} 拉取成功: {len(df)} 条记录 ({df['date'].min()} ~ {df['date'].max()})")
        return df

    except requests.exceptions.Timeout:
        print(f"[AV] {symbol} 请求超时")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[AV] {symbol} 请求失败: {e}")
        return None
    except Exception as e:
        print(f"[AV] {symbol} 未知错误: {e}")
        return None

def fetch_from_akshare(symbol: str, years: int = 5) -> Optional[pd.DataFrame]:
    """
    从 AkShare 获取 A 股数据

    Args:
        symbol: 标准化后的符号（如 'sh000001'）
        years: 获取多少年的历史数据

    Returns:
        DataFrame with columns: date, open, high, low, close, volume
    """
    try:
        import akshare as ak

        # 转换为 AkShare 格式
        if symbol.startswith('sh'):
            ak_symbol = symbol[2:]  # 去掉 'sh'
            is_index = True
        elif symbol.startswith('sz'):
            ak_symbol = symbol[2:]  # 去掉 'sz'
            is_index = True
        else:
            # 默认认为是 A 股代码
            ak_symbol = symbol
            is_index = False

        print(f"[AkShare] 开始拉取 {symbol} ({ak_symbol}) {years}年数据...")

        # 计算日期范围
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=years*365)).strftime('%Y%m%d')

        if is_index:
            # 指数数据（index_zh_a_hist 不接受 adjust 参数）
            df = ak.index_zh_a_hist(
                symbol=ak_symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date
            )
        else:
            # 个股数据
            df = ak.stock_zh_a_daily(
                symbol=ak_symbol,
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )

        if df is None or df.empty:
            print(f"[AkShare] {symbol} 无数据返回")
            return None

        # 标准化列名
        df = df.rename(columns={
            '日期': 'date',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume'
        })

        # 添加标准字段
        df['symbol'] = symbol
        df['timestamp'] = pd.to_datetime(df['date']).apply(lambda x: int(x.timestamp()))
        df['data_type'] = 'daily'

        # 选择需要的列
        df = df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'timestamp', 'data_type']]

        # 转换数据类型
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(int)

        print(f"[AkShare] {symbol} 拉取成功: {len(df)} 条记录 ({df['date'].min()} ~ {df['date'].max()})")
        return df

    except ImportError:
        print(f"[AkShare] 未安装 akshare 库")
        return None
    except Exception as e:
        print(f"[AkShare] {symbol} 拉取失败: {e}")
        return None

def store_to_database(df: pd.DataFrame, table: str = 'market_data_daily') -> bool:
    """
    将数据存储到数据库（使用 INSERT OR REPLACE）

    Args:
        df: 数据 DataFrame
        table: 表名

    Returns:
        是否成功
    """
    if df is None or df.empty:
        print(f"[DB] 数据为空，跳过存储")
        return False

    conn = sqlite3.connect(DB_FILE)
    try:
        # 使用 INSERT OR REPLACE 避免重复
        df.to_sql(table, conn, if_exists='append', index=False, method='multi')
        conn.commit()
        print(f"[DB] 成功写入 {len(df)} 条记录")
        return True
    except Exception as e:
        print(f"[DB] 写入失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def fetch_and_store_symbol(symbol: str, years: int = 5) -> bool:
    """
    抓取并存储单个标的的数据

    Args:
        symbol: 标准化后的符号
        years: 获取多少年的历史数据

    Returns:
        是否成功
    """
    print(f"\n{'='*60}")
    print(f"开始处理: {symbol}")
    print(f"{'='*60}")

    # 判断使用哪个数据源
    if symbol.startswith('sh') or symbol.startswith('sz'):
        # A股使用 AkShare
        df = fetch_from_akshare(symbol, years)
    elif symbol.startswith('us') or symbol.startswith('hk') or symbol in ['gold', 'wti', 'silver', 'dxy', 'cnh', 'vix']:
        # 美股/港股/宏观使用 Alpha Vantage
        df = fetch_from_alpha_vantage(symbol, years)
    else:
        print(f"[ERROR] 不支持的 symbol: {symbol}")
        return False

    if df is None or df.empty:
        print(f"[FAIL] {symbol} 无数据")
        return False

    # 存储到数据库
    success = store_to_database(df)
    if success:
        print(f"[SUCCESS] {symbol} 完成: {len(df)} 条记录")
        return True
    else:
        print(f"[FAIL] {symbol} 存储失败")
        return False

def main():
    """主函数"""
    # 默认抓取 5 年历史数据
    years = 5

    # 获取要抓取的标的列表
    # 优先从环境变量读取，否则使用默认列表
    symbols_str = os.environ.get('FETCH_SYMBOLS', '')

    if symbols_str:
        symbols = symbols_str.split(',')
    else:
        # 默认列表
        symbols = [
            # A股指数
            'sh000001',  # 上证指数
            'sh000300',  # 沪深300
            'sz399001',  # 深证成指
            'sz399006',  # 创业板指
            # 美股指数
            'usixic',    # 纳斯达克
            'usndx',     # 纳斯达克100
            'usspx',     # 标普500
            'usdji',     # 道琼斯
            # 港股指数
            'hkhsi',     # 恒生
            # 宏观商品
            'gold',      # 黄金
            'wti',       # WTI原油
            'silver',    # 白银
            'dxy',       # 美元指数
            'cnh',       # 人民币
        ]

    print(f"开始抓取 {len(symbols)} 个标的的历史数据（{years}年）...")
    print(f"数据源: Alpha Vantage + AkShare")
    print(f"API Key: {'已配置' if AV_API_KEY else '未配置（仅 AkShare 可用）'}")

    success_count = 0
    fail_count = 0

    for symbol in symbols:
        try:
            if fetch_and_store_symbol(symbol, years):
                success_count += 1
            else:
                fail_count += 1
        except KeyboardInterrupt:
            print(f"\n用户中断")
            break
        except Exception as e:
            print(f"[ERROR] {symbol} 处理异常: {e}")
            fail_count += 1
            continue

    print(f"\n{'='*60}")
    print(f"抓取完成: 成功 {success_count}, 失败 {fail_count}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
