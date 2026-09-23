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

- **R and Quarto authoring skills** --- `skills/brand-yml/`, `skills/cli/`, `skills/cran-extrachecks/`, `skills/create-release-checklist/`, `skills/lifecycle/`, `skills/quarto-authoring/`, `skills/r-package-development/`, `skills/release-post/`, `skills/testing-r-packages/` --- adapted from [posit-dev/skills](https://github.com/posit-dev/skills) (MIT).
  The upstream license text is kept verbatim at `skills/POSIT-DEV-LICENSE.txt`.
  Each already carries its own `author`/`version`/`license` in frontmatter rather than a `## Heritage` section --- MIT permits reuse outright, so there is no reuse constraint for an in-body note to carry beyond what the frontmatter and this entry already state.

See the [`scout-peers`](skills/scout-peers/SKILL.md) skill for the full peer
survey and the license-checking procedure used to vet every borrow above.
