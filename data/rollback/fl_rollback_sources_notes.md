# FL 2025 rolled-back vs adopted millage: official sources (OM-ROLLBACK-SOURCES-001)

Read 2026-10-27 (America/Toronto). Downloads are in `raw/`, with `raw/SHA256SUMS` and `raw/fetch_log.tsv`. The row index is `fl_rollback_sources.csv` (83 rows). Every source is from floridarevenue.com (FL DOR) or edr.state.fl.us (Legislature EDR). Every fetch returned HTTP 200, with no CHALLENGE or block. robots.txt allows /property/ on floridarevenue.com. edr.state.fl.us has no robots.txt (404), so all paths are allowed.

## What exists (2025)
DOR publishes no "comp25" spreadsheet. The 2025 files are PDFs only:
1. **MillCapComp25.pdf** gives per-authority millage: `2024 Millage`, `Rolled-Back Rate`, `Majority Vote Rate`, `2025 Rate`, `Extraordinary Vote Required`. It covers 67 counties (BCC row), 393 municipalities, 114 single-county ISDs and 15 multi-county ISDs, including the water management districts. Operating levies only.
   https://floridarevenue.com/property/Documents/MillCapComp25.pdf
   It is byte-identical to the Data Portal copy:
   https://floridarevenue.com/property/dataportal/Documents/PTO%20Data%20Portal/Max%20Millage%20Compliance/Comparison-Millage%20Rate/MillCapComp25.pdf
2. **comp25.pdf** is the same set of authorities in dollars: taxes at the rolled-back rate vs the adopted rate, with `$` and `%` differences. The **two copies differ**. The /property/Documents copy (created 2026-06-10) is newer than the Data Portal copy (created 2026-02-26), and their statewide municipal totals differ. Prefer the /property/Documents copy.
   https://floridarevenue.com/property/Documents/comp25.pdf
   https://floridarevenue.com/property/dataportal/Documents/PTO%20Data%20Portal/Max%20Millage%20Compliance/Comparison-Taxes%20Levied/comp25.pdf
3. **Table 1, Comparison of Taxes Levied (25table1)** has 67 county PDFs plus a statewide one. Columns are `RBR Rate`, `As Adopted Millage Rate` and `% Diff. from RBR` for each levy. **Only this source itemizes county MSTUs and dependent districts and municipal dependent districts (e.g. DDAs).** No ISDs and no schools. Hernando's file is misspelled `Heranando Table 1.pdf` on the server.
   https://floridarevenue.com/property/dataportal/Documents/PTO%20Data%20Portal/County%20Municipal%20Reports/Table%201-Comparison%20of%20Levies/25table1/Alachua%20Table%201.pdf (the other counties follow the same pattern)
   Methodology: https://floridarevenue.com/property/Documents/method.pdf. It says rolled-back rates come from DR-420 and adopted rates from DR-420MM or DR-422.
   Linking page: https://floridarevenue.com/property/Pages/TRIM_MaximumMillage.aspx

Naming check on prior years: MillCapComp07 through MillCapComp25, comp07 through comp25, and 08table1 through 25table1 are all in the Data Portal. MillCapComp24 and comp24 have the same layout as 2025.

## EDR
EDR does **not** republish rolled-back rates. Its Ad Valorem Tax Profiles carry adopted millage only: advaltxco.xlsx (counties), advaltxmu.xlsx (municipalities) and advaltxsd.xlsx (school districts).
https://edr.state.fl.us/Content/local-government/data/data-a-to-z/a-f.cfm
The DOR 2025 Data Book file millage_taxes_levied.xlsx also has adopted millage only, aggregated per county.

## Gaps / NOT published (not_found)
- **School districts:** I found no official statewide 2025 school rolled-back-rate file at DOR, EDR or FLDOE. The only sources are each district's own TRIM documents (DR-420S).
- **DR-420 per-authority data:** DOR publishes no bulk dataset. The forms are filed through the eTRIM/OASYS ePortal, which needs a login; I did not access it.
- **Independent special districts:** only ISDs subject to the maximum-millage limits that have levied for 5 years or more are covered. Newer ISDs, and any ISD outside those reports, have no statewide rolled-back file.
- **MillCapComp25:** no `% over rolled-back` column (compute it as 2025 Rate / Rolled-Back Rate - 1). County MSTUs and dependent districts are not itemized here (use Table 1).
- No CSV or XLSX version of any rolled-back report. Every source is a PDF and needs table extraction.
- Typos in the files: comp25 is stamped "DOR 1/26/2025" while MillCapComp25 says "01-26-26". Read the comp25 date as probably 2026-01-26; this is unconfirmed.
- Wayback availability check returned HTTP 429. Nothing was archived or captured.

## Link check
The box link checker (`linkcheck.py`) was run on this file and on the CSV on 2026-10-27: 82 unique URLs, all OK, with 0 DEAD, CHALLENGE, BLOCKED or ERROR. Report: `linkcheck-2026-10-27/linkcheck-report.md`.
