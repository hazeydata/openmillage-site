#!/usr/bin/env python3
"""Appraiser-only counties (DeSoto, Orange) have their own status and are never listed as "not yet collected". Counts come from
data/special/fl-2025-alt-sources.csv. Run from the repo root after build.py and amend3.py: python3 tests/test_desoto_orange.py"""
import csv, html, os, re, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)
import amend3, sources
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)

ALT = "data/special/fl-2025-alt-sources.csv"
def csv_counts(path):
    c = {}
    for r in csv.DictReader(open(path, newline="", encoding="utf-8")):
        if r["body_type"] == "special_district": c[r["county"]] = c.get(r["county"], 0) + 1
    return c
def render():
    CFG = amend3.CFG
    rows = amend3.rows_from(CFG["rates_csv"]); dist = amend3.rows_from(CFG["districts_csv"])
    cty = [(r["name"].removesuffix(" County"), r["geoid"]) for r in csv.DictReader(open(CFG["counties_csv"]))]
    ballot = __import__("json").load(open(CFG["ballot_json"]))
    return html.unescape(amend3.render_amend3(rows, dist, ballot, cty)[0])
def cov_para(h):
    i = h.index("Special districts: "); return h[i:h.index("</p>", i)]
def check(h, label, counts):
    names = sorted(counts)
    nyc = [m for m in re.findall(r"[Nn]ot yet (?:collected|sourced)[^.<]*", h)]
    ok(all(c not in m for m in nyc for c in names), f"{label}: {names} not in any 'not yet collected' list")
    para = cov_para(h) if "Special districts: " in h else h
    status = "Appraiser rows only, not in baseline CSV: " + ", ".join(f"{c} ({n} row{'' if n == 1 else 's'})" for c, n in sorted(counts.items())) + "."
    ok(status in para, f"{label}: status names them with CSV counts: {status}")
    names_sentence = " and ".join(f"{c} ({n} row{'' if n == 1 else 's'})" for c, n in sorted(counts.items()))
    ok(names_sentence in para, f"{label}: body sentence counts match the CSV ({names_sentence})")

alt_only = sources.coverage(sources.load_rows())["alt_only"]
counts = csv_counts(ALT)
want = {c: counts[c] for c in alt_only}
ok(sorted(want) == ["DeSoto", "Orange"], f"alt-only counties are DeSoto and Orange: {sorted(want)}")
ok(sources.alt_counts(alt_only) == want, "sources.alt_counts equals counts computed directly from the CSV")
check(render(), "amend3 render", want)

# Perturbation: an extra Orange row in a temp alt-sources CSV changes the rendered count to 4 (nothing hard-coded)
src = list(csv.DictReader(open(ALT, newline="", encoding="utf-8")))
extra = dict(next(r for r in src if r["county"] == "Orange" and r["body_type"] == "special_district"), body_id="fl-test-special_district")
tmp = os.path.join(tempfile.mkdtemp(), "alt.csv")
with open(tmp, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(src[0])); w.writeheader(); w.writerows(src + [extra])
orig_file, orig_lock = sources.ALT_FILE, sources.read_lock
def lock_with_tmp(*a):
    lk = orig_lock(*a)
    for e in lk["files"]:
        if e["path"] == orig_file: e["path"] = tmp
    return lk
sources.ALT_FILE, sources.read_lock = tmp, lock_with_tmp
try:
    h = render()
    ok(csv_counts(tmp)["Orange"] == counts["Orange"] + 1 and "Orange (4 rows)" in h and "Orange (3 rows)" not in h, "perturbed CSV: rendered Orange count becomes 4")
    check(h, "perturbed render", {c: csv_counts(tmp)[c] for c in want})
finally:
    sources.ALT_FILE, sources.read_lock = orig_file, orig_lock

# Singular wording
ok(sources.alt_sentence({"DeSoto": 1}) == "DeSoto (1 row) has special-district rates from its county property appraiser. It's on that county page but not in the baseline CSV.", "one alt county: singular wording")
ok(sources.alt_meta_sentence({"DeSoto": 1, "Orange": 3}) == "DeSoto and Orange special-district rows come from county appraisers and are on their county pages only.", "meta wording")

# Built output, if present
for p in ("docs/index.html", "docs/fl/amendment-3/index.html", "docs/llms.txt"):
    if not os.path.isfile(p): print("SKIP " + p + " (not built)"); continue
    h = html.unescape(open(p, encoding="utf-8").read())
    body_sentence = sources.alt_sentence(want)
    ok(body_sentence in h, f"{p}: carries the generated body sentence")
    if p.endswith("amendment-3/index.html"):
        check(h, p, want)
    else:
        ok(not any(c in m for m in re.findall(r"[Nn]ot yet (?:collected|sourced)[^<\n]*", h) for c in want), f"{p}: DeSoto/Orange not in a not-yet list")
    if p.endswith(".html"):
        metas = re.findall(r'<meta name="?description"? content=["\']([^"\']*)', h) + re.findall(r'"description": ?"([^"]*)"', h)
        ok(not metas or all(sources.alt_meta_sentence(want) in m for m in metas if "special-district" in m), f"{p}: meta/JSON-LD descriptions use the meta wording")

print("\n%d failed" % len(FAIL) if FAIL else "\nall passed"); sys.exit(1 if FAIL else 0)
