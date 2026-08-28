#!/usr/bin/env python3
"""Rotate `CLAUDE_CODE_OAUTH_TOKEN` across every repo that already has it.

`CLAUDE_CODE_OAUTH_TOKEN` is provisioned one repo at a time, by whichever
Claude account the local CLI happened to be logged into when
`/install-github-app` or `claude setup-token` was run. Nothing records which
account minted a given token, and nothing can: the secrets API returns only
name, `created_at`, and `updated_at`, and the action's run logs mask the value
(`CLAUDE_CODE_OAUTH_TOKEN: ***`) with an empty `anthropic_organization_id`.

So an estate provisioned across several sittings ends up a mix of accounts
that cannot be untangled after the fact. The only way to make the question
answerable is to set every repo from one known account, which is what this
script does. See ai-config#952 for the sweep that motivated it (35 repos with
the secret across 324 admin repos, zero org-level Claude secrets).

Four properties are deliberate:

  Preview by default. The script prints its plan and changes nothing unless
  `--apply` is passed, matching the preview-by-default stance adopted for
  `scripts/semantic-line-breaks.py` in ai-config#951.

  The token never touches argv. `argv` is visible to anyone who can run `ps`
  and lands in shell history, so the token is read from an environment
  variable or stdin only, and handed to `gh secret set` over stdin (which
  `--body`'s own help documents as the fallback when `--body` is omitted).

  Targets are discovered, not hardcoded. Owners come from `gh api /user/orgs`
  plus the authenticated login, and the repo list from `viewerPermission`, per
  `shared/coding/avoid-hardcoding-external-data.md`. A baked-in repo list
  would go stale the first time a repo was added.

  Every write is verified. `gh secret set` exiting 0 is not evidence the
  secret changed, so each rotated repo's `updated_at` is re-read and compared
  against what it was before. Note the one limitation: if GitHub does not bump
  `updated_at` when the new value equals the old one, re-running with an
  unchanged token reports the write as unverified. That errs toward a false
  alarm rather than a false pass, which is the safe direction.

Only scopes that ALREADY carry the secret are touched.
Since ai-config#2360 the estate's primary copy is an ORG-LEVEL secret, so the
sweep covers both scopes: each org discovered (or named via `--owners`) is
checked for an org-level secret, and the per-repo sweep still runs because a
repo-level override remains legitimate for a repo that should spend a
different account's quota. The two scopes are reported separately, so an org
rotation is never silently counted as covering a repo that still overrides it.
A fully-discovered estate that carries the secret in NO scope is a hard
error (exit 1), not a quiet no-op: that reading is indistinguishable from a
broken sweep, which is how the org-level move was missed (#2371).
`--repos` bypasses discovery entirely (org sweep included), so naming a repo
that lacks the secret just drops it from the run, the same as any other repo
without the secret.
Provisioning the secret into a scope that lacks it is a separate, deliberate
decision and out of this script's scope; do it directly with
`gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo <owner>/<name>` or
`gh secret set CLAUDE_CODE_OAUTH_TOKEN --org <org> --visibility all`.

`claude setup-token` is the USER's to run, in their own terminal. It opens a
browser as its first act and then blocks reading an authorization code from
stdin, which an agent-spawned process (fd 0 is a socket, not a terminal) can
never satisfy -- and no timeout or closed stdin prevents the browser. See
memories/claude-code.md, "`claude setup-token` opens a browser first".

Usage:

    python3 scripts/rotate-claude-token.py                  # preview
    claude setup-token | python3 scripts/rotate-claude-token.py --apply
    CLAUDE_CODE_OAUTH_TOKEN=... python3 scripts/rotate-claude-token.py --apply
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys

DEFAULT_SECRET = "CLAUDE_CODE_OAUTH_TOKEN"
DEFAULT_WORKERS = 8


class GhError(RuntimeError):
    """A `gh` invocation failed. Carries the stderr for reporting."""


def gh(args: list[str], stdin: str | None = None) -> str:
    """Run `gh` and return stdout, raising GhError on a non-zero exit.

    Never pass a secret value inside `args` -- use `stdin`.
    """
    try:
        # `encoding` is load-bearing on Windows; see the long note in
        # `check-pr-fully-clean.py`'s `run_cmd`. Without it the locale codec
        # (cp1252) silently mojibakes most non-ASCII and hard-fails on five
        # bytes, the latter killing subprocess's reader thread and leaving the
        # stream as None with `returncode` unaffected.
        #
        # This script's exposure is narrower than its siblings', and the honest
        # form of that is "no demonstrated exposure" rather than a producer I
        # cannot source. Two earlier drafts of this comment each named a
        # mechanism that turned out to be false -- repo descriptions this script
        # never reads, then a non-English Windows error string that Go's
        # `syscall.Errno.error()` argues against, since it requests US English
        # first and returns UTF-16-to-UTF-8. So no mechanism is claimed here.
        #
        # What IS established: the decode failure itself is measured (a lone
        # 0xE9 on either stream leaves it None with `returncode` intact,
        # Windows / Python 3.13.7), and its five payloads are read from the
        # cp1252 table rather than recalled. Of this script's five `gh` call
        # sites, four read GitHub identifiers and one writes a secret via stdin,
        # so nothing here is a known-risky payload today.
        #
        # The guard earns its place on consistency instead: a reader finding
        # three of four sibling scripts guarded cannot tell whether the fourth
        # was considered or missed, and a future call site here that DOES read
        # arbitrary text would inherit the hole silently.
        proc = subprocess.run(
            ["gh", *args],
            input=stdin,
            capture_output=True,
            encoding="utf-8",
        )
    except FileNotFoundError:
        sys.exit("gh is not on PATH; install the GitHub CLI to use this script.")
    if proc.returncode != 0:
        if proc.stderr is None:
            sys.exit(
                f"gh {' '.join(args)} failed and its stderr could not be read "
                "or decoded, so the reason is unavailable. This is an "
                "environment failure."
            )
        raise GhError(proc.stderr.strip() or f"gh {' '.join(args)} failed")
    if proc.stdout is None:
        sys.exit(
            f"gh {' '.join(args)} produced no capturable stdout; its output "
            "could not be read or decoded. This is an environment failure."
        )
    return proc.stdout


def discover_owners() -> list[str]:
    """The authenticated login plus every org it belongs to."""
    login = gh(["api", "/user", "--jq", ".login"]).strip()
    orgs = gh(["api", "/user/orgs", "--paginate", "--jq", ".[].login"]).split()
    return [login, *orgs]


def admin_repos(owner: str) -> list[str]:
    """`owner/name` for each of `owner`'s repos where the viewer is an admin."""
    out = gh(
        [
            "repo",
            "list",
            owner,
            "--limit",
            "1000",
            "--json",
            "nameWithOwner,viewerPermission",
        ]
    )
    return [
        repo["nameWithOwner"]
        for repo in json.loads(out)
        if repo.get("viewerPermission") == "ADMIN"
    ]


