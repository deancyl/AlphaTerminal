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

def _get_llm_config(provider: str) -> dict:
    """
    获取指定 Provider 的完整配置（DB > .env > 默认值）。
    """
    # 1. 数据库（用户 UI 保存的配置，优先级最高）
    try:
        from app.db.database import get_admin_config
        db_cfg = get_admin_config(f"llm_{provider}")
        if db_cfg and isinstance(db_cfg, dict) and db_cfg.get("api_key"):
            return {
                "api_key":  db_cfg.get("api_key", ""),
                "base_url": db_cfg.get("base_url", ""),
                "model":    db_cfg.get("model", ""),
            }
    except Exception:
        pass
    # 2. 环境变量（.env 文件）
    defaults = {
        "deepseek": {"api_key": os.getenv("DEEPSEEK_API_KEY",""), "base_url": os.getenv("DEEPSEEK_API_BASE","https://api.deepseek.com"), "model": os.getenv("DEEPSEEK_MODEL","deepseek-chat")},
        "qianwen":  {"api_key": os.getenv("QIANWEN_API_KEY",""),  "base_url": os.getenv("QIANWEN_API_BASE","https://dashscope.aliyuncs.com/compatible-mode/v1"), "model": os.getenv("QIANWEN_MODEL","qwen-plus")},
        "openai":   {"api_key": os.getenv("OPENAI_API_KEY",""),  "base_url": os.getenv("OPENAI_API_BASE","https://api.openai.com/v1"), "model": os.getenv("OPENAI_MODEL","gpt-3.5-turbo")},
        "siliconflow": {"api_key": os.getenv("SILICONFLOW_API_KEY",""), "base_url": os.getenv("SILICONFLOW_API_BASE","https://api.siliconflow.cn/v1"), "model": os.getenv("SILICONFLOW_MODEL","deepseek-ai/DeepSeek-V3")},
        "opencode": {"api_key": os.getenv("OPENCODE_API_KEY",""), "base_url": os.getenv("OPENCODE_API_BASE","https://api.opencode.ai/v1"), "model": os.getenv("OPENCODE_MODEL","opencode-chat")},
    }
    return defaults.get(provider, {})

def _detect_provider() -> str:
    """按优先级检测可用的 LLM Provider（优先使用数据库配置）"""
    for p in ["deepseek", "qianwen", "openai", "siliconflow", "opencode"]:
        if _get_llm_config(p).get("api_key"):
            return p
    return "mock"


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

def _build_context_block(symbol: Optional[str], price_info: dict, news_items: list, valuation_data: dict) -> str:
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

    # ── 市场估值（PE/PB/YTD收益率）────────────────────────────
    if valuation_data:
        pe_ttm     = valuation_data.get("pe_ttm")
        pb         = valuation_data.get("pb")
        ret_ytd    = valuation_data.get("returns_ytd")
        pe_pct     = valuation_data.get("pe_percentile")
        pb_pct     = valuation_data.get("pb_percentile")
        if pe_ttm is not None:
            pe_str = f"{pe_ttm:.2f}" + (f"（历史分位：{pe_pct:.1f}%）" if pe_pct else "")
            parts.append(f"【市场估值】当前 PE_TTM：{pe_str}")
        if pb is not None:
            pb_str = f"{pb:.2f}" + (f"（历史分位：{pb_pct:.1f}%）" if pb_pct else "")
            parts.append(f"当前 PB：{pb_str}")
        if ret_ytd is not None:
            arrow_ytd = "▲" if ret_ytd >= 0 else "▼"
            parts.append(f"年初至今收益率：{arrow_ytd}{abs(ret_ytd):.2f}%")

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
        async with httpx.AsyncClient(timeout=120.0) as client:
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
        logger.error(f"[DeepSeek] {e}")
        yield _sse({"error": f"DeepSeek API 调用失败: {e}"})


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
        async with httpx.AsyncClient(timeout=120.0) as client:
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
        logger.error(f"[SiliconFlow] {e}")
        yield _sse({"error": f"硅基流动 API 调用失败: {e}"})


async def _call_opencode(messages: list[dict], model_override: str | None = None) -> AsyncGenerator[str, None]:
    """OpenCode API 调用 - 兼容 OpenAI 格式"""
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
        async with httpx.AsyncClient(timeout=120.0) as client:
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
        logger.error(f"[OpenCode] {e}")
        yield _sse({"error": f"OpenCode API 调用失败: {e}"})


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

    provider_override = (body.get("provider") or "").strip().lower() or None
    model_override = (body.get("model") or "").strip() or None

    if not prompt:
        return StreamingResponse(
            iter([_sse({"error": "prompt 不能为空"})]),
            media_type="text/event-stream",
        )

    provider = provider_override if provider_override else _detect_provider()

    # ── Provider 可用性校验：前端指定但 API Key 为空时降级 Mock ──
    # 从 _get_llm_config 获取配置（DB > .env）
    cfg = _get_llm_config(provider)
    if provider != "mock" and not cfg.get("api_key"):
        logger.warning(f"[Copilot] provider={provider} API Key 为空，降级为 Mock")
        provider = "mock"

    # ── 构建上下文注入 ────────────────────────────────────────
    # 前端可传 context 字段（格式化的市场/板块/情绪数据），补充后端实时数据
    frontend_context = (body.get("context") or "").strip()
    price_info = _fetch_price_context(symbol)
    news_items = _fetch_latest_news(limit=5)
    valuation_data = _fetch_valuation_data(symbol)
    context_block = _build_context_block(symbol, price_info, news_items, valuation_data)
    
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
        f"[Copilot] provider={provider} model={model_override or 'default'} symbol={symbol or '-'} "
        f"prompt='{prompt[:40]}...' context_blocks={len(context_block)}"
    )

    return StreamingResponse(
        _llm_stream(provider, messages, model_override),
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
        "siliconflow": bool(os.getenv("SILICONFLOW_API_KEY", "")),
        "opencode": bool(os.getenv("OPENCODE_API_KEY", "")),
    }
