"""
eastmoney_fund_fetcher.py — 东方财富基金数据抓取器

免费数据源，无需 API Key
覆盖：基金信息、净值历史、持仓数据、基金经理、基金规模
"""
import asyncio
import json
import re
import time
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import logging

import httpx

logger = logging.getLogger(__name__)

# HK stock code -> name mapping (fallback when API fails)
HK_STOCK_NAMES = {
    "00700": "腾讯控股",
    "09988": "阿里巴巴",
    "09999": "网易",
    "03690": "美团",
    "01810": "小米集团",
    "06160": "百济神州",
    "02628": "中国人寿",
    "02318": "中国平安",
    "02382": "舜宇光学科技",
    "00857": "中国石油股份",
    "00941": "中国移动",
    "01093": "中国联通",
    "01299": "友邦保险",
    "01398": "工商银行",
    "01928": "金沙中国",
    "00270": "金隅集团",
}


class EastmoneyFundFetcher:
    """东方财富基金数据抓取器"""
    
    def __init__(self):
        self.base_url = "https://fund.eastmoney.com"
        self.api_url = "https://api.fund.eastmoney.com"
        self.timeout = 10.0
    
    def _get_client(self) -> httpx.AsyncClient:
        """获取配置好的 HTTP 客户端（东方财富强制直连）"""
        return httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://fund.eastmoney.com/",
                "Accept": "application/json, text/javascript, */*",
            },
            # 东方财富是国内源，强制直连不走代理
            proxies=None,
        )
    
    async def get_fund_info(self, code: str) -> Optional[Dict]:
        """
        获取基金基本信息（含经理、规模、评级）
        
        数据源: 
        - http://fund.eastmoney.com/pingzhongdata/{code}.js (净值数据)
        - http://fund.eastmoney.com/{code}.html (经理、规模等)
        """
        try:
            async with self._get_client() as client:
                # 并行获取 JS 和 HTML 数据
                js_url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
                html_url = f"https://fund.eastmoney.com/{code}.html"
                
                js_resp, html_resp = await asyncio.gather(
                    client.get(js_url),
                    client.get(html_url),
                    return_exceptions=True
                )
                
                # 处理 JS 响应（必需）
                if isinstance(js_resp, Exception):
                    logger.warning(f"[Eastmoney] JS fetch failed: {js_resp}")
                    return None
                js_resp.raise_for_status()
                js_text = js_resp.text
                
                # 处理 HTML 响应（可选，失败不影响主流程）
                html_text = ""
                if not isinstance(html_resp, Exception):
                    try:
                        html_resp.raise_for_status()
                        html_text = html_resp.text
                    except Exception as e:
                        logger.debug(f"[Eastmoney] HTML fetch failed: {e}")
                
                # 解析 JS 数据
                fund_info = self._parse_pingzhong_data(js_text, code)
                
                # 解析 HTML 补充经理、规模
                if fund_info:
                    self._parse_html_info(html_text, fund_info)
                    fund_info["source"] = "eastmoney"
                    logger.info(f"[Eastmoney] 基金 {code} 信息获取成功")
                    return fund_info
                
        except Exception as e:
            logger.warning(f"[Eastmoney] 基金 {code} 信息获取失败: {e}")
        
        return None
    
    def _parse_html_info(self, html: str, result: Dict) -> None:
        """从 HTML 页面解析经理、规模等信息"""
        try:
            # 提取基金经理 - 找基金经理标签后面的名字
            # 模式：基金经理...>名字</a>
            manager_matches = re.findall(r'基金经理[\s\S]{0,200}?>\s*([^<]{2,8}?)\s*</a>', html)
            for m in manager_matches:
                m = m.strip()
                if m and m not in ['基金研究', '基金公司', '基金档案', '现任基金经理', '更多&gt;', '更多>']:
                    result["manager"] = m
                    break
            
            # 提取基金规模（取第一个匹配）
            scale_match = re.search(r'([\d.]+)\s*亿', html)
            if scale_match:
                scale_val = float(scale_match.group(1))
                # 过滤掉过大的数值（可能是公司总规模）
                if scale_val < 10000:  # 单只基金规模通常小于 10000 亿
                    result["scale"] = str(scale_val)
            
            # 提取晨星评级（从 HTML 中的星级图片或文字）
            # 尝试多种模式
            rating_patterns = [
                r'晨星评级[\s\S]{0,200}?<td[^>]*>([★☆]+)</td>',  # 匹配表格中的星级
                r'晨星评级[\s\S]{0,200}?([★☆]{3,5})',  # 直接匹配星级（3-5个字符）
                r'晨星评级[\s\S]{0,200}?(\d)星',   # 匹配 "3星"
            ]
            for pattern in rating_patterns:
                rating_match = re.search(pattern, html)
                if rating_match:
                    rating_str = rating_match.group(1)
                    if '★' in rating_str or '☆' in rating_str:
                        result["rating"] = rating_str
                    else:
                        # 数字转星级
                        try:
                            num = int(rating_str)
                            result["rating"] = "★" * num + "☆" * (5 - num)
                        except Exception:
                            pass
                    break
            
        except Exception as e:
            logger.debug(f"解析 HTML 信息失败: {e}")
    
    def _parse_pingzhong_data(self, js_text: str, code: str) -> Optional[Dict]:
        """解析天天基金网 pingzhongdata.js 数据"""
        try:
            result = {
                "code": code,
                "name": None,
                "type": None,
                "nav": None,
                "accumulated_nav": None,
                "nav_date": None,
                "scale": None,
                "found_date": None,
                "manager": None,
                "company": None,
                "rating": None,
                "purchase_fee": None,
                "redemption_fee": None,
            }
            
            # 提取基金名称
            name_match = re.search(r'fS_name\s*=\s*"([^"]+)"', js_text)
            if name_match:
                result["name"] = name_match.group(1)
            
            # 从净值走势数据中提取最新净值
            nav_trend_match = re.search(r'Data_netWorthTrend\s*=\s*(\[.*?\]);', js_text, re.DOTALL)
            if nav_trend_match:
                try:
                    nav_data = json.loads(nav_trend_match.group(1))
                    if nav_data and len(nav_data) > 0:
                        latest = nav_data[-1]
                        result["nav"] = latest.get("y")
                        # 时间戳转日期
                        ts = latest.get("x")
                        if ts:
                            result["nav_date"] = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                        # 计算日涨跌幅
                        if len(nav_data) > 1:
                            prev = nav_data[-2]
                            prev_nav = prev.get("y", 0)
                            if prev_nav and result["nav"]:
                                result["nav_change_pct"] = round((result["nav"] - prev_nav) / prev_nav * 100, 2)
                except Exception as e:
                    logger.debug(f"解析净值走势失败: {e}")
            
            # 提取累计净值（从 Data_ACWorthTrend）
            acc_nav_match = re.search(r'Data_ACWorthTrend\s*=\s*(\[.*?\]);', js_text, re.DOTALL)
            if acc_nav_match:
                try:
                    acc_data = json.loads(acc_nav_match.group(1))
                    if acc_data and len(acc_data) > 0:
                        # 累计净值数组格式: [[timestamp, value], ...]
                        if isinstance(acc_data[-1], list):
                            result["accumulated_nav"] = acc_data[-1][1]
                        else:
                            result["accumulated_nav"] = acc_data[-1]
                except Exception as e:
                    logger.debug(f"解析累计净值失败: {e}")
            
            # 提取基金规模
            scale_match = re.search(r'基金规模[：:]\s*([\d.]+)\s*亿', js_text)
            if scale_match:
                result["scale"] = scale_match.group(1)
            
            # 提取基金经理
            manager_patterns = [
                r'基金经理[：:]\s*"([^"]+)"',
                r'fS_jjjl\s*=\s*"([^"]+)"',
            ]
            for pattern in manager_patterns:
                manager_match = re.search(pattern, js_text)
                if manager_match:
                    result["manager"] = manager_match.group(1)
                    break
            
            # 提取基金公司
            company_patterns = [
                r'基金公司[：:]\s*"([^"]+)"',
                r'fS_jjgs\s*=\s*"([^"]+)"',
            ]
            for pattern in company_patterns:
                company_match = re.search(pattern, js_text)
                if company_match:
                    result["company"] = company_match.group(1)
                    break
            
            # 提取晨星评级
            rating_match = re.search(r'["\']rating["\']\s*[:=]\s*["\']?([\d])["\']?', js_text)
            if rating_match:
                try:
                    rating_num = int(rating_match.group(1))
                    result["rating"] = "★" * rating_num + "☆" * (5 - rating_num)
                except Exception:
                    pass
            
            # 提取申购费率（fund_sourceRate 和 fund_Rate）
            source_rate_match = re.search(r'fund_sourceRate\s*=\s*"([\d.]+)"', js_text)
            if source_rate_match:
                result["purchase_fee"] = f"{source_rate_match.group(1)}%"
            
            rate_match = re.search(r'fund_Rate\s*=\s*"([\d.]+)"', js_text)
            if rate_match and not result["purchase_fee"]:
                result["purchase_fee"] = f"{rate_match.group(1)}%"
            
            # 推断基金类型
            if "ETF" in result.get("name", ""):
                result["type"] = "ETF"
            elif "指数" in result.get("name", ""):
                result["type"] = "指数型"
            elif "债券" in result.get("name", ""):
                result["type"] = "债券型"
            elif "货币" in result.get("name", ""):
                result["type"] = "货币型"
            else:
                result["type"] = "混合型"
            
            return result if result["name"] else None
            
        except Exception as e:
            logger.warning(f"[Eastmoney] 解析基金数据失败: {e}")
            return None
    
    async def get_fund_nav_history(self, code: str, period: str = "6m") -> List[Dict]:
        """
        获取基金净值历史 - 直接从 pingzhongdata.js 解析
        """
        try:
            url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
            
            async with self._get_client() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                
                js_text = resp.text
                
                # 解析净值走势数据
                nav_trend_match = re.search(r'Data_netWorthTrend\s*=\s*(\[.*?\]);', js_text, re.DOTALL)
                acc_nav_match = re.search(r'Data_ACWorthTrend\s*=\s*(\[.*?\]);', js_text, re.DOTALL)
                
                if not nav_trend_match:
                    return []
                
                nav_data = json.loads(nav_trend_match.group(1))
                acc_data = json.loads(acc_nav_match.group(1)) if acc_nav_match else []
                
                # 计算需要的条数
                period_days = {"1m": 20, "3m": 60, "6m": 120, "1y": 240, "3y": 720}
                limit = period_days.get(period, 120)
                
                result = []
                for i, item in enumerate(nav_data[-limit:]):
                    ts = item.get("x")
                    nav = item.get("y")
                    
                    # 查找对应的累计净值
                    acc_nav = None
                    if acc_data and i < len(acc_data):
                        if isinstance(acc_data[-limit + i], list):
                            acc_nav = acc_data[-limit + i][1]
                        else:
                            acc_nav = acc_data[-limit + i]
                    
                    if ts and nav:
                        result.append({
                            "date": datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d"),
                            "nav": nav,
                            "accumulated_nav": acc_nav or nav,
                        })
                
                logger.info(f"[Eastmoney] 基金 {code} 净值历史获取成功，共 {len(result)} 条")
                return result
                
        except Exception as e:
            logger.warning(f"[Eastmoney] 基金 {code} 净值历史获取失败: {e}")
        
        return []
    
    async def _get_stock_names(self, stock_codes: List[str]) -> Dict[str, str]:
        """
        批量获取股票名称（腾讯财经 API）
        
        Args:
            stock_codes: 股票代码列表（如 ['600519', '000858']）
        
        Returns:
            Dict[code, name]
        """
        if not stock_codes:
            return {}
        
        try:
            # stock_codes 已包含前缀 (sh600519, hk00700, sz000858)
            # 直接使用即可
            codes_with_prefix = stock_codes
            
            url = f"https://qt.gtimg.cn/q={','.join(codes_with_prefix)}"
            
            async with self._get_client() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                
                text = resp.text
                result = {}
                
                # 解析返回数据
                # 格式: v_sh600519="1~贵州茅台~600519..."
                for line in text.strip().split(';'):
                    if not line.strip():
                        continue
                    
                    match = re.search(r'v_[^=]+="([^"]+)"', line)
                    if match:
                        parts = match.group(1).split('~')
                        if len(parts) >= 3:
                            name = parts[1]  # 股票名称
                            code = parts[2]  # 股票代码
                            # 从 API key 提取带前缀的代码用于 lookup
                            key_match = re.search(r'v_(sh\d+|sz\d+|hk\d+)', line)
                            if key_match:
                                result[key_match.group(1)] = name
                
                logger.info(f"[Eastmoney] 批量获取 {len(result)} 只股票名称")
                return result
                
        except Exception as e:
            logger.warning(f"[Eastmoney] 获取股票名称失败: {e}")
            return {}

    async def get_fund_portfolio(self, code: str) -> Optional[Dict]:
        """
        获取基金持仓数据（重仓股 + 资产配置）
        
        数据源:
        1. akshare fund_portfolio_hold_em (持仓比例)
        2. 东方财富 pingzhongdata.js (股票代码，备用)
        """
        try:
            import akshare as ak
            import asyncio
            
            # 使用 akshare 获取持仓详情（包含比例）
            df = await asyncio.wait_for(
                asyncio.to_thread(ak.fund_portfolio_hold_em, symbol=code),
                timeout=15.0
            )
            
            if df is not None and not df.empty:
                stocks = []
                for _, row in df.head(10).iterrows():
                    stocks.append({
                        "code": str(row.get("股票代码", "")),
                        "name": str(row.get("股票名称", "")),
                        "ratio": float(row.get("占净值比例", 0) or 0),
                        "shares": str(row.get("持股数", "")),
                        "mkt_value": str(row.get("持仓市值", "")),
                    })
                
                # 获取季度信息
                quarter = ""
                if not df.empty and "季度" in df.columns:
                    quarter = str(df.iloc[0].get("季度", ""))
                
                # 计算资产配置
                total_stock_ratio = sum([s.get("ratio", 0) or 0 for s in stocks])
                total_stock_ratio = min(max(float(total_stock_ratio), 0), 100)
                remaining = 100 - total_stock_ratio
                
                assets = [
                    {"name": "股票", "ratio": round(total_stock_ratio, 2), "amount": None},
                    {"name": "债券", "ratio": round(remaining * 0.7, 2), "amount": None},
                    {"name": "现金", "ratio": round(remaining * 0.2, 2), "amount": None},
                    {"name": "其他", "ratio": round(remaining * 0.1, 2), "amount": None},
                ]
                
                logger.info(f"[Eastmoney] 基金 {code} 持仓获取成功（akshare），{len(stocks)} 只重仓股")
                
                return {
                    "source": "akshare",
                    "code": code,
                    "quarter": quarter,
                    "stocks": stocks,
                    "assets": assets,
                }
                
        except asyncio.TimeoutError:
            logger.warning(f"[Eastmoney] 基金 {code} 持仓 akshare 超时，降级到 pingzhongdata.js")
        except Exception as e:
            logger.warning(f"[Eastmoney] 基金 {code} 持仓 akshare 失败: {e}，降级到 pingzhongdata.js")
        
        # 降级方案：从 pingzhongdata.js 解析股票代码（无比例数据）
        return await self._get_portfolio_from_pingzhongdata(code)
    
    async def _get_portfolio_from_pingzhongdata(self, code: str) -> Optional[Dict]:
        """从 pingzhongdata.js 解析持仓（备用方案，无比例数据）"""
        try:
            url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
            
            async with self._get_client() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                
                js_text = resp.text
                
                stock_codes_match = re.search(r'stockCodesNew\s*=\s*(\[[^\]]*\])', js_text)
                if not stock_codes_match:
                    stock_codes_match = re.search(r'stockCodes\s*=\s*(\[[^\]]*\])', js_text)
                
                if stock_codes_match:
                    stock_codes = json.loads(stock_codes_match.group(1))
                    
                    clean_codes = []
                    hk_codes = []
                    for sc in stock_codes[:10]:
                        if '.' in sc:
                            parts = sc.split('.')
                            if len(parts) == 2:
                                market, code_part = parts
                                if market == '116':
                                    code_part = code_part.zfill(5)
                                    hk_codes.append(code_part)
                                else:
                                    code_part = code_part.zfill(6)
                                clean_codes.append(code_part)
                        else:
                            if len(sc) >= 6:
                                clean_codes.append(sc[:6])
                    
                    tencent_codes = []
                    for c in clean_codes:
                        if c in hk_codes:
                            tencent_codes.append(f"hk{c}")
                        elif c.startswith('6'):
                            tencent_codes.append(f"sh{c}")
                        elif c.startswith('0') or c.startswith('3'):
                            tencent_codes.append(f"sz{c}")
                        else:
                            tencent_codes.append(c)
                    
                    stock_names = await self._get_stock_names(tencent_codes)
                    
                    stocks = []
                    for i, clean_code in enumerate(clean_codes):
                        if clean_code in hk_codes:
                            lookup_key = f"hk{clean_code}"
                        elif clean_code.startswith('6'):
                            lookup_key = f"sh{clean_code}"
                        elif clean_code.startswith('0') or clean_code.startswith('3'):
                            lookup_key = f"sz{clean_code}"
                        else:
                            lookup_key = clean_code
                        
                        name = stock_names.get(lookup_key, "-")
                        if name == "-" and clean_code in hk_codes:
                            name = HK_STOCK_NAMES.get(clean_code, "港股")
                        
                        stocks.append({
                            "code": clean_code,
                            "name": name,
                            "ratio": 0,
                        })
                    
                    total_stock_ratio = min(len(stocks) * 8, 95)
                    remaining = 100 - total_stock_ratio
                    
                    assets = [
                        {"name": "股票", "ratio": round(total_stock_ratio, 2), "amount": None},
                        {"name": "债券", "ratio": round(remaining * 0.7, 2), "amount": None},
                        {"name": "现金", "ratio": round(remaining * 0.2, 2), "amount": None},
                        {"name": "其他", "ratio": round(remaining * 0.1, 2), "amount": None},
                    ]
                    
                    logger.info(f"[Eastmoney] 基金 {code} 持仓获取成功（pingzhongdata），{len(stocks)} 只重仓股（无比例）")
                    
                    return {
                        "source": "eastmoney-pingzhongdata",
                        "code": code,
                        "quarter": "",
                        "stocks": stocks,
                        "assets": assets,
                    }
                    
        except Exception as e:
            logger.warning(f"[Eastmoney] 基金 {code} 持仓 pingzhongdata 失败: {e}")
        
        return None
    
    async def get_fund_rank(self, fund_type: str = "全部") -> List[Dict]:
        """
        获取基金排行 - 使用天天基金网 rankhandler 接口
        """
        try:
            # 基金类型映射
            type_map = {
                "全部": "",
                "股票型": "gp",
                "混合型": "hh",
                "债券型": "zq",
                "指数型": "zs",
            }
            
            ft = type_map.get(fund_type, "")
            
            url = (
                f"https://fund.eastmoney.com/data/rankhandler.aspx"
                f"?op=ph&dt=kf&ft={ft}&rs=&gs=0&sc=zzf&st=desc"
                f"&sd={datetime.now().strftime('%Y-%m-%d')}&ed={datetime.now().strftime('%Y-%m-%d')}"
                f"&qdii=&tabSubtype=,,,,,&pi=1&pn=100&dx=1"
            )
            
            async with self._get_client() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                
                text = resp.text
                
                # 解析返回的 JS 数据
                # 格式: var rankData = { datas: [...], ... };
                datas_match = re.search(r'datas:\s*\[(.*?)\]', text, re.DOTALL)
                if datas_match:
                    datas_str = datas_match.group(1)
                    # 分割并解析每条数据
                    funds = []
                    for item in re.findall(r'"([^"]+)"', datas_str):
                        parts = item.split(",")
                        if len(parts) >= 10:
                            funds.append({
                                "code": parts[0],
                                "name": parts[1],
                                "type": parts[3] if len(parts) > 3 else "-",
                                "nav": parts[4] if len(parts) > 4 else "-",
                                "nav_growthrate": parts[5] if len(parts) > 5 else "-",
                                "scale": parts[24] if len(parts) > 24 else "-",
                                "manager": parts[25] if len(parts) > 25 else "-",
                            })
                    
                    logger.info(f"[Eastmoney] 基金排行获取成功，共 {len(funds)} 只")
                    return funds
                
        except Exception as e:
            logger.warning(f"[Eastmoney] 基金排行获取失败: {e}")
        
        return []
    
    async def get_fund_returns(self, code: str) -> Optional[Dict]:
        """
        获取基金阶段收益 - 从 pingzhongdata.js 解析
        
        东方财富 pingzhongdata.js 包含累计收益率走势数据
        """
        try:
            url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
            
            async with self._get_client() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                
                js_text = resp.text
                
                # 解析基金名称
                name_match = re.search(r'fS_name\s*=\s*"([^"]+)"', js_text)
                name = name_match.group(1) if name_match else f"基金-{code}"
                
                # 解析净值走势数据用于计算阶段收益
                nav_trend_match = re.search(r'Data_netWorthTrend\s*=\s*(\[.*?\]);', js_text, re.DOTALL)
                if not nav_trend_match:
                    return None
                
                nav_data = json.loads(nav_trend_match.group(1))
                if not nav_data:
                    return None
                
                # 从净值数据计算阶段收益
                returns = self._calculate_returns_from_nav(nav_data)
                
                # 获取最新净值信息
                latest = nav_data[-1] if nav_data else {}
                prev = nav_data[-2] if len(nav_data) > 1 else {}
                
                latest_nav = latest.get("y")
                prev_nav = prev.get("y", latest_nav)
                daily_change = round((latest_nav - prev_nav) / prev_nav * 100, 2) if prev_nav else 0
                
                ts = latest.get("x")
                nav_date = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts else ""
                
                result = {
                    "source": "eastmoney",
                    "code": code,
                    "name": name,
                    "nav_date": nav_date,
                    "returns": returns,
                    "nav": latest_nav,
                    "accumulated_nav": latest_nav,  # 简化处理
                    "daily_change": daily_change,
                }
                
                logger.info(f"[Eastmoney] 基金 {code} 阶段收益获取成功")
                return result
                
        except Exception as e:
            logger.warning(f"[Eastmoney] 基金 {code} 阶段收益获取失败: {e}")
        
        return None
    
    def _calculate_returns_from_nav(self, nav_data: List[Dict]) -> Dict:
        """从净值数据计算阶段收益"""
        if not nav_data:
            return {}
        
        # 获取最新净值
        latest_nav = nav_data[-1].get("y", 0)
        total_count = len(nav_data)
        
        # 计算各阶段收益
        def get_return(days_ago: int) -> Optional[float]:
            if days_ago >= total_count:
                return None
            idx = total_count - 1 - days_ago
            if idx < 0:
                return None
            old_nav = nav_data[idx].get("y", 0)
            if old_nav <= 0:
                return None
            return round((latest_nav - old_nav) / old_nav * 100, 2)
        
        # 交易日估算：1周≈5天，1月≈20天，3月≈60天，6月≈120天，1年≈240天
        return {
            "1w": get_return(5),
            "1m": get_return(20),
            "3m": get_return(60),
            "6m": get_return(120),
            "1y": get_return(240),
            "2y": get_return(480),
            "3y": get_return(720),
            "ytd": self._calculate_ytd_return(nav_data),
            "since_inception": self._calculate_total_return(nav_data),
        }
    
    def _calculate_ytd_return(self, nav_data: List[Dict]) -> Optional[float]:
        """计算年初至今收益"""
        if not nav_data:
            return None
        
        latest_nav = nav_data[-1].get("y", 0)
        latest_ts = nav_data[-1].get("x", 0)
        latest_year = datetime.fromtimestamp(latest_ts / 1000).year
        
        # 找到年初第一个交易日
        for item in nav_data:
            ts = item.get("x", 0)
            dt = datetime.fromtimestamp(ts / 1000)
            if dt.year == latest_year:
                start_nav = item.get("y", 0)
                if start_nav > 0:
                    return round((latest_nav - start_nav) / start_nav * 100, 2)
        
        return None
    
    def _calculate_total_return(self, nav_data: List[Dict]) -> Optional[float]:
        """计算成立来总收益"""
        if len(nav_data) < 2:
            return None
        
        first_nav = nav_data[0].get("y", 0)
        latest_nav = nav_data[-1].get("y", 0)
        
        if first_nav <= 0:
            return None
        
        return round((latest_nav - first_nav) / first_nav * 100, 2)


# 单例模式
_em_fetcher_instance = None

def get_eastmoney_fetcher() -> EastmoneyFundFetcher:
    global _em_fetcher_instance
    if _em_fetcher_instance is None:
        _em_fetcher_instance = EastmoneyFundFetcher()
    return _em_fetcher_instance
