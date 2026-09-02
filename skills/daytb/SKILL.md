---
name: daytb
description: "Decide current question yourself."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Grep
  - Glob
---

# daytb -- do as you think best

A one-shot grant of decision latitude.
The user has read the question and is handing it back rather than answering it:
pick the option you would have recommended, act on it, and say what you picked.

## Scope

One decision, task-scoped: the question in front of you plus the follow-ons the same task raises, expiring with that task --- never with the session --- and repeated `daytb` keywords do not accumulate into a session grant.
The sections below carry the full boundaries;
[`away`](../away/SKILL.md) is the session-wide sibling, revoked by [`back`](../back/SKILL.md).

## When this fires

- The bare or slashed keyword `daytb`.
- The phrases it stands in for: "do as you think best", "do as you see fit",
  "do whatever you think is best", "your call", "you decide", "up to you",
  "I trust your judgment here".
- A reply that answers a posed decision by declining to choose --
  "either is fine", "whichever you prefer" -- which is the same grant in
  different words.

## What it grants

Latitude over **the decision in front of you**, and the ones that follow from
it while the same task runs.

It does not silence you.
The user is present, so the point is to stop *asking* rather than to stop
*reporting*: a decision made under `daytb` still gets stated, in the past
tense, with the one reason that settled it.
That is what keeps countermanding cheap.

## What it does not grant

- **Not the rest of the session.**
  `daytb` expires with the task it was given for.
  A later, unrelated decision is a fresh question.
  For a standing session-wide grant, that is [`away`](../away/SKILL.md).
- **Not destructive or irreversible actions.**
  A merge, a force-push, a deletion, anything outward-facing still needs its
  own explicit authorization.
  Merge authority specifically is [`mwc`](../mwc/SKILL.md)'s grant, not this
  one.

  **Local git housekeeping is the exception, and it is inside the grant.**
  Removing a stale worktree, deleting a merged local branch, and
  fast-forwarding a *behind* local branch ref to its remote are all covered
  -- do them rather than filing them back as a question.
  What makes them safe is that they are local and recoverable: the commits
  stay in the object store and the reflog, and nothing outward-facing
  changes.

  Each covered action has its own precondition, and none of them is
  satisfied by a clean tree alone:

  - **Removing a worktree** needs the *liveness* check, not just a content
    check.
    A clean `git status` and an unlisted agent each describe one instant, so
    neither says whether the session working that directory has stopped ---
    ask the agent directly first, per `CLAUDE.md`'s "Subagent worktrees are
    assigned, and an incident never silently repeals a decision" and
    [`memories/git-worktrees.md`](../../memories/git-worktrees.md), which
    records a quiet worktree misread as dead while it was live.
    A long quiet stretch is a reason to ask sooner, not evidence of
    abandonment.
    Then check the content: HEAD reachable from a remote, or demonstrably
    superseded.
  - **Deleting a local branch** needs its content already on the default branch.
    Neither `git merge-base --is-ancestor` nor a commit-range count establishes that in a squash-merging repo --- the branch's own commits are never ancestors of the squash commit, so both report merged work as unmerged.
    A two-dot `git diff <default> <branch>` is not the fix either: a non-empty result conflates the branch carrying content the default branch lacks (unsafe to delete) with the default branch having simply advanced past the branch (irrelevant to deletion), and restricting the diff to the branch's own files does not resolve it, since a sibling PR that touched the same file reproduces the same confusion.
    [`pr-on-claim`](../../shared/workflow/pr-on-claim.md)'s "One reading it does not cover" section carries the measured case: a fully-merged branch whose two-dot diff ran to thousands of lines purely because the default branch had since taken later, unrelated merges.
    Settle it by checking whether the branch's own additions are present on the default branch, not whether the trees differ: grep the merged content (`git show origin/<default>:<path> | grep -c '<distinctive phrase the branch added>'`), or diff in one direction only (`git diff origin/<default>...<branch>`, three-dot so the merge base sits on the left) and confirm none of its `+` lines are missing from the default branch.
    - **Do:** confirm the branch's own additions are present on the default branch, via a grep of the merged content or a one-directional three-dot diff, before deleting.
    - **Don't:** treat a two-dot `git diff <default> <branch>` as the check --- a non-empty result says nothing about which side changed, and a repo with active development makes it non-empty far more often than it makes it a reliable signal either way.
  - **Fast-forwarding a branch ref** needs the local ref to be strictly
    *behind* its remote.
    A ref carrying commits reachable from no remote is not behind, it has
    diverged, and `git branch -f` would drop those commits from the pointer
    --- that is triage, not cleanup, and it is outside the grant.

  Keep anything carrying commits reachable from no remote, in all three
  cases.
  A push, a remote-branch deletion, or a `git reset --hard` over unpushed
  work stays outside the grant.
