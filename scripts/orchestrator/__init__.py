"""Persistent Orchestration Loop package.

Backed by an external SQLite state database, dynamic task queue with DAG support,
and specialized sub-agents.
"""

from .engine import OrchestratorEngine, ensure_git_identity
from .models import (
    SubagentResult,
    Task,
    TaskEvent,
    TaskPriority,
    TaskStatus,
)
from .state_store import StateStore
from .subagents import (
    BaseSubagent,
    CoderSubagent,
    CoordinatorSubagent,
    ResearcherSubagent,
    ReviewerSubagent,
    SubagentRegistry,
    TesterSubagent,
)
from .task_queue import TaskQueue

__all__ = [
    "BaseSubagent",
    "CoderSubagent",
    "CoordinatorSubagent",
    "OrchestratorEngine",
    "ResearcherSubagent",
    "ReviewerSubagent",
    "StateStore",
    "SubagentRegistry",
    "SubagentResult",
    "Task",
    "TaskEvent",
    "TaskPriority",
    "TaskQueue",
    "TaskStatus",
    "TesterSubagent",
    "ensure_git_identity",
]
