# opposition-research — mine a competitor’s community for demanded features

Study what a rival product’s **users** are asking for — not what the rival shipped — and turn the highest-demand, on-scope ideas into tracked issues in our repos. The signal is community demand: feature requests, upvoted wishes, and recurring “why can’t it do X” complaints across the competitor’s public community surfaces.

This is a demand-mining loop, not a copy job. The output is a ranked, evidence-backed list of features the community values, each mapped to one of our repos, plus (on the user’s go-ahead) the filed issues.

## When this fires

- User says `/oppo`, “opposition research”, “do oppo research on `<product>`”, “what features does `<product>`’s community want”, “mine `<product>`’s issues / subreddit / forum for ideas”, “what are users asking `<competitor>` for”, “competitor feature research”, “what do users wish `<product>` had”.
- After shipping a capability, when you want to know what adjacent features the market is already clamoring for.

## Inputs you need first

Pin two things before searching. If the user didn’t give them, infer from the current repo and confirm:

- **The competitor product** to research (the “opposition”).
- **Which of our repos** it competes with — the scope filter that decides whether a demanded feature is even relevant to us.

## Procedure

### 1. Pin the target and our angle

Write a one-line scope statement: *what the competitor is*, *which of our repo(s) it overlaps with*, and *what counts as on-scope* for us. Every idea is later kept or dropped against this line, so make it concrete.

### 2. Map the competitor’s community surfaces

Use `WebSearch` (3–5 queries from different angles) to find where the competitor’s users actually talk. Look for:

- **Issue trackers / discussions** — the competitor’s GitHub/GitLab issues and Discussions (sort by 👍 reactions; filter `label:enhancement` / `feature-request`).
- **Dedicated feature-request boards** — Canny, Featurebase, ProductBoard portals, UserVoice, the project’s own “ideas” board. These rank by vote count natively — the cleanest demand signal there is.
- **Subreddits** — sort *Top*; search the sub for “feature request”, “wish”, “missing”, “switch from”.
- **Q&A sites** — the Stack Overflow / Stack Exchange tag; most-voted questions mark the sharpest friction points.
- **Forums / chat** — Discourse instances, publicly archived Discord channels (read without login), mailing lists. Skip gated Discord/Slack that requires an invite or account to read.
- **Review sites** — G2, Capterra, Trustpilot, app-store and extension-marketplace reviews. The “cons” / “what do you dislike” sections name missing features directly.

### 3. Fan out research agents (parallel)

Spawn subagents (the `Agent` tool) — one per surface or small bucket of surfaces — so the reads run concurrently. Give each the same scope line from §1 plus this fixed reporting contract:

1.  **Surface** — which page/board/sub, and its URL.
2.  **Top demanded items** — the highest-signal feature requests found. For each: *what users want* (in your own words), *demand evidence* (upvotes / reactions / vote count / how many independent threads), and the *source link*.
3.  **On-scope?** — does this fall inside our repo’s scope (§1), or is it adjacent noise?

Prefer official read-only APIs over scraping (see Anti-patterns): the GitHub issues API sorted by reactions, the Reddit `.json` endpoints, the Stack Exchange API.

### 4. Keep only the community-valued, on-scope ideas

Drop two kinds of items:

- **Low-demand** — a single loud user with no upvotes or echoes is not “the community” (see §5).
- **Off-scope** — a real, popular request that has nothing to do with what our repo does.

Keep feature *requests* and the unmet needs behind *recurring* bug complaints. Skip the competitor’s ordinary bug backlog — that’s their defect list, not a demand signal for us.

### 5. Read the demand signal honestly

- **Vote/reaction counts are the primary signal.** A request with 300 upvotes outweighs ten scattered one-line mentions.
- **Recurrence across independent threads** beats a single high-score thread — it shows durable, broad demand.
- **Recent and rising** beats old and stale.
- **“+1” / “any update on this?” pile-ons** indicate sustained, unmet demand.
- Separate *“many users want X”* from *“one user’s edge case.”*