- **Not the safety rules.**
  Everything that required confirmation before still does.
- **Not a licence to guess when you genuinely cannot judge.**
  If proceeding either way would be unsafe, or the options differ on a fact
  only the user holds, say so plainly and ask the narrower question.
  That is rare -- treat it as the exception it is, not an escape hatch.

## Procedure

1. **Name the decision(s) the grant covers.**
   Usually the one just posed.
   If several were queued behind it, they are covered too unless answering
   one moots the rest.
2. **Choose the option you would have recommended.**
   Apply the same criteria you would have written into a
   `🧭 RECOMMENDATION` box.
   If you had already stated a recommendation, take it -- handing the
   decision back is agreement to it, not an invitation to reopen it.

   **Re-read the artifacts the options name before taking it.**
   A recommendation rests on claims about state, and those expire like any
   other ([`metacognitive-monitoring.md`](../../shared/workflow/metacognitive-monitoring.md)),
   so the gap between recommending and being handed the decision is where
   they expire.
   [`challenge-the-assignment.md`](../../shared/workflow/challenge-the-assignment.md)
   owns the general argument and the population it applies to; what is
   specific to `daytb` is that step 2's take-it-don't-reopen instruction
   sits directly over that check and can suppress it.

   **The check is bounded by artifact, not by judgment, and the bound is
   what keeps this from swallowing the rule.**
   It licenses exactly one thing: re-reading the specific artifacts an
   option names -- the file, the config, the workflow -- and seeing whether
   they still say what the option assumed.
   It licenses nothing else.
   A changed weighting, a new argument, a criterion you would now apply
   differently, a consideration that did not occur to you before: each is
   re-deliberation, and each is out of bounds however persuasive.
   The test is mechanical rather than introspective, which is the point --
   if you cannot name the artifact you re-read and quote the line that
   moved, you are reopening the decision, not checking a premise.

   Note the asymmetry that makes the bound necessary rather than tidy.
   Every recommendation rests on many premises, and something has always
   moved -- a branch, a comment, a CI run.
   An unbounded licence to re-check is therefore an unbounded licence to
   re-choose, and it would be cheaper to invoke than to comply with, which
   is a rule that does not exist.

   When a named artifact really has moved, the grant still holds and the
   answer is still yours: pick again on the current facts and report
   **both** the choice and the change, since a silent switch away from a
   stated recommendation reads as having reopened it.
3. **Act.**
4. **Report in the past tense**: what you chose, and the single reason that
   decided it.
   One or two sentences.
   Name anything you deliberately did *not* do, so a silent omission does
   not read as an oversight.
5. **Do not re-ask.**
   A follow-up question about the same decision spends the round trip the
   grant existed to save.

## Relationship to other skills

- **[`away`](../away/SKILL.md)** -- the session-scoped sibling, and the one
  most easily confused with this.
  `away` presumes the user is *gone*: it suppresses questions for the rest of
  the session, keeps a decision log, and is revoked by `back`.
  `daytb` presumes the user is *here* and simply declining to adjudicate one
  thing, so it carries no session state and needs no counterpart.
  Reading `daytb` as `away` would silently suspend clarifying questions long
  after the user expected them back.
- **[`back`](../back/SKILL.md)** -- revokes `away`.
  Nothing revokes `daytb`, because it expires on its own.
- **[`mwc`](../mwc/SKILL.md)** -- the grant that *does* extend to merging.
  `daytb` deliberately stops short of it.
