"""Dynamic task queue with DAG dependency resolution and priority scheduling."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from .models import Task, TaskPriority, TaskStatus
from .state_store import StateStore


class CycleDetectedError(ValueError):
    """Raised when a task dependency cycle is detected."""


class TaskQueue:
    """Dynamic task queue managing priorities, DAG dependencies, and dynamic expansions."""

    def __init__(self, state_store: StateStore):
        self.store = state_store

    def enqueue(self, task: Task) -> Task:
        """Enqueue a single task."""
        if task.depends_on:
            self._validate_dependencies(task.id, task.depends_on)
        return self.store.create_task(task)

    def enqueue_dag(self, tasks: List[Task]) -> List[Task]:
        """Enqueue a collection of tasks representing a DAG.

        Validates that there are no internal circular dependencies before inserting.
        """
        self._validate_dag(tasks)
        for t in tasks:
            self.enqueue(t)
        return tasks

    def enqueue_child_tasks(self, parent_task_id: str, child_tasks: List[Task]) -> List[Task]:
        """Dynamically enqueue child tasks spawned by an active task.

        Links them to the parent task and registers dynamic events.
        """
        for child in child_tasks:
            child.parent_task_id = parent_task_id
            self.enqueue(child)
            self.store.add_event(
                parent_task_id,
                "SPAWNED_CHILD_TASK",
                {"child_task_id": child.id, "title": child.title, "role": child.role},
            )
        return child_tasks

    def dequeue_ready(self, role: Optional[str] = None, limit: int = 10) -> List[Task]:
        """Fetch tasks ready for execution, sorted by priority and creation time."""
        # First resolve any blocked tasks whose dependencies may have completed
        self.store.resolve_blocked_tasks()
        return self.store.list_tasks(status=TaskStatus.READY, role=role, limit=limit)

    def resolve_dependencies(self) -> int:
        """Resolve all blocked dependencies."""
        return self.store.resolve_blocked_tasks()

    def get_stats(self) -> Dict[str, Any]:
        """Return counts and statistics for tasks across all states."""
        all_tasks = self.store.list_tasks(limit=10000)
        counts: Dict[str, int] = {
            TaskStatus.PENDING.value: 0,
            TaskStatus.READY.value: 0,
            TaskStatus.RUNNING.value: 0,
            TaskStatus.COMPLETED.value: 0,
            TaskStatus.FAILED.value: 0,
            TaskStatus.CANCELLED.value: 0,
            TaskStatus.BLOCKED.value: 0,
        }
        roles: Dict[str, int] = {}
        for t in all_tasks:
            status_val = t.status.value if isinstance(t.status, TaskStatus) else str(t.status)
            counts[status_val] = counts.get(status_val, 0) + 1
            roles[t.role] = roles.get(t.role, 0) + 1

        return {
            "total_tasks": len(all_tasks),
            "status_counts": counts,
            "role_counts": roles,
            "active_tasks": counts.get(TaskStatus.RUNNING.value, 0),
            "ready_tasks": counts.get(TaskStatus.READY.value, 0),
            "blocked_tasks": counts.get(TaskStatus.BLOCKED.value, 0),
            "completed_tasks": counts.get(TaskStatus.COMPLETED.value, 0),
            "failed_tasks": counts.get(TaskStatus.FAILED.value, 0),
        }

    def _validate_dependencies(self, task_id: str, depends_on: List[str]) -> None:
        """Check if adding these dependencies creates an immediate self-dependency or cycle."""
        unique_deps = list(dict.fromkeys(depends_on))
        if task_id in unique_deps:
            raise CycleDetectedError(f"Task {task_id} cannot depend on itself.")

        # Depth-first search through existing dependencies
        visited: Set[str] = set()

        def dfs(curr_id: str):
            if curr_id == task_id:
                raise CycleDetectedError(f"Circular dependency detected between {task_id} and {curr_id}.")
            if curr_id in visited:
                return
            visited.add(curr_id)
            existing_deps = self.store.get_dependencies(curr_id)
            for dep in existing_deps:
                dfs(dep)

        for dep_id in unique_deps:
            dfs(dep_id)

    def _validate_dag(self, tasks: List[Task]) -> None:
        """Validate an entire in-memory DAG for circular references using Kahn's algorithm."""
        task_map = {t.id: t for t in tasks}
        in_degree: Dict[str, int] = {t.id: 0 for t in tasks}
        adj: Dict[str, List[str]] = {t.id: [] for t in tasks}

        for t in tasks:
            for dep_id in set(t.depends_on):
                if dep_id in task_map:
                    adj[dep_id].append(t.id)
                    in_degree[t.id] += 1

        queue = [t_id for t_id, deg in in_degree.items() if deg == 0]
        visited_count = 0

        while queue:
            node = queue.pop(0)
            visited_count += 1
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count != len(tasks):
            raise CycleDetectedError("Circular dependency detected within task DAG.")
