"""
AI Copilot 流式对话接口
支持真实LLM接入（OpenAI/DeepSeek/MiniMax/通义千问） + 新闻上下文注入
POST /api/v1/chat → SSE StreamingResponse

Wave 2 Integration:
- Multi-model configuration with hot-reload
- Session management with config binding
- Token tracking with cost calculation
- Concurrency limiting per model
"""
import asyncio
import json
import os
import re
import uuid
import logging
import time
from datetime import datetime
from typing import AsyncGenerator, Optional, List, Dict, Any
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.services.model_config_service import get_model_config_service
from app.services.session_manager import get_session_manager
from app.services.token_tracking_service import get_token_tracking_service
from app.services.concurrency_limiter import get_concurrency_limiter
from app.utils.error_sanitizer import sanitize_error
from app.utils.token_counter import count_tokens
from app.config.settings import get_settings

OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
QIANWEN_API_KEY  = os.getenv("QIANWEN_API_KEY", "")
MINIMAX_API_KEY  = os.getenv("MINIMAX_API_KEY", "")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# 添加控制台 handler（如果还没有）
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(name)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
router = APIRouter()

def _mask_key(key: str) -> str:
    """掩码处理 API Key"""
    if not key:
        return ""
    if len(key) <= 8:
        return key
    return f"{key[:6]}...{key[-4:]}"

# ═══════════════════════════════════════════════════════════════
# LLM 配置 — 优先级：数据库 > 环境变量 > 默认值
# ═══════════════════════════════════════════════════════════════

def _get_llm_config(provider: str, model_id: str = None) -> dict:
    """
    获取指定 Provider 的完整配置（使用 ModelConfigService hot-reload）。
    """
    model_svc = get_model_config_service()
    model = model_svc.get_model(provider, model_id)
    
    if model and model.api_key:
        return {
            "api_key": model.api_key,
            "base_url": model.base_url,
            "model": model.model_id,
            "max_concurrent": model.max_concurrent,
        }
    
    defaults = {
        "deepseek": {"api_key": os.getenv("DEEPSEEK_API_KEY",""), "base_url": os.getenv("DEEPSEEK_API_BASE","https://api.deepseek.com"), "model": os.getenv("DEEPSEEK_MODEL","deepseek-chat")},
        "qianwen":  {"api_key": os.getenv("QIANWEN_API_KEY",""),  "base_url": os.getenv("QIANWEN_API_BASE","https://dashscope.aliyuncs.com/compatible-mode/v1"), "model": os.getenv("QIANWEN_MODEL","qwen-plus")},
        "openai":   {"api_key": os.getenv("OPENAI_API_KEY",""),  "base_url": os.getenv("OPENAI_API_BASE","https://api.openai.com/v1"), "model": os.getenv("OPENAI_MODEL","gpt-3.5-turbo")},
        "siliconflow": {"api_key": os.getenv("SILICONFLOW_API_KEY",""), "base_url": os.getenv("SILICONFLOW_API_BASE","https://api.siliconflow.cn/v1"), "model": os.getenv("SILICONFLOW_MODEL","deepseek-ai/DeepSeek-V3")},
        "opencode": {"api_key": os.getenv("OPENCODE_API_KEY",""), "base_url": os.getenv("OPENCODE_API_BASE","https://api.opencode.ai/v1"), "model": os.getenv("OPENCODE_MODEL","opencode-chat")},
        "opencode_go": {"api_key": os.getenv("OPENCODE_API_KEY",""), "base_url": os.getenv("OPENCODE_API_BASE","https://opencode.ai/zen/go/v1"), "model": os.getenv("OPENCODE_MODEL","minimax-m2.7")},
        "opencode_zen": {"api_key": os.getenv("OPENCODE_API_KEY",""), "base_url": os.getenv("OPENCODE_API_BASE","https://opencode.ai/zen/v1"), "model": os.getenv("OPENCODE_MODEL","minimax-m2.5-free")},
        "minimax": {"api_key": os.getenv("MINIMAX_API_KEY",""), "base_url": "https://api.minimax.chat/v1", "model": "abab6.5s-chat"},
        "kimi": {"api_key": os.getenv("KIMI_API_KEY",""), "base_url": os.getenv("KIMI_API_BASE","https://api.moonshot.cn/v1"), "model": os.getenv("KIMI_MODEL","moonshot-v1-8k")},
    }
    return defaults.get(provider, {})

