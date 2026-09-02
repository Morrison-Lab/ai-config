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
    On the two heads above that waited, a run followed the request within
    seconds, an observed sequence rather than a proven cause.
  - **Don't:** arm a check-in that waits on a round that never started.
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
  The helpers from #2976 landed inline before this was checked and are
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
