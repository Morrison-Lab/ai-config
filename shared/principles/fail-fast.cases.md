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

## "A third direction" --- the diff header that rode into ported prose

(Morrison-Lab/ai-config#1290 -> #1296, 2026-08-08.
Sibling PR #1291 merged at 14:41:26Z, splitting
`shared/workflow/fully-clean.md` and
moving #1290's target section into the new
`shared/workflow/review-verdict-pitfalls.md`, so #1290 had to *port* its prose
rather than merge it.
The port extracted the content with
`git diff <base> <head> -- shared/workflow/fully-clean.md | grep '^+' | sed 's/^+//'`,
which kept the `+++ b/shared/workflow/fully-clean.md` header and stripped one
character from it.
The resulting `++ b/shared/workflow/fully-clean.md` landed mid-prose at line
810 in the conflict-resolution merge `4acf1895` at 14:51:38Z, eight minutes
before #1290 merged as `fa55c46a` at 14:59:26Z.

Four verdict-bearing review rounds had already run that morning --- 06:27:19Z,
06:44:13Z, 06:53:29Z, 07:01:10Z --- and none had the artifact in scope, since
the destination file did not enter the PR's diff until that final merge commit.
The reviewer said so itself: "review-verdict-pitfalls.md didn't exist in this
PR's diff until this merge commit, so it wasn't reachable by any prior review
round."
A fifth round dispatched at 15:02:53Z, after the merge, caught it; `613aba15`
removed it at 17:28:10Z, so it stood on `main` for 2h28m.

Two things kept it there.
A conflict-resolution commit is the least-scrutinized commit on a PR: it lands
after the review rounds and reads as mechanical.
And the mangling disguised the artifact --- an intact `+++ b/<path>` in prose
reads as machine output and gets deleted on sight, while `++ b/<path>` reads
as a typo or an odd bullet, so a read-through for sense passes over it.

The corpus already held the mechanism, at `memories/git.md`'s
stash-supersession bullet, which ships `grep '^+[^+]'` and names the
`+++ b/<path>` headers it excludes.
It did not transfer, and would not have been the right guard here anyway:
measured on git 2.50.1, `^+[^+]` drops added blank lines, so on prose it merges
paragraphs.

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

## "A fallback chain flattens which alternative won" --- the Godot binary path

(2026-08-07, a `Lacaedemon/sparta` session: locating the Godot 4.7 binary ran
`ls "C:/Users/dougm/Documents/Github/Godot_v4.7-stable_win64.exe/" 2>/dev/null`,
falling back with `||` to the same `ls` under `C:/Users/dougm/Downloads/`, and
then to a `find` sweep.
The first `ls` **failed** --- that path does not exist, which is why `||`
advanced at all --- and `2>/dev/null` ate the message saying so.
Two exe filenames then printed from the Downloads branch, were read as
confirming the first path, and a `GODOT` variable built from it failed with
"No such file or directory".
Both `ls` invocations would have printed those same two filenames, since `ls`
on a directory prints its contents rather than its path, so nothing in the
output distinguished them and re-reading the transcript could not have either.
Dropping the two `2>/dev/null` tokens would have prevented the whole thing;
`ls -d` on each candidate would also have been self-identifying.)

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

## The members in a LIST, with the branch inside the loop

(`Morrison-Lab/ai-config#1278`, 2026-08-08, round 6: `classify_verdict()` in
`scripts/check-pr-fully-clean.py` iterates
`for pat in VERDICT_NOT_CLEAN_PATTERNS`, and applied its negation-prefix guard
under `if pat == r"changes\s+requested\b":` --- the single member the guard had
originally been written for.
A sibling pattern added to that list in an earlier round therefore received no
negation handling at all, which is the defect round 6's reviewer found.
The members were not hidden inside one expression the way this section's
alternation case describes: the list literal spells them out, one per line, so
the "same expression, on the same screen" tell did not apply.
What suppressed the enumeration was the branch's own shape --- an equality test
against one literal reads as a special case rather than as an enumeration of
one, so adding a member to the list prompts no look at it.
The fix applies the guard to every member.
The same function's clean-side loop already showed the correct shape for a
genuine exception: `if pat in BARE_CLEAN_PATTERNS:` names the subset, so the
members it excludes are a list a reader can check rather than a literal nobody
revisits.)

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

## "A read-only question does not license a state-mutating answer"

(2026-08-08, `Morrison-Lab/ai-config#1287`: a hook test was failing and the
question was whether it also failed on `main`.
The diagnostic issued as one Bash call ended
`git stash -q 2>/dev/null; git checkout -q origin/main -- hooks/`.
Both commands did exactly what they say, which is why the composition read as a
single act of looking: the uncommitted work went to the stash and the whole
`hooks/` directory in the working tree and index was replaced by `main`'s
version, discarding the PR branch's own committed hook changes from the tree.
Recovered in full with `git checkout HEAD -- hooks/` and `git stash pop`, so the
cost was time rather than work.
The retry used `git archive origin/main hooks/ | tar -x -C "$(mktemp -d)"`,
which answered the same question with `git status` unchanged --- verified on
this corpus by extracting `hooks/` from `origin/main` into a scratch directory
and confirming the worktree stayed clean.
The path argument is load-bearing rather than incidental: omitting it archives
the whole tree instead of the one directory the question was about.)

## "Widen that last bullet's trigger" --- a hazard named and then committed

(`Morrison-Lab/ai-config#1278`, 2026-08-07/08: `scripts/check-pr-fully-clean.py`
carried, directly above its CLEAN verdict patterns, a comment opening
"Deliberately narrow."
and continuing "An over-broad CLEAN pattern is the dangerous direction: it would
let an incidental 'looks ready' in a later chatty comment discharge a standing
'Needs more work'."
The two patterns immediately beneath it were `\bReady\s+for\s+merge\b` and
`\bApproved\s+for\s+merge\b`, unanchored and unqualified, so
"This PR is not ready for merge until the two remaining findings are fixed."
classified as a CLEAN verdict --- the precise hazard the comment had just
named, one line down, in the same commit by the same author.
Unlike the `grep` word-boundary case above, nothing had been removed, so there
was no exclusion reason to re-run over survivors; the comment's own statement of
the hazard was the predicate, and reading the patterns against it would have
caught them.)

## "Enumerate the qualifier classes by which SIDE of the phrase they sit on"

(Same PR, the round that fixed the case above: review supplied three
counterexamples, and a negation lookbehind --- the natural reading of "guard the
phrase against qualifiers" --- closed the first two and left the third.
"not ready for merge" and "never ready for merge" put the qualifier BEFORE the
phrase; "ready for merge once the findings are fixed" puts a condition AFTER it,
where a lookbehind cannot see.
The shipped fix pairs `CLEAN_NEGATION_PREFIX` with a `CLEAN_CONDITIONAL_SUFFIX`
matching `once|after|when|if|unless|pending|provided|assuming|subject to|as soon
as|contingent`, applied only to the two bare phrases --- the `Verdict:`-anchored
patterns need no guard, since they require adjacency to the label.
The after-side form is the likelier one in a real review, because it is how a
reviewer signs off on nearly-done work.)

## "One side's own BOUNDARY can encode the negation of the other side's assumption"

(`Morrison-Lab/ai-config#1278`, 2026-08-08, rounds 2 to 6, on the same
`classify_verdict()` guard as the case above.
Rounds 2 and 3 built the before-side negation scan so that it deliberately looks
backward across a line break, and the reasoning was stated outright: this corpus
writes semantic line breaks, so a negation routinely sits at the end of the
previous line.
Two tests pin it.
Round 4's redesign then replaced a fixed-offset check with a sentence-scoped
one, defining `SENTENCE_END` as `[.!?\n]` --- a bare newline weighted equally
with a full stop.
`_sentence_remainder` therefore returned the empty string whenever a clean
pattern was followed immediately by a newline, so a qualifier opening the next
line was never searched, and the verdict classified as clean.
Round 5's review reproduced it against the extracted classifier and named the
split as "a very natural split under this corpus's own semantic-line-break
convention".
The author's own reply is the entry: "Same corpus property, mirrored side,
opposite conclusion, one round apart", adding "this is the same corpus property
the negation guard is built around" and "the part I should not have gotten
wrong".
Fixed in `7acb6bdd` by dropping `\n` as a terminator while keeping a blank line
as one, "since that is a paragraph break rather than a wrapped clause".
Widening it immediately surfaced the opposite failure, recorded against
[`algorithmatize-checks`](../workflow/algorithmatize-checks.cases.md): a
genuinely clean verdict began classifying as not-clean on an ordinary `but`
about 120 characters downstream, so the scan is now bounded to 60 characters or
the sentence, whichever ends first.
Note the four rounds' own progression, which the author summarised before the
last one: vocabulary, then scope, then position --- "each fix was correct about
the case in front of it and wrong about one level up".)