def _detect_provider() -> str:
    """按优先级检测可用的 LLM Provider（优先使用数据库配置）"""
    for p in ["deepseek", "qianwen", "openai", "siliconflow", "opencode", "opencode_go", "opencode_zen", "minimax", "kimi"]:
        if _get_llm_config(p).get("api_key"):
            return p
    return "mock"


def _get_httpx_timeout():
    """Get httpx timeout configuration from settings."""
    import httpx
    settings = get_settings()
    return httpx.Timeout(
        connect=settings.COPILOT_CONNECT_TIMEOUT_SECONDS,
        read=settings.COPILOT_STREAM_TIMEOUT_SECONDS,
        write=settings.COPILOT_TIMEOUT_SECONDS,
        pool=settings.COPILOT_TIMEOUT_SECONDS,
    )


# ═══════════════════════════════════════════════════════════════
# System Prompt 模板 — 上下文感知注入
# ═══════════════════════════════════════════════════════════════
SYSTEM_PROMPT_TEMPLATE = """你是一位顶级买方机构（Top-tier Buy-side）的首席金融分析师，名为 AlphaTerminal Copilot，专门为中国A股投资者提供投研级深度分析。

【角色定位】
- 你拥有 15 年+ 卖方/买方投研经验，风格严谨、数据驱动、逻辑清晰
- 你熟悉 A 股/港股/美股市场，擅长宏观策略、行业比较、个股估值、技术面与基本面共振分析
- 你的输出直接可用于机构投研报告，读者可一键复制粘贴至"微信公众号/Gemini 研究笔记"等专业排版模板

【输出格式规范（严格遵循）】
1. **Markdown 排版**：使用 `#` 多级标题、`-` 列表、`**加粗**` 强调、`|表格|` 展示数据
2. **标准研报结构**（根据场景灵活裁剪）：
   ```
   ## 📌 核心观点
   （一句话结论，30字以内）

   ## 🔍 逻辑推演
   （分 2-4 点展开，每点含数据/事实支撑）

   ## 📊 数据印证
   | 指标 | 当前值 | 历史分位 | 信号 |
   |------|--------|----------|------|
   （至少 3 行关键数据，用表格展示）

   ## ⚠️ 风险提示
   （列出 2-3 条关键风险，按影响程度排序）

   > 免责声明：以上分析仅供研究参考，不构成任何投资建议。市场有风险，投资需谨慎。
   ```
3. **禁止**：禁止使用 "作为一个AI" 等套话，禁止给出具体买入/卖出价位，禁止编造数据

【回答原则】
- 数据驱动：基于用户提供的市场数据进行分析，不凭空捏造
- 专业精准：使用金融专业术语，同时确保非专业人士也能理解
- 客观中立：多空观点平衡呈现，不做单边判断
- 结构清晰：先给结论，再展开论证，最后附风险提示
- 排版精美：所有输出必须是可直接发布的专业研报格式

【当前时间】{current_time}
{context_block}
""".strip()

def _format_price_info(price_info: dict, symbol: Optional[str]) -> List[str]:
    """格式化实时行情信息"""
    parts = []
    name = price_info.get("name") or symbol or ""
    price = price_info.get("price")
    chg = price_info.get("change_pct")
    if price is not None:
        arrow = "▲" if (chg or 0) >= 0 else "▼"
        parts.append(
            f"【实时行情】{name} 现价 {price:.2f} 元，"
            f"涨跌 {arrow} {abs(chg or 0):.2f}%"
        )
    return parts


def _format_valuation(valuation_data: dict) -> List[str]:
    """格式化市场估值数据"""
    parts = []
    pe_ttm = valuation_data.get("pe_ttm")
    pb = valuation_data.get("pb")
    ret_ytd = valuation_data.get("returns_ytd")
    pe_pct = valuation_data.get("pe_percentile")
    pb_pct = valuation_data.get("pb_percentile")
    
    if pe_ttm is not None:
        pe_str = f"{pe_ttm:.2f}" + (f"（历史分位：{pe_pct:.1f}%）" if pe_pct else "")
        parts.append(f"【市场估值】当前 PE_TTM：{pe_str}")
    if pb is not None:
        pb_str = f"{pb:.2f}" + (f"（历史分位：{pb_pct:.1f}%）" if pb_pct else "")
        parts.append(f"当前 PB：{pb_str}")
    if ret_ytd is not None:
        arrow_ytd = "▲" if ret_ytd >= 0 else "▼"
        parts.append(f"年初至今收益率：{arrow_ytd}{abs(ret_ytd):.2f}%")
    return parts


