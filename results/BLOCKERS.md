# BLOCKERS — Project #4 (Minimum Wage DiD)

## 2026-07-02 (Day 10) — `minwage-did-presentation.pptx` was CORRUPT — REBUILT, needs your visual check

**What broke:** The saved `minwage-did-presentation.pptx` (492,596 bytes, dated Jun 30) is a
damaged OPC/zip package and **cannot be opened by PowerPoint**. Its own central directory and
end-of-central-directory record were overwritten by those of the *embedded* Excel workbook
(`ppt/embeddings/Microsoft_Excel_Worksheet.xlsx`), and every `_rels` relationship part was lost.
Likely cause: the file was still open in PowerPoint / mid-OneDrive-sync when the Day 9 save
completed (the file is currently file-locked in the sandbox — `rm`/overwrite both return
"Operation not permitted", consistent with an open handle).

**What survived:** All authored content is intact — all 7 slide XMLs, 6 notes slides, master,
layout, both themes, the results chart (`chart1.xml`) + its embedded worksheet, and 2 of 3 images.
The 3rd image (`image3.png`, the robustness figure) was truncated in the archive; it is byte-for-byte
`results/fig_robustness.png` (both 116,204 B) and was cleanly substituted.

**Fix applied:** Recovered every good part via `zip -FF`, synthesized the missing `_rels` and
`[Content_Types].xml` from the parts' internal `r:id` references, substituted the good robustness
figure, and re-zipped. Result saved as **`minwage-did-presentation-FIXED.pptx`**. Verified: opens
in python-pptx, 16:9 (10 × 5.625 in), 7 slides, all relationship targets resolve, all 3 images
decode, fonts = Calibri + Georgia (style-guide compliant), palette = 048BE6 / 343E48 / 8A98A5 /
E0E6EB / FFC000 / FFFFFF (+ a green 2E8B57 used only for the ✓ robustness check marks — minor
off-palette accent, left as authored).

**Action needed from you (before committing the deck):**
1. Open `minwage-did-presentation-FIXED.pptx` in PowerPoint and eyeball all 7 slides — the XML is
   faithful but only a visual open confirms rendering.
2. Close any PowerPoint/OneDrive handle on the old `minwage-did-presentation.pptx`, delete the
   corrupt original (and the `minwage-did-presentation.CORRUPT-ORIGINAL.bak` I made — I could not
   delete either; both are file-locked), then rename `-FIXED` → `minwage-did-presentation.pptx`.
3. Commit the renamed working deck. **Do NOT commit the corrupt original or the `.bak`.**

Everything else in the project verified clean (tests 32/32 pass, pipeline reproduces the headline).
This is the only substantive issue found on Day 10.

## 2026-06-24 (Day 3) — Note: no git repo yet (expected, not a blocker)

Project #4 has no `.git` yet, so automated daily commits are skipped. Per Proteek, this is
intentional: all work is done locally and will be committed/pushed to a repo once the project is
finished. No action needed — Day 3 deliverables are saved to disk as normal.


## 2026-06-22 (Day 1) — FRED API unreachable from the automation sandbox — RESOLVED

**Original blocker:** The automation sandbox could not reach FRED (`api.stlouisfed.org` /
`fred.stlouisfed.org` not on the network egress allowlist), so live validation could not run there.

**Resolution:** Proteek ran `py src/series_map.py --validate` **locally** (via the Claude Code /
VSCode environment), where FRED is reachable. Validation now executes. No allowlist change is
strictly required as long as validation and the Day 2+ data pulls are run locally; if a future
*automated* run needs FRED, add those two hosts under Settings → Capabilities → Network access.

## 2026-06-22 (Day 1) — Validation findings (first local run)

First local run returned **117/205 resolved, 88 "missing"** — but 85 of those were **false
negatives from FRED rate-limiting** ("Too Many Requests. Exceeded Rate Limit"): 205 metadata
requests fired back-to-back tripped FRED's ~120 req/min cap from ~`NH` onward (alphabetical).

**Fix applied to `src/series_map.py`:** the validator now (a) throttles to ~100 req/min
(`REQUEST_SLEEP_S = 0.6`) and (b) retries rate-limited lookups with exponential backoff
(`MAX_RETRIES = 5`). It also now separates two categories in the report so transient errors are
never confused with real misses:

- **Missing / discontinued** = FRED returns "does not exist" -> dropped, not imputed.
- **Transient** = rate-limit/network -> NOT dropped; re-run resolves them.

### Genuinely missing series (confirmed, to be dropped — not imputed)

Confirmed "series does not exist" on FRED:

- `STTMINWGAL` (Alabama), `STTMINWGLA` (Louisiana), `STTMINWGMS` (Mississippi)

These three states have **no state minimum-wage statute** and default to the federal floor — so
FRED carries no `STTMINWG` series for them. This is expected, not a data error. **Likely also
missing once the rate-limited batch is re-checked:** `STTMINWGSC` (South Carolina) and
`STTMINWGTN` (Tennessee), the other two no-statute states.

**Methodological handling:** drop the *treatment* (`STTMINWG`) series for these states only. They
remain in the panel as **never-treated control jurisdictions** whose binding wage is the federal
minimum (captured by `FEDMINNFRWG`). Their outcome/normalizer/control series (`<XX>LEIH`, `<XX>NA`,
`<XX>UR`) are unaffected and should resolve normally.

### Action: one clean re-run needed to finalize the checkpoint

```
py src/series_map.py --validate
```

Expected clean result: ~**200/205 resolved, ~5 missing, 0 transient**, where the ~5 missing are
exactly the `STTMINWG` series for the no-statute states (AL, LA, MS, SC, TN). Once that run shows
**0 transient**, the Day 1 series-map checkpoint is complete.
