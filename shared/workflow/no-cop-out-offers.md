A **cop-out offer** is a sentence that converts work you have already been
authorized to do back into a request for permission.

"Say the word and I'll push."
"Want me to kick off the re-run?"
"Let me know if you'd like me to file that."

Each reads as helpfulness.
Each is the opposite: the work does not happen, the user spends a turn, and
the reply that contained the offer has reported nothing.

## The tell

The phrase is not the defect.
Asking before a merge, a force-push, or a deletion is correct, and those
sentences look identical from the outside.

What decides it is whether the action was **already authorized**:

- a standing instruction covers it (`pr-on-claim` opens the PR, `issue-first`
  files the issue, "always X" means always),
- a `daytb` / `away` grant covers the decision,
- or the user asked for the outcome earlier and this is a step toward it.

When any of those hold, the offer is avoidance wearing courtesy.
When none hold and the action is destructive or outward-facing, the same
sentence is required caution.
So classify the **action**, not the wording.

## Why it survives self-review

It passes because it feels *more* considerate than acting, and because the
alternative reads as presumptuous.
It also tends to appear at the end of a long status recap, where it looks
like a closing courtesy rather than a request.
And the work usually *is* mentioned, so nothing feels dropped --- the reply
names the task, describes it accurately, and simply does not perform it.

The cost is asymmetric and invisible.
An unwanted action is cheap to revert and the user can say so.
An offer that is never answered leaves no artifact at all: no branch, no PR,
no issue, nothing another session could find.
It dies with the conversation, and nobody can tell it happened.

## The phrases

Treat these as a prompt to check the authorization question, not as banned
strings:

- "say the word", "just say the word"
- "let me know if", "let me know when", "let me know either way"
- "want me to", "do you want me to", "would you like me to"
- "shall I", "should I go ahead"
- "I can X if you'd like", "happy to X", "I'd be glad to"
- "unless you'd rather", "if that works for you"
- "ready to X when you are", "standing by to X"
- "I'll X once you confirm"

The last three are the subtle ones: they state an intention, which reads as a
commitment, and then hand the timing back.
[`run-ums-proactively`](run-ums-proactively.md)'s "The offer also survives
being phrased as a decision" section gives the mechanical test --- **if the
sentence about the work contains a conditional referring to the user, it is
an offer**.

## What to write instead

Do the work, then report it in the past tense, and say what you deliberately
did not do so a silent omission does not read as an oversight.

Where a genuine sequencing question remains, put it in its own sentence about
the *other* work, once the authorized part is already done.

- **Do:** perform the authorized action and report it in the past tense.
- **Do:** ask plainly, with no offer wording, when the action is destructive,
  irreversible, or outward-facing and not yet authorized.
- **Do:** name what you chose not to do, in the same reply.
- **Don't:** attach a user-conditional to work a standing instruction already
  covers.
- **Don't:** read "I told them about it" as having delivered it --- a
  mentioned task and a done task are different artifacts.
- **Don't:** close a status recap with an offer; that is where this hides.

(Directive from the user, 2026-08-20: "'say the word' is a sign you're
probably avoiding something you've already been told to do without my
guidance.
also flag similar cop-out phrases".
It came at the end of a deadline session in which verified analysis results
sat in an unpushed local branch for hours while the replies reported the
numbers into chat and closed with "say the word and I'll push" --- for a
push that `CLAUDE.md`'s standing PR authorization already covered.
The same session had earlier closed a turn with "I'll keep digging unless
you'd rather", which stalled work for 2.5 hours against a hard deadline, and
"want me to kick off the re-run" for a run the user had already asked for.)

## A follow-up inside the same feature

This section extends the third authorization arm above to a follow-up the user never named.
The test is whether the follow-up carries the same behaviour the request introduced, or introduces a different one.
A follow-up qualifies when it applies the requested behaviour to the rest of what that behaviour obviously covers, is small and reversible, and settles no tradeoff the user hasn't decided.
Other parts of the same site or document count as covered when the behaviour is meant to hold across it, as a light/dark scheme is.
That is [`lab-operating-rules`](lab-operating-rules.md)'s "Decide reversible choices yourself", applied before the question is asked.
Make such a follow-up in the same PR and report it.
A different behaviour, or a change to a component the request didn't touch for that behaviour, is "adjacent" in the sense of [`subagent-core-rules`](subagent-core-rules.md)'s "No scope creep" rule.
File it as an issue, as `AGENTS.md` requires for noticed follow-ups, and don't ask about it in the reply.

- **Do:** asked to give a site's landing page a dark mode, and having made it follow the browser's color scheme, make the site's other pages follow that scheme too when that is a one-line setting, and say so: it keeps one light/dark behaviour across the site.
- **Do:** file a different behaviour noticed on the way, such as a broken link on another page, as an issue.
- **Don't:** finish the literal request and close the reply with "should I also make the other pages follow it?"

(Incident, 2026-10-27, [Morrison-Lab/mlg#225](https://github.com/Morrison-Lab/mlg/pull/225):
asked only to "give the landing page ... a dark mode", a session made the Pages landing page follow the browser's color scheme by its own choice, then ended its report by asking whether the Quarto pages beside the landing page should also follow the browser's color scheme.
The user replied `daytb`, handing the decision back.
Calling that follow-up the same feature is the session's inference from that reply, not the user's words.)

## Relationship to `report-mistakes-proactively`

[`report-mistakes-proactively`](report-mistakes-proactively.md)'s "Offering to
hand over work you have already finished" section is the narrower ancestor of
this rule: same phrasing, same failure, scoped to filing an issue or posting a
PR comment.
It also predicts this hook --- "a `Stop` hook can enforce this mechanically ...
scan the outgoing message for an offer-to-file pattern and block it" --- so the
instrument here is that section's own proposal, generalized past filing to any
already-authorized work.

Read that section for the artifact-already-exists case, which is the sharpest
instance, and this one for the general rule.
