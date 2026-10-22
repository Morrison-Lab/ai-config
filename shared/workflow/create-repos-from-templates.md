# Create every new Morrison-Lab repository from its template

Before creating a repository in the Morrison-Lab organization, look for a template repository that matches it, and create the new repository from that template.
A plain `gh repo create` produces an empty repository that lacks the lab's workflows, checks, style files and macros submodule.

## Do

- List the templates first:
  `gh repo list Morrison-Lab --json name,isTemplate --jq '.[] | select(.isTemplate) | .name'`
  (in a cloud session, the repository search `org:Morrison-Lab template:true`).
- Pick the template that matches the kind of repository:
  - `qwt` for a Quarto notes website.
  - `qbt` for a Quarto book.
  - `qmt` for a Quarto manuscript.
  - `qet` for a Quarto extension.
  - `rpt` for an R package.
- Create from it:
  `gh repo create Morrison-Lab/<name> --template Morrison-Lab/<template> --private` (or `--public`).
- Name the template in the brief when a Remote Control session does the creating, because a cloud session cannot create organization repositories (it gets a 403).
- After creating, rename the site title, package name and URLs inside the copied files, and pin the `latex-macros` submodule at the current `Morrison-Lab/macros` main.

## Do not

- Do not run a plain `gh repo create` (or `--add-readme`) for a repository a template covers.
- Do not fall back silently to an empty repository when no template matches.
  Say that none matches, and ask which existing repository to model it on.

## Repairing a repository created without a template

If the repository is still empty, copy the template's files into it through a pull request.
Do not delete and recreate it unless the owner asks.

(Owner rule, 2026-10-22: "always use templates", after two empty repositories were created in place of `qwt` copies.)
