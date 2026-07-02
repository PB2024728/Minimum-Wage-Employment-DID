#!/usr/bin/env python3
"""build_dashboard.py - Interactive, theme-switchable results dashboard for Project #4.

Reads every result artifact in results/ + the processed panel, and emits a single
self-contained `dashboard.html` at the project root with:
  * interactive Plotly charts (hover, legend toggle) built from the real data,
  * a light/dark theme toggle (charts re-render to match),
  * the full set of comprehensive data tables (every estimate; the 307-event log),
  * a collapsible appendix of the original static figures (base64-embedded).
Plotly loads from CDN; all data is embedded inline (nothing leaves the browser).
Idempotent; standalone. Run: `py src/build_dashboard.py`.
"""
from __future__ import annotations

import base64
import csv
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
PANEL = ROOT / "data" / "processed" / "panel.csv"
OUT = ROOT / "dashboard.html"


# ---------- helpers --------------------------------------------------------
def img64(name: str) -> str:
    return "data:image/png;base64," + base64.b64encode((RES / name).read_bytes()).decode()


def read_csv(name: str) -> list[dict]:
    with (RES / name).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def f(x, nd=4, sign=True, pct=False, suf=""):
    if x is None or x == "" or str(x).lower() == "nan":
        return "&mdash;"
    v = float(x)
    s = f"{v:.{nd}f}"
    if v > 0 and sign:
        s = "+" + s
    s = s.replace("-", "&minus;")
    return s + ("%" if pct else "") + suf


def tbl(headers, rows, cls="", right_from=1):
    th = "".join(f"<th{' class=num' if i>=right_from else ''}>{h}</th>" for i, h in enumerate(headers))
    trs = []
    for r in rows:
        tds = "".join(f"<td{' class=num' if i>=right_from else ''}>{c}</td>" for i, c in enumerate(r))
        trs.append(f"<tr>{tds}</tr>")
    return f"<div class='tw'><table class='{cls}'><thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table></div>"


def q_to_date(qlabel: str) -> str:
    y, q = qlabel.split("Q")
    return f"{y}-{(int(q)-1)*3+1:02d}-01"


# ---------- load data ------------------------------------------------------
comp = read_csv("comparison_table.csv")
es = read_csv("event_study_coefs.csv")
csa = read_csv("csa_aggregations.csv")
plac = read_csv("placebo_estimates.csv")
events = read_csv("events_table.csv")

# panel-derived series (treated effective MW path; treated/control L&H index)
prows = list(csv.DictReader(PANEL.open(encoding="utf-8")))
byq = defaultdict(lambda: {"t_leih": [], "c_leih": [], "t_mw": []})
qlabel = {}
for r in prows:
    qo = int(r["quarter_ord"]); qlabel[qo] = r["quarter"]
    if r["treated"] == "1":
        byq[qo]["t_leih"].append(float(r["leih"])); byq[qo]["t_mw"].append(float(r["effective_min_wage"]))
    else:
        byq[qo]["c_leih"].append(float(r["leih"]))
qs = sorted(byq)
dates = [q_to_date(qlabel[q]) for q in qs]
t0 = st.mean(byq[0]["t_leih"]); c0 = st.mean(byq[0]["c_leih"])
mw_treated = [round(st.mean(byq[q]["t_mw"]), 3) for q in qs]
idx_treated = [round(100 * st.mean(byq[q]["t_leih"]) / t0, 2) for q in qs]
idx_control = [round(100 * st.mean(byq[q]["c_leih"]) / c0, 2) for q in qs]


# ---------- chart data (-> JSON, consumed by Plotly) -----------------------
def g(r, k):
    return None if r[k] in ("", None) else float(r[k])


comp_map = {r["Estimator"]: r for r in comp}
CHARTS = {}

# estimator comparison (% effect + 95% CI %)
order = ["Pooled OLS (no FE)", "TWFE DiD (state+period FE)", "Callaway-Sant'Anna (2021)"]
labels_short = ["Pooled OLS", "TWFE DiD", "Callaway&ndash;Sant'Anna"]
CHARTS["comparison"] = {
    "labels": ["Pooled OLS", "TWFE", "Callaway–Sant'Anna"],
    "pct": [g(comp_map[o], "pct_effect") for o in order],
    "lo": [g(comp_map[o], "pct_CI_low") for o in order],
    "hi": [g(comp_map[o], "pct_CI_high") for o in order],
}

# TWFE event study (log pts) with CI band
CHARTS["twfe_es"] = {
    "k": [int(r["event_time"]) for r in es],
    "coef": [g(r, "coef") for r in es],
    "lo": [g(r, "ci_low") for r in es],
    "hi": [g(r, "ci_high") for r in es],
    "lead": [r["is_lead"] == "True" for r in es],
}

# CSA dynamic ATT interior k=-12..16
csa_dyn = {int(r["key"]): r for r in csa if r["aggregation"] == "event_dynamic"}
kk = [k for k in range(-12, 17) if k in csa_dyn]
CHARTS["csa_dyn"] = {
    "k": kk,
    "att": [g(csa_dyn[k], "att") for k in kk],
    "lo": [g(csa_dyn[k], "ci_low") for k in kk],
    "hi": [g(csa_dyn[k], "ci_high") for k in kk],
}

# CSA by-cohort ATT
bycoh = [r for r in csa if r["aggregation"] == "by_cohort"]
CHARTS["csa_cohort"] = {
    "cohort": [r["cohort_q"] for r in bycoh],
    "att": [g(r, "att") for r in bycoh],
    "lo": [g(r, "ci_low") for r in bycoh],
    "hi": [g(r, "ci_high") for r in bycoh],
    "sig": [r["signif"] == "*" for r in bycoh],
}

# treatment events scatter (all 307)
CHARTS["events"] = {
    "year": [int(r["event_year"]) for r in events],
    "pct": [float(r["increase_pct"]) for r in events],
    "state": [r["jurisdiction"] for r in events],
    "prev": [float(r["prev_wage"]) for r in events],
    "new": [float(r["new_wage"]) for r in events],
    "dabs": [float(r["increase_abs"]) for r in events],
}

# adoption cohort sizes
cohort_order = ["2010Q1", "2011Q1", "2012Q1", "2013Q1", "2014Q1", "2015Q1", "2020Q1", "2021Q1"]
cohort_n = {"2010Q1": 6, "2011Q1": 7, "2012Q1": 1, "2013Q1": 2, "2014Q1": 6, "2015Q1": 7, "2020Q1": 1, "2021Q1": 1}
CHARTS["cohort_sizes"] = {"cohort": cohort_order, "n": [cohort_n[c] for c in cohort_order]}

# panel series
CHARTS["mw_paths"] = {"x": dates, "treated": mw_treated, "fed": [7.25] * len(dates)}
CHARTS["leih_index"] = {"x": dates, "treated": idx_treated, "control": idx_control}

# placebo bar (% effect): L&H vs PBSV, TWFE & CSA
pl = {(r["block"], r["spec"]): r for r in plac}
CHARTS["placebo"] = {
    "groups": ["L&H (main)", "PBSV (placebo)"],
    "twfe": [float(comp_map["TWFE DiD (state+period FE)"]["pct_effect"]),
             float(pl[("placebo_pbsv", "TWFE")]["pct_effect"])],
    "csa": [float(comp_map["Callaway-Sant'Anna (2021)"]["pct_effect"]),
            float(pl[("placebo_pbsv", "CSA_overall")]["pct_effect"])],
}

