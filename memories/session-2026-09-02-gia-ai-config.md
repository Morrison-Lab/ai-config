# Session notebook --- 2026-09-02 --- GIA over `Morrison-Lab/ai-config`

Invocation: `gia ai-config, mwc daytb`.
Grants active: `mwc` (merge when confident) and `daytb` (decide judgment calls myself).
Remote Claude Code session;
**no `gh`/`glab` CLI**, so forge work goes through the GitHub MCP tools per `tool-mappings.md`.

## Running log

- 2026-09-02 19:27 PDT --- session start.
  Phase 1 (ARDIA) surveying 9 open PRs.
- Environment findings, recorded because they change which instruments are usable:
  - `scripts/pr-overlap.py` and `scripts/check-pr-fully-clean.py` both shell out to `gh`, so both refuse in this session.
    `pr-overlap.py` fails loudly and correctly ("environment failure, not a verdict about any PR") rather than reporting a vacuous zero.
  - `GITHUB_TOKEN` is set and `api.github.com` is reachable, but passing it in a `curl` `Authorization` header is refused by the auto-mode classifier.
    MCP tools are the supported route.
  - Substitute for `pr-overlap.py`: fetch every `refs/pull/N/head` locally and derive the file sets with `git diff --name-only -M <merge-base> pr/N`.
    Same derivation, no `gh`.
- Open PRs at survey time (all authored by `d-morrison`, so all in scope): 3014, 3023 (draft), 3024, 3037, 3044, 3056, 3058, 3060 (draft), 3061.
- **Pairwise file-set collisions** (36 pairs examined, 4 collided;
  negative control: every PR but 3060 has a non-empty file set):
  - 3014 x 3023 --- `README.md`, `hooks/hooks.json`, `shared/workflow/adversarial-self-review.md`, `skills/ai-config-hooks/hooks/hooks.json`
  - 3014 x 3061 --- `shared/workflow/adversarial-self-review.md`
  - 3023 x 3056 --- `memories/git-worktrees.md`
  - 3023 x 3061 --- `shared/workflow/adversarial-self-review.md`
  - This is a **collision** derivation only.
    It cannot see a *dependency* (one PR asserting something another makes true);
    that needs a separate read.
- **PR 3060 has an empty diff (0 files changed).**
  It is a draft opened per `pr-on-claim` and never filled in, or its work landed elsewhere.
  Needs a decision rather than an ARDI round.
- 2026-09-02 19:39 PDT --- MERGED #3056 (squash, 9824358).
  Fully clean: verdict on head 5ccb612, 0 findings, 0 threads, all checks green.
  Announced merge intent and held 6 min; no peers reachable via ListAgents.
- Committed fixes awaiting adversarial review + push: #3058 (3 wrong citations -> check-credential-shape/gha#686), #3037 (MD018 at fully-clean.md:1311), #3014 (delete dead inside_quotes, preserve its rationale in quote_state_map).
- **Correction banked**: PR #3014's own session comment flagged two 'untested edge cases' (a flag between diff and refs;
  a long git -C prefix).
  Both are in fact ALREADY tested -- WARN_CASES carries 'git diff --stat main...pr-98' and a 'git -C' case, and mutation tests confirm the pre-existing suite catches both (78/80 and 79/80).
  My first instinct was to add regression cases;
  they were exact duplicates and were reverted.
  Verify coverage by mutating, not by reading a claim that something is untested.
- 2026-09-02 19:43 PDT --- **Another session is actively working these same PRs**, despite ListAgents reporting no peers (it only sees this machine).
  Evidence: #3037's branch gained 1c41ea2 at 19:31 PDT fixing the same MD018 I had just fixed locally, and its PR body was already de-staled.
  My duplicate commit was discarded in favour of theirs (theirs rewords so the reference sits mid-line;
  mine only prefixed it -- both clear MD018, theirs reads better).
  - Lesson, banked: check-before-pushing earned its keep here.
    A pre-push `git ls-remote` caught the divergence;
    pushing without it would have raced a peer's fix on a branch I had fetched 20 minutes earlier.
    The fetch was the stale artifact, not the branch.
  - Consequence for merge posture: mwc's twenty-minutes-clean-then-warn rule for another session's PR is load-bearing in this session, not ceremony.
