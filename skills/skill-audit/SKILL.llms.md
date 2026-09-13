# skill-audit — usage-frequency audit and pruning recommender

Report which skills earn their keep and which are dead weight. This repo’s `skills/` directory grows fast enough that “senior devs run 8 skills, juniors run 30” is a real pruning signal here — but nobody can act on it without first knowing *which* skills actually fire. This skill answers that question; it never deletes anything itself.

## When this fires

- “audit skill usage”, “skill-audit”, “which skills are dead weight”
- “what skills have I never used”, “find unused skills”
- “prune skills by usage”, “skill usage report”, “which skills should I delete”
- Periodically as part of general corpus hygiene, alongside `find-overlap` and `check-info-quality`.

## The open design question: there is no built-in telemetry

Claude Code has no invocation-count API — confirmed at issue-filing time ([anthropics/claude-code#35319](https://github.com/anthropics/claude-code/issues/35319) is an open feature request asking for exactly this as a built-in primitive). Until that lands, this skill defines its own signal rather than assuming one exists: local session transcripts.

**The signal.** Claude Code CLI sessions persist their full transcript as JSONL under `~/.claude/projects/<project-slug>/<session-id>.jsonl` (and subagent runs under `<session-id>/subagents/*.jsonl`). Every explicit `Skill` tool invocation appears in that transcript as a `tool_use` block: `"name":"Skill"` with an `input.skill` field naming which skill fired. Grepping across every transcript this machine has recorded is a real, verifiable per-skill invocation count — not a placeholder.

**The caveat that matters most: this is a per-machine, lower-bound signal.** This repo is explicitly designed to sync across machines (see the repo description: “synced across machines via git”), so:

- A skill invoked only on a different machine reads as unused here. Don’t report “dead” from a single machine’s transcripts without saying so.
- A skill invoked purely by its **bare-keyword trigger** (a matched phrase in the system prompt, not a literal `Skill` tool call) or purely as **standing behavior a `CLAUDE.md`/`shared/` fragment enforces automatically** (e.g. `ardi`’s loop running via the “watch and ARDI every PR” standing rule, without ever being invoked as `/ardi`) can undercount relative to how often its *behavior* actually happens.
- Alias skills (`dc`, `gi`, `sup`, …) log under their own name, separate from the canonical skill’s count. Report both the alias’s own count and the rolled-up alias+canonical total — a “dead” alias whose canonical fires constantly is a different finding (rename/dedupe the alias) than a “dead” capability (nobody uses this at all).

Aggregate across every machine’s transcript store you can actually read (this machine’s `~/.claude/projects/`, plus any other checkout the user points you at); state plainly which machines were and weren’t included.

## Usage tiers

Classify every skill directory into exactly one tier:

1.  **Actively-used** — at least one `Skill` tool invocation (own name or its canonical, if it’s an alias) in the last 30 days of transcript history.
2.  **Dormant** — invoked at some point in the retained transcript history, but not in the last 30 days. A candidate to watch, not yet to prune — could be seasonal (a skill that only fires at PR-merge time, or during a specific project phase).
3.  **Dead** — zero invocations anywhere in the retained transcript history. The strongest pruning candidate — but see the caveats above before recommending deletion of anything that could be firing invisibly (a standing-rule skill, or one only used on another machine).

Retained history length depends on how long this machine’s `~/.claude/projects/` has been accumulating; report the earliest and latest transcript timestamp you found so the reader knows the window, not just today’s date.

## Procedure

1.  **Enumerate the corpus.**

    ``` bash
    ls -d skills/*/ | xargs -n1 basename
    ```

    For each, read its `SKILL.md` frontmatter to tell alias stubs (body reads `"This is a spelled-out alias... → **[<canonical>](../<canonical>/SKILL.md)**"`) from canonical skills, and note which canonical each alias redirects to.

2.  **Gather the usage signal.** Grep every local transcript for `Skill` tool invocations and pull out the `input.skill` value:

    ``` bash
    for f in ~/.claude/projects/*/*.jsonl ~/.claude/projects/*/*/subagents/*.jsonl; do
      [ -f "$f" ] || continue
      grep -oP '"name":"Skill".*?"skill":"\K[^"]+' "$f"
    done | sort | uniq -c | sort -rn
    ```

    Pull each matching record’s `timestamp` field by filtering to the skill name first, then extracting just the timestamp:

    ``` bash
    grep -P '"name":"Skill".*?"skill":"<name>"' "$f" | grep -oP '"timestamp":"\K[^"]+'
    ```

    to get the most recent invocation date for the tier cutoff in step 4.

    (Adjust the glob to match this environment’s actual project-directory naming — `~/.claude/projects/<slug>/` slugs the working-directory path, so list `~/.claude/projects/` first and confirm the pattern before trusting the glob matched everything. The step-2 grep also assumes compact JSON, no spaces around `:` — if the first run returns nothing, sample one `.jsonl` file and check its actual formatting before concluding every skill is dead.)

3.  **Roll up alias counts into their canonical.** For each alias found in step 1, add its invocation count and latest timestamp into its canonical’s row, but keep the alias’s own count visible too (see caveat above).

4.  **Bucket every skill into a tier** (actively-used / dormant / dead) using the 30-day threshold and each skill’s most recent invocation timestamp, falling back to “no invocation found → dead, pending the caveats” when a skill’s name never appears.

5.  **Cross-check dead/dormant candidates against `CLAUDE.md` and `shared/`** before recommending pruning — grep for the skill’s name in both trees. A skill wired into a **standing rule** (invoked automatically, never through an explicit `Skill` call) will show as dead here despite being load-bearing; flag those separately as “automated, not measured” rather than “dead”.

6.  **Report** — see the table format below. Never delete a skill file, edit a `SKILL.md`, or touch `skills.qmd` as part of this skill; that is a human or a separate action step’s call (see Relationship to other skills).

## Report format

One table, one row per canonical skill (aliases nested underneath or noted inline), sorted dead-first so the pruning candidates surface at the top:

    | Skill | Aliases | Tier | Own count | Rolled-up count | Last seen | Notes |
    |-------|---------|------|-----------|------------------|-----------|-------|
    | convert-repo-format | crf | dead | 0 | 0 | never | no standing-rule reference found |
    | ardi | dc, drive, clean, iterate | actively-used | 12 | 47 | 2026-07-04 | — |
    | use-math-macros | macroize | dormant | 2 | 2 | 2026-04-11 | last fired ~12 weeks ago |

Close with a short pruning recommendation list: which “dead” skills look safe to defer for consolidation or deletion, and which “dead” results are actually “automated, not measured” or “machine-local blind spot” and should NOT be pruned on this evidence alone.

## Runs forked; `background: false` for synchronous return

This whole skill — steps 1-6, report and pruning recommendation included — runs isolated as the `skill-usage-auditor` custom agent (`.claude/agents/skill-usage-auditor.md`, `context: fork` + `agent: skill-usage-auditor`), not inline in the calling conversation. No step here needs Edit/Write, so nothing is lost by forking the whole procedure rather than only steps 1-5 — unlike an audit skill that also files an issue or opens a PR, this skill has no write/PR follow-through to leave behind in the main session, and forking the whole run makes the harness-enforced no-Edit/Write guarantee cover step 6 too, not just the counting steps.

Two further reasons this is worth doing, and the second is the one that matters: **context cost** (the skill body never enters the calling conversation at all, rather than staying resident once loaded), and **isolation from anchoring** (a usage audit that has already read the conversation that invoked it is a weaker audit).

`background: false` overrides the fork’s own default so the report still returns in the turn that invoked the skill, matching how this skill is normally used — an interactive query, not a fire-and-forget background task.

## Relationship to other skills

- **`find-overlap`** — finds redundant *content* between skills (two skills saying the same thing). This skill finds *unused* skills (nobody invoking a skill at all). The two axes are orthogonal: a skill can be both a duplicate and dead (the strongest prune signal — flag these first when both audits have run), or unique in content and still dead, or duplicated in content but actively used by both copies.
- **`check-info-quality`** — flags stale or inaccurate *prose inside* a skill file (a version claim that’s since moved, a citation that doesn’t back its claim). This skill flags a skill *itself* going stale through *disuse* — a skill can pass `ciq`’s content check with flying colors and still never fire in practice. Run both; neither subsumes the other.
- **`consolidate-skills`** — the likely action counterpart once this skill flags a genuine duplicate that’s also dead; `consolidate-skills` does the actual merge.
- **`skill-builder`** — the authoring counterpart. Its own “extend before you create” step-0 check is a *pre-creation* dedupe scan; this skill is a *post-hoc* usage audit over skills that already shipped. A `skill-audit` finding can also feed back into `skill-builder`’s step 0 next time someone proposes a near-duplicate of a skill this audit already flagged as low-usage.
- **`heal-skill`** — repairs a skill that misfired after shipping (wrong behavior); this skill flags a skill that never fires at all (no behavior to repair).

## Anti-patterns

- ❌ Deleting or editing a skill file as part of this skill’s own run — it is detect-and-report only, same split as `find-overlap`/`consolidate-skills`.
- ❌ Reporting “dead” from a single machine’s transcripts without the cross-machine caveat — the repo is explicitly multi-machine.
- ❌ Counting an alias’s invocations as if they were the canonical’s, or vice versa, without reporting both the alias-own and rolled-up counts.
- ❌ Flagging a skill wired into a `CLAUDE.md`/`shared/` standing rule as “dead” without first grepping for it there — it can be firing constantly as automated behavior with zero explicit `Skill` tool calls to show for it.
- ❌ Treating “dormant” the same as “dead” — a skill unused for 45 days because it is seasonal (fires only at release time, or once per new repo) is not the same finding as one with zero invocations ever.
- ❌ Assuming Claude Code exposes an invocation-count API and skipping the transcript-grep step — no such API exists as of this skill’s writing.

Back to top
