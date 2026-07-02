# Day 4 - DiD estimates: minimum-wage increase -> log L&H employment

Outcome: `log_leih` (log Leisure & Hospitality employment). Treatment: `treated_post` (ever-treated state x post-first-increase).

## Results table

| Model | Coef (log pts) | SE | t | p | 95% CI | % effect | N |
|---|---|---|---|---|---|---|---|
| Pooled OLS (no FE) | -0.0063 | 0.0343 | -0.19 | 0.853 | [-0.0735, +0.0608] | -0.63% | 3264 |
| TWFE DiD (state+period FE, clustered SE) | -0.0268* | 0.0140 | -1.91 | 0.057 | [-0.0543, +0.0007] | -2.64% | 3264 |

Significance: `***` p<0.01, `**` p<0.05, `*` p<0.10. Pooled-OLS SE is HC1 (heteroskedasticity-robust); TWFE SE is clustered by state (51 clusters).

## Headline (TWFE)

A state minimum-wage increase is associated with a **-2.64%** change in low-wage-sector (L&H) employment (95% CI [-5.29%, +0.07%]), clustered-by-state SE = 0.0140 log points, not statistically significant at the 5% level (p = 0.057).

## Comparison / interpretation

- **Pooled OLS** gives -0.0063 log points (-0.63%). With no fixed effects this conflates the policy with *which* states raise their minimum wage: high-cost states (CA, NY, WA, MA...) both adopt higher minimums and have structurally different L&H employment levels, so the raw cross-sectional gap is confounding, not effect.

- **TWFE DiD** gives -0.0268 log points (-2.64%). State FE remove fixed level differences across states; period FE remove common shocks (notably the 2020 COVID collapse that hit L&H everywhere). The estimate moves by -0.0204 log points relative to pooled OLS, the size of the confounding the design removes.

- Inference: clustering by state (51 clusters) inflates the SE from the naive iid value, the standard correction for serially correlated state panels (Bertrand-Duflo-Mullainathan 2004). The TWFE point estimate is the Day-4 checkpoint.

## Caveats (this is a first pass, not the final number)

- **Always-treated states:** 6 jurisdictions have their first increase at the 2010Q1 panel start, so they contribute no clean pre-period and act partly as controls-by-timing. Kept here; drop-sensitivity is a robustness item.

- **Staggered timing + heterogeneous effects:** the TWFE coefficient is a variance-weighted average of 2x2 DiDs and can be biased when effects vary over time/cohort (Goodman-Bacon 2021; de Chaisemartin-D'Haultfoeuille 2020). The Callaway-Sant'Anna estimator (Day 6) is the designed robustness check; treat this number as provisional until that reconciliation.

- **No controls yet:** `ur` and `min_wage_gap` are available but excluded to keep the checkpoint spec clean (`log_leih ~ treated_post + FE`). Adding them is a Day 7 robustness pass.

- **Binary treatment:** `treated_post` is an on/off indicator, not the size of the increase; it estimates an average post-adoption shift, not a per-dollar elasticity.
