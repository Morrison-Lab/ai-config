# GitHub MCP tools (Claude Code remote/web sessions)

The GitHub MCP tool surface used in remote/web sessions where the `gh`
CLI is unavailable --- tool selection, scope and owner-string quirks,
review/comment/thread mechanics, and the specific failure modes each
tool has shown in practice.
Split out of `github.md` pre-emptively at 1199 lines, just under
`scripts/check-memory-file-size.py`'s gate --- that check fires strictly
above 1200 lines, so the file never actually tripped it.
See ai-config#694 for the precedent.

- In remote/web sessions the authenticated GitHub identity **can be** the repo
  owner (`the repository owner`), in which case requesting `the repository owner` as a PR reviewer
  fails with `422 Review cannot be requested from pull request author`.
  Harmless --- the PR is still created; the reviewer just isn't added. Don't
  treat the 422 as a failure to retry (it's expected per the standing
  request-pr-review rule when the author == the requested reviewer).
  **Do not read that as a standing property of remote sessions**, which is how
  this bullet read before it was caveated: identity varies by container and by
  client, so a container where an MCP write is attributed to `dem-extra1`
  instead accepts the same request with a `201`. See "A per-client identity
  table is a CONTAINER measurement" below for the measurement, and settle it
  by the attributed author of a write you actually made rather than from this
  bullet.
