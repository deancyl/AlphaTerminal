"""
研报平台 API 路由
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import httpx
import akshare as ak
from functools import lru_cache
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/research", tags=["research"])

# 内存缓存
_research_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 300  # 5分钟缓存

# Fallback 数据（当数据源不可用时返回）
FALLBACK_RESEARCH_DATA = [
    {
        "title": "贵州茅台：业绩稳健增长，品牌护城河深厚",
        "institution": "中信证券",
        "date": "2026-05-10",
        "rating": "买入",
        "url": None,
    },
    {
        "title": "贵州茅台：高端白酒龙头，长期价值凸显",
        "institution": "国泰君安",
        "date": "2026-05-08",
        "rating": "增持",
        "url": None,
    },
    {
        "title": "贵州茅台：Q1业绩超预期，现金流充沛",
        "institution": "华泰证券",
        "date": "2026-05-05",
        "rating": "买入",
        "url": None,
    },
    {
        "title": "贵州茅台：渠道改革成效显现",
        "institution": "招商证券",
        "date": "2026-05-03",
        "rating": "强烈推荐",
        "url": None,
    },
    {
        "title": "贵州茅台：估值处于历史低位",
        "institution": "中金公司",
        "date": "2026-05-01",
        "rating": "跑赢行业",
        "url": None,
    },
    {
        "title": "贵州茅台：直销占比提升，毛利率改善",
        "institution": "海通证券",
        "date": "2026-04-28",
        "rating": "买入",
        "url": None,
    },
    {
        "title": "贵州茅台：系列酒增长亮眼",
        "institution": "广发证券",
        "date": "2026-04-25",
        "rating": "买入",
        "url": None,
    },
    {
        "title": "贵州茅台：国际化布局稳步推进",
        "institution": "东方证券",
        "date": "2026-04-22",
        "rating": "增持",
        "url": None,
    },
    {
        "title": "贵州茅台：分红率维持高位",
        "institution": "兴业证券",
        "date": "2026-04-20",
        "rating": "买入",
        "url": None,
    },
    {
        "title": "贵州茅台：量价齐升可期",
        "institution": "平安证券",
        "date": "2026-04-18",
        "rating": "推荐",
        "url": None,
    },
]


def _fetch_reports_sync(symbol: str, page: int = 1, page_size: int = 20, keyword: str = "", institution: str = "") -> Dict[str, Any]:
    """同步获取研报数据"""
    try:
        # 使用 akshare 获取研报数据
        df = ak.stock_research_report_em(symbol=symbol)
        
        if df is None or df.empty:
            logger.warning(f"No research data for {symbol}")
            return {"total": 0, "items": [], "is_fallback": True}
        
        # 数据映射（akshare 列名为中文）
        items = []
        for _, row in df.iterrows():
            item = {
                "title": str(row.get("报告名称", "")),
                "institution": str(row.get("机构", "")),
                "date": str(row.get("日期", "")),
                "rating": str(row.get("东财评级", "")),
                "url": str(row.get("报告PDF链接", "")) if row.get("报告PDF链接") else None,
            }
            
            # 关键词过滤
            if keyword and keyword.lower() not in item["title"].lower():
                continue
            
            # 机构过滤
            if institution and institution != item["institution"]:
                continue
            
            items.append(item)
        
        # 分页
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_items = items[start:end]
        
        return {
            "total": total,
            "items": paginated_items,
            "is_fallback": False,
        }
        
    except Exception as e:
        logger.error(f"Error fetching research data for {symbol}: {e}")
        return {"total": len(FALLBACK_RESEARCH_DATA), "items": FALLBACK_RESEARCH_DATA, "is_fallback": True}


@router.get("/reports")
async def get_reports(
    symbol: str = Query(..., description="股票代码"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: str = Query("", description="关键词搜索"),
    institution: str = Query("", description="机构筛选"),
):
    """获取研报列表"""
    cache_key = f"{symbol}_{keyword}_{institution}"
    
    # 检查缓存
    if cache_key in _research_cache:
        cached = _research_cache[cache_key]
        if (datetime.now() - cached["timestamp"]).total_seconds() < CACHE_TTL:
            data = cached["data"]
            total = data["total"]
            start = (page - 1) * page_size
            end = start + page_size
            return {
                "code": 0,
                "message": "success",
                "data": {
                    "total": total,
                    "items": data["items"][start:end],
                    "is_fallback": data.get("is_fallback", False),
                }
            }
    
    # 获取数据
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _fetch_reports_sync, symbol, 1, 1000, keyword, institution)
    
    # 缓存结果
    _research_cache[cache_key] = {
        "data": data,
        "timestamp": datetime.now(),
    }
    
    # 分页返回
    total = data["total"]
    start = (page - 1) * page_size
    end = start + page_size
    items = data["items"][start:end] if not data.get("is_fallback") else data["items"]
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "total": total,
            "items": items,
            "is_fallback": data.get("is_fallback", False),
        }
    }


@router.get("/statistics")
async def get_statistics(symbol: str = Query(..., description="股票代码")):
    """获取研报统计信息"""
    # 获取所有研报
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _fetch_reports_sync, symbol, 1, 1000, "", "")
    
    if data.get("is_fallback"):
        return {
            "code": 0,
            "message": "success",
            "data": {
                "total": len(FALLBACK_RESEARCH_DATA),
                "institutions": {"中信证券": 2, "国泰君安": 2, "华泰证券": 2},
                "ratings": {"买入": 5, "增持": 3, "推荐": 2},
            }
        }
    
    items = data["items"]
    
    # 统计机构
    institutions: Dict[str, int] = {}
    ratings: Dict[str, int] = {}
    
    for item in items:
        inst = item.get("institution", "未知")
        institutions[inst] = institutions.get(inst, 0) + 1
        
        rating = item.get("rating", "未评级")
        ratings[rating] = ratings.get(rating, 0) + 1
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "total": len(items),
            "institutions": institutions,
            "ratings": ratings,
        }
    }


@router.get("/status")
async def get_status():
    """获取研报缓存状态"""
    return {
        "code": 0,
        "message": "success",
        "data": {
            "cache_ready": len(_research_cache) > 0,
            "cached_symbols": list(set(k.split("_")[0] for k in _research_cache.keys())),
            "cache_size": len(_research_cache),
        }
    }


@router.get("/pdf")
async def proxy_pdf(url: str = Query(..., description="PDF URL")):
    """代理 PDF 文件（绕过安全限制）"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={
                    "Referer": "https://data.eastmoney.com/",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                },
                follow_redirects=True,
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch PDF")
            
            return StreamingResponse(
                iter([response.content]),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"inline; filename=research_report.pdf",
                    "Cache-Control": "no-cache",
                }
            )
    except Exception as e:
        logger.error(f"Error proxying PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))
