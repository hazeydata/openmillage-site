#!/usr/bin/env python3
"""OM-SITE-SOURCE-LEAD-001: the homepage lead names every source type present in the data. Run from the repo root after
build.py and amend3.py: python3 tests/test_source_lead.py"""
import html, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)
os.environ.setdefault("DATA_GLOB", "data/*.csv")
import sources
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)
# Independent of build.py's mapping: classify from the raw source_agency field.
TYPES = [(r"^Florida Department of Revenue", "Florida DOR"), (r"^Florida Office of Economic & Demographic Research", "EDR"),
         (r"County Property Appraiser", "county property appraisers"), (r"County Board of County Commissioners", "county commissions")]
rows = sources.load_rows()
agencies = {r["source_agency"] for r in rows} | {a["source_agency"] for r in rows for a in r.get("additional_sources") or []}
found = {}
for ag in agencies:
    t = [n for p, n in TYPES if re.search(p, ag)]
    ok(len(t) == 1, f"source_agency classified: {ag}")
    if t: found.setdefault(t[0], 0)
for r in rows:
    for p, n in TYPES:
        if re.search(p, r["source_agency"]): found[n] = found.get(n, 0) + 1
idx = open("docs/index.html", encoding="utf-8").read()
m = re.search(r"<p>(\d+ official rates [^<]*)</p>", idx)
ok(bool(m), "homepage lead paragraph present")
lead = html.unescape(m.group(1)) if m else ""
print("lead:", lead)
for t, n in sorted(found.items()):
    print(f"  {t}: {n} row(s)")
    ok(t in lead, f"lead names source type '{t}'")
ok(f"{len(rows)} official rates" in lead, "lead row count matches data")
ok("from Florida DOR and EDR," not in lead or set(found) <= {"Florida DOR", "EDR"}, "lead does not claim DOR/EDR only")
print("FAIL" if FAIL else "ALL PASS", len(FAIL)); sys.exit(1 if FAIL else 0)
