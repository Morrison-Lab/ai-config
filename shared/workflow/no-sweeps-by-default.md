# A new rule is not swept across existing content

Ezra, 2026-10-29 ([ai-config#4829](https://github.com/Morrison-Lab/ai-config/issues/4829)): "don't sweep new rules unless I explicitly tell you to sweep;
by default, just fix incrementally when you are editing a passage anyway."

## The rule

- When a rule lands (a writing rule, a notation rule, a convention), apply it to the content you write or edit from then on.
- Do not open a PR, issue or batch series whose purpose is to bring existing content into line with the new rule, unless Ezra explicitly says to sweep.
- When you edit a passage for any reason, fix its violations of current rules in the same edit, as part of the passage's own diff.
  That is the incremental fix, and it needs no ask.
- Checks look at changed lines only.
  A new content check defaults to diff-scoped;
  a whole-repo mode is for a requested sweep.
- A sweep Ezra asks for goes out as small batches ([`small-prs`](small-prs.md)), and its PR body carries a `Sweep authorized:` line quoting or linking his message.

## What is not a sweep

- Fixing the same defect in the PR you are already working on, including sibling files that PR touches and the divs it includes or follows (`notes-pre-review-pass`, `address-every-comment`) ([`learn-from-review-findings`](learn-from-review-findings.md)).
- Classification work on ai-config's own hooks and scripts, such as [#1967](https://github.com/Morrison-Lab/ai-config/issues/1967) and [#1449](https://github.com/Morrison-Lab/ai-config/issues/1449).
- A one-off audit whose output is a list in an issue, with no content changed.
  Do not file one for a rule that just landed, though: leftover violations are fixed when someone next edits that passage.

## Approving a check is not approving a sweep

On 2026-11-17 Ezra approved a British-spelling check, and the thread that built it opened about 25 PRs fixing existing pages ([ai-config#5773](https://github.com/Morrison-Lab/ai-config/issues/5773)).
A new check reads changed lines, so existing violations do not trip it, and a relayed "yes" covers the check, not a pass over existing content.

- **Do:** ship the check alone.
- **Do:** ask the user before an 11th PR on one ask.
- **Don't:** clear a new check's existing violations because you expect it to flag them.
- **Don't:** read a coordinator's note, or your own reading of the ask, as the user saying "sweep".

## A brief does not widen the ask

On 2026-11-20 Ezra said "do that" to moving the ids equation-label check into gha.
The coordinator's brief to the new thread also told it to label every unlabeled equation in all the notes repos and roll the check out everywhere.
His reply: "did I say to sweep?"
Whoever writes the brief, a coordinator or an agent launching a subagent, is bound by the ask as the user wrote it.

- **Do:** brief the step the user asked for, and name the wider work in the brief as a follow-up to offer the user.
- **Don't:** add a sweep, a rollout to every repo, or edits to existing content to a brief because they seem to follow from the ask.

## The mechanisms

- `hooks/no-unrequested-sweep-in-brief.py` denies a brief (a subagent launch, `SendMessage`, a thread start, a thread or coordinator message, remote-control instructions) that says "sweep", pairs "all/every ... repos", "everywhere" or "existing content" with a content-edit verb, or names three or more notes repos beside an edit verb, unless the user's own words since their latest message ask for that breadth.
  The phrase is read clause by clause (split at commas, semicolons and colons): a clause that is a question, offers the work ("offer it as a follow-up"), negates the phrase, or is about PRs, CI, merges, hooks or branches passes.
  A typed `gia`, `gii`, `gip`, `gmd` or `ardia` grants it, as for the PR guard.
  It catches the widening when the work is handed over, before `no-unrequested-sweep-pr.py` can see any PR.

- `hooks/no-unrequested-sweep-pr.py` denies a PR creation (`gh pr create` or `mcp__github__create_pull_request`) once ten PRs were opened since the user's latest message, unless a sentence the user wrote asks for a sweep.
  Only the user's words count, never a coordinator's `<note>`, a question ("did I say to sweep?") or a negation ("don't sweep").
  A typed `gia`, `gii`, `gip` or `gmd` also allows more.
  There is no agent-side bypass; the user's next message resets the count.
  The reviewer layer is "Unrequested sweeps" in [`adversarial-reviewer`](../../.claude/agents/adversarial-reviewer.md).
- `hooks/no-unnamed-repo-pr.py` denies a PR in a repository the user never named this session, other than the session's own checkout, though a repository named only as precedent still passes ([ai-config#5780](https://github.com/Morrison-Lab/ai-config/issues/5780)).
- `hooks/warn-sweep-pr-without-ask.py` warns when `gh pr create` or `mcp__github__create_pull_request` has "sweep" in the title (or, for `gh pr create` only, a `sweep` label) and no `Sweep authorized:` marker (followed by a message id or link).
  It warns rather than blocks because a title containing the word is not always a sweep, and a hook cannot read Ezra's intent.
- gha's content checks (`check-new-line-breaks`, `check-def-commentary`, `check-exm-figures`, `check-one-div-per-subfile`, `check-tree-lists`, `check-visualization-figures`, `check-typos` and others) are diff-scoped by default (checked 2026-10-29), reflagging nothing already merged.
  Where a whole-tree mode exists (a `whole-tree` input, which most of the checks above carry except `check-new-line-breaks` and `check-typos`), it is opt-in, so keep it off by default.
- `hooks/no-oversized-pr-push.py` already caps any PR at 20 files and 600 lines ([`small-prs`](small-prs.md)), so an unrequested sweep that slips past the title check still cannot ship as one large PR.
- The part with no mechanism: deciding that a fix is incremental, not a sweep, depends on whether the passage was already being edited.
  A hook cannot know that, so this prose carries it.

## Decisions

- Explicit asks still win: Ezra's 2026-10-14 request to backfill visuals ([`visuals-everywhere`](../writing/visuals-everywhere.md)) stands, because he asked for it in those words.
- Earlier follow-ups of the form "sweep lds#..." on rule threads are superseded by this rule, unless Ezra explicitly asked for that sweep.
- "Going forward" alone in a rule message is not a sweep ask;
  the visuals message also said "backfilling the existing content".

- **Do:** fix a violation in the passage you are already editing.
- **Don't:** open a sweep PR or issue because a rule just landed, or add a whole-repo mode to a new check by default.
