# Case records: fail-fast

Worked-example case records for the rules in
[`fail-fast.md`](fail-fast.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## A usage error that would have been read as a verdict

(`Morrison-Lab/ai-config#1462`, 2026-08-14: `scripts/check-pr-fully-clean.py`
documents `0: fully clean` and `1: not clean` in its own docstring, and is the
corpus's verdict authority --- [`fully-clean`](../workflow/fully-clean.md) names
it as such, [`ardi`](../workflow/ardi.md) mandates it, and
[`hooks/no-handrolled-verdict-parse.py`](../../hooks/no-handrolled-verdict-parse.py)
refuses the hand-parse fallback until it has answered.
The PR added argument parsing and a `resolve_repo()` that fails loudly rather
than falling back to a hardcoded literal, and spelled both failures
`raise SystemExit("msg")`.
That exits **1**, so every usage error --- bad arguments, an unresolvable repo,
a URL passed where `OWNER/REPO` was wanted --- would have been reported to
every caller of the verdict authority as *this PR is not clean*.
Caught by the author's own pre-push self-review rather than by a test, because
the tests asserted `SystemExit` was raised and not which status it carried.
Fixed with a `USAGE_EXIT = 2` constant and a `die()` helper, plus two tests
asserting the code.

The exit-status figures in the rule above were measured directly rather than
recalled:

```bash
python3 -c 'raise SystemExit("some message")'; echo "rc=$?"   # some message, rc=1
python3 -c 'import sys; sys.exit("some message")'; echo "rc=$?"  # some message, rc=1
python3 -c 'raise SystemExit(2)'; echo "rc=$?"                # rc=2
python3 -c 'raise SystemExit(None)'; echo "rc=$?"             # rc=0
python3 -c 'raise SystemExit("x")' 2>/dev/null                # prints nothing: stderr
```

CPython 3.11.15.
A non-integer that is not `None` is printed and yields 1, so the collision is
not special to strings.)

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

The corpus already held the mechanism, at `memories/git-stash.md`'s
supersession bullet, which ships `grep '^+[^+]'` and names the
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

## The same block, where the comment stated an exclusion criterion

(`ucdavis/bcs`, 2026-08-13: a dialect word-list table carried a comment saying that words colliding with an R identifier are excluded "because each would be a false positive that blocks a push", naming `grey`/`gray` as the example.
The table immediately beneath it held `summarise`, a dplyr verb appearing in 19 files, plus `colour`, `labeller`, and `analyses`.
Same author, same commit, same shape as the case above.

What it adds is which of the two adjacent blocks fires.
The case above records a comment that removed nothing, so there was no survivor set to sweep and the hazard sentence itself was the whole predicate.
Here the comment states an **exclusion criterion**, so it is the "apply a comment's stated exclusion reason as a predicate to the members still present" block that governs --- and applying it was fully decidable rather than a matter of reading, because the repository's own green spellcheck already labels every in-scope word as accepted.
See [`algorithmatize-checks`](../workflow/algorithmatize-checks.md)'s "A green check on the default branch is a free labelled corpus" for the audit that mechanized it.)

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

## "A narrowing you argued for on one axis can be undone by an independent clause on a DIFFERENT axis"

(`Morrison-Lab/ai-config#1309`, 2026-08-08, on `scripts/compare-shell-forms.py`,
built by a subagent.
Its brief said any non-zero interpreter exit is a harness failure.
The agent narrowed that to 126/127 and flagged the departure, reasoning that
`grep` exits 1 legitimately and that comparing `grep` spellings is a core use of
the tool --- correct on its own terms, and the whole point of the deviation.
`looks_like_harness_failure` then read:

```python
if returncode in (CANNOT_EXECUTE, NOT_FOUND):
    return True
return any(marker in stderr for marker in NOT_FOUND_MARKERS)
```

The first clause implements the argued narrowing; the second matches
`command not found` / `No such file or directory` / `cannot execute` anywhere in
stderr, independent of the exit status, and restores the breadth the first
clause had just removed.
So `grep pat missing.txt` --- exit 2, printing "No such file or directory" ---
was reported HARNESS FAILURE, meaning "not a result about the forms", about the
most ordinary command the tool exists to compare.
Two clauses, two axes (a status and a text match), one question.

Fixed in `f6fbffc6` by deleting the marker clause rather than gating it, on the
measurement that it bought nothing: on this bash an unknown command exits 127
and a missing script exits 127, so every genuine case the markers were meant to
catch already carried a code.
Mutation-checked per clause afterwards --- restoring the free-floating matcher
fails exactly the new marker case, and removing the exit-code check fails five
--- which is the discipline the block prescribes, and it is what showed the
marker clause had been carrying no unique case at all.

Two cross-references rather than new rules.
The suite had contained
`check("a not-found message is a harness failure whatever the status", ...)` at
line 166, a regression test asserting the defect, which is
[`ardi`](../workflow/ardi.md)'s "a regression test written alongside a fix can
lock the bug in" rather than anything this section adds.
And the deviation was flagged in the agent's own report, which is where the
review should have started, per
[`metacognitive-monitoring`](../workflow/metacognitive-monitoring.md)'s
subagent-report section --- the rest of the work followed the brief and was
largely correct.)

## A rule written for one axis does not fire on the sibling axis

(`Morrison-Lab/ai-config#1353`, 2026-08-09, review finding 1, verified by the
reviewer executing the hook's own `offending()` against crafted input rather
than by reading it.
`standing_grant_target` in `hooks/no-unauthorized-merge.py` gates a standing
merge grant on two axes: *which repository* the merge lands in, and *what kind*
of merge it is.
Its docstring argued that reading the first of several matched repo targets is
unsound, and required the target set to have exactly one member so that
ambiguity denies --- and the code directly beneath implemented exactly that.

The merge-type axis then trusted whichever label `offending()`'s own
`MERGE_PATTERNS` loop happened to match first, one stack frame up, so the
first-match reading the docstring rejected arrived as an ordinary parameter.
Because the `pulls/N/merge` patterns are tried before the
`repos/<owner>/<name>/merges` ones, and both scan the segment unanchored, a real
branch merge carrying a forged `pulls/1/merge` substring in an unmasked `-H`
header was labelled `gh api PR merge`:

```
gh api -X POST repos/Morrison-Lab/ai-config/merges -f base=main -f head=x \
  -H "X-Note: repos/Morrison-Lab/ai-config/pulls/1/merge"
```

`-H` is a documented `gh api` flag and is not in `mask_payloads`'s recognized
list, so its value survives to the pattern scan.
The forged and the real `repos/<owner>/<name>/` paths named the same granted
repo, so the target test saw one target and granted a direct push to the
default branch with no PR, no review and no required checks --- the exact case
the PR's own `CLAUDE.md` bullet and `skills/mwc/SKILL.md` both claimed was
excluded.
The same command without the forged header was correctly blocked as
`gh api repository merge`, which is the negative control identifying the header
as the flip.

Fixed by running the ambiguity test on both axes: a new `matched_merge_labels`
re-derives every interpretation the segment matches, and the guard requires
`labels <= STANDING_GRANT_LABELS`.
Taken over the narrower patch of adding `-H` to `mask_payloads`, on the grounds
that the flag is not the problem --- `--header` and `--jq` are two more
carriers and the next one is unenumerable, which is the same argument
`PERMISSIVE_MERGE_PATTERNS` already makes for command positions.
Five regression cases were each confirmed to **allow** against the pre-fix hook
before being confirmed to block against the fixed one; a sixth candidate,
`--jq ".pulls/1/merge"`, was discarded on that check because the `.` before
`pulls/` meant it never matched the PR-merge pattern and so was blocked both
before and after, exercising nothing.)

## "Measure how each wrong answer decays, and check what the status quo already pays"

(`Morrison-Lab/ai-config#1283`, 2026-08-09, round 7 finding 5b, on
`hooks/no-unreviewed-pr.py`.
The question was what the guard should do when a same-turn transition is chained
ahead of a push, so the combined exit status cannot say whether that transition
succeeded: withhold the arm, risking a silently unreported unreviewed head, or
arm it, risking a warning the session cannot clear.

The rebuttal rested on an asymmetry between the two errors' futures.
A wrongly withheld arm self-heals, because the same ambiguity also withholds the
PR's pop from `live`, so the next push re-arms; a wrongly fired arm would recur
on every later event.
Well-formed, mechanism-level, and of exactly the shape this corpus rewards,
which is why nothing in the round prompted a check of it.

Running it settled what arguing about it had not.
Constructing the transcripts and executing both versions showed that the feared
recurrence was already present in the unchanged code, and unaffected by the
change under discussion --- so it was not a cost the change imposed.
What the suppression actually bought was one event's delay, a materially smaller
claim than the protection the argument had attributed to it.

Note what did not catch it.
The same round carried a clause-by-clause mutation matrix in which every clause
was detected and isolated by at least one case.
Mutation testing asks whether a clause is load-bearing; it never asks whether
the reason given for that clause is true.)

## "Normalizing repairs the instrument and not the needle"

(`Morrison-Lab/ai-config#1376`, squashed as `2ed74b89`, 2026-08-09/10.
That PR's own subject was the sibling cause: a line-oriented content check
false-negating in a semantic-line-break corpus.
Minutes after it merged, the merge was verified with the corrected normalizing
search, and two of three probes returned 0 against a file whose content had
demonstrably landed.

The instrument was not at fault.
The probes were: two of the three had been invented from prose *about* the
change rather than read out of it.

| probe | source | normalized hit |
| --- | --- | --- |
| `needs a normalizing search` | the PR title | 0 |
| `exits 1 when the count is 0` | paraphrase of the commit message | 0 |
| `straddles a newline` | the PR body, which happened to overlap the diff | 1 |
| `exits 1 when the count is zero` | the added prose itself | 1 |

Note the last two rows against the second.
The real text reads `zero` and the probe said `0`, so a single substituted word
produced the whole false negative --- which is why quoting a commit message
closely is not a defence.

Re-derive rather than trusting the table, since it is a claim about one commit:

```bash
python3 - <<'PY'
import re, subprocess
norm = lambda s: re.sub(r"[`*_\s]+", " ", s)
d = subprocess.run(["git","show","2ed74b89","--","shared/principles/fail-fast.md"],
                   capture_output=True, text=True).stdout
plus = [l for l in d.splitlines() if l.startswith("+")]
h = norm("\n".join(l[1:] for l in plus[1:]))   # [1:] drops the +++ header
for p in ["needs a normalizing search", "exits 1 when the count is 0",
          "straddles a newline", "exits 1 when the count is zero"]:
    print(f"{norm(p) in h!s:>5}  {p!r}")
PY
```

Both checks that would have settled it were free.
`git show --numstat 2ed74b89 -- shared/principles/fail-fast.md` returns
`31  0  shared/principles/fail-fast.md`, which proves the content landed with
no probe to get wrong.
And the same diff's added lines contain every string that could have served as
a probe, so deriving one discharges the known-positive rule at zero cost.

The dupe check for the rule this record supports also ran the other way and
found the general mechanism already owned.
`memories/debugging.md`'s "An empty grep for one spelling is not evidence the
concept is absent" covers a wrong-guessed spelling for a concept that is
present, and prescribes re-searching for the stable part of the concept.
What that entry does not say, and what is specific to merge verification, is
that the correct needle is obtainable for free from the diff --- so here the
guess is eliminable rather than merely improvable.)

## Five instruments in one session reporting a vacuous zero

(2026-08-07: five instruments in one session each returned an empty or zero
result that was read as absence --- a cumulative delta over a per-tick-cleared
array, a `gh pr diff --name-only` empty from API lag that returned 2 files on
re-query, an `ls A || ls B` fallback that did not say which branch answered, a
diff-scoped grep blind to a defect caused by a *deleted* line, and this one.
The last was published as a false claim by a session that had, earlier that same
day, written the vacuous-zero trap into this very file.
Read that as the argument for the denominator being a property of the
instrument rather than something recalled at the call site ---
[`skill-checklists`](../workflow/skill-checklists.md) already draws exactly that
conclusion, in its "knowing the rule is not what fails here" passage, and is the
place to read rather than restate it.)

## A 947-repo sweep that scanned nothing

(2026-07-28: a 947-repo scan reported `scanned: 0`, caught only because the
count was printed; the `chmod +x` had been in a command the permission
classifier denied minutes earlier.
A later run of the fixed script reported 910 of 947, which is how that same
sweep's rate-limit truncation was found --- the 37 repos it never reached.)

## Why no prefix pattern separates a diff header from its data

Measured on git 2.50.1, against a commit adding `++i;`, `++ foo` and `plain`:

| guard | survives |
|---|---|
| `grep -v '^+++'` | `plain` |
| `grep -v '^+++ '` | `++i;`, `plain` |
| positional | `++i;`, `++ foo`, `plain` |

## The per-file precondition, caught by dogfooding the guard

This is not a hypothetical: the pass that wrote this entry ran the guard over
its own three-file diff as a dogfooding check, and got three hits --- its own
two undropped headers plus one --- which read at first like defects in the
files rather than in the scan.
Per-file scanning returned 0 for every file, as did grepping the files
directly.

## A denominator three too high, from the documented remedy

(`Morrison-Lab/ai-config#1462`, 2026-08-14: an execution miss rather than a
coverage gap.
Both halves of the rule already existed in the section above --- the positional
`tail -n +2` remedy and the per-file precondition --- and the pre-push scan ran
the single-pass form anyway over a **4-file** diff, reporting
`0 hits in 297 added lines` where `git diff --shortstat` says 294.
Three leftover `+++ b/<path>` headers, exactly `files - 1`.
Nothing about the run announced it: the command exited 0, the hit count was
genuinely 0, and only the denominator was wrong.
What caught it was the cross-check, not a re-read of the pipeline.

Re-measured here on a three-file range of this repo's own history, so the
arithmetic is checkable without that PR's branch:

```bash
git diff --name-only fcc09f0~1...a47620b | wc -l          # 3
git diff --shortstat fcc09f0~1...a47620b                  # 267 insertions
git diff fcc09f0~1...a47620b | grep '^+' | tail -n +2 | wc -l   # 269
```

Two too high on three files.
Looping per file and summing returns 267, matching `--shortstat`.)

## What the tighter `^+[^+]` guard drops

Measured on git 2.50.1 against a two-paragraph addition: `^+[^+]` returned the
two lines of text and not the blank between them, while the positional form
returned all three.

## How far a `grep -o` pattern's own alphabet reaches into a value

Measured 2026-08-09 on `ucdavis/bcs`: of 45 sites carrying a ten-character
identifier, a pure-digit pattern matched **12**, and the remaining 33 mix
letters and digits in positions no digit-only rule reaches.

## One shared abbreviation list feeding two regex branches

(Morrison-Lab/gha#425, 2026-08-05: one abbreviation list (`_ABBREV_RE`) fed two
regex branches --- a lowercase-sentence branch and an uppercase one.
Dropping `No` from the list fixed the lowercase branch and un-protected `No.` on
the uppercase branch; registering every lowercase form then fixed the lowercase
branch and leaked protection onto the uppercase one.
Each edit traded one regression for the other until the fix became
architectural: a second, separately-scoped pass applied only after the first
branch ran.)

## A documented enabling procedure naming one of two required steps

(Morrison-Lab/gha#449, 2026-08-12: an opt-in `@claude review` dispatch was added
for repos that disable the agent, enabled by a repository variable **and** by
uncommenting an `issue_comment` trigger the stub ships commented out.
Every doc site named only the variable.
The job's `if:` requires `github.event_name == 'issue_comment'`, so following
the docs produced a one-second run with every job skipped and nothing posted ---
the exact silent no-op the PR existed to fix (gha#447).
Review caught it and called it blocking-ish; the fix stated both steps at six
sites, two more than the review had enumerated.)

## A proxy check that could not discriminate the case it was run for

Measured on `Morrison-Lab/ai-config`, where the two halves disagreed
outright:

| check | result |
|---|---|
| sampled local commit messages found on `origin/main` | 0 of 4 |
| files those commits touched, present on `origin/main` | 4 of 4 |
| paths on local `main` absent from `origin/main` | 0 |

## An empty merge-base substitution reporting HEAD as the merge base

(`Morrison-Lab/ai-config`, 2026-08-09, post-merge cleanup: local `main` and
`origin/main` had **no merge base at all**, and
`git log --oneline -1 $(git merge-base main origin/main)` duly printed local
`main`'s own tip, which was read as the merge base.
That reading implied `main` was an ancestor of `origin/main` while
`git merge-base --is-ancestor` in the same block reported it was not.
The same session then misattributed `$?` twice more --- once after a
pipeline and once after a command substitution --- while dupe-checking
whether this very entry already existed.)

## A published bullet count that was stale before anyone read it

Measured 2026-08-09 on `Morrison-Lab/ai-config`, that returned 3 of 5 carrying
zero bullets.
The sentence this replaced claimed 4 of 5, and the discrepancy is the point
rather than a correction to file away: one merge landed between the measurement
and the review that questioned it, so a bare count published without its command
was stale before anyone read it.

## A sound checker pointed at the wrong repository

(Morrison-Lab/ai-config#1327 / #1395, 2026-08-12: a pre-push semantic-line-break
scan was run as
`cd /home/user/gha && python3 check-new-line-breaks/check-new-line-breaks.py`,
from a session whose review target was `Morrison-Lab/ai-config`.
It printed `No lines missing semantic breaks.`, which was true of `gha`'s diff
and said nothing about ai-config's.

The checker was sound, correctly invoked, and given a real base ref.
Its own scope line reads
`Checking for missing semantic line breaks (lines added since <base_ref>)`, so
it names the comparison and not the tree --- and `origin/main` is a valid base
ref in both repositories, so that line is byte-identical whichever one it ran
in.
Re-running from the ai-config worktree was the whole fix.

Note which remedy this defeats.
The three vacuous-zero causes above all converge on printing a denominator, and
a denominator here would have been non-zero, correct, and equally silent, since
`gha`'s diff genuinely had lines to examine.)

## A precondition that could not fire on the case it named

(`Morrison-Lab/ai-config#1481`, 2026-08-15, review round 1, blocking.
`skills/ardia/SKILL.md`'s supersession recipe extracted a PR's added lines with
`git diff ... | grep '^+' | grep -v '^+++ '`, and its prose offered a guard:
confirm `grep -c '^++[^+]'` returns 0 before trusting the filter, "an added
line whose own text begins `++` is indistinguishable from a header once the
diff's marker is prepended".
The sentence cites this file's own "Why no prefix pattern separates a diff
header from its data" two lines later, in support of a second prefix pattern.

Reproduced on a real two-file `git diff` rather than by reasoning:

| raw content | appears in the diff as | dropped by `grep -v '^+++ '` | matched by `^++[^+]` |
| --- | --- | --- | --- |
| `++ dangerous collision case` | `+++ dangerous collision case` | **yes, wrongly** | **no** |
| `++i;` | `+++i;` | no | no |
| `+1 vote` | `++1 vote` | no | **yes**, harmlessly |

`git diff --numstat` reported 4 insertions and the filter emitted 3, having
silently eaten the collision line.
The guard returned **1** on that same stream --- and the line it named was
`++1 vote`, which the filter had handled correctly.
So it never saw the collision at all: the third character of `+++ foo` is `+`,
which fails `[^+]`.

The `0` that reached the PR body came from a different stream, and that is the
half worth keeping.
An ordinary diff carries no `++`-prefixed content, so the guard returns `0`
there --- confirmed on a control commit with none.
That is the number it returns on almost every real diff, and it is compatible
with both "no collision was present" and "a collision was present and I cannot
see it", because the pattern cannot express the second.
Published as a cross-check, it was a false all-clear in the fail-open
direction: not a wrong count, but a count of the wrong thing.

The fix removed the collision rather than detecting it, scoping the diff per
file so each header is dropped by position:

```bash
git diff --name-only "$base" <head> | while read -r f; do
  git diff -U0 "$base" <head> -- "$f" | grep '^+' | tail -n +2 | sed 's/^+//'
done
```

Against the same fixture that form preserves `++ dangerous collision case`,
leaks no headers, and yields 4 lines against `--numstat`'s 4.
The recipe now carries that `--numstat` comparison, whose value is computed
outside the pipeline it checks.

Two things worth keeping from how it was caught.
The reviewer verified by running the patterns rather than reading them, and
said so, which is what made the finding checkable rather than arguable.
And the corpus already contained the answer --- the review's own closing point
was that this file's table "independently confirms that `grep -v '^+++ '` drops
a raw `++ foo`-style line" --- so the defect was not missing knowledge but a
rule cited while being broken.)
