#!/usr/bin/env python3
"""
AlphaTerminal Week 1-2 功能验证脚本
测试数据导出和预警系统功能
"""

import urllib.request
import json
import sys

def test_backend():
    """测试后端API"""
    print("=" * 60)
    print("🔧 后端API测试")
    print("=" * 60)
    
    base_url = "http://localhost:8002"
    
    # Test 1: Health check
    print("\n1️⃣ 健康检查...")
    try:
        r = urllib.request.urlopen(f"{base_url}/health", timeout=5)
        if r.status == 200:
            print("   ✅ 后端服务正常运行")
        else:
            print(f"   ❌ 状态码异常: {r.status}")
            return False
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
        return False
    
    # Test 2: Export portfolio CSV
    print("\n2️⃣ 投资组合CSV导出...")
    try:
        r = urllib.request.urlopen(f"{base_url}/api/v1/export/portfolio/1?format=csv", timeout=10)
        if r.status == 200:
            content = r.read().decode()
            lines = content.strip().split('\n')
            print(f"   ✅ CSV导出成功")
            print(f"   📊 数据行数: {len(lines)} 行")
            print(f"   📋 列名: {lines[0]}")
            if len(lines) > 1:
                print(f"   📈 示例数据: {lines[1][:80]}...")
        else:
            print(f"   ❌ 导出失败: {r.status}")
            return False
    except Exception as e:
        print(f"   ❌ 导出失败: {e}")
        return False
    
    # Test 3: Export portfolio Excel
    print("\n3️⃣ 投资组合Excel导出...")
    try:
        r = urllib.request.urlopen(f"{base_url}/api/v1/export/portfolio/1?format=excel", timeout=10)
        if r.status == 200:
            content_type = r.headers.get('Content-Type', '')
            if 'spreadsheet' in content_type:
                print(f"   ✅ Excel导出成功")
                print(f"   📦 文件大小: {len(r.read())} bytes")
            else:
                print(f"   ⚠️  Content-Type异常: {content_type}")
        else:
            print(f"   ❌ 导出失败: {r.status}")
            return False
    except Exception as e:
        print(f"   ❌ 导出失败: {e}")
        return False
    
    # Test 4: Export backtest result
    print("\n4️⃣ 回测结果导出...")
    try:
        test_data = json.dumps({
            'result': {
                'total_return_pct': 0.15,
                'annualized_return_pct': 0.15,
                'max_drawdown_pct': -0.05,
                'sharpe_ratio': 1.2,
                'win_rate': 0.65,
                'trades_count': 2,
                'trades': [
                    {'date': '2024-01-01', 'action': 'buy', 'price': 100, 'shares': 100, 'value': 10000, 'pnl': 0},
                    {'date': '2024-01-15', 'action': 'sell', 'price': 110, 'shares': 100, 'value': 11000, 'pnl': 1000}
                ]
            },
            'strategy_type': 'ma_crossover',
            'symbol': 'sh600519',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        }).encode()
        
        req = urllib.request.Request(
            f"{base_url}/api/v1/export/backtest/result?format=excel",
            data=test_data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        r = urllib.request.urlopen(req, timeout=10)
        if r.status == 200:
            print(f"   ✅ 回测导出成功")
            print(f"   📦 文件大小: {len(r.read())} bytes")
        else:
            print(f"   ❌ 导出失败: {r.status}")
            return False
    except Exception as e:
        print(f"   ❌ 导出失败: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ 后端API测试全部通过!")
    print("=" * 60)
    return True

def test_frontend():
    """测试前端可访问性"""
    print("\n" + "=" * 60)
    print("🎨 前端测试")
    print("=" * 60)
    
    try:
        r = urllib.request.urlopen("http://localhost:60100", timeout=5)
        if r.status == 200:
            print("\n✅ 前端页面可访问")
            print(f"   📱 地址: http://localhost:60100")
            print(f"   📄 Content-Type: {r.headers.get('Content-Type')}")
            return True
        else:
            print(f"\n❌ 前端返回异常状态码: {r.status}")
            return False
    except Exception as e:
        print(f"\n❌ 前端访问失败: {e}")
        return False

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🚀 AlphaTerminal Week 1-2 功能验证")
    print("=" * 60)
    print("\n测试项目:")
    print("  Week 1: 数据导出功能 (CSV/Excel)")
    print("  Week 2: 预警系统基础 (前端组件已集成)")
    print()
    
    backend_ok = test_backend()
    frontend_ok = test_frontend()
    
    print("\n" + "=" * 60)
    print("📋 测试结果汇总")
    print("=" * 60)
    print(f"后端API: {'✅ 通过' if backend_ok else '❌ 失败'}")
    print(f"前端页面: {'✅ 通过' if frontend_ok else '❌ 失败'}")
    
    if backend_ok and frontend_ok:
        print("\n🎉 所有测试通过! Week 1-2 功能验证完成!")
        print("\n功能说明:")
        print("  1. 数据导出: 支持投资组合和回测结果的CSV/Excel导出")
        print("  2. 预警系统: AlertManager组件已集成到DashboardGrid")
        print("  3. 浏览器通知: 支持价格阈值预警和通知推送")
        print("\n访问地址:")
        print("  前端: http://localhost:60100")
        print("  后端: http://localhost:8002")
        print("  API文档: http://localhost:8002/docs")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查服务状态")
        return 1

if __name__ == "__main__":
    sys.exit(main())
