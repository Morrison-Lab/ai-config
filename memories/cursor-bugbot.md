# Cursor Bugbot (GitHub PR reviewer)

How Morrison-Lab uses [Cursor Bugbot](https://cursor.com/docs/bugbot.md)
as a pull-request reviewer.
Cursor *IDE/agent* behavior stays in [`cursor.md`](cursor.md).
The gha *capability* (`cursor-code-review.yml`) is catalogued in
[`gha-reusable-workflows.md`](gha-reusable-workflows.md).

This is lab operating procedure, not wai.
wai is the writing-principles book and has no Bugbot coverage
(`gh api "search/code?q=bugbot+repo:Morrison-Lab/wai"` returned `total_count: 0`, 2026-08-24).

## Two paths, only one works for us today

| Path | What it is | Morrison-Lab status (2026-08-23/24) |
|------|------------|-------------------------------------|
| Dashboard Bugbot | Cursor GitHub App + [Automations -> Bugbot](https://cursor.com/automations/from-cursor/bugbot) | **Works** on `Morrison-Lab/gha` when triggered as the PR author |
| `cursor-code-review.yml` | GHA reusable workflow: `POST https://api.cursor.com/bugbot/review` | **Does not work** with a Team/Pro key |

There is no `cursor.yml` mention-bot counterpart to `claude.yml`.
Bugbot is review-only.

## Dashboard Bugbot (the working path)

1. Install the Cursor GitHub App on the org
   (`gh api orgs/Morrison-Lab/installations` listed `cursor` on 2026-08-21
   and 2026-08-24, `repository_selection: all`).
2. Enable Bugbot for the repo in the **Morrison-Lab Cursor team** dashboard,
   not the personal Pro workspace.
   App installed != Bugbot covering that repo.
3. Trigger:
   - automatic on PR open/push once enabled (does not backfill older PRs), or
   - comment `bugbot run` or `cursor review` on the PR.

On success Bugbot:

- publishes a GitHub check named **`Cursor Bugbot`**
  (`app.slug` = `cursor`, not `github-actions`)
- posts a PR review (and inline comments when it finds issues)

Do not confuse that check with gha's selftest job `cursor-review-check`,
which is GitHub Actions exercising the composite, not Bugbot.

### Author must match the linked GitHub account

Individual/Pro Bugbot only reviews PRs whose author is the GitHub account
linked to the Cursor account that owns the run.

Measured on [Morrison-Lab/gha#597](https://github.com/Morrison-Lab/gha/pull/597)
(author `the repository owner`):

- Comment `bugbot run` from `dem-extra1`
  ([comment](https://github.com/Morrison-Lab/gha/pull/597#issuecomment-5391377690)):
  `cursor[bot]` replied **Bugbot couldn't run: GitHub account mismatch**
  ("The GitHub account linked to your Cursor account does not match the PR author
  ... or run Bugbot from a team that covers this repository.").
  No `Cursor Bugbot` check appeared (polled 4 minutes).
- The same phrase on the same PR from **`the repository owner`**:
  check [run 97340670384](https://github.com/Morrison-Lab/gha/runs/97340670384)
  completed **success** in ~7.5 minutes
  ("no issues found"), and Bugbot posted
  [PR review 5005059956](https://github.com/Morrison-Lab/gha/pull/597#pullrequestreview-5005059956).

A session whose `gh api user` is not the PR author cannot test this path
by commenting.
Have the author comment, or use a PR they authored.

Personal **Pro** (and Pro+) does not qualify for the Enterprise trigger API.
Pro can still use dashboard Bugbot on PRs that account authored.

## GHA `cursor-code-review.yml` (Enterprise API)

`Morrison-Lab/gha`'s reusable workflow queues Bugbot via
`admin:*` Basic auth.
Cursor documents the [Bugbot API](https://cursor.com/docs/bugbot.md#api)
as **Enterprise teams** only.

Dispatching gha's dogfood caller (`cursor-review.yml`) on 2026-08-24
against PR #597
([run 32694255358](https://github.com/Morrison-Lab/gha/actions/runs/32694255358)):

- PR resolve and fork/Dependabot guard **succeeded**
  (the secret was present and sent).
- Queue step failed:
  **`HTTP 401: Invalid Team API Key`**.

A Morrison-Lab org Team key in `CURSOR_API_KEY` will keep 401ing.
Do not debug the composite or the caller `secrets:` wiring for that
signature.
Use dashboard Bugbot, or replace the secret with an Enterprise `admin:*` key.

`ai-code-review.yml` can pick `cursor` only when that secret is a working
Enterprise key **and** `cursor` is in `agents`.
`Morrison-Lab/gha`'s `ai-review.yml` does not pass `CURSOR_API_KEY` and does
not include `cursor` in the default agent list.

## What "queued" vs "reviewed" means

GHA success on `cursor-code-review.yml` means the API accepted the queue
request, not that comments exist yet.
Dashboard success is the `Cursor Bugbot` check plus the review body.
A green `cursor-review-check` Actions job is not a Bugbot review.
