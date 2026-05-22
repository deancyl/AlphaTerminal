"""
Agentic Workflow Services

Lightweight agentic workflow engine for natural language task orchestration.

Key Features:
- Tool registry with pre-defined data fetching tools
- Workflow engine with LLM-powered intent parsing
- Multi-step workflow execution with progress tracking
- Markdown report generation

Architecture:
    User Query → QueryClassifier → WorkflowEngine → ToolRegistry → LLM → ReportGenerator
"""
