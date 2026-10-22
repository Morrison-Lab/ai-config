# Branch-ruleset decisions

A dated record of the decisions behind the rulesets in the Morrison-Lab organization.
The rule is in [`shared/workflow/repo-templates.md`](../../shared/workflow/repo-templates.md); the scripts are described in [`README.md`](README.md).

## 2026-10-22: every repo gets a ruleset that follows its template's example

Ezra's rule: when configuring a repo, always set a ruleset, following the example of the template repo it came from, and create the example when the template has none.
The tracking issue is [ai-config#4671](https://github.com/Morrison-Lab/ai-config/issues/4671).
The rule was merged in [ai-config#4672](https://github.com/Morrison-Lab/ai-config/pull/4672).

- **Template examples.**
  `qwt`, `qbt` and `rpt` already had `.github/rulesets/main.json`.
  [qmt#14](https://github.com/Morrison-Lab/qmt/pull/14), [qet#3](https://github.com/Morrison-Lab/qet/pull/3) and [grt#3](https://github.com/Morrison-Lab/grt/pull/3) added theirs.
  `qmt` and `qet` copy `qwt`'s; `grt` uses the shared `base.json` shape, as `mlg` does.
- **Fallback.**
  A repo with no template, or whose template has no example, gets `base.json` (ruleset name `protect-default-branch`).
- **Overrides.**
  GitHub's recorded `template_repository` is unreliable (`qwt` says `qbt`, `qet` says `slidebreak`, `mcs` says none).
  The apply used `mcs=qwt` and `mcsg=grt`, so `mcs` got `qwt`'s example and `mcsg` got `grt`'s.
- **Applied the same day** from cf463-02 with `apply-all.sh --apply`, after a dry run:
  - `gw` got `rpt`'s example.
  - `ids`, `cds`, `career` and `mcs` got `qwt`'s.
  - `mcsg` got `grt`'s.
  - `dlg`, `dds`, `grt`, `qet`, `qmt`, `lds-site`, `gla`, `glr`, `stats-allowlist`, `swc`, `canvas`, `test.quarto.website`, `demo2` and `slidebreak` got `base.json`.
  - A fresh dry run then showed no repo without a ruleset.
    Before, 39 had one and 20 were missing.
- **Why `qmt`, `qet` and `grt` carry `base.json` rather than their own example.**
  The three are templates themselves, so GitHub records no template for them and `apply-all.sh` used the fallback.
  Their own examples were already merged by then, so the live rulesets differ from the examples in their `.github/rulesets/` until a template's `apply-rulesets.sh` is run in that repo.
  `mcsg` is the exception: it was applied with the `mcsg=grt` override, so it got `grt`'s example.
- **Name aliasing.**
  `base.json` is named `protect-default-branch` and the template examples are named `main`.
  The `apply-rulesets.sh` of `qwt`, `qbt`, `rpt`, `qmt`, `qet` and `grt` treats `protect-default-branch` as the same ruleset as `main`.
  A later run therefore updates the live ruleset in place and cannot add a second one.
  When a repo has both names, the script prefers the ruleset named `main`.