- `gh` is NOT available in these sessions — use the `mcp__github__*` tools for
  all GitHub interactions (PRs, issues, comments, reviews). CI status is always
  available via `mcp__github__pull_request_read` (`get_check_runs` / `get_status`)
  and the `mcp__github__actions_*` tools. Some environments may *also* expose a
  separate `github_ci` MCP server (`mcp__github_ci__*`, e.g. `get_ci_status`),
  which can connect asynchronously after session start. Don't conclude a tool is
  absent from one check — `ToolSearch` for what you need before deciding it's
  missing (and don't assume the `github_ci` server is present either).
- **An angle-bracket placeholder can vanish from a PR or issue body posted
  through these tools, and no markdown construct protects it.**
  A PR body written with `` `git ls-remote https://github.com/<owner>/<repo>` ``
  came back from the API as `git ls-remote https://github.com//`, with both
  placeholders gone.
  **No markdown construct protects them.**
  A controlled test posted the same string four ways in one body --- plain
  prose, an inline code span, an indented code block, and a fenced code block
  --- and all four came back stripped, so the removal happens to the raw body
  text and never reaches markdown parsing.
  The instinct that backticks make text literal is therefore wrong twice over
  here: neither the span nor the fence helps.
  What is lost is the *stored* body, not one rendering of it, so re-reading or
  re-rendering will not bring it back.
  The blast radius is narrower than it first looks, and worth knowing precisely:
  only text sent as a body through the API is affected.
  A `<placeholder>` inside a file committed in the same PR is untouched, so a
  memory entry documenting a command survives while the PR description quoting
  that same command does not.
  Write placeholders in a body without brackets --- `OWNER/REPO`, `PATH`, `N`
  --- and re-read the body after posting whenever the exact text matters.
  This is the "Postcondition gate" bullet in [`github.md`](github.md) made concrete:
  nothing errors, the object is created exactly as asked, and only reading the
  stored result back shows the content is not what was sent.
  (ai-config#734, 2026-07-26: caught only because the mangled URL happened to be
  re-read during an unrelated check.)
  **A later observation narrows what "angle-bracket" means here, and its
  mechanism is unconfirmed.**
  A PR body posted through `create_pull_request` on 2026-07-31 came back
  missing `<branch>`, `<gha-checkout>`, and `<base>`, leaving a documented
  command with no path and a `git reset --hard origin/` with no branch --- so
  the stored body carried instructions a reader would run and get wrong.
  Two contrasts stop that from reducing to "angle brackets are stripped".
  In the same body `<=` survived, stored as the escaped entity `&lt;=`, so
  only tag-shaped tokens went.
  And `<branch>` survived intact in a PR comment posted through
  `add_issue_comment` in the same session (ai-config#965), inside backticks in
  a blockquote, so the two write surfaces did not behave alike.
  Which layer strips --- the MCP tool, GitHub's sanitizer, or the two
  composed --- was not established, so read this as an observed effect rather
  than as a mechanism, and do not generalize either surface's behaviour to the
  other.
  The mitigation is unchanged and cheap: spell a placeholder in caps
  (`BRANCH`, `GHA-CHECKOUT`, `BASE`) in any body, where nothing can read it as
  a tag.
  A shell variable is the better form when the body is showing a command a
  reader will run: `$PR` survived a `create_pull_request` body intact on
  2026-08-17, and unlike a caps placeholder it leaves the command executable
  once the variable is set, rather than leaving a token to hand-substitute.
  Files in the diff were unaffected, as above --- the angle-bracket form
  inside a fenced code block is correct there and should stay.
  **`update_pull_request` strips a short placeholder token too, which extends
  this entry's per-surface table rather than opening a new question.**
  Be precise about how much is new here, because the neighbouring autolinks
  entry below already names `update_pull_request` as stripping angle-bracket
  *spans* --- see "The MCP write tools silently drop `<https://...>`
  angle-bracket autolinks", which covers `create_pull_request`,
  `update_pull_request`, and `issue_write` for a full URL.
  What that entry does not settle is the **short token** case this entry is
  about, and the two are worth keeping apart rather than merged: they track
  different content shapes, and this entry deliberately declines to generalize
  between surfaces at all.
  So the per-surface table for a short placeholder reads, as of 2026-08-15:
  `create_pull_request` strips, `update_pull_request` strips,
  `add_issue_comment` does not.
  Editing a body is the likelier moment to meet this than creating one, because
  a correction is exactly when a command gets spelled out for a reader.
  **And the correction describing the loss reproduces it**, which is the part
  worth knowing in advance: a note reading "the operands were spelled as the
  word `head` in angle brackets" is itself a body containing that token, so it
  is stripped too and the sentence explaining the damage arrives damaged.
  Describe the broken form rather than quoting it, the same move
  [`semantic-line-breaks`](../shared/writing/semantic-line-breaks.md) already
  prescribes where quoting a column-1 `#` reproduces the heading it warns
  about.
  Read the stored body back after any edit that adds a command, since the write
  call reports success either way.
  (ai-config#1467, 2026-08-15: a merge-order paragraph documenting
  `git diff --name-only $(git merge-base origin/main PR_HEAD)...PR_HEAD` was
  first written with both operands in angle brackets and came back as
  `$(git merge-base origin/main )...` with the operands gone; the correction
  note naming them was then stripped in turn, and only a third edit describing
  the form rather than showing it survived.)
- **`mcp__github__actions_run_trigger` can't re-run CI jobs in these sessions —
  it 403s.** `method: rerun_failed_jobs` (and `rerun_workflow_run`, and
  `cancel_workflow_run` -- the whole `actions: write` family, so you can neither
  restart a run nor stop one) returns
  `403 Resource not accessible by integration`: the integration token lacks the
  `actions: write` the re-run API needs. So a flaky CI failure can't be re-kicked
  via MCP — **push a commit to re-trigger the whole workflow** (the normal path
  during an iterate loop anyway), or ask the user to click Re-run. (Hit
  re-running a flaky `link-checker` timeout on a lab-manual PR.) **`method:
  run_workflow` (a fresh `workflow_dispatch`, not a rerun) 403s the same way** —
  the token lacks `actions: write` for dispatch too, not just for reruns, so
  don't expect a direct-dispatch workaround to succeed where rerun failed
  (confirmed on UCD-SERG/serodynamics#193, and again on `d-morrison/rme#1017`
  trying to dispatch `publish.yml` — same `403 Resource not accessible by
  integration`).
  **`run_workflow` succeeded on `Morrison-Lab/ai-config`, 2026-08-15, so treat
  this as per-session and per-repo rather than as a standing limit --- and
  attempt it before reporting it blocked.**
  Dispatching `claude-review.yml` with `ref` set to the PR branch and
  `inputs: {"pr_number": "1469"}` returned `204 No Content`, and the run
  genuinely started rather than merely queueing: run `31896086493`, with
  `review / gather-context` reading `in_progress` at `16:39:08Z` seconds later.
  That second check is the load-bearing one, since a 204 is an acknowledgement
  and says nothing about whether a job ran.
  **Every `inputs` value must be a JSON string, even when the workflow declares that input `type: number`.**
  `inputs: {"pr_number": 179}` (a JSON number) failed with `Invalid value for input 'pr_number'`; `inputs: {"pr_number": "179"}` (the same value as a string) queued the run.
  This is the `workflow_dispatch` REST API's own contract -- GitHub Actions inputs are always strings on the wire regardless of the declared `type`, which only affects the web-UI form control -- so the tool is not misbehaving, and the fix is to stringify every input value, not just the ones already quoted in an example.
  **Do:** pass every `actions_run_trigger` input as a string (`"179"`), including a value the workflow declares numeric.
  **Don't:** pass a bare JSON number for a `type: number` input and expect the declared type to be honored.
  **Do not generalize it to the rerun family.**
  `rerun_failed_jobs`, `rerun_workflow_run`, and `cancel_workflow_run` were not
  exercised in that session, so the bullet above stands unrefuted for them; what
  changed is one method on one repo, which is the same per-surface discipline
  the placeholder-stripping entry above insists on.
  The general lesson is [`growth-mindset`](../shared/workflow/growth-mindset.md)'s
  "First check the limitation is real": this was avoided for a whole session on
  the strength of a memory bullet, and one call refuted it.
  A recorded 403 is a measurement of a moment, so re-attempt rather than
  inheriting it, and timestamp whatever you find.
  Prefer folding
  the retry into a real, already-pending fix (e.g. a reviewer's requested
  wording tweak) over pushing a bare `--allow-empty` commit — same retrigger,
  no throwaway commit in history. Only use an empty commit when no real fix is
  pending. (ai-config#403.) **When the failing workflow only triggers on
  `push: main` / `workflow_dispatch` (no `pull_request` trigger), there's no
  "push a commit to re-trigger" fallback either** — nothing exercises the
  actual failing job pre-merge. Ask the user to dispatch it manually from the
  Actions UI (share the exact workflow filename + branch), and get their
  explicit go-ahead first if the workflow has a real side effect (e.g. a
  gh-pages deploy step not gated to `main`) — dispatching isn't just a status
  check in that case, it's a live action.
- **Merging runs the client split the other way: the raw API 403s and
  `mcp__github__merge_pull_request` succeeds.**
  `PUT /repos/{owner}/{repo}/pulls/{n}/merge` with `GH_TOKEN` returns
  `403 Merging into a protected base branch is not permitted for this session
  type.`
  The same merge, same method, same head SHA, goes through the MCP tool
  normally.
  What makes this worth its own bullet is the **wording**, which describes a
  policy rather than a client: it names the base branch's protection and the
  session's type, so the natural reading is "this session may not merge, and a
  branch-protection rule is why".
  Neither half is true, and both are the kind of claim nobody re-tests --- a
  merge authorization is expensive to obtain, so a refusal that appears to
  revoke one tends to be reported rather than retried.
  The generalizable part is that a 403 naming a policy is evidence about the
  client you used and about nothing else, so re-attempt through the other one
  before reporting the capability blocked.
  Do **not** read the sibling bullet above as the mirror case.
  Its 403s are MCP-side, for want of `actions: write`, and its fallbacks are a
  push or a human rather than a raw call --- the word "raw" appears nowhere in
  it, and the one success it records (`run_workflow` on this repo) is itself an
  MCP success.
  No raw-succeeds-where-MCP-403s instance is recorded here, so which client
  wins is not established in either direction; what is established is only that
  one client's refusal does not settle the question.
  - **Do:** re-attempt a 403'd write through the other client before reporting
    the capability blocked, whichever client you started with.
  - **Do:** read a 403 body that names a *repo* condition (branch protection,
    a ruleset) as still possibly client-scoped, and check the condition itself
    before believing it.
  - **Don't:** treat a refusal that mentions branch protection as evidence the
    base branch actually forbids the merge --- `mergeable_state` was `clean`
    and the merge succeeded seconds later.
  - **Don't:** report a merge as blocked on the strength of one client's
    refusal, since that hands a granted authorization back unused.
  (`Lacaedemon/sparta#1275`, 2026-08-16: merged at `16:39:24Z` as `cee465f6`
  via `mcp__github__merge_pull_request` with `merge_method: squash`, moments
  after the identical raw-API `PUT` returned the 403 above.
  `main` is protected there in the sense that the raw path refuses it, and the
  protection did not block the merge itself.)
- **`issue_write`'s `labels` REPLACES the issue's whole label set, and a name
  that does not exist yet is silently CREATED rather than rejected.** Two
  independent surprises in one parameter, pulling in opposite directions.
  The replace semantics come from the underlying REST "update an issue"
  endpoint, so passing `["needs-data"]` to an issue already carrying
  `["bug","tech-debt"]` drops both, with no warning and nothing in the
  response to notice --- always pass the **union** of existing plus new.
  Read the current labels first; `list_issues` already returns them, so a
  bulk pass needs no extra call per issue.
  The auto-creation runs the other way: it means a typo becomes a real label
  rather than an error, so a misspelling silently splits a set in two.
  Confirmed on `ucdavis/bcs`, 2026-07-29: applying `needs-data` to an issue
  in a repo that had no such label created it, and `get_label` then returned
  it with the default grey `#ededed` and an empty description.
  **Nothing in the MCP tool set can set a label's color or description** ---
  there is only `get_label` (`GET_LABEL` in
  [`tool-mappings.md`](../tool-mappings.md)), no create/update --- so a label
  born this way stays grey and undescribed until a human with **write**
  access fixes it, or a workflow with `issues: write` does it via `gh api`.
  Write, not admin: the Labels REST API's create/update endpoints need push
  access, while admin governs repository settings, branch protection, and
  webhooks.
  Note that the Triage role can *apply* an existing label but cannot create
  or edit one, so it is not sufficient here.
  Say so when handing off, rather than leaving someone to wonder why the new
  labels look unstyled.
- **Comments/replies you post via the GitHub MCP tools echo back into the session's `<github-webhook-activity>` events under the human account's identity, not a bot identity.**
  `add_reply_to_pull_request_comment` and `add_issue_comment` authenticate as the human who owns the session (e.g. `the repository owner`), so a webhook event for your own just-posted reply shows `Author: the repository owner` (or whichever human), never a recognizable bot name like `claude[bot]`.
  Don't use the author field to decide "is this my own echo, skip it."
  This is easy to get wrong at a glance since a same-author event looks exactly like a genuine human reply demanding a response.
  **Since 2026-08-24 every agent-posted comment also ends with `_Posted by Claude Code (AI agent) --- not written by a human._`**, which is the corpus-wide marker the `mcp__github__*` comment tools carry --- see [`disclose-agent-authorship`](../shared/workflow/disclose-agent-authorship.md).
  It is a more reliable self-echo test than the author field, and unlike the footer below it is required by a rule rather than by the harness's attribution setting.
  Comments posted before that date carry no marker, so the warning above still governs when auditing older threads.
  **Check for the Claude Code attribution footer instead of fuzzy-matching
  body text/timing** --- every comment posted from these sessions ends with
  `_Generated by [Claude Code](https://claude.ai/code)_` per the system
  prompt's attribution-footer requirement, so a webhook event whose body
  ends with that footer is a much sharper signal than eyeballing whether the
  wording looks familiar. (Hit repeatedly on
  `UCD-SERG/serocalculator#503`, 2026-07-24: several
  `add_reply_to_pull_request_comment` calls immediately produced a webhook
  event attributed to `the repository owner` quoting the reply verbatim --- each one
  a self-echo, not a new human comment, confirmed each time by re-reading
  the body rather than checking for the footer directly.)
  - **Scope that to the question it answers: is this a self-echo or a
    *human* reply.**
    Against a human it is decisive, because a human reply does not carry the
    footer.
    It is **not** proof the comment is this session's own post, and reading
    it that way fails in two directions.
    The footer is body text, so anyone who can comment can paste it --- which
    matters the moment the surrounding question is adversarial rather than
    merely a self-echo check.
    And it identifies a **class** ("some Claude Code session"), not an
    **instance**: a PR Steward or another session watching the same PR
    carries the identical footer, so a peer agent's comment reads as yours.
    Distinguishing *this* session needs something the body cannot forge ---
    match the comment id against a call you made, or the run URL against a
    run you own.
  - **The absence of a footer survives both objections**, which is what keeps
    the check useful.
    Neither a paste nor a peer session *removes* a footer from a comment that
    would otherwise carry one, so a body ending without one is near-conclusive
    evidence it is not agent-posted at all.
    Read the signal one-directionally: absence rules agent authorship out,
    presence does not rule it in.
    (`Morrison-Lab/wai#54`, 2026-08-09: this bullet's "mechanically,
    unambiguously your own post" was transplanted into a chapter that states a
    threat model, and the review's finding 5 correctly called it undercut ---
    "the footer is part of untrusted comment data, and doesn't distinguish
    this session from a peer agent session".
    Note the claim never changed; only the question around it did.
    See
    [`check-purpose-before-reusing`](../shared/workflow/check-purpose-before-reusing.md)'s
    "Reusing a CLAIM" section.)
- **A sustained run of `503` responses across every endpoint (not just PR
  reads) is a GitHub-side outage, not a per-call glitch — confirm with the
  cheapest possible probe, then stop retrying and back off.** When
  `pull_request_read`/`list_pull_requests` both 503, don't keep hammering the
  same call — call `mcp__github__get_me` (no arguments, smallest possible
  request) once: if that 503s too, it's a broad outage rather than something
  scoped to one repo, PR, or endpoint, and no amount of retrying the original
  call will help. Report the outage plainly, use whatever was last confirmed
  before it started, and re-check later rather than looping. (ai-config#583/
  #585 session, 2026-07-16: `pull_request_read`, `list_pull_requests`, and
  `get_me` all 503'd for roughly an hour across several separate check-ins;
  confirmed via `get_me` that it wasn't scoped to the two PRs being watched.)
- `mcp__github__pull_request_read` `method:` enum: `get` · `get_diff` (PR
  unified diff — equivalent to `gh pr diff`) · `get_status` · `get_files` ·
  `get_commits` · `get_review_comments` · `get_reviews` · `get_comments` ·
  `get_check_runs`.
- **`mcp__github__request_copilot_review` is a real, separate tool** (not a
  `pull_request_read` method) -- requests a Copilot code review on a PR,
  equivalent to `gh api .../requested_reviewers -X POST -f
  "reviewers[]=copilot-pull-request-reviewer[bot]"`. Verified directly
  against `github/github-mcp-server`'s own source
  (`pkg/github/copilot.go`'s `RequestCopilotReview`), registered in the
  **default** toolset (`pkg/github/tools.go`), not behind an opt-in flag --
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
  Measured on `Morrison-Lab/ai-config#2913`, 2026-09-01: three consecutive
  pushes (`988b545`, `3b32086`, `ab89045`) produced no
  `copilot-pull-request-reviewer` check run on the new head for several
  minutes, while `request_copilot_review` started one within about fifteen
  seconds each time and the review posted five to six minutes later.
  `get_check_runs` is the tell.
  On the pushes that did get a review (`28c20e5` and the three
  re-requested ones), the check run appeared within about a minute, so one
  minute is the operational heuristic rather than a guarantee: an absent
  run after that is grounds to re-issue, at the cost of a duplicate request
  when check creation was merely delayed, which is cheap next to a check-in
  that waits on a round that never started.
  - **Do:** after every push, confirm the check run exists on the new head,
    and call `request_copilot_review` when it is still absent after about a
    minute.
  - **Don't:** arm a check-in that waits on a round that never started.
- **A Copilot review reporting `Comments generated: 0 new` can still carry
  findings.**
  They sit under `Suppressed comments` in the review body that `get_reviews`
  returns (state `COMMENTED`, header `Needs a closer look`) and nowhere in
  `get_review_comments`, so a `success` check run plus zero open threads is
  not a clean round.
  Rounds thirty-five and thirty-six on `#2913` each carried two such findings.
  The same shape from the `gh` side is `fully-clean.cases.md`'s
  collapsed-block case (`#1029`).
  - **Do:** read the review body with `get_reviews` every round, selecting
    the entry whose `user.login` is `copilot-pull-request-reviewer[bot]` and
    whose `commit_id` is the current head, and paging past the first page
    (`perPage` 5, highest page number) on a long thread.
    The newest entry alone can be a human review or a stale round;
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
- **`get_status` can return "pending / 0 checks" even after CI has finished.**
  Use `get_check_runs` for the real job conclusions (`success`, `failure`,
  `skipped`) --- but see the bullet below: it is the more reliable of the two,
  not an authoritative source.
  `get_status` aggregates
  across check suites and can lag or show a stale "pending" when all runs have
  actually completed; `get_status` is unreliable for CI state.
  (Hit during the ai-config #275 GII session — `get_status` showed
  `total_count: 0` / `pending` while `get_check_runs` correctly showed all 5
  checks `success`.)
  **Given this, don't call `get_status` at all when checking CI state** —
  go straight to `get_check_runs`; calling both in parallel "to be safe"
  just spends a call on a field you already know not to trust. (Repeated
  on `Lacaedemon/sparta` PR #780, 2026-07-12: called both in parallel to
  confirm a canceled-review race, when `get_check_runs` alone — or, when
  the incoming webhook event already names the failing commit's SHA, a
  single `pull_request_read` `get` compared against that SHA — would have
  settled it in one call. See
  [`efficient-pr-babysitting`](../shared/workflow/efficient-pr-babysitting.md).)
- **`get_check_runs` is the better of the two, but it is not authoritative:
  it can report a job as `in_progress` minutes after that job finished.**
  The entry above says to prefer it over `get_status`, which still holds ---
  but read that as "less stale", not "correct".
  `actions_get` `get_workflow_job` on the same job id returns the true
  `status`/`conclusion`, and the two disagree often enough to matter.
  The cross-check is cheap and decides it exactly, so run it rather than
  reasoning about how long the job "should" have taken.
  It is worth running in **both** directions.
  Concluding "still running" from a stale `in_progress` only wastes a wait;
  the dangerous inverse is a
  rollup that has not yet caught up with a job that has since failed, which
  is why the cross-check belongs in the declare-clean sweep
  ([`fully-clean`](../shared/workflow/fully-clean.md) criterion 1) and not
  only when something looks slow.
  Do not over-correct, either: on the same PR minutes later, an
  `in_progress` R-CMD-check was genuinely still running, and the runs
  endpoint confirmed it.
  The endpoint is unreliable, not wrong.
  (`d-morrison/altdoc#61`, 2026-07-25: three instances in one afternoon ---
  `test-coverage`, `docs-check` (completed `21:12:56`, still reported
  `in_progress` after), and one true negative.)
- **`list_pull_requests` reports `merged: false` for every PR, merged ones
  included; `merged_at` is the field that discriminates.**
  The two bullets above are about *staleness*, where a field is sometimes
  wrong; here it is **constant**, so it is wrong for every merged PR while
  looking correct on any unmerged one you spot-check it against.
  A constant carries no information, the argument
  [`fully-clean`](../shared/workflow/fully-clean.md) also makes for `.state`.
  Measured on `Morrison-Lab/ai-config`, 2026-08-01, over 101 rows all `false`:

  | field | open (#1006) | merged (#1005) | closed unmerged (#505) |
  |---|---|---|---|
  | `list` `merged` | `false` | `false` | `false` |
  | `list` `merged_at` | absent | present | absent |
  | `get` `merged` | `false` | `true` | `false` |

  **It is not the `fields` projection**, the first thing to suspect and a
  different remedy: passing no `fields` argument at all returns the same value.
  `merged_by` is no fallback either, never served in a list response even when
  named in `fields` -- consistent with the list endpoint returning GitHub's
  smaller representation, though that is inferred rather than read from source.
  - **Do:** decide merged-versus-closed from `merged_at`, and call
    `pull_request_read` `get` when you need `merged` itself.
  - **Don't:** report a PR as closed-unmerged on a list response's `merged`
    field -- it says that about every PR in the repo.
- **`mcp__github__actions_list` (`list_workflow_runs`) returns a full repository
  object per run -- budget accordingly, and prefer a cheaper call.** Each run in
  the response carries `repository`, `head_repository`, `actor`, and
  `triggering_actor` in full, so even `per_page: 1` runs ~30-60KB and a
  `per_page: 3` call costs several thousand tokens; a large enough response
  blows the tool-output cap and gets spilled to a file instead of returned.
  When the question is "did CI/the review run, and how did it end",
  `pull_request_read` `get_check_runs` answers it for a fraction of that, and
  `actions_get` `get_workflow_run` (a single run by ID) is the right call when
  you need one run's event/trigger/conclusion. Reserve `list_workflow_runs` for
  when you genuinely need to enumerate runs the check-runs view can't see -- the
  `action_required`/zero-job case in
  [`fully-clean`](../shared/workflow/fully-clean.md) -- and when a call has
  already spilled to a file, parse that file
  (`python3 -c "json.load(...)"`) rather than re-listing.
  (ai-config#687, 2026-07-24:
  a two-run `list_workflow_runs` call to check whether a draft PR's review had
  fired cost ~6k tokens; `get_check_runs` gave the same answer.)
- **`gh pr view --json checks` is not a valid field.** When you need the
  combined status/check rollup from `gh pr view`, ask for `statusCheckRollup`
  instead; when you need the actual CI conclusions, use `gh pr checks` or the
  REST check-runs endpoint.
- **`mcp__github__push_files` strips executable bits** — files pushed via this
  tool always land with mode `100644`, regardless of their original mode. Scripts
  that were `100755` become non-executable. This is harmless when the workflow
  invokes them via `bash <script>` (not directly), but creates cosmetic
  inconsistency with sibling scripts. Workaround: fix the bit locally after
  merge with `chmod +x <script> && git add <script> && git commit -m "Restore executable bit"`. Track the deferred fix as a
  follow-up issue; don't block the PR on it. (Hit on `ucdavis/rampp#130` —
  both `reassign-reviewers.sh` and `stash-reviewers.sh` lost `100755`; tracked
  as `ucdavis/rampp#131`.)
- **When rewriting a file's full content via `push_files`, read the current
  file first and diff mentally.** Constructing the content from memory risks
  introducing typos or omitting lines — e.g. accidentally re-adding a
  previously-removed entry (`estiamnd` was re-introduced into `inst/WORDLIST`
  after being removed, requiring a correction commit). Always use
  `get_file_contents` to get the exact current content, then make the minimal
  targeted change before pushing.
- `mcp__github__pull_request_read` parameter names are **camelCase** — use
  `pullNumber`, NOT `pull_number`. Snake_case fails silently or errors.
- `mcp__github__add_issue_comment` parameter is **`issue_number`** (snake_case),
  NOT `issueNumber`. This is the opposite of `pull_request_read`. Reload the
  tool schema when unsure rather than guessing.
- **`mcp__github__issue_write` with `method: "update"` and a `body` param
  REPLACES the entire issue body -- it is not a way to post a comment.**
  Passing a short claim string like "Working on this" as `body` silently
  overwrites the full issue description with that one line; the call
  succeeds with no warning, since `update` genuinely means "set these
  fields," not "append." To post a comment, use
  `mcp__github__add_issue_comment` instead -- never pass `body` to
  `issue_write update` unless the actual intent is to edit/replace the
  issue's description. The tool's own result echoes back the (now-wrong)
  body, so the mistake is visible immediately if you check the response;
  fix it with a follow-up `issue_write update` call restoring the original
  text (keep a copy of the issue's existing body before editing it, since
  the tool's response only echoes the new state, not the prior one --
  or re-fetch it with `issue_read` `get` if you didn't), then post the
  actual comment via `add_issue_comment`. (Hit claiming
  `UCD-SERG/serocalculator#571` per the `claim-pr` convention: intended
  `add_issue_comment` but called `issue_write update` with just the claim
  text as `body`, clobbering the freshly-filed issue description --- caught
  immediately from the echoed response and fixed with a restore-then-comment
  pair of calls.)
- **A milder, distinct mistake with the same tool: `issue_write`'s `method`
  enum accepts only `"create"` or `"update"` --- there is no
  `"add_comment"`.**
  Guessing `method: "add_comment"` (a plausible name with no analog in the
  real schema) fails loudly and immediately: `invalid method, must be
  either 'create' or 'update'`.
  No data is touched, unlike the silent clobbering above --- so this is a
  safe failure mode, not a dangerous one, and the fix is simply to call
  `add_issue_comment` instead.
  Still worth naming so the two are not conflated: one fails loud and safe
  at the call itself, the other succeeds and silently destroys prior
  content.
  (Hit while posting evidence to `Morrison-Lab/ai-config#1330`, 2026-08-10;
  recovered with the correct tool on retry.)
- **`mcp__github__create_or_update_file`'s `content` param is raw plain text,
  not base64** — despite the GitHub REST API's own `PUT /repos/.../contents/`
  endpoint taking base64, this MCP tool does the encoding for you. Passing an
  already-encoded (or garbled-looking) string writes that literal string as the
  file body — it does not decode it first, and the call still reports success,
  so there's no error to catch the mistake. **Verify the write**: the response's
  `content.size` should roughly match the source text's byte length; a
  suspiciously small `size` (e.g. 113 bytes for a file that should be ~2700)
  means the wrong content shipped. Fix immediately with a follow-up
  `create_or_update_file` call using the new `sha` from the bad commit — don't
  leave a broken file on the branch waiting for the next review round to catch
  it. (Hit on lab-manual#376: an editing slip sent a truncated placeholder
  instead of the real fragment text; caught by checking the returned `size`.)
  **Confirmed again with a different downstream symptom, and it defeats a
  naive round-trip check.** Passing an already-base64-encoded string produced
  a `size` of 2310 bytes for content that should have been 1710 -- a ~4/3
  inflation, the base64 expansion ratio, rather than a suspiciously *small*
  number this time. The GitHub Actions symptom was different too: since the
  stored blob was a bare base64 scalar rather than a YAML mapping, the
  workflow read as having no triggers at all -- a dispatch-time `422
  Workflow does not have 'workflow_dispatch' trigger` on that ref (dispatch
  to the unmodified default branch worked fine), and the push itself
  produced a generic `failure` conclusion with zero jobs (not
  `startup_failure`, which is the permissions-cascade shape covered in
  [`gha-reusable-workflow-permissions.md`](gha-reusable-workflow-permissions.md)).
  A naive "does it decode without erroring"
  round-trip check does not catch this: base64-decoding what
  `get_file_contents` reads back just undoes your own accidental encoding
  and returns the intended text, which looks like confirmation. The `size`
  comparison against the source's real byte length is the check that
  actually discriminates. (Morrison-Lab/psw#44, 2026-08-10.)
  **A third instance is not an encoding mistake at all --- the `content`
  parameter can simply be constructed wrong.**
  A follow-up call meant to correct the two case records above instead sent
  a literal placeholder string as the whole file body, caught immediately
  by `content.size` reading 21 bytes for a ~50KB file.
  **A local clone plus a real `git push` avoids this class of mistake
  entirely, when push is available.**
  `git clone --depth 1 --filter=blob:none --sparse` plus `git push` from
  that clone worked in this same session, for a branch that was neither
  harness-assigned nor the working directory's own repo --- consistent
  with [`github-remote-sessions.md`](github-remote-sessions.md)'s
  "the proxy allows branch creation/push but BLOCKS branch deletion."
  `git config -l` showed no local credential (only
  `http.proxyauthmethod=basic` and `credential.interactive=false`, no
  `~/.git-credentials` or `~/.netrc`), so authentication happens somewhere
  in the outbound proxy layer rather than the checkout --- consistent with
  this environment's outbound HTTPS being proxied, though the exact
  mechanism wasn't traced further.
  Once a branch exists to push to, prefer editing the file locally and
  pushing over `create_or_update_file`/`push_files` for anything beyond a
  trivial edit: the committed content is exactly what `git diff` shows, and
  `git hash-object` verifies it byte-for-byte before AND after the push,
  with no encoding step or parameter-construction step for a mistake to
  hide in.
  Not every session gets this --- some are restricted to the
  harness-assigned branch only, or fully read-only, per
  [`gha-reusable-workflows.md`](gha-reusable-workflows.md)'s "403 caveat"
  and "fully READ-ONLY" entries --- so test with a throwaway push before relying on
  it.
- **Issue *writes* 404 while *reads* succeed → the issue was transferred to
  another repo, not a permissions gap.** If `mcp__github__add_issue_comment` /
  `issue_write` to `owner/repo#<N>` fail (`404 Not Found`, or `Could not resolve
  to an Issue with the number of <N>`) but `issue_read` (`get`) on the *same*
  number succeeds and PR-comment writes work, suspect a **GitHub issue
  transfer**. A transfer redirects the old number for *reads* — `issue_read`
  silently follows the redirect and returns the issue at its NEW home, so check
  the returned `html_url`/`number` (they show a different repo/number). Writes to
  the old `owner/repo/issues/<N>` 404 because the issue no longer lives there.
  Fix: re-read to get the new repo + number, then comment/close *there*. Don't
  misdiagnose it as a missing `Issues:write` token scope. (Caught closing
  `gha#75`, transferred to `rme#941`.)
- **A pinned upstream commit SHA that 404s on the GitHub API can mean the
  whole repo moved orgs, not just a stale/rewritten pin.** `renv::restore()`
  (or any tool resolving a `Remotes:`-style GitHub pin) failing with a plain
  network-looking error (curl "error code 22" wrapping an HTTP error) on a
  commit-metadata fetch is easy to read as "transient" or "just re-pin to
  latest `main`." Before assuming that, check whether the source repo itself
  still exists at that path: fetch its `github.com` root page (not
  `api.github.com`, which a sandbox proxy may block for out-of-scope repos —
  use `WebFetch` on the plain `github.com/<owner>/<repo>` URL instead) and
  look for a "this repo has moved to `<new-owner>/<repo>`" redirect notice —
  some orgs (e.g. `insightsengineering`) replace a migrated repo's content
  entirely with a redirect stub and drop its git history, which orphans every
  previously-pinned commit SHA outright (a real 404, not a rate limit or
  blip). Fix by repointing the `Remotes:`/lockfile entry at the NEW org and a
  current commit there, not by re-snapshotting blindly (see the
  `renv::snapshot()` destructive-mistake entry below for why not) or assuming
  a simple re-pin to the old repo's `main` will work.
  (`d-morrison/rme#1017`: `insightsengineering/cards` had moved to
  `pharmaverse/cards`; the old repo was reduced to a redirect-only stub with
  history removed, orphaning the pinned SHA.)
- **WebFetch summarizes rendered page text through a small model, which can
  garble a long hex string (e.g. a 40-char git SHA) even when the source page
  is fetched correctly.** Don't trust a SHA read back from prose/rendered
  text alone — cross-check by asking WebFetch specifically for an anchor
  `href` containing the SHA as a URL path segment (e.g.
  `/owner/repo/commit/<sha>`), which is far less prone to transcription
  errors than reading digits out of rendered commit-page text, and repeat the
  fetch 2-3× to confirm the same value comes back consistently before using
  it in a commit/config change. (`d-morrison/rme#1017`: eyeballing a
  WebFetch-rendered SHA left doubt about its exact length at a glance; an
  href-based cross-check against the commit permalink URL, repeated across
  three independent fetches, confirmed the same 40-char value each time
  before it was used in the fix.)
- **Read a commit SHA back from git before citing it in a comment; never
  write one from memory.** The bullet above covers a SHA *garbled in
  transit* by WebFetch; this is the adjacent failure of never having looked
  it up at all. A PR reply that names "the commit that fixed this" is a
  checkable reference, and an invented one sends every later reader to
  nothing. `git rev-parse --short HEAD` immediately after the push costs one
  call. Correct a wrong one on the thread promptly rather than at leisure:
  an automated reviewer gathers comments when its run starts, so a
  fabricated SHA left standing gets copied into the reviewer's own verdict
  and becomes a second durable artifact to chase. (ai-config#696: a reply
  cited `0d2ec06`, which existed nowhere on the branch -- the real commit
  was `30ac111` -- and the `@claude` reviewer quoted `0d2ec06` back in its
  next review before the correction landed.)
- **In a fresh web/remote container, local `origin/*` refs can be stale or
  phantom — verify true remote state via MCP, not local refs.** The clone's
  `remotes/origin/main` may lag the real default branch by already-merged
  commits, and the harness-assigned `claude/<id>` branch can appear under
  `git branch -a` as `remotes/origin/claude/<id>` while not existing on the real
  remote (`get_file_contents` with `ref: refs/heads/claude/<id>` returns 404).
  `git fetch origin` (all refs) can also exceed the 2-min Bash limit on large
  repos with submodules (rme). To read the real default-branch HEAD cheaply,
  `get_file_contents` any file with no `ref` (= default branch) — the returned
  resource path embeds the live commit SHA. Fetch the single branch you need
  (`git fetch origin main`) and branch off that, so you don't build on a
  stale/polluted base.
- `mcp__github__pull_request_review_write` with `method: resolve_thread`
  requires **only `threadId`** (node ID, e.g. `PRRT_kwDO...`); `owner`,
  `repo`, and `pullNumber` are ignored for that method. Thread node IDs come
  from `get_review_comments` --- **fetch them, never reconstruct one.** They
  are opaque base64, so a plausible-looking id assembled from a remembered
  prefix plus the suffix of a *different* thread fails with "Could not
  resolve to a node with the global id"; that error means the id was
  invented, not that the thread is gone.
  On a PR with many threads, the
  temptation is to skip a re-fetch because the list was read a few calls
  ago --- but a new review round appends threads, so the ones you need are
  exactly the ones not in that earlier read.
  When only the newest threads
  are wanted, `get_review_comments` takes an `after` cursor: pass the
  `endCursor` from the previous listing and get just what has appeared
  since, rather than re-fetching every thread.
  **`page` does not do this for this method**, so `page: 2` returns the
  first page again.
  The tool's own schema is the authority, not the REST
  endpoint [`tool-mappings.md`](../tool-mappings.md) lists as the `gh`
  equivalent: `after` is documented as "used only by the
  `get_review_comments` method", and that method's own description says
  "use cursor-based pagination (`perPage`, `after`)", while `page` is a
  generic parameter shared with the REST-backed methods on the same tool.
  The `PRRT_`-prefixed thread ids corroborate it --- those are GraphQL
  global node ids, which the REST comments endpoint does not return.
  So one `pull_request_read` tool spans both pagination models depending
  on `method`; don't generalize either one across it.
  (Guessed twice in one `d-morrison/altdoc#78` session, 2026-07-27,
  costing two failed calls before fetching properly.)
- **A repository transfer breaks `mcp__github__resolve_review_thread`
  specifically, and neither owner spelling works.**
  The standing advice for a transferred repo --- keep using whichever owner
  the session was scoped with, since the API follows the transfer redirect
  server-side --- holds for every call that names the repo by `owner`/`repo`
  **strings**.
  It does not hold for this tool, whose `threadId` is a GraphQL node ID
  rather than a name, so the declared owner and the node have to agree.
  Read that as an observed gate rather than as a mechanism.
  This entry first explained it as the node "already encoding the
  post-transfer repo", which decoding one shows is the wrong story:
  `PRRT_kwDOShagnM6VdO1_` is MessagePack for
  `[0, 1242996892, 2507468159]`, whose middle element is the repository's
  database ID --- the same value carried by the repo's own node ID
  (`R_kgDOShagnA`) and returned as `id` by the REST API.
  A transfer leaves that number alone, so the node names an identity with no
  pre- or post-transfer form to disagree about.
  What the first error below establishes is only that the server compares the
  node's repository against the declared `owner`/`repo` string and rejects
  the pair.
  The second establishes a separate gate, the session's own repository scope
  list, which never examines the node at all.
  It is not the first comparison in different words: `Morrison-Lab/ai-config`
  is the node's own repository, so that comparison would have matched.
  Why that first comparison fails where string-addressed calls follow the
  redirect was not established.
  Measured on `Morrison-Lab/ai-config` (transferred from `d-morrison`),
  2026-07-31, against PR #975 --- two different gates, one per spelling:
  - `owner: d-morrison` --- `Access denied: review thread
    PRRT_kwDOShagnM6VdO1_ does not belong to the declared repo
    "d-morrison/ai-config".`
  - `owner: Morrison-Lab` --- `Access denied: repository
    "morrison-lab/ai-config" is not configured for this session.
    Allowed repositories: d-morrison/gha, d-morrison/workflows,
    d-morrison/ai-config, d-morrison/rpt, d-morrison/qwt, d-morrison/qbt`

  The second is the session's own repo-scope list, which is fixed at session
  start, and `add_repo` refuses a cross-owner add --- so this is **not
  transient**, and re-testing it each polling round buys nothing.
  Every other tool used in that session worked normally under
  `owner: d-morrison`: `pull_request_read` (every method),
  `add_issue_comment`, `add_reply_to_pull_request_comment`,
  `update_pull_request`, `request_copilot_review`, and
  `subscribe_pr_activity`.
  So the split is between string-addressed and node-addressed calls, not
  between read and write.

  The consequence is worth stating plainly, because it is easy to mistake for
  work left undone.
  [`fully-clean`](../shared/workflow/fully-clean.md) makes "every inline
  review thread is resolved" a criterion for calling a PR clean, so in a
  transferred-repo session that criterion is **structurally unreachable**:
  every finding can be Addressed and replied to, and the PR still cannot be
  reported fully clean from this session.
  Resolve the threads from the GitHub UI, or from a session scoped to the new
  owner.

  One untested alternative, recorded so the next session tries it before the
  UI.
  `pull_request_review_write` with `method: resolve_thread` is a separate tool
  whose own schema says the `owner`, `repo`, and `pullNumber` it still
  requires "are not used for this method", so passing the session's own owner
  should clear the scope gate and then be ignored.
  That is an inference from the tool descriptions rather than a measurement,
  so treat it as one call worth spending, not as a known route.

  - **Do:** resolve the threads in the GitHub UI, or from a session scoped to
    the new owner, once this failure appears.
  - **Do:** say in the status report that the findings are addressed and
    replied to but the fully-clean criterion cannot be met from this session,
    naming the tool.
  - **Don't:** re-test the call each polling round --- the scope list is fixed
    at session start and `add_repo` cannot widen it.
  - **Don't:** report the PR fully clean because every finding was addressed;
    unresolved threads fail that criterion whatever the reason.
- **`mergeable_state` glossary — `unstable` is NOT a merge conflict.** GitHub's
  `pull_request_read` `get` returns `mergeable_state` alongside `mergeable`;
  the common values: `clean` (mergeable, all checks passing), `unstable`
  (mergeable, but some check is pending/failing — not blocking), `dirty` (real
  merge conflicts — this is the one that needs `git merge origin/main` +
  conflict resolution), `blocked` (a required check hasn't passed),
  `behind` (branch protection requires an update first). Only `dirty` means
  conflicts; `unstable` just means "wait for CI" and needs no merge action.
  (ai-config#373: `mergeable_state: unstable` right after a push was CI still
  running, not a conflict signal.)
- **`gh pr merge` can return "Head branch is out of date" even after syncing; verify with SHAs before looping, and re-establish fully-clean before retrying.** When this error repeats, first read the PR's actual base branch (`gh pr view <N> --json baseRefName -q .baseRefName`) — do **not** assume `main`; stacked and release PRs target a different base — then fetch and merge that base into the branch. Merging the base creates a new head SHA, which invalidates the CI/review "fully clean" snapshot that authorized the original merge attempt (a repo that doesn't make every workflow/review a required branch-protection check can otherwise merge an unreviewed/untested new head) — re-run the `fully-clean.md` check against the new SHA before retrying the merge, not just the merge command itself. If it still fails, don't compare against `origin` blindly: for a cross-fork PR, `origin` is the *base* repo, not necessarily where the head branch lives, so `git ls-remote origin refs/heads/<branch>` can silently read a missing ref or an unrelated same-named branch in the base repo. Get the actual head repo and ref from the PR API first (`gh pr view <N> --json headRepositoryOwner,headRepository,headRefName`), query *that* repo's ref (`gh api repos/<head-owner>/<head-repo>/git/refs/heads/<head-ref> --jq .object.sha` — verified this endpoint works), and compare it against the PR API's own `.head.sha` (`gh api repos/<o>/<r>/pulls/<N> --jq .head.sha`); the PR object can lag the branch ref briefly, so **wait** until the two SHAs agree rather than retrying. If branch protection still blocks the merge, only use `gh pr merge --admin` when the user has **separately and explicitly** authorized the bypass itself — ordinary merge authorization does **not** cover it (see `preferences.md`) — otherwise stop and surface it as a blocker.
- Webhook PR-activity events cover comments/reviews/CI *failures* but NOT
  new pushes or merge-conflict transitions --- don't rely on events alone to
  know a PR merged; re-check explicitly.
  **CI success is now partly covered, contrary to what this bullet used to
  say in full: a `check_suite.completed` event is delivered when no
  third-party check suite on a head is still running or failed.**
  Measured 2026-09-01 in a Claude Code remote session on
  `UCD-SERG/serodynamics`, where nine arrived across six PRs.
  Its own body states the limits, and they matter:
  cancelled suites, suites with no runs, the GitHub App's own suites
  and legacy commit statuses are **not** covered.
  So it is a prompt to verify, not a green light --- a PR can carry a
  still-running `review / claude-review` (an App suite)
  while this event says CI is done.
  Read the check runs before calling anything clean.
- **A `check_suite.completed` event can name a superseded head, and its
  wording invites you to act on it anyway.**
  The event body says "If you were waiting on CI, continue with the next
  step", which reads as an all-clear for the PR rather than for one commit.
  Three of the nine measured above named a head that a later push had
  already replaced, written here as superseded-head -> replacement:
  on #311, `8c6c1be` -> `fb8c7ac`;
  on #298, `cb327d7` -> `65fd9fc`, and then `65fd9fc` -> `e76c564`.
  Each arrived one to five minutes after the superseding push,
  and every one was on a PR that had just been pushed to ---
  the old head's suite simply finishes after the new head exists.
  So the risk concentrates exactly where an iterating session lives,
  rather than being spread evenly across events.
  Read those counts as a lower bound on an ongoing pattern
  rather than a fixed tally:
  a fourth arrived later the same session on
  `Morrison-Lab/ai-config#2907` (`2450dd3` -> `30e83de`),
  by the same mechanism,
  which is what establishes that this is not repo-specific.
  This is the same staleness the failure-event bullet below describes,
  in the direction that is easier to act on wrongly:
  a stale *failure* costs a wasted investigation,
  while a stale *success* can license declaring a head green
  whose CI never ran.
  Compare `head_sha` against the PR's live `.head.sha`
  before treating any such event as progress.
  The earliest measurement of this shape predates this bullet and lives in
  [`fully-clean.cases.md`](../shared/workflow/fully-clean.cases.md),
  "A `check_suite.completed` wake at a superseded head"
  (`ucdavis/bcs#732`, 2026-08-23), which this bullet was written without
  having found; read the two together.
  This stays a memory rather than a hook despite clearing
  [`deterministic-tools`](../shared/principles/deterministic-tools.md)'s
  third-occurrence bar:
  deciding it needs a live API read of the PR's current head,
  which is not a condition a transcript-scanning hook can evaluate.
- **A CI-failure webhook event's `HeadSHA` can be stale — compare it against
  the PR's actual current head before investigating.** Pushing a fix-up commit
  right after a bad one (e.g. correcting an encoding mistake seconds later)
  produces a cascade of failure events for every check on the now-superseded
  commit, arriving over the next several minutes as each job finishes. Check
  the event's `HeadSHA` field against the PR's live head (`pull_request_read`
  `get`, `.head.sha`) — if it doesn't match, the event is about a commit no
  one will ever see the result of; skip it with a one-line "stale, superseded"
  note instead of re-diagnosing content you've already fixed. (Hit on
  UCD-SERG/serodynamics#193: an accidental double-base64-encoded push
  triggered ~10 failure events across the whole CI matrix, all for the
  immediately-superseded commit.)
- **Self-wake to re-check CI in remote/web sessions.** Webhooks don't deliver CI
  *success*, new pushes, or merge transitions, so re-check on a timer. Prefer
  `CronCreate` (a harness scheduling tool, not an MCP tool): schedule a one-shot
  (`recurring: false`) or recurring (`recurring: true`) job whose prompt re-polls
  `mcp__github__pull_request_read` (`get_check_runs`) and acts on the result; it
  fires at wall-clock time without holding a background process. (Used to watch
  both PRs' merge transitions while migrating rme's preview workflows to the gha
  reusable family.) Fallback when `CronCreate` isn't available: arm a one-shot
  `Monitor` with `sleep <N>; echo recheck` and re-poll when it fires — the
  `Monitor` can't reach the GitHub API itself (no `gh`; the only git remote is a
  git-only proxy), so it's purely a timer, and foreground Bash `sleep` is
  blocked, which is why the background `Monitor` is the workable one. There is no
  `send_later` tool. Re-arm until the build goes green. Learned driving rme#929.
- **`mcp__Claude_Code_Remote__send_later` can become unavailable mid-session,
  not just absent from the start** (contrast the rme case above, where it was
  never present). Observed failure sequence: first a few transient "Tool
  permission stream closed before response received" errors (retrying the
  identical call sometimes still worked), then a hard "Error: No such tool
  available: mcp__Claude_Code_Remote__send_later" that no retry cleared.
  Fallback to `CronCreate` with `recurring: false`, pinned to a specific
  near-future cron time (compute it with `date`, since `CronCreate` takes an
  absolute cron expression, not a relative "N minutes from now" delay).
  **`CronCreate` jobs are session-only** — they die with the session, unlike
  `send_later`'s durable server-side triggers — so this is a degraded
  substitute, not an equivalent; say so rather than treating it as a full
  replacement. (gha#193 PR-babysitting session, 2026-07-03.)
  **It is degraded in a sharper way than "dies with the session" suggests:**
  a `CronCreate` job can vanish from the store *before its fire time*, with
  no error and nothing to surface the loss.
  See the `CronCreate`-silent-loss entry in
  [`claude-code-scheduling.md`](claude-code-scheduling.md) for the
  observations and the `CronList` re-verification habit that catches it.
- **`add_repo` refuses a cross-owner add once the session already has a repo from a
  different owner** ("cross-tier adds are not supported in v1: requested `<owner>/<repo>`
  but session already has repos from owner(s) `[...]`") — it does NOT fall back to a
  read-only or degraded mode, so a session scoped to e.g. `Morrison-Lab/*` repos cannot add
  a `UCD-SERG/*` repo (or vice versa) no matter how the request is phrased. When a task
  needs to read a PR/issue in such an out-of-scope repo, don't stop at the `add_repo`
  failure or a raw `api.github.com` 403 (a plain `WebFetch` GET to
  `api.github.com/repos/.../issues/comments/<id>` for a public repo 403'd with no body —
  exact cause unconfirmed; `WebFetch` isn't threaded through the GitHub MCP session's own
  auth, so this isn't necessarily the same failure mode as a scoped/cross-owner API call,
  and GitHub's REST API does generally allow unauthenticated reads of public repos at a
  lower rate limit, so don't over-generalize from this one data point) — try `WebFetch`
  on the **rendered** `https://github.com/<owner>/<repo>/pull/<N>`
  (or `/issues/<N>`) page instead. For a public repo this reliably returns the PR/issue
  title, state, and recent comment/review content (works even for reading a *specific*
  comment by its anchor), succeeding where both the MCP tool and the JSON API failed.
  (Used to read UCD-SERG/serodynamics#193's `@claude`-bot comment from a
  `Morrison-Lab/gha`-scoped session, which surfaced the root cause fixed in gha#191.)
- **`add_repo` (and likely other approval-gated MCP tools) can fail repeatedly
  and silently under auto-mode, with no useful error.** In auto mode, a call
  that needs an interactive permission-dialog approval has no human present to
  click it, so it errors `Streamable HTTP error: Error POSTing to endpoint:
  MCP tool call requires approval` — identical on every retry, giving no
  signal that the real blocker is "no one is watching to approve this."
  Retrying the same call in auto mode doesn't help. The fix is to have the
  user switch to a non-auto permission mode (e.g. accept-edits) so there's
  someone to grant it, then retry once — it then either succeeds outright or
  fails with a real, actionable error (e.g. `add_repo`'s cross-tier-owner
  refusal, above). Don't burn more than one or two identical retries in auto
  mode before flagging this to the user. (gha#204 session, 2026-07-03: `rme`
  succeeded immediately after the user switched modes; `epi204`/`epi202` then
  failed with the real cross-tier error instead.)
- **The MCP write tools silently drop `<https://...>` angle-bracket autolinks
  from PR and issue bodies.** A body posted through `create_pull_request`,
  `update_pull_request`, or `issue_write` comes back with the whole
  `<...>` span gone, leaving a double space where the URL was --
  "pointed readers at&nbsp;&nbsp;for the in-development documentation."
  Presumably the angle brackets are treated as an HTML tag and stripped
  somewhere in the write path; whatever the mechanism, the URL never reaches
  GitHub. It is silent (the call succeeds) and easy to miss, because nothing
  in the tool result flags it and the sentence still reads as a sentence.
  Especially costly when the URL *is* the subject -- a PR about a broken link
  losing exactly that link.
  **Backticks do NOT protect it.** The sanitizer runs over the raw body
  string with no regard for Markdown context, so an angle-bracket span inside
  a code span is stripped exactly like a bare one, leaving an empty pair of
  backticks. This is the same formatting-blind-substring failure mode as the
  bot-mention gate in `memories/claude-bot-workflows.md` -- a pass that inspects
  raw text while the author reasons in rendered Markdown.
  **An empty backtick pair is the most visible damage, not the only damage, so
  do not use it as the tell.**
  Removing a span mid-sentence also re-balances
  whatever punctuation surrounded it: a following quotation mark becomes an
  opening one, so a quote silently re-opens and runs on through later prose.
  And a sentence contrasting a raw token against its escaped entity collapses
  into a tautology, because the surviving raw token is itself entity-escaped on
  the way in, leaving the two halves identical.
  Both leave grammatical, plausible-looking text with no empty backticks
  anywhere, which is why the re-read below has to be a **comparison against
  what you sent** rather than a proofread of what is stored.
  Note also that counting empty pairs naively over-reports: every fenced block
  contributes its own marker, so separate them before believing a count.
  (ai-config#1361, 2026-08-09: a PR body describing this very entry lost three
  bracketed placeholders from inside code spans and carried both second-order
  corruptions as well, while the tool reported success both times.
  A naive
  count of empty pairs returned 6, all of which were the three fenced blocks'
  own markers; the zero-genuine result came from a negative-lookaround match
  that excludes triple-backtick runs.)
  **Write the URL with no angle brackets at all**: a `[text](url)` link, or
  the bare `https://...` (GitHub auto-links it in a PR body anyway). Then
  re-read the stored body after posting when a URL matters -- the call
  succeeds either way, so the tool result never tells you.
  Note this is a quirk of the MCP write path, not of GitHub or of Markdown
  files: angle-bracket autolinks in a committed `README.md` render fine and
  should be left alone.
  (`UCD-SERG/serocalculator#605` and its issue #604, 2026-07-25: both bodies
  lost the same URL this way. The backticked-is-safe assumption was then
  disproved by this very bullet's own PR, `ai-config#724`, whose description
  lost an angle-bracket span from inside a code span in the heading that
  introduced this entry.)
- `Morrison-Lab/gha`'s `CLAUDE.md` carries its own `gh`->MCP substitution table
  (the "GitHub access in remote / web sessions" section), scoped to that repo.
  `Morrison-Lab/ai-config` has its own cross-model registry at
  [`tool-mappings.md`](../tool-mappings.md) (generated from `tool-mappings.yml`),
  which ai-config skills can point to directly — see `CLAUDE.md`'s "Skills that
  call gh/glab" section. When a skill or doc in a **different** repo (one with
  neither table) tells a reader to "use the GitHub MCP tools," name the tools by
  example (`mcp__github__add_issue_comment`, `mcp__github__create_pull_request`,
  `mcp__github__search_pull_requests`) rather than pointing at a `CLAUDE.md`
  mapping table that repo doesn't have — that cross-reference resolves only
  where the table actually lives. (Caught in ai-config#137 review: the gip
  skill referenced a table ai-config didn't have at the time; ai-config#327
  later added `tool-mappings.md` to close that gap.)
- **The raw REST API and the `mcp__github__*` tools can be gated
  independently, per ORG --- so a REST `403` is not evidence the repo is
  unreachable.**
  [`github-remote-sessions.md`](github-remote-sessions.md)'s
  "GitHub access from bash in remote/web sessions"
  section is right that REST from bash can be scope-limited rather than
  absent, and it used to add that switching to the MCP tools "does not get
  around a `403`" because they share one repo list.
  That held in the session that wrote it and does not hold generally.
  Measured 2026-08-16, three calls in one command from one session:

  | call | result |
  | --- | --- |
  | `GET /repos/Lacaedemon/sparta/pulls/1303` | `200` |
  | `GET /repos/Morrison-Lab/ai-config/pulls/1538` | `403` |
  | `GET /user` | `200`, `login: dem-extra1` |

  The MCP tools reached `Morrison-Lab/ai-config` throughout the same minutes
  --- reading its checks, its review threads, and merging a PR there --- so
  the two surfaces genuinely disagreed about one org rather than one being
  stale.

  **Read the `403` body, because the two denials have different remedies and
  only one of them is `add_repo`.**
  The per-repo denial that section documents says "Use add_repo to request
  access".
  This one says "GitHub access is not enabled for this session.
  An org admin must connect the Claude GitHub App for this organization",
  which is an org-level app connection --- nothing a session can grant
  itself, and nothing `add_repo` addresses.
  So a session can hold full MCP access to an org whose REST path is closed,
  which is exactly the shape that makes "the API is unreachable" the wrong
  conclusion to draw from a single `curl`.

  The practical consequence is which client to build a workflow on.
  Anything that must edit a PR body from the raw API --- the marker-preserving
  PATCH that `Lacaedemon/sparta`'s own memory prescribes, since the MCP read
  strips HTML comments --- works only where REST is open for that org, and
  has to be re-checked per org rather than per session.

  Note also that `GET /user` answered `dem-extra1` here, where sparta's entry
  records `the repository owner` for that same raw-API read.
  Read that against the table carefully: the table's rows are WRITES, so its
  raw-API row is `claude[bot]`, and the `the repository owner` figure for a raw-API read
  lives in that entry's prose instead --- which is the disagreement it cites
  as its reason for ruling `GET /user` out as an identity signal at all.
  That is the entry behaving as its own caveat says: the measurements are
  per-session, so re-measure rather than carrying one across.

  - **Do:** try the MCP tool after a raw-REST `403`, and read the `403` body
    before deciding what the denial is.
  - **Do:** treat "which client can reach this org" as a per-org question you
    measure, not a session-wide property.
  - **Don't:** read a REST `403` as the repo being out of scope; the MCP
    tools may have it, and `add_repo` may be the wrong remedy entirely.
  - **Don't:** commit a workflow to the raw-API path for an org without
    checking that path answers for that org first.
- **A per-client identity table is a CONTAINER measurement, so its rows do not
  travel --- and the row that disagrees is the WRITE row, which is the one the
  table itself says to trust.**
  `Lacaedemon/sparta`'s `.claude/memories/sparta.md` carries an identity table
  under "A session writes under TWO identities here", mapping each client to
  the login its writes are attributed to: MCP tools to `the repository owner`, the raw
  API to `claude[bot]`, and the `gh` CLI to `dem-extra1`.
  Its framing is already careful --- "the client makes the identity, not the
  session", and do not generalize a row to a client you did not measure.
  What it lacks is a second data point showing which axis actually varies.

  The entry above notes that `GET /user` answered `dem-extra1` rather than the
  table's raw-API row, and correctly declines to make much of it, because that
  same sparta entry rules a `GET /user` probe out as an identity signal.
  The measurement below is not rulable out on those grounds, because it is
  exactly the signal that entry names as the reliable one: **the attributed
  author of a write you actually made.**

  Measured 2026-08-16, in this container:

  | write | client | `user.login` |
  | --- | --- | --- |
  | `Morrison-Lab/ai-config#1539` opened | `mcp__github__create_pull_request` | `dem-extra1` |

  The table predicts `the repository owner` for that client and got `dem-extra1`, on the
  one surface the sparta entry names as reliable.
  So the varying axis is the **container**, not only the client, and a row
  read out of that table is a measurement with an expiry rather than a lookup.

  **The practical cost is a skipped reviewer request, which is why this is
  worth more than a footnote.**
  That same sparta entry records, correctly for its own container, that
  requesting `the repository owner` on a `the repository owner`-authored PR returns `422`, since
  GitHub rejects a review request naming the PR's own author --- and tells you
  not to spend a round diagnosing it.
  Carried into a container where MCP writes as `dem-extra1`, that reads as
  "the reviewer request will be rejected", and the natural response is to skip
  it.
  Measured instead, on `Lacaedemon/sparta#1303` (author `dem-extra1`):
  `POST .../pulls/1303/requested_reviewers` with `the repository owner` returned **201**.
  The `422` is a fact about the author-equals-reviewer collision, not about the
  client --- so it fires only when the container's own MCP identity happens to
  be the reviewer you are requesting.

  - **Do:** re-derive the identity by reading `user.login` on a write you just
    made, per that entry's own rule, rather than reading its table.
  - **Do:** attempt the reviewer request and read the status; a `201` and a
    `422` are one call apart and the wrong guess costs a review.
  - **Don't:** carry an identity row from another repo's memory, or from
    another container, into a claim about this one.
  - **Don't:** read the `422` as a property of the MCP client --- it is the
    author-equals-reviewer collision, and it does not arise when the two
    logins differ.

- **The REST-backed reads can 404 while the GraphQL-backed ones succeed in the
  same container, against the same PR --- so a review verdict can be
  unreachable by every API route the session has and still arrive by webhook.**
  Measured 2026-08-17 against `Morrison-Lab/ai-config#1580`, all in one
  session, minutes apart:

  | call | backing | result |
  | --- | --- | --- |
  | `pull_request_read` `get_comments` | REST | **404** |
  | `pull_request_read` `get_reviews` | REST | **404** |
  | `issue_read` `get_comments` | REST | **404** |
  | `pull_request_read` `get_review_comments` | GraphQL | 200, `totalCount: 0` |
  | `pull_request_read` `get` | --- | 200 |
  | `pull_request_read` `get_check_runs` | --- | 200, 8 runs |
  | `get_job_logs` | --- | 200 |
  | raw `curl` to `api.github.com/.../issues/1580/comments` | REST | **403** |

  The 403 is the org-policy denial this file records elsewhere --- `GitHub
  access is not enabled for this session. An org admin must connect the Claude
  GitHub App for this organization.` --- so it is a policy refusal rather than a
  transient error, and retrying it is wasted.

  **Run the negative control before diagnosing the PR.**
  The first 404 reads as a fact about `#1580`: a permissions oddity, a
  transferred issue, a deleted comment.
  Repeating the identical call against a **different** PR is what converts it
  into a fact about the *route* --- `issue_read` `get_comments` on `#1578`
  returned the same 404, which is the reading that stopped the investigation
  going one PR deeper.
  This is
  [`algorithmatize-checks`](../shared/workflow/algorithmatize-checks.md)'s
  "A negative control must enter at the real input" rule with the polarity
  reversed: there a control establishes that a detector can report a finding,
  and here it establishes that a failure is not about the subject.

  **The consequence is a routing fact rather than a blocker.**
  `subscribe_pr_activity`'s webhook stream carried the full
  `**Claude finished review**` body, including the `### Verdict`, while no
  available read route would return it --- so on a PR you are subscribed to,
  the wake envelope is a first-class surface for the verdict, not merely a
  notification that one exists.
  `CLAUDE.md`'s standing instruction to subscribe to every PR you open is what
  made that surface available; a session that had skipped it would have had no
  route at all.

  - **Do:** re-run a 404-ing read against a second PR before concluding
    anything about the first.
  - **Do:** read the verdict out of the subscription wake when the comment
    routes refuse, rather than treating the PR as unreadable.
  - **Don't:** read a REST-route 404 as covering the GraphQL-backed reads ---
    `get_review_comments`, `get`, and `get_check_runs` answered normally in the
    same minute.
  - **Don't:** retry the raw-API 403; it names an org-admin action, so nothing
    this session does changes it.

- **`get_job_logs`' `tail_lines` defaults to 500, and both directions off that
  default fail differently.**
  Passing `tail_lines: 200` under-fetches --- *below* the tool's own default,
  which is the tell that the number was chosen rather than derived --- and on a
  `claude-review` job the trailing 200 lines are workflow plumbing, so the
  verdict text is not in them.
  Correcting to `tail_lines: 3000` then exceeded the response token limit
  outright: 171,956 characters, rejected and spilled to a scratch file whose
  single-line-per-record shape defeats `Read`'s `offset`/`limit` chunking, so
  recovering it needs character-range slicing rather than a re-read.

  So the two failures bracket a window rather than pointing the same way, and
  neither announces which side you are on.
  Read the default as the starting point and widen once, and treat a
  size-limit rejection as a prompt to find a different surface rather than to
  keep halving --- here the webhook above delivered the same content in full.

- **`pull_request_read` `get_files` is a fourth REST-backed route that 404s,
  and local git is the working fallback rather than another API call.**
  The REST-versus-GraphQL table above lists `get_comments`, `get_reviews`, and
  `issue_read` `get_comments`.
  `get_files` behaves identically: 404 for all four PRs tried (#1566, #1576,
  #1580, #1581) in the same container where the GraphQL-backed reads succeeded
  minutes earlier.
  Keep a number out of that list unless it is a PR --- `get_files` against an
  issue number 404s whatever the route does, so it cannot witness a route
  defect.

  That matters most for the merge-order check `CLAUDE.md` requires before
  asserting two PRs are disjoint, since deriving a PR's file set is exactly
  what `get_files` exists for.
  `scripts/pr-sweep.py` cannot stand in here either --- it shells out to `gh`,
  which is absent from this environment --- so derive the sets from sweep refs
  instead:

  ```bash
  git fetch origin "+refs/pull/*/head:refs/sweep/pr/*" -q
  git diff --name-only "$(git merge-base origin/main refs/sweep/pr/$PR)" refs/sweep/pr/$PR
  ```

  - **Do:** fall back to local sweep refs for a file set, and say in the PR
    body that the API route was unavailable.
  - **Don't:** read a `get_files` 404 as a fact about the PR; it is the same
    route defect the three reads above show.

- **A 503 is transient and worth retrying, unlike the 404 and the 403 ---
  three distinct failure classes that a single "the API is broken" reading
  conflates.**
  `503 No server is currently available to service your request` arrived twice
  in a row on `issue_read` `get` for #1547 and succeeded on the third attempt,
  and once on `merge_pull_request` for #1581, succeeding on an immediate
  identical retry.
  So it fires on reads and on writes alike, and a merge that 503s has not
  necessarily failed to merge --- re-read the PR's `merged` field before
  assuming either outcome.

  The other two are not retryable at all.
  A 404 on the REST-backed routes above is a route defect, so every retry
  returns it.
  The raw-REST 403 names an org-admin action, so nothing this session does
  changes it.

  - **Do:** retry a 503 immediately, and verify the resulting state rather
    than the call's status when the call was a write.
  - **Don't:** retry a 404 or a 403 --- one is a broken route and the other is
    a policy denial.

- **Two shapes to expect when reading workflow runs through the MCP tools.**
  `actions_list` `list_workflow_runs` exceeds the response token limit even at
  `per_page: 3` --- measured at 111,922 characters --- and spills to a scratch
  file whose single-line payload defeats `Read`'s `offset`/`limit`, so it needs
  character-range slicing to recover.
  And a `queued` run object carries no `conclusion` key at all, absent rather
  than null, so iterating runs needs `r.get('conclusion', '-')` rather than
  `r['conclusion']`.

  - **Do:** reach for `get_check_runs` on a specific head before listing runs,
    and use `.get()` on any field a non-terminal run may not carry.
  - **Don't:** lower `per_page` in the hope of fitting the response; three was
    already 111,922 characters.

- **The `tail_lines` window is narrower than the defaults-to-500 bullet above
  implies, and it excludes that default itself.**
  Measured against two `claude-review` jobs: `120` returns workflow plumbing
  only, while `300` returns 54,182 characters, `600` returns 77,823, and
  `3000` returns 171,956 --- each of the last three rejected by the response
  token limit.

  So the usable band sits somewhere between 120 and 300 for a log of that
  size, which puts the default of 500 outside it.
  That last step is a deduction rather than a measurement, and a safe one:
  `tail_lines` returns the last N lines, so a larger N yields a superset and
  cannot come back smaller than 300's 54,182 characters.
  A band that narrow is not worth aiming at either, since its upper edge moves
  with a log length you do not know before fetching.

  - **Do:** read a verdict from the webhook stream or a posted review comment,
    and keep `get_job_logs` for one step's error text once you know which step
    failed.
  - **Don't:** tune `tail_lines` toward the default hoping the response will
    fit --- 300 already overflows, so 500 cannot.