- Pushed four PRs after adversarial review each (all reviews found real defects;
  none was a rubber stamp):
  - **#3058** e24539c --- corrected `check-credential-shape`/gha#686 citations, then round 2 found the entry ALSO misstated the mechanism: the rule is INTERIOR whitespace (a trailing newline is trimmed and tolerated by design), and the failure path spans three places (pre-flight exits 0 and posts nothing;
    "Resolve final review outcome" exits 1;
    `post-review` posts the comment).
    Round 3 found a missing blank line collapsing a bold lead-in into the previous paragraph.
  - **#3014** 656d579 --- deleted the dead `inside_quotes`, preserving its rationale.
    Review then proved BY MUTATION that the preserved rationale overclaims: bare `(` and a bare backtick are excluded by the separator class, NOT by quote state (stubbing `quote_state_map` leaves them silent);
    only `$(` and separator-preceded `then`/`do` are actually protected.
    Corrected, and added the two cases that pin it --- breaking the map now fails 4 cases, was 2.
  - **#3044** e0ba7b6 --- fixed a `gh api` brace-expansion command that could not have run, and an `/issues/2127` link to a merged PR.
    Review caught that my commit message restated Copilot's GFM-rendering justification as fact;
    it is false (CommonMark collapses a newline inside a code span;
    verified against a CommonMark renderer).
    Message corrected to keep the change and drop the bad reason.
  - **#3024** 0bc1b2e --- a peer force-pushed both fixes I had made, so I discarded mine and contributed only what theirs lacked: a test.
    Their null-author jq guard survived deletion with 182/182 green, i.e. it was unpinned.
- **Second peer collision**: #3024's branch was force-pushed (my base was not an ancestor).
  Caught by the pre-push `git ls-remote`, again.
- **#3023 (draft) turned out to be stalled, not held.**
  Its `updated_at` was ~9 h old while #3037/#3024 were minutes old, so the "peer is actively reworking it" read was wrong and it was mine to drive.
  Both defects its own draft-conversion comment named were reproduced and fixed:
  - A `#` comment disabled the guard outright.
    `simple_commands` rewrites newline to `;` BEFORE shlex, and shlex's `commenters` then swallows to end of INPUT rather than end of line.
    `git commit -m x # note\ngit push` measured `allow` pre-fix.
  - The denial echoed credentials into a transcript a session may paste onto a PR (Actions masking does not reach it).
    Seven credential shapes measured leaking pre-fix, none post-fix, with an over-redaction control asserting a benign command still reads back.
  - 3 mutations confirmed red: comment stripping removed (2), quote-blind stripping (1), redaction removed (3).
  - Dropped its `memories/git-worktrees.md` block: superseded by the merged #3056, and it would have re-added a claim `main` now explicitly refutes ("a hook cannot enumerate live agents").
    A merge of `origin/main` is what made that visible --- worth noting, since the collision matrix flagged 3023 x 3056 on that file as a CONFLICT risk and the real risk was semantic supersession, which no file-set intersection can see.
- Filed #3069: the same null-author jq defect in `skills/pr-status/SKILL.md` and `skills/pr-status-all/SKILL.md`, both pre-existing and outside #3024's diff.

## Round 4 --- what the verdict sweep returned

- #3058, #3014, #3044 all came back **Ready for merge** with structured `"findings": []`.
  Merge intent announced on each.
- #3024 came back **Needs more work** with four findings, and the root one is worth banking.
  The block text asserted the exit status "belongs to that later command", and the same paragraph hedged two sentences later that a `&&` chain may have short-circuited before the request ran.
  Both cannot be true.
  Neither direction supports the attribution: `false && <req> && verify` leaves the status with `false`, and `<req> && verify` with a failing request leaves it with the request.
  The sound claim is only the negative one --- the combined status cannot be attributed to the request.
- **A self-contradicting paragraph is a detectable shape.**
  The overclaim survived three review rounds while sitting two sentences from its own refutation, because each round read the hedge as a qualification rather than as a contradiction.
  Worth a checker: an unconditional attribution followed by a hedge that denies it.
- My own first fix on this PR fixed the chained paragraph and left the always-rendered recovery paragraph asserting the same thing.
  The lesson is the one the new test encodes: when a claim appears in three places, a needle over one of them passes while the others still assert it.
  Pin the negative claim over every paragraph that can carry it, not over the one you edited.
- Deferred #3071 (`request_ident` resolves only the first request in a chain) rather than sweeping it in: it is a pre-existing helper outside the diff, and the reviewer graded it non-blocking.

## Correction to my own earlier claim in this notebook

I recorded that the diff-scoped checks "cannot see an uncommitted change".
That is half right and the wrong half is load-bearing.
`gha-check-new-line-breaks.py` takes ADDED LINE NUMBERS from the `base...HEAD` diff but reads CONTENT from the working tree.
So a run over an uncommitted reformat compares committed line numbers against reformatted content and can report clean spuriously.
Measured here: CI failed 22 lines on #3070's commit, a `--write` reformat then reported clean while uncommitted, and only the post-commit re-run was trustworthy.
Commit, then re-run --- the rule survives, but "it sees nothing uncommitted" is not why.

## Account session limit hit, 2026-09-02 20:14 PDT

