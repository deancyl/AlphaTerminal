"""
Agentic Workflow API Router

Provides endpoints for natural language workflow orchestration.

Endpoints:
- POST /api/v1/agentic/workflow - Execute a workflow
- GET /api/v1/agentic/tools - List available tools
- GET /api/v1/agentic/workflow/{id} - Get workflow status
"""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from app.services.agentic.workflow_engine import get_workflow_engine, WorkflowStatus
from app.services.agentic.tool_registry import get_tool_registry
from app.utils.errors import success_response, error_response
from app.utils.error_decorator import handle_errors
from app.utils.error_sanitizer import sanitize_error

logger = logging.getLogger(__name__)
router = APIRouter()


class WorkflowRequest(BaseModel):
    """Request body for workflow execution"""

    query: str = Field(..., description="Natural language query")
    execute: bool = Field(True, description="Whether to execute immediately")
    provider: Optional[str] = Field(None, description="LLM provider (optional)")


class WorkflowResponse(BaseModel):
    """Response for workflow creation"""

    workflow_id: str
    status: str
    message: str


@router.get("/tools")
@handle_errors(module="agentic")
async def list_tools():
    """
    List all available tools.

    Returns:
        List of tool definitions with parameters
    """
    registry = get_tool_registry()
    tools = registry.list_tools()

    return success_response(
        {"tools": [t.to_dict() for t in tools], "count": len(tools)}
    )


@router.post("/workflow")
@handle_errors(module="agentic")
async def create_workflow(request: WorkflowRequest, background_tasks: BackgroundTasks):
    """
    Create and optionally execute a workflow.

    Args:
        request: Workflow request with query and options

    Returns:
        Workflow ID and initial status
    """
    if not request.query or not request.query.strip():
        return error_response("Query cannot be empty", code=400)

    engine = get_workflow_engine()

    workflow = engine.plan_workflow(request.query.strip())

    if request.execute:

        async def run_workflow():
            try:
                await engine.execute_workflow(workflow)
            except Exception as e:
                logger.error(
                    f"[Agentic] Workflow {workflow.id} failed: {e}", exc_info=True
                )
                workflow.status = WorkflowStatus.FAILED
                workflow.result = f"执行失败: {sanitize_error(e)}"

        background_tasks.add_task(run_workflow)

        return success_response(
            {
                "workflow_id": workflow.id,
                "status": "running",
                "steps": len(workflow.steps),
                "message": "Workflow started in background",
            }
        )
    else:
        return success_response(
            {
                "workflow_id": workflow.id,
                "status": "planned",
                "steps": [s.to_dict() for s in workflow.steps],
                "intent": workflow.metadata.get("intent", {}),
                "message": "Workflow planned, use /workflow/{id}/execute to run",
            }
        )


@router.get("/workflow/{workflow_id}")
@handle_errors(module="agentic")
async def get_workflow_status(workflow_id: str):
    """
    Get workflow status and results.

    Args:
        workflow_id: Workflow ID

    Returns:
        Workflow status, steps, and result (if completed)
    """
    engine = get_workflow_engine()
    workflow = engine.get_workflow(workflow_id)

    if not workflow:
        return error_response(f"Workflow not found: {workflow_id}", code=404)

    return success_response(workflow.to_dict())


@router.post("/workflow/{workflow_id}/execute")
@handle_errors(module="agentic")
async def execute_workflow(workflow_id: str, background_tasks: BackgroundTasks):
    """
    Execute a planned workflow.

    Args:
        workflow_id: Workflow ID

    Returns:
        Execution status
    """
    engine = get_workflow_engine()
    workflow = engine.get_workflow(workflow_id)

    if not workflow:
        return error_response(f"Workflow not found: {workflow_id}", code=404)

    if workflow.status != WorkflowStatus.PENDING:
        return error_response(f"Workflow already {workflow.status.value}", code=400)

    async def run_workflow():
        try:
            await engine.execute_workflow(workflow)
        except Exception as e:
            logger.error(f"[Agentic] Workflow {workflow_id} failed: {e}", exc_info=True)
            workflow.status = WorkflowStatus.FAILED
            workflow.result = f"执行失败: {sanitize_error(e)}"

    background_tasks.add_task(run_workflow)

    return success_response(
        {
            "workflow_id": workflow_id,
            "status": "running",
            "message": "Workflow execution started",
        }
    )


@router.get("/workflows")
@handle_errors(module="agentic")
async def list_workflows(limit: int = 20):
    """
    List recent workflows.

    Args:
        limit: Maximum number of workflows to return

    Returns:
        List of recent workflows
    """
    engine = get_workflow_engine()
    workflows = engine.list_workflows(limit=limit)

    return success_response(
        {"workflows": [w.to_dict() for w in workflows], "count": len(workflows)}
    )


@router.get("/health")
@handle_errors(module="agentic")
async def health_check():
    """Health check endpoint"""
    registry = get_tool_registry()
    engine = get_workflow_engine()

    return success_response(
        {
            "status": "healthy",
            "tools_count": len(registry.list_tools()),
            "workflows_cached": len(engine._workflows),
        }
    )
