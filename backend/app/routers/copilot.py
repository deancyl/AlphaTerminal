"""
AI Copilot 流式对话接口 - Phase 6 增强版
支持真实LLM接入 + 新闻上下文分析
POST /api/v1/chat → SSE StreamingResponse
"""
import asyncio
import json
import os
import logging
from typing import AsyncGenerator
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter()

CHUNK_SPEED_CPS = 5
IDLE_CHUNK_DELAY = 0.05

# LLM配置（从环境变量读取）
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_GROUP_ID = os.getenv("MINIMAX_GROUP_ID", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# 是否启用真实LLM
USE_REAL_LLM = bool(MINIMAX_API_KEY or OPENAI_API_KEY)


async def call_minimax_llm(prompt: str, context: str = "") -> AsyncGenerator[str, None]:
    """调用 MiniMax LLM API (流式)"""
    import httpx
    
    url = "https://api.minimax.chat/v1/text/chatcompletion_pro"
    
    # 构建系统提示词
    system_prompt = """你是一个专业的金融投研助手AlphaTerminal，专门为中国A股投资者提供数据分析、市场解读和投资建议。

你的特点：
1. 数据驱动：基于真实市场数据进行客观分析
2. 专业精准：使用专业术语但保持易懂
3. 谨慎负责：提供分析但始终强调投资风险
4. 逻辑清晰：先给出结论，再提供支撑数据

当前时间：2026年4月

请用中文回答，保持专业但不要过于正式。"""
    
    # 构建用户消息
    user_message = prompt
    if context:
        user_message = f"""参考数据：
{context}

---

用户问题：{prompt}"""

    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "abab6.5s-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "stream": True,
        "temperature": 0.7,
        "max_tokens": 2000
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                async for line in response.aiter_lines():
                    if line.strip():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"
                                break
                            try:
                                data = json.loads(data_str)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield f"data: {json.dumps({'content': content, 'done': False})}\n\n"
                            except:
                                continue
    except Exception as e:
        logger.error(f"MiniMax API error: {e}")
        yield f"data: {json.dumps({'error': f'LLM调用失败: {str(e)}', 'done': True})}\n\n"


async def call_openai_llm(prompt: str, context: str = "") -> AsyncGenerator[str, None]:
    """调用 OpenAI API (流式)"""
    import httpx
    
    url = "https://api.openai.com/v1/chat/completions"
    
    system_prompt = """你是一个专业的金融投研助手AlphaTerminal，专门为中国A股投资者提供数据分析、市场解读和投资建议。

当前时间：2026年4月。请用中文回答，保持专业但不要过于正式。"""
    
    user_message = prompt
    if context:
        user_message = f"""参考数据：\n{context}\n\n---\n用户问题：{prompt}"""
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "stream": True,
        "temperature": 0.7,
        "max_tokens": 2000
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                async for line in response.aiter_lines():
                    if line.strip():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"
                                break
                            try:
                                data = json.loads(data_str)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield f"data: {json.dumps({'content': content, 'done': False})}\n\n"
                            except:
                                continue
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        yield f"data: {json.dumps({'error': f'LLM调用失败: {str(e)}', 'done': True})}\n\n"


async def mock_llm_stream(prompt: str, context: str = "") -> AsyncGenerator[str, None]:
    """
    Mock LLM流式输出（无真实API时使用）
    根据上下文动态生成更专业的响应
    """
    # 分析上下文，判断用户意图
    has_market = "上证" in context or "深证" in context or "沪深300" in context
    has_news = "新闻" in context or "快讯" in context
    
    # 根据问题类型生成不同响应
    user_lower = prompt.lower()
    
    if any(k in user_lower for k in ["分析", "怎么看", "如何", "判断", "建议"]):
        # 分析类问题
        if has_market:
            output = """📊 基于当前市场数据分析：

**整体判断**：市场目前处于震荡整理格局，结构性分化明显。

**关键观察**：
1. 权重指数表现相对稳健，题材股活跃度提升
2. 成交额维持在较高水平，市场交投活跃
3. 板块轮动加快，资金寻找低位补涨机会

**操作建议**：
• 仓位建议：保持5-7成仓位，进可攻退可守
• 方向关注：关注业绩确定性强的白马股，以及政策催化的科技成长方向
• 风险提示：美联储政策不确定性仍存，注意控制仓位

⚠️ 免责声明：以上分析仅供参考，不构成投资建议。"""
        elif has_news:
            output = """📰 结合近期新闻热点分析：

从消息面来看，市场关注焦点集中在：
1. 产业政策动态（新质生产力、数字经济）
2. 业绩预告密集期，关注盈利超预期方向
3. 流动性环境，央行公开市场操作

**新闻解读**：
近期多条利好消息提振市场情绪，但需注意部分题材已处于相对高位，追高需谨慎。

**策略建议**：
• 关注低位启动的补涨机会
• 重视业绩+估值的匹配度
• 避免盲目追涨热点

⚠️ 仅供参考，投资有风险。"""
        else:
            output = """收到您的分析请求。

由于当前上下文数据有限，我给出以下通用建议：

**市场展望**：
当前A股处于低位震荡期，政策底已经显现，但市场底还需要时间确认。

**投资思路**：
1. 立足基本面，寻找业绩稳定、估值合理的标的
2. 关注政策方向带来的结构性机会
3. 控制仓位，不要盲目追涨杀跌

如需更精准的分析，请提供具体关注的股票或板块，我可以结合实时数据给出更详细的建议。

⚠️ 免责声明：以上仅供参考。"""
    
    elif any(k in user_lower for k in ["涨停", "跌停", "异动", "北向", "资金"]):
        # 资金/涨停类问题
        output = """📈 关于资金流向和涨跌停分析：

从今日数据来看：
• 涨停家数环比增加，市场情绪偏暖
• 跌停家数维持在较低水平
• 北向资金呈净流入态势

**资金动向解读**：
1. 外资买入有助于稳定市场信心
2. 主力资金近期关注消费和科技方向
3. 杠杆资金活跃度有所提升

**风险提示**：
涨跌停数据仅反映当日情绪，不代表后续走势。投资需结合基本面判断。

⚠️ 仅供参考，股市有风险。"""
    
    elif any(k in user_lower for k in ["板块", "行业", "概念"]):
        # 板块类问题
        output = """🔥 板块分析：

近期板块轮动特征明显：
1. 科技成长：人工智能、半导体反复活跃
2. 消费复苏：白酒、食品饮料底部企稳
3. 周期板块：化工、有色金属分化明显

**操作建议**：
• 追涨需谨慎，回调可考虑分批布局
• 关注板块龙头股的持续性
• 注意高低切换节奏

⚠️ 仅供参考。"""
    
    elif any(k in user_lower for k in ["个股", "股票", "推荐"]):
        # 个股推荐问题（不给出具体推荐）
        output = """📌 关于个股选择：

作为AI助手，我无法给出具体买卖建议，但可以提供选股思路：

**选股维度**：
1. 基本面：业绩稳定增长、估值合理
2. 行业景气度：选择朝阳行业或反转行业
3. 技术面：趋势向上、量价配合
4. 资金面：主力资金持续流入

**风险提示**：
任何股票都有风险，建议深入研究后再做决策。分散投资、控制仓位是降低风险的有效方法。

如有具体股票需要分析基本面，我可以帮您查询相关数据。"""

    else:
        # 通用对话
        if context:
            output = f"""收到您的提问，我已了解您提供的背景信息：

{context}

基于这些数据，我来回答您的问题：{prompt}

从专业角度，我的分析建议是：

1. **保持客观**：投资决策需要基于充分的研究和数据
2. **控制风险**：永远不要满仓操作，留有余地
3. **长期视角**：忽略短期波动，关注长期价值

如需更深入的分析，请告诉我具体想了解的方面。

⚠️ 免责声明：以上仅供参考。"""
        else:
            output = """你好！我是 AlphaTerminal 智能投研助手。

我可以帮助你：
📊 分析大盘走势和市场情绪
📈 查询板块轮动和资金流向
🔍 搜索和分析个股数据
📰 解读新闻热点和投资机会

请告诉我你需要什么帮助？"""

    # 流式输出
    thinking_msg = "🧠 正在分析您的问题...\n\n"
    for i in range(0, len(thinking_msg), CHUNK_SPEED_CPS):
        chunk = thinking_msg[i:i + CHUNK_SPEED_CPS]
        payload = json.dumps({"content": chunk, "done": False})
        yield f"data: {payload}\n\n"
        await asyncio.sleep(IDLE_CHUNK_DELAY * 2)

    # 主输出
    await asyncio.sleep(0.2)
    for i in range(0, len(output), CHUNK_SPEED_CPS):
        chunk = output[i:i + CHUNK_SPEED_CPS]
        payload = json.dumps({"content": chunk, "done": False})
        yield f"data: {payload}\n\n"
        await asyncio.sleep(IDLE_CHUNK_DELAY)

    yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"


async def enhanced_llm_stream(prompt: str, context: str = "") -> AsyncGenerator[str, None]:
    """
    增强版LLM流式输出（根据可用API选择）
    """
    # 获取新闻数据作为额外上下文
    news_context = ""
    try:
        from app.services.news_engine import get_cached_news
        news = get_cached_news(limit=10)
        if news and len(news) > 0:
            # 提取最新5条新闻作为上下文
            recent_news = news[:5]
            news_context = "\n📰 最新快讯：\n"
            for n in recent_news:
                news_context += f"- {n.get('title', '')[:60]} ({n.get('tag', '')})\n"
    except Exception as e:
        logger.warning(f"Failed to get news for LLM context: {e}")

    # 合并所有上下文
    full_context = context
    if news_context:
        full_context += "\n" + news_context

    # 根据配置选择调用方式
    if MINIMAX_API_KEY:
        async for chunk in call_minimax_llm(prompt, full_context):
            yield chunk
    elif OPENAI_API_KEY:
        async for chunk in call_openai_llm(prompt, full_context):
            yield chunk
    else:
        # 无API key，使用增强版mock
        async for chunk in mock_llm_stream(prompt, full_context):
            yield chunk


@router.post("/chat")
async def copilot_chat(request: Request):
    """
    SSE 流式对话接口 - 增强版
    body: { prompt: str, context?: str }
    """
    body = await request.json()
    prompt   = body.get("prompt", "").strip()
    context  = body.get("context", "").strip()

    if not prompt:
        return StreamingResponse(
            iter([f"data: {json.dumps({'error': 'prompt 不能为空'})}\n\n"]),
            media_type="text/event-stream",
        )

    # 检查LLM配置状态
    llm_status = "mock"
    if MINIMAX_API_KEY:
        llm_status = "minimax"
    elif OPENAI_API_KEY:
        llm_status = "openai"
    
    logger.info(f"[Copilot] prompt='{prompt[:50]}...' context_len={len(context)} llm={llm_status}")

    return StreamingResponse(
        enhanced_llm_stream(prompt, context),
        media_type="text/event-stream",
        headers={
            "Cache-Control":  "no-cache",
            "Connection":      "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/status")
async def copilot_status():
    """Copilot状态检查"""
    return {
        "llm_provider": "minimax" if MINIMAX_API_KEY else ("openai" if OPENAI_API_KEY else "mock"),
        "enabled": USE_REAL_LLM,
        "version": "1.0.0"
    }