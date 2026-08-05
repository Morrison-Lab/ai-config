# pending-decisions — surface issues/PRs waiting on a decision from you (pd)

`prompt-me` / `prompt-me-all` sweep the **current conversation** for questions left unanswered. They can’t see a question a *prior* session left stalled on an issue or PR — that stub sits in the tracker until someone happens to reopen it. This skill sweeps the **tracker itself**: it finds issues/PRs genuinely waiting on the user’s decision and triggers the question-asking, one item at a time.

## When this fires

- Explicit invocation: `/pending-decisions`, `/pd`, “pending decisions”, “pd”.
- “what decisions are you waiting on”, “any decisions needed from me”, “check for pending decisions”, “is anything stalled on my input”, “sweep issues for decisions”.
- With a scope argument: `pd all` (every repo in this session’s GitHub scope), `pd owner/repo` (one specific repo).

## Step 1 — Decide scope

- No argument → the **current repo** only.
- `all` / “every repo” / “sweep everything” → every repo in this session’s GitHub scope (the “Repository Scope” list, plus any repo added via `add_repo` this session).
- `owner/repo` → that repo specifically.

State the scope you’re using before searching, so a wrong guess is cheap to correct.

## Step 2 — Find candidates

For each repo in scope, search for open issues/PRs against these signals, most reliable first. An item can hit more than one signal; that’s fine, dedupe in Step 3.

1.  **Explicit review-request escalation** — `search_issues` with `repo:<owner>/<repo> is:open review-requested:@me` (GitHub resolves `@me` to the authenticated user — more portable than hardcoding a username). This is exactly the deadlock-escalation mechanism `ardi`/`fully-clean`/ `address-every-comment` already use (“request a human reviewer… surface the open item to me”) — a hit here is unambiguous: something is genuinely stalled on the user.
2.  **A decision-style label**, if the repo defines one — `search_issues` with `repo:<owner>/<repo> is:open label:question` (GitHub’s common default label) or whatever the repo’s own convention names.
3.  **An unresolved bot-posed question in recent activity** — the noisiest signal, so bound it: pull the ~30 most recently updated open issues/PRs (`search_issues ... sort:updated`), and for each, read the latest comment (`pull_request_read` `get_comments` / `issue_read` `get_comments`, plus `get_review_comments` for inline threads on PRs). Count it as a candidate only when **all** of:
    - the latest comment is bot/agent-authored, not human — a human’s own question is a normal review finding to address, not something the user is waiting on;
    - it reads as a question or decision request directed at the user — a ❓ **QUESTION**/🛑 **BLOCKER** marker, “your call”, “which of these”, “need your input”, explicit deadlock/escalation language, or a plain question ending in `?`;
    - no reply from the user has landed since.

    This is a judgment call, not a regex — when it’s unclear whether a comment is still live or was already resolved by later activity, read the surrounding thread rather than guessing either way. If more open items exist beyond the ~30-item window, say so (“N more open issues not scanned for this signal”) instead of silently under-covering.

## Step 3 — Dedupe and rank

Collect every candidate across repos and signals into one list, dedupe by issue/PR number (an item hitting more than one signal ranks by its **strongest** signal), and rank most-pressing first, three tiers:

1.  **Signal 1** (explicit review-request escalation) — always first; something is already stalled.
2.  **Signal 2** (a human-applied decision label) — a confirmed signal, but one rung below an explicit escalation.
3.  **Signal 3** (an inferred, judgment-call candidate) — least certain, so lowest tier regardless of recency; a fresher guess still doesn’t outrank a labeled item.

Within each tier, **more recently updated** beats older.

(Same ordering `prompt-me`/`prompt-me-all` use for conversation-scoped questions — reused here rather than re-derived.)

## Step 4 — Present one at a time

Apply the “Present decisions one at a time” rule (proposed in [ai-config#584](https://github.com/d-morrison/ai-config/pull/584) — once merged, follow that `CLAUDE.md` section directly; until then, apply the same logic inline): pose only the single most pressing candidate — quote or paraphrase the actual question, link the issue/PR, state how many more are queued — then wait for the answer before moving to the next. Fold each answer into the framing of the next question, and drop any later candidate the answer already mooted.

## Step 5 — Close the loop

Once the user answers a candidate:

1.  **Post the decision back** as a comment on that issue/PR (paraphrased, per `CLAUDE.md`’s “Post in-chat feedback to the PR”), so the record is visible to future sessions and bots — not just this transcript.
2.  **Resume the work now** if this session can act on it immediately (the repo is in scope and nothing else blocks it) — don’t just record the answer and stop when you could unblock the work in the same turn.
3.  If it can’t be acted on immediately (the repo is out of this session’s scope, or the work belongs to a different in-flight session), say so plainly — the comment is still posted, so the decision isn’t lost.

## Step 6 — Nothing found

If the sweep turns up nothing, say so plainly (“no pending decisions found across `<repos>`”) rather than manufacturing a candidate to fill the report.

## Relationship to other skills

- **`prompt-me` / `prompt-me-all`** — the conversation-scoped analog; this skill is scoped to the issue/PR tracker instead, so it survives across sessions and finds what a transcript-only sweep can’t see.
- **`CLAUDE.md`’s “Present decisions one at a time”** ([\#584](https://github.com/d-morrison/ai-config/pull/584)) — the presentation mechanic Step 4 reuses rather than redefining.
- **`ardi` / `fully-clean` / `address-every-comment`** — the mechanisms that produce most Signal-1 candidates (a deadlock escalated to a human reviewer via `request-pr-review`).
- **`post-merge`** — once a candidate’s issue/PR merges or closes, it drops out of the next sweep on its own; nothing extra to clean up here.

## Anti-patterns

- ❌ Surfacing a Signal-3 candidate without confirming no human reply landed since the bot’s question — stale noise dragged back into view.
- ❌ Batching several candidates into one message instead of one at a time — defeats the point (see `CLAUDE.md`’s “Present decisions one at a time”).
- ❌ Treating a human reviewer’s own question (posed *to* the bot, not the other way around) as a pending decision — that’s a normal review finding to address/rebut/defer, not something the user is waiting on.
- ❌ Silently dropping a real candidate because it didn’t match Signal 3’s literal cues — it’s a judgment call; read the thread when unsure.
- ❌ Recording the answer as a comment but not resuming blocked work this session could otherwise act on immediately.

Back to top
