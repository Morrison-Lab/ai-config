# find-overlap — read-only overlap / redundancy detector

Find where a corpus says the same thing twice — and change nothing. This is the *detection* half of de-duplication, factored out so it’s reusable: an action skill calls it for its audit (`consolidate-skills` for the skills corpus, `consolidate-memory` for the memory corpus), and you can run it standalone to ask “what’s redundant here?” over any body of content. It is to `consolidate-skills` what `pr-status` is to `ardi` — it reports, it does not act.

## When this fires

- “find overlap”, “find overlapping skills”, “find overlapping content”, “find duplicates”, “find redundant content”, “audit for duplication”, “dedupe audit”, “what’s redundant here”, “where do these overlap”, `/find-overlap`.
- As the detection phase of an action skill — `consolidate-skills` delegates its audit here.

## The one distinction that matters — three buckets

Most “overlap” is **not** redundancy. Every cluster you surface must be sorted into exactly one of three buckets — the report is only useful if it makes this call, not just “these look similar”:

1.  **Intentional alias / redirect — NOT overlap.** One canonical unit with real content; the rest are thin pointers to it (skill alias stubs ending in `→ …/<canonical>/SKILL.md`; a memory that just says “see \[\[other\]\]”). This is the *target* state. Also here: deliberate single-vs-all pairings (`pr-status` / `pr-status-all`).
2.  **Adjacent-but-distinct — NOT a duplicate.** Same theme, genuinely different purpose or procedure (`tidy` vs `simplify`; two memories on related but separate facts). Merging these *loses* something. If they should reference each other, that’s a cross-link job (→ `link-skills`), not a merge.
3.  **Genuine duplicate / redundant — FLAG THIS.** Two or more units with **real content** that say the same thing or drive the same outcome in different words. This is the only bucket that warrants a merge.

**Litmus:** if you can name a capability or fact that would be lost by removing one member, it isn’t a duplicate. If you can’t, it is.

## Procedure

### 1. Define the corpus and the comparable unit

Pick the scope the user named (default to the skills corpus when you’re in the ai-config repo and none is given), and the unit you compare:

| Corpus | Unit | Cheap signature | Similarity tell |
|----|----|----|----|
| `skills/` | one `skills/<name>/SKILL.md` | `name` + `description` + body | shared trigger phrases / same outcome verb |
| `memories/` + `~/.claude/projects/*/memory/` | one memory file | `name` + `description` + body | same subject/fact restated |
| docs / Quarto / markdown | one heading section | heading + first lines | same topic covered twice |
| code | one function / file | signature + doc comment | same logic, different name |
| pasted prose | one paragraph / section | first sentence | same claim repeated |

### 2. Gather signatures cheaply (one row per unit)

For skills:

``` bash
cd "${CLAUDE_PLUGIN_ROOT:-$(git -C ~/.claude/skills/find-overlap rev-parse --show-toplevel 2>/dev/null || pwd)}"
for d in skills/*/; do n=$(basename "$d")
  # robust for inline and block-scalar (`>`, `|`, with optional `-`/`+` chomp) frontmatter:
  desc=$(python3 -c "
import re
t=open('$d/SKILL.md').read()
m=re.search(r'^description:[ \t]*[>|]?[-+]?[ \t]*\n?(.*?)(?=\n\S|\Z)', t, re.M|re.S)
print(re.sub(r'\s+',' ', m.group(1) if m else '').strip().strip('\"')[:70])")
  lc=$(wc -l < "$d/SKILL.md" | tr -d ' ')
  printf '%4s  %-34s %s\n' "$lc" "$n" "$desc"
done | sort -n
```

(A plain `awk -F'description:'` drops `description: >` block scalars — including this skill’s own — to blank; the `python3` extractor handles both forms.) For memories: the same shape over **both** the in-repo `memories/*.md` and the per-repo project memories in `~/.claude/projects/*/memory/*.md` (`name` + `description` from frontmatter). Repo-specific memories moved out of `memories/repo/` into `~/.claude/projects/<path>/memory/`, so a scan of `memories/*.md` alone now misses the bulk of repo-level knowledge — glob both. The line count separates thin stubs from real bodies at a glance.

### 3. Cluster candidates — then read the bodies

**Run the instrument first, then do the keyword pass — you need both.**

``` bash
python3 scripts/find-near-duplicates.py --calibrate            # skills corpus
python3 scripts/find-near-duplicates.py --corpus 'memories/*.md'
python3 scripts/find-near-duplicates.py --include-aliases      # to audit stubs
```

It ranks every pair by Jaccard similarity over word shingles and prints the candidates above a threshold with their shared phrasing, so which pairs get read is decided by arithmetic rather than by which ones you thought to compare — per [`algorithmatize-checks`](../../shared/workflow/algorithmatize-checks.md). It suppresses alias-stub pairs by default and reports how many it suppressed.

**It covers one of the three buckets, so it does not replace the keyword pass.** It ranks *reused phrasing*, which is where genuine duplicates live. It cannot see conceptual adjacency: `tidy` and `simplify` — this skill’s own canonical adjacent-but-distinct example — score 0.019, because they share an idea and almost no wording. Alias families are likewise invisible to the score (a stub’s body is a pointer, so `find-duplicates` vs `find-overlap` scores 0.002) and are detected structurally instead, via the `alias?` flag. So: take the instrument’s ranking, **then** add whatever the keyword/title pass turns up that it missed.

