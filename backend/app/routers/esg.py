"""
ESG评价体系 API
数据来源: AkShare stock_esg_* 系列函数
功能: ESG评级查询、碳排放数据、ESG趋势分析
"""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Query
from typing import Optional, List
from pydantic import BaseModel
from app.utils.response import success_response, error_response, ErrorCode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/esg", tags=["esg"])

_akshare_module = None

def _get_ak():
    global _akshare_module
    if _akshare_module is None:
        import akshare as ak
        _akshare_module = ak
    return _akshare_module

_cache = {}
_cache_ttl = {}
CACHE_DURATION = 3600  # 1小时缓存（ESG数据更新慢）
_ESG_ALL_DATA = None  # 全量ESG数据缓存
_ESG_DATA_TIME = None

def _get_cache(key):
    if key in _cache and key in _cache_ttl:
        if datetime.now() < _cache_ttl[key]:
            return _cache[key]
    return None

def _set_cache(key, value):
    _cache[key] = value
    _cache_ttl[key] = datetime.now() + timedelta(seconds=CACHE_DURATION)

class ESGRating(BaseModel):
    symbol: str
    name: Optional[str] = None
    rating: Optional[str] = None
    score: Optional[float] = None
    date: Optional[str] = None
    source: str

class ESGRatingResponse(BaseModel):
    ratings: List[ESGRating]

@router.get("/rating/{symbol}")
async def get_esg_rating(symbol: str):
    """
    获取股票ESG评级
    
    数据来源: 华证ESG、MSCI ESG、新浪ESG
    """
    cache_key = f"esg_rating_{symbol}"
    cached = _get_cache(cache_key)
    if cached:
        return success_response(cached)
    
    try:
        ak = _get_ak()
        ratings = []
        
        # 华证ESG评级
        try:
            df_hz = ak.stock_esg_hz_sina()
            if df_hz is not None and not df_hz.empty:
                # 按股票代码筛选
                df_filtered = df_hz[df_hz['股票代码'] == symbol] if '股票代码' in df_hz.columns else df_hz
                for _, row in df_filtered.iterrows():
                    ratings.append({
                        "symbol": symbol,
                        "name": str(row.get("股票名称", "")),
                        "rating": str(row.get("ESG等级", "")),
                        "score": float(row.get("ESG评分", 0)) if row.get("ESG评分") else None,
                        "date": str(row.get("日期", "")),
                        "source": "华证ESG",
                        "environment_score": float(row.get("环境", 0)) if row.get("环境") else None,
                        "social_score": float(row.get("社会", 0)) if row.get("社会") else None,
                        "governance_score": float(row.get("公司治理", 0)) if row.get("公司治理") else None,
                    })
        except Exception as e:
            logger.warning(f"华证ESG数据获取失败: {e}")
        
        # MSCI ESG评级
        try:
            df_msci = ak.stock_esg_msci_sina(symbol=symbol)
            if df_msci is not None and not df_msci.empty:
                for _, row in df_msci.iterrows():
                    ratings.append({
                        "symbol": symbol,
                        "name": str(row.get("股票名称", "")),
                        "rating": str(row.get("MSCI ESG评级", "")),
                        "score": None,
                        "date": str(row.get("评级日期", "")),
                        "source": "MSCI ESG"
                    })
        except Exception as e:
            logger.warning(f"MSCI ESG数据获取失败: {e}")
        
        # 新浪ESG评级汇总
        try:
            df_rate = ak.stock_esg_rate_sina(symbol=symbol)
            if df_rate is not None and not df_rate.empty:
                for _, row in df_rate.iterrows():
                    ratings.append({
                        "symbol": symbol,
                        "name": str(row.get("股票名称", "")),
                        "rating": str(row.get("ESG评级", "")),
                        "score": float(row.get("ESG得分", 0)) if row.get("ESG得分") else None,
                        "date": str(row.get("评级日期", "")),
                        "source": "新浪ESG"
                    })
        except Exception as e:
            logger.warning(f"新浪ESG数据获取失败: {e}")
        
        result = {"ratings": ratings, "total": len(ratings)}
        _set_cache(cache_key, result)
        return success_response(result)
        
    except Exception as e:
        logger.error(f"获取ESG评级失败: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取ESG评级失败: {str(e)}")

@router.get("/carbon")
async def get_carbon_data():
    """
    获取碳排放交易数据
    
    数据来源: 北京碳交易、国内碳交易、欧盟碳交易
    """
    cache_key = "esg_carbon"
    cached = _get_cache(cache_key)
    if cached:
        return success_response(cached)
    
    try:
        ak = _get_ak()
        carbon_data = []
        
        # 北京碳交易
        try:
            df_bj = ak.energy_carbon_bj()
            if df_bj is not None and not df_bj.empty:
                latest = df_bj.iloc[-1]
                carbon_data.append({
                    "market": "北京碳交易",
                    "price": float(latest.get("成交价", 0)) if latest.get("成交价") else None,
                    "volume": float(latest.get("成交量", 0)) if latest.get("成交量") else None,
                    "date": str(latest.get("交易日期", "")),
                })
        except Exception as e:
            logger.warning(f"北京碳交易数据获取失败: {e}")
        
        # 国内碳交易
        try:
            df_domestic = ak.energy_carbon_domestic()
            if df_domestic is not None and not df_domestic.empty:
                for _, row in df_domestic.iterrows():
                    carbon_data.append({
                        "market": str(row.get("市场", "")),
                        "price": float(row.get("收盘价", 0)) if row.get("收盘价") else None,
                        "volume": float(row.get("成交量", 0)) if row.get("成交量") else None,
                        "date": str(row.get("日期", "")),
                    })
        except Exception as e:
            logger.warning(f"国内碳交易数据获取失败: {e}")
        
        result = {"carbon_data": carbon_data, "total": len(carbon_data)}
        _set_cache(cache_key, result)
        return success_response(result)
        
    except Exception as e:
        logger.error(f"获取碳排放数据失败: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取碳排放数据失败: {str(e)}")

@router.get("/rank")
async def get_esg_rank(
    limit: int = Query(20, ge=1, le=100, description="返回数量")
):
    """
    获取ESG评级排名
    
    返回ESG评级较高的股票列表
    """
    cache_key = f"esg_rank_{limit}"
    cached = _get_cache(cache_key)
    if cached:
        return success_response(cached)
    
    try:
        ak = _get_ak()
        df = ak.stock_esg_zd_sina()
        
        if df is None or df.empty:
            return success_response({"items": [], "total": 0})
        
        items = []
        for _, row in df.head(limit).iterrows():
            items.append({
                "symbol": str(row.get("股票代码", "")),
                "name": str(row.get("股票名称", "")),
                "rating": str(row.get("ESG评级", "")),
                "score": float(row.get("ESG得分", 0)) if row.get("ESG得分") else None,
                "date": str(row.get("评级日期", "")),
            })
        
        result = {"items": items, "total": len(items)}
        _set_cache(cache_key, result)
        return success_response(result)
        
    except Exception as e:
        logger.error(f"获取ESG排名失败: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取ESG排名失败: {str(e)}")

@router.get("/health")
async def health_check():
    """健康检查"""
    return success_response({
        "status": "ok",
        "service": "esg",
        "cache_size": len(_cache)
    })