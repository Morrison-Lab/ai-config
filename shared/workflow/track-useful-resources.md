# Track every useful resource in every repo it fits

Ezra, 2026-10-13: any time you or any of your agents comes across a useful resource (textbooks, articles, software packages, websites, videos, or any other format), always make sure it gets tracked in every one of our repos whose topic it covers, in addition to its primary home.
The rule covers any content relevant to any Morrison-Lab repo, course or project, and the goal is to build comprehensive directories of content relevant to all our interests over time.
Each tracked resource is a small contribution to a directory, not a one-off link.

## How

Track it immediately, in the turn where you find it, not at the end of the session: a resource noted "for later" is the one that gets lost.
Track resources through the notes repos, not a separate repo that only catalogs links (Ezra, 2026-10-13).
Put the resource where readers will find it: a chapter's Further reading or "Read" box, a channels table (lds `chapters/data/channels.csv`), or the archive repo `mlr` for official copies of PDFs.

## Put it in every repo whose topic it covers

Ezra, 2026-10-15 (review comment on lds#841, "should some of these entries go in one of the other repos (sds, mds, pds, rme, etc) either instead of or in addition to here?"): the answer is a permanent policy, not a one-off.
Decide at tracking time, for each notes repo, whether the resource covers a topic that repo teaches, and track it in every repo where it does, in addition to its primary home.
A directory entry in lds (a course list, a channels table) does not substitute for a Further reading bullet on the sds, mds, pds or rme page that covers the same topic.

- Use the course sequence ([`course-sequence`](../writing/course-sequence.md)) to find the candidates: a statistics course or lecture belongs in sds (and rme when it is about model inference), a probability resource in pds, a programming or math resource in mds, and a prediction resource in lds.
- Put a topical resource in the Further reading section of the page it matches, and a general one (a whole course, a channel) in the repo's directory.
- Respect each resource's license in each repo: link only when it is not adaptable (no license, or a NoDerivatives license), and adapt with attribution only when it is (CC BY and similar).
- When an existing tracked resource sits in only one repo, open a small PR in each of the others at once if the addition is small.
Otherwise, file an issue in each repo.
- Open one PR per repo, each linking to its own issue and to the PRs in the other repos.

## Where else the rule applies

When a topic or a spinoff of an existing topic has no notes repo, create one for it rather than starting a link-only catalog repo.
If the resource does not fit the current PR, open a small separate PR or an issue for the resource.
Link official sources only: the authors', publisher's or institution's own site, or an open-access host.
Never link an unauthorized copy, and never commit paywalled text.

- **Do:** check that a resource you cite or find is already tracked, and add it (or file an issue) when it is not.
- **Do:** pass this rule to subagents that research or read course material.
- **Don't:** leave a useful resource only in a chat reply or session transcript.
- **Don't:** link an unauthorized copy, or commit paywalled text.

See [`course-repos`](../../memories/course-repos.md) for how the course repositories divide material.