# robustness: TWFE windows + CSA horizons (log pts)
CHARTS["twfe_windows"] = {
    "w": ["±8q", "±12q", "±16q"],
    "att": [g(pl[("robust_twfe_window", s)], "coef") for s in ["pm8q", "pm12q", "pm16q"]],
    "lo": [g(pl[("robust_twfe_window", s)], "ci_low") for s in ["pm8q", "pm12q", "pm16q"]],
    "hi": [g(pl[("robust_twfe_window", s)], "ci_high") for s in ["pm8q", "pm12q", "pm16q"]],
}
CHARTS["csa_horizons"] = {
    "h": ["[0,4]", "[0,8]", "[0,12]", "[0,16]"],
    "att": [g(pl[("robust_csa_horizon", s)], "coef") for s in ["k0_4", "k0_8", "k0_12", "k0_16"]],
}

CHARTS_JSON = json.dumps(CHARTS)


# ---------- comprehensive data tables --------------------------------------
comp_rows = []
for r in comp:
    comp_rows.append([
        r["Estimator"], f(r["Coef_logpts"]), f(r["SE"], sign=False),
        f"[{f(r['CI_low'])}, {f(r['CI_high'])}]", f(r["pct_effect"], 2, pct=True),
        "[" + f(r["pct_CI_low"], 2) + ", " + f(r["pct_CI_high"], 2) + "]%",
        (f(r["p_value"], 3, sign=False) if r["p_value"] else "&mdash;"),
        ("<span class='yes'>yes</span>" if r["Staggered_robust"] == "yes" else "<span class='no'>no</span>"),
    ])
comp_tbl = tbl(["Estimator", "Coef (log pts)", "SE", "95% CI (log pts)", "% effect", "95% CI (%)", "p", "Staggered-robust"], comp_rows)

es_rows = []
for r in es:
    base = r["is_base"] == "True"
    es_rows.append([
        r["label"], ("lead" if r["is_lead"] == "True" else "lag"),
        ("base" if base else f(r["coef"])), ("&mdash;" if base else f(r["se"], sign=False)),
        ("&mdash;" if base else f"[{f(r['ci_low'])}, {f(r['ci_high'])}]"),
        (f(r["p_value"], 3, sign=False) if r["p_value"] not in ("", None) else "&mdash;"),
        ("0.00%" if base else f(r["pct_effect"], 2, pct=True)),
    ])
es_tbl = tbl(["k", "type", "coef (log pts)", "SE", "95% CI", "p", "% effect"], es_rows, cls="compact")

csa_overall = {r["aggregation"]: r for r in csa if r["aggregation"] in ("overall_simple", "overall_event")}
csa_overall_rows = [
    ["Overall (group-size weighted)", f(csa_overall["overall_simple"]["att"]), f(csa_overall["overall_simple"]["std_error"], sign=False),
     f"[{f(csa_overall['overall_simple']['ci_low'])}, {f(csa_overall['overall_simple']['ci_high'])}]",
     f(float(csa_overall["overall_simple"]["att"]) * 100, 2, pct=True)],
    ["Overall (event/post-avg)", f(csa_overall["overall_event"]["att"]), f(csa_overall["overall_event"]["std_error"], sign=False),
     f"[{f(csa_overall['overall_event']['ci_low'])}, {f(csa_overall['overall_event']['ci_high'])}]",
     f(float(csa_overall["overall_event"]["att"]) * 100, 2, pct=True)],
]
csa_overall_tbl = tbl(["Aggregation", "ATT (log pts)", "SE", "95% CI", "% effect"], csa_overall_rows)

cohort_state = {
    "2010Q1": "AK, CT, DC, IL, ME, NV", "2011Q1": "AZ, CO, MT, OH, OR, VT, WA", "2012Q1": "FL",
    "2013Q1": "MO, RI", "2014Q1": "CA, DE, MI, MN, NJ, NY", "2015Q1": "AR, HI, MA, MD, NE, SD, WV",
    "2020Q1": "NM", "2021Q1": "VA",
}
bycoh_rows = []
for r in bycoh:
    cq = r["cohort_q"]
    bycoh_rows.append([cq, str(cohort_n.get(cq, "")), cohort_state.get(cq, ""), f(r["att"]),
                       f(r["std_error"], sign=False), f"[{f(r['ci_low'])}, {f(r['ci_high'])}]",
                       f(float(r["att"]) * 100, 2, pct=True),
                       ("<span class='sig'>yes</span>" if r["signif"] == "*" else "no")])
bycoh_tbl = tbl(["Cohort", "#", "States", "ATT (log pts)", "SE", "95% CI", "% effect", "Sig. 5%"], bycoh_rows, right_from=3)

dyn_rows = []
for k in kk:
    r = csa_dyn[k]
    dyn_rows.append([("base" if k == -1 else str(k)), f(r["att"], 5), f(r["std_error"], 5, sign=False),
                     f"[{f(r['ci_low'],5)}, {f(r['ci_high'],5)}]", f(float(r["att"]) * 100, 2, pct=True),
                     ("<span class='sig'>yes</span>" if r["signif"] == "*" else "no")])
dyn_tbl = tbl(["k", "ATT (log pts)", "SE", "95% pointwise CI", "% effect", "Sig. 5%"], dyn_rows)

pbsv_rows = [
    ["PBSV TWFE", f(pl[("placebo_pbsv", "TWFE")]["coef"]), f(pl[("placebo_pbsv", "TWFE")]["se"], sign=False),
     f"[{f(pl[('placebo_pbsv','TWFE')]['ci_low'])}, {f(pl[('placebo_pbsv','TWFE')]['ci_high'])}]",
     f(pl[("placebo_pbsv", "TWFE")]["pct_effect"], 2, pct=True), f(pl[("placebo_pbsv", "TWFE")]["p_value"], 3, sign=False)],
    ["PBSV Callaway&ndash;Sant'Anna", f(pl[("placebo_pbsv", "CSA_overall")]["coef"]), f(pl[("placebo_pbsv", "CSA_overall")]["se"], sign=False),
     f"[{f(pl[('placebo_pbsv','CSA_overall')]['ci_low'])}, {f(pl[('placebo_pbsv','CSA_overall')]['ci_high'])}]",
     f(pl[("placebo_pbsv", "CSA_overall")]["pct_effect"], 2, pct=True), "&mdash;"],
]
pbsv_tbl = tbl(["Estimator (outcome = log PBSV)", "ATT (log pts)", "SE", "95% CI", "% effect", "p"], pbsv_rows)

fake = pl[("falsification_fake_date", "TWFE_fake_did")]
fake_rows = [
    ["Fake DiD (single fake_treated_post)", f(fake["coef"]), f(fake["se"], sign=False),
     f"[{f(fake['ci_low'])}, {f(fake['ci_high'])}]", f(fake["p_value"], 3, sign=False)],
    ["Joint Wald: post fake-dummies = 0", "F = 13.84", "&mdash;", "&mdash;", "0.086"],
    ["Joint Wald: leads = 0", "F = 16.30", "&mdash;", "&mdash;", "0.023"],
]
fake_tbl = tbl(["Test (outcome = log L&amp;H, treatment shifted &minus;8q)", "Estimate", "SE", "95% CI", "p"], fake_rows)

