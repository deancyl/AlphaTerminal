#!/usr/bin/env python3
"""
生成标准化的美股模拟数据
"""
import sys
import os
import json
import sqlite3
from datetime import datetime, timedelta
import time

# 添加项目路径
sys.path.append('/vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal/backend')

def generate_normalized_data():
    """生成标准化的美股模拟数据"""
    
    # 模拟 Alpha Vantage 返回的数据
    mock_alpha_vantage_data = {
        "usixic": [
            {"date": "2026-03-30", "1. open": 22553.52, "2. high": 22678.87, "3. low": 22534.87, "4. close": 22664.27, "5. volume": 1114097},
            {"date": "2026-03-31", "1. open": 22949.36, "2. high": 22949.36, "3. low": 22398.64, "4. close": 22675.41, "5. volume": 1048819},
            {"date": "2026-04-01", "1. open": 22598.02, "2. high": 22732.4, "3. low": 22324.99, "4. close": 22670.3, "5. volume": 961383},
            {"date": "2026-04-02", "1. open": 22800.14, "2. high": 22930.06, "3. low": 22553.07, "4. close": 22691.72, "5. volume": 999675},
            {"date": "2026-04-03", "1. open": 21827.83, "2. high": 21917.94, "3. low": 21824.72, "4. close": 21879.18, "5. volume": 914192},
        ],
        "usndx": [
            {"date": "2026-03-30", "1. open": 15850.32, "2. high": 15920.15, "3. low": 15820.45, "4. close": 15885.67, "5. volume": 2589341},
            {"date": "2026-03-31", "1. open": 15910.23, "2. high": 15945.67, "3. low": 15850.89, "4. close": 15920.34, "5. volume": 2456789},
            {"date": "2026-04-01", "1. open": 15880.45, "2. high": 15930.12, "3. low": 15840.67, "4. close": 15905.89, "5. volume": 2345678},
            {"date": "2026-04-02", "1. open": 15920.78, "2. high": 15960.34, "3. low": 15890.12, "4. close": 15935.67, "5. volume": 2434567},
            {"date": "2026-04-03", "1. open": 15780.23, "2. high": 15820.45, "3. low": 15760.89, "4. close": 15800.12, "5. volume": 2234567},
        ],
        "usspx": [
            {"date": "2026-03-30", "1. open": 4250.67, "2. high": 4275.89, "3. low": 4245.12, "4. close": 4265.34, "5. volume": 3567890},
            {"date": "2026-03-31", "1. open": 4260.89, "2. high": 4285.67, "3. low": 4255.23, "4. close": 4275.89, "5. volume": 3456789},
            {"date": "2026-04-01", "1. open": 4270.12, "2. high": 4290.45, "3. low": 4265.67, "4. close": 4285.23, "5. volume": 3345678},
            {"date": "2026-04-02", "1. open": 4280.45, "2. high": 4300.89, "3. low": 4275.12, "4. close": 4295.67, "5. volume": 3234567},
            {"date": "2026-04-03", "1. open": 4200.67, "2. high": 4225.89, "3. low": 4195.12, "4. close": 4215.34, "5. volume": 3123456},
        ],
        "usdji": [
            {"date": "2026-03-30", "1. open": 34500.23, "2. high": 34600.45, "3. low": 34450.67, "4. close": 34550.89, "5. volume": 4567890},
            {"date": "2026-03-31", "1. open": 34550.67, "2. high": 34700.23, "3. low": 34500.89, "4. close": 34650.45, "5. volume": 4456789},
            {"date": "2026-04-01", "1. open": 34600.89, "2. high": 34750.67, "3. low": 34550.23, "4. close": 34700.12, "5. volume": 4345678},
            {"date": "2026-04-02", "1. open": 34700.45, "2. high": 34850.89, "3. low": 34650.67, "4. close": 34800.23, "5. volume": 4234567},
            {"date": "2026-04-03", "1. open": 34000.67, "2. high": 34100.23, "3. low": 33950.89, "4. close": 34050.45, "5. volume": 4123456},
        ]
    }
    
    # 指数标准化因子
    normalization_factors = {
        "000001": 1.0,      # 上证指数 (基准)
        "000300": 1.0,      # 沪深300 (基准)
        "399001": 1.0,      # 深证成指 (基准)
        "399006": 1.0,      # 创业板指 (基准)
        "ixic":   0.15,     # 纳斯达克 (22000 → 3300)
        "usixic": 0.15,     # 纳斯达克 (22000 → 3300)
        "ndx":    0.15,     # 纳斯达克100 (22000 → 3300)
        "usndx":  0.15,     # 纳斯达克100 (22000 → 3300)
        "spx":    0.2,      # 标普500 (4500 → 900)
        "usspx":  0.2,      # 标普500 (4500 → 900)
        "dji":    0.01,     # 道琼斯 (35000 → 350)
        "usdji":  0.01,     # 道琼斯 (35000 → 350)
    }
    
    symbol_name = {
        "ixic": "纳斯达克", "usixic": "纳斯达克",
        "ndx": "纳指100", "usndx": "纳指100",
        "spx": "标普500", "usspx": "标普500",
        "dji": "道指", "usdji": "道指",
    }
    
    # 连接数据库
    db_path = '/vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal/database.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=== 生成标准化的美股数据 ===")
    
    for symbol, data in mock_alpha_vantage_data.items():
        norm_factor = normalization_factors.get(symbol.lower(), 1.0)
        name = symbol_name.get(symbol.lower(), symbol.upper())
        
        print(f"\n{symbol} - {name} (标准化因子: {norm_factor})")
        
        for i, day in enumerate(data):
            open_ = float(day["1. open"])
            high = float(day["2. high"])
            low = float(day["3. low"])
            close = float(day["4. close"])
            vol = float(day["5. volume"])
            
            # 应用标准化因子
            norm_open = open_ * norm_factor
            norm_high = high * norm_factor
            norm_low = low * norm_factor
            norm_close = close * norm_factor
            norm_vol = vol / norm_factor if norm_factor > 1 else vol
            
            # 计算涨跌幅
            prev_close = close if i == 0 else float(data[i-1]["4. close"])
            pct = (close - prev_close) / prev_close * 100 if prev_close else 0.0
            
            # 插入数据库
            cursor.execute("""
                INSERT INTO market_data_daily 
                (symbol, date, open, high, low, close, volume, timestamp, data_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol.lower(),
                day["date"],
                round(norm_open, 4),
                round(norm_high, 4),
                round(norm_low, 4),
                round(norm_close, 4),
                int(norm_vol),
                int(time.mktime(datetime.strptime(day["date"], "%Y-%m-%d").timetuple())),
                "daily"
            ))
            
            print(f"  {i+1}. {day['date']}: O={norm_open:.2f} H={norm_high:.2f} L={norm_low:.2f} C={norm_close:.2f} V={norm_vol:.0f}")
    
    conn.commit()
    conn.close()
    print(f"\n=== 完成！已生成 {sum(len(data) for data in mock_alpha_vantage_data.values())} 条标准化美股数据 ===")

if __name__ == "__main__":
    generate_normalized_data()