# SUP — Send to Upstream

File an issue or open a PR on an upstream repository — a fork’s parent, a dependency, or any external project where you’ve found a bug, want to propose a fix, or need to request a feature.

## When this fires

- User says “sup”, “send upstream”, “file upstream”, “report this upstream”
- User says “contribute this fix back”, “open a PR on ”
- User says “file a bug on ”, “upstream issue for this”
- After discovering a bug in a dependency during normal work
- After implementing a workaround that should really be fixed at the source

## Step 0 — read the repo’s contribution policy first (do this BEFORE drafting)

The upstream repo is not ours; its rules bind us, and ignoring them can get the user’s account **banned**. Before drafting a title or body, read:

- **`CODE_OF_CONDUCT.md`** — some projects (e.g. `quarto-dev/quarto-cli`) **ban issues/PRs from autonomous AI agents acting without human oversight** and treat it as **account-bannable on first offense**. If the repo bans AI-agent submissions, **stop — do not file.** Give the user the draft and let *them* decide whether to submit it themselves.
- **`CONTRIBUTING.md`** + **issue/PR templates** (`.github/ISSUE_TEMPLATE/`, `.github/PULL_REQUEST_TEMPLATE.md`) — follow the required template and fill in every required field instead of the generic bodies below.
- **Destination.** Many projects route **feature requests and questions to a Discussions board**, not the issue tracker. Honor that — file in Discussions when the guidelines say so; reserve the tracker for what it’s meant for.

Pull these via the GitHub MCP `get_file_contents` (remote) or `gh api repos/<owner>/<repo>/contents/<path>` / a quick clone (local). If a required check can’t be read, say so and ask the user rather than guessing.

This is in addition to — not a replacement for — the human-approval gate in steps 3A/3B below.

## Determine the action type

| Situation | Action |
|----|----|
| Bug report, feature request, question — no code to contribute | **Issue** (or **Discussion**, if the repo routes it there) |
| You have a fix ready (patch, config change, doc fix) | **PR** |
| You have a fix but aren’t sure upstream wants it | **Issue first**, mention you have a fix ready |
| Fork divergence — your fork has improvements the parent should get | **PR** |

If unclear, ask the user: “Issue (report only) or PR (with fix)?”

## Procedure

### 1. Identify the upstream repo

Try these in order:

``` bash
# Fork parent (GitHub)
gh repo view --json parent --jq '.parent.owner.login + "/" + .parent.name'

# Fork parent (GitLab)
glab repo view --output json | python3 -c "import json,sys; r=json.load(sys.stdin); print(r.get('forked_from_project',{}).get('path_with_namespace',''))"

# Dependency — user must specify or you infer from context
# e.g., "the bug is in rlang" → "r-lib/rlang"
```

If you can’t determine the upstream repo, ask the user.

### 2. Verify access

``` bash
# Can you push/PR to this repo?
gh repo view <owner>/<repo> --json viewerPermission --jq '.viewerPermission'
# WRITE or ADMIN → can PR directly
# READ → fork first, then PR from fork
```

### 3A. File an issue (report-only path)

Gather from context: - **Title**: short, specific, imperative. “X breaks when Y” not “Problem with Z” - **Description**: what happens, what should happen, how to reproduce - **Environment**: version of the package/tool, OS, relevant config - **Minimal reprex**: if you have one (prefer `reprexes` skill output) - **Workaround**: if you have one, mention it — helps others and shows you’ve investigated

**Show the full draft (title + body) to the user and wait for explicit approval before posting.** Output the text as a markdown block, then ask “OK to post?” Do NOT run `gh issue create` until the user confirms.

``` bash
gh issue create --repo <owner>/<repo> \
  --title "<title>" \
  --body "<body>"   # CREATE_ISSUE
```

Or for GitLab:

``` bash
glab issue create --repo <owner>/<repo> \
  --title "<title>" \
  --description "<body>"
```

After filing, report the issue URL back to the user.

### 3B. Open a PR (fix path)

**Show the full draft (title + body) to the user and wait for explicit approval before running `gh pr create`.** Same rule as issues — draft first, post after “OK.”