share_rows = [
    ["TWFE", f(pl[("robust_alt_outcome_share", "TWFE")]["coef"], 5), f(pl[("robust_alt_outcome_share", "TWFE")]["se"], 5, sign=False),
     f"[{f(pl[('robust_alt_outcome_share','TWFE')]['ci_low'],5)}, {f(pl[('robust_alt_outcome_share','TWFE')]['ci_high'],5)}]"],
    ["Callaway&ndash;Sant'Anna", f(pl[("robust_alt_outcome_share", "CSA_overall")]["coef"], 5), f(pl[("robust_alt_outcome_share", "CSA_overall")]["se"], 5, sign=False),
     f"[{f(pl[('robust_alt_outcome_share','CSA_overall')]['ci_low'],5)}, {f(pl[('robust_alt_outcome_share','CSA_overall')]['ci_high'],5)}]"],
]
share_tbl = tbl(["Estimator (outcome = L&amp;H share of nonfarm, share pts)", "ATT", "SE", "95% CI"], share_rows)

hor_rows = []
for spec, lab in [("k0_4", "[0, 4]"), ("k0_8", "[0, 8]"), ("k0_12", "[0, 12]"), ("k0_16", "[0, 16]")]:
    r = pl[("robust_csa_horizon", spec)]
    hor_rows.append([lab, f(r["coef"], 4), f(r["pct_effect"], 2, pct=True), str(int(float(r["n_k"])))])
hor_tbl = tbl(["Horizon k &isin; [0, kmax]", "avg ATT (log pts)", "% effect", "# k"], hor_rows)

win_rows = []
for spec, lab in [("pm8q", "&plusmn;8q"), ("pm12q", "&plusmn;12q"), ("pm16q", "&plusmn;16q")]:
    r = pl[("robust_twfe_window", spec)]
    win_rows.append([lab, f(r["coef"], 4), f(r["se"], 4, sign=False), f"[{f(r['ci_low'])}, {f(r['ci_high'])}]", str(int(float(r["n_obs"])))])
win_tbl = tbl(["Event window |k| &le; W", "TWFE ATT (log pts)", "SE", "95% CI", "N"], win_rows)

ev_rows = [[r["jurisdiction"], r["event_quarter"], f(r["prev_wage"], 2, sign=False), f(r["new_wage"], 2, sign=False),
            f(r["increase_abs"], 2, sign=False), f(r["increase_pct"], 1, sign=False) + "%", f(r["fed_floor"], 2, sign=False)] for r in events]
ev_tbl = tbl(["State", "Quarter", "Prev $", "New $", "&Delta;$", "&Delta;%", "Fed $"], ev_rows, cls="compact", right_from=2)

coh_summary_tbl = tbl(["First-treatment cohort", "# states", "States"],
                      [[c, str(cohort_n[c]), cohort_state[c]] for c in cohort_order], right_from=1)
series_tbl = tbl(["Role", "FRED series", "Measures", "Frequency"], [
    ["Treatment", "STTMINWG&lt;XX&gt;", "State minimum wage ($/hr)", "annual"],
    ["Outcome", "&lt;XX&gt;LEIH", "Leisure &amp; Hospitality employment (000s)", "monthly"],
    ["Normalizer", "&lt;XX&gt;NA", "Total nonfarm employment (000s)", "monthly"],
    ["Control", "&lt;XX&gt;UR", "State unemployment rate (%)", "monthly"],
    ["Flag", "FEDMINNFRWG", "Federal minimum wage ($7.25, flat)", "monthly"]], right_from=3)
miss_tbl = tbl(["State", "Series ID", "Reason dropped (not imputed)"],
               [[s, "STTMINWG" + s, "no state statute &mdash; remains a federal-floor control"] for s in ["AL", "LA", "MS", "SC", "TN"]], right_from=3)
pt_tbl = tbl(["Parallel-trends test (TWFE event study)", "F", "p", "Verdict"],
             [["All 11 leads jointly = 0", "30.16", "0.001", "reject at 5%"],
              ["Near window k &isin; [&minus;4, &minus;2] = 0", "3.69", "0.297", "fail to reject"]])
out_tbl = tbl(["State (2020Q2)", "&Delta;log L&amp;H"],
              [["DC", "&minus;0.920"], ["NY", "&minus;0.850"], ["MA", "&minus;0.799"], ["HI", "&minus;0.784"],
               ["NJ", "&minus;0.758"], ["VT", "&minus;0.754"], ["RI", "&minus;0.722"], ["PA", "&minus;0.709"]])

stats = [("51", "jurisdictions", "50 states + DC"), ("64", "quarters", "2010Q1&ndash;2025Q4"),
         ("3,264", "observations", "balanced, 0 missing"), ("307", "increase events", "31 treated states"),
         ("20", "never-treated", "controls (incl. 5 no-statute)"), ("441", "ATT(g,t) cells", "estimated by CSA")]
stat_cards = "".join(f"<div class='stat'><div class='big'>{b}</div><div class='lab'>{l}</div><div class='sub'>{s}</div></div>" for b, l, s in stats)

caveats = [
    ("On/off treatment", "Treatment is a binary indicator for a state's <b>first</b> increase, not the dollar size or subsequent raises. The estimate is an average post-adoption shift, <b>not a per-dollar elasticity</b>."),
    ("Statistically insignificant", "Every credible 95% CI includes zero. The data are consistent with a modest negative effect, a true null, or a small positive effect; they rule out only <b>large</b> losses (lower bounds &asymp; &minus;5%)."),
    ("Distant pre-trend", "The TWFE lead test rejects parallel trends on far leads (k &le; &minus;9); the near pre-window and the CSA pre-period are approximately flat, but parallel trends are not cleanly satisfied across the full horizon."),
    ("Always-treated dropped", "6 jurisdictions (AK, CT, DC, IL, ME, NV) have their first increase at the 2010Q1 panel start, contribute no clean pre-period, and are excluded from the event study and CSA."),
    ("Pointwise CSA CIs", "CSA bands are analytic and pointwise; simultaneous (multiplier-bootstrap) bands would be modestly wider. Individual-cell significance should be read with that in mind."),
    ("Sector proxy &amp; Q1 timing", "L&amp;H contains non-minimum-wage workers, attenuating any true effect toward zero. Events are dated to Q1 (annual series resolution); mid-year statutory changes cannot be timed more precisely."),
]
caveat_items = "".join(f"<div class='caveat'><h4>{t}</h4><p>{d}</p></div>" for t, d in caveats)

# static-figure appendix (collapsible)
appendix_figs = [
    ("fig_summary.png", "Consolidated summary: estimator comparison and cohort-robust dynamic ATT."),
    ("fig_treatment_timeline.png", "Every increase event by state and quarter (marker size/colour = magnitude)."),
    ("fig_event_study.png", "TWFE event study (static source figure)."),
    ("fig_csa_event_study.png", "Callaway&ndash;Sant'Anna dynamic ATT (static source figure)."),
    ("fig_robustness.png", "Robustness across outcomes and windows (static source figure)."),
    ("fig_placebo_pbsv.png", "High-wage placebo (PBSV)."),
    ("fig_placebo_fake_date.png", "Fake-date falsification."),
    ("fig_minwage_paths.png", "Effective minimum-wage paths."),
    ("fig_trends_treated_control.png", "Indexed L&amp;H employment, treated vs control."),
    ("fig_leih_share_trends.png", "L&amp;H share of nonfarm."),
    ("fig_adoption_cohorts.png", "Adoption cohort sizes."),
    ("fig_raw_event_study.png", "Descriptive (within-state demeaned) event study."),
    ("fig_coverage_quality.png", "Coverage and data-quality scan."),
]
appendix_html = "".join(
    f"<figure class='fig'><img loading='lazy' alt='{n}' src='{img64(n)}'><figcaption>{c}</figcaption></figure>"
    for n, c in appendix_figs)


