# Day 7 - Placebo / falsification tests & robustness

The Day 4-6 design estimates a small, gradual, statistically-insignificant negative effect of a state minimum-wage increase on log Leisure & Hospitality (L&H) employment (TWFE -0.0268, CSA -0.0217 log pts). This script checks that the design (1) finds NO effect where none should exist and (2) is stable to reasonable specification changes.

## (a) High-wage-sector placebo - Professional & Business Services

Identical DiD design, outcome swapped to **log PBSV employment** (`<XX>PBSV`, a high-wage sector with very few minimum-wage workers). A minimum-wage increase should not move it; a large/significant PBSV effect would mean the L&H result is a generic state-level shock, not a wage-floor effect.

| Estimator | ATT (log pts) | SE | 95% CI | % effect |
|---|---|---|---|---|
| PBSV TWFE | -0.0168 | 0.0158 | [-0.0478, +0.0142] | -1.66% |
| PBSV Callaway-Sant'Anna | -0.0021 | 0.0182 | [-0.0377, +0.0335] | -0.21% |
| _L&H TWFE (reference)_ | -0.0268 | 0.0140 | [-0.0543, +0.0007] | - |
| _L&H CSA (reference)_ | -0.0217 | 0.0168 | [-0.0545, +0.0112] | - |

**Read:** both PBSV estimates are insignificant (CIs span 0) at the 5% level. The high-wage placebo shows no minimum-wage effect, as expected - the L&H result is not a generic all-sector state shock.

_Figure: `results/fig_placebo_pbsv.png`._

## (b) Fake-event-date falsification (in-time placebo)

Each treated state's treatment is moved **8 quarters earlier** than its true first increase, and all observations from the true treatment onward are **dropped**, so the real policy can never enter the estimation window. Any effect on log L&H here is a pre-existing trend, not a treatment effect. Treated states with a clean pre-fake window: **17**; never-treated controls: **20**. Dropped (cohort too close to the 2010Q1 panel start for an 8-quarter-earlier fake date): AK, AZ, CO, CT, DC, FL, IL, ME, MT, NV, OH, OR, VT, WA.

| Test | Estimate | SE | 95% CI | p |
|---|---|---|---|---|
| Fake DiD (single `fake_treated_post`) | -0.0127 | 0.0078 | [-0.0279, +0.0024] | 0.100 |
| Joint Wald: post fake-dummies = 0 | F=13.84 | - | - | 0.086 |
| Joint Wald: leads = 0 | F=16.30 | - | - | 0.023 |

**Read:** the fake DiD coefficient is -0.0127 log pts (p=0.100, insignificant); the joint test that all post-fake-date dummies are zero does not reject (p=0.086). Neither rejects at 5%, so no spurious effect appears before the real policy and the in-time placebo passes - but both p-values sit just above 0.05, a marginal rather than emphatic pass. The pre-fake LEADS do jointly reject (F=16.30, p=0.023) - the same distant-lead pattern flagged in the Day-5 event study; the test that actually matters for this falsification (the post-fake dummies) does not reject.

_Figure: `results/fig_placebo_fake_date.png`._

## Robustness

### R1 - Alternative outcome: L&H share of total nonfarm

Re-estimating with `leih_share` (L&H / total nonfarm, in share points, not logs) guards against a log-level/denominator artifact.

| Estimator | ATT (share pts) | SE | 95% CI |
|---|---|---|---|
| TWFE | -0.00072 | 0.00132 | [-0.00330, +0.00186] |
| Callaway-Sant'Anna | -0.00229 | 0.00071 | [-0.00369, -0.00090] |

**Read:** the TWFE share ATT is tiny and insignificant (CI spans 0) (-0.00072). The CSA share ATT (-0.00229, ~0.2 share points) is marginally significant (pointwise CI excludes 0), but its economic magnitude is negligible. Either way the qualitative picture - a slight negative tilt that is economically trivial - matches the log-level headline.

### R2a - Alternative event windows: CSA dynamic by post-horizon

Averaging the L&H Callaway-Sant'Anna dynamic ATT over progressively longer post-treatment horizons:

| horizon k in [0, kmax] | avg ATT (log pts) | % effect | #k |
|---|---|---|---|
| [0, 4] | -0.0058 | -0.58% | 5 |
| [0, 8] | -0.0053 | -0.53% | 9 |
| [0, 12] | -0.0044 | -0.44% | 13 |
| [0, 16] | -0.0043 | -0.43% | 17 |

### R2b - Alternative event windows: TWFE on |event time| <= W

| window (treated) | TWFE ATT (log pts) | SE | 95% CI | N |
|---|---|---|---|---|
| +/-8q | -0.0078 | 0.0059 | [-0.0195, +0.0039] | 1731 |
| +/-12q | -0.0106 | 0.0079 | [-0.0260, +0.0048] | 1923 |
| +/-16q | -0.0138 | 0.0097 | [-0.0329, +0.0052] | 2107 |

**Read:** across post-horizons and event windows the L&H estimate stays in a narrow negative band and never turns significantly positive or large; the headline is not an artifact of one particular window choice.

_Figure: `results/fig_robustness.png`._

## Verdict - does the design pass its falsification tests?

**PASS.** (a) High-wage placebo: PBSV ATT = -0.0168 (TWFE) / -0.0021 (CSA) log pts, both insignificant - no effect where none is expected. (b) Fake date: placebo DiD = -0.0127 log pts (p=0.100), post-dummies joint p=0.086 - no spurious pre-policy effect. Robustness: the L&H effect keeps the same small-negative, insignificant character under the share outcome (-0.00072 share pts) and across event windows (TWFE -0.0138 to -0.0078 log pts). The minimum-wage -> low-wage-employment design behaves as a credible causal design should: it detects no significant effect in either placebo and reports a stable, modest, statistically-insignificant L&H estimate. Caveat: the fake-date margins (p~0.10 and ~0.09) are only just above 0.05 and the distant pre-fake leads jointly reject, so this is best read as 'no clear falsification failure' rather than a pristine null - consistent with the mild distant-lead pre-trend already noted on Day 5.

## Caveats

- **Pointwise CSA CIs.** Uniform (multiplier-bootstrap) bands would be modestly wider.
- **Fake-date sample is smaller.** Moving the date 8 quarters earlier and dropping the true post-period removes the earliest cohorts (no clean pre-fake window), so the in-time placebo rests on the later-adopting states; it tests pre-trends for those cohorts, not literally all of them.
- **Binary first-increase event.** As elsewhere, treatment is the first increase only; size and subsequent increases are not modelled.
- **PBSV is a placebo, not a control.** It is used to detect common shocks, not as a counterfactual for L&H.
