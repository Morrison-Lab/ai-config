# Credits

Ideas adapted into this repo from comparable open-source projects, surfaced via
the [`scout-peers`](skills/scout-peers/SKILL.md) skill. Each entry names the
source and its license. Where a source had **no license**, only the *idea* was
reused — via clean-room reimplementation, with no code or text copied.

## Borrowed ideas

- **Skill & manifest CI validation** — `scripts/validate-skills.py`,
  `.github/workflows/validate.yml`. Approach inspired by
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

- **`heal-skill` skill** — `skills/heal-skill/SKILL.md`. Idea inspired by the
  `/heal-skill` command in
  [justcarlson/dotfiles-claude](https://github.com/justcarlson/dotfiles-claude)
  (**no license** — idea only; clean-room reimplementation, nothing copied).

- **Relative-link linter & inventory/verify conventions** —
  `scripts/check-links.py`, `scripts/inventory.sh`, and the README
  "Inventory"/"Verify the install" sections. Conventions seen across
  [terrylica/cc-skills](https://github.com/terrylica/cc-skills) (MIT),
  [rohitg00/awesome-claude-code-toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit)
  (Apache-2.0), and
  [jeremylongshore/claude-code-plugins-plus-skills](https://github.com/jeremylongshore/claude-code-plugins-plus-skills)
  (MIT). Reimplemented from scratch.

See the [`scout-peers`](skills/scout-peers/SKILL.md) skill for the full peer
survey and the license-checking procedure used to vet every borrow above.
