# GitLab CLI and Discussions API

`glab` and the GitLab Discussions API for inline MR comments.
Split out of [`github.md`](github.md) (ai-config#694 pattern) at the 1200-line gate.

## GitLab Discussions API (inline diff comments)
- Endpoint: `POST /projects/:id/merge_requests/:iid/discussions`
- For inline comments, include `position` object: `position_type: "text"`, `base_sha`, `head_sha`, `start_sha`, `new_path`, `old_path`, `new_line`
- Get SHAs from MR Versions API: `GET /projects/:id/merge_requests/:iid/versions` -> `[0].base_commit_sha`, `[0].head_commit_sha`, `[0].start_commit_sha`
- If the position is rejected (e.g., line not in diff), the API returns 400 --- handle gracefully

## glab (GitLab CLI)
- Installed via Homebrew (macOS) or system package manager --- verify with `which glab`.
- Authenticated on your GitLab instance --- run `glab auth status` to verify host and username
- Use for MR comments, pipeline checks, CI job logs, etc.
- **`glab` opens a pager (alternate buffer) too, most often on `glab api` and
  `glab issue list`.**
  [`gh-cli.md`](gh-cli.md) records the `gh` half --- there the pager *hangs*
  the agent terminal, where `glab` was seen garbling output instead --- and
  its `GH_PAGER=cat` fix, which does not reach `glab`.
  - **Do:** pipe through `| cat`, export `PAGER=cat`, or ask for JSON with
    the long `--output json`, which both commands accept.
  - **Don't:** write `-O json` for `glab api`; that shorthand exists only on
    `glab issue list` (`Unknown shorthand flag: 'O' in -O`).
  - **Don't:** write `--output-format json` anywhere.
    It is a *different* flag, not a deprecated spelling: on `glab issue list`
    it takes `details`, `ids`, or `urls`, and `glab api` has no such flag
    (`Unknown flag: --output-format`).
    The `glab issue list` half is the dangerous one, because it does not fail
    at all: `-F json` **exits 0 and prints the default `details` table**, so
    you get a table where you asked for JSON and nothing says so.
    Verified against `gitlab-org/gitlab`: `-F json` and `-F totallybogus`
    both print the same table `-F` prints when omitted, while `-F ids` prints
    bare IDs and `-O json` prints real JSON.
  - **Don't:** read an empty or garbled capture as the query having returned
    nothing --- the pager ate the output.
  Diagnose all of these from stderr's **message**, never its exit code.
  Run them against a named public project (`-R gitlab-org/gitlab`) rather
  than from a repo with no GitLab remote --- without one, every command here
  exits 1 for that reason alone, and only the text separates a rejected flag
  (`Unknown shorthand flag`) from a command that parsed fine and died later
  (`Unauthenticated`, or `Accepts 1 arg(s), received 0` when the endpoint
  path is missing).
  Any checkout with a GitLab remote shows the silent-success case above just
  as well; `-R` is simply what reaches it from one that has none.
  (`glab 1.106.0`, 2026-09-09; recovered from a 2026-06-22 stash, the one
  entry of thirteen whose content had never reached `main`.)
- `glab issue list --opened` is deprecated --- `--opened` is the default when `--closed` is not used.
  Just use `glab issue list` (no flag needed).
- `glab mr list` also defaults to open items, and the installed CLI may reject
  GitHub-style `--state opened` / `--state open` flags as unknown.
  - **Do:** run `glab mr list` and `glab issue list` without a state flag for
    open items; read each subcommand's `--help` before translating a `gh`
    command mechanically.
  - **Don't:** assume `gh ... list --state open` syntax transfers to `glab`.
- `GITLAB_TOKEN` **is** read and takes precedence over the stored config (per the official `glab` README, 2026-08-26) --- an unset or wrong value in the environment silently overrides a working `glab auth login` session.
  Absent that env var, `glab` falls back to its own config at `~/Library/Application Support/glab-cli/config.yml` (macOS path);
  other platforms use their own config-dir convention.
- **`glab api` has no `--jq` flag**, unlike `gh api`: passing one errors with `Unknown flag: --jq`.
  Pipe the raw JSON to `jq` separately instead: `glab api "projects/<id>" | jq '.default_branch'`.
  **2nd occurrence (2026-09-14, HACtions !56; 1st: 2026-08-06):**
  A pipeline-monitoring loop repeated the same unsupported flag until stopped and rewritten with a pipe.
  **3rd occurrence (2026-09-21, [abridge !103](https://hc2-gitlab.ucdmc.ucdavis.edu/health-analytics-core/abridge/-/merge_requests/103)):**
  A diagnostic query retried the unsupported flag once before switching to raw JSON output.
  **Do:** before running a copied or generated `glab api` command, scan its
  arguments for `--jq` and replace that flag with a separate `jq` pipeline.
  **Don't:** assume a command copied from `gh api` is valid for `glab api`.
- **Never inspect GitLab CI/CD variables with the project variables API in an
  agent-visible terminal.**
  On the HC2 self-hosted GitLab instance, measured
  2026-09-22, `GET /projects/<id>/variables` returned each variable's plaintext
  `value`, including values marked masked.
  Treat the endpoint response as secret material rather than configuration
  metadata: do not run it to enumerate keys, pipe it to a formatter, or include
  it in a diagnostic transcript.
  Audit variable names through the GitLab settings UI, or have a Maintainer
  perform a no-output administrative check; rotate any value emitted by a prior
  API inspection.
  Masking affects logs, not this API response, and variables available to an
  unprotected merge-request pipeline are readable by that pipeline's source
  code.
- **Treat GitLab CI job traces as credential-bearing material.**
  On HC2, observed 2026-09-23, `glab ci trace` rendered a runner
  `Downloading artifacts from coordinator` line with an opaque `token=` value,
  even though no CI variable was printed.
  Do not fetch or render raw traces in an agent-visible terminal without
  explicit authorization for that log.
  Diagnose from job metadata, pipeline status, and narrowly scoped artifacts
  first.
  Do not rely on a line-oriented redaction filter after fetching a trace:
  GitLab ANSI control sequences can split `token=` from its value and bypass
  that pattern.
  If a trace must be inspected under explicit authorization,
  remove ANSI escapes before scanning and redact before any terminal output.
- **A project CI/CD variable overrides a job-level YAML variable.**
  GitLab's documented variable-precedence order, checked 2026-09-23, places
  project variables above variables declared in `.gitlab-ci.yml`.
  An included job that must select its `CI_JOB_TOKEN` fallback therefore needs
  `before_script: unset NAME` for every higher-precedence alias it consumes;
  setting `NAME: ""` in the job YAML does not suppress a project variable.
  GitLab runs `before_script` and `script` in the same shell, so that unset
  reaches the inherited script.
  Recheck this behavior against
  <https://docs.gitlab.com/ci/variables/> when upgrading GitLab.
- **Use the paginated MR notes endpoint as the authoritative unresolved-inline-comment sweep.**
  `GET /projects/:id/merge_requests/:iid/notes` can return resolvable unresolved `DiffNote`s that a Discussions API sweep does not expose as an unresolved discussion.
  Filter every page on `.resolvable == true and .resolved == false`, then use the Discussions API only to locate and resolve the corresponding thread.
  Do not infer that there are no inline findings from an empty discussion-level timestamp filter.
- **Activate manual review jobs before waiting on a GitLab pipeline.**
  After each push, inspect the current pipeline's jobs rather than relying on
  the overall `running` status.
  If the review job is `manual`, play it through the Jobs API (for example,
  `POST /projects/:id/jobs/:job_id/play`) before starting the watcher.
  A pipeline can run its tests while leaving the review stage dormant.
- **A self-hosted GitLab instance on an institutional internal network may only resolve while on that network's VPN.**
  A DNS failure (`NXDOMAIN` / `no such host`) for the GitLab hostname, with ordinary internet DNS resolving fine otherwise, points at needing the VPN rather than a broader outage or sandbox restriction: `nslookup <host>` before and after connecting confirms it.
- Key commands:
  - `glab ci list` --- list pipelines
  - `glab ci get --pipeline-id <ID>` --- view pipeline details (non-interactive)
  - `glab ci create --branch <branch>` --- trigger a NEW pipeline (picks up upstream template changes)
  - `glab ci retry --branch <branch>` --- retries a JOB from the existing pipeline (per the official `glab ci retry` docs, 2026-08-26: its positional argument is a job, not a pipeline, and `--branch` only narrows which pipeline to search) --- with no job given it opens interactive job selection, and either way it does NOT pick up template changes.
  - `glab ci view <id>` --- `<id>` there is a BRANCH or tag, not a pipeline ID (per the official `glab ci view` docs, 2026-08-26);
    pass a pipeline with `--pipelineid`/`-p` instead.
    Also requires TTY; use `glab ci get` or `glab api .../trace` for a non-interactive pipeline view.
  - `glab api "/projects/<ID>/jobs/<JOB_ID>/trace"` --- get job log non-interactively
  - `glab mr note create <MR_IID> --message "..."` --- post MR comment
  - `glab mr list` --- list merge requests
  - `glab mr view <MR_IID>` --- view MR details (including inline pipeline/checks status)
  - `glab mr` has no `checks` subcommand --- query MR CI status via `glab ci status` or `glab mr view` (ai-config#2667 / #2670)
- GitLab CI & HACtions templates:
  - `docs_check`: runs `roxygen2::roxygenise()` and verifies no changes via `git diff-index HEAD -- man/ NAMESPACE DESCRIPTION`.
  - `version-check`: asserts that the package version in `DESCRIPTION` has been incremented beyond `main`.
  - Push vs comment review triggers: repos overriding `claude-review` with `rules: - when: never` suppress push-triggered reviews in favor of comment-triggered reviews.
    Request a review on the MR by posting `@claude review` (e.g. `glab mr note <MR_IID> -m "@claude review"`), which triggers the webhook `claude-respond` pipeline on `main`.
  - Blocking discussions: both automated review comments and `glab mr note create` create resolvable discussion threads.
    If the repository enables "All discussions must be resolved before merge", the MR cannot be merged until all threads are resolved.
    Sweep unresolved items using the paginated notes endpoint above (`.resolvable == true and .resolved == false`), then resolve the corresponding discussion thread with `glab api --method PUT "/projects/:id/merge_requests/:iid/discussions/:discussion_id" -f "resolved=true"`.
    To inspect non-inline or general discussion threads that also block merge, query `glab api "/projects/:id/merge_requests/:iid/discussions?per_page=100" | jq '.[] | select(.notes[0].resolved == false) | .id'`.
  - Shared runner capacity and pipeline queuing: pushing squash-merges to `main` triggers automated pipelines on `main` that can monopolize shared runners (e.g. `check-package`, `test_coverage`, `linting`, `docs_check`).
    Cancel redundant/queued pipelines on `main` with `glab ci cancel pipeline <ID>...` (or use the `cancel-superseded` skill for branch-scoped pipelines) so feature branch pipelines run without waiting in queue.
- GitLab CI job token allowlist:
  - When repo A's CI job needs API access to repo B, repo B must add A to its allowlist
  - `glab api --method POST "/projects/<TARGET_ID>/job_token_scope/allowlist" -f "target_project_id=<SOURCE_ID>"`
  - `include:` (for CI templates) works independently of the API allowlist
  - Check existing: `glab api "/projects/<ID>/job_token_scope/allowlist"`
  - For cross-project Git transport, do not interpolate `CI_JOB_TOKEN` into
    a remote URL.
    An authentication failure can echo a credential-bearing URL.
    Use a short-lived, mode-700 `GIT_ASKPASS` helper that reads the inherited
    job token, keep `GIT_TERMINAL_PROMPT=0`, disable shell tracing during
    authentication, and remove the helper on exit.
    Invoke Git with `LC_ALL=C` when the helper recognizes its username/password
    prompts, because Git localizes those prompt strings.
    (Measured 2026-09-23 while testing HACR access from `test.hac`.)
  - A GitLab personal, group, or project access token can authenticate Git over
    HTTPS as the password with any non-empty username when it has repository
    read access and authorization for the target.
    Use `oauth2` as the generic askpass username and preserve
    `gitlab-ci-token` for `CI_JOB_TOKEN`.
    (Verified against GitLab documentation on 2026-09-24 during review of
    HACtions MR !71.)
  - Unset inherited askpass credential aliases and Git prompt settings, then
    scope their replacements to each Git command instead of exporting them for
    a whole CI script block.
    Test that a later non-Git subprocess cannot inherit those values.
    (Learned from the 2026-09-24 independent review of HACtions MR !71.)
  - In shell, assigning an inherited exported variable preserves its export
    attribute.
    `unset` secret aliases before assigning them for command-local use, and
    test with those aliases pre-exported.
    (Learned from the 2026-09-24 independent review of HACtions MR !71.)
  - Do not materialize a token-backed HTTP header before the selected transport
    needs it.
    Construct it only in the archive-fetch branch so Git transport does not
    leave an unrelated plaintext credential file in the workspace.
    (Learned from the 2026-09-24 independent review of HACtions MR !71.)
  - Build a CI Git remote from `CI_SERVER_URL`, not `CI_SERVER_HOST`.
    The host drops the configured protocol, port, and any GitLab relative URL
    root, which breaks self-hosted instances outside default HTTPS.
    (Learned from the 2026-09-24 review of HACtions MR !71.)
  - A regression test for a CI-variable default must not set that variable in
    the test environment.
    Also assert the rendered YAML value when the default itself is contractual.
    (Learned from the 2026-09-24 review of HACtions MR !71.)
  - A shell test double must explicitly exit on an invariant failure unless it
    enables `set -e`.
    A bare `test` can be overwritten by a later successful command and leave a
    regression undetected.
    (Learned from the 2026-09-24 independent review of HACtions MR !71.)
  - A test for an environment override must set a contrasting ambient value.
    Inheriting the runner environment can mask removal of the override when its
    default already matches the expected value.
    (Learned from the 2026-09-24 independent review of HACtions MR !71.)
  - A credential-provider test must assert both the username and password.
    Include the case where multiple supported credentials are present to keep
    the intended precedence from silently regressing.
    (Learned from the 2026-09-24 independent review of HACtions MR !71.)
  - A Maintainer cannot always temporarily disable a target project's inbound
    scope for an access A/B.
    If `PATCH /projects/<ID>/job_token_scope` with `enabled=false` returns
    "Job token scope cannot be disabled ... enforced for the instance,"
    the setting is instance-enforced and only an instance administrator can change it.
    Verify the subsequent `GET` still reports
    `inbound_enabled: true`; do not retry the CI job under a claimed bypass.
    (Measured 2026-09-23 while diagnosing access from `test.hac` to HACR
    (`health-analytics-core/hacr`).)
  - Decode `access_level` with GitLab's versioned role mapping.
    In GitLab 19.0.2, `40` means Maintainer (`30` is Developer);
    verify effective access with `GET /projects/<ID>/members/all?query=<username>`
    or the corresponding group endpoint before ruling out a maintainer-only repair.
    (Measured 2026-09-23 while diagnosing HACR
    (`health-analytics-core/hacr`) job-token access.)

## GitLab returns 404, not 403, for a project the token cannot SEE

A `CI_JOB_TOKEN` or `GITLAB_TOKEN` call against a project the token lacks
visibility into returns a bare `404 Not Found`, not `403 Forbidden` ---
GitLab's REST API does not distinguish "doesn't exist" from "you can't see
it."
Same non-disclosure choice GitHub makes for its org-installations endpoint
(`github-consumer-ci.md`'s "A 404 from that endpoint is about the caller's
org ROLE").
So "404 on a file I can see exists in the repo/browser" is a **token-scope**
diagnosis, not a missing-file one --- re-scope or allowlist the token rather
than hunting for a renamed or moved path.

- **Do:** read a 404 from a project-scoped token as "this token cannot see
  that project" first, and check the CI job token allowlist or PAT group
  scope before assuming the file moved or was deleted.
- **Don't:** treat a 404 as proof a file is absent when a differently-scoped
  credential (browser session, group-level PAT) can read it fine.

(Measured 2026-09-02, `ucdavis/hac.sap`#38: `CI_JOB_TOKEN` against
`health-analytics-core/HACtions` got 403 --- `hac.sap` was not on HACtions'
job-token allowlist, a role/scope problem the status code named correctly.
The fallback `GITLAB_TOKEN` then got 404 for the exact same file, which
exists at both `v2` and `main` and reads fine under a token with group
access.
Same missing-access problem, two different credentials, two different
status codes on the one call --- 403 named the cause and 404 hid it.)

## A mutable `include: ref:` plus `allow_failure: true` breaks a consumer silently

`include:` pinning a shared CI template to a **tag** (`ref: v2`) rather than
a SHA means every push to that tag reaches every consumer immediately, with
no version bump and no consumer-side signal that anything changed.
When the consuming job also carries `allow_failure: true`, a break
introduced this way is invisible: the job fails, the pipeline still reads
green, and nothing tells anyone the job didn't run.

A job that never ran and a job that ran and found nothing produce the
identical pipeline color.
`allow_failure: true` is the right call for a genuinely flaky external
check, but it also converts every future upstream change into a silent
regression for anyone relying on that job's *output* (a posted review, a
security report) rather than just its exit code.

- **Do:** pin a shared CI template to a SHA, or an immutable
  `v2.3.1`-style tag, when consumers depend on a job's output rather than
  only its exit code.
- **Do:** treat `allow_failure: true` as scoped to exit-code flakiness, and
  add a separate signal (a required "did this job run" check, an assertion
  that a comment got posted) for a job whose product matters more than its
  status.
- **Don't:** read a green pipeline as proof every `allow_failure: true` job
  executed --- check the job's own log/conclusion, not just the pipeline
  color.
- **Don't:** read "nothing changed in this repo" as proof a CI job's
  behavior is unchanged when it `include:`s a moving upstream ref.

Mirror image of [`github-consumer-ci.md`](github-consumer-ci.md)'s "A moving
upstream tag can turn a consumer's default branch red with no local change"
--- there the moving tag makes the check itself loud (red, with no local
diff to explain it); here it makes the review job silent (green, with the
review simply missing), because `allow_failure: true` swallows the exit
code that would otherwise announce it.
Same underlying principle as [`fail-fast.md`](../shared/principles/fail-fast.md)'s
"found nothing vs never ran" (there for a shell `||`-chained check; here for
a CI job attribute).

(Measured 2026-09-02, `ucdavis/hac.sap`#38: `.gitlab-ci.yml` includes
`health-analytics-core/HACtions` at `ref: v2`.
HACtions added a new script dependency to `templates/claude.yml`'s
`claude-review` job on 2026-08-29; `hac.sap`'s own last relevant change was
2026-08-30 and needed nothing from it.
`v2` moved to include the new dependency, `claude-review`
(`allow_failure: true`) started failing to fetch the script, and the
pipeline stayed green throughout --- the MR simply stopped getting
reviewed, with no failed check anywhere to notice.)

(Measured 2026-09-21, [abridge !103](https://hc2-gitlab.ucdmc.ucdavis.edu/health-analytics-core/abridge/-/merge_requests/103), pipeline 9236; 2nd occurrence:
the allowed-to-fail manual `claude-manual` job 39259 failed before review
because `claude-review.sh` referenced the missing
`.gitlab/scripts/lib/review-tools.sh`; as in the first occurrence, the
pipeline remained successful with a warning.)
