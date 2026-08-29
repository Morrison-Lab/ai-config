---
name: scout-peers
description: "Survey peer repos for patterns."
user-invocable: true
allowed-tools:
  - WebSearch
  - WebFetch
  - Agent
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# scout-peers

Find the public repos most comparable to **this** project, determine whether
any one of them is *uniformly superior* (does everything this repo does, but
better), and otherwise harvest their best ideas — adapting each one into this
repo **only after** clearing its license and recording attribution.

This is a research-and-adapt loop, not a blind copy. The output is a ranked,
license-checked, attributed list of borrowable ideas plus (on the user's
go-ahead) the implementations.

## When this fires

- User says `/scout-peers`, "are there other repos like this", "scan similar
  projects", "borrow ideas from comparable repos", "competitive scan", "what
  can we learn from peer projects", "how do others solve this".
- After building something with an established category of prior art, when you
  want to sanity-check the design against the field.

## Procedure

### 1. Characterize this repo

Read the local repo enough to write a tight one-paragraph "reference profile":
what it is, its structure (top-level dirs), its distinctive features, and its
intended use. This profile is what every comparison is measured against, so be
specific about the things that make this repo *itself* (its workflows, its
data model, its niche) — not just generic category membership. Write it once;
hand the same profile to every research agent so verdicts are comparable.

### 2. Find the peer set

**Skip this step when the task already names one repo.** A "study
`<owner>/<repo>`" issue supplies the peer set, so there is nothing to search
for; go straight to §3 and run §4 through §7 unchanged.
Searching anyway produces a survey nobody asked for and buries the named repo
among peers.
The rest of the loop does not depend on the set having more than one member ---
§5's uniformly-superior question and §6's ranked borrow list both work on one.

