# Track every useful resource in every notes repo whose topic it covers

Track every useful resource (textbooks, articles, software packages, websites, videos, or any other format) in its primary home and in every notes repo whose topic it covers.
The primary home is the repo or directory where the resource would live if only one place tracked it, such as the lds directories for courses, channels and programs.
A notes repo is a course site in the sequence that [`course-sequence`](../writing/course-sequence.md) gives (mds, pds, sds, lds, ids, cds, rme, win and cie).
The rule covers any content relevant to any Morrison-Lab repo, course or project, and the goal is to build comprehensive directories of content relevant to all our interests over time.
Each tracked resource is a small contribution to a directory, not a one-off link.

Ezra's first form of the rule, 2026-10-13, said to make sure a resource gets tracked in one or more of our repos.

## How

Track it immediately, in the turn where you find it, not at the end of the session: a resource noted "for later" is the one that gets lost.
Track resources through the notes repos, not a separate repo that only catalogs links (Ezra, 2026-10-13).
Put the resource where readers will find it: a chapter's Further reading or "Read" box, a channels table (lds `chapters/data/channels.csv`), or the archive repo `mlr` for official copies of PDFs.

## Put it in every notes repo whose topic it covers

Ezra asked in a review comment on [lds#841](https://github.com/Morrison-Lab/lds/pull/841#discussion_r4288705723) whether some entries should go in one of the other repos (sds, mds, pds, rme, or another notes repo) "either instead of or in addition to here".
On 2026-10-15, in the project chat, he directed that the answer be a permanent policy rather than a one-off: track the resource in addition to its primary home, not instead of it.

Decide at tracking time, for each notes repo, whether the resource covers a topic that repo teaches, and track it in every repo where it does.
A directory entry in lds (a course list, a channels table) does not substitute for a Further reading bullet on the page of any other notes repo that covers the same topic.

- Use the course sequence to find the candidate repos for a topic.
- Put a resource with a topical scope (a course on multiple testing, a book chapter) in the Further reading section of the page it matches, and a resource that spans topics (a channel, a whole textbook) in the repo's resource directory (such as the lds course list).
  Where a repo has no directory, put the resource in the Further reading section of the page closest to the resource's scope.
- Respect each resource's license in each repo.
  When the resource is not adaptable (no license, or a license that forbids derivatives), link to it and do not copy it.
  When its license allows adaptation, you may adapt it, with attribution, following its other terms (NonCommercial, ShareAlike) and each repo's own license.
  Where the resource's license and the repo's license conflict, link only.
- When you find that a tracked resource is missing from a notes repo whose topic it covers, add it to that repo.
  Open one PR per repo, and link each PR to the PRs in the other repos.
  A PR also links its tracking issue when one exists.

## Gaps

When a topic or a spinoff of an existing topic has no notes repo, create one for it rather than starting a link-only catalog repo.
Propose the new repo in an issue in the repo that holds the resource's primary home.
If adding the resource to an existing repo does not fit the current PR, open a small separate PR or an issue in that existing repo.

## Official sources

Link official sources only: the authors', publisher's or institution's own site, or an open-access host.
Never link an unauthorized copy, and never commit paywalled text.

## Do and don't

- **Do:** check that a resource you cite or find is tracked in every notes repo whose topic it covers, and add it (or file an issue) where it is not.
- **Do:** pass this rule to subagents that research or read course material.
- **Don't:** leave a useful resource only in a chat reply or session transcript.
- **Don't:** link an unauthorized copy, or commit paywalled text.

See [`course-repos`](../../memories/course-repos.md) for how the course repositories divide material.