def secret_updated_at(repo: str, secret: str) -> str | None:
    """`updated_at` for `secret` on `repo`, or None if the repo lacks it.

    `--jq` is what makes `--paginate` safe here. This endpoint returns an
    object (`{"total_count":N,"secrets":[...]}`), not an array, so a bare
    `--paginate` concatenates one object per page and the result is not
    valid JSON. Projecting `.secrets[]` flattens every page into NDJSON
    instead, one entry per line, which parses regardless of page count.
    """
    out = gh(
        [
            "api",
            f"/repos/{repo}/actions/secrets",
            "--paginate",
            "--jq",
            ".secrets[]",
        ]
    )
    for line in out.splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry["name"] == secret:
            return entry["updated_at"]
    return None


def org_secret_info(org: str, secret: str) -> tuple[str, str] | None:
    """`(updated_at, visibility)` for the org-level `secret`, or None.

    A 404 also returns None: the owner is a user rather than an org, so the
    endpoint does not exist for it. That is a normal result -- the owners
    list mixes the authenticated login in with real orgs -- not a failure.
    Any other error (403 permission, network) raises, so an org that exists
    but cannot be read is reported rather than silently counted secretless.
    The `--jq` projection is required for the same pagination reason as
    `secret_updated_at` above.
    """
    try:
        out = gh(
            [
                "api",
                f"/orgs/{org}/actions/secrets",
                "--paginate",
                "--jq",
                ".secrets[]",
            ]
        )
    except GhError as exc:
        # Match gh's own phrasing ("gh: Not Found (HTTP 404)") rather than a
        # bare "404", which could appear inside an unrelated error's text
        # (a timestamp, a rate-limit epoch) and silently misread a real
        # failure as user-not-org absence.
        if "HTTP 404" in str(exc):
            return None
        raise
    for line in out.splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry["name"] == secret:
            return entry["updated_at"], entry.get("visibility", "private")
    return None


def find_org_targets(
    owners: list[str], secret: str
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str]]]:
    """Split `owners` into orgs carrying `secret` and those that errored.

    Returns `(targets, errors)`, where `targets` is
    `(org, updated_at, visibility)` and `errors` is `(owner, message)`.
    A user login, or an org without the secret, appears in neither.
    """
    targets: list[tuple[str, str, str]] = []
    errors: list[tuple[str, str]] = []
    # Serial rather than pooled, unlike find_targets: the owners list is a
    # handful of logins, not hundreds of repos, so a pool buys nothing.
    for owner in owners:
        try:
            info = org_secret_info(owner, secret)
        except (GhError, json.JSONDecodeError) as exc:
            errors.append((owner, str(exc)))
            continue
        if info is not None:
            targets.append((owner, info[0], info[1]))
    return sorted(targets), sorted(errors)


