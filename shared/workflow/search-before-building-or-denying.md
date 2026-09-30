# Search the tracker and AGENTS.md before building or denying a policy

Before answering that a permission or policy does not exist,
and before implementing a new policy or capability,
search the full policy corpus and the issue tracker.

## Why checking skills or memories alone is insufficient

`AGENTS.md` is the universal, cross-agent contract across all repositories.
Many global and cross-repository policies ---
such as standing merge grants, worktree isolation rules,
and delivery conventions ---
are codified directly in `AGENTS.md` rather than duplicated
in individual skill files or local memory notes.

Searching only `skills/` or `memories/` leaves `AGENTS.md` unread.
An agent that searches only those subsets will claim that a policy does not exist,
falsely denying a permission that the user already established.

Similarly, jump-starting implementation immediately upon receiving a prompt
without checking the issue tracker risks duplicating existing open work.
An existing issue or PR may already define the architectural approach,
specify required allowlists,
or record hard-won constraints.
Implementing without searching the tracker causes redundant PRs,
divergent implementations,
and narrowed scopes that contradict earlier decisions.

## Grounding: The 2026-09-28 infra-PR standing grant incident

In a cloud session on `Morrison-Lab/pds` (Issue #4092),
two interrelated failures occurred:

1. **Denied an existing policy:**
   The user asked: "don't you have standing permission to mwc infra PRs?"
   The agent searched `skills/mwc/SKILL.md`, `memories/`, `shared/`, and `skills/`,
   found only the repository-level `ai-config` grant,
   and told the user no such grant existed.
   However, `AGENTS.md`'s Strict Merge Control Policy already stated:
   "Infrastructure PRs carry a standing `mwc` grant,
   in every repo the user can push to".
   Because the agent omitted `AGENTS.md` from its search,
   it denied an established standing grant.
2. **Built without searching the tracker:**
   The user then asked to "create a standing infra-PR mwc grant in ai-config".
   The agent implemented and merged PR #4085 without searching the issue tracker.
   Issue #4039 ("Teach no-unauthorized-merge.py the standing mwc grant
   for infrastructure PRs") was already open,
   containing an established proposal and allowlist from the user.
   PR #4085 duplicated the work and ended up narrower than both the policy
   and the allowlist the user had already approved.
3. **Prompted for settled decisions from scratch:**
   The user was asked to choose a scope for the grant
   ("Tooling + agent config" vs "All Morrison-Lab repos")
   without being shown that they had already defined a broader scope
   in the earlier directive.

## The Search Checklist

Whenever evaluating permissions or starting capability work:

1. **When asked if a permission, grant, or policy exists:**
   Search the entire policy corpus before answering "no":
   - `AGENTS.md` (the primary universal contract)
   - `CLAUDE.md` and repository-level orientation guides
   - `memories/` (cross-workspace and harness preferences)
   - `shared/` (shared workflow guides, principles, and writing standards)
   - Open tracker issues and discussions
2. **When asked to create, add, or adjust a capability or policy:**
   Always run an issue tracker search first (per [`issue-first`](issue-first.md)),
   raising `--limit` well past plausible match counts
   so closed issues do not crowd out open ones:
   ```bash
   gh issue list --state all --limit 300 --search "<keywords>"
   ```
   If the returned count equals the limit,
   raise `--limit` again until the result is uncapped.
   Check if an open issue or PR already tracks the request,
   articulates technical requirements,
   or provides an existing allowlist.
3. **When presenting architectural or scope options:**
   If a prior directive or tracked issue already addressed the design,
   quote the existing directive and ask whether it still stands,
   rather than presenting the decision as an ungrounded blank slate.

## Do / Don't Checklist

- **Do:** search `AGENTS.md`, `CLAUDE.md`, `memories/`, `shared/`,
  and open issues before answering "no" to whether a policy or permission exists.
- **Do:** run an all-state tracker search before implementing a capability request,
  even when the user's prompt is explicit and fresh.
- **Do:** check whether an open issue or PR already established architecture,
  allowlists, or acceptance criteria.
- **Don't:** assert that a standing grant or rule does not exist
  based only on searching `skills/` or `memories/`.
- **Don't:** implement a new policy or script without checking
  whether an active issue already specifies the intended scope.
- **Don't:** ask the user to choose a design when an existing directive
  already covers it; show them the directive and ask whether it still stands.