- **[`prompt-me`](../prompt-me/SKILL.md) /
  [`prompt-me-all`](../prompt-me-all/SKILL.md)** -- the opposite direction:
  surface the questions rather than resolve them.
- **[`dmmhyh`](../dmmhyh/SKILL.md)** -- built on this skill's procedure for resolving the triggering item, but fires when the user is correcting a *pattern* of over-asking rather than just handing back one decision.
  It adds a standing in-session recalibration and a durable memory write that `daytb` alone doesn't do -- reach for `dmmhyh` instead of `daytb` when the user's complaint is about asking too much in general, not this one question.

## Anti-patterns

- Treating it as session-wide, and quietly dropping clarifying questions for
  unrelated later work -- that is `away`, and the user did not ask for it.
- Reading it as authorization to merge, delete, or publish.
- Choosing silently, so the user learns what was decided only by noticing the
  result later.
- Asking a confirming question anyway -- "I'll do X, unless you'd rather Y?"
  is the grant declined, not honoured.
- Reopening a recommendation you had already made, instead of simply taking
  it -- though re-reading the artifacts its options name is not reopening
  it, per step 2.
- Filing a stale worktree or a merged local branch back as a question, or as
  an issue for the user to action, when the grant already covers clearing it.

## Case record: a recommendation that expired between stating and taking it

`Morrison-Lab/gha#240` asked how to restrict the review workflow's network
egress, and enumerated three options.
Its analysis rested on three separately-named tool grants:
`WebFetch`, `Bash(curl:*)`, and `Bash(python3:*)`.
I recommended option 3 -- gate those grants on the repo opting into
computer-algebra review -- and the decision came back as `daytb`.

Step 2's rule says to take the recommendation rather than reopen it.
Re-reading the artifact it named,
`.github/actions/run-claude-review-attempt/action.yml`,
showed the allowlist had become
`"Bash,Edit(//tmp/**),WebFetch,WebSearch"`:
`Bash` is granted **whole** (gha#566/#572), so the two Bash grants option 3
proposed gating are no longer separate allow entries.

**What that does and does not establish is where I first got it wrong.**
It does not make them ungateable.
Deny rules still gate Bash subcommands, the action carries dozens of them
today, and the same file records `Bash(python3 -m:*)` being *removed* from
that deny list under the whole-Bash regime -- which demonstrates the gate
works rather than that it is gone.
What actually defeats option 3 is stated in that file directly: the denials
are "guard rails against an accident, NOT a security boundary", because
"a prefix rule cannot contain a general shell".
So denying `python3` and `curl` while granting `Bash` whole leaves egress
reachable by any other route and reduces no blast radius, which was option
3's entire purpose.
Achieving that purpose would mean returning to a named allowlist -- and
*that* is what five measured starvation incidents had just been spent
removing, none of which involved `python3` or `curl` at all.
The four with recorded costs total about $26.

A second premise had moved the same way: gha#580 split the review so the job
processing attacker-influenceable content holds `contents: read` and no
forge-write, narrowing the risk the issue was filed about.

Both changes post-date the issue by roughly seven weeks, and neither is
visible from its body -- which is the general shape rather than a detail of
this case.
The chosen option became option 1, and the report named the switch and its
cause rather than quietly delivering something other than what had been
recommended.

**The correction is itself part of the record.**
The first version of this entry claimed the grants were "no longer gateable"
and that option 3 would have reintroduced the five starvation incidents.
Both were wrong, and both were caught by an adversarial review reading the
same file -- the first contradicted by a deny list forty entries long, the
second by the fact that not one of the five incidents was denied `python3`
or `curl`.
The decision survived; the reasoning published for it did not, and had to be
corrected on the issue as well as here.
That is the failure mode this entry exists to name, occurring inside the
entry naming it: a premise checked once, at the moment of deciding, and then
narrated from memory rather than re-read.

- **Do:** re-read the artifact an option names, and quote the line that
  moved.
- **Do:** report the switch and its cause when a named artifact has moved.
- **Don't:** re-argue a recommendation the user has handed back -- a
  changed weighting is re-deliberation, not a premise check.
- **Don't:** treat an issue body's enumerated options as current; the older
  the issue, the more its scoping is a claim about a past codebase.
