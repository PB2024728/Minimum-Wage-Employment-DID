# Day 6 - Callaway-Sant'Anna (2021) staggered-adoption DiD

Outcome: `log_leih` (log Leisure & Hospitality employment). Cohort = quarter of a state's **first** minimum-wage increase (`g_csa`). Control group = **never-treated** states. Estimator: doubly-robust group-time ATT via the `differences` package (Callaway & Sant'Anna 2021). SEs clustered by state (analytic, entity-level); CIs are pointwise.

**Sample:** 31 ever-treated + 20 never-treated = 51 jurisdictions. The 6 always-treated states (first increase at the 2010Q1 panel start: AK, CT, DC, IL, ME, NV) have no clean pre-period and are dropped automatically by the estimator - the same 6 dropped by the Day-5 event study. Group-time ATT(g,t) cells estimated: **441**.

## Aggregated ATT

| Aggregation | ATT (log pts) | SE | 95% CI | % effect |
|---|---|---|---|---|
| **Overall (group-size weighted)** | -0.0217 | 0.0168 | [-0.0545, +0.0112] | -2.14% |
| Overall (event/post-avg) | -0.0186 | - | - | -1.84% |

## Headline (CSA)

A state minimum-wage increase is associated with a **-2.14%** change in low-wage-sector (L&H) employment (95% CI [-5.30%, +1.12%]), staggered-adoption-robust (Callaway-Sant'Anna). The CI spans zero, so the effect is **not statistically distinguishable from zero** at the 5% level.

## Reconciliation with TWFE (Day 4)

| Estimator | Overall ATT (log pts) | SE |
|---|---|---|
| TWFE DiD (Day 4) | -0.0268 | 0.0140 |
| Callaway-Sant'Anna | -0.0217 | 0.0168 |
| **Divergence (CSA - TWFE)** | **+0.0051** | - |

The two estimators agree closely: CSA is **+0.0051** log points from TWFE (19% of the TWFE magnitude), and both are negative, modest, and statistically insignificant. Under Goodman-Bacon (2021), the TWFE coefficient is a variance-weighted average of all 2x2 DiD comparisons - including 'forbidden' comparisons that use already-treated states as controls for later-treated ones, which can be mis-weighted (even negatively) when treatment effects are heterogeneous across cohorts or grow over time. CSA avoids those comparisons entirely: every ATT(g,t) uses only not-yet/never-treated states as the clean control group, then aggregates with non-negative, group-size weights.

The small CSA-vs-TWFE gap implies the staggered/heterogeneity bias in this panel is **minor** - the dynamic effects, while present, are not large or variable enough across cohorts to badly contaminate the TWFE weights. CSA is slightly **smaller in magnitude**, consistent with TWFE's forbidden comparisons (later cohorts differenced against earlier-treated, still-adjusting states) mildly inflating the negative TWFE point estimate. There IS real cohort heterogeneity underneath (per-cohort ATTs in `csa_aggregations.csv` range from clearly negative for the 2013-2015 and 2020 cohorts to positive for 2012 and 2021), but it largely averages out at the overall level. The qualitative read is unchanged: a small, gradual, statistically-insignificant relative decline in low-wage employment after a minimum-wage increase.

## Dynamic (event-study) path - cohort-robust

Pre-treatment placebo cells (k<0): **5 of 43** individually significant at 5% (pointwise); near-window |ATT| max (k in [-4,-1]) = 0.0074 log pts - small, supporting approximate parallel pre-trends in the clean CSA comparisons. 
Post path (interior window k in [0, 16]): the effect deepens to a trough of **-0.0109** log pts (-1.08%) at **k=4** (~1 year after adoption), then partially mean-reverts, settling around **-0.0033** log pts (-0.33%) at the longer horizon (k>=8). Every interior post coefficient is negative but none is individually significant at 5% (pointwise). The shape - a gradual dip that bottoms out near the one-year mark and then eases - is the cohort-robust counterpart of the TWFE event study's negative post path, now free of forbidden-comparison contamination. (Far-out event times beyond the window rest on a single sparse cohort and are not interpreted.)

_Figure: `results/fig_csa_event_study.png` (left: cohort-robust dynamic ATT with 95% pointwise CIs; right: CSA-overall vs TWFE)._

## Caveats

- **Pointwise CIs.** Bands are analytic and pointwise; simultaneous (uniform) bands via the multiplier bootstrap would be modestly wider. Individual-cell significance should be read with that in mind.
- **Binary first-increase event.** Cohort = first increase only; the *size* of each increase and subsequent increases are not modelled. ATT is an average post-adoption shift, not a per-dollar elasticity.
- **Never-treated control group.** Uses never-treated states as controls; a not-yet-treated control set is an available robustness variant (Day 7).
- **Sparse extreme event times.** Distant relative periods rest on few cohorts; the interior window (k in [-12, 16]) holds the interpretable estimates.
