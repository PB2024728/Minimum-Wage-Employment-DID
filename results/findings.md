# Findings — Minimum Wage & Low-Wage Employment (Project #4)

*Difference-in-differences study of state minimum-wage increases and Leisure & Hospitality (L&H) employment, 2010Q1–2025Q4, 51 jurisdictions × quarter (N = 3,264 state-quarters). Consolidated Day 8.*

## Headline

**A state minimum-wage increase is associated with a −2.1% change (95% CI [−5.3%, +1.1%]) in low-wage-sector (Leisure & Hospitality) employment — robust to staggered-adoption correction, and not statistically distinguishable from zero.**

The point estimate is the Callaway–Sant'Anna (2021) group-time ATT, the design's most credible number because it is robust to the staggered, heterogeneous treatment timing that biases conventional two-way fixed-effects DiD. The two-way fixed-effects (TWFE) estimate is essentially the same: −2.6% (95% CI [−5.3%, +0.1%]). The closeness of the two — they differ by 0.005 log points, about a fifth of the TWFE magnitude — is the key robustness result: correcting for staggered adoption barely moves the headline, so the negative tilt is real in the data but small and statistically insignificant either way.

## Consolidated comparison table

| Estimator | Coef (log pts) | SE | 95% CI (log pts) | % effect | 95% CI (%) | Staggered-robust |
|---|---|---|---|---|---|---|
| Pooled OLS (no FE) | −0.0063 (p=0.853) | 0.0343 | [−0.0735, +0.0608] | −0.63% | [−7.09%, +6.27%] | no |
| TWFE DiD (state+period FE) | −0.0268 (p=0.057) | 0.0140 | [−0.0543, +0.0007] | −2.64% | [−5.29%, +0.07%] | no |
| Callaway–Sant'Anna (2021) | −0.0217 | 0.0168 | [−0.0545, +0.0112] | −2.14% | [−5.30%, +1.12%] | **yes** |

Outcome: `log_leih` (log L&H employment). Treatment: a state's first minimum-wage increase above its prior level. TWFE SEs clustered by state (51 clusters); CSA SEs analytic, entity-clustered, pointwise CIs. Full table: `results/comparison_table.csv` / `.md`. Headline figure: `results/fig_summary.png`.

## What the three estimators tell us together

The progression across the three rows is itself the story.

**Pooled OLS (−0.63%, p=0.85)** has no fixed effects, so it compares L&H employment between states that did and did not raise their minimum wage. That comparison is confounded: high-cost states (CA, NY, WA, MA…) both adopt higher minimums *and* have structurally different labor markets. The near-zero, hugely uncertain estimate is what confounding looks like, not an effect.

**TWFE DiD (−2.64%, p=0.057)** removes fixed state-level differences (state FE) and common time shocks — crucially the 2020 COVID collapse that hit L&H everywhere (period FE). Moving from pooled OLS to TWFE shifts the estimate by −0.020 log points; that shift is the magnitude of the confounding the design strips out. The result lands just outside 5% significance.

**Callaway–Sant'Anna (−2.14%)** addresses the remaining problem with TWFE under staggered adoption: the TWFE coefficient is a variance-weighted average of all 2×2 DiD comparisons, including "forbidden" ones that use already-treated states as controls for later-treated ones (Goodman-Bacon 2021; de Chaisemartin–D'Haultfœuille 2020). CSA uses only never-treated states as the clean control group for every group-time ATT, then aggregates with non-negative weights. It comes out slightly smaller in magnitude than TWFE — consistent with the forbidden comparisons mildly inflating the TWFE negative — and confirms the staggered-adoption bias in this panel is minor.

## Dynamics

The cohort-robust event study (`fig_summary.png` panel B; `fig_csa_event_study.png`) shows near-flat pre-treatment leads in the near window (k ∈ [−4, −1], max |ATT| ≈ 0.007 log pts), supporting approximate parallel trends in the clean comparisons. After adoption the effect deepens gradually to a trough of about −1.1% around k = 4 (~one year post-increase), then partially mean-reverts toward −0.3% at longer horizons. Every interior post-treatment coefficient is negative; none is individually significant at 5% (pointwise). The shape — a slow dip that bottoms near the one-year mark and then eases — is the credible dynamic picture.

