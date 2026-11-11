# promote-memory — the review gate for staged learnings

Work through [`learn`](../../skills/learn/SKILL.llms.md)’s staging file (`learn-staging.md`) and decide, entry by entry, whether each candidate is durable enough to promote into committed memory. This is a single-pass review, not a multi-agent council — see “Why single-pass, not a critic panel” below for why that’s the right weight here.

## When this fires

- “promote memory”, “review staged learnings”, “clear out learn-staging”, “go through the staging file”
- Periodically, or as part of a `ums` pass, once `learn-staging.md` has accumulated entries since the last review
- When `learn-staging.md` is getting long enough that an unreviewed pile is itself a problem (nothing lost, but nothing promoted either)

## Why single-pass, not a critic panel

A five-critic-council review (independent votes on generality, staleness, redundancy, evidence, and format, then a majority/consensus call) is one way to run this gate, and is what some other agent-workflow setups use. For this repo’s scale — a single maintainer’s personal skill corpus, reviewed by the same agent that staged the entries in the first place — that’s more process than the problem needs: there’s no multi-party disagreement to adjudicate, and the criteria below are checkable in one pass without a panel to catch a single reviewer’s blind spot. This skill runs one pass through explicit, named criteria instead. Revisit this if the staging file starts accumulating contested entries a single pass keeps getting wrong — that would be the signal a heavier review is actually earning its cost.

## Procedure

### 1. Read the staging file

`~/.claude/projects/<project-slug>/memory/learn-staging.md`. If it’s empty or missing, say so and stop — nothing to promote.

### 2. Judge each entry against five criteria

For every staged entry, check:

- **Generality** — does this apply beyond the one session/task it came from, or was it a one-off that won’t recur? A fact tied to a since-closed PR’s specific state usually isn’t general; a tool quirk or a recurring pattern usually is.
- **Staleness** — is it still accurate right now? Something staged a while ago may have been fixed, superseded, or contradicted since — re-check before promoting, don’t just trust the timestamp.
- **Redundancy** — does an existing `CLAUDE.md`/`memories/*.md` entry already say this? Grep the likely destination file first. If it’s a near-duplicate, either skip it or fold in anything the existing entry lacks rather than adding a second copy.
- **Evidence** — is there a concrete example backing the claim (a command, a file:line, a quoted correction, a PR/issue reference)? A vague impression with no evidence is a hold, not a promote — go verify it before committing it as fact.
- **Format** — does it fit the destination file’s existing conventions (bullet not paragraph, right category, right section)? Reshape it to match on promotion; don’t paste the raw staged text in verbatim if the destination file has an established style.

### 3. Decide: promote, discard, or hold

- **Promote** — write it to the right destination, using [`record-learnings`’ own routing table](../../skills/record-learnings/SKILL.llms.md) (user-wide `/memories/`, repo-specific project memory, a shared skill, or `CLAUDE.md`) and its same conventions (check existing notes first, bullet form, the *why* not just the *what*, register a new `/memories/` file in `MEMORY.md`).
- **Discard** — remove the entry from `learn-staging.md`. Too narrow, contradicted, or already covered elsewhere. No need to explain a discard at length; one line is enough if a rationale is worth keeping at all.
- **Hold** — leave it in `learn-staging.md` for now (e.g. evidence is thin but the claim seems plausible and worth re-checking next time, or it needs a decision only the user can make). Don’t let holds accumulate silently forever — if the same entry survives several reviews unresolved, surface it explicitly and ask.

### 4. Clear resolved entries and report

Remove every entry that was promoted or discarded from `learn-staging.md`, leaving only holds. Report a short summary: how many promoted (and where), how many discarded (and why, briefly), how many held.

## Relationship to other skills

- **`learn`** — the staging half this skill reviews. See its own doc for why staging exists at all.
- **`record-learnings`** / **`memorize`** — this skill promotes into the same destinations and follows the same routing/format conventions `record-learnings` already documents; it doesn’t reinvent them.
- **`ums`** — a natural point to fold a `promote-memory` pass in, since both run periodically over accumulated session learnings. Running `promote-memory` doesn’t require `ums` though; it can run standalone whenever staging needs clearing.

## Anti-patterns

- ❌ Promoting an entry without checking for an existing near-duplicate first — that’s exactly the redundancy this gate exists to catch.
- ❌ Treating “it’s in staging” as evidence of durability on its own — the whole point of the gate is that staging doesn’t presume promotion.
- ❌ Letting holds pile up silently across many reviews instead of surfacing a repeatedly-held entry for a decision.
- ❌ Reaching for a multi-agent critic panel by default — see “Why single-pass” above; escalate only if single-pass reviews are demonstrably getting entries wrong.

Back to top
