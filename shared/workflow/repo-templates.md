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
- Before creating from it, check the template for improvements:
  read its README, workflows, instructions and placeholder text, compare it with the newest repository made from it,
  and list the open issues and pull requests on the template.
  Fix what you find in the template through its own pull request, merge it, and only then create from it,
  so every later repository gets the fix and not only this one.
  If a fix cannot merge first, create from the template anyway and open the template pull request alongside.
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
