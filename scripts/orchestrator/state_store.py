"""SQLite-backed persistent state store for the orchestration loop."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, Generator, List, Optional

from .models import Task, TaskEvent, TaskPriority, TaskStatus


class StateStore:
    """ACID-compliant SQLite state database for persistent task and worker coordination."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        if db_path == ":memory:":
            self._connect_uri = "file:memdb_shared?mode=memory&cache=shared"
            self._is_uri = True
        elif db_path.startswith("file:"):
            self._connect_uri = db_path
            self._is_uri = True
        else:
            self._connect_uri = db_path
            self._is_uri = False
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        self._lock = threading.RLock()
        self._local = threading.local()
        self._connections: List[sqlite3.Connection] = []
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            if self._is_uri:
                conn = sqlite3.connect(self._connect_uri, uri=True, timeout=30.0, check_same_thread=False)
            else:
                conn = sqlite3.connect(self._connect_uri, timeout=30.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for high concurrency
            if not self._is_uri:
                conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            self._local.conn = conn
            with self._lock:
                self._connections.append(conn)
        return self._local.conn

    def add_event(self, task_id: str, event_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Add an audit event for a task."""
        now = time.time()
        import uuid
        event_id = f"{task_id}-{event_type.lower()}-{uuid.uuid4()}"
        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO task_events (id, task_id, event_type, details, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, task_id, event_type, json.dumps(details or {}), now),
            )

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager for thread-safe database transactions."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                yield cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _init_schema(self) -> None:
        """Initialize database tables and indices."""
        with self.transaction() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    role TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 50,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    payload TEXT NOT NULL DEFAULT '{}',
                    result TEXT DEFAULT NULL,
                    error TEXT DEFAULT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    timeout_seconds INTEGER NOT NULL DEFAULT 300,
                    heartbeat_at REAL DEFAULT NULL,
                    assigned_worker_id TEXT DEFAULT NULL,
                    parent_task_id TEXT DEFAULT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    started_at REAL DEFAULT NULL,
                    completed_at REAL DEFAULT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS task_dependencies (
                    task_id TEXT NOT NULL,
                    depends_on_task_id TEXT NOT NULL,
                    PRIMARY KEY (task_id, depends_on_task_id),
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    FOREIGN KEY (depends_on_task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS task_events (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '{}',
                    timestamp REAL NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS task_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );
                """
            )

            # Performance indices
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority DESC, created_at ASC);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_role ON tasks(role);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_deps_parent ON task_dependencies(depends_on_task_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_events_task ON task_events(task_id, timestamp ASC);")

    def create_task(self, task: Task) -> Task:
        """Insert a new task into persistent storage."""
        now = time.time()
        import uuid
        task.created_at = task.created_at or now
        task.updated_at = now

        # Determine initial status: if it has dependencies, mark BLOCKED, otherwise READY or PENDING
        if task.depends_on:
            task.status = TaskStatus.BLOCKED
        elif task.status == TaskStatus.PENDING:
            task.status = TaskStatus.READY

        with self.transaction() as cur:
            cur.execute(
                """
                INSERT INTO tasks (
                    id, title, role, priority, status, payload, result, error,
                    retry_count, max_retries, timeout_seconds, heartbeat_at,
                    assigned_worker_id, parent_task_id, created_at, updated_at,
                    started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.title,
                    task.role,
                    task.priority,
                    task.status.value,
                    json.dumps(task.payload),
                    json.dumps(task.result) if task.result is not None else None,
                    task.error,
                    task.retry_count,
                    task.max_retries,
                    task.timeout_seconds,
                    task.heartbeat_at,
                    task.assigned_worker_id,
                    task.parent_task_id,
                    task.created_at,
                    task.updated_at,
                    task.started_at,
                    task.completed_at,
                ),
            )

            for dep_id in set(task.depends_on):
                cur.execute(
                    """
                    INSERT OR IGNORE INTO task_dependencies (task_id, depends_on_task_id)
                    VALUES (?, ?)
                    """,
                    (task.id, dep_id),
                )

            # Record event with unique UUID
            event_id = f"{task.id}-created-{uuid.uuid4().hex}"
            cur.execute(
                """
                INSERT INTO task_events (id, task_id, event_type, details, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    task.id,
                    "TASK_CREATED",
                    json.dumps({"title": task.title, "role": task.role, "status": task.status.value}),
                    now,
                ),
            )
        return task

    def batch_create_tasks(self, tasks: List[Task]) -> List[Task]:
        """Atomically insert multiple tasks and their dependencies in a two-pass transaction."""
        now = time.time()
        import uuid
        with self.transaction() as cur:
            # Pass 1: Insert all task master rows
            for task in tasks:
                task.created_at = task.created_at or now
                task.updated_at = now
                if task.depends_on:
                    task.status = TaskStatus.BLOCKED
                elif task.status == TaskStatus.PENDING:
                    task.status = TaskStatus.READY

                cur.execute(
                    """
                    INSERT INTO tasks (
                        id, title, role, priority, status, payload, result, error,
                        retry_count, max_retries, timeout_seconds, heartbeat_at,
                        assigned_worker_id, parent_task_id, created_at, updated_at,
                        started_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task.id,
                        task.title,
                        task.role,
                        task.priority,
                        task.status.value,
                        json.dumps(task.payload),
                        json.dumps(task.result) if task.result is not None else None,
                        task.error,
                        task.retry_count,
                        task.max_retries,
                        task.timeout_seconds,
                        task.heartbeat_at,
                        task.assigned_worker_id,
                        task.parent_task_id,
                        task.created_at,
                        task.updated_at,
                        task.started_at,
                        task.completed_at,
                    ),
                )

            # Pass 2: Insert all dependency rows
            for task in tasks:
                for dep_id in set(task.depends_on):
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO task_dependencies (task_id, depends_on_task_id)
                        VALUES (?, ?)
                        """,
                        (task.id, dep_id),
                    )

                event_id = f"{task.id}-created-{uuid.uuid4().hex}"
                cur.execute(
                    """
                    INSERT INTO task_events (id, task_id, event_type, details, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        task.id,
                        "TASK_CREATED",
                        json.dumps({"title": task.title, "role": task.role, "status": task.status.value}),
                        now,
                    ),
                )
        return tasks

    def get_task(self, task_id: str) -> Optional[Task]:
        """Fetch a task by ID including its dependencies."""
        with self.transaction() as cur:
            cur.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cur.fetchone()
            if not row:
                return None
            task_dict = dict(row)
            # Fetch dependencies
            cur.execute("SELECT depends_on_task_id FROM task_dependencies WHERE task_id = ?", (task_id,))
            deps = [r["depends_on_task_id"] for r in cur.fetchall()]
            task_dict["depends_on"] = deps
            return Task.from_dict(task_dict)

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        role: Optional[str] = None,
        limit: int = 100,
    ) -> List[Task]:
        """List tasks matching filter criteria."""
        query = "SELECT * FROM tasks WHERE 1=1"
        params: List[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status.value if isinstance(status, TaskStatus) else status)
        if role:
            query += " AND role = ?"
            params.append(role)
        query += " ORDER BY priority DESC, created_at ASC LIMIT ?"
        params.append(limit)

        with self.transaction() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            results = []
            for row in rows:
                t_dict = dict(row)
                cur.execute("SELECT depends_on_task_id FROM task_dependencies WHERE task_id = ?", (t_dict["id"],))
                t_dict["depends_on"] = [r["depends_on_task_id"] for r in cur.fetchall()]
                results.append(Task.from_dict(t_dict))
            return results

    def find_tasks_by_payload_field(self, field_name: str, value: Any, limit: int = 100) -> List[Task]:
        """Find tasks where payload JSON has field_name == value."""
        import re
        if not re.match(r"^[a-zA-Z0-9_]+$", field_name):
            raise ValueError(f"Invalid field_name identifier: {field_name}")

        query = "SELECT * FROM tasks WHERE json_extract(payload, '$.' || ?) = ? LIMIT ?"
        with self.transaction() as cur:
            cur.execute(query, (field_name, value, limit))
            rows = cur.fetchall()
            results = []
            for row in rows:
                t_dict = dict(row)
                cur.execute("SELECT depends_on_task_id FROM task_dependencies WHERE task_id = ?", (t_dict["id"],))
                t_dict["depends_on"] = [r["depends_on_task_id"] for r in cur.fetchall()]
                results.append(Task.from_dict(t_dict))
            return results

    def claim_task(self, task_id: str, worker_id: str) -> bool:
        """Atomically claim a READY task for execution by a worker."""
        now = time.time()
        import uuid
        with self.transaction() as cur:
            cur.execute(
                """
                UPDATE tasks
                SET status = 'RUNNING',
                    assigned_worker_id = ?,
                    started_at = ?,
                    heartbeat_at = ?,
                    updated_at = ?
                WHERE id = ? AND status = 'READY'
                """,
                (worker_id, now, now, now, task_id),
            )
            claimed = cur.rowcount > 0
            if claimed:
                event_id = f"{task_id}-claimed-{uuid.uuid4().hex}"
                cur.execute(
                    """
                    INSERT INTO task_events (id, task_id, event_type, details, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        task_id,
                        "TASK_CLAIMED",
                        json.dumps({"worker_id": worker_id}),
                        now,
                    ),
                )
            return claimed

    def heartbeat_task(self, task_id: str, worker_id: str) -> bool:
        """Update heartbeat timestamp for a running task to prevent lease expiration."""
        now = time.time()
        with self.transaction() as cur:
            cur.execute(
                """
                UPDATE tasks
                SET heartbeat_at = ?, updated_at = ?
                WHERE id = ? AND assigned_worker_id = ? AND status = 'RUNNING'
                """,
                (now, now, task_id, worker_id),
            )
            return cur.rowcount > 0

    def complete_task(
        self,
        task_id: str,
        result: Dict[str, Any],
        artifacts: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Mark a task as completed, store result/artifacts, and record event."""
        now = time.time()
        import uuid
        with self.transaction() as cur:
            cur.execute(
                """
                UPDATE tasks
                SET status = 'COMPLETED',
                    result = ?,
                    error = NULL,
                    completed_at = ?,
                    updated_at = ?
                WHERE id = ? AND status = 'RUNNING'
                """,
                (json.dumps(result), now, now, task_id),
            )
            success = cur.rowcount > 0
            if success:
                if artifacts:
                    for k, v in artifacts.items():
                        cur.execute(
                            """
                            INSERT INTO task_artifacts (task_id, key, value, created_at)
                            VALUES (?, ?, ?, ?)
                            """,
                            (task_id, k, json.dumps(v), now),
                        )
                event_id = f"{task_id}-completed-{uuid.uuid4().hex}"
                cur.execute(
                    """
                    INSERT INTO task_events (id, task_id, event_type, details, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        task_id,
                        "TASK_COMPLETED",
                        json.dumps({"result_keys": list(result.keys())}),
                        now,
                    ),
                )
            return success

    def fail_task(
        self,
        task_id: str,
        error: str,
        can_retry: bool = True,
        worker_id: Optional[str] = None,
    ) -> bool:
        """Handle task execution failure with retry calculation and status fencing."""
        now = time.time()
        import uuid
        with self.transaction() as cur:
            if worker_id:
                cur.execute(
                    """
                    SELECT retry_count, max_retries FROM tasks
                    WHERE id = ? AND status IN ('RUNNING', 'READY') AND (assigned_worker_id = ? OR assigned_worker_id IS NULL)
                    """,
                    (task_id, worker_id),
                )
            else:
                cur.execute(
                    """
                    SELECT retry_count, max_retries FROM tasks
                    WHERE id = ? AND status IN ('RUNNING', 'READY')
                    """,
                    (task_id,),
                )
            row = cur.fetchone()
            if not row:
                return False

            retries = row["retry_count"]
            max_retries = row["max_retries"]

            if can_retry and retries < max_retries:
                # Requeue for retry
                if worker_id:
                    cur.execute(
                        """
                        UPDATE tasks
                        SET status = 'READY',
                            error = ?,
                            retry_count = retry_count + 1,
                            assigned_worker_id = NULL,
                            heartbeat_at = NULL,
                            updated_at = ?
                        WHERE id = ? AND status IN ('RUNNING', 'READY') AND (assigned_worker_id = ? OR assigned_worker_id IS NULL)
                        """,
                        (error, now, task_id, worker_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE tasks
                        SET status = 'READY',
                            error = ?,
                            retry_count = retry_count + 1,
                            assigned_worker_id = NULL,
                            heartbeat_at = NULL,
                            updated_at = ?
                        WHERE id = ? AND status IN ('RUNNING', 'READY')
                        """,
                        (error, now, task_id),
                    )
                event_type = "TASK_RETRY"
            else:
                if worker_id:
                    cur.execute(
                        """
                        UPDATE tasks
                        SET status = 'FAILED',
                            error = ?,
                            completed_at = ?,
                            updated_at = ?
                        WHERE id = ? AND status IN ('RUNNING', 'READY') AND (assigned_worker_id = ? OR assigned_worker_id IS NULL)
                        """,
                        (error, now, now, task_id, worker_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE tasks
                        SET status = 'FAILED',
                            error = ?,
                            completed_at = ?,
                            updated_at = ?
                        WHERE id = ? AND status IN ('RUNNING', 'READY')
                        """,
                        (error, now, now, task_id),
                    )
                event_type = "TASK_FAILED"

            event_id = f"{task_id}-{event_type.lower()}-{uuid.uuid4().hex}"
            cur.execute(
                """
                INSERT INTO task_events (id, task_id, event_type, details, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    task_id,
                    event_type,
                    json.dumps({"error": error, "retry_count": retries + (1 if event_type == "TASK_RETRY" else 0)}),
                    now,
                ),
            )
            return True

    def cancel_task(self, task_id: str, reason: str = "") -> bool:
        """Cancel a pending, ready, or running task."""
        now = time.time()
        with self.transaction() as cur:
            cur.execute(
                """
                UPDATE tasks
                SET status = 'CANCELLED',
                    error = ?,
                    completed_at = ?,
                    updated_at = ?
                WHERE id = ? AND status NOT IN ('COMPLETED', 'FAILED', 'CANCELLED')
                """,
                (reason or "Cancelled by user", now, now, task_id),
            )
            cancelled = cur.rowcount > 0
            if cancelled:
                cur.execute(
                    """
                    INSERT INTO task_events (id, task_id, event_type, details, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        f"{task_id}-cancelled-{now}",
                        task_id,
                        "TASK_CANCELLED",
                        json.dumps({"reason": reason}),
                        now,
                    ),
                )
            return cancelled

    def retry_task(self, task_id: str, reason: str = "Manual retry requested via CLI") -> bool:
        """Atomically retry a FAILED or CANCELLED task by resetting it to READY."""
        now = time.time()
        import uuid
        with self.transaction() as cur:
            cur.execute(
                """
                UPDATE tasks
                SET status = 'READY',
                    error = ?,
                    retry_count = retry_count + 1,
                    assigned_worker_id = NULL,
                    heartbeat_at = NULL,
                    completed_at = NULL,
                    updated_at = ?
                WHERE id = ? AND status IN ('FAILED', 'CANCELLED')
                """,
                (reason, now, task_id),
            )
            success = cur.rowcount > 0
            if success:
                event_id = f"{task_id}-retry-{uuid.uuid4().hex}"
                cur.execute(
                    """
                    INSERT INTO task_events (id, task_id, event_type, details, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (event_id, task_id, "TASK_RETRY", json.dumps({"reason": reason}), now),
                )
            return success

    def get_ready_tasks(self, limit: int = 50) -> List[Task]:
        """Fetch tasks in READY status, sorted by priority and creation date."""
        return self.list_tasks(status=TaskStatus.READY, limit=limit)

    def get_dependencies(self, task_id: str) -> List[str]:
        """Get IDs of all tasks this task depends on."""
        with self.transaction() as cur:
            cur.execute("SELECT depends_on_task_id FROM task_dependencies WHERE task_id = ?", (task_id,))
            return [row["depends_on_task_id"] for row in cur.fetchall()]

    def get_dependents(self, task_id: str) -> List[str]:
        """Get IDs of all tasks that depend on this task."""
        with self.transaction() as cur:
            cur.execute("SELECT task_id FROM task_dependencies WHERE depends_on_task_id = ?", (task_id,))
            return [row["task_id"] for row in cur.fetchall()]

    def resolve_blocked_tasks(self) -> int:
        """Check all BLOCKED tasks and transition them to READY if dependencies are met."""
        now = time.time()
        unblocked_count = 0
        with self.transaction() as cur:
            # Find all BLOCKED tasks
            cur.execute("SELECT id FROM tasks WHERE status = 'BLOCKED'")
            blocked_tasks = [row["id"] for row in cur.fetchall()]

            for t_id in blocked_tasks:
                # Check if any dependencies are still not COMPLETED
                cur.execute(
                    """
                    SELECT t.status FROM task_dependencies d
                    JOIN tasks t ON d.depends_on_task_id = t.id
                    WHERE d.task_id = ?
                    """,
                    (t_id,),
                )
                statuses = [r["status"] for r in cur.fetchall()]

                # If any dependency failed or cancelled, fail the blocked task
                if any(s in ("FAILED", "CANCELLED") for s in statuses):
                    cur.execute(
                        """
                        UPDATE tasks
                        SET status = 'FAILED',
                            error = 'Dependency failed or cancelled',
                            completed_at = ?,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (now, now, t_id),
                    )
                    cur.execute(
                        """
                        INSERT INTO task_events (id, task_id, event_type, details, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            f"{t_id}-dep-failed-{now}",
                            t_id,
                            "TASK_FAILED",
                            json.dumps({"reason": "Dependency failed or cancelled"}),
                            now,
                        ),
                    )
                # If all dependencies are COMPLETED, unblock to READY
                elif all(s == "COMPLETED" for s in statuses):
                    cur.execute(
                        """
                        UPDATE tasks
                        SET status = 'READY',
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (now, t_id),
                    )
                    cur.execute(
                        """
                        INSERT INTO task_events (id, task_id, event_type, details, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            f"{t_id}-unblocked-{now}",
                            t_id,
                            "TASK_UNBLOCKED",
                            json.dumps({"status": "READY"}),
                            now,
                        ),
                    )
                    unblocked_count += 1
        return unblocked_count

    def reclaim_stale_tasks(self, stale_threshold_seconds: float = 60.0) -> int:
        """Find RUNNING tasks whose heartbeat expired, and reset them to READY for retry."""
        now = time.time()
        cutoff = now - stale_threshold_seconds
        reclaimed_count = 0

        with self.transaction() as cur:
            cur.execute(
                """
                SELECT id, retry_count, max_retries FROM tasks
                WHERE status = 'RUNNING' AND (heartbeat_at IS NULL OR heartbeat_at < ?)
                """,
                (cutoff,),
            )
            stale_tasks = cur.fetchall()

            for row in stale_tasks:
                t_id = row["id"]
                retries = row["retry_count"]
                max_retries = row["max_retries"]

                if retries < max_retries:
                    cur.execute(
                        """
                        UPDATE tasks
                        SET status = 'READY',
                            assigned_worker_id = NULL,
                            heartbeat_at = NULL,
                            retry_count = retry_count + 1,
                            error = 'Lease expired / worker timeout, reclaimed',
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (now, t_id),
                    )
                    cur.execute(
                        """
                        INSERT INTO task_events (id, task_id, event_type, details, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            f"{t_id}-reclaimed-{now}",
                            t_id,
                            "TASK_RECLAIMED",
                            json.dumps({"reason": "Lease heartbeat expired", "retry_count": retries + 1}),
                            now,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE tasks
                        SET status = 'FAILED',
                            error = 'Task timed out with no remaining retries',
                            completed_at = ?,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (now, now, t_id),
                    )
                    cur.execute(
                        """
                        INSERT INTO task_events (id, task_id, event_type, details, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            f"{t_id}-timeout-failed-{now}",
                            t_id,
                            "TASK_FAILED",
                            json.dumps({"reason": "Max retries exceeded on timeout"}),
                            now,
                        ),
                    )
                reclaimed_count += 1
        return reclaimed_count

    def get_events(self, task_id: str) -> List[TaskEvent]:
        """Fetch all audit events for a task."""
        with self.transaction() as cur:
            cur.execute(
                "SELECT * FROM task_events WHERE task_id = ? ORDER BY timestamp ASC",
                (task_id,),
            )
            rows = cur.fetchall()
            events = []
            for r in rows:
                events.append(
                    TaskEvent(
                        id=r["id"],
                        task_id=r["task_id"],
                        event_type=r["event_type"],
                        details=json.loads(r["details"]),
                        timestamp=r["timestamp"],
                    )
                )
            return events

    def get_artifacts(self, task_id: str) -> Dict[str, Any]:
        """Fetch all artifacts produced by a task."""
        with self.transaction() as cur:
            cur.execute("SELECT key, value FROM task_artifacts WHERE task_id = ?", (task_id,))
            rows = cur.fetchall()
            return {r["key"]: json.loads(r["value"]) for r in rows}

    def close(self) -> None:
        """Close all open database connections."""
        with self._lock:
            for conn in self._connections:
                try:
                    conn.close()
                except Exception:
                    pass
            self._connections.clear()
            if hasattr(self._local, "conn"):
                self._local.conn = None
