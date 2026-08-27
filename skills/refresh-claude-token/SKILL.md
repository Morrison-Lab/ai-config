---
name: refresh-claude-token
description: "Rotate CLAUDE_CODE_OAUTH_TOKEN."
user-invocable: true
allowed-tools:
  - Bash
  - Read
---

# refresh-claude-token

Replace `CLAUDE_CODE_OAUTH_TOKEN` on the repos that already carry it,
and confirm the replacement actually works.

`/install-github-app` is the only built-in that writes this secret,
and it bundles that write with installing the GitHub App
and committing workflow files.
When the token is the only thing that needs replacing,
that command does far more than the job requires,
and re-running it against a repo whose workflows are already customized
risks scaffolding over them.

This skill is a thin wrapper.
The work is done by `scripts/rotate-claude-token.py`,
which already discovers its targets, previews by default,
keeps the token out of `argv`,
and confirms each write landed.
Read that script's docstring before changing anything here.

## When this fires

- "refresh the claude token", "rotate the claude token", "rct"
- "update CLAUDE_CODE_OAUTH_TOKEN", "the claude token expired"
- A review job whose log carries an explicit credential rejection:
  a 401, an `OAuth token has expired`, or an `Invalid bearer token`.

**A short failing run is not on that list, deliberately.**
It is tempting to add one, because a rejected credential does produce a fast
`is_error: true` run with no verdict.
So do a checkout failure, an App-token exchange failure,
and a workflow-validation refusal,
which step 4 below and
[`fully-clean`](../../shared/workflow/fully-clean.md) both say cannot be told
apart by duration.

Since this skill's whole output is a secret rewrite,
firing it on the ambiguous signal spends a rotation on a problem a rotation
cannot fix,
and then credits the rotation when the real cause clears on its own.
Read the log and find the rejection line first.
No line, no rotation.

## What this is not

Installing the GitHub App,
committing or editing anything under `.github/workflows/`,
or provisioning the secret into a repo that has never had it.

That last one is a hard limit of the script, not a policy choice.

`--repos` bypasses **repo discovery**, not **secret discovery**.
`find_targets()` keeps a repo only when `secret_updated_at()` returns
non-`None`,
so a repo lacking the secret is dropped even when named explicitly,
and `--apply` then reports `Nothing to rotate` without ever calling
`rotate()`.

The script's docstring says the same, so provision with `gh secret set`
directly instead:

```bash
gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo <owner>/<repo>   # SET_SECRET
```

Do that deliberately, one repo at a time,
since it decides which account's quota that repo spends.

For authoring or changing the workflows themselves,
use `claude-agent-workflow` or `claude-review-workflow`.

## Procedure

### 1. Preview, and read the target list

```bash
python3 scripts/rotate-claude-token.py            # preview; changes nothing
```

This prints the owners swept, the number of repos inspected,
and every repo carrying the secret with its current `updated_at`.

Read the count before going further.
A number far below the last known sweep
means the discovery step failed rather than that the estate shrank,
and rotating against a truncated list
leaves the untouched repos on the old token with nothing reporting it.
The script prints unreadable repos to stderr for exactly this reason,
so a run reporting errors has understated its own target list.

### 2. Mint the token -- the human runs this step

`claude setup-token` is interactive,
and an agent session cannot complete it.
Run non-interactively it does not fail fast:
with stdin closed it printed nothing and was still running when killed at 8
seconds,
so an agent that calls it hangs rather than getting an error to report.

The gate is a post-authorize read, established by inspecting the blocked
process rather than inferred:

```bash
ps -o pid=,stat= -p <pid>        # S, still alive after the browser authorize
lsof -p <pid> -a -d 0            # fd 0 is a unix socket, not a TTY
```

It opens a browser, and after you authorize it blocks reading an
authorization code from stdin.
An agent-spawned process has a socket on fd 0, so that read can never be
satisfied.
The full record is in
[`memories/claude-code.md`](../../memories/claude-code.md).

**Never have the user run it bare.**
It prints a live, long-lived OAuth token to stdout,
so a bare `! claude setup-token` puts that credential into the agent's
context and into the persisted session transcript.
Pipe it into the consumer instead, so the value is never displayed --
which is the same reason the script itself refuses the token on `argv`:

