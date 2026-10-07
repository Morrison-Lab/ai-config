---
name: send-notes
description: "Send content to Morrison-Lab notes repos."
user-invocable: true
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Grep
  - Glob
---

# send-notes --- Route and send content to Morrison-Lab notes repositories

Persist notes, principles, definitions, examples, derivations, or writing rules to the appropriate Morrison-Lab notes repository (`psw`, `rme`, `mds`, `lds`, `pds`, `sds`, `wai`, etc.) from any working session or repository.

## When this fires

- User says "send this to psw", "psw: ...", "/psw", "add this writing principle to psw"
- User says "send this to rme", "rme: ...", "/rme", "add this regression note to rme"
- User says "send this to mds", "/mds", "send this to lds", "/lds", "send this to pds", "/pds", "send this to sds", "/sds", "send this to wai", "/wai"
- A session generates an insight, teaching example, mathematical derivation, or style rule whose natural home is one of the Morrison-Lab notes or lecture books rather than the current working repo.

## Notes Repository Registry

Morrison-Lab maintains focused notes repositories, each with a standardized 3-letter shorthand:

| Shorthand | Target Repository | Scope / Topic | Typical Content |
|---|---|---|---|
| `psw` | `Morrison-Lab/psw` | Principles of Scientific Writing | Style guide for scientific writing, grammar, conciseness, defining terms, mathematical notation, avoiding AI tells, paper organization |
| `rme` | `Morrison-Lab/rme` | Regression Models for Epidemiology | Linear/logistic/Poisson/Cox regression, confounding, effect modification, model selection, survival analysis, epidemiology study designs |
| `mds` | `Morrison-Lab/mds` | Mathematics for Data Science | Linear algebra, multivariate calculus, optimization, matrix decompositions, vector spaces |
| `lds` | `Morrison-Lab/lds` (private) | Machine Learning for Data Science | Supervised and unsupervised learning, deep learning, classification, clustering, dimensionality reduction |
| `pds` | `Morrison-Lab/pds` | Probability for Data Science | Random variables, probability distributions, expectations, conditioning, joint distributions, limit theorems |
| `sds` | `Morrison-Lab/sds` | Statistics for Data Science | Statistical inference, point and interval estimation, hypothesis testing, likelihood theory, resampling, bootstrap |
| `wai` | `Morrison-Lab/wai` | Working with AI | Agentic workflows, prompting, LLM capabilities and failure modes, harness integration, AI-assisted development |
| `win` | `Morrison-Lab/win` | What If Notes | Causal inference, counterfactuals, DAGs, propensity scores, g-methods, target trials |
| `araomm` | `Morrison-Lab/araomm` (private) | Applied Regression Analysis | Lecture notes based on Kleinbaum et al., Applied Regression Analysis and Other Multivariable Methods |

*(Note: `cai` / `config-ai` routes AI configuration and agent policies to `ai-config`.)*

## Procedure

### 1. Identify Target Repository and Topic

Match the content to the appropriate notes repository using the registry above.
If the user invoked a specific shorthand (e.g. `/psw` or `/rme`), respect that choice.
If ambiguous (e.g. a statistical property of an ML estimator could fit `sds` or `lds`), choose the repository where the concept is primarily taught or ask the user with a recommended choice.

### 2. Locate Target Chapter or File

Examine the target repository structure to locate where the content fits:
- Check `_quarto.yml`, `_quarto-website.yml`, or `_quarto-book.yml` to understand the table of contents and chapter organization.
- Inspect the `chapters/` directory or root `.qmd` files.
- Determine whether the content:
  - Fits inside an **existing chapter** (e.g., adding a new section or callout to `chapters/defining-terms.qmd` in `psw`).
  - Merits a **new chapter or standalone note** (e.g., `chapters/<new-topic>.qmd`), which also requires updating the navbar/sidebar in the Quarto configuration.

### 3. Draft Content in Target Conventions