def org_selected_repos(org: str, secret: str) -> list[str]:
    """`owner/name` for each repo an org-level `selected` secret reaches."""
    out = gh(
        [
            "api",
            f"/orgs/{org}/actions/secrets/{secret}/repositories",
            "--paginate",
            "--jq",
            ".repositories[].full_name",
        ]
    )
    return [line.strip() for line in out.splitlines() if line.strip()]


def rotate_org(
    org: str, secret: str, token: str, previous: str, visibility: str
) -> str:
    """Set the org-level `secret`, then confirm `updated_at` actually moved.

    `--visibility` is always passed explicitly, preserving what the secret
    already had: the API default is `private`, which reaches no repo (see
    ai-config#2361), so relying on the default would silently narrow an
    `all` secret in the act of rotating it. A `selected` secret keeps its
    repo list by reading it back and passing it through; an unreadable list
    raises out of `org_selected_repos` before the write, and a
    successfully-read but EMPTY list is refused, because writing `selected`
    with no repos would keep the secret detached from every repo.
    """
    args = ["secret", "set", secret, "--org", org, "--visibility", visibility]
    if visibility == "selected":
        selected = org_selected_repos(org, secret)
        if not selected:
            raise GhError(
                f"{secret} on org {org} has visibility=selected with zero "
                "selected repositories; refusing to rotate a secret no "
                "workflow can read (an unreadable list raises earlier)"
            )
        args.extend(["--repos", ",".join(selected)])
    gh(args, stdin=token)
    info = org_secret_info(org, secret)
    if info is None:
        raise GhError(f"{secret} is absent from org {org} after the write")
    current, _ = info
    if current == previous:
        raise GhError(
            f"{secret} on org {org} still reports updated_at={current}; "
            "the write did not take effect"
        )
    return current