# ---------- CSS (raw string; no f-string brace escaping) -------------------
CSS = r"""
:root{
  --bg:#f4f7f9;--bg2:#e7edf1;--card:#fff;--card2:#f8fafc;
  --text:#17252f;--text2:#475560;--text3:#8a98a5;
  --accent:#048be6;--accent-l:#e4f3fd;--accent-m:#7cc4f2;--gold:#ca9500;
  --border:#e0e6eb;--code-bg:#eef3f6;
  --slatebg:#17252f;
  --sh:0 1px 3px rgba(0,0,0,.07),0 4px 12px rgba(0,0,0,.05);
  --sh2:0 10px 28px rgba(0,0,0,.10);
  --tr:all .25s cubic-bezier(.4,0,.2,1);
}
html.dark{
  --bg:#0d1620;--bg2:#16222e;--card:#1b2a37;--card2:#16222e;
  --text:#eef3f6;--text2:#9fb0bc;--text3:#6f8190;
  --accent:#3aa6ee;--accent-l:#123247;--accent-m:#2b6f9c;--gold:#ffc000;
  --border:#2c3d4b;--code-bg:#0f1c27;
  --slatebg:#0a121a;
  --sh:0 2px 8px rgba(0,0,0,.45);--sh2:0 12px 36px rgba(0,0,0,.55);
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;font-size:16px}
body{font-family:Calibri,"Segoe UI",system-ui,Roboto,Arial,sans-serif;background:var(--bg);color:var(--text);line-height:1.6;transition:background .3s,color .3s}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
nav{position:sticky;top:0;z-index:100;background:var(--card);border-bottom:1px solid var(--border);box-shadow:var(--sh);padding:0 1.5rem;display:flex;align-items:center;height:54px;transition:background .3s}
.nav-brand{font-weight:700;font-size:.9rem;color:var(--accent);flex-shrink:0}
.nav-links{display:flex;align-items:center;gap:.15rem;list-style:none;white-space:nowrap;overflow-x:auto;margin:0 .8rem;flex:1}
.nav-links a{color:var(--text2);font-size:.76rem;font-weight:600;padding:.3rem .55rem;border-radius:6px;transition:var(--tr)}
.nav-links a:hover,.nav-links a.active{background:var(--accent-l);color:var(--accent)}
#tbtn{background:var(--bg2);border:1px solid var(--border);border-radius:8px;cursor:pointer;padding:.35rem .7rem;font-size:.8rem;color:var(--text);transition:var(--tr);flex-shrink:0;margin-left:auto;font-family:inherit}
#tbtn:hover{background:var(--accent-l);color:var(--accent)}
.hero{background:var(--slatebg);color:#fff;padding:3rem 1.5rem 2.6rem}
.hero-inner{max-width:1140px;margin:0 auto}
.kicker{color:var(--accent);font-weight:700;letter-spacing:2px;font-size:12px;text-transform:uppercase}
.hero h1{color:#fff;font-size:clamp(1.5rem,4vw,2.1rem);font-weight:800;line-height:1.15;margin:.4em 0 .2em}
.hero .sub{color:#cfd9e0;font-size:1rem;max-width:840px}
.headcard{display:flex;gap:1.4rem;align-items:center;margin-top:1.5rem;background:rgba(255,255,255,.05);border:1px solid var(--accent);border-radius:12px;padding:1.1rem 1.4rem}
.headcard .num{font-family:Georgia,serif;font-size:3.2rem;font-weight:700;color:var(--gold);line-height:1}
html.dark .headcard .num{color:#ffc000}
.headcard b{font-size:.97rem;color:#fff}.headcard .meta{color:#9fb0bc;font-size:.78rem;margin-top:.35rem}
main{max-width:1140px;margin:0 auto;padding:0 1.5rem 4rem}
section{padding-top:2.6rem}section+section{border-top:1px solid var(--border);margin-top:1.4rem}
h2{font-size:1.45rem;font-weight:800;color:var(--text);margin-bottom:.2rem}
h2 .em{color:var(--accent)}
h3{font-size:1.02rem;font-weight:700;color:var(--text);margin:1.3rem 0 .4rem}
.lead{color:var(--text3);margin-bottom:1rem;font-size:.92rem;max-width:880px}
p{color:var(--text2);font-size:.92rem;margin-bottom:.7rem}
strong,b{color:var(--text)}
.stats{display:grid;grid-template-columns:repeat(6,1fr);gap:.7rem;margin:.8rem 0}
.stat{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:.8rem .5rem;text-align:center;box-shadow:var(--sh)}
.stat .big{font-family:Georgia,serif;font-size:1.7rem;font-weight:700;color:var(--accent)}
.stat .lab{font-weight:700;margin-top:.15rem;font-size:.8rem;color:var(--text)}
.stat .sub{color:var(--text3);font-size:.7rem}
.tw{overflow-x:auto;border-radius:10px;border:1px solid var(--border);box-shadow:var(--sh);margin:.7rem 0}
table{width:100%;border-collapse:collapse;font-size:.84rem;background:var(--card)}
thead th{background:var(--text);color:var(--card);text-align:left;padding:.55rem .8rem;font-size:.78rem;white-space:nowrap}
html.dark thead th{background:#243543}
th.num,td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
tbody td{padding:.48rem .8rem;border-top:1px solid var(--border);color:var(--text2)}
tbody tr:nth-child(even) td{background:var(--card2)}
tbody tr:hover td{background:var(--accent-l)}
table.compact tbody td{padding:.32rem .65rem;font-size:.78rem}
.yes{color:#2e8b57;font-weight:700}.no{color:var(--text3)}.sig{color:var(--accent);font-weight:700}
html.dark .yes{color:#4ade80}
.note{color:var(--text3);font-size:.78rem;font-style:italic;margin:.5rem 0}
.takeaway{background:var(--slatebg);color:#fff;border-radius:10px;padding:.9rem 1.2rem;margin:1rem 0;font-size:.9rem}
.takeaway b{color:var(--gold)}html.dark .takeaway b{color:#ffc000}
.chart-box{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1rem 1rem .5rem;box-shadow:var(--sh);margin:.9rem 0}
.chart-head{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;padding:0 .2rem}
.chart-title{font-size:.9rem;font-weight:700;color:var(--text);padding:0 0 .3rem}
.chart-sub{font-size:.76rem;color:var(--text3);padding:0 0 .5rem}
.reset-btn{flex-shrink:0;background:var(--bg2);border:1px solid var(--border);color:var(--text2);border-radius:7px;padding:.32rem .6rem;font-size:.72rem;font-weight:600;cursor:pointer;font-family:inherit;transition:var(--tr);white-space:nowrap}
.reset-btn:hover{background:var(--accent-l);color:var(--accent);border-color:var(--accent-m)}
.chart-help{font-size:.79rem;color:var(--text2);background:var(--accent-l);border-radius:7px;padding:.5rem .7rem;margin:0 .2rem .65rem;line-height:1.5}
.chart-help b{color:var(--accent)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:.9rem}
.caveats{display:grid;grid-template-columns:repeat(3,1fr);gap:.7rem;margin-top:.6rem}
.caveat{background:var(--slatebg);color:#cfd9e0;border-radius:10px;padding:.9rem}
.caveat h4{margin:0 0 .3rem;color:var(--accent);font-size:.86rem}html.dark .caveat h4{color:#3aa6ee}
.caveat p{margin:0;font-size:.78rem;color:#aab8c2}
details{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:.3rem 1rem;margin:.6rem 0;box-shadow:var(--sh)}
summary{cursor:pointer;font-weight:700;color:var(--accent);padding:.5rem 0;font-size:.88rem}
.scroll{max-height:440px;overflow:auto}
.fig{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:.8rem;margin:.7rem 0;box-shadow:var(--sh)}
.fig img{width:100%;height:auto;display:block;border-radius:4px}
.fig figcaption{color:var(--text3);font-size:.76rem;margin-top:.5rem}
#bt{position:fixed;bottom:1.5rem;right:1.5rem;background:var(--accent);color:#fff;width:40px;height:40px;border-radius:50%;border:none;cursor:pointer;font-size:1.05rem;box-shadow:var(--sh2);opacity:0;transform:translateY(10px);transition:opacity .3s,transform .3s;z-index:99}
#bt.vis{opacity:1;transform:translateY(0)}
footer{background:var(--slatebg);color:#9fb0bc;padding:1.6rem;font-size:.78rem;text-align:center}
footer b{color:#fff}
@media(max-width:900px){.stats{grid-template-columns:repeat(3,1fr)}.caveats{grid-template-columns:1fr}.grid2{grid-template-columns:1fr}.headcard{flex-direction:column;align-items:flex-start;gap:.6rem}}
"""


