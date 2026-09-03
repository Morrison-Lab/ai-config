---
name: triage
description: "Label every open issue P1/P2/P3; close junk."
user-invocable: true
allowed-tools:
  - Bash
---

# triage

Run the backlog triage pass from
[`triage-backlog`](../../shared/workflow/triage-backlog.md): every open
issue ends the pass carrying exactly one of `P1`, `P2`, `P3`, or closed.

## When this fires

- "triage the backlog", "triage issues", "/triage".
- The weekly triage routine.
- `gi` / `gii` / `gip` step 2 finds more than a handful of unlabelled open
  issues, which means the weekly pass was missed.

## Procedure

Commands are annotated with their abstract operation token; in a session
without `gh`, resolve through [`tool-mappings.md`](../../tool-mappings.md).
The instrument itself needs `gh` to fetch and apply; without it, fetch the
open issues through the mapped list tool into a JSON file and pass
`--input`, then perform the plan's operations through the mapped issue
write tool.

### 1. Build the plan

```sh
python3 scripts/triage-backlog.py -R <owner>/<repo> --json > /tmp/triage-plan.json   # LIST_ISSUES
python3 scripts/triage-backlog.py -R <owner>/<repo>
```

The stderr summary reports `examined N open issues` and the per-bucket
counts.
`N` must equal the repo's open-issue count; a smaller number means the fetch
was truncated.

### 2. Read the P1 and close lists in full

Read every proposed `P1`, `not-planned`, and `duplicate` row.
The heuristic keys on title phrases, so a discussion about a deadlock can
land at P1 and a defect phrased as a question can land at P3.
Collect corrections as `--override N=P` arguments.
Skim P2 and P3 for the same two mistakes; reading them in full is not
required.

### 3. Apply

```sh
python3 scripts/triage-backlog.py -R <owner>/<repo> --override N=P ... --apply --dry-run
python3 scripts/triage-backlog.py -R <owner>/<repo> --override N=P ... --apply   # EDIT_ISSUE, CLOSE_ISSUE
```

Adding a label the repo lacks creates it with GitHub's default colour.

### 4. Report

Post nothing to the tracker beyond the closes' own comments.
In chat, give the bucket counts, the examined count, every issue closed with
its one-line reason, and the P1 list, each number linked.

## Checklist

Do-Confirm, at the moment the `--apply` command is about to run:

1. Examined count equals the open-issue count.
2. Every P1 row was read, and each is a live block, not a discussion.
3. Every close row was read, and each is a junk title, an aphorism, or a
   duplicate of an older open issue.
4. Anything unlikely-but-actionable is P3, not closed.
5. The dry run printed the command set, and its count matches expectations.
