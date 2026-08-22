# d-morrison/gha reusable workflows

Check `d-morrison/gha` before writing bespoke CI --- it has reusable workflows for common patterns.

Split out of [`github-actions.md`](github-actions.md) (ai-config#1680) at the 1200-line memory-file gate.
Generic Actions-authoring material stays there.

- **`quarto-publish.yml`** --- sets up Quarto, renders, and deploys the site.
  Caller stub is ~12 lines.
  See `examples/quarto-publish.yml` in the gha repo.
  **`@v1` vs `@v2` differ in HOW they deploy, and the two are mutually exclusive at the repo-Pages-source level:**
  - **`@v1`** deploys via the Pages **artifact** (`actions/upload-pages-artifact`
    + `actions/deploy-pages`).
      Repo setup: Settings → Pages → Source = **"GitHub
    Actions"**.
    No `gh-pages` branch served.
  - **`@v2`** (gha#118) deploys to the **`gh-pages` branch** (`JamesIves/github-pages-deploy-action`, `clean-exclude: pr-preview/`, plus a `.nojekyll`).
    Repo setup: Settings → Pages → Source = **"Deploy from a branch", `gh-pages` / `(root)`**.
    Caller grants `contents: write` (not `pages:write` + `id-token:write`), **even with `deploy: false`** (see the reusable-workflow permission rule in [`github-actions.md`](github-actions.md)).
  - **WHY the switch:** the gha PR-preview family (`preview-deploy`, `cleanup-pr-previews`) pushes previews to the `gh-pages` branch.
    A repo serves Pages from **one** source, so Actions-artifact publish + branch-based previews can't coexist --- under Actions-source Pages, every `…/pr-preview/pr-N/` link 404s.
    `rossjrw/pr-preview-action` REQUIRES branch-based Pages.
    So a repo that wants both a main site AND PR previews must use `@v2` + branch Pages.
  - **Branch-served Quarto needs `.nojekyll`** at the gh-pages root, or Jekyll strips Quarto's `_`-prefixed asset dirs.
    `quarto publish gh-pages` adds it automatically; `JamesIves` does not, so `@v2` touches one in before deploy.
  - **Private Pages repositories can receive an opaque `*.pages.github.io` hostname instead of `<owner>.github.io/<repo>`.**
    Read the authoritative URL from `gh api repos/<owner>/<repo>/pages --jq .html_url`.
    Pass only the bare hostname to `rossjrw/pr-preview-action`'s `pages-base-url`
    input because the action prepends `https://`; passing a full URL produces
    `https://https://...` preview links.
    Quarto's `website.site-url` still takes the complete `https://.../` URL.
  - **The repo's Pages *source* is a manual setting** --- not changeable via the MCP tools or (in scoped sessions) the API.
    Hand the flip to the user,
    and order it safely: deploy to `gh-pages` FIRST (populates root;
    live site keeps serving the old artifact), THEN flip the source, or the root 404s in between.
- **`lint-changed-lines.yml@v2`** (gha#276) --- runs `lintr` on changed R files but filters the reported lints down to only the lines a PR **adds or modifies**, so a repo can adopt or tighten a lint rule *incrementally*: new and edited code must comply while untouched legacy code is left alone.
  This is the answer to "a linter version bump (e.g. lintr 3.4.0's `indentation_linter` now matching the current tidyverse single-indent style) flags the whole repo" --- don't disable the linter or reformat everything at once;
  adopt via this workflow and let the rule migrate file-by-file as code is touched.
  Caller stub is ~8 lines (`uses: d-morrison/gha/.github/workflows/lint-changed-lines.yml@v2`).
  Implementation detail worth knowing when debugging false negatives: the reusable workflow checks out `github.event.pull_request.head.sha` (NOT the default `refs/pull/N/merge` ref) so on-disk line numbers match the head-relative line numbers in the GitHub "list PR files" `patch` field.
  serocalculator#564 is the first consumer.
- **Convention:** ai-config (and d-morrison repos generally) call `d-morrison/gha` reusable workflows with `@v1` (not a SHA-pinned ref).
  SHA-pinning is the pattern for third-party actions only.
- **gha's major tag slides ONLY on a manual `workflow_dispatch`, NOT on every merge to main**
  (`slide-major-tag.yml`; `on: workflow_dispatch:` only, gated `if: github.ref == 'refs/heads/main'`).
  It re-points the major derived from the latest `vX.Y.Z` tag to HEAD when dispatched.
  So merging a fix or a new capability to `main` does **not** roll it out to `@v1`/`@v2` consumers on its own --- the tag stays put until someone runs the workflow.
  This is deliberate (the workflow's own header comment: "the slide is a deliberate manual step, not an automatic reaction to every push" --- merge, optionally canary a consumer at `@main`, then dispatch once confident).
  Practical consequence: after merging a PR that adds/fixes a capability, a consumer PR that calls it at `@v2` keeps running the **pre-merge** tagged version until the human dispatches the slide --- the same "can't self-verify before merge" bootstrapping gap gha's own `CLAUDE.md` describes, but persisting *after* merge too until the dispatch.
  (serocalculator#564 called gha's new `lint-changed-lines.yml@v2` right after gha#276 merged;
  it only picked up the real capability once the user manually dispatched `slide-major-tag`.)
  Because the slide is manual, a **breaking** change merging to main does NOT silently slide `v1` onto it --- but when you DO dispatch after a breaking change, guard it with TWO tag moves so the slide doesn't break `v1`: (1) force `v1` back to the last non-breaking commit (`git tag -f v1 <sha>; git push --force origin refs/tags/v1`), and (2) create `v2.0.0` + `v2` at HEAD.
  Once `v2.0.0` exists it's the latest semver, so the slide moves `v2` thereafter and `v1` stays frozen.
  There is NO MCP tool to create tags/releases --- use `git` (but see the 403 caveat below).
  Notify registered consumers in `REVDEPS.md` (e.g. `Lacaedemon/sparta`).
- **`@v1` can trail `main` in practice --- verify against the TAGGED file, not `main` or `examples/`.**
  Observed: `main`'s `claude.yml` / `claude-code-review.yml` both declare an `ANTHROPIC_API_KEY` secret in their `workflow_call: secrets:` block, and `examples/claude.yml` / `examples/claude-code-review.yml` (also on `main`) show passing it --- but the `@v1` tag's copy of both reusable workflows only declares `CLAUDE_CODE_OAUTH_TOKEN`, `SUBMODULES_TOKEN`, and (for `claude.yml`) `WORKFLOW_TOKEN`.
  A caller that copies the example verbatim and pins `@v1` gets a `startup_failure`: `Invalid secret, ANTHROPIC_API_KEY is not defined in the referenced workflow.` Before trusting an `examples/` template (or `main`'s workflow file) for a `secrets:`/`with:` block passed to an `@v1` call, fetch the actual `@v1`-tagged file (`mcp__github__get_file_contents` with `ref: refs/tags/v1`, or `git show v1:.github/workflows/<file>`) and diff its `workflow_call:` section against what you're about to pass.
  Filed as gha#179; worked around in `d-morrison/altdoc`#14 by omitting `ANTHROPIC_API_KEY` until `@v1` catches up.
- **A `workflow_call` reusable-workflow ref (`@v1`/`@v2`) resolves ONCE, at the run's original creation time, and stays pinned to that SHA across every re-run of that same run --- even after the tag has since moved to a fix.**
  So if a consumer PR's `claude-code-review.yml` run first ran while `@v2` still pointed at a broken gha commit, re-running that same run (whether via the Actions UI "Re-run failed jobs" or a bot re-dispatch that happens to target the existing run rather than creating a new one) reproduces the identical pre-fix failure forever, no matter how many times you retry or how long ago the tag was fixed.
  **Diagnose by checking `run_attempt`** (> 1 means this is a re-run, not a fresh dispatch) **and `created_at`** (`mcp__github__actions_get`, `method: get_workflow_run` --- compare against when the fix landed), then read `referenced_workflows[].sha` in the same response --- it shows the ACTUAL resolved commit for that run, which you can diff against the tag's current `get_tag` SHA to confirm staleness.
  **Only a genuinely NEW run (a new `run_id`) re-resolves the tag fresh** --- a new commit (`pull_request: synchronize`) is the reliable trigger;
  an `@claude review` comment sometimes causes the bot to re-run the existing stale run instead of dispatching a new one (observed on UCD-SERG/serodynamics#193 --- a direct `workflow_dispatch` via `actions_run_trigger` would have sidestepped this, but that call 403s in these sessions too, per the note above).
- **Testing a reusable workflow that calls `anthropics/claude-code-action` (a review or agent workflow) before merge is DOUBLY constrained -- a branch-pinned caller cannot exercise the change even when it runs.**
  Two independent mechanisms both defeat the obvious "point a caller at the test branch and dispatch it" approach:
  1. **The action's own workflow-validation guard refuses to run unless the CALLER's workflow file is byte-identical to that repo's DEFAULT branch** (`Workflow validation failed ... must exist and have identical content to the version on the repository's default branch`).
     A caller placed on a throwaway BRANCH therefore always fails validation and skips the review BEFORE it starts -- producing no execution output at all.
     This is the same guard `claude-review-dispatch.md` documents for the review-workflow repo itself, but it fires in **consumer** repos too, not just where the reusable workflow lives.
     To actually run it, the caller has to be on the default branch: add a throwaway dispatch-only caller workflow to `main`, `workflow_dispatch` it, then delete it.
     **Same guard, consumer PR, 2026-08-18 (2nd occurrence, gha#386):** Morrison-Lab/ai-config#1642 edited `.github/workflows/validate.yml` (not the review workflow).
     A `workflow_dispatch` of `claude-review.yml` skipped with a PR warning that token exchange refuses until that file matches the default branch.
     Re-dispatching does not lift it.
     - **Do:** self-review immediately, then start the *agent* workflow with a dedicated mention comment if an external verdict is still owed.
     - **Don't:** re-dispatch `claude-review.yml` hoping the skip comment was a one-off.
  2. **A nested `uses: <owner>/<repo>/.github/actions/<x>@v2` composite ref inside the reusable workflow resolves at its OWN literal `@v2`, independent of the ref the reusable workflow was called at.**
     GitHub resolves each full-path `uses:@ref` independently, so SHA/branch-pinning a consumer's caller to a test branch runs the workflow FILE at that branch but still pulls the composite actions at `@v2` (the old code).
     This is a different fact from the "resolves ONCE at run creation" bullet above (that one is about re-runs of one run;
     this is about which ref each nested reference picks up on a fresh run).
     To exercise a change that lives in a nested composite action, you must ALSO temporarily bump the reusable workflow's own internal `@v2` refs to the test branch -- scaffolding you revert before merge. (gha#400 test, 2026-08-03.)
- **`check-non-standard-chars` (the `chars` selftest job) scans only `.qmd` and `.R` files.**
  Em dashes / smart quotes in workflow YAML comments, README, or example stubs pass;
  the SAME character in a `.qmd` fails CI (`U+2014` etc.).
  When editing gha docs, keep `.qmd` ASCII (`-`/`;`, not an em-dash).
- **403 caveat --- scoped sessions can push ONLY the assigned branch.**
  Tag pushes are denied.
  In remote/web sessions the proxy rejects any ref that isn't the harness-assigned branch with `HTTP 403` --- including `refs/tags/*`.
  **`git push --dry-run` gives a FALSE POSITIVE here** (it prints `* [new tag] …` because the negotiation succeeds, but the real push 403s on the ref update).
  So you cannot cut tags from such a session --- hand the exact `git tag` + `git push` commands to the user instead.
  Don't retry the 403 (policy denial, not transient).
- **A session can be fully READ-ONLY on a repo --- even the harness-assigned branch can be unwritable.**
  Beyond the tag-push case above, some sessions 403 on every write path to a given repo: `git push` to the assigned branch itself (not just other branches --- and `git ls-remote` may show the assigned branch doesn't even exist on the remote yet, so the push 403s trying to create it), plus every GitHub MCP write tool --- `push_files`/branch creation, `create_or_update_file` (contents API), and `add_issue_comment` --- all returning `403 Resource not accessible by integration`.
  Confirm this conclusively by testing 2-3 *distinct* write endpoints (not just retrying the same one) before concluding read-only, since a single 403 could be a branch-scope issue (the case above) rather than a repo-wide one.
  Once confirmed: don't keep retrying --- package the diff as a patch (`git format-patch`) and hand it to the user via `SendUserFile` instead of a pasted diff, so it's directly `git am`-able.
  Because you can't push, watch for the user (or another session) to land an independently-derived fix rather than your literal patch ---
  re-verify the actual merged diff before reporting status rather than assuming your patch was applied as-is.
  (Hit on ucdavis/fxtas#156: diagnosed a CI-breaking dependency issue, delivered the fix as two patch files since every write 403'd;
  the user filed their own issue/PR with a different fix for the same root cause and merged that instead.)
- **Input-forwarding checklist when adding an input to a gha composite action.**
  Adding a new `inputs:` entry to `<name>/action.yml` requires four coordinated updates:
  1. Expose it in the wrapping reusable workflow (`.github/workflows/<name>.yml`) under `on: workflow_call: inputs:`.
  2. Forward it in the reusable workflow's `uses: d-morrison/gha/<name>@v1` step's `with:` block.
  3. Update `examples/<name>.yml` (the caller stub) if the input is consumer-visible.
  4. Update the README table row for `<name>.yml` to list the new input under "Key inputs".
  Missing any of these leaves the input wired only partway --- consumers can't pass it through the reusable workflow even though it exists in the composite.
  (Caught by Copilot on gha#92: `fail-if-empty` was in the composite but not in README or examples;
  a separate pre-existing gap --- the `fail` input --- was filed as gha#93.)
- **Reusable workflow input descriptions say "workflow run", not "action."**
  A `workflow_call` wrapper is not a composite action --- `inputs:` descriptions should say "Fail the workflow run …" not "Fail the action …".
  When copying an input description from `action.yml` into the wrapping `workflow_call` file, update "action" → "workflow run". (Fixed in gha#92: `fail-if-empty` description in `check-links.yml`.)
- **GitHub Actions job conclusions: no "skipped" from a running job.**
  A job that has started can only conclude `success` or `failure` --- never `skipped`.
  The only way to get the gray skip icon on a check is a false `if:` on an *unstarted* job.
  Pattern for infrastructure conditions (quota exhaustion, pre-flight failures): have the main job succeed (exit 0) and set an output flag, then add a second gate job whose `if:` is false when the flag is set.
  The gate job is what consumers watch in branch protection;
  it shows skipped (gray) on infra conditions and success on clean reviews.
  See gha#104 for the `require-review` job implementation.
- **`mcp__github__get_job_logs` usage.**
  Two calling modes --- use the right one:
  - Single job: pass `job_id` (number) + `return_content: true`.
    Do NOT pass `run_id` alongside.
    Without `return_content: true` the tool returns only a `logs_url` download link and `"Job logs are available for download"` --- no actual log text.
  - All failed jobs in a run: pass `run_id` (number) + `failed_only: true` + `return_content: true`.
    Do NOT pass `job_id`.
  The tool's error message ("job_id is required when failed_only is false") is misleading when you pass `failed_only: true` with `run_id`;
  the issue is actually conflicting parameters.
- **A small `tail_lines` on `get_job_logs` can silently miss the real failure** when the log contains a few enormous single-line entries (e.g. a base64-encoded spinner GIF/PNG being curled and embedded in a PR comment) --- the tool's "line" budget gets consumed by those giant lines before reaching earlier real steps, so `tail_lines: 60`/`120`/`300` can return only post-failure cleanup/reviewer-restore steps with no trace of the actual error.
  Escalate `tail_lines` (e.g. to 2000) and, once the result exceeds the token cap and gets saved to a file, grep/slice that file with `python3` (byte-offset search, not line-based) rather than trusting a small default tail.
  Cross-check with `mcp__github__actions_get` (`method: "get_workflow_job"` --- confirmed in the live schema alongside `get_workflow_run`) for the per-step `conclusion` breakdown to know which step actually failed and roughly where in the log to look. (ai-config#403.)
- **`get_job_logs` hard-caps the returned content at 5,000 lines regardless of `tail_lines`** --- a `tail_lines: 100000` request on a 14,503-line job log still returns only the last 5,000 lines.
  The result's `original_length` field reports the full line count, so compute the offset: returned line `i` (0-based) is full-log line `original_length - 5000 + i + 1`.
  There's no way to fetch the head through this tool, and the REST fallback (`/actions/jobs/{id}/logs`) needs `api.github.com`, which the agent proxy blocks in these sessions.
  A GitHub UI deep link `#step:N:L` means line `L` counted *within step N* (step N's first log line is 1), so locating it in the tail needs the step's start line --- estimable from the earlier steps' typical output volume when the head is unfetchable, and worth cross-checking against whether a plausible warning/error actually sits at the computed spot. (rme#1047: located a docx TeX-math warning this way at `#step:10:8366` of a truncated publish log.)
- **`claude-review` failing with "Skipping action due to workflow validation… must have identical content to the default branch" is NOT always the documented self-mod-skip or stale-`@v1`-tag drift.**
  Before assuming either, verify: diff the PR branch's own workflow files against current `origin/main` (`git diff origin/<branch> origin/main -- .github/workflows/`) --- if that's empty, the branch has zero drift and neither known cause applies.
  The actual failure can be a one-off transient GitHub API error unrelated to workflow content at all, e.g. a `502` "Unicorn" error page from `GET /repos/.../collaborators/<actor>/permission` during the action's actor-permission check --- visible only by reading the full job log (see the `tail_lines` note above), not from the top-level check-run message.
  Re-running (push a commit, since `actions:write` is usually unavailable --- see above) clears a transient 502 with no code change needed. (ai-config#403.)
- **`update-snapshots.yml@v1`** --- regenerates testthat snapshots, commits, and pushes.
  Supports `workflow_dispatch`, `/update-snapshots` PR comment (`pr-mode: true`), and auto-update before R-CMD-check (`ref: github.head_ref`).
  Pass system deps via `apt-packages`.
  Added in gha#103; bcs#226 is the reference caller.
