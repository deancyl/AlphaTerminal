"""
Bond data fetcher with multi-source fallback support.

Primary: akshare bond_china_yield (historical, stopped 2021-01-22)
Fallback 1: CFETS fx_spot_quote (RMB bond yields)
Fallback 2: Chinabond API (via httpx)
Last Resort: Static mock data
"""
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import httpx

logger = logging.getLogger(__name__)

# Constants
STALE_DATA_THRESHOLD_DAYS = 7
CFETS_BOND_API = "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr-today.json"
CHINABOND_API = "https://www.chinabond.com.cn/cbweb/market/yield-curves"


class BondDataFetcher:
    """
    Multi-source bond yield data fetcher with automatic fallback.
    
    Fallback chain:
    1. akshare bond_china_yield (primary)
    2. CFETS (China Foreign Exchange Trade System)
    3. Chinabond (China Central Depository & Clearing)
    4. Static mock data
    """
    
    def __init__(self, executor=None):
        self._executor = executor
        self._http_client = httpx.AsyncClient(timeout=15.0)
    
    async def close(self):
        """Close HTTP client."""
        await self._http_client.aclose()
    
    async def fetch_yield_curve(self) -> Dict[str, Any]:
        """
        Fetch bond yield curve with fallback sources.
        
        Returns:
            {
                "yield_curve": {tenor: rate},
                "comm_yield": {tenor: rate},
                "spreads_bps": {tenor: bps},
                "update_time": str,
                "source": str,
                "last_update": str,
                "is_stale": bool
            }
        """
        # Try primary source (akshare)
        data = await self._fetch_from_akshare()
        if data and self._is_data_fresh(data):
            return data
        
        # Try fallback 1: CFETS
        data = await self._fetch_from_cfets()
        if data and self._is_data_fresh(data):
            return data
        
        # Try fallback 2: Chinabond
        data = await self._fetch_from_chinabond()
        if data and self._is_data_fresh(data):
            return data
        
        # Last resort: return mock data with stale flag
        logger.warning("[BondFetcher] All sources failed, using mock fallback")
        return self._get_mock_data(is_stale=True)
    
    async def _fetch_from_akshare(self) -> Optional[Dict[str, Any]]:
        """Fetch from akshare bond_china_yield."""
        try:
            import akshare as ak
            import warnings
            warnings.filterwarnings("ignore")
            
            if self._executor:
                loop = asyncio.get_running_loop()
                df = await asyncio.wait_for(
                    loop.run_in_executor(self._executor, ak.bond_china_yield),
                    timeout=30.0
                )
            else:
                df = await asyncio.to_thread(ak.bond_china_yield)
            
            if df is None or df.empty:
                return None
            
            return self._parse_akshare_df(df)
        except asyncio.TimeoutError:
            logger.warning("[BondFetcher] akshare timeout")
            return None
        except Exception as e:
            logger.warning(f"[BondFetcher] akshare failed: {e}")
            return None
    
    def _parse_akshare_df(self, df) -> Dict[str, Any]:
        """Parse akshare DataFrame into yield curve data."""
        df = df.sort_values("日期").reset_index(drop=True)
        unique_dates = sorted(df["日期"].unique())
        
        def parse_row(row):
            tenors = {}
            for col in ["3月", "6月", "1年", "3年", "5年", "7年", "10年", "30年"]:
                if col in row and row[col] is not None:
                    try:
                        tenors[col] = round(float(row[col]), 4)
                    except (ValueError, TypeError):
                        pass
            return tenors
        
        def get_gov_row(df_slice):
            for _, row in df_slice.iterrows():
                cn = str(row.get("曲线名称", ""))
                if "国债" in cn:
                    return parse_row(row)
            return None
        
        latest_date = unique_dates[-1]
        latest_df = df[df["日期"] == latest_date]
        gov_row = get_gov_row(latest_df)
        
        # Historical curves
        date_1m = unique_dates[-22] if len(unique_dates) >= 22 else None
        date_1y = unique_dates[-252] if len(unique_dates) >= 252 else None
        gov_row_1m = get_gov_row(df[df["日期"] == date_1m]) if date_1m else None
        gov_row_1y = get_gov_row(df[df["日期"] == date_1y]) if date_1y else None
        
        # Commercial bank AAA curve
        comm_row = None
        for _, row in latest_df.iterrows():
            cn = str(row.get("曲线名称", ""))
            if "商业" in cn and comm_row is None:
                comm_row = parse_row(row)
        
        # Calculate spreads
        spreads = {}
        for col in ["3月", "6月", "1年", "3年", "5年", "7年", "10年", "30年"]:
            g = gov_row.get(col) if gov_row else None
            o = comm_row.get(col) if comm_row else None
            if g is not None and o is not None:
                spreads[col] = round((o - g) * 100, 2)  # bps
        
        # Get the actual date from data
        last_update = str(latest_date)
        if hasattr(latest_date, 'strftime'):
            last_update = latest_date.strftime("%Y-%m-%d")
        
        return {
            "yield_curve": gov_row or {},
            "yield_curve_1m": gov_row_1m or {},
            "yield_curve_1y": gov_row_1y or {},
            "comm_yield": comm_row or {},
            "spreads_bps": spreads,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source": "akshare",
            "last_update": last_update,
            "is_stale": False,
        }
    
    async def _fetch_from_cfets(self) -> Optional[Dict[str, Any]]:
        """
        Fetch from CFETS (China Foreign Exchange Trade System).
        
        CFETS provides RMB bond yield data via their public API.
        """
        try:
            response = await self._http_client.get(CFETS_BOND_API)
            if response.status_code != 200:
                return None
            
            data = response.json()
            if not data or "records" not in data:
                return None
            
            # Parse CFETS data format
            # CFETS typically provides: {records: [{bondCode, yield, ...}]}
            yield_curve = {}
            comm_yield = {}
            spreads = {}
            
            for record in data.get("records", []):
                # Map CFETS bond codes to tenors
                bond_code = record.get("bondCode", "")
                yield_val = record.get("yield")
                
                if yield_val is None:
                    continue
                
                # Try to extract tenor from bond code or name
                tenor = self._map_cfets_code_to_tenor(bond_code, record.get("bondName", ""))
                if tenor:
                    if "国债" in record.get("bondName", ""):
                        yield_curve[tenor] = round(float(yield_val), 4)
                    else:
                        comm_yield[tenor] = round(float(yield_val), 4)
            
            if not yield_curve:
                return None
            
            # Calculate spreads
            for tenor in yield_curve:
                if tenor in comm_yield:
                    spreads[tenor] = round((comm_yield[tenor] - yield_curve[tenor]) * 100, 2)
            
            return {
                "yield_curve": yield_curve,
                "yield_curve_1m": {},
                "yield_curve_1y": {},
                "comm_yield": comm_yield,
                "spreads_bps": spreads,
                "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "source": "cfets",
                "last_update": datetime.now().strftime("%Y-%m-%d"),
                "is_stale": False,
            }
        except Exception as e:
            logger.warning(f"[BondFetcher] CFETS fetch failed: {e}")
            return None
    
    async def _fetch_from_chinabond(self) -> Optional[Dict[str, Any]]:
        """
        Fetch from Chinabond (China Central Depository & Clearing).
        
        Chinabond provides official bond yield curves.
        """
        try:
            # Chinabond API endpoint for yield curves
            response = await self._http_client.get(
                CHINABOND_API,
                params={"type": "gov"}  # Government bonds
            )
            
            if response.status_code != 200:
                return None
            
            # Parse response (format varies, this is a simplified example)
            data = response.json()
            if not data:
                return None
            
            # Try to extract yield curve data
            yield_curve = {}
            if isinstance(data, list):
                for item in data:
                    tenor = item.get("tenor")
                    rate = item.get("rate")
                    if tenor and rate:
                        yield_curve[tenor] = round(float(rate), 4)
            
            if not yield_curve:
                return None
            
            return {
                "yield_curve": yield_curve,
                "yield_curve_1m": {},
                "yield_curve_1y": {},
                "comm_yield": {},
                "spreads_bps": {},
                "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "source": "chinabond",
                "last_update": datetime.now().strftime("%Y-%m-%d"),
                "is_stale": False,
            }
        except Exception as e:
            logger.warning(f"[BondFetcher] Chinabond fetch failed: {e}")
            return None
    
    def _map_cfets_code_to_tenor(self, code: str, name: str) -> Optional[str]:
        """Map CFETS bond code/name to standard tenor label."""
        # Try to extract tenor from name first
        name_lower = name.lower()
        
        tenor_map = {
            "3月": ["3m", "3个月", "三个月"],
            "6月": ["6m", "6个月", "六个月"],
            "1年": ["1y", "1年", "一年", "12m"],
            "3年": ["3y", "3年", "三年"],
            "5年": ["5y", "5年", "五年"],
            "7年": ["7y", "7年", "七年"],
            "10年": ["10y", "10年", "十年"],
            "30年": ["30y", "30年", "三十年"],
        }
        
        for tenor, keywords in tenor_map.items():
            for kw in keywords:
                if kw in name_lower:
                    return tenor
        
        return None
    
    def _is_data_fresh(self, data: Dict[str, Any]) -> bool:
        """Check if data is fresh (within STALE_DATA_THRESHOLD_DAYS)."""
        if not data:
            return False
        
        last_update_str = data.get("last_update", "")
        if not last_update_str:
            return False
        
        try:
            # Parse date string
            if isinstance(last_update_str, str):
                last_update = datetime.strptime(last_update_str, "%Y-%m-%d")
            else:
                last_update = last_update_str
            
            # Check if within threshold
            threshold = datetime.now() - timedelta(days=STALE_DATA_THRESHOLD_DAYS)
            return last_update >= threshold
        except (ValueError, TypeError):
            return False
    
    def _get_mock_data(self, is_stale: bool = True) -> Dict[str, Any]:
        """Return static mock data for fallback."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        return {
            "yield_curve": {
                "3月": 2.0316, "6月": 2.1355, "1年": 2.4525,
                "3年": 2.7645, "5年": 2.9373, "7年": 3.1112,
                "10年": 3.1185, "30年": 3.7156,
            },
            "yield_curve_1m": {
                "3月": 2.0816, "6月": 2.1955, "1年": 2.5225,
                "3年": 2.8345, "5年": 3.0273, "7年": 3.2012,
                "10年": 3.1985, "30年": 3.7956,
            },
            "yield_curve_1y": {
                "3月": 2.2316, "6月": 2.3355, "1年": 2.6525,
                "3年": 2.9645, "5年": 3.1373, "7年": 3.3112,
                "10年": 3.2185, "30年": 3.9156,
            },
            "comm_yield": {
                "3月": 2.5210, "6月": 2.6557, "1年": 2.8580,
                "3年": 3.3284, "5年": 3.5453, "7年": 3.6985,
                "10年": 3.8367, "30年": 4.4626,
            },
            "spreads_bps": {},
            "update_time": now_str,
            "source": "mock",
            "last_update": "2021-01-22" if is_stale else now_str.split()[0],
            "is_stale": is_stale,
        }


# Singleton instance
_bond_fetcher: Optional[BondDataFetcher] = None


def get_bond_fetcher(executor=None) -> BondDataFetcher:
    """Get or create BondDataFetcher singleton."""
    global _bond_fetcher
    if _bond_fetcher is None:
        _bond_fetcher = BondDataFetcher(executor)
    return _bond_fetcher
