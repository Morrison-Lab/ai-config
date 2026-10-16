# Track every useful resource in every notes repo whose topic it covers

A notes repo is a course site in the sequence that [`course-sequence`](../writing/course-sequence.md) gives (mds, pds, sds, lds, ids, cds, rme, win and cie).
Track every useful resource (textbooks, articles, software packages, websites, videos, or any other format) in its primary home and in every notes repo whose topic it covers.
The primary home is the lds catalog that matches the resource's type (for example `courses.csv` or `channels.csv` under `chapters/data`), or, for a resource that no catalog fits, the Further reading section of the page in the notes repo whose topic is the resource's main subject, or of the closest lds page when no notes repo covers that subject.
The rule covers any content relevant to any Morrison-Lab repo, course or project, and the goal is to build comprehensive directories of content relevant to all our interests over time.
Each tracked resource is a small contribution to a directory, not a one-off link.

Ezra's first form of the rule, 2026-10-13, said to make sure a resource gets tracked in one or more of our repos.

## How

Track it immediately, in the turn where you find it, not at the end of the session: a resource noted "for later" is the one that gets lost.
Track resources through the notes repos, not a separate repo that only catalogs links (Ezra, 2026-10-13).
Besides the primary home, put the resource wherever else readers will look for it: a chapter's "Read" box, or the archive repo `mlr` for official copies of PDFs.

## Put it in every notes repo whose topic it covers

Ezra asked in a review comment on [lds#841](https://github.com/Morrison-Lab/lds/pull/841#discussion_r4288705723) whether some entries should go in one of the other repos (sds, mds, pds, rme, or another notes repo) "either instead of or in addition to here".
On 2026-10-15, in the project chat, he directed that the answer be a permanent policy rather than a one-off: track the resource in addition to its primary home, not instead of it.

Decide at tracking time, for each notes repo, whether the resource covers a topic that repo teaches, and track it in every repo where it does.
A catalog entry in lds (a course list, a channels table) does not substitute for a Further reading bullet on the page of any other notes repo that covers the same topic.

- Use the course sequence to find the candidate repos for a topic.
- The primary home entry is always made.
  In every other notes repo, put a resource with a topical scope (a course on multiple testing, a book chapter) in the Further reading section of the page it matches.
  Put a resource that spans topics (a channel) in that repo's catalog if it has one, and otherwise in the Further reading section of the page closest to the resource's scope.
- Respect each resource's license in each repo.
  When the resource is not adaptable (no license and not in the public domain, or a license that forbids derivatives), link to it and do not copy it.
  When its license allows adaptation, you may adapt it, with attribution, following its other terms (NonCommercial, ShareAlike) and each repo's own license.
  Where the resource's license and the repo's license conflict, link only.
- When you find that a tracked resource is missing from a notes repo whose topic it covers, add it to that repo.
  Open one PR per repo, and link each PR to the PRs in the other repos.
  A PR also links its tracking issue when one exists.

## Gaps

When a topic or a spinoff of an existing topic has no notes repo, create one for it rather than starting a link-only catalog repo.
If creating the repo does not fit the current PR, file an issue in lds that proposes it.
If adding the resource to an existing repo does not fit the current PR, open a small separate PR or an issue in that existing repo.

## Official sources

Link official sources only: the authors', publisher's or institution's own site, or an open-access host.
Never link an unauthorized copy, and never commit paywalled text.

## Do and don't

- **Do:** check that a resource you cite or find is tracked in its primary home and in every notes repo whose topic it covers, and add it (or file an issue) where it is not.
- **Do:** pass this rule to subagents that research or read course material.
- **Don't:** treat an entry in an lds catalog as covering the other notes repos whose topics the resource covers.
- **Don't:** leave a useful resource only in a chat reply or session transcript.
- **Don't:** link an unauthorized copy, or commit paywalled text.

See [`course-repos`](../../memories/course-repos.md) for how the course repositories divide material.
