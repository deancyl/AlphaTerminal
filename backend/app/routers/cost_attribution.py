"""
LLM Cost Attribution Router

Provides endpoints for visualizing token consumption across different workflows
with Sankey diagrams and prompt tree viewers.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List

from fastapi import APIRouter, Query, HTTPException, Depends

from app.routers.admin import verify_admin_key
from app.db.database import _get_conn
from app.utils.error_decorator import handle_errors
from app.utils.executor import get_executor
from app.utils.error_sanitizer import sanitize_error

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/cost_attribution",
    tags=["cost_attribution"],
    dependencies=[Depends(verify_admin_key)],
)


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════


def _infer_workflow_type(metadata: str, session_id: str) -> str:
    """
    Infer workflow type from metadata JSON or session_id pattern.

    Workflow types:
    - agentic: Multi-step agentic workflows
    - report: Report generation
    - chat: General chat/copilot
    - backtest: Backtest analysis
    - research: Investment research
    - other: Uncategorized
    """
    if metadata:
        try:
            meta = json.loads(metadata)
            # Check for explicit workflow_type
            if meta.get("workflow_type"):
                return meta["workflow_type"]
            # Check for agentic indicators
            if meta.get("agentic_type") or meta.get("tool_calls"):
                return "agentic"
            if meta.get("report_type"):
                return "report"
            if meta.get("backtest_id"):
                return "backtest"
            if meta.get("research_query"):
                return "research"
        except (json.JSONDecodeError, TypeError):
            pass

    # Infer from session_id pattern
    if session_id:
        sid_lower = session_id.lower()
        if "agentic" in sid_lower or "agent" in sid_lower:
            return "agentic"
        if "report" in sid_lower:
            return "report"
        if "backtest" in sid_lower:
            return "backtest"
        if "research" in sid_lower:
            return "research"
        if "copilot" in sid_lower or "chat" in sid_lower:
            return "chat"

    return "other"


def _get_sankey_data_sync(start_date: str, end_date: str) -> Dict[str, Any]:
    """Synchronous function to fetch and aggregate Sankey data."""
    conn = _get_conn()
    try:
        # Fetch all records in date range
        rows = conn.execute(
            """
            SELECT session_id, model_id, provider, prompt_tokens, completion_tokens,
                   total_tokens, cost_usd, metadata, created_at
            FROM token_usage_logs
            WHERE created_at >= ? AND created_at <= ?
            ORDER BY created_at DESC
        """,
            (start_date, end_date),
        ).fetchall()

        # Aggregate by workflow -> model
        workflow_totals: Dict[str, Dict[str, float]] = {}
        model_totals: Dict[str, float] = {}
        total_cost = 0.0

        for row in rows:
            session_id = row[0] or ""
            model_id = row[1] or "unknown"
            cost = row[6] or 0.0
            metadata = row[7]

            workflow = _infer_workflow_type(metadata, session_id)

            # Aggregate workflow -> model
            if workflow not in workflow_totals:
                workflow_totals[workflow] = {}
            if model_id not in workflow_totals[workflow]:
                workflow_totals[workflow][model_id] = 0.0
            workflow_totals[workflow][model_id] += cost

            # Aggregate model totals
            if model_id not in model_totals:
                model_totals[model_id] = 0.0
            model_totals[model_id] += cost

            total_cost += cost

        # Build Sankey nodes and links
        nodes = []
        links = []
        node_index = {}

        # Add "Total" node
        nodes.append({"name": "Total", "itemStyle": {"color": "#0F52BA"}})
        node_index["Total"] = 0

        # Add workflow nodes
        workflow_colors = {
            "agentic": "#E63946",
            "report": "#1A936F",
            "chat": "#F5A623",
            "backtest": "#9B59B6",
            "research": "#3498DB",
            "other": "#95A5A6",
        }

        for workflow, models in sorted(
            workflow_totals.items(), key=lambda x: sum(x[1].values()), reverse=True
        ):
            workflow_cost = sum(models.values())
            if workflow_cost > 0:
                idx = len(nodes)
                node_index[workflow] = idx
                nodes.append(
                    {
                        "name": workflow.capitalize(),
                        "itemStyle": {
                            "color": workflow_colors.get(workflow, "#95A5A6")
                        },
                    }
                )
                # Link from Total to workflow
                links.append(
                    {"source": 0, "target": idx, "value": round(workflow_cost, 6)}
                )

        # Add model nodes and links
        for model_id, cost in sorted(
            model_totals.items(), key=lambda x: x[1], reverse=True
        ):
            if cost > 0:
                idx = len(nodes)
                node_index[model_id] = idx
                nodes.append({"name": model_id})

        # Add links from workflow to model
        for workflow, models in workflow_totals.items():
            if workflow not in node_index:
                continue
            workflow_idx = node_index[workflow]
            for model_id, cost in models.items():
                if model_id in node_index and cost > 0:
                    links.append(
                        {
                            "source": workflow_idx,
                            "target": node_index[model_id],
                            "value": round(cost, 6),
                        }
                    )

        return {
            "nodes": nodes,
            "links": links,
            "total_cost": round(total_cost, 6),
            "workflow_count": len(workflow_totals),
            "model_count": len(model_totals),
            "record_count": len(rows),
        }
    finally:
        conn.close()


def _get_prompt_tree_sync(session_id: str) -> Dict[str, Any]:
    """Synchronous function to build prompt tree for a session."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT request_id, model_id, prompt_tokens, completion_tokens,
                   total_tokens, cost_usd, duration_ms, metadata, created_at
            FROM token_usage_logs
            WHERE session_id = ?
            ORDER BY created_at ASC
        """,
            (session_id,),
        ).fetchall()

        if not rows:
            return {"session_id": session_id, "nodes": [], "total_cost": 0.0}

        nodes = []
        total_cost = 0.0

        for i, row in enumerate(rows):
            request_id = row[0]
            model_id = row[1]
            prompt_tokens = row[2] or 0
            completion_tokens = row[3] or 0
            total_tokens = row[4] or 0
            cost = row[5] or 0.0
            duration_ms = row[6]
            metadata = row[7]
            created_at = row[8]

            # Parse metadata for prompt preview
            prompt_preview = ""
            tool_calls = []
            if metadata:
                try:
                    meta = json.loads(metadata)
                    # Get prompt preview (first 100 chars)
                    if meta.get("prompt"):
                        prompt_preview = str(meta["prompt"])[:100] + "..."
                    if meta.get("tool_calls"):
                        tool_calls = meta["tool_calls"]
                except (json.JSONDecodeError, TypeError):
                    pass

            nodes.append(
                {
                    "id": request_id,
                    "seq": i + 1,
                    "model_id": model_id,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cost_usd": round(cost, 6),
                    "duration_ms": duration_ms,
                    "prompt_preview": prompt_preview,
                    "tool_calls": tool_calls,
                    "created_at": created_at,
                    "children": [],
                }
            )

            total_cost += cost

        return {
            "session_id": session_id,
            "nodes": nodes,
            "total_cost": round(total_cost, 6),
            "total_tokens": sum(n["total_tokens"] for n in nodes),
            "request_count": len(nodes),
        }
    finally:
        conn.close()


def _get_cost_breakdown_sync(
    start_date: str, end_date: str, group_by: str
) -> List[Dict[str, Any]]:
    """Synchronous function to get cost breakdown by dimension."""
    conn = _get_conn()
    try:
        if group_by == "workflow":
            rows = conn.execute(
                """
                SELECT session_id, model_id, provider, prompt_tokens, completion_tokens,
                       total_tokens, cost_usd, metadata
                FROM token_usage_logs
                WHERE created_at >= ? AND created_at <= ?
            """,
                (start_date, end_date),
            ).fetchall()

            workflow_data: Dict[str, Dict[str, Any]] = {}
            for row in rows:
                session_id = row[0] or ""
                model_id = row[1] or ""
                provider = row[2] or ""
                prompt_tokens = int(row[3] or 0)
                completion_tokens = int(row[4] or 0)
                total_tokens = int(row[5] or 0)
                cost_usd = float(row[6] or 0.0)
                metadata = row[7]
                workflow = _infer_workflow_type(metadata, session_id)

                if workflow not in workflow_data:
                    workflow_data[workflow] = {
                        "name": workflow.capitalize(),
                        "requests": 0,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "cost_usd": 0.0,
                    }

                workflow_data[workflow]["requests"] += 1
                workflow_data[workflow]["prompt_tokens"] += prompt_tokens
                workflow_data[workflow]["completion_tokens"] += completion_tokens
                workflow_data[workflow]["total_tokens"] += total_tokens
                workflow_data[workflow]["cost_usd"] += cost_usd

            result = list(workflow_data.values())
            result.sort(key=lambda x: x["cost_usd"], reverse=True)
            return result

        elif group_by == "model":
            rows = conn.execute(
                """
                SELECT model_id, provider,
                       COUNT(*) as requests,
                       SUM(prompt_tokens) as prompt_tokens,
                       SUM(completion_tokens) as completion_tokens,
                       SUM(total_tokens) as total_tokens,
                       SUM(cost_usd) as cost_usd,
                       AVG(duration_ms) as avg_duration_ms
                FROM token_usage_logs
                WHERE created_at >= ? AND created_at <= ?
                GROUP BY model_id, provider
                ORDER BY cost_usd DESC
            """,
                (start_date, end_date),
            ).fetchall()

            return [dict(row) for row in rows]

        elif group_by == "session":
            rows = conn.execute(
                """
                SELECT session_id,
                       COUNT(*) as requests,
                       SUM(prompt_tokens) as prompt_tokens,
                       SUM(completion_tokens) as completion_tokens,
                       SUM(total_tokens) as total_tokens,
                       SUM(cost_usd) as cost_usd,
                       MIN(created_at) as first_request,
                       MAX(created_at) as last_request
                FROM token_usage_logs
                WHERE created_at >= ? AND created_at <= ?
                  AND session_id IS NOT NULL
                GROUP BY session_id
                ORDER BY cost_usd DESC
                LIMIT 100
            """,
                (start_date, end_date),
            ).fetchall()

            return [dict(row) for row in rows]

        else:
            raise HTTPException(status_code=400, detail=f"Invalid group_by: {group_by}")
    finally:
        conn.close()


def _get_sessions_list_sync(
    start_date: str, end_date: str, limit: int
) -> List[Dict[str, Any]]:
    """Get list of sessions with token usage for the prompt tree selector."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT session_id,
                   COUNT(*) as requests,
                   SUM(total_tokens) as total_tokens,
                   SUM(cost_usd) as cost_usd,
                   MIN(created_at) as first_request,
                   MAX(created_at) as last_request
            FROM token_usage_logs
            WHERE created_at >= ? AND created_at <= ?
              AND session_id IS NOT NULL AND session_id != ''
            GROUP BY session_id
            ORDER BY cost_usd DESC
            LIMIT ?
        """,
            (start_date, end_date, limit),
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# API Endpoints
# ═══════════════════════════════════════════════════════════════


@router.get("/sankey")
@handle_errors(module="cost_attribution")
async def get_sankey_data(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
):
    """
    Get Sankey diagram data for cost attribution.

    Returns nodes and links for visualizing cost flow from Total -> Workflow -> Model.
    """
    # P0: Add 30s timeout protection
    COST_TIMEOUT = 30.0
    
    loop = asyncio.get_event_loop()

    try:
        # P0: Timeout protection for blocking DB call
        result = await asyncio.wait_for(
            loop.run_in_executor(get_executor(), _get_sankey_data_sync, start_date, end_date),
            timeout=COST_TIMEOUT
        )
        return {"code": 0, "data": result}
    except Exception as e:
        logger.error(f"[CostAttribution] Error getting Sankey data: {e}", exc_info=True)
        return {"code": 1, "error": sanitize_error(e)}


@router.get("/prompt_tree")
@handle_errors(module="cost_attribution")
async def get_prompt_tree(
    session_id: str = Query(..., description="Session ID to get prompt tree for")
):
    """
    Get prompt tree for a specific session.

    Returns hierarchical tree of prompts with token counts and costs.
    """
    # P0: Add 30s timeout protection
    COST_TIMEOUT = 30.0
    
    loop = asyncio.get_event_loop()

    try:
        # P0: Timeout protection for blocking DB call
        result = await asyncio.wait_for(
            loop.run_in_executor(get_executor(), _get_prompt_tree_sync, session_id),
            timeout=COST_TIMEOUT
        )
        return {"code": 0, "data": result}
    except Exception as e:
        logger.error(f"[CostAttribution] Error getting prompt tree: {e}", exc_info=True)
        return {"code": 1, "error": sanitize_error(e)}


@router.get("/breakdown")
@handle_errors(module="cost_attribution")
async def get_cost_breakdown(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    group_by: str = Query(default="workflow", pattern="^(workflow|model|session)$"),
):
    """
    Get cost breakdown by different dimensions.

    - workflow: Group by workflow type (agentic, report, chat, etc.)
    - model: Group by model_id
    - session: Group by session_id
    """
    # P0: Add 30s timeout protection
    COST_TIMEOUT = 30.0
    
    loop = asyncio.get_event_loop()

    try:
        # P0: Timeout protection for blocking DB call
        result = await asyncio.wait_for(
            loop.run_in_executor(get_executor(), _get_cost_breakdown_sync, start_date, end_date, group_by),
            timeout=COST_TIMEOUT
        )
        return {"code": 0, "data": result, "count": len(result)}
    except Exception as e:
        logger.error(f"[CostAttribution] Error getting breakdown: {e}", exc_info=True)
        return {"code": 1, "error": sanitize_error(e)}


@router.get("/sessions")
@handle_errors(module="cost_attribution")
async def get_sessions_list(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    limit: int = Query(default=50, ge=1, le=500),
):
    """
    Get list of sessions with token usage for the prompt tree selector.
    """
    # P0: Add 30s timeout protection
    COST_TIMEOUT = 30.0
    
    loop = asyncio.get_event_loop()

    try:
        # P0: Timeout protection for blocking DB call
        result = await asyncio.wait_for(
            loop.run_in_executor(get_executor(), _get_sessions_list_sync, start_date, end_date, limit),
            timeout=COST_TIMEOUT
        )
        return {"code": 0, "data": result, "count": len(result)}
    except Exception as e:
        logger.error(f"[CostAttribution] Error getting sessions: {e}", exc_info=True)
        return {"code": 1, "error": sanitize_error(e)}


@router.get("/health")
@handle_errors(module="cost_attribution")
async def health_check():
    """Health check endpoint."""
    return {"code": 0, "message": "Cost Attribution API is healthy"}
