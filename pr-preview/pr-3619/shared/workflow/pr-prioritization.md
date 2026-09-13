When picking which PR or issue to work on next — choosing among several open
PRs to review, iterate (ARDI), or pick up first in a queue, or triaging which
open issue to grab next (`gi`/`gii`/`gip`) — slightly prefer **internal
infrastructure work** over **feature work**, all else equal.

Infrastructure work changes shared tooling other work depends on: CI
workflows, reusable actions, templates, lint/CI config, dev scripts, or
this `ai-config` corpus itself. Feature work adds or changes user-facing
behavior in a product repo. Infrastructure work unblocks everything built on
top of it, so a small lead in priority pays off across every PR or issue that
follows — whether the candidates are open PRs to iterate or open issues to
grab.

This is a **tie-breaker**, not an override: explicit priority labels,
blocking relationships, age, and size still rank above it. Apply it only when
two candidates are otherwise close — don't reorder a queue around it when a
feature PR or issue is clearly more urgent (a labeled `P0`, something
blocking other work, or something the user flagged directly).

**Default to the older PR.** When managing several open PRs at once — a review
queue, an `ardia` sweep, or just picking which to take up next — prefer the
**older** PR over the newer one by default, unless you have more specific
instructions. An older PR has waited longest and drifts further from `main`,
so clearing it first keeps the queue moving. This default
outranks the infrastructure tie-breaker above, but still yields to a more
specific signal: an explicit priority label, a blocking relationship, a PR the
user flagged, or a direct instruction to take a particular one first.
