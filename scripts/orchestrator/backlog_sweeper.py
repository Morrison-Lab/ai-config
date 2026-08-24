"""Automated backlog sweeper and issue pipeline ingestion engine.

Fetches GitHub issues, deduplicates against active tasks/PRs, and builds
multi-model execution DAGs (Research -> Coder -> Adversarial Review -> Test -> PR).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional

from .models import Task, TaskPriority, TaskStatus
from .state_store import StateStore
from .task_queue import TaskQueue

logger = logging.getLogger("orchestrator.sweeper")


class BacklogSweeper:
    """Ingests open repository issues and orchestrates their end-to-end resolution."""

    def __init__(self, state_store: StateStore, repo: Optional[str] = None):
        self.store = state_store
        self.queue = TaskQueue(state_store)
        self.repo = repo

    def fetch_open_issues(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Query GitHub CLI for currently open issues."""
        if not shutil.which("gh"):
            logger.warning("gh CLI not found on PATH. Using mock backlog.")
            return []

        cmd = ["gh", "issue", "list", "--limit", str(limit), "--json", "number,title,body,labels,createdAt,url"]
        if self.repo:
            cmd.extend(["-R", self.repo])

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode == 0:
                return json.loads(proc.stdout)
            else:
                logger.error("Failed to list issues: %s", proc.stderr)
                return []
        except Exception as exc:
            logger.error("Error invoking gh issue list: %s", exc)
            return []

    def ingest_issue(self, issue: Dict[str, Any], priority: int = TaskPriority.NORMAL.value) -> List[Task]:
        """Convert a single GitHub issue into a multi-agent orchestrated DAG."""
        issue_num = issue["number"]
        issue_title = issue["title"]
        issue_body = issue.get("body", "")

        # Check if already enqueued in state store
        existing = self.store.find_tasks_by_payload_field("issue_number", issue_num, limit=1)
        if existing:
            t = existing[0]
            logger.info("Issue #%d is already tracked in task %s (status=%s)", issue_num, t.id, t.status)
            return []

        # Stage 1: Triage & Research (Ollama / Opencode Free / Local)
        triage_task = Task(
            title=f"#{issue_num}: Triage & Research - {issue_title[:50]}",
            role="researcher",
            priority=priority,
            payload={
                "issue_number": issue_num,
                "title": issue_title,
                "body": issue_body,
                "stage": "research",
                "recommended_tier": "local_fast",
            },
        )

        # Stage 2: Implementation & Fix (Claude / Agy / Frontier)
        coder_task = Task(
            title=f"#{issue_num}: Implement Solution - {issue_title[:50]}",
            role="coder",
            priority=priority,
            depends_on=[triage_task.id],
            payload={
                "issue_number": issue_num,
                "title": issue_title,
                "stage": "implementation",
                "branch_name": f"fix-issue-{issue_num}",
                "recommended_tier": "standard_code",
            },
        )

        # Stage 3: Adversarial Self-Review (OpenRouter / Codex / Cross-family model)
        review_task = Task(
            title=f"#{issue_num}: Adversarial Code Review - {issue_title[:50]}",
            role="reviewer",
            priority=priority,
            depends_on=[coder_task.id],
            payload={
                "issue_number": issue_num,
                "title": issue_title,
                "stage": "adversarial_review",
                "recommended_tier": "adversarial_review",
                "author_family": "claude",
            },
        )

        # Stage 4: Automated Verification (Local test runner)
        test_task = Task(
            title=f"#{issue_num}: Verify Quality Gates - {issue_title[:50]}",
            role="tester",
            priority=priority,
            depends_on=[review_task.id],
            payload={
                "issue_number": issue_num,
                "title": issue_title,
                "stage": "test_verification",
                "test_commands": ["python scripts/validate-skills.py", "python scripts/check-links.py"],
            },
        )

        dag = [triage_task, coder_task, review_task, test_task]
        self.queue.enqueue_dag(dag)
        logger.info("Ingested Issue #%d into orchestration DAG (4 tasks created)", issue_num)
        return dag

    def ingest_backlog(self, limit: int = 10) -> int:
        """Ingest open issues up to limit into the queue."""
        issues = self.fetch_open_issues(limit=limit)
        total_ingested = 0
        for issue in issues:
            created = self.ingest_issue(issue)
            if created:
                total_ingested += 1
        return total_ingested
