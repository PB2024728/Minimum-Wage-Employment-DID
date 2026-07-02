# Day 5 - Event study & parallel-trends diagnostic

Dynamic DiD: relative-event-time leads/lags around each state's **first** minimum-wage increase, base period **k = -1** normalised to 0, endpoint binning at k <= -12 and k >= 16. State + period FE; SE clustered by state.

**Estimation sample:** 25 treated (with >=1 pre-quarter) + 20 never-treated = 45 states, 2880 obs. Dropped 6 always-treated states with no pre-period: ['AK', 'CT', 'DC', 'IL', 'ME', 'NV'].

## Parallel-trends test (pre-treatment leads jointly = 0)

- **All 11 leads:** joint Wald **F = 30.16, p = 0.001** -> **reject** at 5%.

- **Near window k in [-4, -2]:** joint Wald **F = 3.69, p = 0.297** -> **fail to reject** at 5%.

Individually, 4 of 11 lead coefficients are significant at 5%: k=-12, k=-11, k=-10, k=-9.

**Read:** the *overall* lead test rejects, but the violation is concentrated in the **distant** leads (the significant ones are all the long-horizon quarters); the **near** pre-window k in [-4,-2] is flat and jointly insignificant. Distant-lead elevation with sparser cohort support is a weaker threat than a pre-trend that accelerates into treatment - but the formal assumption is not cleanly satisfied, so the post estimates remain provisional pending the staggered-robust check.

## Dynamic effects after adoption

- **Early post (0-3q)** (k=0..3): mean effect -0.0062 log pts (~-0.62%).

- **Later post (>=8q)** (k=8..16): mean effect -0.0166 log pts (~-1.64%).

- Largest post coefficient at k=16: -0.0348 log pts (-3.42%), 95% CI [-0.0745, +0.0049], p=0.086.

- 6 of 17 post-treatment coefficients are individually significant at 5%; the post path is **negative and widening** (a gradual relative L&H-employment decline after the wage increase).

## Interpretation

Near-treatment leads are flat while the post path turns steadily negative, so the dynamic picture is a slow relative decline in low-wage-sector employment after a minimum-wage increase. These remain TWFE event-study coefficients; under staggered adoption with heterogeneous effects they can be contaminated by 'forbidden' comparisons among already-treated units (Goodman-Bacon 2021; Sun-Abraham 2021). The Callaway-Sant'Anna estimator (Day 6) is the designed cross-check, and its cohort-robust event study is the more credible dynamic picture; treat today's plot as the diagnostic that motivates it.

## Caveats

- Endpoint bins (k<=-12, k>=16) absorb sparse extreme relative times; interior coefficients are the interpretable ones.

- Binary event = first increase only; later increases and the *size* of each increase are not modelled here.

- TWFE event study is not staggered-robust; treat as a diagnostic, reconcile with Callaway-Sant'Anna on Day 6.


_Figure: `results/fig_event_study.png`. Coefficients: `results/event_study_coefs.csv`._
