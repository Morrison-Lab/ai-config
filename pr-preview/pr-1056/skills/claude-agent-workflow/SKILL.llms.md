# claude-agent-workflow

Sets up or edits the `@claude` agent GitHub Actions workflow. Several moving parts in this file are load-bearing and easy to “simplify” by mistake — this skill documents what to preserve and why.

## Companion skill

For the read-only **PR review** workflow (`claude-code-review.yml`), use `claude-review-workflow`. This skill is for the **agent** workflow (`claude.yml`) that actually edits files in response to `@claude` mentions.

## When working on this file

Path: `.github/workflows/claude.yml`

## Load-bearing pieces (do not remove without a replacement)

### 1. Bot-actor `if:` filter

``` yaml
jobs:
  claude:
    if: |
      (github.event_name == 'issue_comment' && contains(github.event.comment.body, '@claude')) ||
      (github.event_name == 'pull_request_review_comment' && contains(github.event.comment.body, '@claude')) ||
      (github.event_name == 'pull_request_review' && contains(github.event.review.body, '@claude')) ||
      (github.event_name == 'issues' && (contains(github.event.issue.body, '@claude') || contains(github.event.issue.title, '@claude')))
```

The workflow `on:` block fires on *every* comment/review/issue. The `if:` filter narrows execution to events that explicitly mention `@claude`. Without it the agent would burn quota responding to noise.

### 2. Workflow-level concurrency block

``` yaml
concurrency:
  group: claude-${{ github.event.issue.number || github.event.pull_request.number || github.event.review.pull_request_url }}
  cancel-in-progress: false
```

