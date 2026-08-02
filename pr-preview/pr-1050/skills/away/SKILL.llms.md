# away — unattended, best-judgment operating mode

## What this grants

By default, a genuinely ambiguous decision (which of several plausible approaches to take, which issue to pick up next, whether a finding is worth fixing) is a reason to stop and ask — a blocking question pauses the session until the user answers it. `away` is a stronger, deliberately- invoked escalation past that default for a stretch where the user won’t be there to answer: for the rest of the session, don’t surface a blocking question for a **judgment call** — reason it through as far as possible, consult a stronger model when one is available (see Procedure), and otherwise make the more conservative, most-reversible choice and record what you assumed. Reserve actually stopping for the narrower set of cases in Scope and limits below, where no amount of reasoning substitutes for information or authorization only the user holds.

## When this fires

- “away”, “I’ll be away for a while”, “going offline for a bit”, “I’m going to be unavailable”
- “don’t ask me questions”, “use your best judgment”, “operate autonomously”, “no questions mode”
- Any similar standing grant to stop blocking on the user for the rest of the session

Distinguish from a one-off “just proceed” on a single pending question — that resolves the one question in front of you; `away` is a standing mode for everything still to come.

## Scope and limits

- **Session-scoped, not a standing preference.** Applies only to the current conversation; a fresh session (new tab, `/clear`, container restart) starts without it — the same lifetime rule `mwc` uses for merge authority.
- **Judgment calls only — not a bypass for missing information or authorization.** Split every “I’d normally ask here” moment into one of two kinds:
  - **A judgment question** — which of several defensible approaches is better, whether a finding is a real bug, how to scope a fix, which issue is the best next pick. `away` covers these: reason it through, consult a stronger model if one helps, decide, and note the call in your recap.
  - **An information-or-authorization question** — a fact only the user knows (a preference, a business rule, private/undocumented context) or an action that needs their explicit sign-off regardless of confidence (a destructive operation, a merge past a required check, spending real money, anything the session’s own permission system or `CLAUDE.md`/`preferences.md` already marks as “always confirm”). `away` does **not** cover these — skip or defer the item, note why, and move to the next one instead of guessing at an answer nobody but the user can give.
- **Doesn’t grant merge, force-push, or any other destructive-action authority on its own.** Those stay gated exactly as before. `mwc` (merge-when-confident) is the separate, narrower grant for merge authority specifically — see Relationship to other skills. Combine both explicitly (“away, and mwc”) when the user wants full unattended PR throughput, not just decision-making latitude.
- **Revocable immediately.** An explicit “stop”, “ask me from now on”, the named counterpart `back` (see Relationship to other skills), or the session ending revokes the grant right away.
- **Applies session-wide unless the user narrows it.** Honor an explicit scope (“away, but still ask about anything touching the release branch”) over the default full-session grant.

## Procedure

1.  **Acknowledge the grant in one sentence** — what it does and doesn’t cover — so the user knows it’s active before they step away.
2.  **Picking work (issue/task selection):** when several candidates are open (a `gi`/`gii`/`gia` queue, several review findings, multiple possible next steps), prefer the ones you’re **confident** about — clear acceptance criteria, a design direction that’s already settled or obviously correct, no open question that only the user could resolve. Skip or defer a candidate that’s genuinely ambiguous (a stated-but- unverified root cause, a design decision with more than one defensible answer, scope that could reasonably go two ways) rather than guessing and building the wrong thing — note what you skipped and why in your recap so the user can redirect later. `gii`’s own auto-proceed mode already bypasses-and-notes a blocked or ambiguous issue within one sweep; `away` extends that same skip-and-note default across the whole session and to any kind of work choice, not just issue-grabbing.
3.  **Hitting a judgment call mid-task:** before treating it as blocking, check whether a **stronger model than the one currently running this session** is available. In this harness that means a higher tier than your current one (Fable \< Haiku \< Sonnet \< Opus, per `select-model`’s tier table) — prefer the **highest** available tier, not just the next step up, since the whole point is the best perspective available, and a mid-tier consult that still can’t resolve the ambiguity just wastes a round-trip. If a stronger tier exists, spawn a foreground `Agent` call with `model` set to that tier, hand it the specific decision (not the whole task — just enough context to weigh in: the options, the constraints, why it’s ambiguous), and use its answer to proceed. Note in your recap that you consulted it and what it said. If you’re already running the top available tier (no stronger model to ask), or the question is the information/authorization kind from Scope and limits above, don’t fabricate certainty — make the most conservative, easiest-to-reverse choice, and flag the assumption clearly in your recap rather than silently picking one.
4.  **Keep a running log of judgment calls made**, not just a final summary — each time you resolve something you’d normally have asked about, add one line (what the question was, what you decided, why) so the eventual recap is a genuine decision log the user can scan and countermand any of, not just a “done, trust me” report.
5.  **The grant doesn’t relax anything else** — still follow `ardi`, `fully-clean`, the git safety protocol, and every other standing procedure exactly as if the user were watching. `away` only changes what happens at the moment you’d otherwise stop and ask.

## Relationship to other skills

- **`back`** — the named counterpart that revokes this grant and surfaces the decision log described in Procedure step 4, so the user has a reviewable record of what was decided (and skipped) while they were away. Any of the phrasings in Scope and limits’ revocation bullet also end the grant, but `back` is the one worth invoking by name.
- **`mwc`** (merge-when-confident) — the sibling session-scoped grant for merge authority specifically. `away` covers decision-making latitude (don’t block on judgment calls); `mwc` covers the one destructive action (merging) `away` deliberately doesn’t extend to. Grant both together for full unattended PR throughput.
- **`select-model` / `assess-model-fit`** — own the model-tier knowledge `away`’s step 3 leans on for “consult a stronger model.” `away` doesn’t duplicate their tier table or escalation logic; it just names the trigger (a judgment call that would otherwise block) for invoking them.
- **`gi` / `gii` / `gia` / `gip`** — their own auto-proceed modes already skip the per-item confirmation and bypass blocked/oversized issues while surfacing the bypass; `away`’s step 2 generalizes that same skip-and-note pattern to genuinely ambiguous issues too, and extends the “don’t block” default to the whole session rather than one sweep.
- **`ardi`** — still runs exactly as documented under `away`; a reviewer’s finding is either fixable/rebuttable/deferrable by judgment (covered) or a genuine impasse needing a **human** reviewer (still escalate per `ardi`’s own deadlock rule — `away` doesn’t let you override a stuck review yourself).
- **`AskUserQuestion` tool** — `away` is what tells you *not* to reach for it on a judgment call; it doesn’t change when the tool itself is appropriate for the narrower information/authorization case that’s still in scope.

## Anti-patterns

- ❌ Treating `away` as license to skip `ardi`, `fully-clean`, or the git safety protocol — it only changes what happens at a “should I ask?” moment, nothing else.
- ❌ Guessing at a fact only the user could know (a preference, private context) instead of skipping/deferring that item — `away` covers judgment, not mind-reading.
- ❌ Treating a stronger-model consult as authorization for a destructive action — a second AI opinion raises confidence in a judgment call; it never substitutes for the user’s own sign-off where one is required.
- ❌ Silently picking the more aggressive/harder-to-reverse option under uncertainty instead of the conservative one, just because `away` is active.
- ❌ Reporting back only a “done” summary with no record of which calls were judgment calls made on the user’s behalf — the whole point is a scannable decision log they can review and countermand.
- ❌ Assuming `away` survives past the session it was granted in, or quietly extends into merge/destructive-action authority `mwc` alone covers.

Back to top
