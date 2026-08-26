import json
import subprocess
from typing import Dict, List, Optional, Tuple, Any, Callable

def default_fetcher(cmd: List[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout

class Review:
    def __init__(self, data: Dict[str, Any]):
        self.state: str = data.get("state", "").upper()
        self.submitted_at: str = data.get("submittedAt", "")
        self.body: str = data.get("body", "")
        self.commit_oid: str = data.get("commit", {}).get("oid", "") if data.get("commit") else ""
        self.author_login: str = (data.get("author") or {}).get("login", "")

class IssueComment:
    def __init__(self, data: Dict[str, Any]):
        self.body: str = data.get("body", "")
        self.author_login: str = (data.get("author") or {}).get("login", "")
        self.created_at: str = data.get("createdAt", "")

class CheckRun:
    def __init__(self, data: Dict[str, Any]):
        self.name: str = data.get("name", "")
        self.status: str = data.get("status", "")
        self.conclusion: Optional[str] = data.get("conclusion")
        self.html_url: str = data.get("html_url", "")

class PullRequest:
    def __init__(self, pr_num: str, repo: str, fetcher: Callable[[List[str]], str] = default_fetcher):
        self.pr_num = str(pr_num)
        self.repo = repo
        self._fetcher = fetcher
        self._data = self._fetch_pr_data()
        self._check_runs = None
        
    def _fetch_pr_data(self) -> Dict[str, Any]:
        fields = [
            "headRefOid", "headRefName", "state", "commits", 
            "reviewDecision", "reviews", "comments"
        ]
        cmd = ["gh", "pr", "view", self.pr_num, "--repo", self.repo, "--json", ",".join(fields)]
        stdout = self._fetcher(cmd)
        return json.loads(stdout)

    @property
    def head_sha(self) -> str:
        return self._data.get("headRefOid", "")

    @property
    def branch(self) -> str:
        return self._data.get("headRefName", "")

    @property
    def state(self) -> str:
        return self._data.get("state", "")

    @property
    def review_decision(self) -> str:
        return self._data.get("reviewDecision") or ""

    @property
    def commit_date(self) -> str:
        commits = self._data.get("commits", [])
        if commits:
            return commits[-1].get("committedDate", "")
        return ""

    def get_reviews(self) -> List[Review]:
        return [Review(r) for r in self._data.get("reviews", [])]

    def get_comments(self) -> List[IssueComment]:
        return [IssueComment(c) for c in self._data.get("comments", [])]

    def get_check_runs(self) -> List[CheckRun]:
        if self._check_runs is None:
            cmd = ["gh", "api", f"repos/{self.repo}/commits/{self.head_sha}/check-runs?per_page=100"]
            stdout = self._fetcher(cmd)
            self._check_runs = [CheckRun(cr) for cr in json.loads(stdout).get("check_runs", [])]
        return self._check_runs