**Why:** rapid `@claude` comments fired parallel runs that all tried to push to the same branch; the action’s `git-push.sh` refuses non-fast- forward pushes, silently dropping the loser-of-the-race’s work (PR \#706 on 2026-05-19 18:31–18:39 lost 2 of 4 runs this way). Serializing per-PR/issue with `cancel-in-progress: false` makes new comments queue behind the running session instead of racing. **Don’t switch to `cancel-in-progress: true`** — that would just throw away in-flight work.

### 3. Late-comment polling prompt

``` yaml
- uses: anthropics/claude-code-action@v1
  with:
    prompt: |
      You were triggered by an @claude mention in
      ${{ github.event_name }}. Address the request in that
      comment/issue/review.

      **Before declaring the task complete, check for additional
      @claude requests that arrived after the triggering event:**

      1. Fetch the latest issue/PR comments:
         `gh api 'repos/${{ github.repository }}/issues/${{ github.event.issue.number || github.event.pull_request.number }}/comments' --paginate`

      2. From the response, identify comments where ALL of:
         - `created_at` is strictly greater than the triggering
           comment's timestamp
         - body contains `@claude`
         - user.login is neither `claude[bot]` nor `github-actions[bot]`

      3. If any matching comments exist, address each one in this same
         session (in chronological order), then repeat from step 1.
         Stop when no new @claude comments remain.

      4. Push all commits before finishing.
```

The concurrency block alone prevents *parallel* races, but a long-running session can still miss a comment posted while it’s working. Polling fills that gap so a single session handles a whole burst of comments. The corresponding `Bash(gh api:*)`, `Bash(gh pr view:*)`, `Bash(gh issue view:*)` entries in the allowed-tools list are what let this step run.

### 4. Capture-then-detect-push pattern

``` yaml
- name: Capture PR head SHA before Claude
  id: head_before
  if: github.event.pull_request.number || github.event.issue.pull_request
  run: |
    SHA=$(gh api ...)
    echo "sha=$SHA" >> "$GITHUB_OUTPUT"

- name: Run Claude Code
  ...

- name: Re-request review and dispatch code review if Claude pushed commits
  if: always() && (github.event.pull_request.number || github.event.issue.pull_request) && steps.head_before.outputs.sha != ''
  run: |
    SHA_AFTER=$(gh api ...)
    if [ "$SHA_AFTER" != "$SHA_BEFORE" ]; then
      gh api -X POST repos/.../pulls/$PR_NUMBER/requested_reviewers -f "reviewers[]=d-morrison" || true
      gh workflow run claude-code-review.yml -f pr_number="$PR_NUMBER" || \
        echo "::warning::Could not dispatch claude-code-review.yml"
    fi
```

The post-step detects whether Claude actually pushed (comparing SHA before/after), re-requests `d-morrison` as reviewer, and dispatches `claude-code-review.yml` via `workflow_dispatch`. The dispatch is needed because `GITHUB_TOKEN`-driven pushes don’t fire `synchronize` events, so the review workflow wouldn’t auto-trigger otherwise.

### 5. stats-allowlist for WebFetch

``` yaml
- name: Build allowed-tools list from stats-allowlist
  id: tools
  run: |
    curl -fsSL https://raw.githubusercontent.com/d-morrison/stats-allowlist/main/allowlist.txt -o /tmp/allowlist.txt || ...
    WEBFETCH=$(tr -d '\r' < /tmp/allowlist.txt \
      | grep -v '^[[:space:]]*$' \
      | grep -v '^[[:space:]]*#' \
      | sed -E 's#^[[:space:]]*https?://##' \
      | sed -E 's#/.*$##' \
      | sed -E 's#[^A-Za-z0-9.-]+$##' \
      | tr '[:upper:]' '[:lower:]' \
      | grep -E '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$' \
      | sort -u \
      | sed 's#.*#WebFetch(domain:&)#' \
      | paste -sd, -)
    ...
```

The hostname-regex filter is **security-load-bearing**: anyone with push access to `d-morrison/stats-allowlist@main` can expand WebFetch scope on the next run here. The regex ensures even a tampered upstream entry can only widen WebFetch coverage, not inject other `claude_args` via `"` or shell metacharacters.

### 6. EPI202_TOKEN env exposure

``` yaml
env:
  EPI202_TOKEN: ${{ secrets.EPI202_TOKEN }}
```

Exposes the fine-grained PAT for the private `ucdavis/epi202` repo to the Claude subprocess. See `.github/copilot-instructions.md` → “Accessing the private `ucdavis/epi202` repository” for the usage pattern. If the secret isn’t set the variable is empty — no error.

### 7. Submodule checkout via `SUBMODULES_TOKEN`

``` yaml
- name: Checkout submodules
  run: |
    git config --global url."https://x-access-token:${{ secrets.SUBMODULES_TOKEN }}@github.com/".insteadOf "https://github.com/"
    git submodule update --init --recursive --depth 1
```

`latex-macros` and friends are private submodules that need a token with read access. The `SUBMODULES_TOKEN` URL rewrite is the cleanest way to pass it through `git submodule update`.

### 8. R+Quarto+renv setup chain

The agent needs to run `Rscript -e 'lintr::lint(...)'`, `Rscript -e 'spelling::spell_check_package()'`, and `quarto render <chapter>.qmd --to html` per the rme CLAUDE.md pre-commit checklist. The setup steps load:

1.  apt deps (`jags`, `poppler-utils`, `tesseract-ocr`, `maxima`, plus R build chain)
2.  `pip3 install --break-system-packages sympy`
3.  `r-lib/actions/setup-pandoc@v2`
4.  `r-lib/actions/setup-r@v2`
5.  `quarto-dev/quarto-actions/setup@v2` with `tinytex: true`
6.  `r-lib/actions/setup-renv@v2` with `cache-version: 1`

`cache-version: 1` should match `claude-code-review.yml` so they share the renv cache and warm setup costs are amortized across both workflows.

### 9. `claude_args: --allowed-tools` and the gh subset

``` yaml
GH_TOOLS='Bash(gh api:*),Bash(gh pr view:*),Bash(gh issue view:*)'
echo "allowed=Bash(Rscript *),Bash(quarto *),Bash(curl *),${GH_TOOLS},${WEBFETCH}" >> "$GITHUB_OUTPUT"
```

The gh subset is intentionally narrow — *read-only* gh commands for the late-comment polling step. Don’t expand to `Bash(gh *)` without thinking about what other gh subcommands you’re handing the agent (`gh pr merge`, `gh release create`, etc.).

### 10. In-thread replies to inline review comments

When the agent is triggered by a `pull_request_review_comment` (an inline comment on the diff), the prose-reply post-step should reply **in the review thread**, not as a detached top-level comment:

``` bash
BODY="$(printf '%s\n\n<sub>— posted by @claude post-step …</sub>\n' "$RESPONSE" "$RUN_URL")"
if [ "${{ github.event_name }}" = "pull_request_review_comment" ]; then
  if jq -n --arg b "$BODY" '{body: $b}' \
       | gh api --method POST \
           "repos/${{ github.repository }}/pulls/$ENTITY_NUMBER/comments/${{ github.event.comment.id }}/replies" \
           --input - >/dev/null; then
    exit 0
  fi
  echo "::warning::In-thread reply failed; falling back to a top-level comment."
fi
gh issue comment "$ENTITY_NUMBER" --body "$BODY" || echo "::warning::…"
```

- The replies endpoint is `POST /repos/{owner}/{repo}/pulls/{N}/comments/{id}/replies` with `{body}`; `id` is `github.event.comment.id`, `N` is the PR number (`ENTITY_NUMBER` resolves to it for this event).
- **Keep the top-level fallback** — the parent comment can be deleted between trigger and post, which would 404 the reply.
- Only branch for `pull_request_review_comment`. `issue_comment` (PR conversation), `pull_request_review` (review summary), and `issues` triggers all stay top-level — issue and PR-conversation comments share the same `/issues/{N}/comments` endpoint, and a review summary has no single line thread to anchor to.
- Pair with a prompt nudge so Claude writes a thread-appropriate reply (“…that reply is posted as a threaded reply to that exact comment — keep it focused on the line(s) that comment is about”). Added in qwt#93 / rme#833.

## Refactoring this file

If you’re tempted to “simplify” something, check this skill first to see if it’s load-bearing. Specifically, **don’t**:

- Drop the bot-actor `if:` filter (would let unrelated comments fire the agent).
- Change `cancel-in-progress: false` to `true` (would lose in-flight work on each new comment).
- Remove the polling prompt (would re-introduce the late-comment-dropped failure mode within a single long session).
- Replace the stats-allowlist hostname regex with `awk '{print}'` or similar (would let a tampered allowlist inject claude_args).
- Skip the SHA-before-and-after capture (would lose the auto-re-dispatch of `claude-code-review.yml` when Claude pushes).
- Merge the `Bash(gh api:*)` etc. allowlist into `Bash(gh *)` (would hand the agent gh’s mutating subcommands).

## Fallback: direct-CLI bypass when the action is broken

The official `anthropics/claude-code-action` has shipped intermittently broken auth — e.g. `anthropics/claude-code-action#1281`, where the `claude_code_oauth_token:` failed to propagate to the spawned Claude subprocess (crash at SDK init with `apiKey`/`authToken` null), and the action’s “Restoring .claude from origin/main” step wiped the documented file-based credential workaround too.

When the action itself is the blocker, replace it with a **direct-CLI workflow** that runs `claude` headless and does the action’s plumbing by hand. Reference implementation: `UCD-SERG/shigella`’s `claude.yml` (PR \#20 and follow-ups). Shape:

1.  **Install the CLI:** `npm install -g @anthropic-ai/claude-code@latest`.

2.  **Pre-write credentials** (no action left to wipe them):

    ``` bash
    jq -n --arg token "$OAUTH_TOKEN" \
      '{claudeAiOauth: {accessToken: $token, subscriptionType: "max"}}' \
      > "$HOME/.claude/.credentials.json"
    chmod 600 "$HOME/.claude/.credentials.json"
    ```

    Also export `CLAUDE_CODE_OAUTH_TOKEN` as a belt-and-suspenders backup.

3.  **Build a prompt** from the trigger event into a file, fencing the user message as data (see hardening note below).

4.  **Run headless:** `claude --print --max-turns 100 --allowed-tools '...' --disallowed-tools 'Bash(git push:*),WebFetch' < prompt.txt > out.md 2> >(tee stderr.log >&2)`.

5.  **Post a sticky comment** (create “working…”, then PATCH it with the result) and **push any commits** Claude made to the PR branch.

Trade-offs to call out when proposing this: you lose the action’s MCP GitHub tools (Claude falls back to `gh` via Bash) and its `.claude/CLAUDE.md` restore-from-main (so CLAUDE.md on the PR head is trusted — fine for a single-org repo with no untrusted PR authors, not for a public one).

**Pair the bypass with \[\[workaround-watcher\]\]** pointed at the upstream action issue, so the repo auto-PRs its way back to the simple official-action invocation once upstream is fixed — and keep that simple version committed as `.github/templates/claude-simple.yml`.

### Hardening nuggets from the bypass (some apply to the action path too)

- **Prompt-injection data-fencing** (bypass only — the official action already fences trigger content): wrap the user’s message in explicit `<<<USER_MESSAGE_START>>>` / `<<<USER_MESSAGE_END>>>` markers and tell Claude to treat everything inside as data, not instructions.

- **Staged-edits sweep before the HEAD-unchanged check** (applies to BOTH paths): Claude sometimes runs `git add` without `git commit`. Any push step that decides “no changes” by comparing `git rev-parse HEAD` to a recorded starting SHA will silently drop those staged edits. Sweep first:

  ``` bash
  if [ -n "$(git status --porcelain)" ]; then
    git add -A && git commit -m "@claude: auto-commit residual uncommitted changes"
  fi
  ```

  (shigella PR \#24.)

- **Failure diagnostics** (bypass only): capture stderr via `2> >(tee stderr.log >&2)` and, on failure, surface partial stdout + an stderr tail (byte-capped) in the sticky comment — turns an opaque red X into something debuggable.

- **Self-trigger guard:** a hidden marker in the bot’s own comments (`<!-- claude-cli-bot:sticky -->`) plus `&& !contains(<body>, 'sticky')` in the `if:` gate, so the agent can’t be re-triggered by its own output.

## Reference incident — PR \#706 burst, 2026-05-19

The user posted 4 rapid `@claude` comments on PR \#706 between 18:31:46 and 18:37:04. Without `concurrency:` and without the polling prompt:

| \#  | Trigger comment                           | Conclusion | Pushed?      |
|-----|-------------------------------------------|------------|--------------|
| 1   | “split observed-marginal-risk”            | success    | ✅           |
| 2   | “split causal-marginal-risk + others”     | success    | ❌ blocked   |
| 3   | “g-computation / predictive-margins defs” | success    | ❌ blocked   |
| 4   | “potential mean / probability”            | success    | ✅ (rebased) |

Two of the four runs silently lost their work. Both fixes (concurrency + polling) ship together — they cover different segments of the same failure mode.

## Relationship to other skills

- **`claude-review-workflow`** — the companion skill for the read-only PR review workflow; see “Companion skill” above.
- **`config-ai`** — the broader router: when a request is “change how the `@claude` bot behaves when invoked,” not “add something consumers’ CI can call,” `config-ai` hands off to this skill (or `claude-review-workflow`) rather than `skill-builder`/`agent-builder`.

Back to top
