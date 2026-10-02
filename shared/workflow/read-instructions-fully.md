# Read instructions fully: every word, the obvious implications, and the general principle

AGENTS.md's "Interpret instructions broadly" section sets the breadth of a reading.
This fragment covers three habits that keep a reading complete, each one a step another agent could watch you take or skip.

## Every word carries meaning

Keep each qualifier and hedge as a constraint on the task.
A hedge the user writes ("if convenient", "for now") is the user narrowing the request, which is the case the broad-reading default already exempts.
Read "etc." as the whole category the listed items share, not as the named items alone.

## Treat a correction as a general principle

Treat a correction as a general principle whenever plausible.
Apply it to the whole class of cases it belongs to, and file it per [`encode-reusable-feedback`](encode-reusable-feedback.md).

## Infer what a request plainly implies

A request carries the implications any careful colleague would act on without being told.
A request for a resource means giving its direct link, per [`link-forge-artifacts`](../writing/link-forge-artifacts.md).
A correction applies every time the situation recurs, not only on the occasion it named.

When the user adds a clarification in parentheses, or as a second message right after the first, it names an inference you were expected to make unprompted.
If the clarification was not already obvious to you, take it as a correction: a missed inference, not new information.
Act on it, and record the general lesson as [the correction section above](#treat-a-correction-as-a-general-principle) describes.

- **Do:** act on a request's plain implications unprompted, such as linking the resource it asks for.
- **Do:** when the user has to add a clarification, fix the case and record the general inference you missed.
- **Don't:** confine a correction to the case it mentioned, or drop a qualifier or "etc." when restating a request.
- **Don't:** wait for the user to spell out what a request plainly implies.

(Directives from the user, 2026-10-02: "assume that nothing I write is filler";
after having to add "(that is, give me the link)" and "(always)" to a request for a referee report: "something I write to you parenthetically should be obvious to you", and "take it as a correction if it's not obvious".)