# ---------- JS (raw string) -----------------------------------------------
JS = r"""
const C={blue:'#048BE6',gold:'#FFC000',slate:'#17252F',gray:'#8A98A5',red:'#E74C3C',green:'#2E8B57',mblue:'#7cc4f2'};
const tbtn=document.getElementById('tbtn');
function isDark(){return document.documentElement.classList.contains('dark');}
function applyTheme(d){document.documentElement.classList.toggle('dark',d);tbtn.textContent=d?'☀️ Light':'🌙 Dark';}
function toggleTheme(){const d=!isDark();try{localStorage.setItem('mw_theme',d?'dark':'light');}catch(e){}applyTheme(d);renderCharts();}
(function(){let s=null;try{s=localStorage.getItem('mw_theme');}catch(e){}const p=window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches;applyTheme(s?s==='dark':p);})();
const bt=document.getElementById('bt');
window.addEventListener('scroll',()=>bt.classList.toggle('vis',scrollY>400),{passive:true});
const als=document.querySelectorAll('.nav-links a');
document.querySelectorAll('section[id]').forEach(sec=>{new IntersectionObserver(es=>{es.forEach(e=>{if(e.isIntersecting)als.forEach(a=>a.classList.toggle('active',a.getAttribute('href')==='#'+e.target.id));});},{rootMargin:'-15% 0px -75% 0px'}).observe(sec);});
function txtC(){return isDark()?'#eef3f6':'#17252f';}
function gridC(){return isDark()?'#2c3d4b':'#e0e6eb';}
function LAY(extra){return Object.assign({paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{color:txtC(),family:'Calibri,Segoe UI,Arial,sans-serif',size:12},xaxis:{gridcolor:gridC(),linecolor:gridC(),zerolinecolor:gridC()},yaxis:{gridcolor:gridC(),linecolor:gridC(),zerolinecolor:gridC()},legend:{bgcolor:'rgba(0,0,0,0)'},margin:{t:24,b:46,l:60,r:18},hovermode:'closest'},extra||{});}
const CFG={responsive:true,displayModeBar:false};
function band(x,lo,hi,color){return {x:x.concat(x.slice().reverse()),y:hi.concat(lo.slice().reverse()),fill:'toself',fillcolor:color,line:{width:0},hoverinfo:'skip',showlegend:false,type:'scatter'};}
function rgba(hex,a){const n=parseInt(hex.slice(1),16);return 'rgba('+((n>>16)&255)+','+((n>>8)&255)+','+(n&255)+','+a+')';}
const D=window.CHARTS;
const BUILDERS={};
  BUILDERS.c_cmp=function(){const c=D.comparison;const colors=[C.gray,C.gray,C.blue];
    const tr={type:'bar',x:c.labels,y:c.pct,marker:{color:colors},
      error_y:{type:'data',symmetric:false,array:c.hi.map((h,i)=>h-c.pct[i]),arrayminus:c.pct.map((p,i)=>p-c.lo[i]),color:isDark()?'#9fb0bc':'#475560',thickness:1.4,width:6},
      text:c.pct.map(v=>v.toFixed(2)+'%'),textposition:'outside',textfont:{size:11,color:txtC()},
      hovertemplate:'<b>%{x}</b><br>%{y:.2f}%<extra></extra>'};
    Plotly.newPlot('c_cmp',[tr],LAY({yaxis:Object.assign(LAY().yaxis,{title:'% effect on L&H employment',range:[-8,7]}),
      shapes:[{type:'line',x0:-.5,x1:2.5,y0:0,y1:0,line:{color:C.gray,width:1}}]}),CFG);};
  BUILDERS.c_twfe=function(){const c=D.twfe_es;const x=c.k;
    const lo=c.lo.map(v=>v==null?null:v*100),hi=c.hi.map(v=>v==null?null:v*100),y=c.coef.map(v=>v==null?null:v*100);
    const xi=x.filter((_,i)=>c.lo[i]!=null),loi=lo.filter(v=>v!=null),hii=hi.filter(v=>v!=null);
    const pts={type:'scatter',mode:'markers',x:x,y:y,marker:{size:7,color:x.map((k,i)=>c.lead[i]?C.gray:C.blue)},
      error_y:{type:'data',symmetric:false,array:hi.map((h,i)=>h==null?null:h-y[i]),arrayminus:y.map((v,i)=>v==null?null:v-lo[i]),color:rgba('#8A98A5',.5),thickness:1,width:0},
      hovertemplate:'k=%{x}<br>ATT %{y:.2f}%<extra></extra>',showlegend:false};
    Plotly.newPlot('c_twfe',[band(xi,loi,hii,rgba('#048BE6',.12)),pts],LAY({
      xaxis:Object.assign(LAY().xaxis,{title:'quarters relative to first increase (k)'}),
      yaxis:Object.assign(LAY().yaxis,{title:'ATT on log L&H (%)'}),
      shapes:[{type:'line',x0:Math.min(...x),x1:Math.max(...x),y0:0,y1:0,line:{color:C.gray,width:1}},
              {type:'line',x0:-1,x1:-1,y0:-5,y1:4,line:{color:C.red,width:1,dash:'dash'}}]}),CFG);};
  BUILDERS.c_csa=function(){const c=D.csa_dyn;const x=c.k;
    const y=c.att.map(v=>v*100),lo=c.lo.map(v=>v*100),hi=c.hi.map(v=>v*100);
    const pts={type:'scatter',mode:'markers',x:x,y:y,marker:{size:7,color:x.map(k=>k<0?C.gray:C.blue)},
      hovertemplate:'k=%{x}<br>ATT %{y:.2f}%<extra></extra>',showlegend:false};
    Plotly.newPlot('c_csa',[band(x,lo,hi,rgba('#048BE6',.13)),pts],LAY({
      xaxis:Object.assign(LAY().xaxis,{title:'quarters relative to first increase (k)'}),
      yaxis:Object.assign(LAY().yaxis,{title:'cohort-robust ATT (%)'}),
      shapes:[{type:'line',x0:Math.min(...x),x1:Math.max(...x),y0:0,y1:0,line:{color:C.gray,width:1}},
              {type:'line',x0:-.5,x1:-.5,y0:-2.5,y1:1.2,line:{color:C.red,width:1,dash:'dash'}}]}),CFG);};
  BUILDERS.c_coh=function(){const c=D.csa_cohort;const y=c.att.map(v=>v*100);
    const tr={type:'bar',x:c.cohort,y:y,marker:{color:y.map(v=>v<0?C.blue:C.gold)},
      error_y:{type:'data',symmetric:false,array:c.hi.map((h,i)=>(h-c.att[i])*100),arrayminus:c.att.map((a,i)=>(a-c.lo[i])*100),color:rgba('#8A98A5',.7),thickness:1.2,width:5},
      hovertemplate:'<b>%{x}</b><br>ATT %{y:.2f}%<extra></extra>'};
    Plotly.newPlot('c_coh',[tr],LAY({yaxis:Object.assign(LAY().yaxis,{title:'cohort ATT (%)'}),
      shapes:[{type:'line',x0:-.5,x1:c.cohort.length-.5,y0:0,y1:0,line:{color:C.gray,width:1}}]}),CFG);};
  BUILDERS.c_ev=function(){const c=D.events;
    const tr={type:'scatter',mode:'markers',x:c.year,y:c.pct,
      marker:{size:c.dabs.map(d=>6+d*4),color:c.pct,colorscale:[[0,'#7cc4f2'],[1,'#048BE6']],opacity:.6,line:{width:.5,color:isDark()?'#0d1620':'#fff'}},
      text:c.state,customdata:c.year.map((y,i)=>[c.prev[i],c.new[i],c.dabs[i]]),
      hovertemplate:'<b>%{text} %{x}</b><br>$%{customdata[0]:.2f} → $%{customdata[1]:.2f} (Δ $%{customdata[2]:.2f})<br>+%{y:.1f}%<extra></extra>'};
    Plotly.newPlot('c_ev',[tr],LAY({xaxis:Object.assign(LAY().xaxis,{title:'event year',dtick:1}),
      yaxis:Object.assign(LAY().yaxis,{title:'increase size (%)'}),showlegend:false}),CFG);};
  BUILDERS.c_cohn=function(){const c=D.cohort_sizes;
    const tr={type:'bar',x:c.cohort,y:c.n,marker:{color:C.blue},text:c.n,textposition:'outside',textfont:{color:txtC()},
      hovertemplate:'<b>%{x}</b><br>%{y} states<extra></extra>'};
    Plotly.newPlot('c_cohn',[tr],LAY({yaxis:Object.assign(LAY().yaxis,{title:'# first-treated states',range:[0,8]})}),CFG);};
  BUILDERS.c_mw=function(){const c=D.mw_paths;
    const t1={type:'scatter',mode:'lines',name:'Treated mean (effective)',x:c.x,y:c.treated,line:{color:C.blue,width:2.4},hovertemplate:'%{x|%Y-%m}<br>$%{y:.2f}<extra>Treated</extra>'};
    const t2={type:'scatter',mode:'lines',name:'Federal floor ($7.25)',x:c.x,y:c.fed,line:{color:C.gray,width:1.6,dash:'dash'},hovertemplate:'$%{y:.2f}<extra>Federal</extra>'};
    Plotly.newPlot('c_mw',[t1,t2],LAY({yaxis:Object.assign(LAY().yaxis,{title:'$ / hour',range:[6,15]}),legend:{orientation:'h',y:1.12}}),CFG);};
  BUILDERS.c_idx=function(){const c=D.leih_index;
    const t1={type:'scatter',mode:'lines',name:'Treated',x:c.x,y:c.treated,line:{color:C.blue,width:2.2},hovertemplate:'%{x|%Y-%m}<br>%{y:.1f}<extra>Treated</extra>'};
    const t2={type:'scatter',mode:'lines',name:'Control (never-treated)',x:c.x,y:c.control,line:{color:C.gold,width:2.2},hovertemplate:'%{x|%Y-%m}<br>%{y:.1f}<extra>Control</extra>'};
    Plotly.newPlot('c_idx',[t1,t2],LAY({yaxis:Object.assign(LAY().yaxis,{title:'L&H employment (2010Q1=100)'}),legend:{orientation:'h',y:1.12}}),CFG);};
  BUILDERS.c_plac=function(){const c=D.placebo;
    const t1={type:'bar',name:'TWFE',x:c.groups,y:c.twfe,marker:{color:C.blue},text:c.twfe.map(v=>v.toFixed(2)+'%'),textposition:'outside',textfont:{color:txtC()},hovertemplate:'<b>%{x}</b> TWFE<br>%{y:.2f}%<extra></extra>'};
    const t2={type:'bar',name:'Callaway-Sant Anna',x:c.groups,y:c.csa,marker:{color:C.gold},text:c.csa.map(v=>v.toFixed(2)+'%'),textposition:'outside',textfont:{color:txtC()},hovertemplate:'<b>%{x}</b> CSA<br>%{y:.2f}%<extra></extra>'};
    Plotly.newPlot('c_plac',[t1,t2],LAY({barmode:'group',yaxis:Object.assign(LAY().yaxis,{title:'% effect',range:[-4,1.2]}),legend:{orientation:'h',y:1.14},
      shapes:[{type:'line',x0:-.5,x1:1.5,y0:0,y1:0,line:{color:C.gray,width:1}}]}),CFG);};
  BUILDERS.c_win=function(){const c=D.twfe_windows;const y=c.att.map(v=>v*100);
    const tr={type:'bar',x:c.w,y:y,marker:{color:C.blue},
      error_y:{type:'data',symmetric:false,array:c.hi.map((h,i)=>(h-c.att[i])*100),arrayminus:c.att.map((a,i)=>(a-c.lo[i])*100),color:rgba('#8A98A5',.7),thickness:1.2,width:6},
      hovertemplate:'<b>%{x}</b><br>%{y:.2f}%<extra></extra>'};
    Plotly.newPlot('c_win',[tr],LAY({yaxis:Object.assign(LAY().yaxis,{title:'TWFE ATT (%)',range:[-3.6,1]}),
      shapes:[{type:'line',x0:-.5,x1:2.5,y0:0,y1:0,line:{color:C.gray,width:1}}]}),CFG);};
  BUILDERS.c_hor=function(){const c=D.csa_horizons;const y=c.att.map(v=>v*100);
    const tr={type:'scatter',mode:'lines+markers',x:c.h,y:y,line:{color:C.blue,width:2.2},marker:{size:8,color:C.blue},
      hovertemplate:'<b>%{x}</b><br>avg ATT %{y:.2f}%<extra></extra>'};
    Plotly.newPlot('c_hor',[tr],LAY({yaxis:Object.assign(LAY().yaxis,{title:'avg ATT (%)',range:[-1,0]}),
      xaxis:Object.assign(LAY().xaxis,{title:'post-horizon k in [0, kmax]'})}),CFG);};
function renderCharts(){Object.keys(BUILDERS).forEach(function(id){BUILDERS[id]();});}
function resetChart(id){if(BUILDERS[id])BUILDERS[id]();}
document.addEventListener('DOMContentLoaded',renderCharts);
"""


