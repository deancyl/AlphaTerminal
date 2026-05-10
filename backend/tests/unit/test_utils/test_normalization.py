#!/usr/bin/env python3
"""
测试数据标准化逻辑
"""
import sys
import os
import time
from datetime import datetime, timedelta

# 添加项目路径
sys.path.append('/vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal/backend')

def test_normalization():
    """测试数据标准化逻辑"""
    
    # 模拟 Alpha Vantage 返回的数据
    mock_alpha_vantage_data = {
        "usixic": [
            {"date": "2026-03-30", "1. open": 22553.52, "2. high": 22678.87, "3. low": 22534.87, "4. close": 22664.27, "5. volume": 1114097},
            {"date": "2026-03-31", "1. open": 22949.36, "2. high": 22949.36, "3. low": 22398.64, "4. close": 22675.41, "5. volume": 1048819},
            {"date": "2026-04-01", "1. open": 22598.02, "2. high": 22732.4, "3. low": 22324.99, "4. close": 22670.3, "5. volume": 961383},
            {"date": "2026-04-02", "1. open": 22800.14, "2. high": 22930.06, "3. low": 22553.07, "4. close": 22691.72, "5. volume": 999675},
            {"date": "2026-04-03", "1. open": 21827.83, "2. high": 21917.94, "3. low": 21824.72, "4. close": 21879.18, "5. volume": 914192},
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
    
    print("=== 数据标准化测试 ===")
    
    for symbol, data in mock_alpha_vantage_data.items():
        norm_factor = normalization_factors.get(symbol.lower(), 1.0)
        name = symbol_name.get(symbol.lower(), symbol.upper())
        
        print(f"\n{symbol} - {name} (标准化因子: {norm_factor})")
        print("原始数据 vs 标准化数据:")
        
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
            
            print(f"  {i+1}. {day['date']}")
            print(f"     原始: O={open_:.2f} H={high:.2f} L={low:.2f} C={close:.2f} V={vol:.0f}")
            print(f"     标准化: O={norm_open:.2f} H={norm_high:.2f} L={norm_low:.2f} C={norm_close:.2f} V={norm_vol:.0f}")
    
    print("\n=== 上证指数对比 ===")
    # 获取上证指数数据
    try:
        import json
        import urllib.request
        import urllib.error

        response = urllib.request.urlopen("http://localhost:8002/api/v1/market/history/000001?period=daily&limit=5")
        data = json.loads(response.read().decode())
        sh_data = data.get('history', [])

        print("上证指数数据:")
        for i, day in enumerate(sh_data[:3]):
            print(f"  {i+1}. {day['date']}: O={day['open']:.2f} H={day['high']:.2f} L={day['low']:.2f} C={day['close']:.2f}")
    except urllib.error.URLError as e:
        print(f"获取上证指数数据失败 (URL错误): {e}")
    except urllib.error.HTTPError as e:
        print(f"获取上证指数数据失败 (HTTP错误): {e}")
    except json.JSONDecodeError as e:
        print(f"获取上证指数数据失败 (JSON解析错误): {e}")
    except KeyError as e:
        print(f"获取上证指数数据失败 (数据格式错误): {e}")
    except Exception as e:
        print(f"获取上证指数数据失败: {e}")

if __name__ == "__main__":
    test_normalization()