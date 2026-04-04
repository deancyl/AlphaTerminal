#!/usr/bin/env python3
"""
示例数据生成器
为美股/港股/宏观数据生成合理的历史数据（用于测试和演示）

注意：这是模拟数据，不是真实的市场数据！
仅用于测试和演示目的，不应用于实际投资决策。
"""
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 数据库路径
DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database.db')

# 示例数据配置
SAMPLE_DATA_CONFIG = {
    # 美股指数
    'usixic': {
        'name': '纳斯达克综合指数',
        'start_date': '2021-04-01',  # 5年历史
        'start_price': 13000.0,
        'end_price': 21879.18,       # 使用当前真实价格
        'volatility': 0.02,          # 日波动率
    },
    'usndx': {
        'name': '纳斯达克100',
        'start_date': '2021-04-01',
        'start_price': 12500.0,
        'end_price': 24045.53,
        'volatility': 0.018,
    },
    'usspx': {
        'name': '标普500',
        'start_date': '2021-04-01',
        'start_price': 4000.0,
        'end_price': 5200.0,         # 估算
        'volatility': 0.015,
    },
    'usdji': {
        'name': '道琼斯',
        'start_date': '2021-04-01',
        'start_price': 33000.0,
        'end_price': 39000.0,        # 估算
        'volatility': 0.012,
    },
    # 港股指数
    'hkhsi': {
        'name': '恒生指数',
        'start_date': '2021-04-01',
        'start_price': 28000.0,
        'end_price': 25116.53,
        'volatility': 0.018,
    },
    'hkhscei': {
        'name': '恒生中国企业指数',
        'start_date': '2021-04-01',
        'start_price': 10500.0,
        'end_price': 8800.0,
        'volatility': 0.02,
    },
    # 宏观商品
    'gold': {
        'name': '黄金',
        'start_date': '2021-04-01',
        'start_price': 1750.0,
        'end_price': 4675.99,        # 注意：这个价格看起来异常高，可能是单位问题
        'volatility': 0.01,
    },
    'wti': {
        'name': 'WTI原油',
        'start_date': '2021-04-01',
        'start_price': 60.0,
        'end_price': 112.23,
        'volatility': 0.025,
    },
    'silver': {
        'name': '白银',
        'start_date': '2021-04-01',
        'start_price': 25.0,
        'end_price': 28.0,
        'volatility': 0.02,
    },
    # 外汇
    'dxy': {
        'name': '美元指数',
        'start_date': '2021-04-01',
        'start_price': 92.0,
        'end_price': 104.0,
        'volatility': 0.008,
    },
    'cnh': {
        'name': '在岸人民币',
        'start_date': '2021-04-01',
        'start_price': 6.5,
        'end_price': 7.2,
        'volatility': 0.005,
    },
    # 其他
    'vix': {
        'name': 'VIX恐慌指数',
        'start_date': '2021-04-01',
        'start_price': 20.0,
        'end_price': 15.0,
        'volatility': 0.05,
    },
}

def generate_geometric_brownian_motion(start_price, end_price, n_days, volatility):
    """
    生成几何布朗运动模拟价格（更真实的股票价格模型）

    Args:
        start_price: 起始价格
        end_price: 结束价格
        n_days: 天数
        volatility: 波动率

    Returns:
        价格序列
    """
    # 计算漂移率（使价格从 start_price 变到 end_price）
    drift = np.log(end_price / start_price) / n_days

    # 生成随机游走
    dt = 1.0
    np.random.seed(42)  # 固定随机种子，保证可重复性
    random_shocks = np.random.normal(0, 1, n_days)

    # 几何布朗运动
    prices = [start_price]
    for i in range(1, n_days):
        prev_price = prices[-1]
        # dS = S * (mu * dt + sigma * dW)
        change = drift * dt + volatility * random_shocks[i] / np.sqrt(n_days)
        new_price = prev_price * np.exp(change)
        prices.append(max(new_price, 0.01))  # 确保价格不为负

    # 调整最后一个价格，使其接近目标价格
    if len(prices) > 1:
        prices[-1] = end_price

    return prices

def generate_sample_data(symbol, config):
    """
    为单个标的生成示例数据

    Args:
        symbol: 标的代码
        config: 配置字典

    Returns:
        DataFrame
    """
    start_date = datetime.strptime(config['start_date'], '%Y-%m-%d')
    end_date = datetime.now()
    n_days = (end_date - start_date).days

    print(f"生成 {config['name']} ({symbol}) 数据: {n_days} 天")

    # 生成价格序列
    prices = generate_geometric_brownian_motion(
        config['start_price'],
        config['end_price'],
        n_days,
        config['volatility']
    )

    # 生成 OHLCV 数据
    data = []
    for i, price in enumerate(prices):
        date = start_date + timedelta(days=i)

        # 生成当日 OHLC（基于收盘价）
        high = price * (1 + abs(np.random.normal(0, config['volatility'] * 0.5)))
        low = price * (1 - abs(np.random.normal(0, config['volatility'] * 0.5)))
        open_price = price * (1 + np.random.normal(0, config['volatility'] * 0.3))
        close = price
        volume = int(np.random.normal(1000000, 200000))

        # 确保 OHLC 逻辑正确
        high = max(high, open_price, close, low)
        low = min(low, open_price, close, high)

        data.append({
            'symbol': symbol,
            'date': date.strftime('%Y-%m-%d'),
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close, 2),
            'volume': max(volume, 0),
            'timestamp': int(date.timestamp()),
            'data_type': 'daily'
        })

    df = pd.DataFrame(data)
    print(f"  生成 {len(df)} 条记录")
    print(f"  价格范围: {df['close'].min():.2f} ~ {df['close'].max():.2f}")

    return df

def store_to_database(df, symbol):
    """存储数据到数据库"""
    if df.empty:
        return False

    conn = sqlite3.connect(DB_FILE)
    try:
        # 先删除该标的的旧数据（如果存在）
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM market_data_daily WHERE symbol = '{symbol}'")

        # 写入新数据
        df.to_sql('market_data_daily', conn, if_exists='append', index=False, method='multi')
        conn.commit()

        print(f"  已写入 {len(df)} 条记录到数据库")
        return True
    except Exception as e:
        print(f"  写入数据库失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def main():
    """主函数"""
    print("="*60)
    print("示例数据生成器")
    print("="*60)
    print("⚠️  警告：这是模拟数据，不是真实的市场数据！")
    print("⚠️  仅用于测试和演示目的，不应用于实际投资决策。")
    print("="*60)
    print()

    # 检查数据库
    if not os.path.exists(DB_FILE):
        print(f"错误：数据库文件不存在: {DB_FILE}")
        print("请先运行 scripts/init_database.py 初始化数据库")
        sys.exit(1)

    # 生成所有标的的示例数据
    success_count = 0
    fail_count = 0

    for symbol, config in SAMPLE_DATA_CONFIG.items():
        try:
            print(f"\n处理 {symbol}...")
            df = generate_sample_data(symbol, config)

            if store_to_database(df, symbol):
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            print(f"  处理失败: {e}")
            fail_count += 1
            continue

    print("\n" + "="*60)
    print(f"生成完成: 成功 {success_count}, 失败 {fail_count}")
    print("="*60)

if __name__ == "__main__":
    main()
