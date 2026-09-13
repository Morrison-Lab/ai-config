# Fetch All (aka `fa`)

Run `git fetch origin` across **every git repo under a directory** and report a per-repo status line. This is a **read-only** sweep — it updates remote-tracking refs only. It never merges, pulls, rebases, or touches any working tree, so it’s safe to run over a whole directory of repos with uncommitted work.

## When this fires

- “fetch all”, “fa”, “fetch from origin on all repos”, “fetch every repo”
- “update all my repos”, “git fetch everywhere”
- “fetch all the repos under `<dir>`”

For a single repo that also merges main and the remote branch and pushes, use `sync-pr-branch` / `sync` instead — that one mutates the tree; this one doesn’t.

## Scope

- **Default root**: the current working directory. Sweep its **immediate subdirectories** (depth 1) that are git repos.
- The user may name a different root (“fetch all the repos under `~/code`”) — use that instead.
- A repo with **no `origin` remote** is reported `SKIP`, not failed.

## Procedure

### 1. Preview the repos (optional)

To see what the sweep will cover before running it:

``` bash
ROOT="${ROOT:-$PWD}"     # or the directory the user named
find "$ROOT" -maxdepth 2 -name .git | sort   # no -type d: worktree/submodule .git is a file
```

`-maxdepth 2` finds `<root>/<repo>/.git` — the immediate children. (If `ROOT` is *itself* a repo it also lists `<root>/.git`; the Step 2 loop ignores that case, fetching only the subdirectories.) Don’t recurse deeper by default: nested repos and submodules balloon the sweep, and submodule fetches are handled by their superproject. This step is just a preview — the Step 2 loop discovers the repos on its own, so you can skip straight to it.

### 2. Fetch each, capture status

Loop over the immediate subdirectories, fetch each from origin, and classify the outcome. This loop is self-contained — it does its own discovery (no need to pipe Step 1 into it). Run it as a single block so the user gets one consolidated report:

``` bash
ROOT="${ROOT:-$PWD}"     # the root from Step 1, or default to the current dir
cd "$ROOT" || { echo "ERROR: cannot cd to $ROOT"; exit 1; }
for d in */; do
  repo="${d%/}"
  [ -e "$repo/.git" ] || continue   # -e, not -d: a worktree/submodule .git is a file
  if ! git -C "$repo" remote | grep -qx origin; then
    echo "SKIP $repo (no origin remote)"; continue
  fi
  if ! out=$(git -C "$repo" fetch origin 2>&1); then   # FETCH
    echo "FAIL $repo: $(echo "$out" | tr '\n' ' ')"
  elif [ -z "$out" ]; then
    echo "OK   $repo"
  else
    echo "UPD  $repo: $(echo "$out" | tr '\n' ' ')"
  fi
done
```

Status codes:

| Code   | Meaning                                                         |
|--------|-----------------------------------------------------------------|
| `OK`   | Fetch succeeded, already up to date (no new refs)               |
| `UPD`  | Fetch succeeded and pulled new commits / branches / tags        |
| `FAIL` | Fetch errored (unreachable host, auth, missing repo, ref clash) |
| `SKIP` | No `origin` remote — nothing to fetch                           |

### 3. Report

Summarize counts (OK / updated / failed / skipped), then **call out the failures and skips explicitly** — those are the only lines the user needs to act on. For each `FAIL`, give the one-line reason and, where the fix is obvious, suggest it:

- **`Could not resolve host`** → off the VPN / network for an internal forge (e.g. a corporate GitLab). Reconnect and re-run.
- **`Repository not found` / `repository ... not found`** → the remote was moved or deleted; the `origin` URL is stale.
- **`'refs/remotes/origin/<x>' exists; cannot create 'refs/remotes/origin/<x>/<y>'`** → a ref/namespace clash. Fix with `git -C <repo> remote prune origin` then re-fetch that one. Same for an `Errors during submodule fetch` line.

Don’t bury a `FAIL` inside a wall of `OK` lines — the failures are the signal.

## Anti-patterns

- ❌ Following the fetch with `git pull` / `git merge` — this skill is read-only by contract; mutating the tree is `sync-pr-branch`’s job.
- ❌ Recursing into every nested `.git` (huge sweeps, redundant submodule fetches). Stay at depth 1 unless asked.
- ❌ Reporting a no-`origin` repo as a failure — it’s a `SKIP`.
- ❌ Aborting the whole sweep when one repo fails — each repo is independent; keep going and collect every result.

## Relationship to other skills

- **`sync-pr-branch` / `sync` / `merge-main`** — single-repo, *mutating* counterpart: fetch **and** merge main + remote branch, then push. Use that when you want the working tree updated, not just the refs.
- **`clean-branches` / `cb` / `prune`** — after fetching, prune and tidy the branches the fetch revealed.
- **`pr-status-all`** — whole-repo status overview once refs are current.

Back to top
