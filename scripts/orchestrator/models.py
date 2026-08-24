"""Data models and enums for the persistent orchestrator."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
import time
from typing import Any, Dict, List, Optional
import uuid


class TaskStatus(str, Enum):
    """Lifecycle status of an orchestration task."""

    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"


class TaskPriority(int, Enum):
    """Priority levels for task scheduling (higher number = higher priority)."""

    LOW = 10
    NORMAL = 50
    HIGH = 80
    CRITICAL = 100


@dataclass
class Task:
    """Represents a discrete unit of work in the orchestration queue."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    role: str = "generic"  # Required specialized subagent role / capability
    priority: int = TaskPriority.NORMAL.value
    status: TaskStatus = TaskStatus.PENDING
    payload: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300
    heartbeat_at: Optional[float] = None
    assigned_worker_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary representation."""
        data = asdict(self)
        data["status"] = self.status.value if isinstance(self.status, TaskStatus) else self.status
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Task:
        """Construct task from dictionary representation."""
        data = dict(data)
        if "status" in data and isinstance(data["status"], str):
            data["status"] = TaskStatus(data["status"])
        if isinstance(data.get("payload"), str):
            data["payload"] = json.loads(data["payload"])
        if isinstance(data.get("result"), str):
            data["result"] = json.loads(data["result"])
        if isinstance(data.get("depends_on"), str):
            data["depends_on"] = json.loads(data["depends_on"])
        return cls(**data)


@dataclass
class TaskEvent:
    """Audit log event representing a state change or milestone for a task."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    event_type: str = ""  # e.g., CREATED, CLAIMED, HEARTBEAT, SPAWNED_CHILD, COMPLETED, FAILED
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SubagentResult:
    """Output returned by a specialized subagent upon task execution."""

    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    spawned_tasks: List[Task] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    execution_time_seconds: float = 0.0


@dataclass
class SubagentContext:
    """Execution context passed to a specialized subagent."""

    task: Task
    state_store: Any  # StateStore reference
    worker_id: str
    workspace_root: str
    abort_requested: bool = False
