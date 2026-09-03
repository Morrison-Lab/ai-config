#!/usr/bin/env python3
"""Decide which pull requests a sweep is allowed to touch.

`memories/reviewing-prs.md`, "Only work PRs I opened, am assigned to, or
asked for by name, or the Actions app authored", is the rule. A PR is in
scope when the invoking user opened it, is assigned to it, explicitly asked
for it by number, or the GitHub Actions app authored it -- and an explicit
"do not touch #N" is a veto checked before every one of those arms.

That rule is restated as prose in every sweep that pushes to PRs (`ardia`,
`ardi`, `gia`, `ardiaei`, `mma`, `cascade`, `wrap-up`, `post-merge`,
`sync-with-main`), and the parts that decide it are deterministic:

  1. Actor-form normalization. The same app slug reaches a caller as
     `github-actions[bot]` (REST and the MCP tools), bare `github-actions`
     (GraphQL and `scripts/pr-sweep.py`), or `app/github-actions`
     (`gh pr list --json author`). Forms measured 2026-09-01.
  2. Field-name normalization. The author is `author.login` under
     `gh --json`, `user.login` under REST and `mcp__github__list_pull_requests`,
     and `author.username` on GitLab; assignees are `assignees[].login`,
     bare login strings, or `assignees[].username`, and the MCP list tool
     omits the key entirely on an unassigned PR.
  3. Alias expansion, comparison, and the exclusion veto.

Per `shared/workflow/algorithmatize-checks.md` those belong in an
instrument rather than in nine prose reimplementations, since one
inconsistent restatement is enough to push to a PR that was never in scope
(measured on `UCD-SERG/serodynamics`, 2026-09-01, where a sweep drove four
other members' PRs). The judgment this script does not make is which PR
numbers a request authorizes: the caller passes those as `--requested`, and
passes a "do not touch #N" as `--excluded`, because a mention is not a
request.

Fails closed on identity. With no resolved user the author and assignee
arms are left unevaluated -- not assumed true -- so only explicitly
requested and Actions-app-authored PRs survive, and `identity_resolved` in
the output says so.

Read-only. It classifies; it never pushes, comments, or merges. The full
normalized listing is kept in the output so a caller can still map stacks
over out-of-scope PRs (`skills/ardia/SKILL.md` step 3 needs the bases it is
not allowed to drive).

DRW: no upstream package models this repo's own scope rule. The nearest
existing implementation is the inline `jq` filter in
`skills/chores/SKILL.md` step 1, whose `PR_SCOPE_ALIASES`,
`PR_SCOPE_REQUESTED`, and `PR_SCOPE_EXCLUDED` inputs this script
generalizes; `gh`'s own `--search` filters cannot express the alias or
veto arms.

Usage:

    gh pr list --repo owner/name --state open --limit 200 \\
      --json number,author,assignees,headRefName,baseRefName \\
      | python3 scripts/pr-scope.py --user "$(gh api user --jq .login)"

    python3 scripts/pr-scope.py --repo owner/name --user d-morrison \\
      --alias dem-extra1 --requested 123,456 --excluded 284 --text
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

# The app slug whose PRs are in scope, normalized. `memories/reviewing-prs.md`
# narrows the directive's "workflow-opened" to this author test on purpose,
# because provenance is not observable from the API: a `gha` sync workflow
# handed a `WORKFLOW_TOKEN` posts under that token's own identity instead.
ACTIONS_APP_SLUG = "github-actions"

# Reasons, as a closed vocabulary so a caller can branch on them.
REASON_EXCLUDED = "explicitly-excluded"
REASON_REQUESTED = "explicitly-requested"
REASON_ACTIONS_APP = "author-is-actions-app"
REASON_AUTHOR = "author-is-user"
REASON_ASSIGNEE = "assigned-to-user"
REASON_NOT_MINE = "not-authored-assigned-or-requested"
REASON_NO_IDENTITY = "identity-unresolved-arms-unevaluated"

INCLUDING_REASONS = frozenset(
    {REASON_REQUESTED, REASON_ACTIONS_APP, REASON_AUTHOR, REASON_ASSIGNEE}
)


class InputError(ValueError):
    """Raised when the supplied PR payload cannot be normalized."""


def normalize_login(value):
    """Strip the decorations an actor login picks up in transit.

    `app/github-actions`, `github-actions[bot]`, and `github-actions` are one
    actor. Comparison is case-folded because GitHub logins are.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if text.startswith("app/"):
        text = text[len("app/"):]
    if text.endswith("[bot]"):
        text = text[: -len("[bot]")]
    return text.casefold()


