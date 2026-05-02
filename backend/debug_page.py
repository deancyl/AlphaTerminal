"""
Playwright高级调试脚本 v2.0 - 智能模拟点击 + 全面测试覆盖
用于捕获页面截图、console日志、网络请求、执行智能模拟点击和交互测试
支持：智能元素定位、显式等待、重试机制、性能监控、HTML报告生成
"""
import asyncio
import json
import time
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from playwright.async_api import async_playwright, Page, Browser, BrowserContext


class SmartSelector:
    """智能元素选择器 - 支持多种策略级联尝试"""
    
    @staticmethod
    async def find_element(page: Page, selectors: List[str], timeout: int = 5000) -> Optional[object]:
        """尝试多个selector，返回第一个匹配的元素"""
        for selector in selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=timeout, state='visible')
                if element:
                    return element
            except:
                continue
        return None
    
    @staticmethod
    async def click_smart(page: Page, name: str, selectors: List[str], timeout: int = 5000) -> bool:
        """智能点击 - 尝试多个selector"""
        for selector in selectors:
            try:
                await page.wait_for_selector(selector, timeout=timeout, state='visible')
                await page.click(selector)
                return True
            except:
                continue
        return False
    
    @staticmethod
    async def fill_smart(page: Page, selectors: List[str], text: str, timeout: int = 5000) -> bool:
        """智能填写 - 尝试多个selector"""
        for selector in selectors:
            try:
                await page.wait_for_selector(selector, timeout=timeout, state='visible')
                await page.fill(selector, text)
                return True
            except:
                continue
        return False


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics = []
    
    async def measure_navigation(self, page: Page, url: str) -> Dict:
        """测量页面导航性能"""
        start = time.time()
        response = await page.goto(url, wait_until='networkidle', timeout=30000)
        load_time = time.time() - start
        
        # 获取浏览器性能指标
        perf_data = await page.evaluate("""
            () => {
                const timing = performance.timing;
                const navigation = performance.getEntriesByType('navigation')[0];
                return {
                    domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
                    loadComplete: timing.loadEventEnd - timing.navigationStart,
                    firstPaint: performance.getEntriesByType('paint').find(p => p.name === 'first-paint')?.startTime || 0,
                    firstContentfulPaint: performance.getEntriesByType('paint').find(p => p.name === 'first-contentful-paint')?.startTime || 0
                };
            }
        """)
        
        metric = {
            'type': 'navigation',
            'url': url,
            'total_time': round(load_time, 3),
            'dom_content_loaded': round(perf_data.get('domContentLoaded', 0) / 1000, 3),
            'load_complete': round(perf_data.get('loadComplete', 0) / 1000, 3),
            'first_paint': round(perf_data.get('firstPaint', 0) / 1000, 3),
            'fcp': round(perf_data.get('firstContentfulPaint', 0) / 1000, 3),
            'status': response.status if response else 0
        }
        self.metrics.append(metric)
        return metric
    
    async def measure_api(self, page: Page, url: str) -> Dict:
        """测量API响应时间"""
        start = time.time()
        try:
            response = await page.evaluate(f"""
                async () => {{
                    const start = performance.now();
                    const response = await fetch('{url}');
                    const end = performance.now();
                    return {{
                        status: response.status,
                        time: end - start
                    }};
                }}
            """)
            metric = {
                'type': 'api',
                'url': url,
                'response_time': round(response['time'] / 1000, 3),
                'status': response['status']
            }
        except Exception as e:
            metric = {
                'type': 'api',
                'url': url,
                'response_time': round(time.time() - start, 3),
                'status': 0,
                'error': str(e)[:100]
            }
        self.metrics.append(metric)
        return metric


