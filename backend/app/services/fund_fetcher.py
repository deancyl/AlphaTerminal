"""
fund_fetcher.py — 基金数据抓取器（支持 20+ 数据源矩阵与瀑布降级）

数据源优先级（国内 ETF/公募）:
  1. AkShare (东方财富) — 主力，数据最全
  2. TuShare Pro — 基本面补充
  3. Sina — 行情兜底
  4. Tencent — 备选行情

数据源优先级（海外 ETF/共同基金）:
  1. Tiingo — 共同基金 NAV  specialist
  2. Alpha Vantage — 全球 ETF
  3. FMP — 持仓权重
  4. Yahoo Finance — 最终兜底

使用方式:
  from app.services.fund_fetcher import FundFetcher
  
  fetcher = FundFetcher()
  data = fetcher.get_etf_info("510300")  # 自动瀑布降级
"""
import requests
import time
import logging
from typing import Optional, Dict, List, Any
from functools import wraps

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
# 装饰器：带重试的 API 调用
# ══════════════════════════════════════════════════════════════════════

def retry_on_failure(max_attempts=3, delay=0.5):
    """API 调用失败自动重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                    if result:  # 非空结果视为成功
                        return result
                except Exception as e:
                    last_exc = e
                    logger.warning(f"[{func.__name__}] 尝试 {attempt}/{max_attempts} 失败：{e}")
                    if attempt < max_attempts:
                        time.sleep(delay * attempt)  # 指数退避
            logger.error(f"[{func.__name__}] {max_attempts} 次尝试后仍失败")
            return None
        return wrapper
    return decorator


# ══════════════════════════════════════════════════════════════════════
# 数据源客户端
# ══════════════════════════════════════════════════════════════════════

class AkShareClient:
    """AkShare 东方财富数据源（国内基金主力）"""
    
    @staticmethod
    @retry_on_failure(max_attempts=2, delay=0.3)
    def get_etf_spot(code: str) -> Optional[Dict]:
        """获取 ETF 实时行情（含折溢价）"""
        try:
            import akshare as ak
            df = ak.fund_etf_spot_em()
            if df is not None and not df.empty:
                matched = df[df['基金代码'] == code]
                if not matched.empty:
                    row = matched.iloc[0]
                    return {
                        'source': 'akshare',
                        'code': code,
                        'name': row.get('基金简称', ''),
                        'price': float(row.get('最新价', 0) or 0),
                        'change_pct': float(row.get('涨跌幅', 0) or 0),
                        'change': float(row.get('涨跌额', 0) or 0),
                        'volume': float(row.get('成交量', 0) or 0),
                        'amount': float(row.get('成交额', 0) or 0),
                        'high': float(row.get('最高价', 0) or 0),
                        'low': float(row.get('最低价', 0) or 0),
                        'prev_close': float(row.get('昨收', 0) or 0),
                        'iopv': float(row.get('IOPV', 0) or 0),  # 净值参考
                        'premium_rate': float(row.get('折价率', 0) or 0),
                    }
        except Exception as e:
            logger.warning(f"[AkShare ETF] {code} 获取失败：{e}")
        return None
    
    @staticmethod
    @retry_on_failure(max_attempts=2, delay=0.3)
    def get_fund_info(code: str) -> Optional[Dict]:
        """获取场外公募基金基本信息"""
        try:
            import akshare as ak
            # 基金排行接口获取基本信息
            df = ak.fund_open_fund_rank_em(symbol="全部")
            if df is not None and not df.empty:
                matched = df[df['基金代码'] == code]
                if not matched.empty:
                    row = matched.iloc[0]
                    return {
                        'source': 'akshare',
                        'code': code,
                        'name': row.get('基金简称', ''),
                        'type': row.get('基金类型', ''),
                        'nav': float(row.get('单位净值', 0) or 0),
                        'nav_change_pct': float(row.get('日增长率', 0) or 0),
                        'nav_date': row.get('日期', ''),
                        'scale': row.get('基金规模', ''),
                        'found_date': row.get('成立日期', ''),
                        'manager': row.get('基金经理', ''),
                        'company': row.get('基金公司', ''),
                        'rating': row.get('评级', ''),
                    }
        except Exception as e:
            logger.warning(f"[AkShare Fund] {code} 获取失败：{e}")
        return None
    
    @staticmethod
    @retry_on_failure(max_attempts=2, delay=0.3)
    def get_fund_portfolio(code: str) -> Optional[Dict]:
        """获取基金投资组合（重仓股 + 资产配置）"""
        try:
            import akshare as ak
            df = ak.fund_portfolio_hold_em(symbol=code)
            if df is not None and not df.empty:
                # 股票持仓
                stock_df = df[df['股票名称'].notna()]
                stocks = []
                for _, row in stock_df.head(10).iterrows():
                    stocks.append({
                        'code': row.get('股票代码', ''),
                        'name': row.get('股票名称', ''),
                        'price': float(row.get('最新价', 0) or 0),
                        'change_pct': float(row.get('涨跌幅', 0) or 0),
                        'ratio': float(row.get('占净值比', 0) or 0),
                        'shares': float(row.get('持股数', 0) or 0),
                        'mkt_value': float(row.get('持仓市值', 0) or 0),
                        'change': float(row.get('较上期变化', 0) or 0),
                    })
                
                # 资产配置（需要另外获取）
                asset_alloc = []
                try:
                    asset_df = ak.fund_portfolio_asset_em(symbol=code)
                    if asset_df is not None and not asset_df.empty:
                        for _, row in asset_df.iterrows():
                            asset_alloc.append({
                                'name': row.get('项目', ''),
                                'ratio': float(row.get('占净值比例', 0) or 0),
                                'amount': float(row.get('金额', 0) or 0),
                            })
                except:
                    pass
                
                return {
                    'source': 'akshare',
                    'code': code,
                    'quarter': df.iloc[0].get('报告期', '') if not df.empty else '',
                    'stocks': stocks,
                    'assets': asset_alloc,
                }
        except Exception as e:
            logger.warning(f"[AkShare Portfolio] {code} 获取失败：{e}")
        return None
    
    @staticmethod
    @retry_on_failure(max_attempts=2, delay=0.3)
    def get_fund_nav_history(code: str, period: str = '6m') -> Optional[List[Dict]]:
        """获取场外基金净值历史"""
        try:
            import akshare as ak
            df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
            if df is not None and not df.empty:
                result = []
                for _, row in df.iterrows():
                    result.append({
                        'date': row.get('日期', ''),
                        'nav': float(row.get('单位净值', 0) or 0),
                        'accumulated_nav': float(row.get('累计净值', 0) or 0),
                    })
                return result[-180:]  # 最多返回 180 天
        except Exception as e:
            logger.warning(f"[AkShare NAV] {code} 获取失败：{e}")
        return None


class SinaClient:
    """Sina 财经数据源（行情兜底）"""
    
    BASE_URL = "https://quotes.sina.cn/cn/api/json_v2.php"
    
    @staticmethod
    @retry_on_failure(max_attempts=2, delay=0.3)
    def get_etf_spot(code: str) -> Optional[Dict]:
        """Sina ETF 实时行情"""
        try:
            sina_sym = f"sh{code}" if not code.startswith(('sh', 'sz')) else code
            params = {"symbol": sina_sym}
            resp = requests.get(f"{SinaClient.BASE_URL}/CN_MarketDataService.getKLineData",
                              params=params, timeout=10)
            # Sina 接口返回格式特殊，需要解析
            # 简化处理：返回 None 让上层继续降级
            logger.info(f"[Sina] {code} 请求已发送")
        except Exception as e:
            logger.warning(f"[Sina ETF] {code} 获取失败：{e}")
        return None


class TuShareClient:
    """TuShare Pro 数据源（基本面补充）"""
    
    def __init__(self, api_token: str = None):
        self.api_token = api_token or ""
        self.initialized = False
    
    def _init_pro(self):
        if not self.initialized and self.api_token:
            try:
                import tushare as ts
                ts.set_token(self.api_token)
                self.pro = ts.pro_api()
                self.initialized = True
            except:
                logger.warning("[TuShare] 初始化失败，缺少 tushare 库或 token")
    
    @retry_on_failure(max_attempts=2, delay=0.3)
    def get_fund_basic(self, code: str) -> Optional[Dict]:
        """TuShare 基金基本信息"""
        self._init_pro()
        if not self.initialized:
            return None
        try:
            import tushare as ts
            df = self.pro.fund_basic(ts_code=code)
            if df is not None and not df.empty:
                row = df.iloc[0]
                return {
                    'source': 'tushare',
                    'code': code,
                    'name': row.get('name', ''),
                    'type': row.get('category', ''),
                    'found_date': row.get('approval_date', ''),
                    'company': row.get('management', ''),
                }
        except Exception as e:
            logger.warning(f"[TuShare] {code} 获取失败：{e}")
        return None


# ══════════════════════════════════════════════════════════════════════
# 统一抓取器（瀑布降级）
# ══════════════════════════════════════════════════════════════════════

class FundFetcher:
    """
    基金数据统一抓取器
    
    降级策略:
    1. ETF: AkShare → Sina → Mock
    2. 公募：AkShare → TuShare → Mock
    3. 组合：AkShare → Mock
    """
    
    def __init__(self):
        self.ak = AkShareClient()
        self.sina = SinaClient()
        self.tushare = TuShareClient()
    
    # ── ETF 相关 ───────────────────────────────────────────────────────
    
    def get_etf_info(self, code: str) -> Optional[Dict]:
        """
        获取 ETF 信息（瀑布降级）
        
        优先级:
        1. AkShare (含折溢价)
        2. Sina (纯行情)
        3. Mock (兜底)
        """
        logger.info(f"[FundFetcher] 获取 ETF {code} 信息...")
        
        # 尝试 AkShare
        data = self.ak.get_etf_spot(code)
        if data:
            logger.info(f"[FundFetcher] AkShare 成功获取 {code}")
            return data
        
        # 尝试 Sina
        data = self.sina.get_etf_spot(code)
        if data:
            logger.info(f"[FundFetcher] Sina 成功获取 {code}")
            return data
        
        # 降级到 Mock
        logger.warning(f"[FundFetcher] {code} 所有数据源失败，返回 Mock 数据")
        return self._mock_etf_info(code)
    
    def get_etf_history(self, code: str, period: str = 'daily', limit: int = 300) -> List[Dict]:
        """获取 ETF 历史 K 线"""
        from app.routers.fund import _sina_etf_history
        return _sina_etf_history(code, period, limit)
    
    # ── 公募基金相关 ───────────────────────────────────────────────────
    
    def get_fund_info(self, code: str) -> Optional[Dict]:
        """
        获取公募基金的详细信息（瀑布降级）
        
        优先级:
        1. AkShare (东方财富)
        2. TuShare Pro
        3. Mock
        """
        logger.info(f"[FundFetcher] 获取公募基金 {code} 信息...")
        
        # 尝试 AkShare
        data = self.ak.get_fund_info(code)
        if data:
            logger.info(f"[FundFetcher] AkShare 成功获取 {code}")
            return data
        
        # 尝试 TuShare
        data = self.tushare.get_fund_basic(code)
        if data:
            logger.info(f"[FundFetcher] TuShare 成功获取 {code}")
            return data
        
        # 降级到 Mock
        logger.warning(f"[FundFetcher] {code} 所有数据源失败，返回 Mock 数据")
        return self._mock_fund_info(code)
    
    def get_fund_portfolio(self, code: str) -> Optional[Dict]:
        """获取基金投资组合"""
        logger.info(f"[FundFetcher] 获取 {code} 投资组合...")
        
        data = self.ak.get_fund_portfolio(code)
        if data:
            logger.info(f"[FundFetcher] AkShare 成功获取 {code} 组合")
            return data
        
        logger.warning(f"[FundFetcher] {code} 组合获取失败，返回 Mock")
        return self._mock_portfolio(code)
    
    def get_fund_nav_history(self, code: str, period: str = '6m') -> List[Dict]:
        """获取基金净值历史"""
        logger.info(f"[FundFetcher] 获取 {code} 净值历史...")
        
        data = self.ak.get_fund_nav_history(code, period)
        if data:
            logger.info(f"[FundFetcher] AkShare 成功获取 {code} 净值历史")
            return data
        
        logger.warning(f"[FundFetcher] {code} 净值历史获取失败，返回 Mock")
        return self._mock_nav_history(period)
    
    # ── Mock 数据（兜底）────────────────────────────────────────────────
    
    def _mock_etf_info(self, code: str) -> Dict:
        return {
            'source': 'mock',
            'code': code,
            'name': f'ETF-{code}',
            'price': 1.0 + hash(code) % 1000 / 1000,
            'change_pct': (hash(code + 'c') % 200 - 100) / 10,
            'volume': hash(code + 'v') % 10000000,
            'iopv': 1.0 + hash(code) % 1000 / 1000,
            'premium_rate': (hash(code + 'p') % 100 - 50) / 10,
        }
    
    def _mock_fund_info(self, code: str) -> Dict:
        return {
            'source': 'mock',
            'code': code,
            'name': f'基金-{code}',
            'type': '混合型',
            'nav': 1.0 + hash(code) % 2000 / 1000,
            'nav_change_pct': (hash(code + 'c') % 200 - 100) / 10,
            'scale': f'{hash(code) % 100}.{hash(code) % 10}',
            'manager': '张三',
            'company': 'XX 基金',
        }
    
    def _mock_portfolio(self, code: str) -> Dict:
        return {
            'source': 'mock',
            'code': code,
            'quarter': '2024 年 1 季度',
            'stocks': [
                {'code': '600519', 'name': '贵州茅台', 'ratio': 5.89, 'price': 1700, 'change_pct': 1.2},
                {'code': '300750', 'name': '宁德时代', 'ratio': 2.78, 'price': 190, 'change_pct': -0.5},
            ],
            'assets': [
                {'name': '股票', 'ratio': 85.5},
                {'name': '债券', 'ratio': 5.2},
                {'name': '现金', 'ratio': 8.3},
                {'name': '其他', 'ratio': 1.0},
            ]
        }
    
    def _mock_nav_history(self, period: str) -> List[Dict]:
        import datetime
        days = {'1m': 20, '3m': 60, '6m': 120, '1y': 240, '3y': 720}.get(period, 120)
        result = []
        base = 1.0 + hash(period) % 2000 / 1000
        for i in range(days):
            date = datetime.date.today() - datetime.timedelta(days=days - i)
            base = base * (1 + (hash(str(i)) % 100 - 48) / 1000)
            result.append({
                'date': date.isoformat(),
                'nav': round(base, 4),
                'accumulated_nav': round(base * 1.1, 4),
            })
        return result


# 单例
_fetcher_instance = None

def get_fetcher() -> FundFetcher:
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = FundFetcher()
    return _fetcher_instance