Then **read the full body of every member of each candidate cluster.** Never classify on titles, descriptions, or a similarity score alone — that’s the top source of false positives (two skills can share a verb, or a paragraph of boilerplate, and do different work).

### 4. Classify each cluster into one of the three buckets

Apply the litmus above. Be skeptical: assume *adjacent-but-distinct* until the bodies prove genuine duplication.

### 5. Report — read-only, routed to an action

Output one compact table; **edit nothing.** For each cluster give the members, the bucket, what they share, and a recommended disposition pointed at the skill that would carry it out:

| Cluster | Members | Bucket | Shared | Recommended |
|----|----|----|----|----|
| deploy | `deploy-staging`, `push-to-staging` | genuine duplicate | same deploy steps | merge → `consolidate-skills` |
| sync trio | `merge-main`, `sync` | intentional alias | redirect stubs | leave |
| tidy/simplify | `tidy`, `simplify` | adjacent-distinct | “clean up code” | cross-link → `link-skills` |

(The first row is illustrative — a hypothetical pair, not a live finding. The other two model real corpus relationships.)

Disposition routing: duplicate skills → `consolidate-skills`; duplicate memories → `consolidate-memory`; adjacent-but-distinct missing a link → `link-skills`; redundant code → `tidy` / `simplify`; prose/docs → a manual edit. Always end with a recommendation per cluster — a raw similarity list with no disposition just pushes the judgment back to the reader.

## Runs forked; `background: false` for synchronous return

This whole skill — every step above, including the report — runs isolated as the `overlap-detector` custom agent (`context: fork` + `agent: overlap-detector`), not inline in the calling conversation. Two reasons, and the second is the one that matters:

- **Context cost.** The skill body (this file) never enters the calling conversation at all, rather than staying resident once loaded.
- **Isolation from anchoring.** A dedup pass that has already read the conversation that produced the content under audit is a weaker audit — the same argument behind the `Workflow` adversarial-verify pattern this skill’s own Orchestration step already uses.

Every step above needs only `Bash`/`Read`/`Grep`/`Glob`, so nothing is lost by running the whole procedure inside `overlap-detector` rather than only a sub-step of it — unlike an audit skill that also files an issue or opens a PR, find-overlap has no write/PR follow-through to leave behind in the main session.

`background: false` overrides the fork’s own default so the report still returns in the turn that invoked the skill, matching how `consolidate-skills` and `consolidate-memory` already consume it (step 1 of each delegates here and acts on the result immediately, not asynchronously).

## Orchestration

Overlap detection over a large corpus decomposes by comparison cluster — each candidate group of comparable units can be classified independently, and the work is pure reading with no shared-runner cost. Consult `shared/workflow/when-to-orchestrate.md`. When the corpus is large (many skills, memories, or files), run a Workflow: parallel agents each judging one cluster against the three buckets, then a synthesis stage that assembles the dispositions, rather than reading the whole corpus in one context. This stays read-only; it only parallelizes the reading and classification. Launch directly when an opt-in signal is present; otherwise propose with a cost estimate first.

**This decomposition needs the calling session, not the forked run.** `overlap-detector`’s own tool list has no `Workflow` — deliberately, so granting the fork read-only detection doesn’t also hand it a path to spin up a sub-agent with write access. So the fork itself always reads the corpus serially. For a corpus large enough to want the Workflow fan-out above, run that fan-out in the main session instead of invoking this skill, or treat it as a known limitation until a follow-up gives `overlap-detector` a read-only-scoped path to it.

## Relationship to other skills

- **`consolidate-skills`** — the action counterpart for the skills corpus; it delegates its audit to this skill, then merges the genuine-duplicate clusters. find-overlap finds; consolidate-skills acts.
- **`consolidate-memory`** — the action counterpart for the memory corpus.
- **`link-skills`** — finds the *inverse* (distinct skills that should reference each other but don’t); hand it the adjacent-but-distinct clusters.
- **`challenge-redundant-content`** (`shared/workflow/`) — the review-time, single-diff counterpart: questions redundancy while reviewing a diff or document’s prose/math/code, rather than sweeping the whole corpus.
- **`find-ai-tells`** — sibling read-only scanner over prose, for a different signal (AI tells, not duplication).
- **`tidy` / `simplify`** — code-level dedup once overlap is found.
- **`pr-status` ↔︎ `ardi`** — the same read-only-report vs. actor split this skill has with the `consolidate-*` family.

## Anti-patterns

- ❌ Editing, merging, or deleting anything — find-overlap only detects and reports. Acting is the `consolidate-*` skills’ job.
- ❌ Flagging an **intentional alias family** or a single-vs-all pairing (`pr-status` / `pr-status-all`) as a duplicate.
- ❌ Conflating **adjacent-but-distinct** with **duplicate** — that recommends a merge that loses a capability.
- ❌ Classifying on titles/descriptions alone without reading bodies — the main false-positive source.
- ❌ Checking only one corpus when the user said “generally” / “everywhere”.
- ❌ Reporting raw similarity with no per-cluster disposition.

Back to top