class AlphaTerminalDebuggerV2:
    """AlphaTerminal前端调试器 v2.0"""
    
    def __init__(self):
        self.console_logs = []
        self.network_requests = []
        self.network_responses = []
        self.page_errors = []
        self.interactions = []
        self.screenshots = []
        self.performance = PerformanceMonitor()
        self.test_results = []
        
    async def setup(self, page: Page):
        """设置事件监听器"""
        # Console日志
        page.on('console', lambda msg: self.console_logs.append({
            'type': msg.type,
            'text': msg.text,
            'time': datetime.now().isoformat()
        }))
        
        # 网络请求
        page.on('request', lambda req: self.network_requests.append({
            'url': req.url,
            'method': req.method,
            'time': datetime.now().isoformat()
        }))
        
        # 网络响应
        page.on('response', lambda res: asyncio.create_task(self._handle_response(res)))
        
        # 页面错误
        page.on('pageerror', lambda err: self.page_errors.append({
            'error': str(err),
            'time': datetime.now().isoformat()
        }))
        
        # 对话框自动处理
        page.on('dialog', lambda dialog: asyncio.create_task(dialog.dismiss()))
    
    async def _handle_response(self, response):
        """处理网络响应"""
        try:
            self.network_responses.append({
                'url': response.url,
                'status': response.status,
                'time': datetime.now().isoformat()
            })
        except:
            pass
    
    async def take_screenshot(self, page: Page, name: str, full_page: bool = False) -> str:
        """截图"""
        path = f'/tmp/alphaterminal_{name}_{datetime.now().strftime("%H%M%S")}.png'
        await page.screenshot(path=path, full_page=full_page)
        self.screenshots.append({'name': name, 'path': path, 'time': datetime.now().isoformat()})
        return path
    
    async def smart_click(self, page: Page, name: str, selectors: List[str], 
                         wait_after: int = 1000, timeout: int = 5000) -> bool:
        """智能点击 - 支持多种selector策略"""
        print(f"  🖱️  点击: {name}")
        success = await SmartSelector.click_smart(page, name, selectors, timeout)
        
        if success:
            await page.wait_for_timeout(wait_after)
            self.interactions.append({
                'action': 'click',
                'target': name,
                'status': 'success',
                'time': datetime.now().isoformat()
            })
            print(f"     ✅ 成功")
            return True
        else:
            self.interactions.append({
                'action': 'click',
                'target': name,
                'status': 'failed',
                'time': datetime.now().isoformat()
            })
            print(f"     ❌ 失败")
            return False
    
    async def smart_fill(self, page: Page, name: str, selectors: List[str], 
                        text: str, timeout: int = 5000) -> bool:
        """智能填写"""
        print(f"  ⌨️  填写: {name} = '{text}'")
        success = await SmartSelector.fill_smart(page, selectors, text, timeout)
        
        if success:
            self.interactions.append({
                'action': 'fill',
                'target': name,
                'value': text,
                'status': 'success',
                'time': datetime.now().isoformat()
            })
            print(f"     ✅ 成功")
            return True
        else:
            self.interactions.append({
                'action': 'fill',
                'target': name,
                'status': 'failed',
                'time': datetime.now().isoformat()
            })
            print(f"     ❌ 失败")
            return False
    
    async def check_element_smart(self, page: Page, name: str, selectors: List[str], 
                                   timeout: int = 3000) -> Tuple[bool, Optional[str]]:
        """智能检查元素"""
        element = await SmartSelector.find_element(page, selectors, timeout)
        if element:
            try:
                text = await element.text_content()
                visible = await element.is_visible()
                print(f"  ✅ {name}: 可见={visible}, 文本='{text[:50] if text else '空'}'")
                return True, text
            except:
                print(f"  ✅ {name}: 存在但无法获取文本")
                return True, None
        else:
            print(f"  ⚠️  {name}: 未找到")
            return False, None
    
    async def run_test_case(self, page: Page, test_name: str, test_func):
        """运行单个测试用例"""
        print(f"\n📋 测试: {test_name}")
        start = time.time()
        try:
            await test_func(page)
            duration = time.time() - start
            self.test_results.append({
                'name': test_name,
                'status': 'passed',
                'duration': round(duration, 2),
                'time': datetime.now().isoformat()
            })
            print(f"   ✅ 通过 ({duration:.2f}s)")
        except Exception as e:
            duration = time.time() - start
            self.test_results.append({
                'name': test_name,
                'status': 'failed',
                'error': str(e)[:200],
                'duration': round(duration, 2),
                'time': datetime.now().isoformat()
            })
            print(f"   ❌ 失败: {str(e)[:100]}")
            await self.take_screenshot(page, f"error_{test_name}")
    
    # ============ 测试用例 ============
    
    async def test_homepage_load(self, page: Page):
        """测试首页加载"""
        metric = await self.performance.measure_navigation(page, 'http://localhost:60100')
        print(f"   📊 加载时间: {metric['total_time']}s, FCP: {metric['fcp']}s")
        await self.take_screenshot(page, "01_homepage", full_page=True)
        
        # 检查关键元素
        await self.check_element_smart(page, "页面头部", [
            'header', '.header', '[data-testid="header"]',
            '.app-header', '.top-bar'
        ])
        await self.check_element_smart(page, "侧边栏", [
            'nav', '.sidebar', '[data-testid="sidebar"]',
            '.side-nav', '.navigation'
        ])
    
    async def test_navigation_bond(self, page: Page):
        """测试债券导航"""
        await self.smart_click(page, "债券导航", [
            'text=债券', 'text=Bond',
            'a[href*="bond"]', '[data-testid="nav-bond"]',
            '.nav-item:has-text("债券")', 'button:has-text("债券")'
        ], wait_after=2000)
        await self.take_screenshot(page, "02_bond_page")
        
        # 检查债券相关内容
        exists, text = await self.check_element_smart(page, "债券面板", [
            '.bond-dashboard', '[data-testid="bond-dashboard"]',
            '.yield-curve', '.bond-list',
            'text=收益率', 'text=国债'
        ])
        
        # 检查Mock警告
        await self.check_element_smart(page, "Mock数据警告", [
            '.warning', '.mock-warning', '[data-testid="mock-warning"]',
            'text=模拟数据', 'text=mock'
        ])
    
    async def test_navigation_futures(self, page: Page):
        """测试期货导航"""
        await self.smart_click(page, "期货导航", [
            'text=期货', 'text=Futures',
            'a[href*="futures"]', '[data-testid="nav-futures"]',
            '.nav-item:has-text("期货")'
        ], wait_after=2000)
        await self.take_screenshot(page, "03_futures_page")
        
        await self.check_element_smart(page, "期货面板", [
            '.futures-dashboard', '[data-testid="futures-dashboard"]',
            '.commodities-list', 'text=大宗商品',
            'text=股指期货'
        ])
    
    async def test_navigation_macro(self, page: Page):
        """测试宏观数据导航"""
        await self.smart_click(page, "宏观导航", [
            'text=宏观', 'text=Macro',
            'a[href*="macro"]', '[data-testid="nav-macro"]',
            '.nav-item:has-text("宏观")'
        ], wait_after=2000)
        await self.take_screenshot(page, "04_macro_page")
        
        await self.check_element_smart(page, "宏观面板", [
            '.macro-dashboard', '[data-testid="macro-dashboard"]',
            'text=GDP', 'text=CPI', 'text=PMI',
            '.economic-indicators'
        ])
    
    async def test_search_function(self, page: Page):
        """测试搜索功能"""
        # 尝试多种搜索框selector
        search_selectors = [
            'input[type="search"]', 'input[placeholder*="搜索"]',
            '[data-testid="search-input"]', '.search-input input',
            '.search-box input', 'input[placeholder*="stock"]'
        ]
        
        if await self.smart_fill(page, "搜索框", search_selectors, "600519"):
            await page.wait_for_timeout(1500)
            await self.take_screenshot(page, "05_search_result")
            
            # 检查搜索结果
            await self.check_element_smart(page, "搜索结果", [
                '.search-results', '.stock-info',
                '[data-testid="search-result"]', 'text=贵州茅台'
            ])
    
    async def test_portfolio_features(self, page: Page):
        """测试组合功能"""
        await self.smart_click(page, "组合导航", [
            'text=组合', 'text=Portfolio',
            'a[href*="portfolio"]', '[data-testid="nav-portfolio"]',
            '.nav-item:has-text("组合")'
        ], wait_after=2000)
        await self.take_screenshot(page, "06_portfolio_page")
        
        await self.check_element_smart(page, "组合面板", [
            '.portfolio-dashboard', '[data-testid="portfolio-dashboard"]',
            'text=资产', 'text=盈亏', 'text=持仓'
        ])
    
    async def test_backtest_features(self, page: Page):
        """测试回测功能"""
        await self.smart_click(page, "回测导航", [
            'text=回测', 'text=Backtest',
            'a[href*="backtest"]', '[data-testid="nav-backtest"]',
            '.nav-item:has-text("回测")'
        ], wait_after=2000)
        await self.take_screenshot(page, "07_backtest_page")
        
        await self.check_element_smart(page, "回测面板", [
            '.backtest-dashboard', '[data-testid="backtest-dashboard"]',
            'text=策略', 'text=回测结果', 'text=收益率'
        ])
    
    async def test_copilot_features(self, page: Page):
        """测试Copilot功能"""
        await self.smart_click(page, "Copilot导航", [
            'text=Copilot', 'text=AI', 'text=助手',
            'a[href*="copilot"]', '[data-testid="nav-copilot"]'
        ], wait_after=2000)
        await self.take_screenshot(page, "08_copilot_page")
    
    async def test_chart_interactions(self, page: Page):
        """测试图表交互"""
        # 尝试找到图表元素并hover
        chart_selectors = [
            '.echarts', '.chart-container', 'canvas',
            '[data-testid="chart"]', '.kline-chart'
        ]
        
        element = await SmartSelector.find_element(page, chart_selectors, timeout=3000)
        if element:
            print(f"  📊 图表交互: hover图表")
            try:
                await element.hover()
                await page.wait_for_timeout(500)
                await self.take_screenshot(page, "09_chart_hover")
                
                # 尝试点击图表
                await element.click()
                await page.wait_for_timeout(500)
                await self.take_screenshot(page, "10_chart_click")
            except Exception as e:
                print(f"     ⚠️ 图表交互失败: {str(e)[:80]}")
    
    async def test_responsive_mobile(self, page: Page):
        """测试移动端响应式"""
        print(f"\n📱 测试移动端响应式 (375x667)")
        await page.set_viewport_size({'width': 375, 'height': 667})
        await page.reload(wait_until='networkidle')
        await page.wait_for_timeout(2000)
        await self.take_screenshot(page, "11_mobile_view", full_page=True)
        
        # 检查移动端菜单
        await self.check_element_smart(page, "移动端菜单按钮", [
            '.mobile-menu', '.hamburger', '[data-testid="mobile-menu"]',
            'button:has-text("☰")', '.menu-toggle'
        ])
        
        # 恢复桌面视图
        await page.set_viewport_size({'width': 1920, 'height': 1080})
    
    async def test_api_performance(self, page: Page):
        """测试API性能"""
        print(f"\n🌐 测试API性能")
        apis = [
            'http://localhost:8002/api/v1/macro/overview',
            'http://localhost:8002/api/v1/bond/active',
            'http://localhost:8002/api/v1/futures/main_indexes',
            'http://localhost:8002/health'
        ]
        
        for api in apis:
            metric = await self.performance.measure_api(page, api)
            status_icon = "✅" if metric['status'] == 200 else "❌"
            print(f"   {status_icon} {api.split('/')[-1]}: {metric['response_time']}s (HTTP {metric['status']})")
    
    # ============ 报告生成 ============
    
    def generate_json_report(self) -> Dict:
        """生成JSON报告"""
        return {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': len(self.test_results),
                'passed': len([t for t in self.test_results if t['status'] == 'passed']),
                'failed': len([t for t in self.test_results if t['status'] == 'failed']),
                'console_logs': len(self.console_logs),
                'console_errors': len([l for l in self.console_logs if l['type'] == 'error']),
                'console_warnings': len([l for l in self.console_logs if l['type'] == 'warning']),
                'network_requests': len(self.network_requests),
                'failed_requests': len([r for r in self.network_responses if r.get('status', 0) >= 400]),
                'interactions': len(self.interactions),
                'successful_interactions': len([i for i in self.interactions if i['status'] == 'success']),
                'screenshots': len(self.screenshots),
                'page_errors': len(self.page_errors)
            },
            'test_results': self.test_results,
            'performance_metrics': self.performance.metrics,
            'interactions': self.interactions,
            'page_errors': self.page_errors,
            'screenshots': self.screenshots
        }
    
    def generate_html_report(self) -> str:
        """生成HTML报告"""
        summary = self.generate_json_report()['summary']
        
        # 测试结果表格
        test_rows = ""
        for test in self.test_results:
            status_color = "#28a745" if test['status'] == 'passed' else "#dc3545"
            error_cell = f"<td style='color:#dc3545;font-size:12px;'>{test.get('error', '')[:80]}</td>" if test['status'] == 'failed' else "<td>-</td>"
            test_rows += f"""
                <tr>
                    <td>{test['name']}</td>
                    <td style="color:{status_color};font-weight:bold;">{test['status'].upper()}</td>
                    <td>{test['duration']}s</td>
                    {error_cell}
                </tr>
            """
        
        # 性能指标表格
        perf_rows = ""
        for metric in self.performance.metrics:
            if metric['type'] == 'navigation':
                perf_rows += f"""
                    <tr>
                        <td>页面加载</td>
                        <td>{metric['url']}</td>
                        <td>{metric['total_time']}s</td>
                        <td>{metric.get('fcp', 'N/A')}s</td>
                        <td>HTTP {metric['status']}</td>
                    </tr>
                """
            elif metric['type'] == 'api':
                status_color = "#28a745" if metric['status'] == 200 else "#dc3545"
                perf_rows += f"""
                    <tr>
                        <td>API</td>
                        <td>{metric['url']}</td>
                        <td style="color:{status_color}">{metric['response_time']}s</td>
                        <td>-</td>
                        <td>HTTP {metric['status']}</td>
                    </tr>
                """
        
        # 截图展示
        screenshot_divs = ""
        for ss in self.screenshots[:12]:  # 最多显示12张
            screenshot_divs += f"""
                <div style="margin:10px;display:inline-block;vertical-align:top;">
                    <div style="font-size:12px;color:#666;margin-bottom:5px;">{ss['name']}</div>
                    <img src="{ss['path']}" style="max-width:300px;max-height:200px;border:1px solid #ddd;border-radius:4px;" 
                         onerror="this.style.display='none'"/>
                </div>
            """
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>AlphaTerminal Debug Report</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
                h1 {{ color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }}
                h2 {{ color: #555; margin-top: 30px; }}
                .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
                .card {{ background: #f8f9fa; padding: 15px; border-radius: 6px; border-left: 4px solid #007bff; }}
                .card.success {{ border-left-color: #28a745; }}
                .card.warning {{ border-left-color: #ffc107; }}
                .card.error {{ border-left-color: #dc3545; }}
                .card h3 {{ margin: 0 0 10px 0; font-size: 14px; color: #666; }}
                .card .value {{ font-size: 28px; font-weight: bold; color: #333; }}
                table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #dee2e6; }}
                th {{ background: #f8f9fa; font-weight: 600; color: #555; }}
                .screenshots {{ display: flex; flex-wrap: wrap; justify-content: center; }}
                .timestamp {{ color: #999; font-size: 14px; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🧪 AlphaTerminal Debug Report</h1>
                <div class="timestamp">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
                
                <h2>📊 测试摘要</h2>
                <div class="summary">
                    <div class="card {'success' if summary['passed'] == summary['total_tests'] else 'error'}">
                        <h3>测试通过率</h3>
                        <div class="value">{summary['passed']}/{summary['total_tests']}</div>
                    </div>
                    <div class="card {'success' if summary['console_errors'] == 0 else 'warning'}">
                        <h3>Console错误</h3>
                        <div class="value">{summary['console_errors']}</div>
                    </div>
                    <div class="card {'success' if summary['failed_requests'] == 0 else 'error'}">
                        <h3>失败请求</h3>
                        <div class="value">{summary['failed_requests']}</div>
                    </div>
                    <div class="card">
                        <h3>页面错误</h3>
                        <div class="value">{summary['page_errors']}</div>
                    </div>
                    <div class="card">
                        <h3>交互操作</h3>
                        <div class="value">{summary['successful_interactions']}/{summary['interactions']}</div>
                    </div>
                    <div class="card">
                        <h3>截图数量</h3>
                        <div class="value">{summary['screenshots']}</div>
                    </div>
                </div>
                
                <h2>📝 详细测试结果</h2>
                <table>
                    <tr>
                        <th>测试名称</th>
                        <th>状态</th>
                        <th>耗时</th>
                        <th>错误信息</th>
                    </tr>
                    {test_rows}
                </table>
                
                <h2>⚡ 性能指标</h2>
                <table>
                    <tr>
                        <th>类型</th>
                        <th>URL</th>
                        <th>响应时间</th>
                        <th>FCP</th>
                        <th>HTTP状态</th>
                    </tr>
                    {perf_rows}
                </table>
                
                <h2>📸 截图记录</h2>
                <div class="screenshots">
                    {screenshot_divs}
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def save_reports(self):
        """保存所有报告"""
        # JSON报告
        json_report = self.generate_json_report()
        with open('/tmp/alphaterminal_debug.json', 'w') as f:
            json.dump(json_report, f, indent=2, ensure_ascii=False, default=str)
        
        # HTML报告
        html_report = self.generate_html_report()
        with open('/tmp/alphaterminal_debug.html', 'w') as f:
            f.write(html_report)
        
        return json_report


async def check_service_available(url: str = 'http://localhost:60100', timeout: int = 5) -> bool:
    """检查服务是否可用"""
    import urllib.request
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except:
        return False


async def main():
    """主函数"""
    print("=" * 70)
    print("🚀 AlphaTerminal Playwright 智能调试脚本 v2.0")
    print("=" * 70)
    
    # 检查服务
    print("\n🔍 检查服务状态...")
    if not await check_service_available():
        print("❌ 前端服务未启动 (http://localhost:60100)")
        print("   请先启动前端服务:")
        print("   cd frontend && npm run build && npx vite preview --host 0.0.0.0 --port 60100")
        return
    
    if not await check_service_available('http://localhost:8002/health'):
        print("⚠️  后端服务可能未启动 (http://localhost:8002)")
    else:
        print("✅ 前端服务运行正常")
        print("✅ 后端服务运行正常")
    
    # 初始化调试器
    debugger = AlphaTerminalDebuggerV2()
    
    async with async_playwright() as p:
        # 启动浏览器
        headless = '--headed' not in sys.argv
        browser = await p.chromium.launch(headless=headless)
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            record_video_dir='/tmp/playwright_videos/' if not headless else None
        )
        
        page = await context.new_page()
        await debugger.setup(page)
        
        try:
            # 定义测试用例
            test_cases = [
                ("首页加载测试", debugger.test_homepage_load),
                ("债券页面测试", debugger.test_navigation_bond),
                ("期货页面测试", debugger.test_navigation_futures),
                ("宏观数据测试", debugger.test_navigation_macro),
                ("搜索功能测试", debugger.test_search_function),
                ("组合功能测试", debugger.test_portfolio_features),
                ("回测功能测试", debugger.test_backtest_features),
                ("Copilot功能测试", debugger.test_copilot_features),
                ("图表交互测试", debugger.test_chart_interactions),
                ("移动端响应式测试", debugger.test_responsive_mobile),
                ("API性能测试", debugger.test_api_performance),
            ]
            
            # 执行测试
            print(f"\n📋 计划执行 {len(test_cases)} 个测试用例\n")
            for test_name, test_func in test_cases:
                await debugger.run_test_case(page, test_name, test_func)
            
            # 生成报告
            print("\n" + "=" * 70)
            print("📝 生成报告...")
            report = debugger.save_reports()
            
            # 输出摘要
            summary = report['summary']
            print("\n📊 测试摘要:")
            print(f"   ✅ 通过: {summary['passed']}/{summary['total_tests']}")
            print(f"   ❌ 失败: {summary['failed']}/{summary['total_tests']}")
            print(f"   ⚠️  Console错误: {summary['console_errors']}")
            print(f"   ⚠️  Console警告: {summary['console_warnings']}")
            print(f"   🌐 失败请求: {summary['failed_requests']}")
            print(f"   🖱️  成功交互: {summary['successful_interactions']}/{summary['interactions']}")
            print(f"   📸 截图: {summary['screenshots']} 张")
            
            print(f"\n📁 报告文件:")
            print(f"   JSON: /tmp/alphaterminal_debug.json")
            print(f"   HTML: /tmp/alphaterminal_debug.html")
            print(f"   截图: /tmp/alphaterminal_*.png")
            
            # 如果测试失败，输出详细信息
            if summary['failed'] > 0:
                print(f"\n❌ 失败测试详情:")
                for test in debugger.test_results:
                    if test['status'] == 'failed':
                        print(f"   - {test['name']}: {test.get('error', 'Unknown error')}")
            
        except Exception as e:
            print(f"\n💥 严重错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()
            print("\n" + "=" * 70)
            print("🏁 调试完成!")
            print("=" * 70)


# 快捷功能
async def quick_check():
    """快速检查"""
    print("🔍 快速检查服务状态...")
    frontend_ok = await check_service_available('http://localhost:60100')
    backend_ok = await check_service_available('http://localhost:8002/health')
    
    print(f"   前端 (60100): {'✅ 运行中' if frontend_ok else '❌ 未启动'}")
    print(f"   后端 (8002):  {'✅ 运行中' if backend_ok else '❌ 未启动'}")
    
    if frontend_ok:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto('http://localhost:60100', wait_until='networkidle', timeout=10000)
            await page.screenshot(path='/tmp/alphaterminal_quick.png', full_page=True)
            await browser.close()
            print("   📸 截图已保存: /tmp/alphaterminal_quick.png")


async def screenshot_only():
    """仅截图"""
    if not await check_service_available():
        print("❌ 服务未启动")
        return
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1920, 'height': 1080})
        await page.goto('http://localhost:60100', wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(2000)
        await page.screenshot(path='/tmp/alphaterminal_screenshot.png', full_page=True)
        print("📸 截图已保存: /tmp/alphaterminal_screenshot.png")
        await browser.close()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == 'quick':
            asyncio.run(quick_check())
        elif mode == 'screenshot':
            asyncio.run(screenshot_only())
        else:
            print("用法:")
            print("  python debug_page.py          # 完整调试")
            print("  python debug_page.py quick    # 快速检查")
            print("  python debug_page.py screenshot # 仅截图")
            print("  python debug_page.py --headed  # 可视化模式")
    else:
        asyncio.run(main())
