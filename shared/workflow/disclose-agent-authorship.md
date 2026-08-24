Every comment an agent posts to a forge --- GitHub, GitLab, or any other --- says, in the body, that an agent posted it.

The reason is that the forge cannot say it for you.
An agent driving `gh` under the account holder's credentials posts as **that person**: the comment carries their avatar, their login, and a `MEMBER` or `OWNER` association, and nothing in the API response distinguishes it from a comment they typed.
`type` reads `User`, not `Bot`, because the token belongs to a user.
So a reader deciding how much weight to give a claim, a status report, or a review has no way to tell which of the two they are reading, and the default reading is the wrong one.

The marker is one line, on its own, at the end of the body:

```
_Posted by Claude Code (AI agent) --- not written by a human._
```

**It deliberately does not use the robot emoji.**
That looks like the obvious choice, and it is the one thing the marker must avoid: `scripts/check-pr-fully-clean.py` matches the bare emoji as a `REVIEW_BODY_MARKERS` entry, so any comment carrying it is admitted into the verdict scan as a review item.
A disclosure footer on every agent comment would therefore turn every claim, every status note, and every deferral into something the fully-clean checker reads as a review --- and a claim comment carries no findings, so it would scan as a **clean** one.
That is the false-clean failure [`fully-clean`](fully-clean.md) already describes for a human-authored self-review, arriving through the very mechanism added to make authorship legible.

The marker above collides with none of the checker's `REVIEW_BODY_MARKERS` (the robot emoji, `### ` plus that emoji, `code review`, `**claude finished`, `### verdict`, `verdict:`) nor with any `REVIEW_AGENT_MARKERS` entry, verified against `scripts/check-pr-fully-clean.py` on 2026-08-24.
Check a replacement marker against both tuples before changing it.

**The scope is every comment, not every review.**
Review comments are the case that already discloses, since a review body announces its own agent.
The comments that need this are the ones that read most like a person: a claim, a release, a status update, a reply on a review thread, an issue filed on the user's behalf, a paraphrase of the user's own in-chat feedback.
Each of those is short, conversational, and posted under a human login, which is exactly the shape that gets mistaken for a human.

**A prose self-identification is not a substitute for the marker.**
"Claude Code CLI (local session) is working on this" already discloses, so appending the footer to it looks redundant.
Keep both.
A convention worth anything has to be checkable by one query rather than by reading each body and judging whether its prose happened to disclose --- and a uniform trailing marker is what makes a sweep, or a hook, possible at all.

**Search for the marker as a substring, never as a whole line.**
A body composed inside an indented code fence carries that fence's indentation into the posted comment, so the marker can arrive with leading spaces.
Dedenting the source to column 0 is not the fix: a column-0 line ends the enclosing list item, which closes the fence and turns the marker into prose --- markdownlint MD049 catches it, and the comment stops being shown as a command at all.
So the source keeps its indentation and the query drops its anchor.

**The guard cannot see every body, and the gaps are worth knowing.**
`hooks/require-agent-disclosure.py` reads the command text and the `mcp__github__*` comment tools, so it is silent on a body it cannot reach: a `--body-file`, an `--editor` session, an interpolated `$BODY`.
It reports those as an **unreadable** body rather than as a missing marker, so its warning never asserts more than it observed --- but a `--body-file` comment that genuinely omits the marker draws only the weaker note.
`skills/ard/SKILL.md`'s per-round summary is exactly that shape, which is why it states the requirement in its own text rather than relying on the guard.

**Where the marker must NOT go: content that is not a comment.**
A commit message, a PR title, or an issue title has its own attribution conventions and its own consumers, and a trailing italic line in a commit message corrupts a changelog.
PR bodies already carry the harness's own generated-with footer.
This rule governs comment bodies.

**One exemption, and it is narrow: a comment another MACHINE parses as a command.**
`@dependabot rebase`, `@dependabot squash and merge`, and their equivalents are not addressed to a reader at all --- they are an API call wearing a comment, and the receiving bot parses the body.
Appending prose to one risks changing what it parses, for no reader's benefit, since nobody mistakes `@dependabot rebase` for a human's considered opinion.

The exemption is about the **audience**, not about brevity.
A one-line status comment is short and still has a human reader, so it carries the marker.

As of 2026-08-24 the exemption covers three sites: `skills/chores/SKILL.md`'s two Dependabot commands, and the review re-request `skills/ardi/SKILL.md` mandates, whose whole body is the reviewer's own `@`-mention.
That third one is worth naming because the first draft of this rule missed it and asserted the other two were the only instances --- an enumeration of a population nobody had queried, which is [`metacognitive-monitoring`](metacognitive-monitoring.md)'s scope-claim failure.
Derive the set before restating it:

```bash
grep -rn -- '--body "@\|--message "@' --include="*.md" --include="*.sh" .
```

- **Do:** omit the marker on a comment whose whole body is a command addressed to another bot.
- **Don't:** widen that to any comment that happens to be short, or to any comment posted by automation --- the test is whether a machine parses the body, not whether a machine wrote it.

- **Do:** end every agent-posted forge comment with the marker line, on its own, after a blank line.
- **Do:** keep the marker on comments whose prose already identifies the session, so one query finds all of them.
- **Do:** check a proposed replacement marker against `check-pr-fully-clean.py`'s `REVIEW_BODY_MARKERS` and `REVIEW_AGENT_MARKERS` before adopting it.
- **Don't:** use the robot emoji in the marker --- it is a review-body marker, and it converts every disclosed comment into a finding-free review item.
- **Don't:** treat a comment posted under a human login as self-evidently agent-authored because the account holder knows an agent is running.
  The reader is whoever finds the thread later.
- **Don't:** put the marker in a commit message, a title, or a PR body.

(Directive from the user, 2026-08-24: "all comments online posted by bots should say so", citing <https://github.com/UCD-SERG/ucd-serg.github.io/pull/108#issuecomment-5397889734> --- an agent-authored claim comment posted under `d-morrison`, `type: User`, `author_association: MEMBER`, reading exactly like a human's.)