def actor_login(value):
    """Pull a login out of an actor field that may be a string or an object."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("login", "username", "name"):
            if value.get(key):
                return str(value[key])
        return ""
    raise InputError(f"unrecognized actor field: {value!r}")


def normalize_pr(raw):
    """Map one PR payload onto the fields the predicate reads.

    Accepts the `gh --json` shape, the REST / MCP shape, and the GitLab MR
    shape. A missing `assignees` key means unassigned rather than malformed:
    `mcp__github__list_pull_requests` omits it on an unassigned PR (measured
    2026-09-01), so treating its absence as an error would fail every sweep
    that used that tool.
    """
    if not isinstance(raw, dict):
        raise InputError(f"PR entry is not an object: {raw!r}")

    number = raw.get("number", raw.get("iid"))
    if number is None:
        raise InputError(f"PR entry has no number: {raw!r}")
    try:
        number = int(number)
    except (TypeError, ValueError):
        raise InputError(f"PR number is not an integer: {number!r}") from None

    author = actor_login(raw.get("author") or raw.get("user"))

    assignees_raw = raw.get("assignees")
    if assignees_raw is None:
        assignees_raw = []
    if not isinstance(assignees_raw, list):
        raise InputError(f"assignees is not a list on #{number}: {assignees_raw!r}")
    assignees = [actor_login(entry) for entry in assignees_raw]
    assignees = [login for login in assignees if login]

    return {
        "number": number,
        "title": raw.get("title", ""),
        "url": raw.get("url", raw.get("html_url", raw.get("web_url", ""))),
        "author": author,
        "assignees": assignees,
        "head": raw.get("headRefName", raw.get("source_branch", "")),
        "base": raw.get("baseRefName", raw.get("target_branch", "")),
        "is_draft": bool(raw.get("isDraft", raw.get("draft", False))),
    }


def classify(pr, identities, requested, excluded, identity_resolved):
    """Return (in_scope, reason) for one normalized PR.

    Order matters. The exclusion veto runs before every positive arm, so a
    PR the user authored is still dropped when the request said not to touch
    it.
    """
    if pr["number"] in excluded:
        return False, REASON_EXCLUDED
    if pr["number"] in requested:
        return True, REASON_REQUESTED
    if normalize_login(pr["author"]) == ACTIONS_APP_SLUG:
        return True, REASON_ACTIONS_APP
    if not identity_resolved:
        return False, REASON_NO_IDENTITY
    if normalize_login(pr["author"]) in identities:
        return True, REASON_AUTHOR
    if any(normalize_login(a) in identities for a in pr["assignees"]):
        return True, REASON_ASSIGNEE
    return False, REASON_NOT_MINE


def scope(prs, identities, requested, excluded, identity_resolved):
    """Classify a whole listing, keeping the full list for stack mapping."""
    normalized = [normalize_pr(raw) for raw in prs]
    ids = {normalize_login(i) for i in identities if normalize_login(i)}
    results = []
    for pr in normalized:
        in_scope, reason = classify(pr, ids, requested, excluded, identity_resolved)
        entry = dict(pr)
        entry["in_scope"] = in_scope
        entry["reason"] = reason
        results.append(entry)

    warnings = []
    if not identity_resolved:
        warnings.append(
            "identity unresolved: author and assignee arms unevaluated; "
            "only explicitly requested and Actions-app-authored PRs kept"
        )

    return {
        "identity_resolved": identity_resolved,
        "identities": sorted(ids),
        "requested": sorted(requested),
        # The veto list as supplied, kept distinct from `excluded` below:
        # one is an input, the other is the verdict, and a consumer reading
        # the wrong one would treat unvetoed out-of-scope PRs as drivable.
        "vetoed": sorted(excluded),
        "examined": len(results),
        "included": [p["number"] for p in results if p["in_scope"]],
        "excluded": [p["number"] for p in results if not p["in_scope"]],
        "prs": results,
        "warnings": warnings,
    }


def render(result):
    """Render the report, leading with what was examined."""
    lines = [
        f"examined {result['examined']} PR(s); "
        f"{len(result['included'])} in scope, "
        f"{len(result['excluded'])} excluded; "
        f"identity {'resolved' if result['identity_resolved'] else 'UNRESOLVED'}"
        f" ({', '.join(result['identities']) or 'none'})"
    ]
    for warning in result["warnings"]:
        lines.append(f"  WARNING: {warning}")
    for pr in result["prs"]:
        mark = "in scope " if pr["in_scope"] else "EXCLUDED "
        lines.append(
            f"  {mark} #{pr['number']:<5} {pr['reason']:<38} "
            f"author={pr['author'] or '(unknown)'}"
        )
    if not result["prs"]:
        lines.append("  (no PRs supplied)")
    return "\n".join(lines)


def split_numbers(values):
    """Parse repeated and comma-separated PR numbers into a set."""
    numbers = set()
    for value in values or []:
        for part in str(value).split(","):
            part = part.strip().lstrip("#")
            if not part:
                continue
            try:
                numbers.add(int(part))
            except ValueError:
                raise InputError(f"not a PR number: {part!r}") from None
    return numbers


def split_logins(values):
    """Parse repeated and comma-separated logins into a list."""
    logins = []
    for value in values or []:
        for part in str(value).split(","):
            part = part.strip()
            if part:
                logins.append(part)
    return logins


def load_payload(text):
    """Accept a bare list, or the object shapes the GitHub tools return."""
    data = json.loads(text)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("prs", "pull_requests", "pullRequests", "items", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
        if "number" in data or "iid" in data:
            return [data]
    raise InputError("payload is not a list of PRs or a recognized wrapper")


def fetch(repo, limit, number=None):
    """Fetch PR metadata with `gh`. Fails loudly rather than returning [].

    Kept out of the classification path so the tests run offline.
    """
    if number is None:
        cmd = [
            "gh", "pr", "list", "--repo", repo, "--state", "open",
            "--limit", str(limit),
            "--json", "number,title,url,author,assignees,headRefName,"
                      "baseRefName,isDraft",
        ]
    else:
        cmd = [
            "gh", "pr", "view", str(number), "--repo", repo,
            "--json", "number,title,url,author,assignees,headRefName,"
                      "baseRefName,isDraft",
        ]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", check=False
    )
    if proc.returncode != 0:
        raise InputError(f"gh failed: {proc.stderr.strip() or proc.returncode}")
    return load_payload(proc.stdout)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Decide which PRs a sweep is allowed to touch.",
    )
    parser.add_argument(
        "--user", default=None, metavar="LOGIN",
        help="Resolved invoking user. Omit to fail closed.",
    )
    parser.add_argument(
        "--alias", action="append", default=[], metavar="LOGIN",
        help="Another login for the same person; repeat or comma-separate.",
    )
    parser.add_argument(
        "--requested", action="append", default=[], metavar="N",
        help="PR numbers the request explicitly asked for.",
    )
    parser.add_argument(
        "--excluded", action="append", default=[], metavar="N",
        help="PR numbers the request said not to touch (a veto).",
    )
    parser.add_argument(
        "--repo", "-R", default=None, metavar="OWNER/NAME",
        help="Fetch the listing with gh instead of reading stdin.",
    )
    parser.add_argument(
        "--number", type=int, default=None, metavar="N",
        help="With --repo, classify this one PR instead of the open list.",
    )
    parser.add_argument(
        "--limit", type=int, default=200,
        help="Maximum open PRs to fetch with --repo (default 200).",
    )
    parser.add_argument(
        "--text", action="store_true",
        help="Emit a human-readable report instead of JSON.",
    )
    args = parser.parse_args(argv)

    if args.number is not None and args.repo is None:
        parser.error("--number requires --repo")

    try:
        if args.repo:
            payload = fetch(args.repo, args.limit, args.number)
        else:
            payload = load_payload(sys.stdin.read())
        identities = split_logins([args.user] if args.user else [])
        identities += split_logins(args.alias)
        result = scope(
            payload,
            identities,
            split_numbers(args.requested),
            split_numbers(args.excluded),
            identity_resolved=bool(identities),
        )
    except (InputError, json.JSONDecodeError) as exc:
        print(f"pr-scope: {exc}", file=sys.stderr)
        return 2

    if args.repo:
        result["repo"] = args.repo
    print(render(result) if args.text else json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
