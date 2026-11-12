# Read instructions fully: every word and the obvious implications

The "Interpret instructions broadly and maximize safe progress" bullet of AGENTS.md's "Act on the whole request, and decide rather than ask" section sets the breadth of a reading.
This fragment covers two habits that keep a reading complete, each one a step another agent could watch you take or skip.

## Every word carries meaning

Keep each qualifier and hedge as a constraint on the task.
A hedge the user writes ("if convenient", "for now") is the user narrowing the request, which is the case the broad-reading default already exempts.

Read "etc." as the whole category the listed items share, not as the named items alone.

## Infer what a request plainly implies

A request carries the implications any careful colleague would act on without being told.
A request for a resource means giving its direct link (compare [`link-forge-artifacts`](../writing/link-forge-artifacts.md), which covers every item you name).

When the user adds a clarification in parentheses, or as a second message right after the first, it names an inference you were expected to make unprompted.
If the clarification was not already obvious to you, take it as a correction: a missed inference, not new information.
Act on the clarification, and record the general lesson per [`encode-reusable-feedback`](encode-reusable-feedback.md), as for any other correction.

- **Do:** act on a request's plain implications unprompted, such as linking the resource it asks for.
- **Do:** when the user has to add a clarification, fix the case and record the general inference you missed.
- **Don't:** confine a correction to the case it mentioned, or drop a qualifier or "etc." when restating a request.
- **Don't:** ask whether to do what a request plainly implies ("want the link?") instead of doing it.
  A whether-or-how question is not a request; it gets a start-or-file ask ([`start-or-file`](start-or-file.md)).

Read broadly as well as fully: unless the user narrows a request, take the reading that advances its obvious objective (`AGENTS.md`'s "Interpret instructions broadly and maximize safe progress").
Do not reduce an instruction to the smallest literal action when its context makes a larger in-scope outcome clear.
Apply grants and rules at the breadth stated, without adding unstated conditions, exceptions or restrictions.

- **Do:** inspect for adjacent actionable work, resolve it, verify it, and carry it through the normal PR, review, and monitoring lifecycle.
- **Don't:** stop at a narrow literal reading that leaves the requested outcome only partially achieved.

(Directives from the user, 2026-10-02: "assume that nothing I write is filler";
after having to add "(that is, give me the link)" and "(always)" to a request for a referee report: "something I write to you parenthetically should be obvious to you", and "take it as a correction if it's not obvious".)
