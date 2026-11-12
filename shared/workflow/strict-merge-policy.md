# Strict Merge Control Policy

Merging a Pull Request or Merge Request is strictly controlled across all agents and harnesses.

## Rules

- **NEVER merge any Pull Request or Merge Request without explicit user permission.**
  Creating, opening, updating, or driving a PR to clean CI/review does NOT grant permission to merge it.
  Merging a PR is strictly forbidden unless the user explicitly grants session permission (e.g. via `/mwc` or `/maw`) or explicitly issues a merge instruction for that specific PR (e.g. `/merge-it` or "merge this PR").
- **Never merge over open review findings or treat a reviewer skip notice as approval.**
  Under `mwc`, a PR must be fully clean across CI and review (see [`fully-clean.md`](fully-clean.md)).
  A clean automated review from every available provider evaluating the current HEAD commit is strictly required for merging with `mwc`.
  A reviewer skip notice (e.g. for quota exhaustion or workflow edits) or a fallback self-review does NOT satisfy `mwc` or grant autonomous merge authority.
  All findings across the PR history must be Addressed, Rebutted, or Deferred before merge.
  A disagreement among reviews is not fully clean: any reviewer's standing not-clean --- nits included --- vetoes merge even with `mwc` active.
  ARD every item from every review, then request fresh reviews.
- **Never describe a PR as merge-ready without a clean review verdict on the latest commit.**
  GitHub's `mergeable` field is conflict existence (`MERGEABLE` / `CONFLICTING` / `UNKNOWN`).
  `mergeStateStatus: CLEAN` is conflict-free (GitHub `mergeable`) plus passing commit status, not a review verdict.
  Only `DIRTY` / `CONFLICTING` means conflicts.
  A PR whose latest commit has no authentic clean review is not merge-ready.
  Report it as blocked on review, not as merge-ready.
- **Revert premature or defective merges immediately.**
  If a PR is merged incorrectly, prematurely, or without clean external review approval,
  open a revert PR on `main` immediately and continue on the original PR branch per [`revert-premature-merge.md`](revert-premature-merge.md).
- **Another session's PR needs a second condition: clean on its current head for more than twenty minutes, then warned.**
  A peer may have further commits planned, so merging one that just went clean can destroy work it was about to push.
  Start the clock at the clean verdict on the current head, which a push resets, not at the PR's `updatedAt`, which any comment bumps.
  Message the owning session when `ListAgents` reaches it;
  otherwise comment that you intend to merge and wait five more minutes for a hold-off.
  It applies only to a peer PR that passes `memories/reviewing-prs.md`'s scope test (a peer session under your own login satisfies the author arm);
  another lab member's PR that fails the test gets neither the comment nor the merge.
  Derivation and cases: [`mwc`](../../skills/mwc/SKILL.md)'s "Another session's PR" section ([ai-config#2460](https://github.com/Morrison-Lab/ai-config/issues/2460)).
- **When you revert a merge, reopen its issue.**
  GitHub does not automatically reopen the issue a reverted PR closed;
  explicitly and immediately reopen the corresponding issue(s) (`gh issue reopen <issue-number>`) per [`revert-merge.md`](revert-merge.md).

## Waiver of the cross-model review

When no non-Claude model and harness can run (the network policy blocks the host, the backend is down, the CLI or credential is absent after enumerating every route), try each route once, then waive the cross-model review.
The waiver grants no merge authority: the merge still needs `mwc` or an explicit instruction, a clean Claude review plus green CI, and a PR note that the review was waived, which reviewer was attempted, and the error.
A reviewer that ran and returned not-clean is not unavailable and still vetoes the merge.
The waiver removes only the cross-model requirement;
authorization, [`fully-clean`](fully-clean.md), and the clean-on-head rules still bind.
Full procedure: [`adversarial-self-review`](adversarial-self-review.md#waiver-when-no-cross-model-reviewer-can-run) (Ezra, 2026-10-16).

## Infrastructure PRs standing `mwc` grant

Infrastructure PRs carry a standing `mwc` grant in every repo the user can push to.
A PR whose diff is only infrastructure --- CI workflows, tooling and scripts, configuration, and recorded instructions and notes for AI and human developers (`CLAUDE.md`, `AGENTS.md`, `.github/`, `.claude/`, memories, skills, contributor docs, checker scripts and their tests under `tools/`) --- may be merged without asking once it is fully clean.
The exact path list the merge guard accepts is `INFRA_PATH_PATTERNS` in `hooks/no-unauthorized-merge.py`.
`scripts/merge-infra-pr` reads that same list from a fresh ai-config clone, so the wrapper and the hook cannot drift apart (ai-config#5293).
Agent configuration is infra in every repo, content repos included (Ezra, 2026-11-11: "the infra grant should cover agent-config files").
Of the rest of `tools/`, only preview and CI helpers named in the list count: each one changes only what a PR preview or a CI run does, never what the published site shows, such as `tools/skip-pdf-in-previews.py` (Ezra, 2026-11-11, of lds#2319: "the infra grant should cover this").
Figure, data and content generators stay out, and so do build steps that shape the published site, such as `build_math_macros.py`.
Every other rule in this section still binds, including the clean automated review on the current head,
so a quota-skipped review still holds the merge.
The test is effect rather than file type: infrastructure is whatever does not directly change the repo's consumer's experience.
Every PR in `Morrison-Lab/gha`, `Morrison-Lab/ai-config` or the macros repo (`d-morrison/macros` or `Morrison-Lab/macros`) counts as infrastructure, as all three are infrastructure repos.
The grant is scoped to the merge's **target** repo, which `hooks/no-unauthorized-merge.py` reads off the command, so a merge run from an ai-config checkout into another repo is unaffected.
Where `hooks/no-unauthorized-merge.py` is active, clear it with `ALLOW_MERGE=1` on that one merge command, and state in the reply why the PR qualified.
Do not enable session-wide `/mwc` for it.

- **Classify before asking.**
  Before telling the user a PR waits on `mwc`, list its changed paths.
  If every path matches `INFRA_PATH_PATTERNS` in `hooks/no-unauthorized-merge.py` (`.github/`, `.claude/`, `CLAUDE.md`/`AGENTS.md`, lint, spell and link-check configuration) or the repo is gha, macros or ai-config, report it as merging under the infra grant, not as waiting on the user (Ezra, 2026-11-07, about lds#2009: "it's infra and shouldn't need my word").
  `hooks/no-mwc-ask-for-infra-pr.py` denies a reply that asks otherwise (ai-config#5097).
- **Do:** merge a fully clean infrastructure PR without asking, and say in the same reply that you did and why it qualified.
  In a project, an owner thread never merges: it sends the PR's final head to the coordinator, and the runner thread merges once the fully-clean checker exits 0 (ai-config#5111).
- **Don't:** extend the grant to a PR that mixes infrastructure with content, or merge one whose review was skipped.

See [`AGENTS.cases.md`](../../AGENTS.cases.md), "Strict Merge Control Policy" for the authentic user directives.