`claude-code-review` on #3070 posted the graceful-skip notice: "You've hit your session limit, resets 4:50am (UTC)" --- the mid-run 429 shape (gha#520), not a credential defect.
Reset is 04:50Z, which is 21:50 PDT.

What this does and does not invalidate, stated carefully because the distinction decides whether three merges may proceed:

- It does NOT retract a verdict already posted.
  #3058, #3014 and #3044 each carry a clean verdict on a head that has not moved since, obtained before the limit.
  Those PRs remain fully clean at head.
- It DOES mean any NEW review round is skipped.
  So #3070's newest head, #3024's `1152b26`, and anything I push to #3023 will get no external verdict until reset.
- `require-review` grays rather than reddens on this path, so a skipped round is not a red check to chase.

Consequence for the sweep: merging the three already-verified PRs is still correct, and opening NEW work (Phase 2) would produce PRs that cannot be reviewed for the next hour and a half.
The fallback is `shared/workflow/self-review-fallback.md` --- post a self-review at the bot's own standard --- but the adversarial-reviewer subagent runs on this same account, so it may be subject to the same limit.
That is worth measuring rather than assuming, since it decides whether the fallback is even available.

**Measured rather than assumed: the two quotas are separate pools.**
A one-word `haiku` subagent probe returned immediately while `claude-code-review` was refusing with a session limit.
So the limit is on the credential the CI workflow authenticates with, not on this session's own budget, and the adversarial-reviewer fallback stays available throughout the outage.
Worth knowing because the natural inference --- "the account is limited, so every Claude call is limited" --- is wrong, and acting on it would have stalled the sweep for ninety minutes for no reason.
The probe costs one cheap call and settles it.

- **Do:** probe with a trivial subagent call before concluding a quota outage reaches this session.
- **Don't:** infer from a CI review skip that self-review is unavailable too.

## Correction to a correction

I recorded earlier in this file that the diff-scoped checker "takes line numbers from the commit and content from the working tree" as though it were a fresh finding.
It is not.
`shared/writing/semantic-line-breaks.md` already carries it as its **third dirty-tree symptom**, in those words.
I asserted the gap from recollection rather than checking, which is exactly the failure [`grep-is-not-coverage`](../shared/workflow/grep-is-not-coverage.md) names, committed in the same session where I quoted that fragment's sibling rule approvingly.
The UMS pass caught it before it became a duplicate corpus entry, which is the argument for the pass running at all.

## Phase 1 outcome

Merged: #3056, #3014, #3058, #3044.
Pushed and awaiting review (blacked out until 21:50 PDT): #3023, #3024, #3070.
Left to the peer session: #3061 (its head moved again), #3037.
Untouched: #3060, an empty draft closing #3059.
Filed: #3069, #3071, #3072.

## Round 6 on #3023 --- three false verdicts, a false attribution, and an amend that hit the wrong commit

2026-09-03 09:33 PDT.
The round-5 verdict came back **Needs more work** with one finding, and Copilot added two more in a separate pass.
All three are false verdicts of the guard, and all three were reproduced against the shipped code before any fix:

| # | Source | Defect | Direction |
| --- | --- | --- | --- |
| F1 | Claude verdict | `_heredoc_free` scans only the FIRST heredoc opener on a line | false DENY |
| F2 | Copilot | `RX_HEREDOC_OPEN` matches the 2nd and 3rd `<` of a here-string | false ALLOW (silent guard) |
| F3 | Copilot | `strip_env` peels `export` as a wrapper | false DENY |

F3 is the one worth keeping.
`export FOO=1 git push` runs no git: `export` is a builtin whose arguments are names and assignments, so it exports the three names `FOO`, `git` and `push`.
Verified against bash directly rather than reasoned about.
Three of this PR's own test cases asserted the wrong reading and had to be replaced, which is the tell that the defect was in the model of the shell rather than in the code.

### The false attribution, and the amend that hit the wrong commit

Both lessons are now folded into durable memory, so only the session-specific facts stay here.

My first commit message said F1 was "a regression of this PR's own opener-line fix";
`7b54d28` reproduces the same defect by a different route, so it predated the fix.
`git commit --amend` after merging `main` in then retargeted the merge rather than the fix commit, and the recovery was a reset, amend and re-merge whose resulting tree hash matched the pre-reset one.

The generalizable halves live in [`metacognitive-monitoring`](../shared/workflow/metacognitive-monitoring.md), "Your own most recent change is a cause claim too" with its case record, and in [`git`](git.md), "`git commit --amend` after a merge amends the MERGE".
Read those rather than this;
the paragraphs that used to restate them here were pruned during the same UMS pass that wrote them, per [`run-ums-proactively`](../shared/workflow/run-ums-proactively.md)'s fold-or-prune step.
