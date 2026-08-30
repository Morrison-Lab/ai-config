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

THE CENTRAL SAFETY PROPERTY: unusable payload data must exit 2, never 1.
Exit 1 is this script's *not-clean verdict*, so a data problem reported as
exit 1 is indistinguishable from a real finding about the PR -- the laundering
shape `run_cmd`'s own comments describe.

Note what this rationale is NOT. An absent `check_runs` read as `[]` does not
score clean: `check_ci_runs` already emits "No check runs found for SHA ..."
and returns not-clean. Measured 2026-08-30. Reading absent data as empty would
therefore produce exit 1 WITH a finding bullet, which is worse than a crash
rather than better, because it invents a finding. Raising is still correct;
the reason is laundering, not a false clean.

The one place a false clean WAS reachable is guarded explicitly below: an
absent `headRefOid` leaves the head SHA empty, and the verdict scan's
`sha_short in body` test makes `"" in body` true for every comment, so a
review of an unrelated commit satisfied the quorum. Unreachable through `gh`,
which always returns a head SHA; reachable through a hand-built payload, which
is exactly what this module accepts.
"""

import json
from typing import Any, Dict, List


class PayloadError(Exception):
    """A payload was absent, malformed, or missing a key the script needs.

    Deliberately NOT a RuntimeError. Two helpers in check-pr-fully-clean.py
    catch RuntimeError and degrade silently (returning None or ""), which
    would swallow a payload error into a finding bullet at exit 1 -- the
    laundering this module exists to prevent (`fail-fast.md`).
    """


# Exact-match heads for the two subcommand shapes. The two `gh api` paths are
# matched by substring below, which is looser; an unrecognized command still
# raises rather than returning an empty answer.
_PR_VIEW = ("pr", "view")
_REPO_VIEW = ("repo", "view")


def _require(payload: Dict[str, Any], key: str, what: str) -> Any:
    if key not in payload:
        raise PayloadError(
            f"payload has no {key!r} key, needed for {what}.\n"
            "Gather it per shared/workflow/fully-clean.md and include it. An "
            "absent value is not substituted with an empty one, because that "
            "would report a data problem as a finding about the PR."
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
            return json.dumps(self._pr())

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

    def _pr(self) -> Dict[str, Any]:
        """Return the `pr` object, refusing shapes that would score falsely.

        `headRefOid` is checked first and hardest. The verdict scan tests
        `sha[:7] in body` to decide whether a review evaluated HEAD, and an
        empty SHA makes that true for EVERY comment -- so a payload missing
        this one field turns a review of an unrelated commit into a clean
        verdict at quorum. Measured 2026-08-30 before this guard existed:
        exit 0, "FULLY CLEAN on HEAD " with nothing after it.

        The container type checks exist for a duller reason: a wrong-typed
        value raises AttributeError deep in pull_request.py, and an
        AttributeError is not a PayloadError, so it reached the interpreter as
        exit 1 -- this script's not-clean verdict.
        """
        pr = _require(self.payload, "pr", "the pull request's fields")
        if not isinstance(pr, dict):
            raise PayloadError(
                f"payload 'pr' must be an object, got {type(pr).__name__}."
            )

        sha = pr.get("headRefOid")
        if not isinstance(sha, str) or not sha.strip():
            raise PayloadError(
                "payload 'pr' has no usable 'headRefOid'.\n"
                "This is the head SHA every review is matched against; an empty "
                "one matches every comment, so a review of an unrelated commit "
                "would satisfy the quorum. If you gathered this from "
                "pull_request_read, map `head.sha` to `headRefOid`."
            )

        for key, want in (("commits", list), ("reviews", list), ("comments", list)):
            val = pr.get(key)
            if val is not None and not isinstance(val, want):
                raise PayloadError(
                    f"payload 'pr.{key}' must be a {want.__name__}, got "
                    f"{type(val).__name__}."
                )
        for key in ("reviews", "comments", "commits"):
            for i, item in enumerate(pr.get(key) or []):
                if not isinstance(item, dict):
                    raise PayloadError(
                        f"payload 'pr.{key}[{i}]' must be an object, got "
                        f"{type(item).__name__}."
                    )
        return pr

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
            for i, item in enumerate(runs.get("check_runs") or []):
                if not isinstance(item, dict):
                    raise PayloadError(
                        f"payload 'check_runs[{i}]' must be an object, got "
                        f"{type(item).__name__}."
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
