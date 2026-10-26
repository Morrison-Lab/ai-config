# Create every new Morrison-Lab repository from its template

Before creating a repository in the Morrison-Lab organization, look for a template repository that matches it, and create the new repository from that template.
A plain `gh repo create` produces an empty repository that lacks the lab's workflows, checks, style files and macros submodule.

## Do

- List the templates first:
  `gh repo list Morrison-Lab -L 500 --json name,isTemplate --jq '.[] | select(.isTemplate) | .name'`
  (in a cloud session, the repository search `org:Morrison-Lab template:true`).
- Pick the template that matches the kind of repository:
  - `qwt` for a Quarto notes website.
  - `qbt` for a Quarto book.
  - `qmt` for a Quarto manuscript.
  - `qet` for a Quarto extension.
  - `rpt` for an R package.
  - `grt` for a grading repository (private, so a reviewer without access to it will not see it in a listing).
- Before creating from it, check the template for improvements:
  read its README, workflows, instructions and placeholder text, compare it with the newest repository made from it,
  and list the open issues and pull requests on the template.
  Fix what you find in the template through its own pull request, and drive it to fully clean.
  Create from the template once that pull request has merged, so every later repository gets the fix and not only this one.
  Merging it follows the usual merge policy: it needs the owner's merge words (or a standing grant that covers that repository), never an assumption.
  If it has not merged, create from the template anyway and keep the template pull request open alongside.
- Create from it:
  `gh repo create Morrison-Lab/<name> --template Morrison-Lab/<template> --private` (or `--public`).
- Name the template in the brief when a Remote Control session does the creating, because a cloud session cannot create organization repositories (it gets a 403).
- After creating, rename the site title, package name and URLs inside the copied files.
  Then pin any macros submodule the template carries at the current `Morrison-Lab/macros` main.
  The path differs by template:
  `latex-macros` in `qwt`, `macros` in `qbt`, `vignettes/macros` in `rpt`, and none in `qmt` or `qet`.

## Do not

- Do not run a plain `gh repo create` (or `--add-readme`) for a repository a template covers.
- Do not create an empty repository when no template matches.
  Create the missing template first (next section), then create the repository from it.

## When no template matches

Create a template repository first, then create the new repository from it.

- Model the template on the closest existing repository of that kind, with its files and checks but none of its content.
  A grading repository, for example, copies the folder layout and tooling of `mlg` and leaves out the course files.
- Create the template with `gh repo create Morrison-Lab/<template> --private --add-readme`,
  push the layout, and mark it as a template (`gh repo edit Morrison-Lab/<template> --template`).
  Make it public only if it holds no course, student or assessment material.
- Name templates like the others: a short code ending in `t` (`qwt`, `qbt`, `rpt`).
- Add the new template to the list in the Do section above.

## Repairing a repository created without a template

If the repository is still empty, copy the template's files into it through a pull request.
Do not delete and recreate it unless the owner asks.

(Owner rule, 2026-10-22: "always use templates", after two empty repositories were created in place of `qwt` copies.)
Owner rule, 2026-10-22: "and before using a template, first check for opportunities to improve the template".
Owner rule, 2026-10-22: "create a template first when none exists" (said about a grading repository, which had no template).

## Set a branch ruleset that follows the template's example

When you configure a repository, always give it a branch ruleset, and follow the example ruleset of the template it came from.
(Owner rule, 2026-10-22: "when configuring a repo, always set a ruleset, following the examples from the corresponding template repos (create such examples if missing)".)

- Each template carries its example as `.github/rulesets/main.json` with `.github/scripts/apply-rulesets.sh`.
  Templates with an example: `qwt`, `qbt` and `rpt`;
  `qmt`, `qet` and `grt` get theirs from [qmt#14](https://github.com/Morrison-Lab/qmt/pull/14), [qet#3](https://github.com/Morrison-Lab/qet/pull/3) and [grt#3](https://github.com/Morrison-Lab/grt/pull/3) (2026-10-22), and carry one once those merge.
- A template without an example gets one by its own pull request, modelled on the closest template that has one, before any repo is made from it.
  A repo with no template uses `examples/branch-rulesets/base.json`.
- Apply it with the template's `apply-rulesets.sh` (idempotent by ruleset name), or audit and apply across the org with
  `examples/branch-rulesets/apply-all.sh` (a dry run unless `--apply`).
- Naming repos on the command line restricts the run to those repos, so after an override run such as `mcs=qwt mcsg=grt --apply`, rerun `--apply` with no names, then a final dry run must show 0 `MISSING` (2026-10-22: 20 repos applied in two runs).
- Applying needs repo admin, which a cloud session lacks (403).
  Run it in a Remote Control session with the owner's typed go, and prepare the exact command in the brief.
- Never replace a live ruleset that is stricter than the example, and never add `required_status_checks` without reading the check-run names from a merged PR.

## Keep an R package and a notes site in separate repositories

Do not merge an R package (`rpt`) into a notes site (`qwt`), or the reverse, even when they cover one topic.
A notes site documents the topic and links to the package that supplies the code.
(Owner decision, 2026-10-22, on whether `Morrison-Lab/vds` and `Morrison-Lab/qnp` should be one repository, with "document this decision" as the instruction.
The answer was no.
See [ai-config#4674](https://github.com/Morrison-Lab/ai-config/issues/4674).)

- A site that uses the package installs it in CI, with an `owner/repo` line in its `r-packages` list.
  For example, [lds#1280](https://github.com/Morrison-Lab/lds/pull/1280) adds `Morrison-Lab/qnp` there.
  A merged repository would make every such site clone the other site's chapters, data and Quarto configuration to get one function.
- A package has checks and a release cycle that prose does not: a dev version bump, a `NEWS.md` bullet, and `R CMD check` on three operating systems.
  A merged repository would put both sets of checks on every change.
