"""
Workflow Engine for Agentic Workflow

Orchestrates multi-step workflows based on natural language queries.
Uses LLM for intent parsing and step planning.
"""
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from app.services.agentic.tool_registry import get_tool_registry
from app.services.copilot.query_classifier import get_query_classifier, QueryType

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="workflow_")


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStep:
    """Single step in a workflow"""
    id: str
    tool: str
    params: Dict[str, Any]
    output: Optional[Dict[str, Any]] = None
    status: str = "pending"
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    elapsed_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tool": self.tool,
            "params": self.params,
            "output": self.output,
            "status": self.status,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed_ms": self.elapsed_ms
        }


@dataclass
class Workflow:
    """Complete workflow with steps and result"""
    id: str
    query: str
    steps: List[WorkflowStep] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    result: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "query": self.query,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status.value,
            "result": self.result,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata
        }


class WorkflowEngine:
    """
    Workflow orchestration engine.
    
    Parses natural language queries into executable workflows,
    executes steps, and generates reports.
    """

    def __init__(self):
        self.registry = get_tool_registry()
        self.classifier = get_query_classifier()
        self._workflows: Dict[str, Workflow] = {}

    def parse_intent(self, query: str) -> Dict[str, Any]:
        """
        Parse user intent from natural language query.
        
        Returns:
            Dict with query_type, symbols, sector, suggested_tools
        """
        result = self.classifier.classify(query)

        suggested_tools = self._suggest_tools(result.query_type, result.symbols, result.sector)

        return {
            "query_type": result.query_type.value,
            "symbols": result.symbols,
            "sector": result.sector,
            "confidence": result.confidence,
            "suggested_tools": suggested_tools
        }

    def _suggest_tools(self, query_type: QueryType, symbols: List[str], sector: Optional[str]) -> List[str]:
        """Suggest tools based on query type"""
        base_tools = []

        if query_type == QueryType.COMPANY_DEEP_DIVE:
            if symbols:
                base_tools.extend(["get_quote", "get_financial", "get_kline", "get_news"])
        elif query_type == QueryType.SECTOR_COMPARISON:
            if symbols:
                base_tools.extend(["get_quote", "get_financial"])
        elif query_type == QueryType.MACRO_IMPACT:
            base_tools.append("get_macro_data")
        elif query_type == QueryType.EVENT_DRIVEN:
            base_tools.extend(["get_news", "get_quote"])
        elif query_type == QueryType.QUICK_QA:
            if symbols:
                base_tools.extend(["get_quote", "get_financial"])

        if sector:
            base_tools.append("get_sector_stocks")

        return list(set(base_tools))

    def plan_workflow(self, query: str) -> Workflow:
        """
        Plan a workflow based on the query.
        
        Returns:
            Workflow with planned steps
        """
        intent = self.parse_intent(query)

        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"

        steps = []
        symbols = intent.get("symbols", [])
        sector = intent.get("sector")
        tools = intent.get("suggested_tools", [])

        for i, tool_name in enumerate(tools):
            params = {}

            if tool_name == "get_quote":
                if symbols:
                    params["symbol"] = symbols[0]
            elif tool_name == "get_financial":
                if symbols:
                    params["symbol"] = symbols[0]
            elif tool_name == "get_kline":
                if symbols:
                    params["symbol"] = symbols[0]
                    params["period"] = "daily"
                    params["limit"] = 60
            elif tool_name == "get_news":
                params["limit"] = 10
                if symbols:
                    params["symbol"] = symbols[0]
            elif tool_name == "get_sector_stocks":
                if sector:
                    params["sector"] = sector
            elif tool_name == "get_macro_data":
                macro_keywords = ["GDP", "CPI", "PPI", "PMI", "M2"]
                for kw in macro_keywords:
                    if kw in query.upper():
                        params["indicator"] = kw
                        break
                if not params:
                    params["indicator"] = "GDP"

            if params or tool_name in ["get_news"]:
                steps.append(WorkflowStep(
                    id=f"{workflow_id}_step_{i+1}",
                    tool=tool_name,
                    params=params
                ))

        if not steps and symbols:
            steps.append(WorkflowStep(
                id=f"{workflow_id}_step_1",
                tool="get_quote",
                params={"symbol": symbols[0]}
            ))

        workflow = Workflow(
            id=workflow_id,
            query=query,
            steps=steps,
            metadata={
                "intent": intent,
                "planned_at": datetime.now().isoformat()
            }
        )

        self._workflows[workflow_id] = workflow
        logger.info(f"[WorkflowEngine] Planned workflow {workflow_id} with {len(steps)} steps")

        return workflow

    async def execute_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """
        Execute a single workflow step.
        
        Returns:
            Execution result
        """
        step.status = "running"
        step.started_at = datetime.now().isoformat()

        result = await self.registry.execute(step.tool, step.params)

        step.completed_at = datetime.now().isoformat()
        step.elapsed_ms = result.get("elapsed_ms", 0)

        if result.get("success"):
            step.status = "completed"
            step.output = result.get("data")
        else:
            step.status = "failed"
            step.error = result.get("error", "Unknown error")

        return result

    async def execute_workflow(self, workflow: Workflow) -> Workflow:
        """
        Execute all steps in a workflow.
        
        Returns:
            Updated workflow with results
        """
        workflow.status = WorkflowStatus.RUNNING

        for step in workflow.steps:
            try:
                await self.execute_step(step)
            except Exception as e:
                logger.error(f"[WorkflowEngine] Step {step.id} failed: {e}", exc_info=True)
                step.status = "failed"
                step.error = str(e)

        all_completed = all(s.status == "completed" for s in workflow.steps)
        any_failed = any(s.status == "failed" for s in workflow.steps)

        if all_completed:
            workflow.status = WorkflowStatus.COMPLETED
        elif any_failed:
            workflow.status = WorkflowStatus.FAILED
        else:
            workflow.status = WorkflowStatus.COMPLETED

        workflow.completed_at = datetime.now().isoformat()

        workflow.result = await self.generate_report(workflow)

        self._workflows[workflow.id] = workflow
        logger.info(f"[WorkflowEngine] Workflow {workflow.id} completed with status {workflow.status.value}")

        return workflow

    async def generate_report(self, workflow: Workflow) -> str:
        """
        Generate Markdown report from workflow results.
        
        Returns:
            Markdown formatted report
        """
        query = workflow.query
        steps_data = []

        for step in workflow.steps:
            if step.output:
                steps_data.append({
                    "tool": step.tool,
                    "params": step.params,
                    "output": step.output
                })

        if not steps_data:
            return f"# 分析报告\n\n查询：{query}\n\n未能获取到有效数据。"

        report_lines = [
            "# 投研分析报告",
            "",
            f"**查询**: {query}",
            f"**生成时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}",
            "",
            "---",
            ""
        ]

        for step_data in steps_data:
            tool = step_data["tool"]
            output = step_data["output"]

            if tool == "get_quote":
                report_lines.extend(self._format_quote_section(output))
            elif tool == "get_financial":
                report_lines.extend(self._format_financial_section(output))
            elif tool == "get_kline":
                report_lines.extend(self._format_kline_section(output))
            elif tool == "get_news":
                report_lines.extend(self._format_news_section(output))
            elif tool == "get_sector_stocks":
                report_lines.extend(self._format_sector_section(output))
            elif tool == "get_macro_data":
                report_lines.extend(self._format_macro_section(output))

        report_lines.extend([
            "",
            "---",
            "",
            "## ⚠️ 风险提示",
            "",
            "- 以上分析基于公开数据，仅供参考，不构成投资建议",
            "- 股市有风险，投资需谨慎",
            "- 请结合自身风险承受能力做出投资决策",
            ""
        ])

        return "\n".join(report_lines)

    def _format_quote_section(self, data: Dict[str, Any]) -> List[str]:
        """Format quote data as Markdown"""
        if not data or data.get("error"):
            return ["## 📊 行情数据", "", "暂无行情数据", ""]

        symbol = data.get("symbol", "")
        name = data.get("name", "")
        price = data.get("price", 0)
        change = data.get("change", 0)
        change_pct = data.get("change_pct", 0)

        arrow = "▲" if change_pct >= 0 else "▼"
        color = "green" if change_pct >= 0 else "red"

        return [
            "## 📊 实时行情",
            "",
            f"**{name} ({symbol})**",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 最新价 | ¥{price:.2f} |",
            f"| 涨跌幅 | {arrow}{abs(change_pct):.2f}% |",
            f"| 涨跌额 | {arrow}¥{abs(change):.2f} |",
            f"| 成交量 | {data.get('volume', 0):,.0f} |",
            f"| 最高 | ¥{data.get('high', 0):.2f} |",
            f"| 最低 | ¥{data.get('low', 0):.2f} |",
            ""
        ]

    def _format_financial_section(self, data: Dict[str, Any]) -> List[str]:
        """Format financial data as Markdown"""
        if not data or data.get("error"):
            return ["## 📈 财务数据", "", "暂无财务数据", ""]

        latest = data.get("data", {})
        history = data.get("history", [])

        lines = [
            "## 📈 财务指标",
            ""
        ]

        if latest:
            key_metrics = ["roe", "roa", "pe_ttm", "pb", "debt_ratio", "current_ratio"]
            lines.append("| 指标 | 数值 |")
            lines.append("|------|------|")

            for metric in key_metrics:
                value = latest.get(metric)
                if value is not None:
                    lines.append(f"| {metric.upper()} | {value} |")
            lines.append("")

        if history:
            lines.append("**近8季度趋势**:")
            lines.append("")
            lines.append("| 报告期 | ROE | 净利润率 |")
            lines.append("|--------|-----|----------|")
            for h in history[-8:]:
                period = h.get("报告期", h.get("date", ""))
                roe = h.get("roe", h.get("ROE", ""))
                npm = h.get("net_profit_margin", h.get("销售净利率", ""))
                lines.append(f"| {period} | {roe} | {npm} |")
            lines.append("")

        return lines

    def _format_kline_section(self, data: Dict[str, Any]) -> List[str]:
        """Format K-line data as Markdown"""
        if not data or data.get("error") or not data.get("data"):
            return ["## 📉 K线数据", "", "暂无K线数据", ""]

        kline_data = data.get("data", [])
        symbol = data.get("symbol", "")

        if len(kline_data) < 2:
            return ["## 📉 K线数据", "", "数据不足", ""]

        latest = kline_data[-1]
        prev = kline_data[-2]

        ma5 = sum(d["close"] for d in kline_data[-5:]) / 5 if len(kline_data) >= 5 else 0
        ma20 = sum(d["close"] for d in kline_data[-20:]) / 20 if len(kline_data) >= 20 else 0

        recent_high = max(d["high"] for d in kline_data[-20:]) if len(kline_data) >= 20 else 0
        recent_low = min(d["low"] for d in kline_data[-20:]) if len(kline_data) >= 20 else 0

        return [
            "## 📉 技术分析",
            "",
            f"**{symbol} ({data.get('period', 'daily')})**",
            "",
            "| 指标 | 数值 | 信号 |",
            "|------|------|------|",
            f"| 最新收盘 | ¥{latest['close']:.2f} | - |",
            f"| MA5 | ¥{ma5:.2f} | {'多头' if latest['close'] > ma5 else '空头'} |",
            f"| MA20 | ¥{ma20:.2f} | {'多头' if latest['close'] > ma20 else '空头'} |",
            f"| 20日最高 | ¥{recent_high:.2f} | - |",
            f"| 20日最低 | ¥{recent_low:.2f} | - |",
            ""
        ]

    def _format_news_section(self, data: Dict[str, Any]) -> List[str]:
        """Format news data as Markdown"""
        if not data or not data.get("news"):
            return ["## 📰 相关新闻", "", "暂无相关新闻", ""]

        news_list = data.get("news", [])

        lines = [
            "## 📰 相关新闻",
            "",
            f"共 {len(news_list)} 条新闻",
            ""
        ]

        for i, news in enumerate(news_list[:5], 1):
            title = news.get("title", "")
            tag = news.get("tag", "")
            time = news.get("time", "")
            lines.append(f"{i}. **{title}**")
            if tag:
                lines.append(f"   - 标签: {tag}")
            if time:
                lines.append(f"   - 时间: {time}")
            lines.append("")

        return lines

    def _format_sector_section(self, data: Dict[str, Any]) -> List[str]:
        """Format sector data as Markdown"""
        if not data or data.get("error"):
            return ["## 🏭 板块数据", "", "暂无板块数据", ""]

        sector = data.get("sector", "")
        stocks = data.get("stocks", [])
        change_pct = data.get("change_pct", 0)

        lines = [
            f"## 🏭 板块分析: {sector}",
            "",
            f"板块涨跌: {'▲' if change_pct >= 0 else '▼'}{abs(change_pct):.2f}%",
            "",
            "**成分股**:",
            "",
            "| 代码 | 名称 | 涨跌幅 |",
            "|------|------|--------|"
        ]

        for stock in stocks[:10]:
            sym = stock.get("symbol", "")
            name = stock.get("name", "")
            pct = stock.get("change_pct", 0)
            arrow = "▲" if pct >= 0 else "▼"
            lines.append(f"| {sym} | {name} | {arrow}{abs(pct):.2f}% |")

        lines.append("")
        return lines

    def _format_macro_section(self, data: Dict[str, Any]) -> List[str]:
        """Format macro data as Markdown"""
        if not data or data.get("error"):
            return ["## 🌏 宏观经济", "", "暂无宏观数据", ""]

        indicator = data.get("indicator", "")
        name = data.get("name", "")
        latest = data.get("latest", {})

        lines = [
            f"## 🌏 宏观经济: {name} ({indicator})",
            ""
        ]

        if latest:
            lines.append("| 指标 | 数值 |")
            lines.append("|------|------|")
            for key, value in latest.items():
                if value is not None and not key.startswith("_"):
                    lines.append(f"| {key} | {value} |")
            lines.append("")

        return lines

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get workflow by ID"""
        return self._workflows.get(workflow_id)

    def list_workflows(self, limit: int = 20) -> List[Workflow]:
        """List recent workflows"""
        workflows = list(self._workflows.values())
        workflows.sort(key=lambda w: w.created_at, reverse=True)
        return workflows[:limit]


_engine: Optional[WorkflowEngine] = None


def get_workflow_engine() -> WorkflowEngine:
    """Get singleton WorkflowEngine instance"""
    global _engine
    if _engine is None:
        _engine = WorkflowEngine()
    return _engine