### 6. Dedupe, rank, and map to our repos

Merge the agents’ findings, collapse duplicate ideas, and rank by **demand ÷ effort** (best bang-for-buck first). For each survivor record:

- **Idea** — one line, in our own words.
- **Demand evidence** — the counts plus source link(s).
- **Our repo** — which of our repositories it would land in.
- **Do we already have it?** — search that repo’s open issues and existing features first, so you propose genuinely new work, not a duplicate.
- **Effort** — Low / Med / High.

### 7. Report, then file issues on the user’s go-ahead

Present the ranked list and ask which items to file — don’t open a flood of issues unprompted. For each greenlit idea, file a tracking issue in the right repo (issue-first; hand off to `st` / `defer-issue`). In the issue body, **link the source threads as demand evidence** and state the need in our own words. Restate it as our requirement; do not paste the competitor’s proprietary copy, screenshots, or roadmap text.

## Output format

1.  **Scope line** — competitor, our overlapping repo, what counts as on-scope.
2.  **Surface map** — short table: surface · what’s there · demand sample.
3.  **Ranked idea list** — as in §6, best-bang-for-buck first, with demand evidence and the target repo per row.
4.  **Recommended issues to file** — the shortlist you’d open, pending the user’s pick.

## Orchestration

Step 3 already fans out — one agent per community surface (issue tracker, feature board, subreddit, Q&A site, forum, review site), each blind to the others, and the work is web reading with no shared-runner cost. That is the workflow-shaped pattern in `shared/workflow/when-to-orchestrate.md`. When the surfaces are many or the ask says “thorough”, drive that fan-out through a Workflow: parallel finders by surface, then the dedupe-and-rank synthesis stage (step 6). Launch directly when an opt-in signal is present; otherwise propose with a cost estimate first.

## Custom agent for the per-surface fan-out

Step 3’s fan-out workers have no need for Edit, Write, or Bash access. Spawn the `community-demand-scout` custom agent (`.claude/agents/community-demand-scout.md`) for each surface instead of a general-purpose subagent, for a hard, harness-enforced guarantee that no worker can file an issue or commit on its own — rather than relying on this skill’s own instruction-only discipline. Dedupe, rank, and file issues (§6–7) in the main session afterward.

## Relationship to other skills

- **`scout-peers`** — the sibling, mirror image. `scout-peers` reads a competitor’s **code / repo** to borrow license-checked *implementations*; `opposition-research` reads its **users’ discourse** for *demanded features*, regardless of whether anyone built them yet. Run `oppo` to learn *what* to build, then `scout-peers` to learn *how* others built it.
- **`deep-research`** — the general multi-source, fact-checked web-research harness. `oppo` is the focused specialization: demand-mining a named competitor’s community to produce repo issues.
- **`st` / `gi` / `defer-issue`** — `oppo`’s output feeds these. Each greenlit idea becomes a tracked issue (issue-first), then gets picked up as normal work.
- **`memorize`** — when `oppo` identifies a competitor worth watching over time, record it so future runs start from a known target list.

## Anti-patterns

- ❌ Mining what the competitor *shipped* instead of what its users *want* — that’s `scout-peers`’ job, not this one.
- ❌ Treating one loud user as “the community.” Weigh by votes, reactions, and recurrence, not by how strongly a single thread is worded.
- ❌ Copying the competitor’s proprietary text, screenshots, or roadmap wording into our issues. Capture the *need* in our own words and link the source as evidence.
- ❌ Scraping gated/logged-in content or hammering a site’s rate limits. Use public pages and official APIs, read-only.
- ❌ Dumping raw complaints with no demand evidence and no mapping to a specific repo of ours.
- ❌ Filing a pile of issues unprompted. Rank, present, ask which to file, then file only those.

Back to top
