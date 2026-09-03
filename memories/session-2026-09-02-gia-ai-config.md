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