Follow the shared Morrison-Lab writing and technical standards:
- **Semantic Line Breaks (SemBr)**: One thought / sentence per line.
  Never reflow text into arbitrary line wraps.
- **LaTeX Math Macros**: When writing mathematical notation, use the shared semantic macros from `Morrison-Lab/macros` (e.g. `\E`, `\Prob`, `\Var`, `\Cov`, `\indic`, `\R`, etc., per `use-math-macros`).
- **Callout Enclosures**: Use GitHub or Quarto callouts (`> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, theorem/lemma environments) where appropriate.
- **Tone & Style**: Clear, pedagogical, direct, concise, avoiding passive voice and avoiding AI prose tells (per `find-ai-tells` and `psw`).

### 4. Deliver on a Dedicated Branch and PR

Never push directly to `main` of the notes repository.
Always isolate work on a dedicated branch and deliver via Pull Request:

#### Path A: Local Checkout / Worktree Available
If a local clone exists under `$HOME/Documents/GitHub/<repo>`:
```bash
repo_path="$HOME/Documents/GitHub/<repo>"
git -C "$repo_path" fetch origin main
# Create dedicated worktree
wt="$(mktemp -d)"
git -C "$repo_path" worktree add "$wt" -b notes/<slug> origin/main
# Make edits in $wt/...
git -C "$wt" add <files>
git -C "$wt" commit -m "docs(<topic>): <concise description of additions>"
# Push and open PR
git -C "$wt" push -u origin notes/<slug>
gh pr create --repo Morrison-Lab/<repo> --base main --head notes/<slug> \
  --title "docs(<topic>): <concise description>" \
  --body "<summary of content added>"
# Keep worktree intact while driving PR through review; clean up after merge.
```

#### Path B: Remote / GitHub API / Temporary Clone
If working remotely or without an existing local checkout:
```bash
# Clone shallowly into a temporary directory
tmp_dir="$(mktemp -d)"
git clone --depth 1 https://github.com/Morrison-Lab/<repo>.git "$tmp_dir"
cd "$tmp_dir"
git checkout -b notes/<slug>
# Apply edits to the relevant .qmd file(s)
git add <files>
git commit -m "docs(<topic>): <concise description of additions>"
git push -u origin notes/<slug>
gh pr create --repo Morrison-Lab/<repo> --base main --head notes/<slug> \
  --title "docs(<topic>): <concise description>" \
  --body "<summary of content added>"
```

### 5. Drive PR to Clean (ARDI)

- Ensure the PR description follows lab conventions and agent disclosure footer:
  `_Posted by <Agent Name> (AI agent) --- not written by a human._`
- Run local formatting / link checks if tooling is present.
- Monitor automated checks and drive review to clean.

### 6. Wrap Up

- Once the PR is merged into `main`, remove any temporary worktree or clone:
  `git -C "$repo_path" worktree remove "$wt"` (or `rm -rf "$tmp_dir"`).

## Relationship to other skills

- **`push-memory`**: Routes general-purpose AI agent memories and rules to `ai-config`.
- **`config-ai` (`cai`)**: Routes AI capability and infrastructure requests to `ai-config`.
- **`use-math-macros`**: Standardizes LaTeX macros across all notes repos.
- **`sembr-reformat`**: Formats prose to semantic line breaks.
- **`find-ai-tells`**: Audits drafts for AI-generated stylistic tells.

## Anti-patterns

- ❌ Pushing directly to `main` on a notes repository without a PR.
- ❌ Dumping unstructured raw text instead of properly formatted Quarto (`.qmd`) sections.
- ❌ Inventing ad-hoc LaTeX math symbols instead of using shared macros from `Morrison-Lab/macros`.
- ❌ Modifying unrelated chapters or files in the target notes repository.
- ❌ Forgetting to update `_quarto.yml` / `_quarto-website.yml` when adding a brand new chapter file.
