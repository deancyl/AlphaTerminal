"""
AI Copilot 流式对话接口 - Phase 4
POST /api/v1/copilot/chat  →  SSE StreamingResponse
"""
import asyncio
import json
from typing import AsyncGenerator
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()

# ── Mock LLM 流式生成器（Phase 4 占位）─────────────────────────────────
CHUNK_SPEED_CPS = 5       # 每秒 5 个字符
IDLE_CHUNK_DELAY = 0.05   # 每 chunk 间隔（秒）


async def mock_llm_stream(prompt: str) -> AsyncGenerator[str, None]:
    """
    异步生成器：模拟大模型思考输出
    实际 Phase 5 替换为 Minimax/OpenAI 流式 API
    """
    template = (
        "这是一段来自 AlphaTerminal 的跨市场联动分析预测："
        "当前 A 股上证指数报收于 3923 点，成交量能温和放大，资金面呈现边际宽松格局。 "
        "从技术形态来看，指数在 3900 附近获得有效支撑，MACD 指标出现金叉信号，短期趋势转多。 "
        "与此同时，SHIBOR 利率走廊整体下移，银行间流动性充裕，为权益资产提供估值修复的宏观环境。 "
        "美股方面，纳斯达克指数在 AI 算力板块的带领下强势反弹，市场风险偏好回升， "
        "北上资金有望加速流入 A 股核心资产。 "
        "综合研判：上证指数短期目标位 4100，沪深 300 相对占优，建议关注券商、保险等非银金融板块。 "
        "风险提示：以上为 AI 辅助分析，不构成投资建议，市场的随机性永远存在，请谨慎决策。"
    )

    output = template
    chunk_size = CHUNK_SPEED_CPS
    delay = IDLE_CHUNK_DELAY

    # 模拟首字延迟（模型"思考"时间）
    await asyncio.sleep(0.3)

    for i in range(0, len(output), chunk_size):
        chunk = output[i : i + chunk_size]
        # 标准 SSE 格式：data: {json}\n\n
        payload = json.dumps({"content": chunk, "done": False})
        yield f"data: {payload}\n\n"
        await asyncio.sleep(delay)

    # 发送结束标记
    yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"


@router.post("/chat")
async def copilot_chat(request: Request):
    """
    SSE 流式对话接口
    前端通过 fetch EventSource 消费此接口
    """
    body = await request.json()
    prompt = body.get("prompt", "").strip()

    if not prompt:
        return StreamingResponse(
            iter([f"data: {json.dumps({'error': 'prompt 不能为空'})}\n\n"]),
            media_type="text/event-stream",
        )

    return StreamingResponse(
        mock_llm_stream(prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection":    "keep-alive",
            "X-Accel-Buffering": "no",   # 禁用 Nginx 缓冲
        },
    )
