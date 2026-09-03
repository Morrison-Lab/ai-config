# ai-config's three context pools -- only one of them is worth splitting

Split out of [`claude-code.md`](claude-code.md) (ai-config#694 pattern) at the 1200-line gate.

Not all of this corpus costs the same per session, and the cheapest way to waste effort is to "reduce context" by shrinking the wrong layer:

- **Always-loaded** -- `CLAUDE.md` plus every `@shared/...` fragment it references, plus *every* skill's `description` frontmatter.
  Paid on every session regardless of task.
  Splitting a file here saves **nothing**: each piece still loads.
  The only levers are pruning, consolidating, or demoting a fragment to on-demand.
- **On-demand** -- `memories/*.md` and skill bodies.
  Paid only when read, so file length is a real per-use cost and splitting genuinely helps.
- **Generated** -- `codex-skills/` and other derived trees.
  Costs CI time and merge conflicts, not context.

Measure before acting: as of 2026-07-24 the always-loaded set was ~48.5k tokens (`CLAUDE.md` + 47 fragments) plus ~15.2k tokens of skill descriptions, against `memories/tools.md` at ~48k tokens paid only on a whole-file read.
That is why ai-config#696 split `tools.md` (on-demand, so the split pays) while ai-config#700 attacked the description budget by removing duplication rather than by splitting anything (always-loaded, so splitting would not have paid).

**That "splitting saves nothing" claim is Claude Code's documented behaviour, not an inference, and the docs name a lever this section omits.**
Verified against <https://code.claude.com/docs/en/memory> on 2026-07-31.
Imported files "are expanded and loaded into context at launch alongside the CLAUDE.md that references them";
"Splitting into `@path` imports helps organization but doesn't reduce context, since imported files load at launch";
imports recurse to "a maximum depth of four hops";
and "CLAUDE.md files are loaded in full regardless of length, though shorter files produce better adherence".
Two details worth adding to the pools above.
Import parsing skips Markdown code spans and fenced code blocks, so a backticked `@README` stays literal text rather than becoming an import.
And the docs' own recommended lever for a large instruction set is **path-scoped rules**, which load only when Claude works with matching files --- effectively a fourth pool, and one this corpus does not currently use.

**Re-measure before arguing from a number: the always-loaded closure has roughly tripled since the 2026-07-24 figure above.**
The instrument is a recursive walk summing `os.path.getsize` over whole-line `@path` matches, seeded at `CLAUDE.md`:

```python
import os, re
IMPORT = re.compile(r"^@([\w./-]+)$", re.M)
def closure(root, start="CLAUDE.md"):
    seen, stack = {}, [os.path.join(root, start)]
    while stack:
        p = os.path.normpath(stack.pop())
        if p in seen or not os.path.isfile(p):
            continue
        seen[p] = os.path.getsize(p)
        text = open(p, encoding="utf-8", errors="replace").read()
        stack += [os.path.join(root, m) for m in IMPORT.findall(text)]
    return len(seen), sum(seen.values())
```

Measured 2026-07-31: ai-config's closure is **66 files, 661,750 bytes** --- roughly 165k tokens at a 4-bytes-per-token rule of thumb --- with all 65 imports at depth 1, so the corpus uses one of the four available hops.
`Morrison-Lab/gha`'s closure is 1 file, 104,462 bytes, which is the comparison worth holding onto: a repo with no imports at all pays about a sixth as much.

**A CI review bot pays that closure too, so it is not only an interactive- session cost.**
`claude-code-action` defaults `settingSources` to `["user", "project", "local"]` in `base-action/src/parse-sdk-options.ts`, and `"project"` is what loads the repo's own `CLAUDE.md`.
The default is overridden only by passing `--setting-sources` in `claude_args`, which `Morrison-Lab/gha` does at none of `main`, `v1`, or `v2` (`git grep -c setting-sources <ref> -- '*.yml' '*.yaml'` returns no hits at any of the three).
So every `@claude` run in a gha-consuming repo loads that repo's whole always-loaded set before it reads a line of the diff.

**That closure has now overflowed the context limit for at least one workflow in this repo, so the cost is a measured failure rather than a projected one.**
`Morrison-Lab/ai-config#986` carries a comment posted at 2026-07-31T20:47:04Z whose body is the API's context-length error verbatim, `Prompt is too long`, emitted by `claude.yml@v1`'s post-step from workflow run 30664135897.
The agent had loaded the always-loaded set and done no work of its own: its `Run Claude Code` step ran 36 seconds, and the job concluded `success` with no step failing.
So the figure above is not merely large;
it exceeds what at least one consumer of it can accept.

The second-order effect is the part to plan around.
An agent that cannot run in this repo cannot be asked to help shrink it, so the corpus's size now blocks the tool that would reduce the corpus's size.
That argues for treating the levers above as urgent rather than tidy, and for preferring the ones a human or a plain script can apply without an agent.

**The reviewer half of the same afternoon is inference, and is labelled that way deliberately.**
`claude-review` failed at two heads with `is_error: true` alongside `subtype: "success"`, and has **not** been shown to hit the same limit.
The shapes do fit: the agent died before its first call, while the reviewer ran 43 seconds and spent $0.97 across 2 turns, which is what a prompt sitting just under the line and then pushed over by tool results would look like.
A fitting shape is not evidence, so treat the reviewer failure as an open question rather than as a second instance, until something reads its own error string.

- **Do:** re-run the closure walk before making a context-budget argument --- the figure moves fast, and a stale one argues for the wrong lever.
- **Do:** reach for pruning, consolidating, demoting to on-demand, or path-scoped rules, which are the levers that change the number.
- **Do:** treat the closure as a ceiling already reached rather than a budget still being spent, since one workflow here has now failed on it outright.
- **Don't:** propose splitting a large `CLAUDE.md` into `@path` imports as a context saving;
  it buys organization and nothing else.
- **Don't:** assume the always-loaded cost is paid only by interactive sessions.
- **Don't:** report the `claude-review` failures as the same overflow --- that is a shape match, and no error string has been read for them.

**A `shared/` fragment marked `<!-- Shared with the lab manual -->` in `CLAUDE.md` is transcluded WHOLE by the UCD-SERG lab manual, so restructuring one silently damages the manual.**
Six `@shared/...` fragments carry that comment as of 2026-08-08 (`grep -c 'Shared with the lab manual' CLAUDE.md`): `shared/coding/avoid-nesting.md`, `prefer-packaged-functions.md`, `per-operation-grouping.md`, `avoid-hardcoding-external-data.md`, `shared/writing/plain-prose.md`, and `ai-tells.md` --- all small (17-209 lines), not the corpus's heaviest closure fragments.
`shared/workflow/fully-clean.md`, `ardi.md`, and `address-every-comment.md` do NOT carry the marker, despite an earlier version of this entry claiming otherwise;
they are large but ai-config-only, so restructuring them (e.g. ai-config#1236's `fully-clean.md` split) needs no manual coordination.
The two `shared/vendored/**` copies are the same kind of shared-source file as the six marked fragments.
The manual transcludes each one with `{{< include .ai-config/shared/<area>/<topic>.md >}}` through its `.ai-config` git submodule (README, "Shared content"), rendering the file as it stands.
So any edit to such a fragment's content or structure reaches the manual too: splitting part of it into a new sibling drops that part from the rendered manual, and a relative link to a companion the manual does not `include` dangles there.
A corpus-restructuring pass that alters fragment content must therefore EXCLUDE the lab-manual-shared and `shared/vendored/**` fragments, or coordinate with the manual.
This is why a 2026-08 case-record-extraction pass touched only the ai-config-only fragments (those without the marker);
the lab-manual-shared ones are tracked in Morrison-Lab/ai-config#1191 (move records out) and #1192 (condense them in place).

**Content leaves the always-loaded closure when it moves into a sibling file referenced by a PLAIN MARKDOWN LINK, not an `@`-import.**
`scripts/check-context-closure.py`, which implements the closure walk, follows only `@path` imports (whole-line or inline in prose);
a `[text](topic.cases.md)` markdown link matches neither, so its target is never followed into the closure.
Relocating worked-example case records from a fragment into a `[...](<name>.cases.md)` sibling thus drops them from every session's always-loaded set while keeping them one click away.
Run the script before and after to confirm: the file count is unchanged (the sibling never joins the closure, the parent stays imported) while the byte total falls by the relocated content.
This is the concrete form of the section's "demoting a fragment to on-demand" lever, bounded by the lab-manual constraint above --- apply it only to ai-config-only fragments, since a markdown-linked sibling is invisible to the manual's whole-file `include`. (Tracked in Morrison-Lab/ai-config#1193.)

## A new skill can fail validate-skills.py on the listing budget alone (2026-09-03)

`scripts/validate-skills.py` sums `name + description + 8` over every skill.
It errors past 9,000 chars.
At 202 skills the pool sat within 60 chars of the cap.
Adding `triage` with a 44-char description therefore failed it,
even though the skill itself was valid.
The over-budget line looks like `check-context-closure.py`'s advisory output,
and was misread as one.
It is an error.
The review round caught it.
The fix that fits is to trim the longest existing descriptions,
which the error names,
rather than the new one alone.
Each trimmed description must stay accurate to the skill body:
a second round caught "Detect and" dropped from `prune-dead-code`.

- **Do:** run `validate-skills.py` and read its exit status before dispatching review when adding a skill.
- **Do:** trim the longest descriptions the error names, not only the new one.
- **Don't:** read the over-budget line as advisory.
- **Don't:** shorten a description past what the skill body says it does.