HELP = {
    "c_ev": "Each dot is one state minimum-wage increase. Higher up = a bigger percentage raise; bigger, darker dots = a larger dollar jump. Hover a dot to see the state, the year, and the old &rarr; new wage. Drag a box over part of the chart to zoom in, then click <b>Reset view</b> to zoom back out.",
    "c_cohn": "Each bar counts how many states raised their minimum wage for the first time in that year. Hover a bar for the exact number of states. Click <b>Reset view</b> to undo any zoom.",
    "c_cmp": "Each bar is one statistical method's estimated effect on jobs. The thin vertical line through the bar is the 95% confidence range &mdash; where the true effect most plausibly lies. If that line crosses the zero line, the effect is <i>not</i> statistically clear. Hover a bar for the exact figures.",
    "c_twfe": "Left-to-right is time around the wage hike, where 0 is the quarter the wage rose. Dots to the left of 0 are &lsquo;before&rsquo;, dots to the right are &lsquo;after&rsquo;; the shaded band is the 95% confidence range. Roughly flat dots before 0 are the sign the method can be trusted. Hover any dot for its value; drag to zoom, then <b>Reset view</b>.",
    "c_csa": "Same idea as the chart on the left, using the staggered-robust method. 0 marks the wage hike; dots before it are &lsquo;before&rsquo; and after it are &lsquo;after&rsquo;, with the shaded 95% confidence band. Hover any dot for its exact value.",
    "c_coh": "Each bar is the estimated job effect for the group of states that <i>first</i> raised wages in that year. Blue = employment dipped, gold = employment rose; the thin line is the 95% confidence range. Hover a bar for exact values.",
    "c_mw": "Blue = the average minimum wage in states that raised it; dashed grey = the unchanged $7.25 federal floor that binds the comparison states. The widening gap between the lines is the policy change being studied. Hover a point for the dollar amount.",
    "c_idx": "Both lines start at 100 in 2010 so their growth is directly comparable. Blue = states that raised the minimum wage, gold = states that never did. The two lines moving together early on is the key assumption behind the whole analysis. Click a label in the legend to hide or show a line.",
    "c_plac": "A sanity check. The left pair of bars is the low-wage industry we actually study; the right pair is a high-wage industry the minimum wage should barely touch. We <i>want</i> the right pair sitting near zero &mdash; if it were large, the method would be suspect. Hover a bar for the exact percent.",
    "c_win": "Re-runs the estimate using only data within 8, 12, or 16 quarters of each wage hike. If the bars barely move, the result isn't an artifact of one particular window. The thin line on each bar is the 95% confidence range. Hover for values.",
    "c_hor": "The average effect when we look 1, 2, 3, and 4 years after the hike (the x-axis lists the quarter ranges). A fairly flat line means the effect is stable over time. Hover a point for its value.",
}


