# Case records: pr-on-claim

Worked-example case records for the rules in
[`pr-on-claim.md`](pr-on-claim.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## Run the reviewer POST as the sole (or last) command

(Morrison-Lab/rpt#181, 2026-08-03: the POST was chained ahead of `gh pr view`/`gh pr checks` in one call across six turns, so the hook re-fired every Stop;
running the POST bare discharged it.
The failure was misread as the hook not recognizing a Copilot quota refusal, which it was not about.)

## "Nothing chained after it" includes a formatting pipe

(Morrison-Lab/ai-config#1139, 2026-08-04: the pipe variant, in a session that had already cited this rule's reasoning aloud earlier in the same hour.
The request was written `gh api -X POST .../requested_reviewers -f 'reviewers[]=...' 2>&1 | tail -3`, and it genuinely succeeded --- the response named `Copilot` in `requested_reviewers`, and Copilot posted its quota refusal at `07:22:15Z`.
The hook still fired at Stop, correctly, because `tail` owned the exit status.
Re-running the POST bare discharged it and produced a second, identical refusal at `07:53:03Z`.)

## The blocked-request test's false positive on auto-requesting repos

(Morrison-Lab/ai-config#1077, 2026-08-03: two explicit requests each returned `["Copilot"]` and each left `reviewRequests` empty within a minute, and both were reported as a possible blocked/silent reviewer.
The repo's `main` ruleset carries `copilot_code_review` with `review_on_push: true` and `review_draft_pull_requests: false`, so neither request was ever needed.
Copilot separately did stay silent on that PR, which is the distinct third state [`review-verdict-pitfalls`](review-verdict-pitfalls.md) records --- the point here is that the empty pending-list was not the evidence for it.)

## Request the reviewer in the same step; don't leave it "review owed"

(Morrison-Lab/ai-config #1038 and #1040, 2026-08-02: both PRs were opened around 07:00Z and then reported as still owing review requests.
They had zero Copilot reviews until the user asked why no review had been requested about ten minutes later.
The repo's `claude-review` workflow was failing for the same context-closure limit that made #1029's review fail on every attempt, so a PR without the explicit Copilot request had no working reviewer despite review-shaped checks.)

## Verify you switched branches before the second issue's code

(ucdavis/bcs `gia` session, 2026-07-06: SLURM-hardening changes for issue #286
were written while still on issue #281's `chore/renv-explicit-snapshot`
branch --- caught before pushing, but only by re-checking `git status`/`git
diff --stat` against expectations, not because anything failed.)
