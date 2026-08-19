# Case records: run-ums-proactively

Worked-example case records for the rules in
[`run-ums-proactively.md`](run-ums-proactively.md), moved here verbatim to
keep them out of the auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## Stale records checker baseline and shallow clones

### Measured baseline (2026-08-16)

Measured against this repo on 2026-08-16:
503 files examined,
3 orphans (`commands/release-pr.md`, `memories/MEMORY.md`, `references/cloud-setup/README.md`),
181 generated wrappers and 2 root entry points exempt.
All three were inspected and are the benign kinds above,
so treat that as the baseline rather than as a backlog.

### Shallow clone behavior

The age bucket carries no information under a shallow clone,
which is what the checker's own output says (`age_informative: false` in `--json`).
`git log` cannot see past the fetch depth,
so every file reads as no older than the oldest fetched commit.
`actions/checkout` clones at depth 1,
so the CI step is advisory for that reason as well as for the orphan bucket's.
Re-run against a full clone (`git fetch --unshallow`) before reading it.
