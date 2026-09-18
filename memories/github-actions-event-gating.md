# Driving an action from an event it refuses

One topic, kept in its own file: a third-party action that hard-gates on
`ctx.eventName` can still be run from another event, because every input that
gate reads is caller-supplied through the environment.

Split out of [`github-actions.md`](github-actions.md), which keeps the generic
authoring material, at the 1250-line gate (ai-config#694 pattern).

## An action that hard-gates on the event name can still be driven from another event

A third-party action can refuse every event but the one it was written for,
before it reads any of its own inputs:

```js
// sanjay3290/jules-pr-reviewer, src/index.ts:37 (at the pinned SHA)
if (ctx.eventName !== 'pull_request') {
  core.setFailed(`Unsupported event: ${ctx.eventName}. Use on: pull_request.`);
  return;
}
```

That reads like a hard constraint on the trigger, and it usually gets treated
as one: the obvious conclusions are "this capability cannot be made
on-demand" or "fork the action".
Neither is necessary.
`@actions/github`'s `Context` hydrates itself entirely from environment
variables, so both halves of the gate are caller-supplied:

```js
if (process.env.GITHUB_EVENT_PATH) {
  if (existsSync(process.env.GITHUB_EVENT_PATH)) {
    this.payload = JSON.parse(readFileSync(process.env.GITHUB_EVENT_PATH, ...));
  }
}
this.eventName = process.env.GITHUB_EVENT_NAME;
```

Step-level `env:` on a `uses:` step does **not** override those.
GitHub documents `GITHUB_*` as reserved
(https://docs.github.com/en/actions/reference/workflows-and-actions/variables,
checked 2026-08-26):
"You can't overwrite the value of the default environment variables named
`GITHUB_*` and `RUNNER_*`."
The runner still *prints* the YAML `env:` values in the step log, so the wrap
looks applied.
Measured 2026-08-26 on
[run 32942088643](https://github.com/Morrison-Lab/ai-config/actions/runs/32942088643):
the `uses: sanjay3290/jules-pr-reviewer` step logged
`GITHUB_EVENT_NAME: pull_request` and then failed with
`Unsupported event: issue_comment`.
That was the wrap #857 shipped, and every `@jules` mention since has failed
the same way (#2280).

The override that actually reaches `Context()` is `env(1)` on a `run:` step
that starts `node dist/index.js` as a child.
`env(1)` sets the child's environment after the runner's reserved-name merge.
A workflow triggered by `issue_comment` can still present the action with
`pull_request` this way.
For a `pull_request` gate the payload is close to one API call, because
`GET /repos/{owner}/{repo}/pulls/{n}` returns nearly the shape the event
delivers --- near enough to work, not near enough to skip the field check
below:

```yaml
      - name: Resolve the PR into a pull_request event payload
        run: |
          gh api "${{ github.event.issue.pull_request.url }}" \
            | jq '{pull_request: .}' > "$RUNNER_TEMP/pr_event.json"

      - name: Fetch the action at the pinned SHA
        run: |
          dest="$RUNNER_TEMP/the-action"
          git init --quiet "$dest"
          git -C "$dest" remote add origin https://github.com/owner/the-action.git
          git -C "$dest" fetch --depth 1 origin <sha>
          git -C "$dest" checkout --quiet --detach FETCH_HEAD

      - name: Run the action under a synthetic pull_request event
        env:
          INPUT_SOME_INPUT: value
          SYNTHETIC_EVENT_PATH: ${{ runner.temp }}/pr_event.json
          ACTION_DIR: ${{ runner.temp }}/the-action
        run: |
          env \
            GITHUB_EVENT_NAME=pull_request \
            GITHUB_EVENT_PATH="$SYNTHETIC_EVENT_PATH" \
            node "$ACTION_DIR/dist/index.js"
```

`action.yml` defaults are applied only by a `uses:` step.
A `run: node dist/index.js` invocation must set every `INPUT_*` the JS reads,
including the ones a `uses:` step would have inherited.

Two things make this safe rather than merely clever, and both need checking
before relying on it:

- **Read the action's own source for what it consumes past the gate**, and
  confirm the synthesized payload covers it.
  Everything after the gate in the case above read only the `pull_request`
  object, so nothing else had to be faked.
  A field the action reads and the API omits is the failure this check
  catches; `labels` was the near-miss, and it survived only because the action
  guards it as `(pr.labels || [])`.
- **`ctx.repo` is unaffected**, since it prefers `GITHUB_REPOSITORY`, which
  Actions always sets.

Note what the override does **not** change: the token's permissions, and the
security properties of the real trigger.
An `issue_comment` run executes in the base repo with a write token even for a
fork PR, so a gate the original event enforced implicitly (fork PRs get no
secrets under `pull_request`) has to be re-established explicitly.

- **Do:** read the pinned action's own code for how it reads `eventName` and
  `payload` before concluding its trigger is fixed --- `src/` for a legible
  version of the gate, and `dist/` to confirm what the pinned SHA actually
  runs, since the bundle is what Actions executes and it can lag `src/`.
- **Do:** invoke the action from a `run:` step with `env(1)` setting
  `GITHUB_EVENT_NAME` and `GITHUB_EVENT_PATH` on the node child, and set
  every `INPUT_*` the JS reads because `action.yml` defaults will not apply.
- **Do:** pin Node to the interpreter GitHub actually runs for that
  `runs.using`, not the label in `action.yml`.
  Measured 2026-08-26 on run 32942088643:
  this action declares `node20` and was forced onto Node 24.
- **Do:** write `success()` on wrap steps even though GitHub auto-applies
  it when `if:` has no status-check function.
  The could-not-start notifier uses `failure()`, which overrides that
  default, and a copy onto the node step would spawn node after a failed pin.
- **Do:** keep wrap preflight (`test -f` on the synthetic payload and the
  bundle) in its own step so a "could not start" comment can gate on it.
  Assertions left on the `jules` step fail before the process assigns
  `commentId`, and the notifier that excludes that step will not fire.
- **Do:** gate a wrap checker on the `node ... dist/index.js` invocation
  line, not a substring comments also contain.
- **Don't:** spawn `env` from Python without `shutil.which("env")`.
  Windows Python outside Git Bash has no `env` on PATH, so the call raises
  `FileNotFoundError` before the suite can print its tally, and local
  pre-commit goes red while ubuntu CI stays green.
- **Don't:** set `INPUT_RULES_FILE` to a path and then comment that the
  rules-file input is deliberately unused.
  The empty string is the documented disable value.
- **Do:** fetch a checker at the SHA the calling workflow **pins** when
  reproducing a diff-scoped CI gate locally, not the action's default branch.
  The first Do pins when *auditing* an action; the same applies when
  *running* one to validate a fix pre-push, where a shallow default-branch
  clone yields a plausible script with no sign it is the wrong one.
  Measured 2026-08-19: `ai-config`'s `validate.yml` pins
  `Morrison-Lab/gha/.github/workflows/check-new-line-breaks.yml@209bfb76`,
  whose `check-new-line-breaks.py` differs from that repo's default branch by
  **339 lines**, so validating against the default branch would have exercised
  a different checker and reported a result about nothing.
  Run `git fetch --depth 1 origin <sha>`, then `git diff --stat FETCH_HEAD --
  <subdir>/` (empty output means the pin is current) *before*
  `git checkout FETCH_HEAD -- <subdir>/`, which makes that question
  unanswerable.
- **Do:** re-derive any safety property the original event was providing for
  free, once the event is synthesized.
- **Don't:** fork an action, or abandon the feature, on the strength of an
  `eventName` guard alone.
- **Don't:** assume the API response is a drop-in payload without checking
  every field the action reads.
- **Don't:** treat a `uses:` step's logged `env:` as evidence the process
  received those values --- reserved `GITHUB_*` names are printed and then
  ignored.

(Morrison-Lab/ai-config#857, 2026-07-30: making the Jules reviewer on-demand
needed an `issue_comment` trigger, which its pinned action rejects outright.
Both files were read at the pinned SHA rather than assumed --- `src/index.ts`
for the gate quoted above, `dist/index.js` for the `Context` constructor that
makes the override work --- and then this PR's own API object, for field
coverage.
The line number above was `:38` when first written, and a review round caught
it: it is `:37`.
Worth noting how, since it is the cheap lesson here.
The reviewer inferred the citation was unverifiable because the case note named
only `dist/`, which was the wrong reason --- but a `grep -n` settled the real
question in one command, and the same off-by-one had already shipped into the
workflow comment that makes the same claim.
The wrap this case shipped --- YAML `env:` on the `uses:` step --- did not
work.
Measured 2026-08-26 on run 32942088643 / #2280: the step logged the override
and the action still saw `issue_comment`.
The working form is `env(1)` around `node dist/index.js`, recorded in
`.github/workflows/jules-review.yml` and gated by
`scripts/check-jules-review-workflow.py`.)
