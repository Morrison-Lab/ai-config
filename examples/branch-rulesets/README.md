# Example branch rulesets

These are draft GitHub repository-ruleset payloads (the body of a `POST
/repos/{owner}/{repo}/rulesets` call) for the lab's repositories. They did
not exist anywhere in the org before this PR -- a search of `ai-config` and
a read of its tree turned up no `rulesets/` or `examples/` directory
carrying one, so this PR is what creates the canonical example set rather
than restoring one that was exported earlier.

## What every draft does

- `base.json` is the shared shape: on the default branch, block
  `deletion` and `non_fast_forward` (no force-push, no branch deletion)
  for **everyone**, including admins (`bypass_actors: []`), and require a
  pull request before merging.
- The `pull_request` rule's `required_approving_review_count` is `0`.
  Agents in this org merge through PRs (never a direct push to the
  default branch) but don't necessarily wait on a formal GitHub approval
  before an `mwc`-style merge, so the ruleset enforces "came in through a
  PR" without also enforcing "was approved", which would block the
  standing merge grants recorded in team memory.
- No `required_status_checks` rule is included anywhere in this PR.
  `ai-config`'s own `hooks/no-underived-required-check.py` warns for good
  reason: a required-check context is matched against a check-run name by
  exact string, and a wrong or renamed one sits as `Expected` forever and
  silently blocks every future merge. Confirm each repo's actual
  check-run names (a merged PR's checks, read from the Checks API) before
  adding this rule by hand.

## Per-repo notes

- `mln.json` -- deliberately carries **no** required-status-checks rule,
  matching the standing decision in `Morrison-Lab/mln#75` that this repo
  has no required CI checks.
- `mlg.json`, `mlr.json`, `gha.json`, `ai-config.json`, `islp.json`,
  `islp_labs.json` -- all use the shared `base.json` shape unmodified.
  None of these had their live ruleset read before drafting this file
  (repo-settings reads/writes are constrained for this session -- see
  team memory `repo-settings-writes-blocked-at-the-proxy`), so treat each
  as a proposal to reconcile against whatever that repo's ruleset
  actually holds today, not as a diff.

## Repos not covered here

`mds`, `pds`, `sds`, `psw`, `epi202`, `epi203`, and `araomm` are in the
requested scope but outside this GitHub session's configured repository
list, so they could not be read or drafted for in this pass. A follow-up
pass (with those repos added to scope, or run from a session that already
has them) still needs to check and, where missing, add a matching
ruleset.

## Applying a draft

Repository-settings writes (which is what creating a ruleset is) are
blocked from this cloud session's network path. Apply from an
authenticated local `gh` session instead:

```bash
gh api --method POST /repos/<owner>/<repo>/rulesets \
  --input examples/branch-rulesets/<repo>.json
```

To update an existing ruleset instead of creating a duplicate, first list
the repo's rulesets (`gh api /repos/<owner>/<repo>/rulesets`), find the
matching `id`, and `PUT` to `/repos/<owner>/<repo>/rulesets/<id>` with the
same body.

`~DEFAULT_BRANCH` in `conditions.ref_name.include` is a real GitHub
ruleset special value -- it resolves to whatever the repo's actual default
branch is, so the same JSON works whether that branch is named `main` or
something else.