def _format_portfolio(portfolio_data: dict) -> List[str]:
    """格式化投资组合数据"""
    parts = []
    portfolio_name = portfolio_data.get("name", "")
    total_value = portfolio_data.get("total_value", 0)
    total_pnl = portfolio_data.get("total_pnl", 0)
    positions = portfolio_data.get("positions", [])
    
    parts.append(f"【投资组合】{portfolio_name}")
    parts.append(f"  总市值：¥{total_value:,.2f}")
    if total_pnl >= 0:
        parts.append(f"  总盈亏：+¥{total_pnl:,.2f}（盈利）")
    else:
        parts.append(f"  总盈亏：-¥{abs(total_pnl):,.2f}（亏损）")
    
    if positions:
        parts.append(f"  持仓明细（共{len(positions)}只）：")
        for pos in positions[:10]:
            pnl = pos.get("unrealized_pnl", 0)
            arrow = "▲" if pnl >= 0 else "▼"
            parts.append(
                f"    {pos.get('symbol', '')} {pos.get('name', '')}: "
                f"{pos.get('shares', 0)}股，成本¥{pos.get('avg_cost', 0):.2f}，"
                f"现价¥{pos.get('current_price', 0):.2f}，"
                f"市值¥{pos.get('market_value', 0):,.2f}，"
                f"盈亏{arrow}{abs(pos.get('unrealized_pnl_pct', 0)):.2f}%"
            )
    return parts


def _format_historical(historical_data: dict) -> List[str]:
    """格式化历史K线数据和技术指标"""
    parts = []
    data_points = historical_data.get("data", [])
    if not data_points or len(data_points) < 5:
        return parts
    
    symbol_hist = historical_data.get("symbol", "")
    period = historical_data.get("period", "daily")
    parts.append(f"【历史行情】{symbol_hist} ({period})")
    
    latest = data_points[-1]
    latest_close = latest.get("close", 0)
    
    # MA5
    ma5 = sum(d.get("close", 0) for d in data_points[-5:]) / 5
    parts.append(f"  MA5: ¥{ma5:.2f} (当前{'高于' if latest_close > ma5 else '低于'}MA5)")
    
    # MA20
    if len(data_points) >= 20:
        ma20 = sum(d.get("close", 0) for d in data_points[-20:]) / 20
        parts.append(f"  MA20: ¥{ma20:.2f} (当前{'高于' if latest_close > ma20 else '低于'}MA20)")
    
    # 最新涨跌
    prev_close = data_points[-2].get("close", 0)
    if prev_close > 0:
        change_pct = (latest_close - prev_close) / prev_close * 100
        arrow = "▲" if change_pct >= 0 else "▼"
        parts.append(f"  最新涨跌: {arrow}{abs(change_pct):.2f}%")
    
    # 近期最高最低价
    recent_high = max(d.get("high", 0) for d in data_points[-20:])
    recent_low = min(d.get("low", float('inf')) for d in data_points[-20:])
    if recent_low < float('inf'):
        parts.append(f"  20日最高: ¥{recent_high:.2f}, 最低: ¥{recent_low:.2f}")
    
    return parts


def _format_news(news_items: list) -> List[str]:
    """格式化新闻快讯"""
    parts = ["【最新快讯】（按时间倒序）"]
    for n in news_items[:5]:
        tag = n.get("tag") or n.get("category") or ""
        title = n.get("title") or ""
        if title:
            parts.append(f"  [{tag}] {title}")
    return parts


def _build_context_block(symbol: Optional[str], price_info: dict, news_items: list, valuation_data: dict, 
                         portfolio_data: dict = None, historical_data: dict = None) -> str:
    """构建注入给 LLM 的上下文数据块"""
    parts = []
    
    if symbol:
        parts.append(f"【当前标的】{symbol}")
    
    if price_info:
        parts.extend(_format_price_info(price_info, symbol))
    
    if valuation_data:
        parts.extend(_format_valuation(valuation_data))
    
    if portfolio_data:
        parts.extend(_format_portfolio(portfolio_data))
    
    if historical_data:
        parts.extend(_format_historical(historical_data))
    
    if news_items:
        parts.extend(_format_news(news_items))
    
    if not parts:
        return ""
    
    return "\n\n" + "\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# LLM 流式调用（各 Provider 统一接口）
# ═══════════════════════════════════════════════════════════════