def chart(cid, title, sub, h=360):
    helptext = HELP.get(cid, "")
    helprow = ("<div class='chart-help'><b>How to use:</b> " + helptext + "</div>") if helptext else ""
    return ("<div class='chart-box'><div class='chart-head'>"
            "<div><div class='chart-title'>" + title + "</div>"
            "<div class='chart-sub'>" + sub + "</div></div>"
            "<button class='reset-btn' onclick=\"resetChart('" + cid + "')\">&#8635; Reset view</button>"
            "</div>" + helprow +
            "<div id='" + cid + "' style='height:" + str(h) + "px'></div></div>")


# ---------- assemble HTML --------------------------------------------------
body = f"""
<nav>
  <span class="nav-brand">Minimum Wage DiD</span>
  <ul class="nav-links">
    <li><a href="#facts">Facts</a></li><li><a href="#data">Data</a></li><li><a href="#treatment">Treatment</a></li>
    <li><a href="#results">Results</a></li><li><a href="#twfe">Event study</a></li><li><a href="#csa">Callaway&ndash;Sant'Anna</a></li>
    <li><a href="#descriptives">Descriptives</a></li><li><a href="#placebo">Robustness</a></li>
    <li><a href="#figures">Figures</a></li><li><a href="#caveats">Caveats</a></li>
  </ul>
  <button id="tbtn" onclick="toggleTheme()">&#127769; Dark</button>
</nav>
<div class="hero"><div class="hero-inner">
  <div class="kicker">Econometrics &middot; Difference-in-Differences &middot; Project #4</div>
  <h1>Minimum Wage &amp; Low-Wage Employment &mdash; Interactive Results Dashboard</h1>
  <p class="sub">Causal effect of statutory state minimum-wage increases on Leisure &amp; Hospitality employment, estimated by staggered difference-in-differences. State&times;quarter panel, 2010Q1&ndash;2025Q4, 51 jurisdictions, N&nbsp;=&nbsp;3,264. All data from FRED. Hover any chart for exact values; toggle light/dark at top-right.</p>
  <div class="headcard"><div class="num">&minus;2.1%</div>
    <div><b>Effect of a state's first minimum-wage increase on L&amp;H employment (Callaway&ndash;Sant'Anna ATT)</b>
    <div class="meta">&minus;0.0217 log pts &middot; SE 0.0168 &middot; 95% CI [&minus;5.30%, +1.12%] &middot; not statistically distinguishable from zero &middot; robust to staggered-adoption correction</div></div>
  </div>
</div></div>
<main>
<section id="facts"><h2>Key facts</h2>
  <p class="lead">Panel scope and treatment structure.</p>
  <div class="stats">{stat_cards}</div>
</section>
<section id="data"><h2>Data &amp; <span class="em">pipeline</span></h2>
  <p class="lead">Five FRED series per jurisdiction; monthly series collapsed to quarterly means, the annual minimum wage forward-filled to quarters. 205 series in the map &mdash; 200 resolved, 5 dropped (not imputed).</p>
  {series_tbl}
  <p>Unique series: <b>205</b>. Cached: <b>191</b>. Fetched: <b>9</b>. Missing/discontinued: <b>5</b>. Transient errors: <b>0</b>. Panel: <b>3,264 rows</b> = 51 &times; 64; gap quarters = 0; missing cells = <b>0</b>.</p>
  {miss_tbl}
  <p class="note">The 5 dropped series are the state-minimum-wage series for the no-statute states; their LEIH / NA / UR resolve normally, so they remain in the panel as never-treated federal-floor controls.</p>
</section>
<section id="treatment"><h2>Treatment <span class="em">structure</span></h2>
  <p class="lead">An event = a state minimum-wage increase whose new level sits above the binding $7.25 federal floor. 307 events across 31 states, 8 staggered yearly cohorts. Median increase 5.4%. By 2025Q4 the treated-state mean effective minimum wage is $13.71 vs the $7.25 federal floor.</p>
  {chart("c_ev", "Every minimum-wage increase event (all 307)", "x = event year, y = increase size; marker size/colour scale with the dollar increase. Hover for state and prev&rarr;new wage.", 380)}
  {chart("c_cohn", "First-treatment cohort sizes", "Number of states whose first qualifying increase falls in each cohort year. Largest cohort: 2011 (7 states).", 300)}
  {coh_summary_tbl}
  <p class="note">Never-treated controls (20): AL, GA, IA, ID, IN, KS, KY, LA, MS, NC, ND, NH, OK, PA, SC, TN, TX, UT, WI, WY. No-statute states (5, subset): AL, LA, MS, SC, TN.</p>
  <details><summary>Full event log &mdash; all 307 minimum-wage increase events</summary><div class="scroll">{ev_tbl}</div></details>
</section>
<section id="results"><h2>Main results <span class="em">&mdash; estimator comparison</span></h2>
  <p class="lead">Outcome log(L&amp;H employment); treatment = a state's first increase above the federal floor. Pooled-OLS SE is HC1; TWFE SE clustered by 51 states; CSA SE analytic/entity-clustered, pointwise CI.</p>
  {chart("c_cmp", "Estimated % effect with 95% CI", "Bars = point estimate; whiskers = 95% confidence interval. Callaway&ndash;Sant'Anna (blue) is the staggered-robust headline. Every CI crosses zero.", 360)}
  {comp_tbl}
  <div class="takeaway"><b>The staggered-adoption correction barely moves the headline.</b> TWFE (&minus;0.0268) and Callaway&ndash;Sant'Anna (&minus;0.0217) differ by +0.0051 log pts &mdash; 19% of the TWFE magnitude. Moving from pooled OLS to TWFE shifts the estimate by &minus;0.0204 log pts: the size of the confounding the design strips out.</div>
</section>
<section id="twfe"><h2>TWFE event study <span class="em">&amp; parallel-trends test</span></h2>
  <p class="lead">Relative-event-time leads/lags around each state's first increase; base period k = &minus;1; endpoint bins at k &le; &minus;12 and k &ge; 16. State + period FE, SE clustered by state. Sample: 25 treated (with a pre-period) + 20 never-treated = 45 states, 2,880 obs.</p>
  {chart("c_twfe", "TWFE dynamic ATT (leads &amp; lags)", "Points = coefficients (grey = pre-treatment leads, blue = post); shaded band = 95% CI; dashed red line marks treatment (k = &minus;1 base).", 400)}
  {pt_tbl}
  <p class="note">4 of 11 lead coefficients individually significant at 5% (k = &minus;12, &minus;11, &minus;10, &minus;9) &mdash; concentrated in distant leads; near pre-window jointly flat. 6 of 17 post coefficients individually significant; post path negative and widening.</p>
  <details><summary>Full TWFE event-study coefficients (all 29 leads/lags)</summary>{es_tbl}</details>
</section>
<section id="csa"><h2>Callaway&ndash;Sant'Anna <span class="em">(2021) &mdash; staggered-robust</span></h2>
  <p class="lead">Doubly-robust group-time ATT via the <code>differences</code> package. Cohort = quarter of a state's first increase; control = never-treated states. 31 ever-treated + 20 never-treated; 6 always-treated states dropped automatically. 441 ATT(g,t) cells estimated.</p>
  {csa_overall_tbl}
  <div class="grid2">
    {chart("c_csa", "Cohort-robust dynamic ATT", "Points = ATT by event time (grey pre, blue post); band = 95% pointwise CI. Trough &asymp; &minus;1.1% near k = 4.", 360)}
    {chart("c_coh", "ATT by adoption cohort", "Per-cohort overall ATT (blue = negative, gold = positive) with 95% CI. Negative for 2013&ndash;2015 &amp; 2020; positive for 2012 &amp; 2021.", 360)}
  </div>
  {bycoh_tbl}
  <p class="note">Near-window |ATT| max (k &isin; [&minus;4,&minus;1]) = 0.0074 log pts. Post path deepens to a trough of &minus;0.0109 log pts (&minus;1.08%) at k = 4, then partially mean-reverts. No interior post coefficient individually significant at 5% (pointwise).</p>
  <details><summary>Full CSA dynamic ATT table (k = &minus;12 &hellip; 16)</summary>{dyn_tbl}</details>
</section>
<section id="descriptives"><h2>Descriptive <span class="em">evidence</span></h2>
  <p class="lead">Policy variation and raw trends (nothing causal). Treated and control L&amp;H track closely pre-2014 (mean absolute index gap = 0.24 pts).</p>
  <div class="grid2">
    {chart("c_mw", "Effective minimum-wage paths", "Treated-state mean effective minimum wage vs the flat $7.25 federal floor that binds controls. Clear policy variation to exploit.", 340)}
    {chart("c_idx", "L&amp;H employment index (2010Q1 = 100)", "Treated vs never-treated group means, indexed to the panel start. The eyeball parallel-trends check.", 340)}
  </div>
  <h3>Outlier scan &mdash; largest quarter-on-quarter &Delta;log moves (60 exceed 4&sigma;, &sigma; = 0.0766)</h3>
  <p class="note">The largest swings are the 2020Q2 COVID drop (and 2020Q3 rebound), not data errors &mdash; retained; period FE absorb them.</p>
  {out_tbl}
</section>
<section id="placebo"><h2>Placebo &amp; <span class="em">robustness</span></h2>
  <p class="lead">The design finds no effect where none should exist, and the estimate is stable to specification changes. Verdict: <b>PASS</b> (fake-date margins read as &ldquo;no clear failure&rdquo; rather than a pristine null).</p>
  {chart("c_plac", "High-wage-sector placebo &mdash; L&amp;H vs PBSV", "% effect for the main outcome (L&amp;H) vs the placebo sector (Professional &amp; Business Services), TWFE and Callaway&ndash;Sant'Anna. PBSV is near zero, as it should be.", 340)}
  {pbsv_tbl}
  <h3>Fake-event-date falsification (treatment shifted &minus;8 quarters)</h3>
  {fake_tbl}
  <p class="note">Treated states with a clean pre-fake window: 17; controls: 20. The fake DiD (p = 0.100) and the post-fake-dummy joint test (p = 0.086) do not reject; the distant pre-fake leads jointly reject (p = 0.023).</p>
  <div class="grid2">
    {chart("c_win", "TWFE on restricted event windows", "ATT re-estimated on |k| &le; W. Stays in a narrow negative band; whiskers = 95% CI.", 330)}
    {chart("c_hor", "CSA dynamic averaged over post-horizons", "Average cohort-robust ATT over k &isin; [0, kmax] for growing horizons. Small and stable.", 330)}
  </div>
  <h3>Alternative outcome: L&amp;H share of total nonfarm</h3>
  {share_tbl}
  <div class="grid2">{win_tbl}{hor_tbl}</div>
</section>
<section id="figures"><h2>Source <span class="em">figures (static)</span></h2>
  <p class="lead">The original publication figures (matplotlib, 300 DPI), embedded for completeness. The interactive charts above are built from the same underlying data.</p>
  <details><summary>Show all 13 source figures</summary>{appendix_html}</details>
</section>
<section id="caveats"><h2>Caveats &amp; <span class="em">limitations</span></h2>
  <p class="lead">Bottom line: no evidence of <i>large</i> minimum-wage disemployment in U.S. Leisure &amp; Hospitality, 2010&ndash;2025; the data cannot rule out a small negative effect.</p>
  <div class="caveats">{caveat_items}</div>
</section>
</main>
<button id="bt" onclick="window.scrollTo({{top:0,behavior:'smooth'}})" title="Back to top">&#8593;</button>
<footer>
  <b>Minimum Wage &amp; Low-Wage Employment &mdash; Project #4</b> &middot; Proteek Basu &middot; Pre-Masters Economics Portfolio (Georgia Tech MS prep)<br>
  Methods: pooled OLS, two-way fixed effects, TWFE event study, Callaway&ndash;Sant'Anna (2021) group-time ATT. Data: FRED. Charts: Plotly (CDN). Generated by <code>src/build_dashboard.py</code> from <b>results/</b>.
</footer>
"""

html = ("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Minimum Wage and Low-Wage Employment - Results Dashboard (Project #4)</title>"
        "<script src='https://cdn.plot.ly/plotly-2.26.0.min.js'></script>"
        "<style>" + CSS + "</style></head><body>"
        + body
        + "<script>window.CHARTS=" + CHARTS_JSON + ";</script>"
        + "<script>" + JS + "</script>"
        + "</body></html>")

OUT.write_text(html, encoding="utf-8")
print(f"WROTE {OUT} ({OUT.stat().st_size/1024:.0f} KB)")
