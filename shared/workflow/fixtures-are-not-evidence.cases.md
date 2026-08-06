# Case records: fixtures-are-not-evidence

Worked-example case records for the rules in
[`fixtures-are-not-evidence.md`](fixtures-are-not-evidence.md), moved here verbatim to keep them out of the
auto-loaded `CLAUDE.md` context.
Each heading names the rule the record supports.

## A GH013 line invented in a fixture, read as GitHub's wording

(gha#361, 2026-07-29: a `GH013` line was added to a fixture commented as the
verbatim rejection from gha#360.
When a reordered classifier chain made that fixture fail, the failure was
read as evidence that GitHub wraps workflow-permission rejections in the
generic rule-violation envelope, and that claim went into a review reply, a
code comment, and a commit message.
The real log quoted in gha#360's body has no `GH013` line.
The claim was the whole justification for a chain order that hid a security
bug, so the review round had to disprove the reasoning as well as the code.)

## "A fixture that agrees with the bug" --- an upper-bound-only adherence filter

(ucdavis/bcs#479, 2026-07-30: `calc_ip_weights_ab507bs()` filtered adherence
intervals with an upper bound only, `window_dur <= window_months`, missing the
lower bound the SAS reference applies.
The shared fixtures built annual interval durations of 4, 7, 8, 10 and 13
months against an 11-18 month window, and a multi-round fixture whose
intervals were 3 months throughout.
Only the 13-month intervals clear the lower bound, so applying it stripped the
annual model frame to a fraction of its rows and emptied the multi-round one,
and the durations had to move inside the real windows before the fix could
pass.
One existing test asserted the bug: "only the terminal round enters the
adherence model, so perturbing the first exam's score leaves every weight
unchanged" held only because a `slice_max` had collapsed the accumulation to
one row per participant, and it now asserts the opposite.
Run against `main`'s implementation, the new tests produced 9 failures across
all six blocks that touch the behavior.)

## "A fixture that cannot tell the two apart" --- degenerate age coefficients

(`ucdavis/bcs#534`, 2026-07-30/31: `compute_gcomp_cif_ab507bs()` evaluated the
CIF for one synthetic participant at the mean baseline age instead of averaging
each participant's hazard over the observed age distribution.
The existing `fit_ab507bs_gee()` fixture fixes event timing by profile and
repeat rather than by age, so the fit returns age coefficients of order
`1e-17`; with no age effect the two estimators coincide exactly, and a
regression test built on it would have passed against the buggy code.
The new fixture draws deaths from a logit hazard with real linear and quadratic
age terms, and the test asserts
`expect_gt(abs(betas[["age_monthly"]]), 0.01)` and
`expect_gt(abs(betas[["age_monthly2"]]), 0.001)` before asserting
`expect_gt(max(abs(cif$cum_incidence - at_mean$cum_incidence)), 0.05)` against
`ab507bs_gcomp_cif_at_mean_age()`, the retired computation kept as a helper.)