async def _llm_stream(
    provider: str,
    messages: list[dict],
    model_override: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    统一的 LLM 流式调用，分发给各 Provider。
    messages: [{"role": "user"|"system"|"assistant", "content": str}, ...]
    """
    if provider == "deepseek":
        async for chunk in _call_deepseek(messages, model_override):
            yield chunk
    elif provider == "qianwen":
        async for chunk in _call_qianwen(messages, model_override):
            yield chunk
    elif provider == "minimax":
        async for chunk in _call_minimax(messages):
            yield chunk
    elif provider == "openai":
        async for chunk in _call_openai(messages, model_override):
            yield chunk
    elif provider == "siliconflow":
        async for chunk in _call_siliconflow(messages, model_override):
            yield chunk
    elif provider == "opencode":
        async for chunk in _call_opencode(messages, model_override):
            yield chunk
    elif provider == "opencode_go":
        async for chunk in _call_opencode_go(messages, model_override):
            yield chunk
    elif provider == "opencode_zen":
        async for chunk in _call_opencode_zen(messages, model_override):
            yield chunk
    elif provider == "kimi":
        async for chunk in _call_kimi(messages, model_override):
            yield chunk
    else:
        async for chunk in _mock_stream(messages):
            yield chunk


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _call_openai(messages: list[dict], model_override: str | None = None) -> AsyncGenerator[str, None]:
    import httpx
    cfg = _get_llm_config("openai")
    url = f"{(cfg['base_url'] or 'https://api.openai.com/v1').rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       model_override or cfg.get("model") or "gpt-3.5-turbo",
        "messages":    messages,
        "stream":      True,
        "temperature": 0.7,
        "max_tokens": 2000,
    }
    try:
        async with httpx.AsyncClient(timeout=_get_httpx_timeout()) as client:
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
        yield _sse({"error": sanitize_error(e, provider="openai")})


async def _call_deepseek(messages: list[dict], model_override: str | None = None) -> AsyncGenerator[str, None]:
    import httpx
    cfg = _get_llm_config("deepseek")
    url = f"{(cfg['base_url'] or 'https://api.deepseek.com').rstrip('/')}/chat/completions"
    logger.warning(f"[DeepSeek] 调用配置：base_url={cfg.get('base_url')}, model={cfg.get('model')}, url={url}, api_key_masked={_mask_key(cfg.get('api_key', ''))}")
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       model_override or cfg.get("model") or "deepseek-chat",
        "messages":    messages,
        "stream":      True,
        "temperature": 0.7,
        "max_tokens": 8192,
    }
    try:
        async with httpx.AsyncClient(timeout=_get_httpx_timeout()) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            d = json.loads(line[6:])
                            delta = d.get("choices", [{}])[0].get("delta", {})
                            # DeepSeek R1 思维链：reasoning_content → 单独传递
                            reasoning = delta.get("reasoning_content", "")
                            content = delta.get("content", "")
                            if reasoning:
                                yield _sse({"reasoning": reasoning})
                            if content:
                                yield _sse({"content": content})
                        except json.JSONDecodeError:
                            continue
    except Exception as e:
        yield _sse({"error": sanitize_error(e, provider="deepseek")})


async def _call_qianwen(messages: list[dict], model_override: str | None = None) -> AsyncGenerator[str, None]:
    import httpx
    cfg = _get_llm_config("qianwen")
    url = f"{(cfg['base_url'] or 'https://dashscope.aliyuncs.com/compatible-mode/v1').rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       model_override or cfg.get("model") or "qwen-plus",
        "messages":    messages,
        "stream":      True,
        "temperature": 0.7,
        "max_tokens": 2000,
    }
    try:
        async with httpx.AsyncClient(timeout=_get_httpx_timeout()) as client:
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
        yield _sse({"error": sanitize_error(e, provider="qianwen")})


async def _call_minimax(messages: list[dict], model_override: str | None = None) -> AsyncGenerator[str, None]:
    import httpx
    cfg = _get_llm_config("minimax")
    url = f"{cfg['base_url']}/text/chatcompletion_pro"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       model_override or cfg.get("model") or "abab6.5s-chat",
        "messages":    messages,
        "stream":      True,
        "temperature": 0.7,
        "max_tokens": 2000,
    }
    try:
        async with httpx.AsyncClient(timeout=_get_httpx_timeout()) as client:
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
        yield _sse({"error": sanitize_error(e, provider="minimax")})


async def _call_siliconflow(messages: list[dict], model_override: str | None = None) -> AsyncGenerator[str, None]:
    """硅基流动 API 调用 - 兼容 OpenAI 格式"""
    import httpx
    cfg = _get_llm_config("siliconflow")
    url = f"{(cfg['base_url'] or 'https://api.siliconflow.cn/v1').rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       model_override or cfg.get("model") or "deepseek-ai/DeepSeek-V3",
        "messages":    messages,
        "stream":      True,
        "temperature": 0.7,
        "max_tokens":  4096,
    }
    try:
        async with httpx.AsyncClient(timeout=_get_httpx_timeout()) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            d = json.loads(line[6:])
                            delta = d.get("choices", [{}])[0].get("delta", {})
                            # 硅基流动可能返回 reasoning_content（思维链）
                            reasoning = delta.get("reasoning_content", "")
                            content = delta.get("content", "")
                            if reasoning:
                                yield _sse({"reasoning": reasoning})
                            if content:
                                yield _sse({"content": content})
                        except json.JSONDecodeError:
                            continue
    except Exception as e:
        yield _sse({"error": sanitize_error(e, provider="siliconflow")})


async def _call_opencode(messages: list[dict], model_override: str | None = None) -> AsyncGenerator[str, None]:
    """OpenCode API 调用 - 标准 OpenAI 兼容接口"""
    import httpx
    cfg = _get_llm_config("opencode")
    url = f"{(cfg['base_url'] or 'https://api.opencode.ai/v1').rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       model_override or cfg.get("model") or "opencode-chat",
        "messages":    messages,
        "stream":      True,
        "temperature": 0.7,
        "max_tokens":  4096,
    }
    try:
        async with httpx.AsyncClient(timeout=_get_httpx_timeout()) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            d = json.loads(line[6:])
                            delta = d.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield _sse({"content": content})
                        except json.JSONDecodeError:
                            continue
    except Exception as e:
        yield _sse({"error": sanitize_error(e, provider="opencode")})


async def _call_opencode_go(messages: list[dict], model_override: str | None = None) -> AsyncGenerator[str, None]:
    """OpenCode Go API 调用 - 订阅制开源模型服务"""
    import httpx
    cfg = _get_llm_config("opencode_go")
    url = f"{(cfg['base_url'] or 'https://opencode.ai/zen/go/v1').rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       model_override or cfg.get("model") or "minimax-m2.7",
        "messages":    messages,
        "stream":      True,
        "temperature": 0.7,
        "max_tokens":  4096,
    }
    try:
        async with httpx.AsyncClient(timeout=_get_httpx_timeout()) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            d = json.loads(line[6:])
                            delta = d.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield _sse({"content": content})
                        except json.JSONDecodeError:
                            continue
    except Exception as e:
        yield _sse({"error": sanitize_error(e, provider="opencode_go")})


async def _call_opencode_zen(messages: list[dict], model_override: str | None = None) -> AsyncGenerator[str, None]:
    """OpenCode Zen API 调用 - 精选模型付费网关"""
    import httpx
    cfg = _get_llm_config("opencode_zen")
    # Zen 使用 /chat/completions 端点（OpenAI兼容格式）
    url = f"{(cfg['base_url'] or 'https://opencode.ai/zen/v1').rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       model_override or cfg.get("model") or "minimax-m2.5-free",
        "messages":    messages,
        "stream":      True,
        "temperature": 0.7,
        "max_tokens":  4096,
    }
    try:
        async with httpx.AsyncClient(timeout=_get_httpx_timeout()) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            d = json.loads(line[6:])
                            delta = d.get("choices", [{}])[0].get("delta", {})
                            # OpenCode Zen (minimax) 可能返回 reasoning 而不是 content
                            content = delta.get("content") or delta.get("reasoning", "")
                            if content:
                                yield _sse({"content": content})
                        except json.JSONDecodeError:
                            continue
    except Exception as e:
        yield _sse({"error": sanitize_error(e, provider="opencode_zen")})


async def _call_kimi(messages: list[dict], model_override: str | None = None) -> AsyncGenerator[str, None]:
    """Kimi (Moonshot) API 调用 - OpenAI 兼容格式"""
    import httpx
    cfg = _get_llm_config("kimi")
    url = f"{(cfg['base_url'] or 'https://api.moonshot.cn/v1').rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       model_override or cfg.get("model") or "moonshot-v1-8k",
        "messages":    messages,
        "stream":      True,
        "temperature": 0.7,
        "max_tokens":  4096,
    }
    try:
        async with httpx.AsyncClient(timeout=_get_httpx_timeout()) as client:
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
        yield _sse({"error": sanitize_error(e, provider="kimi")})


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


def _fetch_valuation_data(symbol: Optional[str]) -> dict:
    """获取市场估值数据（PE_TTM、PB、历史分位、YTD收益率）"""
    try:
        # 从 market_quote_detail 获取大盘指数（如上证指数 sh000001）的估值
        # 优先使用 sh000001 作为大盘基准
        index_sym = symbol.upper() if symbol else None
        if not index_sym:
            index_sym = "sh000001"
        # 去掉前缀以匹配 market_quote_detail 的 normalize 逻辑
        sym_clean = index_sym.lower().replace("sh", "").replace("sz", "")

        # 调用 market.py 的 quote_detail 端点获取估值
        from app.db import get_latest_prices
        from app.services.quote_source import get_quote_with_fallback

        db_sym = sym_clean  # market_data_realtime 存无前缀纯数字
        rows = get_latest_prices([db_sym]) if callable(get_latest_prices) else []
        quote_data = get_quote_with_fallback(index_sym) if index_sym else {}

        # pe_tbm / pb 从腾讯/东财/新浪多源fallback获取
        pe_ttm = quote_data.get("pe_ttm")
        pb     = quote_data.get("pb")

        return {
            "pe_ttm":        float(pe_ttm) if pe_ttm not in (None, 0, '-', '') else None,
            "pb":            float(pb)     if pb     not in (None, 0, '-', '') else None,
            "pe_percentile": None,   # 需要历史PE数据计算，后续接入 akshare 或 tushare
            "pb_percentile": None,   # 同上
            "returns_ytd":   None,   # YTD收益率需要历史数据计算
        }
    except Exception as e:
        logger.warning(f"[Copilot] valuation lookup error: {e}")
    return {"pe_ttm": None, "pb": None, "pe_percentile": None, "pb_percentile": None, "returns_ytd": None}


def _fetch_portfolio_data(portfolio_id: Optional[int]) -> dict:
    """获取投资组合数据（持仓、盈亏等）"""
    if not portfolio_id:
        return {}
    
    try:
        from app.db.database import _get_conn
        conn = _get_conn()
        
        # 获取组合基本信息
        portfolio = conn.execute(
            "SELECT id, name FROM portfolios WHERE id = ?",
            (portfolio_id,)
        ).fetchone()
        
        if not portfolio:
            conn.close()
            return {}
        
        # 获取持仓数据
        positions = conn.execute(
            """SELECT 
                p.symbol,
                p.shares,
                p.avg_cost,
                s.name as stock_name,
                s.price as current_price
            FROM positions p
            LEFT JOIN market_all_stocks s ON p.symbol = s.symbol
            WHERE p.portfolio_id = ? AND p.shares > 0""",
            (portfolio_id,)
        ).fetchall()
        
        # 计算持仓市值和盈亏
        positions_list = []
        total_value = 0
        total_cost = 0
        
        for pos in positions:
            symbol = pos[0]
            shares = pos[1] or 0
            avg_cost = pos[2] or 0
            name = pos[3] or ""
            current_price = pos[4] or 0
            
            market_value = shares * current_price
            cost_basis = shares * avg_cost
            unrealized_pnl = market_value - cost_basis
            unrealized_pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0
            
            positions_list.append({
                "symbol": symbol,
                "name": name,
                "shares": shares,
                "avg_cost": avg_cost,
                "current_price": current_price,
                "market_value": market_value,
                "unrealized_pnl": unrealized_pnl,
                "unrealized_pnl_pct": unrealized_pnl_pct
            })
            
            total_value += market_value
            total_cost += cost_basis
        
        total_pnl = total_value - total_cost
        
        conn.close()
        
        return {
            "id": portfolio_id,
            "name": portfolio[1],
            "total_value": total_value,
            "total_cost": total_cost,
            "total_pnl": total_pnl,
            "total_pnl_pct": (total_pnl / total_cost * 100) if total_cost > 0 else 0,
            "positions": positions_list
        }
    except Exception as e:
        logger.warning(f"[Copilot] portfolio lookup error: {e}")
    return {}


def _fetch_historical_data(symbol: str, period: str = "daily", limit: int = 60) -> dict:
    """获取历史K线数据"""
    if not symbol:
        return {}
    
    try:
        from app.db.database import _get_conn
        conn = _get_conn()
        
        # 确定表名
        table_map = {
            "daily": "market_data_daily",
            "weekly": "market_data_weekly", 
            "monthly": "market_data_monthly"
        }
        table = table_map.get(period, "market_data_daily")
        
        # 查询历史数据
        rows = conn.execute(
            f"""SELECT date, open, high, low, close, volume
            FROM {table}
            WHERE symbol = ?
            ORDER BY date DESC
            LIMIT ?""",
            (symbol, limit)
        ).fetchall()
        
        conn.close()
        
        if not rows:
            return {}
        
        # 转换为列表（按时间正序）
        data = []
        for row in reversed(rows):
            data.append({
                "date": row[0],
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5]
            })
        
        return {
            "symbol": symbol,
            "period": period,
            "data": data,
            "count": len(data)
        }
    except Exception as e:
        logger.warning(f"[Copilot] historical data lookup error: {e}")
    return {}
# 对话历史持久化
# ═══════════════════════════════════════════════════════════════

def _init_conversations_table():
    """确保 conversations 表存在"""
    try:
        from app.db.database import _get_conn
        conn = _get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS copilot_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[Copilot] conversations table init error: {e}")

def _save_message(session_id: str, role: str, content: str):
    """保存单条消息到历史"""
    try:
        from app.db.database import _get_conn
        conn = _get_conn()
        conn.execute(
            "INSERT INTO copilot_conversations (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[Copilot] save message error: {e}")

def _load_conversation(session_id: str, limit: int = 20) -> List[dict]:
    """加载对话历史，返回消息列表"""
    try:
        from app.db.database import _get_conn
        conn = _get_conn()
        rows = conn.execute(
            "SELECT role, content FROM copilot_conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        ).fetchall()
        conn.close()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
    except Exception as e:
        logger.warning(f"[Copilot] load conversation error: {e}")
        return []

# SSE 流式对话端点
# ═══════════════════════════════════════════════════════════════

@router.post("/chat")
async def copilot_chat(request: Request):
    """
    SSE 流式对话接口

    请求体：
      prompt  : str  用户提问
      symbol? : str  当前标的（可选，用于上下文注入）
      provider?: str 指定 provider
      model?  : str  指定 model ID
      session_id?: str 会话ID（可选）
      user_id?: str  用户ID（可选）

    Wave 2 Integration:
      - Session management with config binding
      - Concurrency limiting per model
      - Token tracking with cost calculation
    """
    body = await request.json()
    prompt = (body.get("prompt") or "").strip()
    symbol = (body.get("symbol") or "").strip() or None
    provider_override = (body.get("provider") or "").strip().lower() or None
    model_override = (body.get("model") or "").strip() or None
    user_id = (body.get("user_id") or "").strip() or None

    session_id = (body.get("session_id") or "").strip()
    if not session_id:
        session_id = str(uuid.uuid4())

    _init_conversations_table()

    if not prompt:
        return StreamingResponse(
            iter([_sse({"error": "prompt 不能为空"})]),
            media_type="text/event-stream",
        )

    provider = provider_override if provider_override else _detect_provider()
    cfg = _get_llm_config(provider, model_override)
    
    if provider != "mock" and not cfg.get("api_key"):
        logger.warning(f"[Copilot] provider={provider} API Key 为空，降级为 Mock")
        provider = "mock"

    model_id = model_override or cfg.get("model", "")

    session_mgr = get_session_manager()
    session = session_mgr.create_or_get_session(
        session_id=session_id,
        user_id=user_id,
        config_version=1
    )
    
    bound_model = session_mgr.get_bound_model(session_id, provider)
    if bound_model and not model_override:
        model_id = bound_model
        cfg = _get_llm_config(provider, model_id)
    elif model_id:
        session_mgr.bind_model(session_id, provider, model_id)

    limiter = get_concurrency_limiter()
    acquired = await limiter.acquire(provider, model_id, timeout=30.0)
    if not acquired:
        return StreamingResponse(
            iter([_sse({"error": "并发限制，请稍后重试"})]),
            media_type="text/event-stream",
        )

    frontend_context = (body.get("context") or "").strip()
    
    price_info = _fetch_price_context(symbol)
    news_items = _fetch_latest_news(limit=5)
    valuation_data = _fetch_valuation_data(symbol)
    
    portfolio_data = None
    historical_data = None
    
    portfolio_id = body.get("portfolio_id")
    if portfolio_id:
        portfolio_data = _fetch_portfolio_data(int(portfolio_id))
    
    hist_symbol = body.get("hist_symbol") or symbol
    hist_period = body.get("hist_period", "daily")
    hist_limit = body.get("hist_limit", 60)
    if hist_symbol and body.get("include_historical"):
        historical_data = _fetch_historical_data(hist_symbol, hist_period, hist_limit)
    
    context_block = _build_context_block(
        symbol, price_info, news_items, valuation_data, 
        portfolio_data, historical_data
    )
    
    if frontend_context:
        context_block = f"{frontend_context}\n{context_block}"

    current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")

    system_msg = SYSTEM_PROMPT_TEMPLATE.format(
        current_time=current_time,
        context_block=context_block,
    )

    history = _load_conversation(session_id) if session_id else []

    messages = [
        {"role": "system", "content": system_msg},
    ]
    for h in history:
        messages.append(h)
    messages.append({"role": "user", "content": prompt})

    if session_id:
        _save_message(session_id, "user", prompt)

    logger.info(
        f"[Copilot] provider={provider} model={model_id} session={session_id[:8]}... "
        f"prompt='{prompt[:40]}...' history={len(history)}"
    )

    start_time = time.time()
    
    tracking_svc = get_token_tracking_service()
    prompt_tokens = sum(count_tokens(m.get("content", ""), model_id) for m in messages)
    completion_tokens = 0
    settings = get_settings()
    max_duration_seconds = settings.COPILOT_STREAM_TIMEOUT_SECONDS

    async def tracked_stream():
        nonlocal completion_tokens
        try:
            start_stream_time = time.time()
            async for chunk in _llm_stream(provider, messages, model_override):
                if time.time() - start_stream_time > max_duration_seconds:
                    logger.warning(f"[Copilot] Stream timeout after {max_duration_seconds}s")
                    yield _sse({"error": "请求超时，请稍后重试", "done": True})
                    return
                
                data = chunk.replace("data: ", "").strip()
                if data:
                    try:
                        parsed = json.loads(data)
                        if "content" in parsed:
                            completion_tokens += count_tokens(parsed["content"], model_id)
                    except json.JSONDecodeError:
                        pass
                yield chunk
        finally:
            limiter.release(provider, model_id)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            record = tracking_svc.track_usage(
                model_id=model_id,
                provider=provider,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                session_id=session_id,
                user_id=user_id,
                duration_ms=duration_ms
            )
            
            session_mgr.update_session_usage(
                session_id,
                tokens=record.total_tokens,
                cost_usd=record.cost_usd
            )
            
            logger.debug(
                f"[Copilot] Tracked: {record.total_tokens} tokens, ${record.cost_usd:.6f}, "
                f"{duration_ms}ms"
            )

    return StreamingResponse(
        tracked_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":   "no-cache",
            "Connection":       "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Session-Id": session_id,
            "X-Model-Id": model_id,
        },
    )


@router.post("/analyze-walkforward")
async def analyze_walkforward(request: Request):
    """
    AI-powered Walk-Forward Analysis interpretation.
    Uses Copilot LLM to generate plain language explanation and recommendations.
    """
    body = await request.json()
    wfa_result = body.get("result", {})
    
    if not wfa_result:
        return StreamingResponse(
            iter([_sse({"error": "Missing result data"})]),
            media_type="text/event-stream",
        )
    
    context = f"""
【Walk-Forward 分析结果】
股票: {wfa_result.get('symbol', 'N/A')}
策略: {wfa_result.get('strategy_type', 'N/A')}
模式: {wfa_result.get('window_mode', 'N/A')}
总窗口数: {wfa_result.get('total_windows', 0)}

【核心指标】
样本外平均收益: {wfa_result.get('avg_test_return_pct', 0):.2f}%
样本外夏普比率: {wfa_result.get('avg_test_sharpe', 0):.2f}
训练-测试收益差: {wfa_result.get('avg_return_gap', 0):.2f}%
过拟合程度: {wfa_result.get('overfitting_severity', 'unknown')}
过拟合窗口比例: {wfa_result.get('overfitting_ratio', 0) * 100:.1f}%
一致性得分: {wfa_result.get('consistency_score', 0):.1f}
置信度: {wfa_result.get('confidence', 'low')}

【系统建议】
{wfa_result.get('recommendation', 'N/A')}
"""
    
    prompt = f"""请分析以上Walk-Forward分析结果，提供：

1. **策略表现解读**（2-3句话，用通俗语言解释）
2. **过拟合风险评估**（分析训练-测试差距的含义）
3. **操作建议**（具体、可执行的建议）
4. **风险提示**（列出2-3条关键风险）

请用专业但易懂的语言，避免使用"作为一个AI"等套话。直接开始分析。

{context}
"""
    
    provider = _detect_provider()
    messages = [
        {"role": "system", "content": "你是一位专业的量化投资分析师，擅长用通俗语言解释复杂的策略分析结果。"},
        {"role": "user", "content": prompt}
    ]
    
    return StreamingResponse(
        _llm_stream(provider, messages),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
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
        "siliconflow": bool(os.getenv("SILICONFLOW_API_KEY", "")),
        "opencode_go": bool(os.getenv("OPENCODE_API_KEY", "")),
        "opencode_zen": bool(os.getenv("OPENCODE_API_KEY", "")),
    }
