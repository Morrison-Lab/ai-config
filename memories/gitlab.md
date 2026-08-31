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
  - Blocking discussions: `glab mr note create` creates a resolvable discussion thread.
    If the repository enables "All discussions must be resolved before merge", the MR cannot be merged until the thread is resolved via `glab api --method PUT projects/:id/merge_requests/:iid/discussions/:discussion_id -f "resolved=true"`.
- GitLab CI job token allowlist:
  - When repo A's CI job needs API access to repo B, repo B must add A to its allowlist
  - `glab api --method POST "/projects/<TARGET_ID>/job_token_scope/allowlist" -f "target_project_id=<SOURCE_ID>"`
  - `include:` (for CI templates) works independently of the API allowlist
  - Check existing: `glab api "/projects/<ID>/job_token_scope/allowlist"`
