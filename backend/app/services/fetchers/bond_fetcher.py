"""
Bond data fetcher with multi-source fallback support.

Primary: bond_spot_quote (real-time dealer quotes)
Fallback 1: bond_spot_deal (real-time deals)
Fallback 2: akshare bond_china_yield (historical, stopped 2021-01-22)
Fallback 3: CFETS fx_spot_quote (RMB bond yields)
Fallback 4: Chinabond API (via httpx)
Last Resort: Static mock data
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import httpx

from app.services.unified_fetcher import get_source_breaker

logger = logging.getLogger(__name__)

# Constants
STALE_DATA_THRESHOLD_DAYS = 7
CFETS_BOND_API = (
    "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr-today.json"
)
CHINABOND_API = "https://www.chinabond.com.cn/cbweb/market/yield-curves"


class BondDataFetcher:
    """
    Multi-source bond yield data fetcher with automatic fallback.

    Fallback chain:
    1. bond_zh_us_rate (daily updated yields) - PRIMARY
    2. bond_spot_quote (real-time dealer quotes)
    3. bond_spot_deal (real-time deals)
    4. akshare bond_china_yield (historical, may be stale)
    5. CFETS (China Foreign Exchange Trade System)
    6. Chinabond (China Central Depository & Clearing)
    7. Static mock data
    """

    # Source name constants for circuit breaker registry
    SOURCE_BOND_ZH_US_RATE = "bond_zh_us_rate"
    SOURCE_BOND_SPOT_QUOTE = "bond_spot_quote"
    SOURCE_BOND_SPOT_DEAL = "bond_spot_deal"
    SOURCE_AKSHARE = "bond_akshare"
    SOURCE_CFETS = "bond_cfets"
    SOURCE_CHINABOND = "bond_chinabond"

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
        # Try primary source: bond_zh_us_rate (daily updated, multiple tenors)
        data = await self._fetch_from_bond_zh_us_rate()
        if data and self._is_data_fresh(data):
            logger.info("[BondFetcher] Using bond_zh_us_rate data")
            return data

        # Try fallback 1: bond_spot_quote (real-time dealer quotes)
        data = await self._fetch_from_bond_spot()
        if data and self._is_data_fresh(data):
            logger.info("[BondFetcher] Using bond_spot_quote data")
            return data

        # Try fallback 2: bond_spot_deal (real-time deals)
        data = await self._fetch_from_bond_spot_deal()
        if data and self._is_data_fresh(data):
            logger.info("[BondFetcher] Using bond_spot_deal data")
            return data

        # Try fallback 3: akshare (historical, may be stale)
        data = await self._fetch_from_akshare()
        if data:
            logger.warning("[BondFetcher] Using stale akshare data")
            return data

        # Try fallback 4: CFETS
        data = await self._fetch_from_cfets()
        if data and self._is_data_fresh(data):
            return data

        # Try fallback 5: Chinabond
        data = await self._fetch_from_chinabond()
        if data and self._is_data_fresh(data):
            return data

        # Last resort: return mock data with stale flag
        logger.warning("[BondFetcher] All sources failed, using mock fallback")
        return self._get_mock_data(is_stale=True)

    async def _fetch_from_bond_zh_us_rate(self) -> Optional[Dict[str, Any]]:
        """
        Fetch Chinese government bond yields from bond_zh_us_rate.

        This provides daily updated yield curve data with multiple tenors.
        """
        cb = get_source_breaker(self.SOURCE_BOND_ZH_US_RATE)

        if not cb.is_available():
            logger.warning(f"[Bond] {self.SOURCE_BOND_ZH_US_RATE} CB OPEN")
            return None

        try:
            import akshare as ak
            import warnings

            warnings.filterwarnings("ignore")

            if self._executor:
                loop = asyncio.get_running_loop()
                df = await asyncio.wait_for(
                    loop.run_in_executor(self._executor, ak.bond_zh_us_rate),
                    timeout=15.0,
                )
            else:
                df = await asyncio.to_thread(ak.bond_zh_us_rate)

            if df is None or df.empty:
                return None

            data = self._parse_bond_zh_us_rate_df(df)
            cb.record_success()
            return data
        except asyncio.TimeoutError:
            cb.record_failure()
            logger.warning(f"[Bond] {self.SOURCE_BOND_ZH_US_RATE} timeout", exc_info=True)
            return None
        except Exception as e:
            cb.record_failure()
            logger.warning(f"[Bond] {self.SOURCE_BOND_ZH_US_RATE} failed: {e}", exc_info=True)
            return None

    def _parse_bond_zh_us_rate_df(self, df) -> Dict[str, Any]:
        """Parse bond_zh_us_rate DataFrame into yield curve format."""
        df = df.sort_values("日期").reset_index(drop=True)
        latest_row = df.iloc[-1]

        yield_curve = {}
        tenor_map = {
            "中国国债收益率2年": "2年",
            "中国国债收益率5年": "5年",
            "中国国债收益率10年": "10年",
            "中国国债收益率30年": "30年",
        }

        for col, tenor in tenor_map.items():
            if col in df.columns and latest_row[col] is not None:
                try:
                    yield_curve[tenor] = round(float(latest_row[col]), 4)
                except (ValueError, TypeError):
                    pass

        # Linear interpolation for missing tenors (1Y, 3Y, 7Y)
        import numpy as np

        known_years = []
        known_rates = []
        for tenor, rate in yield_curve.items():
            year = int(tenor.replace("年", ""))
            known_years.append(year)
            known_rates.append(rate)

        if len(known_years) >= 2:
            for missing_year in [1, 3, 7]:
                missing_tenor = f"{missing_year}年"
                if missing_tenor not in yield_curve:
                    interpolated = float(
                        np.interp(missing_year, known_years, known_rates)
                    )
                    yield_curve[missing_tenor] = round(interpolated, 4)

        last_update = str(latest_row["日期"])
        if hasattr(latest_row["日期"], "strftime"):
            last_update = latest_row["日期"].strftime("%Y-%m-%d")

        return {
            "yield_curve": yield_curve,
            "yield_curve_1m": {},
            "yield_curve_1y": {},
            "comm_yield": {},
            "spreads_bps": {},
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source": "bond_zh_us_rate",
            "last_update": last_update,
            "is_stale": False,
        }

    async def _fetch_from_bond_spot(self) -> Optional[Dict[str, Any]]:
        """
        Fetch real-time bond yield data from akshare bond_spot_quote.

        This is a working alternative to bond_china_yield which stopped updating 2021-01-22.
        """
        cb = get_source_breaker(self.SOURCE_BOND_SPOT_QUOTE)

        if not cb.is_available():
            logger.warning(f"[Bond] {self.SOURCE_BOND_SPOT_QUOTE} CB OPEN")
            return None

        try:
            import akshare as ak
            import warnings

            warnings.filterwarnings("ignore")

            if self._executor:
                loop = asyncio.get_running_loop()
                df = await asyncio.wait_for(
                    loop.run_in_executor(self._executor, ak.bond_spot_quote),
                    timeout=15.0,
                )
            else:
                df = await asyncio.to_thread(ak.bond_spot_quote)

            if df is None or df.empty:
                return None

            data = self._parse_bond_spot_df(df)
            cb.record_success()
            return data
        except asyncio.TimeoutError:
            cb.record_failure()
            logger.warning(f"[Bond] {self.SOURCE_BOND_SPOT_QUOTE} timeout", exc_info=True)
            return None
        except Exception as e:
            cb.record_failure()
            logger.warning(f"[Bond] {self.SOURCE_BOND_SPOT_QUOTE} failed: {e}", exc_info=True)
            return None

    async def _fetch_from_bond_spot_deal(self) -> Optional[Dict[str, Any]]:
        """
        Fetch real-time bond deal data from akshare bond_spot_deal.

        bond_spot_deal returns recent bond transactions with yield rates.
        """
        cb = get_source_breaker(self.SOURCE_BOND_SPOT_DEAL)

        if not cb.is_available():
            logger.warning(f"[Bond] {self.SOURCE_BOND_SPOT_DEAL} CB OPEN")
            return None

        try:
            import akshare as ak
            import warnings

            warnings.filterwarnings("ignore")

            if self._executor:
                loop = asyncio.get_running_loop()
                df = await asyncio.wait_for(
                    loop.run_in_executor(self._executor, ak.bond_spot_deal),
                    timeout=15.0,
                )
            else:
                df = await asyncio.to_thread(ak.bond_spot_deal)

            if df is None or df.empty:
                return None

            data = self._parse_bond_spot_deal_df(df)
            cb.record_success()
            return data
        except asyncio.TimeoutError:
            cb.record_failure()
            logger.warning(f"[Bond] {self.SOURCE_BOND_SPOT_DEAL} timeout", exc_info=True)
            return None
        except Exception as e:
            cb.record_failure()
            logger.warning(f"[Bond] {self.SOURCE_BOND_SPOT_DEAL} failed: {e}", exc_info=True)
            return None

    async def _fetch_from_akshare(self) -> Optional[Dict[str, Any]]:
        """Fetch from akshare bond_china_yield."""
        cb = get_source_breaker(self.SOURCE_AKSHARE)

        if not cb.is_available():
            logger.warning(f"[Bond] {self.SOURCE_AKSHARE} CB OPEN")
            return None

        try:
            import akshare as ak
            import warnings

            warnings.filterwarnings("ignore")

            if self._executor:
                loop = asyncio.get_running_loop()
                df = await asyncio.wait_for(
                    loop.run_in_executor(self._executor, ak.bond_china_yield),
                    timeout=30.0,
                )
            else:
                df = await asyncio.to_thread(ak.bond_china_yield)

            if df is None or df.empty:
                return None

            data = self._parse_akshare_df(df)
            cb.record_success()
            return data
        except asyncio.TimeoutError:
            cb.record_failure()
            logger.warning(f"[Bond] {self.SOURCE_AKSHARE} timeout", exc_info=True)
            return None
        except Exception as e:
            cb.record_failure()
            logger.warning(f"[Bond] {self.SOURCE_AKSHARE} failed: {e}", exc_info=True)
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
        if hasattr(latest_date, "strftime"):
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

    def _parse_bond_spot_df(self, df) -> Dict[str, Any]:
        """
        Parse bond_spot_quote DataFrame into yield curve format.

        bond_spot_quote returns dealer quotes with yield rates.
        We extract government bond yields and calculate spreads.
        """
        # Filter for government bonds (国债)
        gov_bonds = df[df["债券简称"].str.contains("国债", na=False)]

        # Build yield curve from quotes
        yield_curve = {}
        for _, row in gov_bonds.iterrows():
            tenor = self._extract_tenor_from_bond_name(row["债券简称"])
            if tenor:
                # Use average of buy/sell yield
                avg_yield = (row["买入收益率"] + row["卖出收益率"]) / 2
                yield_curve[tenor] = round(float(avg_yield), 4)

        # Also get policy bank bonds (农发, 国开, 进出)
        policy_bonds = df[df["债券简称"].str.contains("农发|国开|进出", na=False)]
        comm_yield = {}
        for _, row in policy_bonds.iterrows():
            tenor = self._extract_tenor_from_bond_name(row["债券简称"])
            if tenor:
                avg_yield = (row["买入收益率"] + row["卖出收益率"]) / 2
                comm_yield[tenor] = round(float(avg_yield), 4)

        # Calculate spreads
        spreads = {}
        for tenor in yield_curve:
            if tenor in comm_yield:
                spreads[tenor] = round(
                    (comm_yield[tenor] - yield_curve[tenor]) * 100, 2
                )

        return {
            "yield_curve": yield_curve,
            "yield_curve_1m": {},
            "yield_curve_1y": {},
            "comm_yield": comm_yield,
            "spreads_bps": spreads,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source": "bond_spot_quote",
            "last_update": datetime.now().strftime("%Y-%m-%d"),
            "is_stale": False,
        }

    def _parse_bond_spot_deal_df(self, df) -> Dict[str, Any]:
        """
        Parse bond_spot_deal DataFrame into yield curve format.

        bond_spot_deal returns recent bond transactions with yield rates.
        """
        # Filter for government bonds (国债)
        gov_bonds = df[df["债券简称"].str.contains("国债", na=False)]

        # Build yield curve from recent deals
        yield_curve = {}
        for _, row in gov_bonds.iterrows():
            tenor = self._extract_tenor_from_bond_name(row["债券简称"])
            if tenor:
                # Use latest yield from deals
                if "最新收益率" in row and row["最新收益率"] is not None:
                    yield_curve[tenor] = round(float(row["最新收益率"]), 4)

        # Also get policy bank bonds (农发, 国开, 进出)
        policy_bonds = df[df["债券简称"].str.contains("农发|国开|进出", na=False)]
        comm_yield = {}
        for _, row in policy_bonds.iterrows():
            tenor = self._extract_tenor_from_bond_name(row["债券简称"])
            if tenor:
                if "最新收益率" in row and row["最新收益率"] is not None:
                    comm_yield[tenor] = round(float(row["最新收益率"]), 4)

        # Calculate spreads
        spreads = {}
        for tenor in yield_curve:
            if tenor in comm_yield:
                spreads[tenor] = round(
                    (comm_yield[tenor] - yield_curve[tenor]) * 100, 2
                )

        return {
            "yield_curve": yield_curve,
            "yield_curve_1m": {},
            "yield_curve_1y": {},
            "comm_yield": comm_yield,
            "spreads_bps": spreads,
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source": "bond_spot_deal",
            "last_update": datetime.now().strftime("%Y-%m-%d"),
            "is_stale": False,
        }

    def _extract_tenor_from_bond_name(self, name: str) -> Optional[str]:
        """
        Extract tenor from bond name.

        Examples:
        - "20抗疫国债02" -> "2年"
        - "21农发清发04" -> "4年"
        - "23附息国债05" -> "5年"
        """
        import re

        # Try to extract year number from bond name
        match = re.search(r"(\d{2})$", name)
        if match:
            year_num = int(match.group(1))
            # Map to standard tenors
            if year_num <= 1:
                return "1年"
            elif year_num <= 3:
                return "3年"
            elif year_num <= 5:
                return "5年"
            elif year_num <= 7:
                return "7年"
            elif year_num <= 10:
                return "10年"
            else:
                return "30年"

        return None

    async def _fetch_from_cfets(self) -> Optional[Dict[str, Any]]:
        """
        Fetch from CFETS (China Foreign Exchange Trade System).

        CFETS provides RMB bond yield data via their public API.
        """
        cb = get_source_breaker(self.SOURCE_CFETS)

        if not cb.is_available():
            logger.warning(f"[Bond] {self.SOURCE_CFETS} CB OPEN")
            return None

        try:
            response = await self._http_client.get(CFETS_BOND_API)
            if response.status_code != 200:
                cb.record_failure()
                return None

            data = response.json()
            if not data or "records" not in data:
                cb.record_failure()
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
                tenor = self._map_cfets_code_to_tenor(
                    bond_code, record.get("bondName", "")
                )
                if tenor:
                    if "国债" in record.get("bondName", ""):
                        yield_curve[tenor] = round(float(yield_val), 4)
                    else:
                        comm_yield[tenor] = round(float(yield_val), 4)

            if not yield_curve:
                cb.record_failure()
                return None

            # Calculate spreads
            for tenor in yield_curve:
                if tenor in comm_yield:
                    spreads[tenor] = round(
                        (comm_yield[tenor] - yield_curve[tenor]) * 100, 2
                    )

            result = {
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
            cb.record_success()
            return result
        except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
            cb.record_failure()
            logger.warning(f"[HTTP] {self.SOURCE_CFETS} failed: {e}", exc_info=True)
            return None

    async def _fetch_from_chinabond(self) -> Optional[Dict[str, Any]]:
        """
        Fetch from Chinabond (China Central Depository & Clearing).

        Chinabond provides official bond yield curves.
        """
        cb = get_source_breaker(self.SOURCE_CHINABOND)

        if not cb.is_available():
            logger.warning(f"[Bond] {self.SOURCE_CHINABOND} CB OPEN")
            return None

        try:
            # Chinabond API endpoint for yield curves
            response = await self._http_client.get(
                CHINABOND_API, params={"type": "gov"}  # Government bonds
            )

            if response.status_code != 200:
                cb.record_failure()
                return None

            # Parse response (format varies, this is a simplified example)
            data = response.json()
            if not data:
                cb.record_failure()
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
                cb.record_failure()
                return None

            result = {
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
            cb.record_success()
            return result
        except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
            cb.record_failure()
            logger.warning(f"[HTTP] {self.SOURCE_CHINABOND} failed: {e}", exc_info=True)
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
                "3月": 2.0316,
                "6月": 2.1355,
                "1年": 2.4525,
                "3年": 2.7645,
                "5年": 2.9373,
                "7年": 3.1112,
                "10年": 3.1185,
                "30年": 3.7156,
            },
            "yield_curve_1m": {
                "3月": 2.0816,
                "6月": 2.1955,
                "1年": 2.5225,
                "3年": 2.8345,
                "5年": 3.0273,
                "7年": 3.2012,
                "10年": 3.1985,
                "30年": 3.7956,
            },
            "yield_curve_1y": {
                "3月": 2.2316,
                "6月": 2.3355,
                "1年": 2.6525,
                "3年": 2.9645,
                "5年": 3.1373,
                "7年": 3.3112,
                "10年": 3.2185,
                "30年": 3.9156,
            },
            "comm_yield": {
                "3月": 2.5210,
                "6月": 2.6557,
                "1年": 2.8580,
                "3年": 3.3284,
                "5年": 3.5453,
                "7年": 3.6985,
                "10年": 3.8367,
                "30年": 4.4626,
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
