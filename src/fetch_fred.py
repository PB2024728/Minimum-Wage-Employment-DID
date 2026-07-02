"""
fetch_fred.py - Pull every FRED series in the Day-1 series map into data/raw/ (cached).

For each (jurisdiction, role, series_id) in series_map.series_index() this script downloads
the full observation history from FRED and writes it to a per-series CSV cache under data/raw/.
Re-runs are cheap: a series whose cache file already exists is skipped unless --refresh is
passed, so we never re-hit the API needlessly.

Series that genuinely do not exist on FRED (the no-statute states' STTMINWG: AL, LA, MS, SC, TN)
are logged and skipped - never imputed. Transient rate-limit / network errors are retried with
exponential backoff and, if still failing, recorded as errors (NOT as "missing") so a re-run can
resolve them.

Outputs
-------
data/raw/<SERIES_ID>.csv        one file per resolved series: columns [date, value]
data/raw/_fetch_manifest.json   machine-readable record of what was fetched / skipped / missing
results/fetch_summary.md        human-readable summary

Project rules honoured
----------------------
* FRED_API_KEY read from .env via python-dotenv; never hardcoded or printed.
* Raw pulls cached in data/raw so re-runs don't re-hit the API.
* Missing/discontinued series are dropped WITH A NOTE, never imputed.
* Standalone + idempotent.

Usage
-----
    python fetch_fred.py            # fetch all (uses cache where present)
    python fetch_fred.py --refresh  # ignore cache, re-download everything
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from series_map import series_index, PROJECT_ROOT  # local module

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RAW_DIR = PROJECT_ROOT / "data" / "raw"
RESULTS_DIR = PROJECT_ROOT / "results"
ENV_PATH = PROJECT_ROOT / ".env"
MANIFEST_PATH = RAW_DIR / "_fetch_manifest.json"

# ---------------------------------------------------------------------------
# Throttle / retry (FRED documented limit ~120 req/min)
# ---------------------------------------------------------------------------
REQUEST_SLEEP_S = 0.6
MAX_RETRIES = 5
BACKOFF_BASE_S = 2.0


def _load_fred():
    """Authenticated Fred client from .env. Never prints the key."""
    from dotenv import load_dotenv
    from fredapi import Fred
    load_dotenv(ENV_PATH)
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise RuntimeError(f"FRED_API_KEY not found in {ENV_PATH}")
    return Fred(api_key=api_key)


def _is_rate_limited(err: str) -> bool:
    e = err.lower()
    return "too many requests" in e or "rate limit" in e


def _is_does_not_exist(err: str | None) -> bool:
    if not err:
        return False
    e = err.lower()
    return "does not exist" in e or ("bad request" in e and "rate limit" not in e)


def _get_series_with_retry(fred, sid: str):
    """Return (pandas.Series, None) on success or (None, error_str) on failure."""
    err = None
    for attempt in range(MAX_RETRIES):
        try:
            return fred.get_series(sid), None
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
            if _is_rate_limited(err) and attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_BASE_S * (2 ** attempt))
                continue
            return None, err
    return None, err


def _cache_path(sid: str) -> Path:
    return RAW_DIR / f"{sid}.csv"


def fetch_all(refresh: bool = False) -> dict:
    """Fetch every unique series in the map, caching to data/raw/. Returns a manifest dict."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    index = series_index()
    # De-duplicate series IDs (each ID appears once; map has no dupes, but be safe).
    seen: set[str] = set()
    unique_records = []
    for rec in index:
        if rec["series_id"] not in seen:
            seen.add(rec["series_id"])
            unique_records.append(rec)

    fred = None  # lazy: only build the client if we actually need to hit the network

    fetched, cached, missing, errors = [], [], [], []

    for rec in unique_records:
        sid = rec["series_id"]
        cpath = _cache_path(sid)

        if cpath.exists() and not refresh:
            try:
                df = pd.read_csv(cpath)
                cached.append({**rec, "n_obs": int(len(df)), "cache": cpath.name})
                continue
            except Exception:
                pass  # corrupt cache -> re-fetch below

        if fred is None:
            fred = _load_fred()

        s, err = _get_series_with_retry(fred, sid)
        time.sleep(REQUEST_SLEEP_S)

        if s is not None:
            s = s.dropna()
            out = s.rename("value").rename_axis("date").reset_index()
            out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
            out.to_csv(cpath, index=False)
            fetched.append({**rec, "n_obs": int(len(out)),
                            "obs_start": out["date"].min() if len(out) else None,
                            "obs_end": out["date"].max() if len(out) else None,
                            "cache": cpath.name})
        elif _is_does_not_exist(err):
            missing.append({**rec, "error": err})
        else:
            errors.append({**rec, "error": err})

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "refresh": refresh,
        "n_unique_series": len(unique_records),
        "n_fetched": len(fetched),
        "n_cached": len(cached),
        "n_missing": len(missing),
        "n_errors": len(errors),
        "fetched": fetched,
        "cached": cached,
        "missing": missing,
        "errors": errors,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_summary(manifest)
    return manifest


def _write_summary(m: dict) -> None:
    lines = [
        "# FRED Fetch Summary - Project #4 (Day 2)",
        "",
        f"_Generated: {m['generated_utc']}_",
        "",
        f"- Unique series in map: **{m['n_unique_series']}**",
        f"- Fetched this run: **{m['n_fetched']}**",
        f"- Served from cache: **{m['n_cached']}**",
        f"- Missing / discontinued (dropped, not imputed): **{m['n_missing']}**",
        f"- Transient errors (re-run to resolve): **{m['n_errors']}**",
        "",
    ]
    if m["missing"]:
        lines += ["## Missing / discontinued (dropped, not imputed)", "",
                  "| Jurisdiction | Role | Series ID | Error |", "|---|---|---|---|"]
        for x in m["missing"]:
            lines.append(f"| {x['jurisdiction']} | {x['role']} | `{x['series_id']}` | {x['error']} |")
        lines.append("")
    if m["errors"]:
        lines += ["## Transient errors (NOT treated as missing; re-run to resolve)", "",
                  "| Jurisdiction | Role | Series ID | Error |", "|---|---|---|---|"]
        for x in m["errors"]:
            lines.append(f"| {x['jurisdiction']} | {x['role']} | `{x['series_id']}` | {x['error']} |")
        lines.append("")
    (RESULTS_DIR / "fetch_summary.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    refresh = "--refresh" in sys.argv
    print(f"Fetching FRED series into {RAW_DIR} (refresh={refresh}) ...")
    man = fetch_all(refresh=refresh)
    print(f"Done: {man['n_fetched']} fetched, {man['n_cached']} cached, "
          f"{man['n_missing']} missing, {man['n_errors']} transient errors.")
    if man["missing"]:
        print("Missing (dropped, not imputed): "
              + ", ".join(x["series_id"] for x in man["missing"]))
    if man["errors"]:
        print("Transient errors remain (re-run): "
              + ", ".join(x["series_id"] for x in man["errors"]))
        sys.exit(1)
