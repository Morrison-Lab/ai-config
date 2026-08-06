# Case records: fail-fast

Worked-example case records for the rules in
[`fail-fast.md`](fail-fast.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## "In a check you run by hand" --- the swallowed grep

(ai-config#754, 2026-07-28: a pre-push scan for banned punctuation used
`grep -P '[\x{2014}...]' || echo "none"`.
PCRE rejected the pattern with "character code point value in \x{} or \o{}
is too large", and the `||` branch printed `none`, which read as a pass.
A rewrite in Python found a real em-dash on an added line.)

## Setting the locale on the wrong command in a pipeline

(ai-config#871, 2026-07-30: a pre-push punctuation scan written as
`LC_ALL=C.UTF-8 git diff -U0 origin/main...HEAD | grep -P '[...]'` aborted with
rc=2.
The fix adopted was rewriting the scan in Python, which also reports how many
added lines it examined --- so a zero-hit result is distinguishable from a run
that examined nothing, per the fan-out section of
[`fail-fast.md`](fail-fast.md).)

## "The narration can be the unfalsifiable part"

(2026-08-03, one `ucdavis/bcs` session: three instances in about an hour, each
printed beneath output that contradicted it.
`(empty = my files are untouched by those commits)` beneath three filenames,
which was briefly believed and produced a wrong statement before a corrected
query caught it; `(no output above = no auto-review rule)` beneath the
`copilot_code_review` rule it denied; and `(empty above means none)` beneath
the commit it said was absent.
The two later ones were caught immediately, which is the point --- the pattern
recurred after being noticed twice, because nothing about writing the label
feels like making a claim.)

## "A zero-shaped summary can be sound" --- markdownlint scope line

(Morrison-Lab/ai-config#974, 2026-07-31: a `markdownlint-cli2` result already
published in a PR body as `0 issues in 0 files` was about to be re-reported as
a check that examined nothing.
Re-running it printed `Linting: 439 files` above the same summary.)

## "A background watcher reports failure as silence"

(2026-08-01, a `UCD-SERG/ucd-serg.github.io` session: two successive monitors
watching a PR's checks exited silently after 25 minutes, both written to print
only when zero checks were pending.
The first hid a red `validate`; the second hid nothing but was equally
uninformative.
Both were caught by querying the PR directly rather than by anything the
watchers did, and the second was armed *after* writing a status note about the
first --- so knowing the failure mode did not prevent repeating it within the
hour.)

## "The pattern itself is the other half" --- the unanchored `uses:` grep

(Morrison-Lab/gha#328/#329, 2026-07-31: the unanchored `uses: [a-z]` was
published in an issue and a merged PR body as *the* verification command
for a security invariant, so the phantom it produced was reported as a
regression before the pattern was re-read.)

## "The third one arrives in the repair" --- the empty-input sentinel

(Morrison-Lab/ai-config#1056, 2026-08-02: review round 1 found that a
verification step read the newest bot comment *after* dispatching a run, so a
pre-existing comment satisfied it and a broken credential read as working.
The repair split that read in two, taking a baseline with
`... | last | .id // "none"` and the later read with
`... | last | "\(.id) \(.createdAt)"`.
On jq 1.7.1 an empty selection yields `none` from the first and `null null`
from the second, so on any PR carrying no prior bot comment the two differ and
the check again reported success whatever the run did.
Round 2 caught it, and the landed fix is a single filter naming all four
outcomes rather than a patched sentinel.
The worked commands live in
[`refresh-claude-token`](../../skills/refresh-claude-token/SKILL.md), which
that PR merged on 2026-08-03.
This entry is the general rule.)

## "In a guard you ship: partial is worse than absent"

(ai-config#950/#951, 2026-07-30/31: `scripts/semantic-line-breaks.py` has three
emitters --- its own docstring lists "prose paragraphs, bullet continuation
text, and blockquote prose" --- and a draft of the scope fix guarded only the
blockquote one, leaving the two that do the bulk of the reflowing unscoped.
The script therefore still rewrote whole files while its source visibly
contained the fix; the unguarded behaviour changed 342 of `CLAUDE.md`'s 1163
lines.
Caught before it was committed, so the landed fix at `39b98c7b` already calls
`_in_scope` at all three sites --- which is why git history shows no trace of
the partial state, and why the enumeration has to happen while the guard is
being written rather than afterwards.)

## A review lifecycle playing the partial-guard failure out one path at a time

(Morrison-Lab/ai-config#1042, 2026-08-03: `hooks/no-unreviewed-pr.py` has four
parallel open/draft/request/self discharge-and-identity paths, and the
fail-safe guard --- structural identity, "last simple command", same-PR
scoping --- was applied to them one at a time across the review rather than all
at once, and each subsequent round surfaced the one path still unguarded: the
shell-command parser underlying them, then the `open` path (`open_ident`), then
the `self` discharge.
The per-path *discharge* mechanics of that same PR are in
[`fail-fast.md`](fail-fast.md)'s "A combined result cannot attribute a
per-step outcome" section.)

## "When the siblings are members of one pattern" --- the `grep` word boundary

(Morrison-Lab/ai-config#1151, 2026-08-04/05: at `dcd7eb0c^`,
`hooks/remind-brief-premises.py` carried a six-line comment at lines 185 to 190
recording that `cat`, `head`, and `tail` had been dropped from `DERIVE_ANY`
because "head commit", "head node", and "head_sha" occur constantly here, so
"a sentence merely naming a file next to the word `head` silently discharged a
real claim".
It even named the failure class and its symptom: "That is the
over-broad-discharge failure, and its symptom is silence, so nothing would have
reported it."
Two lines below, line 192 still read
`\b(?:git\s+)?(?:grep|rg|ag|ack)\b`, so the same hazard applied unchanged to
`grep`.
Review found that a claim sentence using "grep" as an English verb, or merely
naming `shared/workflow/grep-is-not-coverage.md`, discharged itself --- the
filename matching because `\b` treats `-` as a word boundary.
The stated reason covers both forms, so applying it as a predicate would have
caught them when the comment was written.
Fixed in `dcd7eb0c` by giving every command name a `(?![-\w])` suffix.)

## "A combined result cannot attribute a per-step outcome"

(Morrison-Lab/ai-config#1042, 2026-08-02/03: the `no-unreviewed-pr.py` Stop
hook took ~12 review rounds, six of them closing the same dangerous class ---
a discharge, an obligation-drop, and a draft-clear each fired on unattributable
or premature evidence.
Its discharge path churned across rounds 8-10, and round 9 is the clean instance
of the trap this section warns about: a fix that *reduced* a safe-direction nag
introduced a non-4xx-failure silent discharge, which round 10 caught and fixed.
They converged only when the ad-hoc patches were replaced by the single
`req_failed = (not last) or err or RX_REQ_FAILED(body)` invariant (discharge iff
`not req_failed`) plus result-gated `pending`/`pending_clear` maps, every term
mutation-checked.)