```
! cd <ai-config-checkout> && claude setup-token | python3 scripts/rotate-claude-token.py --apply
```

**Mind which account is logged in, without minting anything to find out.**
The command mints from whichever account the local CLI is currently
authenticated as,
with no account picker and no confirmation naming it,
and nothing afterwards records which account a given token came from.
`claude auth status` answers that on its own,
so run it *before* deciding to rotate rather than minting a token to
discover the answer:

```bash
claude auth status
```

### 3. Rotate

Pipe the token straight in.
Never paste it as an argument:
`argv` is visible to anyone who can run `ps`,
and it lands in shell history.

```bash
claude setup-token | python3 scripts/rotate-claude-token.py --apply
```

The user runs that pipeline themselves, for the reason in step 2.
When the token is already in the environment, the agent can run:

```bash
python3 scripts/rotate-claude-token.py --apply     # reads $CLAUDE_CODE_OAUTH_TOKEN
```

The script re-reads each repo's `updated_at` after writing
and fails the repo if the timestamp did not move,
so a silent no-op cannot pass for a rotation.

### 4. Verify the new token authenticates

**This is the step the script cannot do, and the reason this skill exists.**

`gh secret set` succeeds against any value.
A garbage token bumps `updated_at` exactly like a good one,
so step 3 finishing clean proves the secret **changed**
and says nothing about whether it **works**.

Settle it on the artifact rather than on the write.
Pick one **non-draft** PR, record what already exists, then dispatch:

First find the reviewer's login **in this repo**, rather than assuming it.
It differs by repo:
`Morrison-Lab/ai-config` posts as `claude`,
while `Morrison-Lab/gha` posts as `github-actions[bot]`.
A hardcoded login matches nothing, which reads as "posted nothing":

```bash
gh pr view <N> --repo <owner>/<repo> --json comments \
  --jq '[.comments[].author.login] | unique'      # pick the reviewer's login
```

Then record the current state and dispatch:

```bash
BOT=claude                                        # from the query above
BEFORE=$(gh pr view <N> --repo <owner>/<repo> --json comments \
  | jq -r --arg bot "$BOT" '[.comments[] | select(.author.login == $bot)] | last | .id // "none"')
gh workflow run claude-review.yml --repo <owner>/<repo> \
  --ref <branch> --field pr_number=<N>            # RUN_WORKFLOW
```

