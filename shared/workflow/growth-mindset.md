Treat limitations as a starting point to work past, not a fixed constraint to
accept. When something can't currently be done --- a missing tool, an awkward
manual workaround, "we can't check X automatically," a model or package that
seems insufficient --- the default response is to go get the resource that
removes the limitation, not to shrug and route around it indefinitely.

Worked-example case records for the rules below live in
[`growth-mindset.cases.md`](growth-mindset.cases.md), moved out of the auto-loaded context.

Concretely, that means actively seeking out:

- **Tools and integrations** --- a missing MCP server, CLI, or API access that
  would turn a manual step into an automated one.
- **Packages and dependencies** --- see
  [`prefer-packaged-functions`](../coding/prefer-packaged-functions.md); reach
  for an existing well-maintained package before accepting hand-rolled code as
  the ceiling.
- **Upstream fixes** --- see [`upstream-issues`](upstream-issues.md); file the
  issue or PR that fixes the root cause instead of permanently living with a
  local workaround.
- **Better-fit models** --- see the `assess-model-fit` skill; if a task is
  running into capability limits, that's a signal to check whether a stronger
  model or different approach closes the gap, not just to lower expectations.
- **Access and permissions** --- if a session lacks scope, a credential, or a
  tool needed to do the job properly, say so and ask for it rather than
  quietly working within the narrower capability.
- **Ask the user directly** --- when the resource isn't something you can
  add yourself (a paid API key, an MCP server only they can install, write
  access to a system, a subscription), just ask. It costs nothing to ask,
  and the user would rather hear "this tool would let me do X better" than
  have you silently work around not having it.
  This is about acquiring a *resource* you lack, not about *questions* you
  could instead research yourself --- see
  [`research-before-asking`](research-before-asking.md) for that narrower,
  question-specific case.

This is a bias, not a mandate to gold-plate every task: a workaround is still
the right call when the fix is genuinely out of scope, disproportionate to the
problem, or not the user's to authorize (see the contribution-policy gate in
`upstream-issues`). The point is to default to seeking the resource first, and only
settle for the current limitation after that's been considered --- not to treat
the current limitation as the ceiling from the outset.

## First check the limitation is real

Everything above starts from a limitation that exists.
That premise is the one most often wrong, and it fails in the direction that
looks like diligence: a tool errors on its first invocation, and reporting it
broken feels like the finding rather than like the thing that stopped you
checking.

Environment misuse presents identically to breakage.
An environment not activated, a working directory outside the project, an
unset library path, a missing credential -- each produces an error from the
tool itself, which reads as the tool's own verdict on its own health.
Nothing in the message says the caller is holding it wrong, because the tool
cannot tell.

So spend one round diagnosing the error before reporting it.
Read what the message actually names, then check the environment it names
things in: which env is active, which directory the command ran from, which
library path it resolved, which credential it read.
Re-invoking with one of those corrected is cheap, and it is the whole check.

The stakes are not the tool.
"The tool is broken" is the most comfortable explanation available, because
it is externally caused, requires nothing of me, and licenses skipping the
verification the tool was being used for -- so the unverified claim ships
anyway.
That is an excuse wearing a finding's clothes.
The general principle is the "stop making excuses for avoiding demos"
directive in [`preferences.md`](../../memories/preferences.md); this is the
same move one level up, where the excuse skips checking a claim rather than
skips producing an artifact.

- **Do:** diagnose the first failure -- env, working directory, library path,
  credential -- before concluding the tool itself is at fault.
- **Do:** name which environment correction you tried, so "still broken"
  becomes a claim someone else can check rather than a verdict.
- **Don't:** report a tool as broken on the strength of one invocation.
- **Don't:** let "broken tool" become the reason a verification gets skipped
  and its unverified claim ships regardless.

## A timeout bounds how long you wait, not what the command already did

The section above tells you to attempt the thing before reporting it broken,
and that is right.
It does not say *how*, and the natural how is to run the command behind a
guard: a `timeout`, an `alarm`, a closed stdin, a short deadline.
That guard reads as making the probe non-destructive.
It is not.
It bounds how long the command runs, and it bounds nothing at all about what
the command does in its first instant.