#### If you have push access (collaborator/org member):

``` bash
# Clone or add remote
git remote add upstream https://github.com/<owner>/<repo>.git 2>/dev/null || true
git fetch upstream   # FETCH

# Branch from upstream's default branch
git checkout -b fix/<slug> upstream/main  # CREATE_BRANCH — or upstream/master, upstream/develop

# Apply your fix (copy from local workaround, write fresh, cherry-pick)
# ... make edits ...

git add -A && git commit -m "<conventional commit message>"   # COMMIT
git push upstream fix/<slug>                                   # PUSH

# Open PR
gh pr create --repo <owner>/<repo> \
  --base main \
  --head fix/<slug> \
  --title "<title>" \
  --body "<body>"   # CREATE_PR
```

#### If you need to fork first:

``` bash
# Fork (idempotent — won't re-fork if already forked)
gh repo fork <owner>/<repo> --clone=false

# Your fork is now at <your-username>/<repo>
gh repo clone <your-username>/<repo> /tmp/upstream-fix
cd /tmp/upstream-fix

# Branch, fix, commit, push to YOUR fork
git checkout -b fix/<slug>   # CREATE_BRANCH
# ... make edits ...
git add -A && git commit -m "<conventional commit message>"   # COMMIT
git push origin fix/<slug>                                     # PUSH

# Open PR from your fork to upstream
gh pr create --repo <owner>/<repo> \
  --base main \
  --head <your-username>:fix/<slug> \
  --title "<title>" \
  --body "<body>"   # CREATE_PR
```

### 4. Link back to local context

After filing the upstream issue/PR:

- If you have a local workaround, add a comment in the code: `# WORKAROUND: upstream <owner>/<repo>#<N> — remove when fixed`
- If you used `workaround-watcher`, set it to watch the new issue/PR
- If you deferred from a local MR review, update the ARD summary with the upstream issue link

### 5. Report to user

Provide: - The upstream issue/PR URL (clickable markdown link) - What was filed (issue vs PR, title) - Any next steps (watch for response, set up workaround-watcher, etc.)

## PR body template

``` markdown
## Problem

<What's broken / missing — 2-3 sentences>

## Reproduction

<Minimal steps or reprex>

## Fix

<What this PR does — 1-2 sentences>

## Notes

- Found while working on <context> in <your-repo>
- Currently working around this with <workaround description>
```

## Issue body template

``` markdown
## Problem

<What's broken / missing>

## Reproduction

<Minimal steps, version info, reprex>

## Expected behavior

<What should happen instead>

## Workaround

<If you have one — helps others and shows investigation>

## Environment

- Package version: X.Y.Z
- R/Python/Node version: ...
- OS: ...
```

## Relationship to other skills

- **`prefer-upstream`** — discovers that an upstream solution exists; `sup` contributes fixes back to it
- **`workaround-watcher`** — watches an upstream issue for resolution; `sup` creates that upstream issue in the first place
- **`defer-issue`** — files issues on YOUR repo; `sup` files on THEIR repo
- **`reprexes`** — creates minimal examples; `sup` includes them in the upstream report

## Anti-patterns

- ❌ Filing **autonomously, without the user’s explicit approval** — every upstream submission needs the human contributor to review and verify it. Some repos’ Codes of Conduct make unattended AI-agent submissions account-bannable on first offense.
- ❌ Filing **before reading the repo’s `CODE_OF_CONDUCT.md` / `CONTRIBUTING.md` / templates** — you can’t file correctly without knowing the rules.
- ❌ Filing a **feature request as an issue** when the project routes feature requests to a **Discussions** board.
- ❌ Posting a **free-form body when the repo provides an issue/PR template** — use the template and fill in every required field.
- ❌ Filing a vague issue (“something is broken”) — always include a reprex or clear reproduction steps
- ❌ Sending a massive PR that mixes your fix with unrelated changes — keep it minimal and focused
- ❌ Not mentioning your workaround — upstream maintainers appreciate knowing the impact and that you’ve investigated
- ❌ Filing on the wrong repo (e.g., filing on a mirror instead of the canonical source)

Back to top
