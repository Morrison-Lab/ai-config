Before starting a work session on a GitHub PR or issue --- i.e. before fetching
the branch, making edits, or invoking an automated review cycle --- post a brief
comment on the PR/issue so other people and any automated review bots know not
to start a conflicting parallel session.

Use:

```
gh pr comment <N> --body "Working on this --- please hold off on pushing to this branch until I'm done.

_Posted by Claude Code (AI agent) --- not written by a human._"
gh issue comment <N> --body "Working on this --- please hold off until I'm done.

_Posted by Claude Code (AI agent) --- not written by a human._"
```

Both halves of that body are load-bearing, and they answer different questions.
The first line says the thread is claimed.
The trailing line says **who claimed it**, and it is required on every comment an agent posts to a forge --- not only on a claim.
See [`disclose-agent-authorship`](disclose-agent-authorship.md), which carries the rule, the exact marker, and why the marker deliberately avoids the robot emoji.

Then proceed with the work.
After the session ends (PR merged, issue closed, or work otherwise paused), follow up with a closing comment so the PR/issue is unclaimed for the next person.

Skip the claim step if the most recent comment already says you are working on
it **and that claim is still live under the expiration rule below**.
This applies to any task that will push commits to a PR branch or run
iterative review loops. It does **not** apply to read-only inspection (showing a
PR, checking status, explaining a diff) --- those don't risk a parallel session.

This includes a PR **you opened yourself**: in repos with an active `@claude`
agent (`claude.yml`), the agent can push commits to your branch on PR activity
--- e.g. merging `main` in --- and collide with your in-flight push, so claim
early to flag the branch as actively worked. (See
`memories/claude-bot-workflows.md`, "@claude CI action", for the
collision-recovery steps.)

When starting work from an issue, follow the claim comment with an immediate
draft PR --- see [`pr-on-claim`](pr-on-claim.md) for the mechanics. An open
PR is a stronger "in-flight" signal than a comment alone.

**A claim expires 2 hours after the most recent push or comment on the
PR/issue --- reassert it rather than resuming under a stale one.**
A claim comment with no expiry binds the thread indefinitely: a crashed or abandoned session leaves its "hold off" standing forever, and a second session has no rule for when the claim stops blocking.
So the convention is time-boxed and keyed to observable activity: a claim is **live for 2 hours from the most recent push or comment** on the PR/issue, and **expired** past that.

The rule cuts both ways.

- **As the claimant:** resuming work after more than 2 idle hours --- no push
  and no comment in that window --- starts with a fresh claim comment, not with
  an edit.
  The skip-if-already-claimed shortcut above covers only a live claim; an
  expired claim of your own no longer covers you, because a parallel session
  is entitled to treat it as lapsed.
- **As a would-be second session:** another claimant's claim whose PR/issue
  shows no push or comment in over 2 hours no longer blocks you.
  Take over by posting your own claim comment, never by starting silently ---
  the fresh claim is what flips the thread's state, and it is what tells the
  stale claimant they were superseded if they return.
  A claim's age is evidence about the *claim*, not proof the branch is quiet,
  so the mid-task checks below --- the "already done" cross-check against the
  PR's actual commit list, and the rejected-push tree comparison --- still
  apply before your first push, as does the branch-head re-fetch in the
  [`claim-pr`](../../skills/claim-pr/SKILL.md) skill's Notes.

Staleness is decidable by one read rather than by judgment, per
[`algorithmatize-checks`](algorithmatize-checks.md):

```bash
gh pr view <N> --json updatedAt --jq .updatedAt        # VIEW_PR
gh issue view <N> --json updatedAt --jq .updatedAt     # VIEW_ISSUE
```

`updatedAt` moves on more events than pushes and comments (labels, reviews,
body edits), so it only ever **over-approximates** freshness: a stale verdict
from it is definitive, and a borderline-fresh one defaults to respecting the
claim --- the safe direction, since over-respecting a dead claim costs a wait
while under-respecting a live one costs a collision.