def find_targets(
    repos: list[str], secret: str, workers: int
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Split `repos` into those carrying `secret` and those that errored.

    Returns `(targets, errors)`, where `targets` is `(repo, updated_at)` and
    `errors` is `(repo, message)`. A repo that simply lacks the secret appears
    in neither -- it is a normal result, not a failure.

    Unparseable output is caught alongside a failed `gh` call, so one bad
    response is reported against its own repo rather than aborting the whole
    sweep. It still lands in `errors` and is printed, so this reports the
    failure rather than swallowing it.

    Reads are concurrent because a full sweep is several hundred API calls;
    they are read-only, so ordering does not matter.
    """
    targets: list[tuple[str, str]] = []
    errors: list[tuple[str, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(secret_updated_at, repo, secret): repo for repo in repos
        }
        for future in concurrent.futures.as_completed(futures):
            repo = futures[future]
            try:
                updated_at = future.result()
            except (GhError, json.JSONDecodeError) as exc:
                errors.append((repo, str(exc)))
                continue
            if updated_at is not None:
                targets.append((repo, updated_at))
    return sorted(targets), sorted(errors)


def rotate(repo: str, secret: str, token: str, previous: str) -> str:
    """Set `secret` on `repo`, then confirm `updated_at` actually moved.

    Returns the new `updated_at`. Raises GhError if the write failed or if the
    timestamp did not change, so a silent no-op cannot pass for a rotation.
    """
    gh(["secret", "set", secret, "--repo", repo], stdin=token)
    current = secret_updated_at(repo, secret)
    if current is None:
        raise GhError(f"{secret} is absent from {repo} after the write")
    if current == previous:
        raise GhError(
            f"{secret} on {repo} still reports updated_at={current}; "
            "the write did not take effect"
        )
    return current


def read_token(env_var: str) -> str:
    """The token, from `env_var` or stdin. Exits rather than return empty."""
    token = (os.environ.get(env_var) or "").strip()
    if token:
        return token
    if sys.stdin.isatty():
        sys.exit(
            "No token supplied. Either pipe one in:\n"
            "    claude setup-token | python3 scripts/rotate-claude-token.py --apply\n"
            f"or export it:\n"
            f"    export {env_var}=...\n"
            "The token is never accepted as a command-line argument, because "
            "argv is visible in `ps` and recorded in shell history."
        )
    token = sys.stdin.read().strip()
    if not token:
        sys.exit("Empty token on stdin; refusing to write an empty secret.")
    return token


def collect_repos(args: argparse.Namespace) -> tuple[list[str], list[str]]:
    """The repos to inspect, and the owners they came from."""
    if args.repos:
        return sorted(set(args.repos)), []
    owners = args.owners or discover_owners()
    repos: set[str] = set()
    for owner in owners:
        repos.update(admin_repos(owner))
    return sorted(repos), owners


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--secret",
        default=DEFAULT_SECRET,
        help=f"secret name to rotate (default: {DEFAULT_SECRET})",
    )
    parser.add_argument(
        "--owners",
        nargs="+",
        help="owners to sweep (default: the authenticated login and its orgs)",
    )
    parser.add_argument(
        "--repos",
        nargs="+",
        help="explicit owner/name list, bypassing discovery",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"concurrent API reads (default: {DEFAULT_WORKERS})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually rotate (default: preview only, changing nothing)",
    )
    args = parser.parse_args()

    try:
        repos, owners = collect_repos(args)
    except GhError as exc:
        sys.exit(f"Could not enumerate repos: {exc}")

    if owners:
        print(f"Owners swept: {', '.join(owners)}")
    print(f"Repos inspected: {len(repos)}")

    targets, errors = find_targets(repos, args.secret, args.workers)
    # The org sweep runs off the same owners list; with --repos there are no
    # owners, so discovery (org sweep included) is bypassed, per the
    # docstring.
    org_targets, org_errors = find_org_targets(owners, args.secret)
    errors.extend(org_errors)

    # Report what could not be read before reporting what was found: an
    # unreadable scope is indistinguishable from one without the secret in
    # the counts below, so a silent error would understate the target list.
    for scope, message in errors:
        print(f"  ERROR {scope}: {message}", file=sys.stderr)
    if errors:
        print(f"{len(errors)} scope(s) could not be read.", file=sys.stderr)

    # The two scopes are reported separately, so an org-level rotation is
    # never silently counted as covering a repo that still overrides it.
    # Gated on `owners` like the "Owners swept" line above: under --repos the
    # org sweep never ran, and printing "0" would read as a checked result.
    if owners:
        print(f"Orgs carrying {args.secret} at org level: {len(org_targets)}")
        for org, updated_at, visibility in org_targets:
            print(f"  {org:<44} updated={updated_at} visibility={visibility}")
    print(f"Repos carrying {args.secret}: {len(targets)}")
    for repo, updated_at in targets:
        print(f"  {repo:<44} updated={updated_at}")

    if not targets and not org_targets:
        if owners:
            # An empty estate under FULL DISCOVERY is an ERROR, not a quiet
            # success (#2371 point 4): the secret disappearing from every
            # scope is exactly the topology change this script exists to
            # notice, and "Nothing to rotate" was how a broken sweep passed
            # for a healthy one when the estate moved to an org-level secret
            # (fail-fast's pass-path-equals-failure-path shape).
            print(
                f"\nERROR: {args.secret} was found in NO scope -- neither "
                "an org-level secret nor any repo-level copy. Either the "
                "estate is unprovisioned or discovery is looking in the "
                "wrong place; both need a human, so this is an error "
                "rather than a no-op.",
                file=sys.stderr,
            )
            sys.exit(1)
        # Under --repos the org sweep never ran and the caller deliberately
        # narrowed the query, so an empty result is the documented benign
        # narrowing (see the docstring), not the vanished-estate signal.
        print("\nNothing to rotate in the named repos.")
        sys.exit(1 if errors else 0)

    total = len(org_targets) + len(targets)
    if not args.apply:
        print(
            f"\nPreview only; nothing was changed. "
            f"Re-run with --apply to rotate all {total}."
        )
        sys.exit(1 if errors else 0)

    token = read_token(args.secret)

    rotated = 0
    if org_targets:
        print(f"\nRotating {len(org_targets)} org secret(s):")
        for org, previous, visibility in org_targets:
            try:
                current = rotate_org(
                    org, args.secret, token, previous, visibility
                )
            except GhError as exc:
                print(f"  FAILED  org:{org}: {exc}", file=sys.stderr)
                errors.append((org, str(exc)))
                continue
            rotated += 1
            print(f"  ok      org:{org:<40} updated={current}")

    if targets:
        print(f"\nRotating {len(targets)} repo(s):")
        for repo, previous in targets:
            try:
                current = rotate(repo, args.secret, token, previous)
            except GhError as exc:
                print(f"  FAILED  {repo}: {exc}", file=sys.stderr)
                errors.append((repo, str(exc)))
                continue
            rotated += 1
            print(f"  ok      {repo:<44} updated={current}")

    print(f"\nRotated {rotated} of {total}.")
    if errors:
        print(f"{len(errors)} scope(s) failed; see above.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
