"""Serve `check-pr-fully-clean.py`'s GitHub reads from a pre-gathered payload.

Morrison-Lab/ai-config#2441: the script hard-required the `gh` CLI, so the
corpus's one deterministic instrument for the highest-stakes decision it
automates was unavailable in exactly the remote/web sessions that most need
it, and the fallback was the model reasoning `algorithmatize-checks` exists
to displace.

An MCP tool cannot be called from inside a subprocess -- MCP tools belong to
the agent, not to the script -- so "use MCP" resolves to a split rather than
to a different fetcher implementation:

    the AGENT retrieves (pull_request_read, via tool-mappings.md)
    the SCRIPT judges (the verdict scan, thread accounting, check accounting)

`PullRequest` already takes an injectable `fetcher: Callable[[List[str]], str]`
that receives a `gh` argv and returns its stdout, so nothing in
`scripts/lib/pull_request.py` changes. This module supplies an alternative
fetcher that dispatches on the argv shape and returns the corresponding slice
of a caller-supplied payload.

THE CENTRAL SAFETY PROPERTY: a missing payload key is an ERROR, never an empty
result. An absent `check_runs` that returned `[]` would score as "no checks
pending, nothing failed" -- i.e. it would manufacture a clean verdict out of
missing data, on the one instrument whose job is to withhold that verdict.
Every lookup here raises instead (`fail-fast.md`).
"""

import json
from typing import Any, Dict, List


class PayloadError(RuntimeError):
    """A payload was absent, malformed, or missing a key the script needs."""


# The four `gh` command shapes the script issues. Kept as an explicit
# inventory rather than matched loosely, so an unrecognized command is a loud
# error rather than a silently empty answer.
_PR_VIEW = ("pr", "view")
_REPO_VIEW = ("repo", "view")


def _require(payload: Dict[str, Any], key: str, what: str) -> Any:
    if key not in payload:
        raise PayloadError(
            f"payload has no {key!r} key, needed for {what}.\n"
            "Gather it per tool-mappings.md and include it; an absent value is "
            "not treated as an empty one, because that would score clean."
        )
    return payload[key]


class PayloadFetcher:
    """A `fetcher` that answers from *payload* instead of running `gh`.

    Instances are callables so they drop straight into
    ``PullRequest(..., fetcher=...)`` and into this script's own `run_cmd`
    call sites.
    """

    def __init__(self, payload: Dict[str, Any]):
        if not isinstance(payload, dict):
            raise PayloadError(
                f"payload must be a JSON object, got {type(payload).__name__}."
            )
        self.payload = payload
        self.seen: List[List[str]] = []

    @classmethod
    def from_file(cls, path: str) -> "PayloadFetcher":
        try:
            with open(path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except FileNotFoundError:
            raise PayloadError(f"payload file not found: {path}")
        except json.JSONDecodeError as exc:
            raise PayloadError(f"payload file is not valid JSON: {path}: {exc}")
        return cls(raw)

    def __call__(self, cmd: List[str]) -> str:
        self.seen.append(list(cmd))
        if not cmd or cmd[0] != "gh":
            raise PayloadError(f"not a gh command: {cmd!r}")

        head = tuple(cmd[1:3])

        if head == _PR_VIEW:
            return json.dumps(_require(self.payload, "pr", "the pull request's fields"))

        if head == _REPO_VIEW:
            # resolve_repo consumes bare stdout, not JSON.
            return str(_require(self.payload, "repo", "repository resolution"))

        if cmd[1] == "api":
            return self._api(cmd[2])

        raise PayloadError(
            f"no payload mapping for command: {' '.join(cmd)}.\n"
            "This fetcher covers `gh pr view`, `gh repo view`, and the two "
            "`gh api` reads. A new call site needs a new payload key."
        )

    def _api(self, path: str) -> str:
        if "/check-runs" in path:
            runs = _require(self.payload, "check_runs", "check-run status")
            if isinstance(runs, list):
                # Accept the bare list as well as the REST envelope, since an
                # agent transcribing from pull_request_read naturally produces
                # the list.
                runs = {"check_runs": runs}
            if not isinstance(runs, dict) or "check_runs" not in runs:
                raise PayloadError(
                    "'check_runs' must be a list, or an object with a "
                    "'check_runs' key."
                )
            return json.dumps(runs)

        if "/actions/runs/" in path:
            run_id = path.rstrip("/").rsplit("/", 1)[-1]
            runs = self.payload.get("actions_runs")
            if not isinstance(runs, dict) or run_id not in runs:
                # Deliberately NOT an error. The workflow-path lookup is a
                # refinement used to attribute a check run to a workflow file;
                # the script already tolerates it being unavailable, and
                # demanding every Actions run id up front would make the
                # payload unbuildable without knowing the answer first.
                return json.dumps({})
            return json.dumps(runs[run_id])

        raise PayloadError(f"no payload mapping for gh api path: {path}")
