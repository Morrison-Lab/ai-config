[`issue-first`](issue-first.md) governs *whether* something is tracked before
work starts.
It does not settle *where*, and defaulting everything to the issue tracker
misfiles a whole category of item.

The split is the one GitHub's own product taxonomy draws:

- **Issue** --- actionable, trackable work.
  A bug, a task, an enhancement with a definite deliverable and a "done".
- **Discussion** --- an open-ended question, an idea, or a policy debate whose
  deliverable is a *decision*, and which has a real do-nothing option.

A policy question filed as an issue has no good ending.
It sits open indefinitely, or it gets closed as "decided: no" --- which reads in
the tracker like abandoned work rather than a settled decision, and is
indistinguishable from it a month later.

So when the deliverable is a judgment rather than a diff, open a discussion.
File the *consequences* as issues once it settles, each referencing the topic,
which is also what keeps the tracker a list of things someone could pick up.

## Prefer an answerable category for a decision topic

GitHub marks exactly one default category answerable (`Q&A`,
`isAnswerable=true`); `Ideas`, `General`, and the rest are not.
Marking an accepted answer is the only native mechanism that records a
resolution *on* the topic, so a decision belongs in the answerable category even
though `Ideas` sounds like the better fit by name.

Without it the outcome lives in whichever comment happened to be last, which a
later reader has to reconstruct by reading the whole thread.

## Best practice outranks precedent

The venue rule above is a specific case of a general one, and the general one is
what the correction that produced this fragment was actually about.

When deciding **how** or **where** to do something, weigh best practice above
what the repo has happened to do before.
Precedent records what was convenient at the time rather than what was right, so
leading with it launders an unexamined habit into a justification.
It compounds, too: every appeal to precedent strengthens the next one, whether
or not the underlying practice was ever examined.

The sharpest form of the mistake is **circular discoverability reasoning**:
"the discussion board is unused, so a decision recorded there would be buried."
That argument can never permit anyone to start using it, because the only way an
unused venue becomes used is for someone to post the first topic.
An argument whose premise is guaranteed by its own conclusion is not an
argument.

- **Do:** pick venue and method from the tool's actual purpose.
- **Do:** cite precedent as context, and say plainly when you are departing from
  it and why.
- **Don't:** treat "this repo files decisions as issues" as settling where a
  decision goes.
- **Don't:** argue against a venue because it is currently unused, or against a
  practice because it would be the first instance.

## Keep the mechanical costs separate from the habit argument

One objection to Discussions survives the correction above, and it is worth
stating precisely so it does not get waved away along with the bad one.

Discussion **writes** are GraphQL-only.
There is no `gh discussion` subcommand and no `mcp__github__*` Discussions tool,
so a remote or web session without `gh` may be unable to post at all
(see [`tool-mappings.md`](../../tool-mappings.md), and the
[`discussions`](../../skills/discussions/SKILL.md) skill for the local
`gh api graphql` path).
That is a real property of the tool.
"Nobody uses the board" is not.

**Reads are a different story, and this fragment's older blanket
"GraphQL-only" claim was wrong about them.**
GitHub serves repository discussions over REST:
`GET /repos/{owner}/{repo}/discussions`,
`.../discussions/{n}`,
and `.../discussions/{n}/comments` all return normally.
So a session with no `gh` and no GraphQL passthrough can still read a topic
and its comments,
which is enough to answer a question *about* a discussion,
to check whether an answer has been marked,
and to dupe-check before filing.
It is not enough to reply in the thread.

The distinction matters because the blanket claim licensed the wrong
conclusion twice over.
It invited reporting a discussion as entirely unreachable when only half of it
was,
and it is the shape
[`growth-mindset`](growth-mindset.md) warns about:
a limitation asserted from a category ("Discussions are GraphQL-only") rather
than from an attempt.
Try the REST read before reporting either half unavailable.

