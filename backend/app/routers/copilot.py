"""
AI Copilot 流式对话接口
支持真实LLM接入（OpenAI/DeepSeek/MiniMax/通义千问） + 新闻上下文注入
POST /api/v1/chat → SSE StreamingResponse
"""
import asyncio
import json
import os
import re
import logging
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# ═══════════════════════════════════════════════════════════════
# LLM 配置 — 从环境变量读取（支持多种 Provider）
# ═══════════════════════════════════════════════════════════════
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY",  "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE",  "https://api.openai.com/v1")
OPENAI_MODEL    = os.getenv("OPENAI_MODEL",     "gpt-3.5-turbo")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL   = os.getenv("DEEPSEEK_MODEL",   "deepseek-chat")

QIANWEN_API_KEY = os.getenv("QIANWEN_API_KEY", "")
QIANWEN_API_BASE = os.getenv("QIANWEN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QIANWEN_MODEL   = os.getenv("QIANWEN_MODEL",    "qwen-plus")

MINIMAX_API_KEY  = os.getenv("MINIMAX_API_KEY",  "")
MINIMAX_GROUP_ID = os.getenv("MINIMAX_GROUP_ID",  "")

def _detect_provider() -> str:
    """按优先级检测可用的 LLM Provider"""
    if DEEPSEEK_API_KEY:  return "deepseek"
    if QIANWEN_API_KEY:   return "qianwen"
    if MINIMAX_API_KEY:   return "minimax"
    if OPENAI_API_KEY:    return "openai"
    return "mock"


# ═══════════════════════════════════════════════════════════════
# System Prompt 模板 — 上下文感知注入
# ═══════════════════════════════════════════════════════════════
SYSTEM_PROMPT_TEMPLATE = """你是一个专业的金融投研助手AlphaTerminal，专门为中国A股投资者提供数据分析、市场解读和投资建议。

【能力范围】
- 分析大盘走势、板块轮动、资金流向
- 解读个股基本面、技术形态、公告新闻
- 解释金融术语、量化指标、投资策略
- 撰写投研笔记、风险提示

【回答原则】
1. 数据驱动：基于真实市场数据分析，不编造数据
2. 专业精准：使用专业术语但保持通俗易懂
3. 谨慎负责：提供分析但明确提示投资风险
4. 逻辑清晰：先给结论，再提供数据支撑
5. 始终以【免责声明】结尾：以上仅供参考，不构成投资建议

【当前时间】{current_time}
{context_block}
""".strip()

def _build_context_block(symbol: Optional[str], price_info: dict, news_items: list) -> str:
    """构建注入给 LLM 的上下文数据块"""
    parts = []

    if symbol:
        parts.append(f"【当前标的】{symbol}")

    if price_info:
        name  = price_info.get("name") or symbol or ""
        price = price_info.get("price")
        chg   = price_info.get("change_pct")
        if price is not None:
            arrow = "▲" if (chg or 0) >= 0 else "▼"
            parts.append(
                f"【实时行情】{name} 现价 {price:.2f} 元，"
                f"涨跌 {arrow} {abs(chg or 0):.2f}%"
            )

    if news_items:
        parts.append("【最新快讯】（按时间倒序）")
        for n in news_items[:5]:
            tag  = n.get("tag") or n.get("category") or ""
            title = n.get("title") or ""
            if title:
                parts.append(f"  [{tag}] {title}")

    if not parts:
        return ""

    return "\n\n" + "\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# LLM 流式调用（各 Provider 统一接口）
# ═══════════════════════════════════════════════════════════════

async def _llm_stream(
    provider: str,
    messages: list[dict],
) -> AsyncGenerator[str, None]:
    """
    统一的 LLM 流式调用，分发给各 Provider。
    messages: [{"role": "user"|"system"|"assistant", "content": str}, ...]
    """
    if provider == "deepseek":
        async for chunk in _call_deepseek(messages):
            yield chunk
    elif provider == "qianwen":
        async for chunk in _call_qianwen(messages):
            yield chunk
    elif provider == "minimax":
        async for chunk in _call_minimax(messages):
            yield chunk
    elif provider == "openai":
        async for chunk in _call_openai(messages):
            yield chunk
    else:
        async for chunk in _mock_stream(messages):
            yield chunk


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _call_openai(messages: list[dict]) -> AsyncGenerator[str, None]:
    import httpx
    url = f"{OPENAI_API_BASE.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       OPENAI_MODEL,
        "messages":    messages,
        "stream":      True,
        "temperature": 0.7,
        "max_tokens": 2000,
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            d = json.loads(line[6:])
                            content = (
                                d.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content", "")
                            )
                            if content:
                                yield _sse({"content": content})
                        except json.JSONDecodeError:
                            continue
    except Exception as e:
        logger.error(f"[OpenAI] {e}")
        yield _sse({"error": f"OpenAI API 调用失败: {e}"})


async def _call_deepseek(messages: list[dict]) -> AsyncGenerator[str, None]:
    import httpx
    url = f"{DEEPSEEK_API_BASE.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       DEEPSEEK_MODEL,
        "messages":    messages,
        "stream":      True,
        "temperature": 0.7,
        "max_tokens": 2000,
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            d = json.loads(line[6:])
                            content = (
                                d.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content", "")
                            )
                            if content:
                                yield _sse({"content": content})
                        except json.JSONDecodeError:
                            continue
    except Exception as e:
        logger.error(f"[DeepSeek] {e}")
        yield _sse({"error": f"DeepSeek API 调用失败: {e}"})


async def _call_qianwen(messages: list[dict]) -> AsyncGenerator[str, None]:
    import httpx
    url = f"{QIANWEN_API_BASE.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {QIANWEN_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       QIANWEN_MODEL,
        "messages":    messages,
        "stream":      True,
        "temperature": 0.7,
        "max_tokens": 2000,
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            d = json.loads(line[6:])
                            content = (
                                d.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content", "")
                            )
                            if content:
                                yield _sse({"content": content})
                        except json.JSONDecodeError:
                            continue
    except Exception as e:
        logger.error(f"[Qianwen] {e}")
        yield _sse({"error": f"通义千问 API 调用失败: {e}"})


async def _call_minimax(messages: list[dict]) -> AsyncGenerator[str, None]:
    import httpx
    url = "https://api.minimax.chat/v1/text/chatcompletion_pro"
    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       "abab6.5s-chat",
        "messages":    messages,
        "stream":      True,
        "temperature": 0.7,
        "max_tokens": 2000,
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            d = json.loads(line[6:])
                            content = (
                                d.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content", "")
                            )
                            if content:
                                yield _sse({"content": content})
                        except json.JSONDecodeError:
                            continue
    except Exception as e:
        logger.error(f"[MiniMax] {e}")
        yield _sse({"error": f"MiniMax API 调用失败: {e}"})


async def _mock_stream(messages: list[dict]) -> AsyncGenerator[str, None]:
    """Mock 流式响应（无 API Key 时使用）"""
    last_msg = messages[-1]["content"] if messages else ""
    lower = last_msg.lower()

    # 根据问题类型生成不同响应
    if any(k in lower for k in ["分析", "怎么看", "如何", "判断", "建议"]):
        output = """📊 基于您的问题，我给出以下分析思路：

**核心观点**：当前市场处于结构性震荡格局，板块分化明显。

**关键逻辑**：
1. 政策面：稳增长政策持续发力，对A股形成中期支撑
2. 资金面：北向资金流向需重点关注
3. 情绪面：题材炒作与业绩确定性之间的跷跷板效应

**操作建议**：
• 仓位管理：保持5-7成，进可攻退可守
• 方向选择：业绩确定性 + 政策催化双轮驱动
• 风险控制：设置止损位，避免追高

⚠️ **免责声明**：以上分析仅供研究参考，不构成任何投资建议。股市有风险，投资需谨慎。"""
    elif any(k in lower for k in ["涨停", "跌停", "异动", "北向", "资金"]):
        output = """📈 关于资金流向与涨跌停分析：

从近期数据来看：
• 涨停家数环比变化反映市场短线情绪
• 北向资金作为"聪明钱"值得持续跟踪
• 板块内部分化意味着选股难度加大

**解读要点**：
1. 资金大幅流入的板块通常有持续性
2. 涨停股需结合题材强度判断持续性
3. 跌停股需警惕流动性风险

⚠️ 仅供参考，投资有风险。"""
    elif any(k in lower for k in ["个股", "股票", "推荐"]):
        output = """📌 关于个股选择：

我无法给出具体买卖建议，但可以提供选股框架：

**选股维度**：
1. 基本面：业绩稳定增长、估值合理（PE/PB）
2. 行业景气：选择政策支持或业绩反转行业
3. 技术面：趋势向上、量价配合
4. 资金面：机构持仓增加、北向买入

**风险提示**：
任何股票都有风险，建议深入研究基本面后再做决策。

⚠️ 仅供参考。"""
    else:
        output = """您好！我是 AlphaTerminal 智能投研助手 🧠

我可以帮助您：
📊 分析大盘走势和市场情绪
📈 查询板块轮动和资金流向
🔍 解读个股基本和技术形态
📰 解读新闻热点和投资机会

请告诉我您想了解什么？"""

    # 流式输出
    for i in range(0, len(output), 8):
        chunk = output[i:i + 8]
        yield _sse({"content": chunk})
        await asyncio.sleep(0.03)

    yield _sse({"content": "", "done": True})


# ═══════════════════════════════════════════════════════════════
# 上下文注入：查询标的实时价格 + 最新新闻
# ═══════════════════════════════════════════════════════════════

def _fetch_price_context(symbol: Optional[str]) -> dict:
    """查询标的的实时价格信息"""
    if not symbol:
        return {}
    try:
        from app.db.database import _get_conn
        conn = _get_conn()
        # 尝试直接匹配
        row = conn.execute(
            "SELECT name, price, change_pct FROM market_all_stocks WHERE symbol=? OR symbol=? OR symbol=? LIMIT 1",
            (symbol, f"sh{symbol}", f"sz{symbol}")
        ).fetchone()
        conn.close()
        if row:
            return {"name": row[0] or "", "price": float(row[1] or 0), "change_pct": float(row[2] or 0)}
    except Exception as e:
        logger.warning(f"[Copilot] price lookup error: {e}")
    return {}


def _fetch_latest_news(limit: int = 5) -> list:
    """获取最新快讯"""
    try:
        from app.db.database import _get_conn
        conn = _get_conn()
        rows = conn.execute(
            "SELECT title, tag FROM news_cache ORDER BY ctime DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return [{"title": r[0], "tag": r[1]} for r in rows]
    except Exception as e:
        logger.warning(f"[Copilot] news lookup error: {e}")
    return []


# ═══════════════════════════════════════════════════════════════
# SSE 流式对话端点
# ═══════════════════════════════════════════════════════════════

@router.post("/chat")
async def copilot_chat(request: Request):
    """
    SSE 流式对话接口

    请求体：
      prompt  : str  用户提问
      symbol? : str  当前标的（可选，用于上下文注入）

    上下文注入流程：
      1. 读取 symbol → 查询 market_all_stocks 实时价格
      2. 查询 news_cache 最新 N 条快讯
      3. 拼接 SYSTEM_PROMPT_TEMPLATE（含 context_block）
      4. 将完整 messages 发送给 LLM（流式 SSE）
    """
    body = await request.json()
    prompt = (body.get("prompt") or "").strip()
    symbol = (body.get("symbol") or "").strip() or None

    if not prompt:
        return StreamingResponse(
            iter([_sse({"error": "prompt 不能为空"})]),
            media_type="text/event-stream",
        )

    provider = _detect_provider()

    # ── 构建上下文注入 ────────────────────────────────────────
    # 前端可传 context 字段（格式化的市场/板块/情绪数据），补充后端实时数据
    frontend_context = (body.get("context") or "").strip()
    price_info = _fetch_price_context(symbol)
    news_items = _fetch_latest_news(limit=5)
    context_block = _build_context_block(symbol, price_info, news_items)
    
    # 合并：前端上下文（更丰富）+ 后端上下文（实时行情+快讯）
    if frontend_context:
        context_block = f"{frontend_context}\n{context_block}"

    from datetime import datetime
    current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")

    system_msg = SYSTEM_PROMPT_TEMPLATE.format(
        current_time=current_time,
        context_block=context_block,
    )

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user",   "content": prompt},
    ]

    logger.info(
        f"[Copilot] provider={provider} symbol={symbol or '-'} "
        f"prompt='{prompt[:40]}...' context_blocks={len(context_block)}"
    )

    return StreamingResponse(
        _llm_stream(provider, messages),
        media_type="text/event-stream",
        headers={
            "Cache-Control":   "no-cache",
            "Connection":       "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/status")
async def copilot_status():
    """Copilot LLM 配置状态"""
    provider = _detect_provider()
    return {
        "provider":  provider,
        "has_key":  bool(OPENAI_API_KEY or DEEPSEEK_API_KEY or QIANWEN_API_KEY or MINIMAX_API_KEY),
        "openai":   bool(OPENAI_API_KEY),
        "deepseek": bool(DEEPSEEK_API_KEY),
        "qianwen":  bool(QIANWEN_API_KEY),
        "minimax":  bool(MINIMAX_API_KEY),
        "version":  "1.1.0",
    }
