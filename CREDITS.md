# Credits

Ideas adapted into this repo from comparable open-source projects, surfaced via
the [`scout-peers`](skills/scout-peers/SKILL.md) skill. Each entry names the
source and its license. Where a source had **no license**, only the *idea* was
reused — via clean-room reimplementation, with no code or text copied.

This file is the index.
When a borrow lands in a skill (a file under `skills/*/SKILL.md`), that skill also carries its own short `## Heritage` section naming the source, its license, and any reuse constraint --- a deliberate second copy rather than a DRY violation, since a reader who loaded only that one skill never sees this file.
Keep the in-skill note short enough that the two cannot meaningfully drift: the license and the constraint, not the whole story.

## Borrowed ideas

- **Skill & manifest CI validation** — `scripts/validate-skills.py`,
  `.github/workflows/validate.yml`.
  Approach inspired by
  [terrylica/cc-skills](https://github.com/terrylica/cc-skills)
  (`validate-plugins.mjs`, MIT) and
  [jeremylongshore/claude-code-plugins-plus-skills](https://github.com/jeremylongshore/claude-code-plugins-plus-skills)
  (`validate-skills-schema.py`, MIT). Reimplemented from scratch in Python — no
  source copied.

- **Pre-commit security gates** — `.pre-commit-config.yaml`. Convention from
  [daymade/claude-code-skills](https://github.com/daymade/claude-code-skills)
  (MIT). Runs the upstream
  [gitleaks](https://github.com/gitleaks/gitleaks) and
  [pre-commit-hooks](https://github.com/pre-commit/pre-commit-hooks) hooks under
  their own licenses.

- **`heal-skill` skill** — `skills/heal-skill/SKILL.md`.
  Idea inspired by the `/heal-skill` command in [justcarlson/dotfiles-claude](https://github.com/justcarlson/dotfiles-claude) (**no license** — idea only;
  clean-room reimplementation, nothing copied).
  Also carries its own `## Heritage` section.

- **Relative-link linter & inventory/verify conventions** —
  `scripts/check-links.py`, `scripts/inventory.sh`, and the README
  "Inventory"/"Verify the install" sections.
  Conventions seen across
  [terrylica/cc-skills](https://github.com/terrylica/cc-skills) (MIT),
  [rohitg00/awesome-claude-code-toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit)
  (Apache-2.0), and
  [jeremylongshore/claude-code-plugins-plus-skills](https://github.com/jeremylongshore/claude-code-plugins-plus-skills)
  (MIT). Reimplemented from scratch.

- **R and Quarto authoring skills** --- `skills/alt-text/`, `skills/brand-yml/`, `skills/cli/`, `skills/cran-extrachecks/`, `skills/create-release-checklist/`, `skills/lifecycle/`, `skills/quarto-authoring/`, `skills/r-package-development/`, `skills/release-post/`, `skills/testing-r-packages/` --- adapted from [posit-dev/skills](https://github.com/posit-dev/skills) (MIT).
  The upstream license text is kept verbatim at `skills/POSIT-DEV-LICENSE.txt`.
  Each already carries its own `author`/`version`/`license` in frontmatter rather than a `## Heritage` section --- MIT permits reuse outright, so there is no reuse constraint for an in-body note to carry beyond what the frontmatter and this entry already state.

- **Question the design after three failed fixes** --- `shared/principles/think-outside-the-box.md`.
  Adapted from the `systematic-debugging` skill in [obra/superpowers](https://github.com/obra/superpowers) (MIT).
  Restated in our own words; no text copied.

- **Look up a version before reporting it does not exist** --- `shared/workflow/quotable-findings.md`.
  Pattern from the `suppressions.json` of [tag1consulting/claude-comprehensive-review](https://github.com/tag1consulting/claude-comprehensive-review) (MIT).
  Restated in our own words; no text copied.

## Reviewed sources

Outside repositories read through a reading-assignment issue, with what came of each.
An idea already covered names the file that covers it.

- [svetdev/cleat](https://github.com/svetdev/cleat) (MIT), [#3153](https://github.com/Morrison-Lab/ai-config/issues/3153), reviewed 2026-11-19.
  Filed [#5904](https://github.com/Morrison-Lab/ai-config/issues/5904) (deny messages that print their own bypass) and [#5906](https://github.com/Morrison-Lab/ai-config/issues/5906) (state the predicted effect before an eval ablation).
  Already covered: monotonic baselines (`shared/workflow/algorithmatize-checks.md`), gates over instructions (`shared/principles/deterministic-tools.md`), document size and citation gates (`scripts/check-memory-file-size.py`, `scripts/check-links.py`).
- [obra/superpowers](https://github.com/obra/superpowers) (MIT), [#2009](https://github.com/Morrison-Lab/ai-config/issues/2009), reviewed 2026-11-19.
  Adopted the three-failed-fixes trigger (above).
  Added its "descriptions say only when to use a skill" finding to [#5331](https://github.com/Morrison-Lab/ai-config/issues/5331#issuecomment-7022160948).
  Already covered: testing a skill with and without it loaded (`evals/README.md`), brainstorming (`skills/brainstorm/`), receiving review (`shared/workflow/address-every-comment.md`), verifying before claiming done (`shared/workflow/fully-clean.md`), loophole-proof rules (`shared/principles/no-gameable-rules.md`).
- [derailed-dash/dazbo-agent-skills](https://github.com/derailed-dash/dazbo-agent-skills) (MIT), [#1161](https://github.com/Morrison-Lab/ai-config/issues/1161), reviewed 2026-11-19.
  Nothing adopted or filed.
  Already covered: deterministic checks before model judgment (`shared/workflow/algorithmatize-checks.md`), findings checked against the file on disk (`shared/workflow/quotable-findings.md`), no unchecked universal claims (`shared/workflow/metacognitive-monitoring.md`), a skill-listing budget (`scripts/validate-skills.py`).
  Its other skills (Dev.to, git-crypt, Antigravity setup, WSL browser) are outside this repo's scope.
- [0xsline/awesome-deepseek-harness](https://github.com/0xsline/awesome-deepseek-harness) (CC0-1.0), [#2188](https://github.com/Morrison-Lab/ai-config/issues/2188), reviewed 2026-11-19.
  Nothing adopted or filed: it is a link list for the DeepSeek Harness plugin system, not a corpus of practices.
  The transferable entries are already covered: destructive-command guard (`hooks/run-cc-safety-net.py`, which runs `kenryu42/cc-safety-net`, one of the list's own entries), plugin vetting before install (`shared/workflow/use-plugins.md`), PR size budgets (`hooks/no-oversized-pr-push.py`).
- [tag1consulting/claude-comprehensive-review](https://github.com/tag1consulting/claude-comprehensive-review) (MIT), [#2228](https://github.com/Morrison-Lab/ai-config/issues/2228), reviewed 2026-11-19.
  Adopted the version lookup (above).
  Filed [#5905](https://github.com/Morrison-Lab/ai-config/issues/5905) (a context-free reviewer lane).
  Already covered: parallel review agents (`shared/workflow/adversarial-self-review.md`), fresh rounds without prior findings (`shared/workflow/self-review-fallback.md`), untrusted PR content (`shared/workflow/untrusted-content-is-data.md`).
- [jrjsmrtn/project-orchestration-skills](https://github.com/jrjsmrtn/project-orchestration-skills) (MIT), [#2892](https://github.com/Morrison-Lab/ai-config/issues/2892), reviewed 2026-11-19.
  Nothing adopted or filed.
  Already covered: workflow hardening (`shared/workflow/upgrade-to-gha.md`, with zizmor and deliberate tag pins), local checks matching CI (`scripts/run-local-validation.py`), the tracker over an in-repo backlog (`shared/workflow/issue-first.md`), renamed-skill aliases (`skills/skill-builder/SKILL.md`).
  Rejected: sprint planning and C4 or ADR scaffolding, which fit a product team's project rather than an agent-config corpus.

See the [`scout-peers`](skills/scout-peers/SKILL.md) skill for the full peer
survey and the license-checking procedure used to vet every borrow above.