Use `WebSearch` (2–4 queries from different angles — by category, by
"awesome-X list", by the repo's distinctive feature) to assemble a candidate
list. Pull in curated "awesome" lists too: they surface peers a direct search
misses. Dedupe into a flat list of repo URLs, then bucket them:

- **Closest analogs** — same shape and purpose. These get the deepest look.
- **Adjacent / larger** — same category, different emphasis (e.g. a broad
  marketplace vs. a personal config). Mine for *structural/tooling* ideas.
- **Directories / lists** — not configs themselves; mine for *pointers* to
  notable individual projects and for organization conventions.

### 3. Fan out research agents (parallel)

Spawn subagents (the `Agent` tool) — one per small bucket of 1–4 repos — so the reads
run concurrently. Give every agent the **same reference profile** plus this
fixed reporting contract:

1. **What it is** — one paragraph on structure & purpose.
2. **License** — exact license, and whether it permits reuse-with-attribution.
   The agent MUST fetch the actual license file (see §4), not guess. If none is
   found: `NO LICENSE FOUND — reuse not permitted by default.`
3. **Borrowable ideas** — concrete, specific features/patterns this repo lacks
   that would improve it. Each: *what it is*, *why it's good*, *adoption
   difficulty (Low/Med/High)*. Demand specificity ("a `/heal-skill` command
   that repairs a skill based on where the session got confused", not "good
   commands").
4. **Verdict** — is it *uniformly superior* to this repo? Almost always no —
   the agent must name what this repo has that the peer lacks.

Tell agents WebFetch summaries come from a small model, so they should flag any
mechanic they're paraphrasing rather than verifying against source.

### 4. License gate (do this before borrowing ANYTHING)

For each repo you intend to borrow from, confirm the license from the source,
not from memory. Fetch in order until one resolves:

```
https://raw.githubusercontent.com/<owner>/<repo>/main/LICENSE
https://raw.githubusercontent.com/<owner>/<repo>/master/LICENSE
https://raw.githubusercontent.com/<owner>/<repo>/HEAD/LICENSE
gh api repos/<owner>/<repo>/license   # returns license.spdx_id, or 404/null
```

Then apply:

| License found | What you may do |
|---|---|
| **MIT / BSD / Apache-2.0 / ISC** | Copy or adapt code/text **with attribution** — retain the copyright + permission notice. Apache-2.0: also preserve `NOTICE` if present. |
| **GPL / AGPL / LGPL / MPL (copyleft)** | Do **not** copy into a permissive/unlicensed repo without flagging the license-compatibility consequence to the user first. Prefer reimplementing the *idea* independently. |
| **CC-BY / CC-BY-SA** (no `NC`, no `ND`) | Fine for prose/docs with attribution; SA imposes share-alike --- flag it. Not meant for code. |
| **CC-BY-NC / CC-BY-NC-SA / CC-BY-NC-ND** | **Read-only for a permissively licensed repo.** The NonCommercial term does not survive relicensing, so it cannot go into an MIT/BSD/Apache repo at all --- not even prose, not even with attribution. Clean-room the *idea* and credit it as inspiration. *Using* the work is still fine where the use is noncommercial; this row is about copying. |
| **CC-BY-ND** | **Read-only.** ND does permit reproducing and Sharing the material *verbatim*; what it forbids is Sharing anything adapted --- you may "produce and reproduce, but not Share, Adapted Material" (§2(a)(1)). That still lands on idea-only here, for two reasons. The grant is **non-sublicensable** (same section), so this repo cannot re-offer the material under MIT, which is what vendoring it would do. And a fragment nobody may revise is dead weight in a corpus whose files exist to be revised --- the *next* edit to it is the one that becomes an unshareable derivative. |
| **No license / "all rights reserved"** | **Read-only.** You may learn from it and reimplement the *idea* from scratch in your own words/code, but you may **not** copy its files, text, or structure verbatim. |

**Match the full SPDX id, not the `CC BY` prefix.** A Creative Commons
license's base letters look permissive while the suffix carries the
restriction, so `CC-BY-4.0` and `CC-BY-NC-4.0` differ by exactly the clause
that decides the answer.
Read the whole identifier, and check `.claude-plugin/*.json`, `package.json`,
or an equivalent manifest as a second source --- a repo that declares its
license in metadata as well as in `LICENSE` gives you a free cross-check.

When in doubt, treat it as "no license" and reimplement independently.
A clean-room reimplementation of an *idea* is always allowed — copyright
protects expression, not concepts.

**Copying and using are separate questions, and only the first is what this
gate decides.** A license that forbids vendoring a peer's files into this repo
may still permit installing and running that peer alongside it --- which is
often the better outcome anyway, since it needs no maintenance here.
When the gate comes back read-only, check whether the peer ships as an
installable plugin before concluding there is nothing to gain, and report both
answers.

### 5. Decide "uniformly superior"

A peer is *uniformly superior* only if it is a strict superset: it does
everything this repo does, at least as well, with no meaningful capability this
repo has that it lacks. This is rare — collect the disqualifier for each
(the thing this repo does that the peer doesn't). If one genuinely dominates,
say so plainly and recommend adopting it wholesale rather than cherry-picking.

### 6. Synthesize a ranked borrow list

Merge all agents' findings, dedupe overlapping ideas, and rank by
**impact ÷ effort** (best bang-for-buck first). For each item give:

- **Idea** — one line.
- **Source** — repo + its license (the borrow basis: "MIT, attribute" /
  "no license — reimplement idea").
- **Why** — the gap it closes here.
- **Effort** — Low / Med / High.

Lead the report with the headline verdict: *is anything uniformly superior?*
(usually no, with the one-line reason), then the ranked list.

### 7. Implement — with attribution

Don't restructure the repo unprompted. Present the ranked list and ask which
items to implement (mirror `tidy`'s close-out). For each item the user greenlights:

- **MIT/BSD/Apache borrow:** adapt it, and record attribution. Maintain a
  `CREDITS.md` (or `NOTICE`) at repo root with an entry per source:
  `- <feature> — adapted from [<owner>/<repo>](url) (<SPDX license>)`.
  For a copied file, also keep the original copyright header inline.
- **No-license idea:** reimplement from scratch; still credit the inspiration
  in `CREDITS.md` as "*idea inspired by …*" (courtesy, not a legal requirement).
- **When the borrow lands in a skill** (a file under `skills/*/SKILL.md`):
  add a short `## Heritage` section to that skill naming the source, its
  license, and any reuse constraint --- especially for an unlicensed or
  NC source, where the constraint is "do not copy this source's prose",
  not merely "credit this". A reader who loaded only that skill never sees
  `CREDITS.md`, so the in-skill note is a deliberate second copy, not a
  DRY violation --- keep it short (the license and the constraint, not the
  whole story) so the two records cannot meaningfully drift apart.
- File deferred items as issues so they aren't lost.

## Output format

1. **Verdict** — uniformly-superior? yes/no + one-line reason.
2. **Peer map** — short table: repo · bucket · license · 1-line "what".
3. **Ranked borrow list** — as in §6, best-bang-for-buck first.
4. **What this repo uniquely owns** — the capabilities no peer replicated
   (reassurance + positioning).

## Relationship to other skills

- **`opposition-research`** (alias `oppo`) — the mirror image. `scout-peers`
  reads a competitor's **code / repo** to borrow license-checked
  *implementations*; `oppo` reads its **users' discourse** (issue trackers,
  feature-request boards, subreddits, reviews) for *demanded features*,
  regardless of whether anyone built them. Use `oppo` to learn *what* to build,
  `scout-peers` to learn *how* others built it.
- **`deep-research`** — the general multi-source web-research harness;
  `scout-peers` is the repo-survey-and-adapt specialization.
- **`prefer-upstream`** — before hand-rolling something, both skills push toward
  reusing what the ecosystem already maintains.

## What NOT to do

- Don't copy from a repo whose license you haven't fetched and verified this
  session. "Probably MIT" is not a license check.
- Don't copy verbatim from an unlicensed repo — reimplement the idea instead.
- Don't strip a copyright/permission notice when adapting permissively-licensed
  code.
- Don't make the borrow-implementations unilaterally — audit, then ask which to
  adopt (these are opinionated changes to the user's repo).
- Don't trust a WebFetch paraphrase of a peer's internals as fact when it
  matters — fetch the actual source file before relying on the mechanic.
- Don't over-weight raw size/star count; a bigger catalog is not "superior" to
  a focused tool that does its job well.
