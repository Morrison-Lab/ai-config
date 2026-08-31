---
name: ard
description: "Address, rebut, or defer review items."
user-invocable: true
allowed-tools:
  - Bash
  - Agent
  - Read
  - Edit
  - Write
---

# ARD — Address, Rebut, Defer, or Acknowledge

Every review comment gets exactly one disposition: **A**, **R**, **D**, or **K**. Ignoring is not an option.

## What counts as a finding

A *finding* is anything the reviewer requests or implies a change to — including items tagged "nit", "minor", "non-blocker", "optional", or "consider". All of these require **Address**, **Rebut**, or **Defer**.

Pure praise or neutral observations with **no** requested change ("nice refactor", "TIL") still get a row — disposition **Acknowledge** — so the summary accounts for *every* comment the reviewer made and nothing reads as silently dropped.

## The four dispositions

| Code | Meaning | Action required |
|------|---------|-----------------|
| **A** — Address | Valid and in-scope. | Fix it in this PR/MR and commit. |
| **R** — Rebut | Incorrect, already handled, or a misunderstanding. | Explain *why*, citing concrete evidence (line, test, doc, spec). Specific enough that the reviewer can verify it without re-reading the whole PR. |
| **D** — Defer | Valid but out of scope (new feature, broad refactor, needs design discussion). | File a follow-up issue (`CREATE_ISSUE` on GitHub — `gh issue create`; `glab issue create` on GitLab), link it, and add it to the PR/MR's **Deferred / Out-of-Scope** section. |
| **K** — Acknowledge | Praise or a neutral observation with no change requested. | Give it a row so it's accounted for; no code change, no rebuttal needed. Don't stretch this to dodge a real finding. |

### Decision order

For anything that requests a change, choose among the first three (Acknowledge is only for no-ask comments):

1. **Address** — the default. Most findings are 1–5 line fixes; if it takes under ~2 min, just fix it.
2. **Rebut** — only when you're confident the reviewer is mistaken. A rebuttal that isn't falsifiable ("I think it's fine") is not a rebuttal. **Before applying *or* rebutting any factual claim about an API, deprecation, signature, or behavior, TEST it** — run the code both ways. Reviewers (including the `@claude` bot) state such claims confidently but are sometimes exactly backwards, and blindly "Addressing" a wrong one breaks the build. (Seen on rme #873 with igraph ≥ 2.x: the bot insisted `bfs(mode=)` was deprecated in favor of `neimode=`; the reverse is true — `neimode` is a hard `deprecate_stop` error, `mode` is current. Re-running the script revealed it instantly. The deprecation *direction* can differ across igraph major versions, so test on the locked version.)
   The same testing discipline applies when the claim is about the **PR's own state or metadata** rather than code behavior — which footer/URL convention a given post uses, whether a file matches `main`, whether a check still exists — not just runnable code. Fetch the actual PR data (the API call, not memory) before Addressing or Rebutting. (Seen on ai-config#688: a review claimed a memory bullet's cited attribution-footer text was wrong, reasoning from the PR's own body — but the PR *body* and a *reply comment* get their footer through two different code paths that don't match. Fetching both directly via the API before responding showed the bullet was right and the reviewer had compared the wrong artifact; rebutted with that evidence instead of either implementing the suggested fix or dismissing the finding unchecked.)
3. **Defer** — only when the fix genuinely expands scope. Never defer just because a fix is "minor" — minor fixes get Addressed.

**Recording a finding as a known limitation, to close it without changing anything, is a Rebut --- and it owes a Rebut's evidence.**
Writing the finding into a code comment closes it without fixing it, reads as rigour, and leaves nothing red.
The claim it rests on --- *no rule could decide this* --- is one nobody asks you to support, unlike the claims in a posted rebuttal.
Before recording a limitation, name the mechanism that makes the input undecidable, and check it against the format's own generator rather than against how the input looks.
If the generator cannot emit the shape you are excusing, it is decidable and the disposition is Address.

