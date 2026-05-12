"""
研报平台 API
数据来源: AkShare stock_research_report_em
功能: 研报列表查询、研报摘要、研报统计
"""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Query
from typing import Optional, List
from pydantic import BaseModel
from app.utils.response import success_response, error_response, ErrorCode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/research", tags=["research"])

# 延迟导入
_akshare_module = None

def _get_ak():
    global _akshare_module
    if _akshare_module is None:
        import akshare as ak
        _akshare_module = ak
    return _akshare_module

# 缓存
_cache = {}
_cache_ttl = {}
CACHE_DURATION = 600  # 10分钟缓存

def _get_cache(key):
    if key in _cache and key in _cache_ttl:
        if datetime.now() < _cache_ttl[key]:
            return _cache[key]
    return None

def _set_cache(key, value):
    _cache[key] = value
    _cache_ttl[key] = datetime.now() + timedelta(seconds=CACHE_DURATION)

# 响应模型
class ResearchReport(BaseModel):
    title: str
    institution: str
    analyst: Optional[str] = None
    date: str
    rating: Optional[str] = None
    summary: Optional[str] = None
    url: Optional[str] = None

class ResearchListResponse(BaseModel):
    total: int
    items: List[ResearchReport]
    page: int
    page_size: int

@router.get("/reports")
async def get_research_reports(
    symbol: Optional[str] = Query(None, description="股票代码"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    institution: Optional[str] = Query(None, description="机构筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """
    获取研报列表
    
    参数:
    - symbol: 股票代码（如 600519）
    - keyword: 关键词搜索
    - institution: 机构筛选
    - page: 页码
    - page_size: 每页数量
    """
    cache_key = f"research_reports_{symbol}_{keyword}_{institution}_{page}_{page_size}"
    cached = _get_cache(cache_key)
    if cached:
        return success_response(cached)
    
    try:
        ak = _get_ak()
        
        # 获取研报数据
        if symbol:
            df = ak.stock_research_report_em(symbol=symbol)
        else:
            # 无symbol时返回空列表（AkShare需要symbol参数）
            return success_response({
                "total": 0,
                "items": [],
                "page": page,
                "page_size": page_size
            })
        
        if df is None or df.empty:
            return success_response({
                "total": 0,
                "items": [],
                "page": page,
                "page_size": page_size
            })
        
        # 处理数据
        items = []
        for _, row in df.iterrows():
            item = {
                "title": str(row.get("报告名称", "")),
                "institution": str(row.get("机构", "")),
                "analyst": None,
                "date": str(row.get("日期", "")),
                "rating": str(row.get("东财评级", "")) if row.get("东财评级") else None,
                "summary": None,
                "url": str(row.get("报告PDF链接", "")) if row.get("报告PDF链接") else None
            }
            
            # 关键词过滤
            if keyword and keyword.lower() not in item["title"].lower():
                continue
            
            # 机构过滤
            if institution and institution not in item["institution"]:
                continue
            
            items.append(item)
        
        # 分页
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        paged_items = items[start:end]
        
        result = {
            "total": total,
            "items": paged_items,
            "page": page,
            "page_size": page_size
        }
        
        _set_cache(cache_key, result)
        return success_response(result)
        
    except Exception as e:
        logger.error(f"获取研报列表失败: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取研报列表失败: {str(e)}")

@router.get("/reports/{report_id}")
async def get_research_report_detail(report_id: str):
    """
    获取研报详情（预留接口）
    
    注: AkShare暂不支持研报全文，仅返回基本信息
    """
    return success_response({
        "id": report_id,
        "message": "研报全文需要付费数据源支持"
    })

@router.get("/statistics")
async def get_research_statistics(
    symbol: str = Query(..., description="股票代码")
):
    """
    获取研报统计
    
    返回: 各机构评级分布、近期研报数量等
    """
    cache_key = f"research_stats_{symbol}"
    cached = _get_cache(cache_key)
    if cached:
        return success_response(cached)
    
    try:
        ak = _get_ak()
        df = ak.stock_research_report_em(symbol=symbol)
        
        if df is None or df.empty:
            return success_response({
                "total": 0,
                "institutions": [],
                "ratings": {}
            })
        
        # 统计机构分布
        institutions = df["机构"].value_counts().to_dict() if "机构" in df.columns else {}
        
        # 统计评级分布
        ratings = df["评级"].value_counts().to_dict() if "评级" in df.columns else {}
        
        result = {
            "total": len(df),
            "institutions": institutions,
            "ratings": ratings
        }
        
        _set_cache(cache_key, result)
        return success_response(result)
        
    except Exception as e:
        logger.error(f"获取研报统计失败: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取研报统计失败: {str(e)}")

@router.get("/health")
async def health_check():
    """健康检查"""
    return success_response({
        "status": "ok",
        "service": "research",
        "cache_size": len(_cache)
    })
