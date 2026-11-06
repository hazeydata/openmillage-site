# CAPTIONS — OM-SITE-TX-001 dataviz (TX YoY county totals)

Art slots per `/workspace/evidence/OM-SITE-TX-001/writing/LAYOUT.md`. Wording from `VOICE-DRAFT.md` chart captions / keynums. Numbers below are the recomputed pin counts (48 rose / 194 fell / 11 unchanged / 1 Culberson null pair at `2166c845…`); they match VOICE-DRAFT. Lucille 2’s second steering note said “48 rose / 194 held / 11 fell” — that swap is wrong; do not use it in page copy.

No mismatch vs VOICE-DRAFT keynums (Jeff Davis +58.7, Willacy +56.3, Baylor +38.0; Cochran −26.1, Bee −25.2, Hopkins −24.8).

## Rose / held panel

- **Files:** `tx-yoy-rose-held.png`, `tx-yoy-rose-held.svg` (script `tx-yoy-rose-held.py`)
- **Caption (VOICE-DRAFT):** Counties whose county total rate rose or held, 2021 vs 2025, per $100 of value. Source: Texas Comptroller, via the table below.
- **Alt text:** Dumbbell chart of 59 Texas counties whose county total property tax rate rose or stayed the same from 2021 to 2025. Open dots are 2021 rates and blue dots are 2025 rates, in dollars per $100 of taxable value; labels show the change in cents per $100. Title: 48 of 254 Texas counties raised their total rate and 11 held it; the largest rise was Jeff Davis, +58.7 cents per $100. Culberson County is excluded because its 2025 total is not reported.

## Fell panel

- **Files:** `tx-yoy-fell.png`, `tx-yoy-fell.svg` (script `tx-yoy-fell.py`)
- **Caption (VOICE-DRAFT):** Counties whose county total rate fell, 2021 vs 2025, per $100 of value. Source: Texas Comptroller, via the table below.
- **Alt text:** Dumbbell chart of 194 Texas counties whose county total property tax rate fell from 2021 to 2025. Open dots are 2021 rates and blue dots are 2025 rates, in dollars per $100 of taxable value; labels show the change in cents per $100. Title: 194 of 254 Texas counties had a lower total rate in 2025 than in 2021; the largest drop was Cochran, −26.1 cents per $100. Culberson County is excluded because its 2025 total is not reported.

## Keynums (for implement beside each figure; VOICE-DRAFT)

Rose/held: In numbers: 48 counties raised their rate and 11 kept it the same. Biggest rises per $100: Jeff Davis County (+58.7 cents), Willacy County (+56.3 cents) and Baylor County (+38.0 cents).

Fell: In numbers: 194 counties lowered their rate. Biggest drops per $100: Cochran County (−26.1 cents), Bee County (−25.2 cents) and Hopkins County (−24.8 cents).

## Chart source note (VOICE-DRAFT; also on-figure)

Source: hazeydata/openmillage-site data/tx/tx-2021.csv and data/tx/tx-2025.csv (body_type = county, levy_component = total, one row per county; Texas Comptroller).
Unit basis: statutory_per_100 (Tex. Tax Code §26.04(c), §26.062(d)(1), §26.07).
253 of 254 counties compared; Culberson County excluded because its 2025 total rate is not reported. 194 fell, 48 rose, 11 unchanged.
2025 rates are preliminary (Comptroller Working version).

## Data JSON for implement

- `tx-yoy-counts.json` — keynums, null pair, biggest movers, pin + sha256
- `tx-yoy-series.json` — `rose_or_held` and `fell` arrays in chart order; rate strings verbatim from CSV
