"""
研报平台 API 路由
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import httpx
import akshare as ak
from app.services.data_cache import get_cache
from app.services.model_config_service import get_model_config_service
from app.utils.error_decorator import handle_errors

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/research", tags=["research"])

_cache = get_cache()
NAMESPACE = "research:"
TTL = 300  # 5分钟缓存

# Fallback 数据（当数据源不可用时返回）
FALLBACK_RESEARCH_DATA = [
    {
        "title": "贵州茅台：业绩稳健增长，品牌护城河深厚",
        "institution": "中信证券",
        "date": "2026-05-10",
        "rating": "买入",
        "url": None,
        "category": "stock",
    },
    {
        "title": "贵州茅台：高端白酒龙头，长期价值凸显",
        "institution": "国泰君安",
        "date": "2026-05-08",
        "rating": "增持",
        "url": None,
        "category": "stock",
    },
    {
        "title": "贵州茅台：Q1业绩超预期，现金流充沛",
        "institution": "华泰证券",
        "date": "2026-05-05",
        "rating": "买入",
        "url": None,
        "category": "stock",
    },
    {
        "title": "贵州茅台：渠道改革成效显现",
        "institution": "招商证券",
        "date": "2026-05-03",
        "rating": "强烈推荐",
        "url": None,
        "category": "stock",
    },
    {
        "title": "贵州茅台：估值处于历史低位",
        "institution": "中金公司",
        "date": "2026-05-01",
        "rating": "跑赢行业",
        "url": None,
        "category": "stock",
    },
    {
        "title": "贵州茅台：直销占比提升，毛利率改善",
        "institution": "海通证券",
        "date": "2026-04-28",
        "rating": "买入",
        "url": None,
        "category": "stock",
    },
    {
        "title": "贵州茅台：系列酒增长亮眼",
        "institution": "广发证券",
        "date": "2026-04-25",
        "rating": "买入",
        "url": None,
        "category": "stock",
    },
    {
        "title": "贵州茅台：国际化布局稳步推进",
        "institution": "东方证券",
        "date": "2026-04-22",
        "rating": "增持",
        "url": None,
        "category": "stock",
    },
    {
        "title": "贵州茅台：分红率维持高位",
        "institution": "兴业证券",
        "date": "2026-04-20",
        "rating": "买入",
        "url": None,
        "category": "stock",
    },
    {
        "title": "贵州茅台：量价齐升可期",
        "institution": "平安证券",
        "date": "2026-04-18",
        "rating": "推荐",
        "url": None,
        "category": "stock",
    },
]

# 研报分类
RESEARCH_CATEGORIES = ["macro", "industry", "stock", "fixed_income"]

# 分类关键词映射
CATEGORY_KEYWORDS = {
    "macro": ["宏观", "经济", "GDP", "CPI", "PMI", "货币政策", "财政政策", "利率", "汇率", "通胀"],
    "industry": ["行业", "板块", "产业链", "竞争格局", "市场规模", "行业趋势"],
    "stock": ["公司", "个股", "业绩", "估值", "盈利", "财报", "分红", "增持", "减持"],
    "fixed_income": ["债券", "信用", "利率债", "信用债", "国债", "收益率曲线", "利差"],
}


class SummarizeRequest(BaseModel):
    """研报总结请求"""
    report_id: str = Field(..., description="研报ID")
    title: str = Field(..., description="研报标题")
    institution: str = Field(..., description="机构名称")
    content: Optional[str] = Field(None, description="研报内容（可选）")


def _classify_report(title: str) -> str:
    """根据标题关键词自动分类研报"""
    title_lower = title.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in title_lower:
                return category
    return "stock"


def _fetch_reports_sync(symbol: str, page: int = 1, page_size: int = 20, keyword: str = "", institution: str = "", category: str = "") -> Dict[str, Any]:
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
                "category": _classify_report(str(row.get("报告名称", ""))),
            }

            # 关键词过滤
            if keyword and keyword.lower() not in item["title"].lower():
                continue

            # 机构过滤
            if institution and institution != item["institution"]:
                continue

            # 分类过滤
            if category and category != item["category"]:
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
        logger.error(f"Error fetching research data for {symbol}: {e}", exc_info=True)
        filtered_fallback = FALLBACK_RESEARCH_DATA
        if category:
            filtered_fallback = [r for r in filtered_fallback if r.get("category") == category]
        return {"total": len(filtered_fallback), "items": filtered_fallback, "is_fallback": True}


@router.get("/reports")
@handle_errors(module="research")
async def get_reports(
    symbol: str = Query(..., description="股票代码"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: str = Query("", description="关键词搜索"),
    institution: str = Query("", description="机构筛选"),
    category: str = Query("", description="分类筛选 (macro/industry/stock/fixed_income)"),
):
    """获取研报列表"""
    cache_key = f"{NAMESPACE}{symbol}_{keyword}_{institution}_{category}"

    cached = _cache.get(cache_key)
    if cached is not None:
        data = cached
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

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _fetch_reports_sync, symbol, 1, 1000, keyword, institution, category)

    _cache.set(cache_key, data, ttl=TTL)

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
@handle_errors(module="research")
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
@handle_errors(module="research")
async def get_status():
    """获取研报缓存状态"""
    stats = _cache.get_stats()
    return {
        "code": 0,
        "message": "success",
        "data": {
            "cache_ready": stats["entry_count"] > 0,
            "cache_stats": stats,
        }
    }


@router.get("/pdf")
@handle_errors(module="research")
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
                    "Content-Disposition": "inline; filename=research_report.pdf",
                    "Cache-Control": "no-cache",
                }
            )
    except Exception as e:
        logger.error(f"Error proxying PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
@handle_errors(module="research")
async def get_categories():
    """获取研报分类列表"""
    return {
        "code": 0,
        "message": "success",
        "data": {
            "categories": RESEARCH_CATEGORIES,
            "labels": {
                "macro": "宏观经济",
                "industry": "行业研究",
                "stock": "个股分析",
                "fixed_income": "固定收益",
            }
        }
    }


@router.post("/summarize")
@handle_errors(module="research")
async def summarize_report(request: SummarizeRequest):
    """使用LLM总结研报核心观点 - 支持大文本分块处理"""
    model_svc = get_model_config_service()
    model = model_svc.get_model("openai") or model_svc.get_model("deepseek")

    if not model or not model.api_key:
        return {
            "code": 1,
            "message": "LLM服务未配置，请检查API Key设置",
            "data": {"summary": None}
        }

    base_url = (model.base_url or "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/chat/completions"

    # Text chunking for large documents (MapReduce style)
    MAX_CHUNK_SIZE = 3000  # Characters per chunk (approx 1000 tokens)
    MAX_TOTAL_SIZE = 50000  # Maximum total content size

    content = request.content or ""
    if len(content) > MAX_TOTAL_SIZE:
        content = content[:MAX_TOTAL_SIZE]
        logger.info(f"[Research] Content truncated to {MAX_TOTAL_SIZE} chars")

    # Split content into chunks if too large
    chunks = []
    if len(content) > MAX_CHUNK_SIZE:
        # Split by paragraphs/sections for better context preservation
        paragraphs = content.split('\n\n')
        current_chunk = ""
        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= MAX_CHUNK_SIZE:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"
        if current_chunk:
            chunks.append(current_chunk.strip())
        logger.info(f"[Research] Split content into {len(chunks)} chunks")
    else:
        chunks = [content] if content else []

    async def call_llm(prompt_text: str, max_tokens: int = 500) -> str:
        """Helper function to call LLM API"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {model.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model.model_id,
                    "messages": [
                        {"role": "system", "content": "你是一位专业的金融分析师，擅长提炼研报核心观点。"},
                        {"role": "user", "content": prompt_text}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.7,
                }
            )

            if response.status_code != 200:
                logger.error(f"LLM API error: {response.status_code} - {response.text}")
                raise Exception(f"LLM API error: {response.status_code}")

            result = response.json()
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")

    try:
        # Map phase: Summarize each chunk
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            chunk_prompt = f"""请用中文总结以下研报片段的核心要点（片段{i+1}/{len(chunks)}）：
研报标题：{request.title}
发布机构：{request.institution}

内容片段：
{chunk}

请提炼2-3个关键要点，每个要点用一句话概括。"""

            try:
                chunk_summary = await call_llm(chunk_prompt, max_tokens=300)
                chunk_summaries.append(chunk_summary)
            except Exception as e:
                logger.warning(f"[Research] Chunk {i+1} summary failed: {e}")
                # Continue with other chunks

        # Reduce phase: Combine chunk summaries
        if len(chunk_summaries) > 1:
            combined_prompt = f"""请整合以下研报片段的总结，生成最终的核心观点总结：

研报标题：{request.title}
发布机构：{request.institution}

各片段总结：
{chr(10).join([f'片段{i+1}: {s}' for i, s in enumerate(chunk_summaries)])}

要求：
1. 整合所有片段的关键要点
2. 去除重复内容
3. 突出投资逻辑和风险提示
4. 最终输出3-5个核心要点"""

            final_summary = await call_llm(combined_prompt, max_tokens=500)
        elif len(chunk_summaries) == 1:
            final_summary = chunk_summaries[0]
        else:
            # No content, use title-only summary
            title_prompt = f"""请用中文总结以下研报的核心观点，要求：
1. 提炼3-5个关键要点
2. 每个要点用一句话概括
3. 突出投资逻辑和风险提示

研报标题：{request.title}
发布机构：{request.institution}"""

            final_summary = await call_llm(title_prompt, max_tokens=500)

        return {
            "code": 0,
            "message": "success",
            "data": {
                "summary": final_summary,
                "model": model.model_id,
                "provider": model.provider,
                "chunks_processed": len(chunk_summaries),
            }
        }

    except httpx.TimeoutException:
        logger.error("LLM API timeout", exc_info=True)
        return {
            "code": 1,
            "message": "LLM服务超时，请稍后重试",
            "data": {"summary": None}
        }
    except Exception as e:
        logger.error(f"Error calling LLM: {e}", exc_info=True)
        return {
            "code": 1,
            "message": "总结服务暂时不可用",
            "data": {"summary": None}
        }
