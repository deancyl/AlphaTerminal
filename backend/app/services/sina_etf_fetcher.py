"""
sina_etf_fetcher.py — 新浪财经 ETF 实时行情抓取器

免费数据源，无需 API Key
覆盖：ETF 实时价格、涨跌幅、成交量
"""
import asyncio
import re
from typing import Optional, Dict, List
from datetime import datetime
import logging

import httpx

logger = logging.getLogger(__name__)


class SinaETFFetcher:
    """新浪财经 ETF 实时行情抓取器"""
    
    def __init__(self):
        self.base_url = "https://hq.sinajs.cn"
        self.timeout = 5.0
    
    def _get_client(self) -> httpx.AsyncClient:
        """获取配置好的 HTTP 客户端"""
        return httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://finance.sina.com.cn/",
            },
        )
    
    def _format_code(self, code: str) -> str:
        """格式化 ETF 代码（添加市场前缀）"""
        # ETF 基金代码规则：
        # 上海：51xxxx, 56xxxx → sh
        # 深圳：15xxxx, 16xxxx → sz
        if code.startswith(('51', '56', '58', '60')):
            return f"sh{code}"
        elif code.startswith(('15', '16', '00', '30')):
            return f"sz{code}"
        return code
    
    async def get_etf_info(self, code: str) -> Optional[Dict]:
        """
        获取 ETF 实时行情
        
        数据源: https://hq.sinajs.cn/list=sh510300
        """
        try:
            formatted_code = self._format_code(code)
            url = f"{self.base_url}/list={formatted_code}"
            
            async with self._get_client() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                
                text = resp.text
                
                # 解析返回数据
                # 格式: var hq_str_sh510300="名称,昨收,今开,最新,最高,最低...";
                match = re.search(rf'var hq_str_{formatted_code}="([^"]*)"', text)
                if not match:
                    return None
                
                data_str = match.group(1)
                parts = data_str.split(',')
                
                if len(parts) < 33:
                    return None
                
                # 字段映射（根据新浪 API 文档）
                result = {
                    "code": code,
                    "name": parts[0],  # 名称
                    "source": "sina",
                    "price": float(parts[3]) if parts[3] else None,  # 最新价
                    "open": float(parts[1]) if parts[1] else None,  # 今开
                    "high": float(parts[4]) if parts[4] else None,  # 最高
                    "low": float(parts[5]) if parts[5] else None,  # 最低
                    "prev_close": float(parts[2]) if parts[2] else None,  # 昨收
                    "volume": int(parts[8]) if parts[8] else 0,  # 成交量（手）
                    "amount": float(parts[9]) if parts[9] else 0,  # 成交额
                    "date": parts[30] if len(parts) > 30 else None,  # 日期
                    "time": parts[31] if len(parts) > 31 else None,  # 时间
                    # 买卖盘五档
                    "bids": [],  # 买盘
                    "asks": [],  # 卖盘
                }
                
                # 解析买卖盘五档
                # 买盘：字段 10-19（买一到买五）
                for i in range(5):
                    volume_idx = 10 + i * 2
                    price_idx = 11 + i * 2
                    if len(parts) > price_idx:
                        try:
                            volume = int(parts[volume_idx]) if parts[volume_idx] else 0
                            price = float(parts[price_idx]) if parts[price_idx] else None
                            if price:
                                result["bids"].append({
                                    "level": i + 1,
                                    "price": price,
                                    "volume": volume,
                                })
                        except:
                            pass
                
                # 卖盘：字段 20-29（卖一到卖五）
                for i in range(5):
                    volume_idx = 20 + i * 2
                    price_idx = 21 + i * 2
                    if len(parts) > price_idx:
                        try:
                            volume = int(parts[volume_idx]) if parts[volume_idx] else 0
                            price = float(parts[price_idx]) if parts[price_idx] else None
                            if price:
                                result["asks"].append({
                                    "level": i + 1,
                                    "price": price,
                                    "volume": volume,
                                })
                        except:
                            pass
                
                # 计算涨跌幅
                if result["price"] and result["prev_close"]:
                    result["change"] = round(result["price"] - result["prev_close"], 3)
                    result["change_pct"] = round((result["price"] - result["prev_close"]) / result["prev_close"] * 100, 2)
                
                logger.info(f"[Sina] ETF {code} 行情获取成功: {result['price']}")
                return result
                
        except Exception as e:
            logger.warning(f"[Sina] ETF {code} 行情获取失败: {e}")
        
        return None
    
    async def get_etf_batch(self, codes: List[str]) -> Dict[str, Dict]:
        """
        批量获取 ETF 行情
        
        Args:
            codes: ETF 代码列表
        
        Returns:
            Dict[code, info]
        """
        try:
            formatted_codes = [self._format_code(c) for c in codes]
            url = f"{self.base_url}/list={','.join(formatted_codes)}"
            
            async with self._get_client() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                
                text = resp.text
                result = {}
                
                for code, formatted in zip(codes, formatted_codes):
                    match = re.search(rf'var hq_str_{formatted}="([^"]*)"', text)
                    if match:
                        data_str = match.group(1)
                        parts = data_str.split(',')
                        
                        if len(parts) >= 33:
                            info = {
                                "code": code,
                                "name": parts[0],
                                "source": "sina",
                                "price": float(parts[3]) if parts[3] else None,
                                "open": float(parts[1]) if parts[1] else None,
                                "high": float(parts[4]) if parts[4] else None,
                                "low": float(parts[5]) if parts[5] else None,
                                "prev_close": float(parts[2]) if parts[2] else None,
                                "volume": int(parts[8]) if parts[8] else 0,
                                "amount": float(parts[9]) if parts[9] else 0,
                                "date": parts[30] if len(parts) > 30 else None,
                                "time": parts[31] if len(parts) > 31 else None,
                            }
                            
                            if info["price"] and info["prev_close"]:
                                info["change"] = round(info["price"] - info["prev_close"], 3)
                                info["change_pct"] = round((info["price"] - info["prev_close"]) / info["prev_close"] * 100, 2)
                            
                            result[code] = info
                
                logger.info(f"[Sina] 批量获取 {len(result)} 只 ETF 行情")
                return result
                
        except Exception as e:
            logger.warning(f"[Sina] 批量获取 ETF 行情失败: {e}")
        
        return {}


# 单例模式
_sina_fetcher_instance = None

def get_sina_fetcher() -> SinaETFFetcher:
    global _sina_fetcher_instance
    if _sina_fetcher_instance is None:
        _sina_fetcher_instance = SinaETFFetcher()
    return _sina_fetcher_instance
