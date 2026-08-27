# Consumer-side GitHub CI, App installs, and moving-tag pins

Diagnosing a consumer repo's CI going red for a GitHub-platform reason rather than a local diff: a documented-but-wrong convention whose real fix is already upstream, a GitHub App install check, and a moving major tag that turns the default branch red with no local change.
Split out of [`github.md`](github.md) (ai-config#694 pattern) at the 1200-line gate.

## A CI failure caused by a documented-but-wrong convention may already have an upstream fix -- check before re-patching the symptom

When a consumer repo's CI fails because a *documented* convention (a skip label, a config key) doesn't actually work as described, the first instinct is to fix the local documentation to match the tool's real behavior.
Check first whether a **shared/reusable workflow this repo depends on** already fixed the actual root cause in a newer version than the one pinned -- the consumer's stale pin, not the doc wording, may be the real bug.

Concretely: `UCD-SERG/serocalculator`'s docs said a PR could skip its `news.yaml` changelog check with a `no-changelog` (hyphen) label, but applying that label didn't work -- the wrapped `UCD-SERG/changelog-check-action` hardcodes checking for `no changelog` (space), a different string.
The first fix redocumented the label as `no changelog` (space) everywhere -- technically unblocked the PR, but was wrong: it was really the shared `d-morrison/gha` `check-news.yml` reusable workflow, pinned to the repo's frozen `@v1` tag, that was stale.
A newer version (`@v2`) already had a configurable `no-changelog-label` input, added specifically for this convention by an earlier, already-closed upstream issue (gha#143).
The wrapper doesn't pass the label through to the action (which still unconditionally hardcodes `no changelog`, space) -- instead its own job carries a job-level `if:` that skips the whole job, action included, whenever the configured label is present, so the hardcoded check inside the action never runs at all for a PR carrying it.
Confirmed by diffing the reusable workflow's file content at the two tags directly (`git show <tag>:<path>` / a raw fetch per tag), not by trusting a versioning doc's blanket claim.
The correct fix was reverting the re-documented label and bumping the stale `@v1` pin to `@v2`, which restored the originally-documented (and originally correct) hyphenated label.

**Tell:** a review flags "this looks like the fix for an issue that's already closed" or the bug's exact symptom appears in a shared workflow's own inline comments/changelog.
Before accepting a symptom-level fix (redocumenting behavior to match what's observed), check the shared/reusable component's own issue tracker and version history for a fix already covering this exact case, and check whether the consumer is pinned to a version that predates it.

**A second-order lesson from the same investigation:** a package/repo's own versioning docs claiming a component is "audited, unchanged since the freeze" can itself be stale -- the audit can predate a later fix to that exact component.
Verify the claim against the two tags' actual file content rather than trusting the doc;
if wrong, fix it too (not just the one broken reference that surfaced the problem) via a repo-wide grep, since the same claim is often restated in multiple docs/pages.

**A third, narrower lesson: an unassembled `changelog.d/`-style fragment is a pending draft, not published history -- don't treat it as immutable.**
A fragment already merged to `main` but not yet collated into `CHANGELOG.md` by the release script can assert the exact stale claim being corrected.
Fix it in place like any other stale doc;
leaving it risks a self-contradictory `CHANGELOG.md` once both fragments are assembled together.
A review caught this only because it explicitly checked fragments outside the current PR's diff -- don't assume a `changelog.d/` file is out of scope just because this PR didn't author it.

(`UCD-SERG/serocalculator#593` / `d-morrison/gha#304`/`#143`, 2026-07-25: the label-name fix round-tripped through a wrong "redocument the label" patch before the actual `@v1`->`@v2` pin bump was found;
`gha#304`'s own review then caught two more stale `@v1` references in sibling docs pages and the contradicting pending changelog fragment, all in the same repo-wide sweep.)

## Verify GitHub App installation per repository

- **`gh api orgs/<org>/installations` answers this without a browser, in any org you own.**
  Measured 2026-08-21 under a classic PAT carrying `admin:org`: `Morrison-Lab` returned `claude`, `google-labs-jules`, and `cursor`.
  The `cursor` slug means the GitHub App is installed, not that Bugbot reviews PRs.
  Dashboard enablement, the Enterprise GHA queue, and the author-mismatch on `bugbot run` are in [`cursor-bugbot.md`](cursor-bugbot.md).

  ```bash
  gh api orgs/<org>/installations --jq '.installations[].app_slug'
  ```

- **A 404 from that endpoint is about the caller's org ROLE, not about token class.**
  GitHub documents that "the authenticated user must be an organization owner to use this endpoint" ([List app installations for an organization](https://docs.github.com/en/rest/orgs/orgs#list-app-installations-for-an-organization)).
  So the same PAT that answers for `Morrison-Lab` returned 404 for `ucdavis` on 2026-08-21, where we are not an owner --- the token was fine and the role was missing.
  Don't generalize that 404 into "a classic PAT cannot check installations";
it is a per-org fact rather than a property of the credential.
  Note the response is a bare `404 Not Found` rather than a `403`, so nothing in it names the missing role --- which is why the 404 invites a token-shaped explanation it does not support.
- **The two endpoints that genuinely need App credentials are different endpoints, and neither explains the 404 above.**
  `GET /repos/<owner>/<repo>/installation` needs an app JWT, and `GET /user/installations` needs a GitHub App user access token ([GitHub App installation API](https://docs.github.com/en/rest/apps/installations)).
  Both are true and neither is the org endpoint, so neither is evidence about it.
- **Fall back to the browser for an org you don't own.**
  With repository-admin access, open `https://github.com/<owner>/<repo>/settings/installations` and read the **Installed GitHub Apps** list.
  This distinguishes an installed Claude app from a repository that merely has workflow files or secrets.
- Verified 2026-08-21 by that route: `ucdavis/bcs` listed **Claude**, developed by Anthropic, while `ucdavis/hac.it` listed only GitHub Learning Lab.

## A moving upstream tag can turn a consumer's default branch red with no local change

A consumer pinned to a moving major tag (`...@v2`) inherits every change the tag's owner slides under it, so its default branch can go green-to-red between two consecutive commits while nothing changed that the check even looks at.

Two cheap reads settle it before anyone's diff is opened.
Check whether the **default branch itself** is red rather than only the PR, since that means the cause is not in any open branch;
then intersect the red commit's changed files with the flagged files, where an empty intersection points at the moving pin upstream.

**A tail-limited log fetch truncates the beginning of the output**, so earlier findings are absent and a complete checker looks partial.
Read the checker's own summary line, which usually states the true total.

- **Do:** read the default branch's status and intersect the red commit's changed files with the flagged files, before diagnosing anyone's diff.
- **Do:** compare a checker's stated total against the entries a fetch returned, and re-derive the affected set from its own extension list.
- **Don't:** read a green-to-red transition as evidence the red commit caused it --- a moving pin changes what runs without changing what it runs on.
- **Don't:** treat a tail-limited log read as the breakage's full scope.

(2026-08-15: a consumer pinning a shared `check-non-standard-chars` workflow at `@v2` went red when that checker's banned-glyph set gained U+00D7.
The red commit changed only a demo JSON and one GDScript file --- no file the checker scans and no workflow file.
The log itself was complete, opening `Found 19 non-standard character(s) in 4 file(s)` and listing all four;
a `tail_lines`-capped fetch showed only the last two, and that partial read was mistaken for the checker's own output.
An independent scan produced the right set anyway, so the fix was correct while the reason given for it was not.)