- **Do:** post a fresh claim before resuming work when more than 2 hours have
  passed since the most recent push or comment on the PR/issue.
- **Do:** treat another session's claim as expired on the same 2-hour reading,
  and post your own claim before touching anything.
- **Don't:** read "the most recent comment already says I'm working on it" as
  a standing skip --- that shortcut covers only a claim under 2 hours old.
- **Don't:** start work under an expired claim, your own or anyone else's,
  without a fresh claim comment --- a silent resumption and a silent takeover
  collide identically.

(Directive from the user, 2026-08-15: "let's set a convention that pr and
issue claims last 2 hours from the most recent push or comment; if it's been
longer than that, reassert your claim.")

**Every detector of a claim matches the OLD wording as well as the new one, and dropping the old alternation is the one edit that fails silently.**
There were **two** retired invariants, not one, and enumerating them from the file in front of you is how the second was missed for a whole review round.
Most emitters carried the `paws off` invariant --- `claim-pr`, `gi`, `st`, `gip`, `pr-on-claim`, `post-merge`, `handoff` (as "still claimed, paws off.") and the orchestrator (as "paws off until done").
[`ardi`](ardi.md) did not.
It said "back off until done", and had done since 2026-06-17 --- and it is the corpus's highest-traffic claim emitter, run on every PR in every repo.
Both now read "please hold off ...".

Derive that set from history rather than from the current tree, which no longer contains any of them.
Match the **wordings**, not the `--body` flag.
Keying on the flag looks tighter and reaches neither `gip`, which states its claim as quoted prose inside a worker brief, nor the orchestrator, which builds the body as a Python f-string on a different line from the flag --- the two emitters least like the others, and so the two a flag-shaped search is least able to find.
Widen the pathspec past `skills/` for the same reason.

```bash
git log -p --all -- 'skills/**' 'shared/**' 'commands/**' 'scripts/**' \
  | grep -oiE '^\+.*(paws off|back off|hold off)[^"]*' | sort -u
```

That returns the matcher and prose lines too, so it wants a skim rather than a count --- the deliberate trade for a search that cannot miss an emitter because of how it happened to spell the call.

Claims posted before that are still sitting on open PRs and issues, and a claim stays live on activity rather than on age --- so a thread claimed under the old wording and pushed to this morning is live right now.

A detector narrowed to the new phrase alone still returns cleanly on such a thread.
It returns **nothing**, which is indistinguishable from an unclaimed thread, and that reading licenses exactly the parallel session this whole convention exists to prevent.
Nothing in the output announces the miss: a claim search that finds no claim looks the same whether the thread is free or the matcher went blind.

**Match the two-word invariant, never a whole sentence.**
The claim body varies by target --- a PR claim says "please hold off on pushing to this branch until I'm done" and an issue claim says "please hold off until I'm done" --- so neither sentence contains the other, and a detector keyed on either one is blind to half the claims.
Under the old single-string wording that distinction did not exist, which is exactly why it is easy to carry a whole-sentence matcher across the rename without noticing it has narrowed.
`hold off` is the invariant.
`paws off` and `back off` are its two predecessors, and a matcher naming only the first is the failure this very section describes, committed by the section itself.

So match the alternation, case-insensitively, everywhere a claim is read:

```bash
gh pr view <N> --json comments \
  -q '.comments[] | select(.body | test("hold off|paws off|back off"; "i"))'   # READ_PR_COMMENTS
```

Keep both old alternatives until no claim under a retired wording can plausibly still be live --- which, given the 2-hour rule keys on activity and not on the comment's own age, means until every PR and issue open on 2026-08-24 has closed.
Removing it is a deliberate later edit, not tidying to do in passing.

**Then check the same comment for a release term, because one release marker contains a claim invariant.**
The retired release wording is `... done --- paws off released.`, which matches `paws off` --- so the invariant that fixes the whole-sentence bug introduces a second one, and this one fails the quiet way round: a *released* PR reads as claimed, the reader backs off, and nothing reports why.
The sentence matcher this replaced did not collide, so the collision arrived with the fix.
Treat a comment as a release rather than a claim when it also matches `unclaim|released|PR is free|now mergeable`, and derive that list rather than copying it: `grep -rn "unclaim\|released\|PR is free\|now mergeable" skills/ commands/`.

- **Do:** match `hold off|paws off|back off` case-insensitively wherever a claim is read, then exclude the comment if it also carries a release term.
- **Do:** treat both old alternatives as load-bearing until the threads carrying them have closed.
- **Don't:** read an empty claim search as an unclaimed thread without first confirming the matcher covers both wordings --- the two results are identical.
- **Don't:** drop a back-compat alternative as part of an unrelated change.
- **Don't:** enumerate the retired wordings from the files you happen to be editing --- `back off` was invisible to exactly that method for a full review round, because the one file that posted it was not one of the seven that agreed with each other.

**Verify a mid-task "already done" claim against real PR state before trusting or redoing it.**
A PR you claimed and are actively driving can still gain commits from a **second, independently-running session** under the same account.
A `<github-webhook-activity>` review-comment-reply event can describe work this session never did, in the form "Addressed, pushed in `<sha>`".
Don't assume it's fabricated or injected, and don't reflexively redo the same fix: cross-check the PR's actual commit list (`gh pr view --json commits` / `pull_request_read` `get_commits`) and review threads before either (a) trusting the claim, or (b) starting the same fix yourself.
If a commit with that SHA genuinely exists, authored close to when the event arrived, treat it as confirmation a live parallel session owns this PR right now --- stop pushing further speculative fixes yourself, and, if genuinely in doubt, ask whether to keep driving or step back, rather than racing the other session's pushes.
This gap is distinct from the initial claim check above: it's not about claiming a PR before starting, but about **re-verifying you're still the sole active driver** once work has been under way for a while --- especially when you picked up the PR mid-session (e.g. by answering a diagnostic question about it) rather than through the normal claim-then-branch flow, so no fresh claim check ever ran right before you started pushing.

(`d-morrison/gha#286`, 2026-07-24: a webhook event delivered a review-comment reply attributed to `d-morrison`, reading exactly like a Claude-authored reply and claiming a fix this session hadn't made, worded "Addressed, pushed in 3fb8c5b".
It was verified real via `get_commits` before proceeding --- a second live session, not injection.)

**The git-level variant of that check: a rejected push whose remote commit is byte-for-byte what you were about to push.**
The section above covers a *comment* claiming work was done.
Here the parallel session makes no claim at all.
Your `git push` is simply rejected because it pushed first, and what it pushed is the same merge you just made.
The reflex on a rejected push is to merge again, which would stack a redundant merge commit on top of an identical one.

Four reads settle it before you touch anything:

```bash
git rev-parse HEAD^{tree}                 # your merge's tree
git rev-parse origin/<branch>^{tree}      # theirs
git show -s --format=%P HEAD              # your merge's parents
git show -s --format=%P origin/<branch>   # its parents
```

An identical tree plus identical parents means the two merges are the same merge, so the right action is `git reset --hard origin/<branch>`.

- **Do:** compare trees and parents before deciding what a rejected push means.
- **Do:** discard your local merge with `git reset --hard origin/<branch>` once both match.
- **Don't:** re-merge reflexively on a rejected push --- that is what produces the redundant merge commit.
- **Don't:** force-push over the other session's commit.

(`Morrison-Lab/ai-config#965`, 2026-07-31: `main` moved one commit, a local `git merge origin/main` was made, and the push was rejected.
The remote carried `b8d2273`, a merge of the same two parents, with tree
`1bda1bc`, identical to the local merge's.)

**Matching parents with a differing tree means the two sessions resolved
the same merge differently --- merge the two commits together, don't
reset onto either one.**
Identical parents but a different tree is not the "same merge" case
above: a concurrent session (a human, or an `@claude`-style bot
reacting to PR activity) merged the same `main` commit into the same
branch, but resolved a real conflict (or made an additional fix)
differently than you did.
`git reset --hard origin/<branch>` here silently discards whatever your
version got right that theirs didn't --- e.g. a version-parity bump
their merge didn't carry, or a merge-conflict resolution theirs got
wrong.
Instead, fetch and merge the remote branch into your local one (an
ordinary three-way merge, since the two commits share both parents as a
common ancestor between them); resolve any conflict on its own merits,
the same as any other merge, then push the result.

- **Do:** compare parents first, then trees; matching parents with a
  differing tree calls for a merge of the two commits, not a reset.
- **Do:** merge the remote branch in normally, resolving whatever
  differs on its own merits.
- **Don't:** `git reset --hard` onto a same-parents-different-tree
  remote commit --- that discards your own resolution outright, on the
  assumption the two were interchangeable.

(`UCD-SERG/serocalculator#654`, 2026-08-08: `main` had absorbed a
same-version dev bump from an unrelated PR, so this session merged
`main` in and bumped the version past it while separately resolving a
real conflict in `inst/WORDLIST`.
The `@claude` review bot's own `main`-sync had pushed a merge with the
same two parents in the meantime, but it left the version at parity ---
still failing `version-check` --- and had never seen the `WORDLIST`
conflict at all, since its sync predated that conflict existing.
Merging the two commits, rather than resetting onto either, kept both
fixes.)

**Second occurrence, 2026-08-24, with DIFFERENT parents --- the same lesson in the case the section above does not describe.**
Both branches of the rule above turn on the parents matching, which happens when two sessions resolve the same `main`-merge.
The commoner collision has matching parents nowhere in sight: two sessions independently fix the **same review round's findings** on one branch, five minutes apart, so the two commits share only their base and the divergence is ordinary.

What carries over is the part that is not about parents.
"They addressed the same findings" is exactly the belief that makes a reset feel safe, and it is the same interchangeability assumption the `Don't` above rejects.
Measured on [ai-config#2185](https://github.com/Morrison-Lab/ai-config/pull/2185), 2026-08-24 Pacific (`3b8d04e6` at 18:23 and `cf195e46` at 18:28, merged as `5c577a54` at 18:35): each side had a fix the other lacked --- `3b8d04e6` an attached `-F` body (`-Fbody.md`), `cf195e46` a flag-boundary lookbehind without which a **compliant** comment warned --- so either reset would have shipped a regression that no check could see, since both sides were green.
A third apparent difference was inert: `cf195e46` dropped the `--comment=` alternative the base already carried, and `--comment\b` matches `--comment=x` anyway, since the boundary sits between `t` and `=`.
That one is the reason to **execute** both patterns rather than read both diffs.

- **Do:** merge two independent fixes for one review round, whatever their parents, and **run** each side's version against the inputs at issue --- a diff shows what each side changed, and only executing it shows which of those changes did anything.
- **Don't:** reset onto the other session's commit because the two rounds answered the same findings --- addressing the same list is not producing the same fix.

**Handing off mid-task to another agent, on user request ("finish what you're
doing, then relinquish holds; I'll put another agent on them"):** don't just
stop --- leave the next agent a clean starting point. On each claimed PR/issue:
(1) post a status comment on the PR itself distinguishing what's **done** from
what's genuinely **not done** (the actual point of the issue, not just the
side-fixes found along the way) and any blocker still open, so the next agent
doesn't have to re-derive it from the diff; (2) post the closing/unclaim
comment on the issue per the pattern above; (3) `unsubscribe_pr_activity` (or
stop babysitting locally) so you don't keep auto-fixing a PR you no longer
own; (4) stop any background watch/poll task tied to that work (e.g. a
`ScheduleWakeup` or a `Monitor`/background-Bash wait) so it doesn't fire into
a session that's moved on. A merge-conflict-free `git status` and a pushed
branch are not enough on their own --- the status comment is what makes the
handoff legible. (ucdavis/bcs `gia` session, 2026-07-06: handed off PRs #310
and #311 mid-implementation this way, each blocked on the same slow
`renv::restore()`.)
