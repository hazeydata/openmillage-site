#!/usr/bin/env python3
"""OM-SITE-SOURCE-LEAD-001: the homepage lead names every source type present in the data, and a build with an
unknown source fails without touching docs/. Run from the repo root after build.py and amend3.py:
python3 tests/test_source_lead.py"""
import csv, hashlib, html, json, os, re, shutil, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)
BASE, SD, ALT, LOCK = "data/fl-2025.csv", "data/special/fl-2025-special-districts.csv", "data/special/fl-2025-alt-sources.csv", "data/SOURCES.lock"

# Expected lead terms, written by hand from the raw source_agency values in the CSVs (not imported from build.py).
# A new agency in the data that is not listed here fails this test until someone decides how the lead should name it.
PRIMARY = {
    "Florida Department of Revenue (Data Book: Millage and Taxes Levied, sheet 'Millage Rates')": "Florida DOR",
    "Florida Department of Revenue, Property Tax Oversight (2025 TACD, as filed by the county property appraiser)": "Florida DOR",
    "Florida Office of Economic & Demographic Research (Municipal Ad Valorem Tax Profile; data source FL DOR)": "EDR",
    "DeSoto County Property Appraiser (2025 DeSoto County Final Millage)": "county property appraisers",
    "Orange County Property Appraiser (2025 Final Millage Rates, taxing authorities by mill code)": "county property appraisers",
}
ADDITIONAL = {"Pasco County Board of County Commissioners (Resolution No. 25-348)": "Pasco County BOCC resolution"}
ORDER = ["Florida DOR", "EDR", "county property appraisers"]

def rd(p): return list(csv.DictReader(open(p, encoding="utf-8")))
alt = rd(ALT)
prim_rows = rd(BASE) + rd(SD) + [r for r in alt if r["body_type"] == "special_district"]
addl_rows = [r for r in alt if r["body_type"] != "special_district"]
counts = {}
for r in prim_rows:
    a = r["source_agency"]; ok(a in PRIMARY, f"primary source_agency mapped: {a}") if a not in PRIMARY else None
    counts[PRIMARY.get(a, a)] = counts.get(PRIMARY.get(a, a), 0) + 1
for r in addl_rows:
    ok(r["source_agency"] in ADDITIONAL, f"additional source_agency mapped: {r['source_agency']}") if r["source_agency"] not in ADDITIONAL else None
types = sorted(counts, key=lambda t: ORDER.index(t) if t in ORDER else 99)
extras = sorted({ADDITIONAL.get(r["source_agency"], r["source_agency"]) for r in addl_rows})
for t in types: print(f"  {t}: {counts[t]} row(s)")
for e in extras: print(f"  additional: {e}")
join = lambda xs: xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]
expected = f"{len(prim_rows)} official rates from {join(types)}" + (
    f" (additional source{'s' if len(extras) > 1 else ''}: {join(extras)})" if extras else "") + ", retrieved "

idx = open("docs/index.html", encoding="utf-8").read()
m = re.search(r"<p class=lead>(\d+ official rates [^<]*)</p>", idx)
ok(bool(m), "homepage lead paragraph present")
lead = html.unescape(m.group(1)) if m else ""
print("lead:", lead)
for t in types: ok(t in lead, f"lead names source type '{t}'")
ok(lead.startswith(expected), f"lead starts exactly with: {expected!r}")
ok(("(additional source: " in lead) == (len(extras) == 1) and ("(additional sources: " in lead) == (len(extras) > 1),
   "additional-source label is singular for one source, plural for several")

# Failure path: an unknown source must stop the build with a non-zero exit and leave docs/ byte-for-byte unchanged.
def tree(d):
    return {os.path.relpath(os.path.join(p, f), d): hashlib.sha256(open(os.path.join(p, f), "rb").read()).hexdigest()
            for p, _, fs in os.walk(d) for f in fs}
def planted(path, old, new):
    tmp = tempfile.mkdtemp()
    for n in ("build.py", "sources.py", "amend3.py", "analytics.py", "site_chrome.py", "amend3_config.json"): shutil.copy(n, tmp)
    shutil.copytree("data", os.path.join(tmp, "data")); shutil.copytree("docs", os.path.join(tmp, "docs"))
    p = os.path.join(tmp, path); s = open(p, encoding="utf-8").read(); assert old in s, old
    open(p, "w", encoding="utf-8").write(s.replace(old, new, 1))
    lp = os.path.join(tmp, LOCK); lock = json.load(open(lp))
    for f in lock["files"]:
        if f["path"] == path: f["sha256"] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    json.dump(lock, open(lp, "w"), indent=1)
    before = tree(os.path.join(tmp, "docs"))
    r = subprocess.run([sys.executable, "build.py"], cwd=tmp, capture_output=True, text=True,
                       env=dict(os.environ, DATA_GLOB="data/*.csv", PYTHONDONTWRITEBYTECODE="1"))
    after = tree(os.path.join(tmp, "docs")); shutil.rmtree(tmp)
    return r, before == after
for path, old, label in ((BASE, "Florida Office of Economic & Demographic Research (Municipal", "primary"),
                         (ALT, "Pasco County Board of County Commissioners", "additional")):
    r, same = planted(path, old, "Acme Unknown Agency (")
    ok(r.returncode != 0 and "unmapped" in r.stderr and "source_agency" in r.stderr,
       f"unknown {label} source: build exits non-zero naming the unmapped source_agency (rc={r.returncode})")
    ok(same, f"unknown {label} source: docs/ unchanged after the failed build")
print("FAIL" if FAIL else "ALL PASS", len(FAIL)); sys.exit(1 if FAIL else 0)
