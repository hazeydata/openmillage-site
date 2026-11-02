# Page copy, OM NC rates and FL rolled-back pages (extracted from built HTML)

## NC hub: nc/property-tax-rates/
North Carolina property tax rates by county, FY2021-22 to FY2025-26

Skip to contentOpenMillage › North Carolina

### North Carolina property tax rates by county, FY2021-22 to FY2025-26
Between FY2021-22 and FY2025-26, 81 of North Carolina's 100 counties lowered their general property tax rate, 9 raised it and 10 kept it the same. Rates below are per $100 of assessed value, straight from NC Department of Revenue spreadsheets.
About the unit. Every rate here is dollars per $100 of assessed value, so 0.5000 means 50 cents per $100. Only North Carolina DOR's FY2025-26 county rate PDF states that unit (“(All rates per $100 valuation*)”, source). The DOR spreadsheets the other rates come from carry no unit label, so for those rates the unit is inferred, not stated. In DOR's words from our data notes: “NC DOR doesn't state a unit for this rate; we read it as per $100 based on older DOR tables” (Table 67). Rates marked i use the inferred unit.1
1. North Carolina law caps these rates per $100 of value, so per $100 is also inferred from statute: city rates under G.S. 160A-209(d), city service districts under G.S. 160A-542(c) and county service districts under G.S. 153A-307. Back
Rural fire districts: not collected yet. This page shows county and city rates only. Fire, rescue and other special-district rates aren't on it.
County general rate, FY2021-22 vs FY2025-26, per $100 of value. Source: NC DOR, via the table below. SVG.

### Every county, five yearsFind a county
Change is the FY2025-26 rate minus the FY2021-22 rate, both from DOR. Click a column heading to sort. Each county page also lists its cities and towns. Data file: hazeydata/openmillage data/nc-2021..2025.csv.

## NC county page sample: nc/wake-county/
Wake County NC property tax rate, FY2021-22 to FY2025-26

Skip to contentOpenMillage › North Carolina › Wake County

### Wake County NC property tax rate, FY2021-22 to FY2025-26
Wake County's general property tax rate is 0.5171 per $100 of assessed value in FY2025-26, down from 0.6000 in FY2021-22 (-0.0829). Cities and towns add their own rate on top for property inside their limits.
About the unit. Every rate here is dollars per $100 of assessed value, so 0.5000 means 50 cents per $100. Only North Carolina DOR's FY2025-26 county rate PDF states that unit (“(All rates per $100 valuation*)”, source). The DOR spreadsheets the other rates come from carry no unit label, so for those rates the unit is inferred, not stated. In DOR's words from our data notes: “NC DOR doesn't state a unit for this rate; we read it as per $100 based on older DOR tables” (Table 67). Rates marked i use the inferred unit.1
1. North Carolina law caps these rates per $100 of value, so per $100 is also inferred from statute: city rates under G.S. 160A-209(d), city service districts under G.S. 160A-542(c) and county service districts under G.S. 153A-307. Back

### County rate

### City and town rates in Wake County
Rural fire districts: not collected yet. This page shows county and city rates only. Fire, rescue and other special-district rates aren't on it.
Each rate links to the DOR spreadsheet for its year; hover for the exact row and cell. “not listed” means DOR's sheet for that year has no row for that body. A town in two counties shows once per county portion.
All 100 North Carolina counties

## FL: fl/rolled-back-rate/
Florida rolled-back rate vs adopted millage, 2025

Skip to contentOpenMillage › Florida rolled-back rate

### Florida rolled-back rate vs adopted millage, 2025
In 2025, 733 of the 927 Florida levies we could compare were adopted above their rolled-back rate, 69 matched it and 125 came in below it. Under Florida's TRIM law, adopting a rate above the rolled-back rate counts as a tax increase.

### What the rolled-back rate is
The rolled-back rate is the millage that would raise the same property tax revenue as last year, leaving out new construction. Every taxing authority computes it each summer during TRIM (Truth in Millage). Florida DOR publishes each authority's rolled-back and adopted rates after the fact (DOR method). One mill is $1 per $1,000 of taxable value.
Adopted minus rolled-back millage, 927 Florida 2025 levies. Source: Florida DOR, via the table below. SVG.

### Every levyFind a county or body
Adopted minus rolled-back is computed from the two DOR figures in the same row. Click a column heading to sort. Data file: fl-2025-rollback.csv.

### What isn't here
These aren't in DOR's statewide rolled-back reports, so they aren't on this page:
FL 2025 school districts: No statewide official per-district 2025 school rolled-back-rate file was found; only per-district DR-420S filings exist.
FL 2025 independent special districts levying less than 5 years not printed in MillCapComp25: MillCapComp25 excludes independent special districts levying less than 5 years except rows it prints with *; no statewide rolled-back file covers the rest.
FL 2025 independent special districts not subject to maximum millage: Districts outside the maximum-millage reports have no statewide rolled-back file.
FL 2025 dependent districts and MSTUs of independent special districts: No statewide rolled-back file itemizes dependent districts of independent special districts.
FL 2025 all taxing authorities, per-authority DR-420 filings: DOR publishes no bulk DR-420 dataset; filings sit behind the eTRIM/OASYS login, which was not accessed.
FL 2025 Broward Table 1 row 'Sunrise Key' (CITY OF FORT LAUDERDALE): duplicate row in source: Broward_Table_1.pdf p1 repeats every value of the 'City of Sunrise' row (p2); its real levy is not printed in any source. Fact check: evidence/om-rollback/fact/verdicts.md
4 rows are in our file but can't be compared because a rate is missing or the rolled-back rate is zero:
Duette Fire Rescue District (Manatee): rolled-back 0.0000, adopted not printed (source, row 636)
North River Fire District (Manatee): rolled-back 0.0000, adopted 0.5000 (source, row 639)
King's Crest (Osceola): rolled-back not printed, adopted not printed (source, row 838)
Law Enforcement (Santa Rosa): rolled-back 0.0000, adopted 2.0700 (source, row 879)

## Chart alt text (dataviz, verbatim)

#### nc-rates.png
Dot plot of all 100 North Carolina counties, one row each, showing the county general property tax rate in dollars per $100 of valuation for FY2021-22 (open dot) and FY2025-26 (blue dot), sorted by change. 81 counties fell, 9 rose and 10 were unchanged. The largest increase was Currituck (+16.0 cents per $100) and the largest decreases were Cumberland (−30.0 cents) and Franklin (−29.0 cents). Rates range from $0.225 to $1.00. The unit basis is stated in the source for FY2025-26 and inferred for FY2021-22.

#### fl-rollback.png
Strip plot of 927 Florida 2025 operating levies, showing adopted millage minus rolled-back millage in three rows: above (733 levies, blue), equal (69, grey) and below (125, orange). The median difference is +0.08 mills. Most above-rate levies sit within 0 to +0.5 mills, and the highest is Bunnell (Flagler) at +2.23 mills. The lowest is Waterway Shores Light (Lee) at −5.59 mills. Four source rows are not plotted because they have no usable rolled-back or adopted rate, and school districts and some special districts are out of scope.
