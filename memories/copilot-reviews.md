# GitHub Copilot Code Reviews

GitHub Copilot pull-request code reviews (`copilot-pull-request-reviewer[bot]`,
`request_copilot_review` tool, and `requested_reviewers` API endpoint):
quota mechanics, latency, timing and per-push guarantees, suppressed comments,
branch-ruleset blocks, and review verification.
Split out of [`github-mcp-tools.md`](github-mcp-tools.md) topically per
ai-config#2969 (ai-config#694 pattern) to keep both files well under the
1250-line gate.

- **`mcp__github__request_copilot_review` is a real, separate tool** (not a
  `pull_request_read` method) --- requests a Copilot code review on a PR,
  equivalent to `gh api .../requested_reviewers -X POST -f
  "reviewers[]=copilot-pull-request-reviewer[bot]"`.
  Verified directly against `github/github-mcp-server`'s own source
  (`pkg/github/copilot.go`'s `RequestCopilotReview`), registered in the
  **default** toolset (`pkg/github/tools.go`), not behind an opt-in flag ---
  don't assume a tool is a hallucination just because it's absent from this
  file, which is a running collection of quirks encountered, not an
  exhaustive registry.
- **`request_copilot_review` returns success even when Copilot's quota is
  exhausted -- the refusal arrives later, as a posted review.**
  The tool reports no error and no output whether or not Copilot will
  actually review; what comes back minutes later is a `COMMENTED` review
  whose entire body is *"Copilot was unable to review this pull request
  because the user who requested the review has reached their quota
  limit"*.
  So a clean return is **not** evidence the quota is back, and neither is
  the absence of an error --- only the posted review body settles it.
  Two further specifics:
  - The quota is **per requesting user**, not per repo or per PR, so every
    request from the same account keeps refusing until it resets, however
    many different PRs it's spread across.
  - **Latency is a weak tell, and an untested one.**
    Every refusal came back within roughly a minute of the request.
    A later request was still pending when last checked about ten minutes
    in, which is the only reason to suspect a long-pending request may be
    a real review rather than a slow refusal -- but its outcome was never
    observed, because the PR merged first.
    So treat a long wait as weak grounds for holding off on re-requesting,
    not as evidence a review is coming, and read the posted review either
    way.
  Copilot and the `@claude` reviewer fail **independently**: Copilot can be
  quota-dead while `claude-review` posts genuine verdicts at the same head,
  so a Copilot refusal is never a reason to stop checking the other one.
  (`ucdavis/rampp#111`, 2026-07-24/25: three refusals across two heads while
  `claude-review` reviewed both normally, and Copilot itself had worked on
  the same PR two days earlier.)
- **Copilot's per-push review is not guaranteed, and a missing one is
  silent.**
  Measured on [Morrison-Lab/ai-config#2913](https://github.com/Morrison-Lab/ai-config/pull/2913)
  on 2026-09-01 PT (2026-09-02 on the UTC clock used below).
  Every source is public and re-runnable: commit times from
  `git log --format=%cI` on `refs/pull/2913/head`; check runs from
  `GET repos/Morrison-Lab/ai-config/commits/<sha>/check-runs` filtered to
  `name == "copilot-pull-request-reviewer"`; request times from the
  `review_requested` events whose `requested_reviewer.login` is `Copilot`
  on `GET repos/Morrison-Lab/ai-config/issues/2913/timeline`; review times
  from `get_reviews`.
  `28c20e5`: committed 03:17:52, requested 03:18:15, run `100111746156`
  started 03:18:28, review 03:23:12.
  `988b545`: committed 03:24:10, no run at 03:30, requested 03:31:08, run
  `100114154380` started 03:31:22, review 03:35:41.
  `3b32086`: committed 03:36:59, no run at 03:38, requested 03:39:03, run
  `100115600016` started 03:39:16, review 03:44:37.
  `ab89045`: committed 03:47:53, requested 03:48:09 without waiting, run
  `100117262861` started 03:48:21, review 03:53:50.
  Every run followed a request by twelve to sixteen seconds, none started
  on its own in the time it was given, and two waited seven and two minutes.
  `get_check_runs` (current head) or the per-SHA endpoint above is the tell.
  One minute is therefore the heuristic rather than a guarantee: an absent
  run after that is grounds to re-issue, and a duplicate request when
  creation was merely delayed is the accepted side of the trade.
  - **Do:** after every push to a PR that is ready for review (a draft's
    pushes defer review, per `hooks/no-unreviewed-pr.py`), confirm a
    `copilot-pull-request-reviewer` check run exists on the new head
    within about a minute.
    While one is queued or in progress, `pr-on-claim.md`'s rule against
    re-posting on an auto-requesting repo holds.
    Call `request_copilot_review` when none has appeared, and after a
    Rebut/Defer-only round with no push (`skills/ardi/SKILL.md`): the
    completed run on the unchanged head is no veto.
    **That instruction is suspended while the Copilot moratorium stands**, which is the live state whenever `MORATORIUM_END` in [`hooks/no-unreviewed-pr.py`](../hooks/no-unreviewed-pr.py) is still in the future.
    Every bullet in this file about *requesting* a review is suspended with it;
    the bullets about *reading* one that already exists are not, since an older review's findings still bind.
    On the two heads above that waited, a run followed the request within
    seconds, an observed sequence rather than a proven cause.
  - **Don't:** arm a check-in that waits on a round that never started.
  - **Don't:** read a real, successful past request on this same PR as still
    covering the current head --- the obligation is per-HEAD, not per-PR, so
    it re-arms on every push regardless of how many earlier heads were
    already reviewed.
    See [`mistake-patterns.md`](mistake-patterns.md) Pattern 51.
- **A Copilot review reporting `Comments generated: 0 new` can still carry
  findings.**
  They sit under `Suppressed comments` in the `COMMENTED` review body that
  `get_reviews` returns and nowhere in `get_review_comments`, so a
  `success` check run plus zero open threads is not a clean round.
  Rounds thirty-five and thirty-six on [#2913](https://github.com/Morrison-Lab/ai-config/pull/2913) each carried two such findings.
  The same shape from the `gh` side is `fully-clean.cases.md`'s
  collapsed-block case ([#1029](https://github.com/Morrison-Lab/ai-config/pull/1029)).
  - **Do:** read the review body with `get_reviews` every round.
    Page through every review page first, as `skills/ardi/SKILL.md`'s
    `--paginate` query does.
    Then filter the complete list to every entry whose `user.login` is
    `copilot-pull-request-reviewer[bot]` and whose `commit_id` is the
    current head, and work each unhandled one in submission order.
    Later human reviews can push that entry off the last page without the
    head moving, and the newest entry alone can be a human review or a
    stale round.
    `shared/workflow/review-verdict-pitfalls.md`'s reviewer-login table
    carries the field and value per surface.
  - **Don't:** call a round clean from `get_review_comments` and the check
    run alone.
- **A branch ruleset can block Copilot from pushing a fix while leaving my
  own push to the same branch unaffected.**
  When Copilot reports it prepared a change but could not apply it ---
  e.g. *"Cannot update this protected ref"* --- don't infer the branch is
  write-protected for this session too: try the push.
  The corollary matters more for review triage: a Copilot-identified issue
  still sitting unfixed may be unfixed because its push was rejected,
  **not** because the fix was wrong, disputed, or deliberately dropped.
  Re-check such a finding on its own merits rather than reading "Copilot
  left it alone" as a signal it was already settled.
  (`ucdavis/rampp#111`: Copilot had prepared the `DESCRIPTION` version bump
  that `version-check` was failing on and was rejected with that error; the
  identical fix pushed fine from this session as `0c72d81`.)
- **Copilot applied `one-function-per-file` to Python scripts and to test modules on 2026-09-01 (Pacific),
  and the written rule backs it as a standing requirement:
  rebut only from the rule's own carve-out, or comply.**
  Measured 2026-09-01 (Pacific) on [#2976](https://github.com/Morrison-Lab/ai-config/pull/2976):
  it asked for `_triggers` and a new `test_*` function to move into their
  own modules.
  The first rebuttal called the rule R-only, which
  [`shared/coding/one-function-per-file.md`](../shared/coding/one-function-per-file.md)
  contradicts: it applies per-language and names a substantial Python
  function, and it says an existing multi-function file is no exemption for
  a new function.
  What the rule does carve out is a two-liner ("a trivial wrapper or short
  helper", in its words) grouped with closely related functions in a
  shared file; "short helper" there describes the two-liner, not a second,
  looser exemption.
  So a rebuttal has to show the helper is about two lines and closely
  related to the functions beside it; anything larger goes in its own
  module.
  The helpers from [#2976](https://github.com/Morrison-Lab/ai-config/pull/2976) landed inline before this was checked and are
  tracked in
  [#2990](https://github.com/Morrison-Lab/ai-config/issues/2990).
  - **Do:** rebut only by the rule's own carve-out (a two-liner grouped
    with closely related functions), citing the fragment, or move any
    larger new function into its own module.
  - **Don't:** call the rule R-only, or cite a file's existing shape as if
    the fragment did not already address that case.
- **On a repository without a `review_on_push` ruleset, Copilot was not
  observed to re-review after a push until re-requested, and a
  re-requested round can repeat a finding the previous round already
  answered.**
  This is the measured shape on one PR; the per-push behaviour recorded
  earlier in this file is "not guaranteed", not "never".
  Measured 2026-09-01 (Pacific) on [#2976](https://github.com/Morrison-Lab/ai-config/pull/2976):
  a finding rebutted in one ARD comment was restated in the next review
  body's `Suppressed comments` section, in different words, while the
  inline thread kept only the earlier comment.
  So read the review body as well as the inline thread when checking for
  a repeat.
  A repeat says nothing by itself about whether the earlier disposition was
  a rebuttal or a fix; compare the repeated comment against the prior
  disposition on the thread (the ARD comment, or the fix commit) before
  treating it as new.
  - **Do:** read the prior round's disposition for a repeated comment, and
    answer it again by citing that disposition when nothing has changed.
  - **Don't:** treat repeated comment text as proof that an earlier fix did
    not land, or as a new finding, without checking the thread.
- **A PR does not count as clean for MWC while Copilot (or any review) is still running, even if another reviewer reported clean.**
  In [#3469](https://github.com/Morrison-Lab/ai-config/pull/3469#pullrequestreview-5175527714), Claude review finished clean at `06:09:39Z`,
  while Copilot was still running until `06:19:33Z` when it submitted `### 🟡 Changes recommended`.
  An in-flight review blocks clean status;
  consensus clean verdicts across all active reviewers are required before merging under MWC (ai-config#3570).
  - **Do:** wait for all running reviews (check runs in progress or pending review requests) to complete before evaluating whether the PR is fully clean.
  - **Don't:** declare clean or merge under MWC when one reviewer has finished clean while another review is still in flight.
- **Automated bot review tracking must account for formal states, header variations, and commit boundaries.**
  In `plugins/ai-config/enforce-mwc-review-gate.py`, bot reviews (like Copilot and CodeRabbit) require:
  1. Recognizing both formal states (`CHANGES_REQUESTED`, `APPROVED`, `DISMISSED`) and header verdicts (`Changes recommended`, `Needs a closer look`, `Approval recommended`).
  2. Preserving earlier `NOT_CLEAN` verdicts across commit pushes until the same reviewer evaluates the new HEAD commit or is dismissed/approved.
  3. Verifying `Suppressed comments` blocks even when the header states `Approval recommended`.
  4. Guarding against short commit abbreviations (`len(oid) >= 7`) before matching head OIDs.
  - **Do:** ensure bot review gates require a later clean review from the same bot or formal dismissal before clearing standing negative reviews across pushes.
  - **Don't:** drop standing bot findings simply because a new commit moved `HEAD`.
- **An empty BALANCED "Needs a closer look" review is non-blocking; the identical review at LITE effort still blocks.**
  The `ccr-overview-v2` heading `Needs a closer look` is Copilot flagging a large or ambiguous diff for a human's own judgment, not stating a finding.
  When it carries `**Review effort:** Balanced`, `**Findings:** None`, no "Open (N)" details block, and no "Previously missed" item, there is no finding behind it at all --- `scripts/check-pr-fully-clean.py`'s `copilot_verdict()` used to treat ANY `Needs a closer look` occurrence as `not-clean` unconditionally, so this exact shape blocked a merge with nothing to address ([Lacaedemon/sparta#1638](https://github.com/Lacaedemon/sparta/pull/1638), review 5316721676, `b36fe3bb`, 2026-09-25T10:42:37Z).
  Fixed in ai-config#4004: the carve-out reads the body as NO VERDICT (`""`), never as `clean` --- it must not count toward a clean-review quorum, and it must not supersede an earlier not-clean Copilot verdict from an earlier round.
  `Changes recommended` stays unconditionally blocking regardless of effort or Findings count; only `Needs a closer look` gets the carve-out.
  A `Lite` review carrying the identical `Findings: None` still blocks: `Needs a closer look` at Lite effort is Copilot declining to do a Balanced pass on a diff it judged too large, and it still needs a Balanced re-request before it says anything about the diff's actual content.
  A live re-check on the same merged PR after the fix landed: with an EARLIER `Needs a closer look` review (2026-09-25T09:44:20Z, same PR) that DOES carry a genuine `Previously missed (1)` item, `check-pr-fully-clean.py` correctly reports THAT round as the latest not-clean Copilot verdict, and the later empty-Balanced round at 10:42:37Z is silently skipped rather than reported at all --- confirming the carve-out discriminates a real finding from an empty flag-for-review even between two rounds of the same reviewer on the same PR.
  Applies to EVERY agent's merge gate, not just `check-pr-fully-clean.py` (CLAUDE.md's "Generalize instructions to every AI agent by default").
  Antigravity's own, independent Copilot classifier in `plugins/ai-config/enforce-mwc-review-gate.py` (`latest_bot_review_states()`, consumed by its `deny()` path) never calls `check-pr-fully-clean.py`, so it needed its own carve-out rather than inheriting one.
  `copilot_is_empty_balanced_closer_look()` there mirrors this same four-condition check, kept stdlib-only (no cross-module import) because the gate is staged into `~/.gemini/config/plugins/ai-config/` at a relative depth to `scripts/lib` that differs from the repo's own layout.
  Its FIRST version still used a bare `.search()` over the raw body throughout, which was itself a fail-open gap the reviewer caught one round later: an empty-Balanced shape stated ONLY inside an HTML comment or a collapsed `<details>` section (a re-review echoing a prior round's own overview) was carved out (read as no verdict) exactly like a live one, even though `check-pr-fully-clean.py`'s own block-and-liveness-aware parser already failed that shape closed to not-clean.
  Fixed by splitting the check in two: `_strip_non_live_regions()` builds a `live_body` (HTML comments and `<details>...</details>` regions removed, nesting and an unterminated opener both handled the same fail-closed way `scripts/lib/copilot_overview.py`'s own comment/details scan does), and the heading plus at least one Balanced effort line plus at least one `Findings: None` line must all exist in `live_body` -- while the uniformity checks (every effort line reads Balanced, every findings line reads None) and the `Previously missed`/`Open (N)` guards still scan the RAW, unstripped body, so a real finding hidden in a `<details>` still blocks.
  Covered in `scripts/test_enforce_mwc_review_gate.py`: empty-Balanced allows; Lite, Previously-missed, and Changes-recommended still deny; the empty shape stated only inside a `<details>` section, or only inside an HTML comment, still denies too.
  - **Do:** read an empty `Needs a closer look` review at Balanced effort (no Open/Previously-missed block, Findings: None) as no verdict, and keep waiting on or re-requesting review rather than treating it as a blocker to ARD.
  - **Do:** keep treating the identical shape at Lite effort, or one carrying an "Open (N)" listing or a "Previously missed" item, as a real not-clean verdict.
  - **Do:** give every independent Copilot-body classifier in this repo (currently `scripts/check-pr-fully-clean.py` and `plugins/ai-config/enforce-mwc-review-gate.py`) the same carve-out, since neither imports the other's logic.
  - **Do:** require the carve-out's EXISTENCE half (the heading, a Balanced effort line, a Findings: None line) to be checked against LIVE text with HTML comments and `<details>` regions removed, not against the raw body -- a shape stated only in a hidden or collapsed region is not the current round's own state.
  - **Don't:** let an empty Balanced "Needs a closer look" round count toward a clean-review quorum.
  - **Don't:** let it clear a standing not-clean verdict from an earlier round by the same reviewer --- it is silently skipped, not treated as an all-clear.
  - **Don't:** assume fixing one classifier (e.g. `check-pr-fully-clean.py`) reaches a sibling classifier that reads the same review body independently.
  - **Don't:** write a coarser-rigor classifier's existence checks as a bare `.search()` over the raw body -- that is sound for a DISQUALIFYING check (presence anywhere, hidden or not, should still block) but unsound for a REQUIRED one (existence only counts if it is live).
  (Directive from the user, 2026-09-25: "you can ignore empty 'balanced' copilot reviews like [Lacaedemon/sparta#1638#pullrequestreview-5316721676](https://github.com/Lacaedemon/sparta/pull/1638#pullrequestreview-5316721676)". Tracked as [ai-config#4004](https://github.com/Morrison-Lab/ai-config/issues/4004).)
- **`reviewRequests` is uninformative for Copilot in-flight status.**
  Check runs and review bodies govern instead.
  As measured in `memories/gh-cli.md`, `gh pr view --json reviewRequests` and REST `requested_reviewers`
  clear within moments of a request landing, even while Copilot is actively running or queued to review (as occurred in #3469).
  While `reviewRequests` catches pending requests when present (e.g. human reviewers), detecting Copilot in flight requires:
  1. Checking for queued or in-progress check runs (e.g. `copilot-pull-request-reviewer`)
     via the commit check-runs REST endpoint (`commits/<sha>/check-runs`),
     since GitHub GraphQL `statusCheckRollup` drops `copilot-pull-request-reviewer`
     (ai-config#3570, `fully-clean.cases.md:79`).
  2. Preserving prior `NOT_CLEAN` verdicts across pushes until a new clean review is posted on HEAD.
  - **Do:** check check-run status via the commit check-runs REST endpoint and poll `reviews[]` rather than relying on `reviewRequests` to know if Copilot is in flight.
  - **Don't:** treat an empty `reviewRequests` response as proof that Copilot has completed its review.