- **Do:** cite the generator's own behaviour when you claim an input is ambiguous, the way any other Rebut cites a line or a spec.
- **Don't:** let a comment describing a limitation stand in for a disposition --- it is a Rebut written where the reviewer cannot see it.

(Measured on d-morrison/altdoc#125, 2026-08-28.
A parser input was documented as one of several inherent ambiguities.
roxygen2 joins its file list with `", "` and wraps at spaces, so the shape being excused --- a continuation line beginning with a comma --- is one that format cannot produce.
One added predicate rejected it.
The claim had survived several review rounds inside a comment that read as careful.)

> **"You deleted/removed X" findings — check for branch-behind-main first.** When
> a reviewer says the PR removed something you don't recall touching, run
> `git log HEAD..origin/main` and `git show HEAD:<file>` before Addressing. Main
> may have *added* X after you branched, so X is absent only because the branch is
> stale — not because your diff deleted it. The fix is **merge `origin/main` in**
> (the standing keep-synced rule), not "restore" a line you never removed. Verify
> the actual committed diff (`git show <commit> -- <file>`) rather than trusting
> the finding's framing. (Seen on ai-config PR #52.)

> **"Blocking: missing X" findings that cite a CI job or policy — check the job
> still exists on `main` first.** A review can flag a CI failure (e.g. "the
> Require Changelog Entry job is failing, add a CHANGELOG.md entry") as
> blocking, but the requirement itself can be removed from `main` in the time
> between when the review ran and when you address it — a different PR deletes
> the CI job and/or the file it checks. This isn't the branch-behind-main case
> above (nothing was deleted from *this* PR); the requirement stopped existing
> project-wide. Before Addressing, check whether the cited job/file is still on
> `main` (`git log --oneline origin/main -- <path>`, or `git show origin/main:<path>`).
> If it's gone, Rebut with the removal commit(s) as evidence rather than
> resurrecting a dead requirement. (Seen on ai-config PR #376: a "blocking"
> CHANGELOG.md finding referenced `require-changelog.yml`, which had been
> deleted from `main` in #385/#387 by the time the fix round ran.)

## Procedure

### 1. Gather every finding

Collect the full set *before* dispositioning, so none slips through. Pull both the summary comment and the inline review threads — `READ_PR_COMMENTS` and `READ_PR_REVIEW_COMMENTS` (abstract operation tokens; resolve to your model's tool via [`tool-mappings.md`](../../tool-mappings.md)).

**GitHub**

```bash
gh pr view <N> --comments                            # READ_PR_COMMENTS — top-level + summary comments
gh api repos/{owner}/{repo}/pulls/<N>/comments       # READ_PR_REVIEW_COMMENTS — inline review-thread comments
```

**GitLab**

```bash
glab mr view <N> --comments                          # discussion notes
glab api --paginate "projects/:id/merge_requests/<N>/notes?per_page=100"  # authoritative unresolved DiffNote sweep
glab api "projects/:id/merge_requests/<N>/discussions"                    # thread identifiers for replies/resolution
```

Bots often post the same finding twice — once inline and once in the summary comment. Collect the **union and dedupe** before numbering, so one issue doesn't get two rows (or two conflicting dispositions). Then number 1..n; every number must end up with a row in the summary.

Filter the paginated notes response for `.resolvable == true and .resolved == false`;
GitLab can return unresolved `DiffNote`s there even when a discussion-level timestamp filter finds no recent unresolved thread.
The Discussions endpoint still owns the reply and resolution actions once the note has been identified.

A PR can also carry **more than one review surface from different reviewers**: an inline code-review bot, a separate *agent* post-step that posts its own top-level summary, and Copilot are each distinct. `gh pr view <N> --comments` returns every top-level comment, so disposition each reviewer's findings — not just the inline review or the most recent comment. A whole review summary left un-dispositioned reads as ignored even when every inline thread was handled.

### 2. Disposition each one

Apply the decision order above. For Address items, make the edits now.

### 3. Commit Addressed fixes (one commit per review round)

```bash
git add -p                                           # stage deliberately
git commit -m "fix: address round <k> review findings"   # COMMIT
git push                                                  # PUSH
```

- **One commit per round**, not one per finding — reference its SHA in every Address row.
- **Never `--amend`** the already-reviewed commits: the reviewer (and CI) ran against them and others may have pulled. A fresh commit keeps the audit trail.
- Don't push generated cruft (`.Rout`, build artifacts); respect the repo's `.gitignore`.
- If every finding is Rebut/Defer, there's nothing to commit — skip to step 4 and still post the summary.

### 4. Post one summary comment

Write the summary to a file and post it *from* the file — **never inline on GitLab**, because `glab` mis-parses backticks (e.g. commit SHAs in code spans) as shell subcommands:

```bash
# write the summary to ard-summary.md, then:
gh pr comment <N> --body-file ard-summary.md         # COMMENT_PR — GitHub
glab mr note <N> -F ard-summary.md                   # GitLab
```

**End `ard-summary.md` with the agent-disclosure marker**, on its own line after a blank line:

```
_Posted by Claude Code (AI agent) --- not written by a human._
```

This comment is posted under the account holder's own login on every round of every PR, so it is among the likeliest in the corpus to be mistaken for their own writing --- see [`disclose-agent-authorship`](../../shared/workflow/disclose-agent-authorship.md).
The body arrives via `--body-file`, which the disclosure guard cannot read.
It still warns --- but only that the body is unreadable, never that the marker is absent, and that weaker note reads as a formality rather than a finding.
So this step states the requirement itself.

**Keep the bot's trigger phrase out of the summary body.** The `issue_comment`
trigger fires on the bare bot `@`-mention **anywhere** in a comment — even in a
sentence saying you're *not* re-requesting a review. Refer to it obliquely
("re-request review", "the review-trigger mention") or split the tokens (e.g.
`@ claude`, with a space, so the raw body never contains the contiguous handle);
paste the literal `@`-mention only when you actually intend to dispatch a review. A
stray mention spawns a run that cancels the push-triggered review on
`cancel-in-progress` setups. On some mention-bot setups it also starts a
session whose residual-commit sweep can churn the branch.

Summary format:

```
Addressed findings from review of <commit-or-range>:

| # | Finding | Disposition | Detail |
|---|---------|-------------|--------|
| 1 | <summary> | ✅ Address | Fixed in <commit-sha> |
| 2 | <summary> | 🔄 Rebut | <one-line reason> |
| 3 | <summary> | 📌 Defer | <issue-link> |
| 4 | <summary> | 👍 Acknowledge | <one-line thanks / note> |

### Rebuttal: Finding 2
<full explanation with evidence>
```

Expand each Rebut below the table. Deferred rows must carry a real issue link.

**Backtick any verdict phrase you quote, including the one in the opening line.**
A disposition summary names the round it is disposing of, and the natural way to write that names the round's verdict too:

```
Addressed GitHub Claude of `9508454e` (Needs more work). Pushed `8af4edc9`.
```

`check-pr-fully-clean.py` reads that parenthetical as this comment's OWN verdict.
Because a driving session never posts a superseding clean one, the per-reviewer rule from #2274 then keeps the PR not-clean permanently, on a citation of a round that was already addressed.
Measured on ai-config#2341: that line alone froze the PR, while the disposition table and a self-imposed hold in the same comment produced no verdict at all.

The fix is one pair of backticks, because `strip_cited_finding_vocab` already blanks inline code spans as citation (#1202):

```
Addressed GitHub Claude of `9508454e` (`Needs more work`). Pushed `8af4edc9`.
```

Do not expect the checker to infer it from the sentence instead.
Three attempts were built and deleted on ai-config#2409 -- a driver-ledger classifier keyed on claim wording, the same classifier gated on the agent-disclosure marker, and a citation rule keyed on the disposition verb.
Each dropped or blanked a genuine reviewer's not-clean, because a reviewer rejecting a claimed fix writes the same sentence a driver does ("Addressed in `abc1234` (still Needs more work)").
The disambiguation has to come from the author, and a code span is how this corpus already spells it.

**The opening line is the commonest instance, not the only one.**
The same wire is tripped by a verdict phrase left bare anywhere in the comment --- a table cell summarizing what the reviewer said, or a paraphrase inside a Rebuttal expansion:

```
| 1 | Reviewer said `Needs more work` on the null check | Address | Fixed in `8af4edc9` |
```

Verified by execution: without those backticks, that row alone classifies the whole comment not-clean, exactly as the header line does.
So sweep the finished comment for the phrase rather than backticking only the line the example shows.

- **Do:** wrap a quoted verdict phrase in backticks wherever it appears in a disposition comment --- the opening line, a table cell, and a Rebuttal paraphrase alike.
- **Do:** re-read the finished comment for any remaining bare verdict phrase before posting it.
- **Don't:** leave a bare `(Needs more work)` next to a cited SHA -- that is the exact shape that freezes the PR.
- **Don't:** backtick the opening line and stop, on the strength of the worked example above.

### 4b. Reply to every inline review thread — and resolve where appropriate

(The standalone [`resolve-pr-threads`](../resolve-pr-threads/SKILL.md) skill
runs just the resolve half of this step on its own — useful for sweeping
already-settled threads without a full ARD pass.)

The one summary comment is **not** enough on its own. A reviewer who left
inline comments wants a response **on each thread**, not just a table posted
elsewhere. For every inline comment, post a short reply on its own thread with
the disposition (and the commit SHA for an Address), then **resolve** the thread
once the item is genuinely settled.

**GitHub** — reply on the comment's thread (`REPLY_REVIEW_COMMENT`), then
resolve via GraphQL (`RESOLVE_REVIEW_THREAD`):

```bash
# Reply on the same thread as inline comment <comment_id>:
# (quote every argument containing a <placeholder> -- bash treats a bare `<`
# as a redirection operator even mid-word, so an unquoted path like
# /tmp/reply-<comment_id>.md silently writes to the wrong file)
cat > "/tmp/reply-<comment_id>.md" <<'EOF'
✅ Addressed in `<sha>`.

_Posted by Claude Code (AI agent) --- not written by a human._
EOF
gh api "repos/{owner}/{repo}/pulls/<N>/comments" \
  -F in_reply_to="<comment_id>" -F body="@/tmp/reply-<comment_id>.md"   # REPLY_REVIEW_COMMENT

# List threads to get the node id, then resolve the settled one:
gh api graphql -f query='query { repository(owner:"<owner>",name:"<repo>") {
  pullRequest(number:<N>) { reviewThreads(first:100) { nodes {
    id isResolved comments(first:1){ nodes { databaseId body } } } } } } }'
gh api graphql -f query='mutation {
  resolveReviewThread(input:{threadId:"<thread_node_id>"}) { thread { isResolved } } }'   # RESOLVE_REVIEW_THREAD
```

In a remote/web session without `gh`, resolve `RESOLVE_REVIEW_THREAD` via
`mcp__github__resolve_review_thread` instead (see `tool-mappings.md`).

**GitLab** — reply to the discussion, then resolve it:

```bash
cat > "/tmp/reply-<discussion_id>.md" <<'EOF'
Addressed in `<sha>`.

_Posted by Claude Code (AI agent) --- not written by a human._
EOF
glab api -X POST "projects/:id/merge_requests/<N>/discussions/<discussion_id>/notes" \
  -F body="@/tmp/reply-<discussion_id>.md"
glab api -X PUT "projects/:id/merge_requests/<N>/discussions/<discussion_id>?resolved=true"
```

**Resolve only when the item is actually settled:**

- **Address** — resolve after the fix is **pushed** (reply names the SHA). Never
  resolve an Address whose fix isn't on the branch yet. Not confident the fix
  fully settles the concern? When the finding is ambiguous, turns on a design
  choice, or admits only a partial fix, reply explaining what you did and
  **ask for confirmation** instead of resolving. Leave the thread open for the
  reviewer to verify.
- **Defer** — reply with the tracked issue link, then resolve (work lives
  elsewhere now).
- **Acknowledge** — reply briefly, then resolve.
- **Rebut** — reply with the falsifiable evidence. A rebuttal only counts as
  settled once it **convinces the reviewer** — i.e. they don't re-raise it on
  the next round. While that's still in question, **leave the thread open**:
  resolve a bot's thread once it drops the item, and leave a human's thread
  open if they may want to respond. Resolving on acceptance happens a round
  *later* than the rebuttal, so it's easy to forget — **at the start of each
  new round, first sweep your still-open rebuttal threads and resolve any the
  latest review didn't re-raise**, before dispositioning the new findings. If
  you and the reviewer reach an impasse (your rebuttal didn't convince them,
  their re-raise didn't convince you), **escalate to a human reviewer** —
  request `the repository owner` via the `request-pr-review` skill (or
  `gh pr edit <N> --add-reviewer <reviewer>`, which bypasses that skill and so
  does **not** inherit its `Lacaedemon/sparta` exception --- in sparta, escalate
  to the user in chat instead of requesting a reviewer) and `@`-mention them
  with the impasse --- rather than resolving unilaterally or looping forever.
  Not every re-raise is an impasse, though: if the reviewer **accepts your fact
  but objects that the claim is over-generalized** (you verified one case and
  stated a sweeping rule), **narrow the claim to what you actually observed** —
  that's an Address, not a continued Rebut. Reserve escalation for genuine
  factual disputes. (Seen on ai-config PR #183: a tested
  project-root `{{< include >}}` behavior was correct but asserted as a
  universal Quarto-projects rule; the reviewer granted the test and asked only
  that it be scoped to the observed case, so the fix was to soften the wording,
  not re-argue.)

Don't resolve a thread you haven't replied to. Every inline comment ends with
both a reply and (where appropriate) a resolution — silence on a thread reads as
ignored, exactly the failure ARD exists to prevent.

**End-state (fully clean):** when the PR/MR is fully clean, **every inline
review thread is resolved**, and the only conversation left open is the final
all-clear exchange — the reviewer's all-clear comment (usually a top-level PR
comment, not an inline thread) and your reply to it. A leftover open inline
thread (an unaccepted rebuttal, an un-resolved Address) means you're not clean
yet.

### ARD round-close checklist

**Pause point: before reporting the round done.**
Do-Confirm; per
[`shared/workflow/skill-checklists.md`](../../shared/workflow/skill-checklists.md).

- [ ] Every finding is captured exactly once in the ARD table (after
      deduping summary + inline duplicates).
- [ ] Every table row has exactly one disposition (A/R/D/K), and no change
      request is labeled K.
- [ ] Every Address row points to a pushed commit SHA.
- [ ] Every Defer row links a filed tracking issue.
- [ ] **Killer item:** every inline thread has a reply; settled
      Address/Defer/Acknowledge threads are **resolved**; unresolved rebuttals
      stay open.
      Marked because addressing and resolving are separate actions and only
      the second clears
      [`fully-clean`](../../shared/workflow/fully-clean.md)'s criterion --- an
      addressed-but-unresolved thread reads as outstanding work to every later
      reviewer.
      Sweep by thread id, not by finding: a re-raise usually opens a *second*
      thread on the same line, often already marked outdated.
- [ ] The summary comment is posted from a body file (not inline), and no
      accidental review-trigger mention is present unless this round must
      explicitly re-request review.

### 5. Report back with a link

Tell the user what you did and give a **clickable URL** to the PR/MR (and to the posted summary comment if available), so they can review in one click.

## Rules

- **Every reviewer comment appears in the table AND gets a reply on its own inline thread** (step 4b). The summary table is the overview; the per-thread reply is what the reviewer sees in context. A thread with no reply reads as ignored.
- **Resolve threads once settled** (Addressed-and-pushed / Deferred-with-issue / Acknowledged), but never resolve a thread you haven't replied to or whose fix isn't pushed — and leave a human reviewer's thread open if they may want to respond.
- **Severity never exempts.**
  "Informational" / "Not a blocker" / "Nit" / "optional" / "consider" still require A, R, or D — never K.
- **Rebuttals must be falsifiable** — point to specific code, behavior, or documentation.
- **Deferrals must be tracked.** A defer without a filed issue is just ignoring with extra words.
- **Push before you post.** The reviewer should be able to verify Addressed fixes are on the branch.
- **A `suggestion` block is a hint, not gospel.** Before committing a reviewer's suggested fix, verify it actually works and handles the *general* case — not just the flagged spot. A confident suggestion can overcorrect (e.g. a regex tweak that fixes one form but breaks all the others). If the correct fix differs, apply that and note the divergence in your reply, so the reviewer sees why.

## Delegating sidecar work

When dispositioning a finding (step 2) turns up something that needs
independent digging --- testing a reviewer's factual claim before Addressing
or Rebutting it (see the testing rule above), researching how a prior PR
handled the same pattern, or checking whether a cited CI job still exists on
`main` --- hand it to a subagent via the `Agent` tool rather than blocking the
rest of the round on it. Keep dispositioning the remaining findings, posting
the summary, and pushing fixes on the main thread.

Give the subagent a stronger model (e.g. `model: 'opus'` on the `Agent` tool
call) when the check is judgment-heavy --- a subtle behavioral claim, a
disputed rebuttal --- rather than leaving it at the session default.
Symmetrically, drop to a cheaper/faster tier (`model: 'fable'` or `'haiku'`)
for a mechanical check (a lookup, confirming a file/symbol still exists); see
[`select-model`](../../skills/select-model/SKILL.md)'s decision tree for both
directions. For a heavy fan-out verification pass, prefer a separately-billed
provider (e.g. the `codex` CLI) first when available --- see
[`delegate-to-codex`](../delegate-to-codex/SKILL.md).

## Integration with ardi

Inside the `ardi` loop (also reachable as `iterate`):

1. Read the latest review (`ardi` step 2)
2. Apply ARD to each finding (this skill: steps 1–2)
3. Commit + push fixes (this skill: step 3)
4. Post the ARD summary and per-thread replies (this skill: steps 4–4b)
5. Re-request review (`ardi` step 6) — **even if this round was Rebut/Defer only**, so the reviewer re-evaluates.

The loop continues until the PR/MR is **fully clean** — zero findings, all CI
workflows green, and every inline review thread resolved (the only open
conversation being the final all-clear exchange — the reviewer's all-clear and
your reply to it). A rebuttal counts only once it convinces the reviewer; on an
impasse, escalate to a human reviewer (`the repository owner`; see step 4b for how).

## Edge cases

- **Ambiguous finding** — if you can't tell whether it's a change request or an observation, treat it as a finding and Address or Rebut. Don't assume it's informational.
- **Reviewers contradict each other** — Address the most recent reviewer; note the contradiction in your response so the user can arbitrate.
- **Finding duplicates a deferred item** — Rebut by pointing to the existing issue. Keeping the **Deferred / Out-of-Scope** section current in the PR/MR description should prevent re-flagging; if it recurs, update that section.
- **Findings sourced from a different PR/MR than the target branch** — treat the cited review as the finding source, but apply dispositions on the target PR/MR branch the user names. Post the ARD summary on the target PR/MR, then reply on each original inline thread with the target PR/MR link plus disposition-specific evidence: Address -> target fix commit SHA; Rebut -> target PR/MR comment link with the falsifiable evidence; Defer -> follow-up issue link; Acknowledge -> brief acknowledgment. This keeps provenance auditable across both threads without requiring a commit in non-Address rounds.