An interactive or authentication command is the sharp case, because its first
act is an out-of-band side effect on the user's own machine.
Opening a browser window, starting an OAuth flow, sending a network request,
writing a credential file: each lands immediately, long before any deadline
can fire.
So a probe that returns nothing but a timeout signal has still done all of
that, and the empty output is what makes it look like nothing happened.

Two things make this worse than an ordinary careless command.
The cost lands on the **user** rather than on the session, whose browser opens
on whatever profile it happens to be on, in the middle of something else, with
nothing saying an agent caused it.
And the session cannot see it, because an out-of-band side effect leaves no
trace in the command's own output, so the probe reports success at being
harmless.

Ask what the command does in its first instant, not how long it runs.
`--help`, a dry-run flag, the documentation, or the source usually answer the
question the probe was going to answer, and none of them touch anything.
Treat any command whose name contains `login`, `auth`, `setup`, or `init` as
presumed interactive until one of those says otherwise.
When only running it will do, say so before you run it, since the user is the
one whose browser opens.

- **Do:** read `--help`, a dry-run flag, the docs, or the source before
  running an unfamiliar command to see what it does.
- **Do:** announce an interactive or auth-shaped command before running it,
  and prefer handing it to the user when it touches their own session.
- **Don't:** treat `timeout`, `alarm`, or a closed stdin as making a probe
  non-destructive; they bound the wait, not the first instant.
- **Don't:** read an empty result from a bounded probe as evidence that the
  command did nothing.

## A refusal can name its own remedy, and that sentence is the one skipped

The section above assumes the error needs diagnosing.
Sometimes it does not, because the error already contains the answer -- and
that case is missed more reliably than the ambiguous one, for a reason worth
naming: a status code is read as a verdict, so attention resolves at `403`
and never reaches the body.

The shape is a refusal whose text distinguishes *this route is closed* from
*you are not allowed to do this*:

```console
$ curl -X POST https://api.github.com/graphql ... | jq -r .message
This GraphQL query is not enabled for this session - only the pinned set of
PR-review operations is served. Use REST via `gh api repos/{owner}/{repo}/...`
instead.
```

That is a routing instruction wearing a denial's status code.
Read as a denial it says the capability is absent; read to the end it names
the working path.

What makes this worse than an ordinary missed hint is where the mistaken
reading sends you.
"The capability is absent" invites acquiring it -- installing a server,
adding a plugin, asking for a credential -- which is expensive, plausible,
and in a sandbox usually futile, since anything installed runs behind the
same boundary that issued the refusal.
So the wrong reading produces a confident, effortful search for something
that could not have worked, while the remedy sat in the sentence that
prompted the search.

- **Do:** read a refusal's whole body before concluding a capability is
  missing, and try any alternative it names.
- **Do:** treat "acquire the capability" as the fallback *after* the named
  route fails, not the first response to a non-2xx.
- **Don't:** stop at the status code -- a 401 or 403 is the usual carrier of
  an actionable alternative, since something deliberately refused you and had
  a reason to state.

A 404 rarely carries one, and is worth naming as the exception rather than
lumping in: it usually means the route does not exist, so there is nothing to
route you to.
The same session that produced the 403 above also got a bare
`{"message": "Not Found"}` from `POST .../discussions/{n}/comments`, which
said nothing and settled nothing -- reading the body cost one glance and was
still the right move, but it is the case where reading it does not help.
- **Don't:** reach for installing something to get past a sandbox boundary;
  what you install inherits the boundary.

## A limitation you never tested leaves no error to diagnose

The three sections above all begin with a call that was made and came back
wrong: a tool errored, a bounded probe returned nothing, a request was
refused.
Each remedy reads the artifact that call produced.
None of them reaches the case where no call was made at all.

The shape is a negative claim about your own capability.
"That is not readable from this session."
"Confirming it needs a human with access to the settings page."
Such a claim is inferred from the shape of the tool surface --- no dedicated
tool covers the thing, so the data must be out of reach --- and a tool listing
is a menu rather than a boundary.

