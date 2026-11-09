# Rationale: choose explicitly whether to centralize or distribute

The evidence and the decision aids behind the rule in [`centralize-or-distribute`](centralize-or-distribute.md) (Ezra, 2026-11-09, [ai-config#5185](https://github.com/Morrison-Lab/ai-config/issues/5185)).
The fragment's own text is authoritative.

## Why this is a rule

Copying is the path of least effort, so unexamined work distributes itself.
A survey of the 30 private Morrison-Lab repos with workflows on 2026-11-09 found 407 workflow files with the same names repeated across repos.
Of the 10 most duplicated names, 8 had more than one distinct content across the repos that carry them.
For example, `claude.yml` is in 14 repos with 14 distinct contents, and `claude-code-review.yml` is in 20 repos with 14.
Callers pinned `Morrison-Lab/gha` at both `@v2` and `@v3`, and a 253-line `check-secrets.yml` carried a full inline `secrets-detector-probe` job beside its `uses:` line.
The `rpkg-ci.def` and `epi204-ci.def` image recipes repeat the same apt library list, and every job fetches TinyTeX, Quarto and Pandoc from GitHub release URLs on its own.
The tracked follow-up is [Morrison-Lab/gha#1799](https://github.com/Morrison-Lab/gha/issues/1799).

## What to decide, and where

Decide at planning time (when you pick where the change goes) and again when performing it (when you are about to paste a second copy):

| Question | Centralize when | Distribute when |
| :--- | :--- | :--- |
| Will a change to it need to reach every user? | yes: one edit fixes all | each user needs its own value or timing |
| Do the copies have to stay identical? | yes | they are meant to diverge (per-repo settings, student-facing text) |
| Does the consumer pin a version? | a shared pin you control (`gha@v3`) | a pin per repo is the point (a repo that must not move) |
| Is the shared place reachable and owned? | yes, with an owner who will maintain it | no owner, or the shared place is a bottleneck or a single point of failure |

Typical homes, within a repo: a shared fragment, a helper script or one reusable step, instead of the same block pasted into several files.
Across repos: `Morrison-Lab/gha` for CI logic, `Morrison-Lab/ai-config` for agent rules, the notes repos' shared include for course content, one baked image for tooling several jobs install.

## Why prose and not a hook

I found no decidable condition for whether an author chose: a near-copy and a deliberate per-repo variant look the same in a diff, so a deny hook would have to guess intent from text.
That was a judgment from the cases in the survey above, not a test of every hook shape.
Where part of the question is mechanical, use a check instead: a `--check` drift flag on a generated copy, or a CI check that a caller file contains no job of its own (see [`prefer-systemic-solutions-over-one-off-fixes`](../principles/prefer-systemic-solutions-over-one-off-fixes.md) and [`algorithmatize-checks`](algorithmatize-checks.md)).