The TWFE event study (`fig_event_study.png`) shows the same qualitative negative post path but its overall lead test rejects parallel trends (F=30.16, p=0.001) — driven entirely by *distant* leads (k=−12…−9); the near pre-window is jointly flat (F=3.69, p=0.30). This distant-lead elevation is the main internal-validity caveat and is why the cohort-robust CSA path is treated as the primary dynamic evidence.

## Falsification & robustness (Day 7) — design passes

- **High-wage placebo (Professional & Business Services):** swapping the outcome to a sector with few minimum-wage workers gives an insignificant ATT (TWFE −1.66%, CSA −0.21%, both CIs span 0). No effect where none should exist — the L&H result is not a generic all-sector state shock.
- **Fake-date falsification:** moving each treatment 8 quarters earlier and dropping the true post-period yields a placebo DiD of −0.0127 log pts (p=0.10) and a joint post-dummy test that does not reject (p=0.086). No spurious pre-policy effect — though both p-values sit just above 0.05, so this is "no clear failure" rather than a pristine null.
- **Alternative outcome (L&H share of nonfarm):** TWFE −0.0007 share pts (insignificant); CSA −0.0023 share pts (marginally significant but economically trivial, ~0.2 share points).
- **Alternative windows:** across event windows (TWFE ±8q to ±16q: −0.78% to −1.37%) and post-horizons (CSA k∈[0,kmax]: −0.43% to −0.58%) the estimate stays in a narrow negative band and never turns significantly positive or large. The headline is not an artifact of one window choice.

## Limitations & caveats

- **Binary first-increase treatment.** Treatment is an on/off indicator for a state's *first* increase, not the dollar size of increases or subsequent raises. The estimate is an average post-adoption shift, **not a per-dollar employment elasticity** — the single most important interpretive limit.
- **Statistically insignificant.** Every credible specification has a 95% CI that includes zero. The data are consistent with a modest negative effect, a null, or a small positive effect; they rule out only *large* employment losses (the lower bounds sit around −5%). Read this as "no evidence of large disemployment," not as a precise point estimate.
- **Distant pre-trend.** The TWFE lead test rejects on far leads (k≤−9); the near pre-window is flat and the CSA pre-period is approximately flat, but parallel trends are not cleanly satisfied across the full horizon.
- **Always-treated states dropped.** 6 jurisdictions (AK, CT, DC, IL, ME, NV) have their first increase at the 2010Q1 panel start and contribute no clean pre-period; they are excluded from the event study and CSA. The headline rests on the 25 treated states with a usable pre-period plus 20 never-treated controls.
- **Pointwise CIs for CSA.** Simultaneous (multiplier-bootstrap) bands would be modestly wider; individual-cell significance should be read with that in mind.
- **Sector proxy.** L&H is the low-wage proxy; it contains non-minimum-wage workers, attenuating any true minimum-wage effect toward zero. Aggregate state employment cannot isolate sub-sector or worker-level reallocation.

## Bottom line

Across pooled OLS, TWFE, and the staggered-robust Callaway–Sant'Anna estimator, a state minimum-wage increase is associated with a small (≈2%) relative decline in low-wage-sector employment that is **not statistically distinguishable from zero**, follows a gradual dip-and-recovery path peaking around one year, and survives high-wage-sector and fake-date placebos plus alternative-outcome and window robustness checks. The staggered-adoption correction changes the headline negligibly. The credible reading: **no evidence of large minimum-wage disemployment effects in U.S. Leisure & Hospitality over 2010–2025**, with the data unable to rule out a small negative effect.

---
*Sources (all in `results/`): `comparison_table.csv/.md`, `did_estimates.md`, `csa_estimates.md`, `event_study.md`, `placebo.md`; figures `fig_summary.png`, `fig_csa_event_study.png`, `fig_event_study.png`, `fig_robustness.png`, `fig_placebo_pbsv.png`, `fig_placebo_fake_date.png`.*
