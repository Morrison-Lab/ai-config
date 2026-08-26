# GitLab CLI and Discussions API

`glab` and the GitLab Discussions API for inline MR comments.
Split out of [`github.md`](github.md) (ai-config#694 pattern) at the
1200-line gate.

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
- No `GITLAB_TOKEN` env var --- glab uses its own config at `~/Library/Application Support/glab-cli/config.yml`
- **`glab api` has no `--jq` flag**, unlike `gh api`: passing one errors with
  `Unknown flag: --jq`.
  Pipe the raw JSON to `jq` separately instead:
  `glab api "projects/<id>" | jq '.default_branch'`.
- **A self-hosted GitLab instance on an institutional internal network may
  only resolve while on that network's VPN.**
  A DNS failure (`NXDOMAIN` / `no such host`) for the GitLab hostname, with
  ordinary internet DNS resolving fine otherwise, points at needing the VPN
  rather than a broader outage or sandbox restriction: `nslookup <host>`
  before and after connecting confirms it.
- Key commands:
  - `glab ci list` --- list pipelines
  - `glab ci get --pipeline-id <ID>` --- view pipeline details (non-interactive)
  - `glab ci create --branch <branch>` --- trigger a NEW pipeline (picks up upstream template changes)
  - `glab ci retry --branch <branch>` --- retries the EXISTING pipeline (does NOT pick up template changes)
  - `glab ci view <id>` --- requires TTY; use `glab ci get` or `glab api .../trace` instead
  - `glab api "/projects/<ID>/jobs/<JOB_ID>/trace"` --- get job log non-interactively
  - `glab mr note create <MR_IID> --message "..."` --- post MR comment
  - `glab mr list` --- list merge requests
  - `glab mr view <MR_IID>` --- view MR details
- GitLab CI job token allowlist:
  - When repo A's CI job needs API access to repo B, repo B must add A to its allowlist
  - `glab api --method POST "/projects/<TARGET_ID>/job_token_scope/allowlist" -f "target_project_id=<SOURCE_ID>"`
  - `include:` (for CI templates) works independently of the API allowlist
  - Check existing: `glab api "/projects/<ID>/job_token_scope/allowlist"`

