# tidy

Audit the codebase for opportunities to reduce complexity, duplication, and maintenance burden. Produce a **prioritized, actionable** list of suggestions — not vague advice.

## When this fires

- User says `/tidy`, “tidy up”, “DRY this”, “what can we remove”, “what can we outsource”, or similar.
- After a large feature lands and the user wants a cleanup pass.
- When reviewing a repo for the first time and looking for quick wins.

## Scope

If the user specifies a file, directory, or topic, restrict the audit to that scope. Otherwise, audit the full workspace.

## What to look for

Evaluate the codebase along these axes (in priority order):

### 1. Dead code & unused features

- Functions/modules/files never called or imported.
- Feature flags that are always on/off.
- Commented-out code blocks.

### 2. Outsource to external tools

- Hand-rolled logic that a well-maintained package/CLI already handles (e.g., custom YAML parsing → use a library; hand-rolled HTTP retry → use a retry library; custom linting rules → existing linter plugin).
- Vendored code that could be a dependency instead.
- Shell scripts reimplementing `jq`, `yq`, `sed` pipelines that a purpose-built tool does better.

### 3. DRY (Don’t Repeat Yourself)

- Duplicated logic across files that could be extracted into a shared helper/module.
- Copy-pasted config blocks that could be templated or parameterized.
- Repeated patterns that suggest a missing abstraction.

### 4. Simplify

- Over-engineered abstractions (more indirection than the problem warrants).
- Deeply nested conditionals that could be flattened with early returns or guard clauses.
- Complex shell pipelines that could be a single tool invocation.
- Overly defensive code for impossible states.

### 5. Reduce maintenance burden

- Pinned dependency versions that could use ranges.
- CI/CD steps that could be consolidated or parallelized.
- Documentation that duplicates what the code already says.
- Config files with stale/irrelevant entries.

## Output format

Present findings as a numbered list, grouped by axis, with:

1.  **What**: One-line description of the issue.
2.  **Where**: File(s) and line(s) affected.
3.  **Suggestion**: Concrete action to take (not “consider refactoring” — say exactly what to extract, replace, or delete).
4.  **Impact**: Low / Medium / High — how much maintenance burden it removes.
5.  **Effort**: Low / Medium / High — how much work the fix is.

Sort within each group by impact÷effort (best bang-for-buck first).

## What NOT to do

- Don’t make the changes yourself unless explicitly asked. This is an audit.
- Don’t suggest changes that alter public API or behavior without flagging the breaking-change risk.
- Don’t suggest “rewrite in language X” — stay within the current stack.
- Don’t flag style/formatting issues — that’s the linter’s job.
- Don’t suggest adding complexity (new abstractions, frameworks) unless it clearly nets out simpler.

## After the audit

Ask the user which items (if any) they’d like you to implement. Offer to: - Implement the top-N items in this session. - File issues for deferred items. - Skip items the user disagrees with.

## Relationship to other skills

- **`shared/workflow/challenge-unnecessary-complexity.md`** — the standing review-time counterpart to this skill’s axis 4 (“Simplify”). That fragment folds an unnecessary-complexity check into every normal review pass (including prose and math, not just code) and runs automatically, not on demand; run `/tidy` when you want a full prioritized audit across all 5 axes on demand, not just complexity.
- **`simplify`** — the narrow dead-code-removal counterpart, triggered after a refactor narrows invocation context, not an on-demand audit.

Back to top