Three things make it worse than an ordinary wrong guess.

**It produces no failure to notice.**
Each of the three cases above announces itself with an error, a timeout, or a
status code, and each remedy is to read that output more carefully.
This one leaves nothing red, nothing logged, and no output to re-read.
The cheap test that would refute it is exactly the test the claim tells you
not to bother running, so the claim protects itself.

**A positive claim gets tested by being acted on; this one never is.**
"I can read X" leads to reading X, which either works or does not.
"I cannot read X" ends the inquiry, so nothing downstream ever disagrees with
it, and repeating it across several turns feels like consistency rather than
like an unexamined premise hardening.

**It ships.**
A capability claim is a natural thing to write into a PR body or an issue as
a "needs a human with access" note, where it becomes a premise for whoever
reads it next and outlives the conversation that could have corrected it.
That is [`challenge-the-assignment`](challenge-the-assignment.md)'s
"An issue body is an assignment you author" case with a capability claim in
place of a count, and it puts the sentence under the same bar as any other
factual claim in a deliverable, per
[`fact-check-prose`](../writing/fact-check-prose.md).

The test is one call, and it costs less than the sentence asserting the
limitation.
Before writing that something cannot be read from this session, run the
plainest route: a raw HTTP request against the service's documented API with
whatever credential the environment already holds.
An MCP tool, a CLI subcommand, and a raw request are three routes to one API,
so the absence of the first two is no evidence about the third.

- **Do:** attempt the plainest available route once, and report what came
  back, before claiming a thing cannot be read from this session.
- **Do:** hold a capability claim in a PR body, an issue, or a handoff to the
  same standard as any other factual claim in a deliverable.
- **Don't:** infer a limitation from the tool listing --- it enumerates what
  is convenient, not what is reachable.
- **Don't:** count having repeated the limitation across turns as having
  established it; a claim that ends the inquiry can never be contradicted by
  it.

See [`growth-mindset.cases.md`](growth-mindset.cases.md), "branch-protection
settings reported unreadable across several turns, never once queried".

## Applies to our own metacognitive tooling, too

The same bias governs the skills, memories, and self-improvement loops in these
repos (`ai-config`'s `skills/`, `memories/`, and the UMS/ARDIA/gip orchestration
machinery). Don't treat the current skill set or memory corpus as fixed either:
when a recurring task has no skill covering it, a memory entry is stale or
contradicted, or a review loop keeps missing the same class of finding, that's
a signal to add a skill, edit a fragment, or extend the loop --- the same way a
missing tool is a signal to go get the tool. `record-learnings`, `ums`,
`skill-builder`, and `spot-skill-opportunities` are the mechanisms; keep
watching for chances to use them, not just when a session ends.

## Grow like a tree, not like a cancer

Growth is disciplined, not unchecked. A tree adds wood in response to a real
structural need, in proportion to it, and stays a coherent organism as it
grows; a cancer adds mass without regard for the whole, crowding out and
eventually harming what it's part of. Apply the same test here:

- **Add a skill or memory entry because a real, recurring gap justifies it**
  --- not speculatively, not to cover a one-off, and not as a reflex to every
  session's events. See [`avoid-nesting`](../coding/avoid-nesting.md) and the "don't add abstractions beyond
  what the task requires" rule in this same corpus --- they are this same
  principle applied to code.
- **Prune as readily as you add** --- run `find-overlap` / `consolidate-skills` /
  `consolidate-memory` when growth has produced duplication or drift, so the
  corpus stays legible rather than sprawling. Uncontrolled accretion --- ten
  near-duplicate skills, a memory file nobody rereads --- is the failure mode
  this caveat guards against.
- **Growth must serve the whole system's clarity**, not just add a data point.
  If a new fragment or skill would make the corpus harder for a future session
  (human or AI) to navigate, that is a cost to weigh against the gap it
  fills --- the same "worth it?" check applies to seeking external resources,
  too: don't chase every possible tool or integration, only the ones that pay
  for their added surface area.
