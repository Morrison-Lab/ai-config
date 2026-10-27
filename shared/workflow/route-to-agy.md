# Route bounded work to `agy` first, on a machine where it is signed in

Ezra's request (2026-10-26): move work off the Claude subscription onto Antigravity (`agy`) to save Claude quota.
Subscription-only: `agy` uses the Antigravity login stored on the machine, never an API key.

## Where `agy` runs

Measured 2026-10-26 13:55 PDT on `cf463-02`: `agy` 1.4.7 at `~/.local/bin/agy`, `agy models` listed 13 models, and `gemini-4-argon-low` answered a headless `--print` in 16 s.
The XPS also runs it (Argon).
A cloud session has no `agy`; use `delegate-to-opencode` there.
`agy` exposes no quota figure (its log has a `quota_manager` but prints no numbers, 2026-10-26), so treat an unexplained failure on every item as possible exhaustion and fall back to Claude, never to a metered API.

## Routing table

| Work | Route | Mechanism |
|---|---|---|
| Cross-harness PR review (a Claude-authored PR) | `agy`, Argon, `--mode plan`, diff inline | `scripts/agy-review/rf.sh <owner/repo> <pr>` (model chain, posts the comment; for a PR whose diff it truncates, run `scripts/agy-review/bigread.py` by hand); `scripts/agy-dispatch.py review <owner/repo> <pr> --cwd <scratch clone>` prints the comment body without posting |
| Orphan-PR sweeps, checker re-runs, read-and-report audits | `agy` with the data embedded in the brief | `scripts/agy-dispatch.py brief --brief-file <f>` |
| Mechanical content edits (rename, reformat, table fill) | `agy` drafts the replacement text; Claude applies it with Edit and runs the checkers | `brief`, then Claude edits |
| Focused authoring, the critical-path edit, merges, anything with restricted data | Claude | none |

Why not let `agy` write files: `cf463-02`'s `~/.gemini/antigravity-cli/settings.json` has no allow-rule for edits, and headless `agy` otherwise exits 0 having written nothing.
Claude applies the edits.

## Capacity: two Argon reviewers

Argon on the XPS and Argon on `cf463-02` are interchangeable reviewers.
Pick the box you are on.
Run several reviews in parallel from separate scratch clones (earlier measured: eight in parallel on 2026-10-14).
One reviewer's verdict stands for the head it names (`Reviewed-Commit`).

## What `scripts/agy-dispatch.py` enforces

It fails, rather than reporting clean, on a `jetski: no output produced` denial, empty output, a nonzero exit, a brief over 100 KB, or any change in the checkout.
Output for `review` is a PR-comment body in the standard cross-harness shape.
Post it with `gh pr comment --body-file`; the footer already discloses the agent.

- **Do:** check a cheap lane's findings before acting (Argon over-flags style and sometimes misreads regexes), and rebut the ones that are wrong.
- **Don't:** count a one-line clean verdict as a review, or let the run push.