Measured 2026-07-30 against
[`Morrison-Lab/gha` discussion 378](https://github.com/Morrison-Lab/gha/discussions/378),
from a session whose egress proxy refuses GraphQL outright:
all three GETs returned 200 from `Server: github.com`, with
`X-Github-Api-Version-Selected: 2022-11-28` and a real `X-Github-Request-Id`,
so they are genuine GitHub responses rather than a proxy shim.
`POST .../discussions/378/comments` returned 404 from that same host.
The write half was not pinned down further --
a 404 there is consistent both with the route not existing and with the token
lacking discussion write --
so treat writes as GraphQL-only until something demonstrates otherwise,
and re-test rather than trusting this paragraph if it matters.

**When you do re-test, expect the GraphQL refusal to send you somewhere that
does not work.**
A proxy that blocks GraphQL can refuse it with advice attached:

```
403  This GraphQL query is not enabled for this session -- only the pinned set
     of PR-review operations is served.
     Use REST via `gh api repos/{owner}/{repo}/...` instead.
```

That advice is right about most of the API and wrong about this corner of it,
since the REST discussion-comment route 404s.
So the error hands you a remedy, the remedy fails, and the natural reading of
the 404 is that your call was malformed rather than that the route is closed.

Read the two together instead: a 403 naming a session policy plus a 404 on the
REST equivalent is the *same* answer twice, not two separate problems to debug.
The write half is closed; stop and hand the text to a human.

- **Do:** treat a 403-with-advice and a 404 on the advised route as one
  finding.
- **Don't:** spend calls varying the REST request after the 403 --- the
  suggestion was generic, not endpoint-specific.

(Re-measured 2026-07-31 against the same discussion, from a different session:
GraphQL `POST` 403 with the message above, REST `POST .../comments` 404, REST
`GET` still 200.
The failed probe created nothing --- the discussion still reported 0 comments
afterward --- so a probe of this shape is safe to run.)

There is also **no issue-to-discussion conversion mutation** in the public
schema.
`createDiscussion`, `updateDiscussion`, and `closeDiscussion` all exist;
conversion is UI-only.
That matters here because it makes a misfiled item expensive to move rather than
free, so the venue judgment is worth making up front rather than deferring.
When something is already in the wrong place, run
[`migrate-discussion`](../../skills/migrate-discussion/SKILL.md) rather than
improvising: it prefers GitHub's native convert path, which preserves the
author, the thread, and an automatic cross-reference that a re-file cannot.

## Relationship to other rules

- [`issue-first`](issue-first.md) --- decides that something gets tracked before
  work begins; this fragment decides where it lands.
- [`report-mistakes-proactively`](report-mistakes-proactively.md) --- a noticed
  *mistake* is nearly always issue-shaped, since it names a concrete defect to
  fix.
  Its "Where to file" ladder is about which *repo*, orthogonal to this
  fragment's which *venue*.
- [`upstream-issues`](upstream-issues.md) --- already applies this judgment to
  external repos, whose own guidelines frequently route questions and feature
  requests to a board.
  This fragment says the same reasoning applies to repos we administrate, rather
  than being a courtesy owed only to strangers.
- [`migrate-discussion`](../../skills/migrate-discussion/SKILL.md) --- the
  after-the-fact correction.
  This fragment picks the venue before filing; that skill moves an item already
  in the wrong one, and owns the mechanics for both directions.
  Reach for it instead of hand-rolling a create-and-close, which loses
  provenance the native convert path keeps.

(Corrected 2026-07-29: a verdict-gating policy question was filed as
[`Morrison-Lab/gha#377`](https://github.com/Morrison-Lab/gha/issues/377),
justified by two `Decide whether/...` issues as precedent plus the board's
`totalCount: 0`.
The user's correction was "I want to start using the discussion board when it's
more appropriate than an issue;
precedent is not as important as best practice."
Moved to
[gha discussion #378](https://github.com/Morrison-Lab/gha/discussions/378),
in `Q&A` rather than `Ideas` so the decision can be marked as the answer.)
