"""
AI Copilot 流式对话接口 - Phase 5
POST /api/v1/chat  →  SSE StreamingResponse
支持 context 字段注入大盘指数/利率/快讯
"""
import asyncio
import json
from typing import AsyncGenerator
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()

CHUNK_SPEED_CPS = 5
IDLE_CHUNK_DELAY = 0.05


async def mock_llm_stream(prompt: str, context: str = "") -> AsyncGenerator[str, None]:
    """
    异步生成器：模拟大模型思考输出
    若收到 context，将其注入到输出开头
    实际 Phase 6 替换为 Minimax/OpenAI 流式 API
    """
    # 根据是否有 context 选择不同的输出策略
    if context:
        # 用户提供了上下文，AI 基于上下文作答
        output = (
            "收到您的提问，正在结合您提供的数据进行综合分析：\n\n"
            f"{context}\n\n"
            "基于以上数据，我的分析如下：\n"
            "当前市场呈现'股债双暖'格局，股票市场在流动性宽松预期下估值修复延续，"
            "而利率环境的变化需要关注央行公开市场操作的节奏。\n"
            "综合判断：风险偏好回暖支持权益类资产，但外围美联储政策的不确定性仍构成扰动项，"
            "建议保持攻守兼备的仓位结构，关注高股息与科技成长两条主线的轮动节奏。\n"
            "风险提示：以上为 AI 辅助分析，不构成投资建议，市场的随机性永远存在，请谨慎决策。"
        )
    else:
        output = (
            "这是一段来自 AlphaTerminal 的跨市场联动分析预测：\n\n"
            "当前 A 股上证指数报收于 3923 点，成交量能温和放大，资金面呈现边际宽松格局。\n"
            "从技术形态来看，指数在 3900 附近获得有效支撑，MACD 指标出现金叉信号，短期趋势转多。\n"
            "与此同时，SHIBOR 利率走廊整体下移，银行间流动性充裕，为权益资产提供估值修复的宏观环境。\n"
            "美股方面，纳斯达克指数在 AI 算力板块的带领下强势反弹，市场风险偏好回升，"
            "北上资金有望加速流入 A 股核心资产。\n\n"
            "综合研判：上证指数短期目标位 4100，沪深 300 相对占优，建议关注券商、保险等非银金融板块。\n"
            "风险提示：以上为 AI 辅助分析，不构成投资建议，市场的随机性永远存在，请谨慎决策。"
        )

    # 先发一句"正在思考"
    thinking_msg = "🧠 正在分析您提供的数据...\n\n"
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


@router.post("/chat")
async def copilot_chat(request: Request):
    """
    SSE 流式对话接口
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

    return StreamingResponse(
        mock_llm_stream(prompt, context),
        media_type="text/event-stream",
        headers={
            "Cache-Control":  "no-cache",
            "Connection":    "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
