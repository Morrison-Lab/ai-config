# resolve-pr-threads

A narrow, standalone sweep: resolve inline review threads that are already settled, without running a full `ard`/`ardi` pass. Useful when threads were replied to in an earlier round but never resolved (a rebuttal the reviewer stopped re-raising, a fix that landed after the reply), or before re-requesting review so stale threads don’t clutter the new round.

This skill does **not** invent dispositions. The settlement rules — what counts as Address / Rebut / Defer / Acknowledge, and exactly when each is safe to resolve — are defined once, in [`ard`](../../skills/ard/SKILL.llms.md) step 4b. This skill only applies those existing rules to threads that already carry a reply.

## When this fires

- “resolve pr threads”, “clean up the threads”, “resolve stale threads”, “sweep the review threads”.
- At the start of a fresh `ardi` round, to resolve any rebuttal threads the latest review didn’t re-raise (already covered inline by `ard`, but callable standalone here too).
- Before re-requesting review, so the reviewer isn’t looking at threads that are already settled.

## Procedure

### 1. List every inline review thread

**GitHub** — pull threads with their resolution state and last reply (`READ_PR_REVIEW_COMMENTS` — abstract operation token; resolve to your model’s tool via [`tool-mappings.md`](../../tool-mappings.md)):

``` bash
gh api graphql -f query='query {
  repository(owner:"<owner>", name:"<repo>") {
    pullRequest(number:<N>) {
      reviewThreads(first:100) {
        totalCount
        nodes {
          id
          isResolved
          comments(last:5) { nodes { databaseId body author { login } } }
        }
      }
    }
  }
}'
```

If `totalCount` exceeds the returned node count, say so in the report instead of silently sweeping a partial list (same cap caveat as `pr-status`).

**GitLab**:

``` bash
glab api "projects/:id/merge_requests/<N>/discussions"
```

### 2. Classify each unresolved thread

For every thread where `isResolved` is false:

- **No reply yet from this side** (the last comment is the reviewer’s, with no Address/Rebut/Defer/Acknowledge response) — **leave it open**. This is a fresh finding; it needs an `ard` pass, not a resolve.
- **Replied, and settled per `ard`’s resolve-only-when-settled rules**:
  - Address — the reply names a commit SHA, and that SHA (or a later one) is on the branch.
  - Defer — the reply links a tracked issue.
  - Acknowledge — a reply exists at all.
  - Rebut — a reply with falsifiable evidence exists, **and** the reviewer’s most recent review round did not re-raise the same point.
  - -\> **resolve it**.
- **Replied, but not actually settled** (an Address whose fix isn’t pushed yet, a Rebut the reviewer just re-raised, an ambiguous partial fix awaiting reviewer confirmation) — **leave it open**.

Don’t resolve a thread that has no reply on it — that skips straight past `ard`’s dispositioning step, and the reviewer never sees a response.

### 3. Resolve the settled ones

**GitHub**:

``` bash
gh api graphql -f query='mutation {
  resolveReviewThread(input:{threadId:"<thread_node_id>"}) { thread { isResolved } } }'   # RESOLVE_REVIEW_THREAD
```

**GitLab**:

``` bash
glab api -X PUT "projects/:id/merge_requests/<N>/discussions/<discussion_id>?resolved=true"
```

In a remote/web session without `gh`/`glab`, use `mcp__github__resolve_review_thread` (see `tool-mappings.md`).

### 4. Report

State plainly, per thread: resolved (with the settlement reason) or left open (with why — no reply / fix not pushed / re-raised / needs confirmation). If any thread lacks a reply, note that a full `ard` pass is needed for those before they can be swept.

## Relationship to `ard` / `ardi`

`ard` step 4b already runs this exact sweep as part of every review round — this skill exists so the sweep is callable on its own, without re-running the whole Address/Rebut/Defer pass. The settlement criteria live in one place (`ard`); this skill and `ard` both point to it rather than each keeping a separate copy.

Back to top
