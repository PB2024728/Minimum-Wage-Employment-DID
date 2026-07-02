# Consolidated estimator comparison - minimum-wage increase -> log L&H employment

Outcome: `log_leih` (log Leisure & Hospitality employment). Treatment: a state's first minimum-wage increase above its prior level. Panel: 51 jurisdictions x quarter, 2010Q1-2025Q4 (N = 3,264 state-quarters).

| Estimator | Coef (log pts) | SE | 95% CI (log pts) | % effect | 95% CI (%) | Staggered-robust |
|---|---|---|---|---|---|---|
| Pooled OLS (no FE) | -0.0063 (p=0.853) | 0.0343 | [-0.0735, +0.0608] | -0.63% | [-7.09%, +6.27%] | no |
| TWFE DiD (state+period FE) | -0.0268 (p=0.057) | 0.0140 | [-0.0543, +0.0007] | -2.64% | [-5.29%, +0.07%] | no |
| Callaway-Sant'Anna (2021) | -0.0217 | 0.0168 | [-0.0545, +0.0112] | -2.14% | [-5.30%, +1.12%] | yes |

All three estimators agree on a small, negative, statistically insignificant relative decline in low-wage-sector employment after a minimum-wage increase. The TWFE and Callaway-Sant'Anna point estimates differ by only 0.0051 log points (19% of the TWFE magnitude), so the staggered-adoption correction barely moves the headline.