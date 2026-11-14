# Merging from a cloud session: gate mechanics

Measured in claude.ai cloud threads of the Machine Learning course project, 2026-10-10 to 2026-10-16.
The general merge policy is in [`skills/mwc/SKILL.md`](../skills/mwc/SKILL.md) and [`fully-clean`](../shared/workflow/fully-clean.md);
this file holds the cloud-specific quirks that stalled merges.

## Grants

- A merge grant covers the PRs it names.
  "mwc 548" or "merge macros 122 when ready" covers that PR once it passes `check-pr-fully-clean.py`.
  A bare "mwc" means "mwc all", the PRs in that thread at that time (Ezra, 2026-10-16;
  [`skills/mwc/SKILL.md`](../skills/mwc/SKILL.md)).
- "daytb" means go with the recommendation on an open question, and a decision-card tap answers only that card.
  Neither is a merge grant.
- A PR that goes clean with no named grant gets a reply asking for "mwc N".
- `ai-config`, `macros` and `gha` carry a standing mwc (Ezra, 2026-10-16: "standing mwc on macro stands", "also on ai-config and gha").
  It covers PRs in those repos only, not a downstream `latex-macros` pin bump in another repo.
- The merge hook's own list (`STANDING_MERGE_GRANT_REPOS`) names only `ai-config` and the macros repo, so a `gha` merge still needs `enable-mwc`;
  [ai-config#3490](https://github.com/Morrison-Lab/ai-config/issues/3490) describes the mismatch and is closed, although the mismatch persists (checked 2026-10-16).
  Infra-only PRs in any Morrison-Lab repo have a separate standing grant, described in `skills/mwc/SKILL.md`.
- In a Hearth project thread of the Machine Learning course project, the project rule is stricter: a merge needs Ezra's own word, typed in the owning thread, for PRs that existed when he typed it.
  A thread does not invoke the standing grants above there, and does not relay them.
  Slip, 2026-10-22: a thread squash-merged [gha#1169](https://github.com/Morrison-Lab/gha/pull/1169) under `gha`'s `CLAUDE.md` standing rule, without Ezra's typed word.
  Nothing was lost (CI green, Claude review clean), but the project rule was broken.
  **Do:** when a PR in such a thread is ready, report it to the coordinator and wait for Ezra's word.
  **Don't:** read a repo's standing grant as covering a Hearth thread, or merge before `check-pr-fully-clean.py` has run.
  The scorer cannot run in these sessions (it calls `gh pr view`, which needs GraphQL, blocked here), so verify readiness by REST and say so.
- The merge words are unchanged while the cross-harness reviewer is out;
  only the review changes (see "Cross-harness review" below).

## The merge hook marker

`no-unauthorized-merge.py` blocks `mcp__github__merge_pull_request` until `ai-session.sh enable-mwc` has run, even after Ezra's prose "mwc".
The marker lives in the repository's git common directory, so it is per repo checkout.

- **Do:** run `cd /home/user/<repo>` in its own Bash call, then `ai-session.sh enable-mwc --id <transcript uuid>` and `check-mwc --id <same id>`.
  The id is the file stem under `~/.claude/projects/<dir>/<uuid>.jsonl`.
  The claude.ai `session_...` id did not satisfy the hook (2026-10-14, lds#819).
- **Do:** repeat the enable in each repo you merge into, since a grant active in one checkout reads "no grant recorded" in another (2026-10-16, macros#164).
- **Do:** run `heartbeat --id <uuid>` from the same checkout right before each merge;
  the marker goes stale after 1800 s, so a long queue needs it repeatedly.
- **Do:** pass the full 40-character `expectedHeadSha`.
  The gate prints only 8; read the rest from the payload JSON (`headRefOid`).
- **Don't:** pin the head with the MCP tool's `sha` parameter instead.
  The hook reads only `expectedHeadSha`, so a call carrying the full SHA in `sha` was still refused (ai-config#5636, 2026-11-14).
- **Do:** locate the script with `ls -d ~/.claude/plugins/cache/Morrison-Lab/ai-config/*/skills/session-lock/scripts/ai-session.sh`.
  `build-pr-payload.py` and `check-pr-fully-clean.py` are under `scripts/` in the same plugin directory.
- **Do:** pass `--id <transcript uuid>` to `enable-mwc` itself, and not only to `check-mwc`.
  Without it, `check-mwc` still reported "active" while the merge hook said no grant was recorded, and two merge calls were refused (mds#650, 2026-11-05).
- **Do:** print the checker's result line into the transcript (`... | tail -3`) in the Bash call just before the merge call, with the checker named by its literal path.
  The hook answers "needs a check-pr-fully-clean.py pass" when the line is only in a file or an earlier turn.
- **Don't:** retry a refused merge as `ALLOW_MERGE=1 gh pr merge`.
  The auto-mode classifier denied that shape (mds#650, 2026-11-05).
  Fix the marker instead.
- **Don't:** run the marker commands from `/home/user/ai-config` or `/home/claude` for a merge in another repo.
  A merge from the wrong cwd was denied as "MECHANISTIC PROHIBITION" despite an active grant (2026-10-15).
- **Don't:** tell the user a hook blocks a granted merge before running the documented `enable-mwc` step (2026-10-10, lds#557 and psw#163).

If the auto-mode classifier denies `register`/`enable-mwc` right after a coordinator-relayed grant, stop.
Post the PR as ready and ask the coordinator for a fresh "mwc" from Ezra in the thread;
the identical command then ran and the merge went through (lds#1015, 2026-10-16).
Do not retry or work around a denial.

## The checker comes before the merge call

- The hook only warns afterwards; it does not gate.
  On ai-config#4538 (2026-10-15) a merge went through on hand-read verdicts without `check-pr-fully-clean.py`, which is a procedural miss even though a later run found the PR clean.
- In a cloud session GraphQL is blocked, so the bare checker exits 1 with a traceback and no finding bullets.
  That is a data failure, not a verdict.
  Run `python3 scripts/build-pr-payload.py OWNER/REPO N OUT.json`, then `python3 scripts/check-pr-fully-clean.py -R OWNER/REPO --from-json OUT.json N`, and read the exit status unpiped (0 clean, 1 not clean, other is a data problem).
  Build the payload only after the `build` job finishes, since an in-progress build is itself a failure.
- Re-run it on the current head after any push or branch update.
  A `check_run.completed` failure wake carries `head_sha`;
  compare it with the PR's head, since failures on older heads were already fixed.
- Without the checker, report a REST check-run count (`commits/<sha>/check-runs?per_page=100 --paginate`) and say the checker could not run.
  Do not write "ready for merge" (lds#640, 2026-10-12; the Stop hook flags it).
- A gate that looks wrong is fixed, or its input corrected, never merged over (project coordinator session, 2026-10-16, gha#1073;
  the same rule is in [`claude-app-projects`](claude-app-projects.md)).
  Report the failing lines to the coordinator, wait for the corrected input, rebuild the payload, rerun, and merge only on a pass.
- The checker fails a PR when main gained commits touching `.github/workflows/` since the merge base (ai-config#2982).
  In a batch of workflow PRs (pds#177 to #184, 2026-10-16) each merge forced every remaining PR to merge main, re-review and rebuild the preview, about 10 minutes per round.
  Push the nit fixes and the main merge together, then merge the batch back to back.
- After one squash merge every other open PR is behind main, so merge serially: update branch pinned to head, `/review`, gate, base-currency check, merge (about 10 minutes per PR with a render).
- Other people also merge into the repo while a gate runs (macros, 2026-10-15), and unresolved review threads refuse the merge, so resolve answered threads first.

## Cross-harness review

- Rule from the project's coordinator session (2026-10-15, after pds#170 merged on "mwc 170" with Argon still queued): wait for the cross-harness verdict on the current head even after Ezra says mwc.
  The gate needs a reviewer whose model and harness both differ from the author's;
  Claude's CI review does not count, unless the dated exception below applies.
  An mwc removes the asking, not the gate.
- Carry-over of an Argon CLEAN applies only to a fix matching Argon's own suggestion.
  A nit from the Claude CI reviewer needs a new Argon pass on the new head, so batch such nits into the push that answers Argon.
  Moving the head by a main merge needs the coordinator to confirm the CLEAN carries over;
  a non-overlapping main commit need not move the head.
- Argon quota failure looks like review output: a comment headed "FINDINGS" holding only `RESOURCE_EXHAUSTED (code 429) ... Resets in 2h0m28s` and an empty `VERDICT:` (lds#1027, 2026-10-15).
  Read the reset time, ask the coordinator to re-queue after it, and merge nothing on it.
  The CI review's own 429 skip behaviour is in [`claude-review-dispatch`](claude-review-dispatch.md).
- The checker admits a comment as a counted reviewer only through a first or last line marker in `REVIEW_AGENT_MARKERS`.
  A clean read posted by `dem-extra1` with no marker never counts toward `--quorum` (lds#938, 2026-10-16), and the "_Posted by Claude Code (AI agent)_" footer is excluded on purpose.
  The XPS router therefore posts Argon reads with the Antigravity agent header as the first line.
  Keep `--quorum 2` whenever a cross-harness reviewer is available.
  The Claude-only exception below uses quorum 1 and applies only while no cross-harness reviewer is reachable.
- Dated exception to `skills/mwc/SKILL.md`, which says a Claude subagent and the CI review do not satisfy the cross-harness requirement.
  It ends when a cross-harness reviewer (Argon, agy, codex, opencode) is reachable again, and the skill's rule then applies in full.
  Ezra's cards of 2026-10-16 05:01 UTC (the coordinator made it project-wide at 05:11) and 07:31 UTC ("Claude-only") override the skill until then.
  An independent adversarial Claude subagent, separate from the author and the CI reviewer, stands in for the cross-harness review.
  Run a general-purpose subagent on the final head with the diff as a file and no `mcp__hearthbot__` tools.
  Post a comment with "### Verdict", "VERDICT: CLEAN", "Reviewed-Commit: <full sha>" and a line saying it is the stand-in per Ezra's decision.
  A PR with his mwc then merges on the Claude CI review plus that CLEAN subagent review on the current head, checked at `--quorum 1`.
  The hook's cross-harness warning is expected while the exception holds.
  Argon's quota was expected back about 2026-10-21, so reread this bullet after that date.
  Wording nits still block.
  The subagent keeps finding header-wording nits each round: shorten archive headers to claim nothing that can go stale (lds#1052).
- On macros the gate said "No valid clean review" until a `/review` comment dispatched the Claude CI review, so the stand-in comment alone did not satisfy it.
  Whichever quorum applies, post the stand-in verdict, then `/review`, then run the checker.

## `/review` must begin the comment

The Claude review dispatches only on a comment whose first text is `/review` (macros#151 and #162, 2026-10-15).
Put the explanation after it.
After pushing, confirm a "Claude Review Dispatched" comment names the new head SHA before waiting.

## A PR parked in a queue goes stale

- After merging main into a PR branch, run `git diff origin/main --stat` and reread each claim in the PR body against it.
  When main already carries part of the change, the body keeps claiming it, and reviewers compare the body to the diff against main (lds#1016, 2026-10-15).
  That PR waited hours for a slot, main then split the very div it edited, and it was closed as wrong.
- A PR waiting for a slot needs a fresh look at main's version of its file, not only a gate re-run.
- When a PR merges before its follow-up arrives, restart the branch from main and open a fresh PR;
  the merged one cannot be reused.

## Meeting the cross-harness review gate from a cloud session

Learned on [ai-config#5023](https://github.com/Morrison-Lab/ai-config/pull/5023) (2026-11-06).

- A cloud session has no `agy`, `gemini`, `cursor-agent` or `opencode` CLI.
  Probe OpenCode Go by curl first: a Python `urllib` request needs a `User-Agent` header, or Cloudflare returns 403 code 1010.
  On 2026-11-06 it returned `GoUsageLimitError` (monthly) for every model tried, so the gate was not waived.
  That quota state is dynamic and expires with the monthly limit (by 2026-12-06 at the latest): re-probe live and never waive from this note.
- Start a Remote Control session on the Mac (`start_remote_control`, read-only brief) to run `agy` on `gh pr diff N -R O/R`.
  Ask for it in parallel with the fully-clean checker, not after, because Ezra must approve the card.
- Run `check-pr-fully-clean.py` as its own Bash call, with no `&&` and no pipe.
  Pass `--annotations-read=all` after `-R` only once you have read every listed annotation and posted a comment beginning `Annotation dispositions for head <sha7>:`, which the checker requires (ai-config#4893).
  The merge hook does not credit a compound or piped run.
- `validate` runs twice on one head (pull_request and push events), and the checker blocks until both finish.

Added on 2026-11-11 ([ai-config#5359](https://github.com/Morrison-Lab/ai-config/issues/5359)), when the OpenCode Go route worked again:

- **Do:** run the OpenCode Go review on the shipping head before the merge call, and write a waiver only after every route failed in this session.
- **Do:** check each passage a diff-only reviewer quotes against the head, and run the failing command a finding claims, before you accept or rebut the finding.
  A reviewer that sees only the diff can quote code that is not in the file.
- **Do:** relay an outside review in your own words: say that it did not approve, list each finding, and address, rebut or defer each one on the PR before merging.
- **Don't:** copy a waiver from a note about an earlier outage.
  One was posted on [ai-config#5352](https://github.com/Morrison-Lab/ai-config/pull/5352) before any reviewer was tried.
- **Don't:** accept or rebut from the reviewer's quotation alone.
- **Don't:** paste the reviewer's verdict line into your relay comment.
  `scripts/check-pr-fully-clean.py` then records the relay comment itself as a not-clean verdict from its author (criterion 4 in its module docstring), and only a later clean verdict from that same author clears it.
  The findings still block the merge until each is answered.
  The wording only keeps the relay from becoming a second verdict.

Other notes from that day:

- The header that worked for the `urllib` probe named above was `User-Agent: curl/8.5.0`.
  A 403 with code 1010 is the gateway refusing the client, so it is not a failed route and does not count toward a waiver.
- An answer with reasoning and no text is no verdict ([`ci-quirks`](ci-quirks.md), "Cross-harness review tooling").
  `glm-5.3` returned that on three diffs in a row while `kimi-k3` answered, so list first the model that last answered.
- `scripts/summarize-pr-annotations.sh` did not finish in a cloud session: it printed an HTTP 403 line about 1,500 times in five minutes ([ai-config#5377](https://github.com/Morrison-Lab/ai-config/issues/5377)).
  Its header already pages by hand around one proxy 403 (gha#1432), and which call still gets the 403 was not read.
  Until that issue is fixed, read `repos/<owner>/<repo>/commits/<sha>/check-runs` and each `repos/<owner>/<repo>/check-runs/<id>/annotations` with `gh api`, which took under a minute.

## The merge hook needs literal ids in the checker command

- The merge hook reads the checker's result line from this transcript, and a run whose `--annotations-read` value is a shell variable (`"$IDS"`) did not satisfy it on mds#671 (2026-11-06).
  Paste the comma-separated ids into the command itself, copied whole from the id listing: a list with one id dropped (`127720012940`) ends with a not-clean line for the check run that carries it.
- A bare mwc covers the PRs open when Ezra sends it.
  A PR whose branch you update afterwards (sds#537, new head 9c75704) keeps that grant, but its re-review and checker run must be clean on the new head before the merge.
  That carry-over holds only for a PR an mwc line actually names, with content unchanged beyond a main merge.
  Never infer coverage for an unnamed PR from its unchanged content
  (the coordinator did so for lds#2176, 2026-11-10; ai-config#5275).
  Cite the line that names the PR in the merge command's report.

## A runner session's merge queue, 2026-11-09 to 2026-11-10

Learned over about 90 merges through `merge-infra-pr` and pinned `gh pr merge` in the Data 571 project.

- A merge grant must reach the runner session as the user's own wake.
  Ezra's mwc lines cited by the coordinator, or read back with `read_thread`, were denied "Merge Without Review" or "Auto-Mode Bypass" two to three times each.
  The identical command passed once his message arrived as a wake (psc "Sync site scaffolding" dispatch, pds#392, #406, #408).
  Try once after a cite, report the denial, and stop before a third attempt.
- `merge-infra-pr` accepts a PR only when every changed path matches `INFRA_PATH_PATTERNS` in `hooks/no-unauthorized-merge.py` or is under `changelog.d/`, or the repo is gha, macros, ai-config or teaching-tools (Ezra, 2026-11-10: "teaching-tools is infra").
  It reads that list from a fresh ai-config clone, so it covers agent configuration (`.claude/`, `CLAUDE.md`, `AGENTS.md`) in content repos too (Ezra, 2026-11-11: "the infra grant should cover agent-config files";
  it had refused lds#2291, ai-config#5293).
  A blanket `tools/` or `scripts/` is refused in any other repo;
  only checkers, tests and named preview/CI helpers under `tools/` pass.
  One `_quarto.yml` or `canvas/` file in a content repo makes the PR content, which needs a typed mwc (mlg#330).
  Canvas writes still need Ezra's explicit ok, whatever repo the PR is in,
  and `merge-infra-pr` refuses any PR that touches a `canvas/` path.
- Every merge that changes `.github/workflows/` makes the other open PRs of that repo stale by the checker's stale-base rule.
  Merge workflow PRs last, merge content PRs first when an mwc is waiting, and for caller pairs (mds#705/#706, mcs#122/#123, pds#415/#416, sds#574/#575) merge one and ask the owner to merge main into the second.
- `slide-major-tag.yml` fails if any check run on main's tip is cancelled (`r-cmd-check-tests` was, twice).
  Re-run that one job, then slide once at the end of a gha batch: every gha merge moves the tip.
- When agy has no quota, enumerate the other routes once (here `cursor-agent` needed a key, `opencode` and `gemini` were absent), post the waiver note on the PR, and owe the review after the reset.
- `gh api rate_limit` costs nothing.
  A gha PR needs about 800 calls for the annotation read and 100 to 300 for the checker.
  The 5,000 per hour budget therefore supports about four gha merges plus a few content checks, so pace by the reset time.