**Pipe into standalone `jq`; do not pass `--arg` to `gh`'s own `--jq`.**
`gh`'s `--jq` takes exactly one argument, the filter, and has no
`--arg`/`--argjson` passthrough
([cli/cli#10263](https://github.com/cli/cli/issues/10263) is the open request).
Passing them makes `gh` read each as a positional argument and refuse:

```
accepts at most 1 arg(s), received 4
```

This corpus already records that, in
[`skills/ardi/SKILL.md`](../ardi/SKILL.md) and
[`memories/gh-cli.md`](../../memories/gh-cli.md).

Once the run completes, evaluate it in **one** filter that names every
outcome:

```bash
gh pr view <N> --repo <owner>/<repo> --json comments \
  | jq -r --arg bot "$BOT" --arg before "$BEFORE" '
    [.comments[] | select(.author.login == $bot)] | last
    | if   . == null      then "BROKEN: no comment from \($bot) at all"
      elif .id == $before then "BROKEN: newest comment unchanged; this run posted nothing"
      elif (.body | test("(?i)###\\s*verdict")) then "WORKING: new verdict \(.id)"
      else "INCONCLUSIVE: new comment \(.id), no verdict heading"
      end'
```

**Use one filter, never a `BEFORE` capture compared against a
differently-shaped read.**
That two-command form is the trap, and it is subtle enough to have shipped
here once already.
`.id // "none"` yields `none` on an empty result,
while `"\(.id) \(.createdAt)"` on the same empty result yields the string
`null null`.
Those two differ, so a PR with **no** prior review reports the token
**working** whatever the run did --
a false pass in the one step that exists to prevent false passes.
Measured on this repo, against a PR with no reviews:
`none` versus `null null`.

Note what the `.body` test buys as well.
Without it the check accepts any new comment,
including a cost tally or a quota-exhausted notice,
neither of which is a review.

Take the run's length from its own `createdAt` and `updatedAt` once it has
completed, never from a `status` field read mid-flight.
`status` lags, so a finished job can still read `in_progress`,
and inferring elapsed time from that measures the API's freshness
rather than the job's runtime.

Two cautions on reading a short run.

A short run means the job stopped before reaching the model.
It does not by itself mean the credential is why.
Checkout failures, App-token exchange failures,
and workflow-validation refusals all die in the same few-tens-of-seconds band.
Open the log and quote the line the job actually died on
before blaming the token.

And a draft PR is not a test.
This repo's `claude-review` skips on drafts,
so dispatching against one produces a fast, green, review-free run
that looks exactly like the failure you are checking for.
Use a non-draft PR.

### 5. Report

Say how many repos rotated, which failed, and which repo the verification ran on.
Name the account if step 2 established it.
A rotation reported without a verification repo
is a write that nobody confirmed authenticates.

## Why write-verified is not auth-verified

Worth stating plainly, because the script's own verification is good
and that is exactly what makes it easy to over-read.

`rotate()` compares `updated_at` before and after,
which answers "did GitHub store something different".
The question a user actually cares about
is "will the reviewer be able to authenticate",
and no property of the secrets API can answer that:
the endpoint returns only name, `created_at`, and `updated_at`,
and the action's logs mask the value as `***`.

So the only instrument is behavioural,
and the only positive evidence is a run that reached the model.
This is the failure recorded in
[`review-verdict-pitfalls`](../../shared/workflow/review-verdict-pitfalls.md)'s
eighth case and its cross-repo variant:
seven `claude-review` runs on `d-morrison/altdoc` #95 and #96
failing in the 26-to-35-second band
with `is_error: true`, `total_cost_usd: 0`, and no permission denials,
while the same reviewer returned a full verdict on another owner's repo
minutes later.
No number of re-runs would have shown that;
only a working control on a different credential did.

## Edge cases

- **A repo that has never had the secret.**
  The script cannot reach it at all, with or without `--repos`,
  for the reason in "What this is not" above.
  Use `gh secret set` directly.
- **Re-running with an unchanged token.**
  If GitHub does not bump `updated_at` when the value is identical,
  the script reports the write as unverified.
  That is a false alarm rather than a false pass,
  which is the safe direction.
- **`gh` not on `PATH`.**
  The script exits with that message rather than proceeding.
- **Org-level secrets.**
  `gh secret set <name> --org <org> --visibility selected --repos <repo1>,<repo2>`
  sets one secret for several repos.
  `--repos` takes **bare** repo names, comma-separated, not `owner/name`:
  the owner is already fixed by `--org`.
  Note that a sweep of 324 admin repos in 2026-07 found
  zero org-level Claude secrets and 35 repo-level ones,
  so the estate is repo-level today
  and moving it is a change of shape, not a rotation.

## Anti-patterns

- Running `/install-github-app` to fix an expired token,
  which reinstalls the App and rescaffolds workflows to change one secret.
- Passing the token as a command-line argument or via `--body`,
  putting it in `ps` output and shell history.
- Reporting a rotation as done on the strength of step 3 alone,
  which verifies the write and not the credential.
- Reading a short, green, review-free run on a **draft** PR
  as evidence the token is broken.
- Diagnosing a short run as a credential failure
  without opening the log,
  when checkout, App-token exchange, and workflow validation
  fail in the same duration band.
- Rotating against a preview whose error count was not read,
  leaving unreadable repos silently on the old token.
- Hardcoding a repo list into a rotation
  instead of letting the script discover it,
  per [`avoid-hardcoding-external-data`](../../shared/coding/avoid-hardcoding-external-data.md).

## Relationship to other skills

- **`claude-agent-workflow` / `claude-review-workflow`** author and modify the
  workflows that consume this secret.
  This skill only replaces the secret and never edits a workflow file.
- **`permission-check`** covers what a workflow token is allowed to do;
  this covers whether the Claude credential authenticates at all.
  A job can fail for either reason with a similar-looking short run.
- **`ardi`** is what resumes once reviews work again.
  A reviewer that never posts is not a clean verdict,
  per [`fully-clean`](../../shared/workflow/fully-clean.md)'s
  "no findings" versus "no verdict" distinction.
- **`cdu`** audits stale pinned dependencies.
  A stale credential is a different kind of staleness and is not in its sweep.
