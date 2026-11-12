#!/usr/bin/env python3
"""Rate/millage display formatting (site_chrome.rate_text) and no binary float noise on any built page.
Run from the repo root after build.py, amend3.py and statepages.py:  python3 tests/test_rate_format.py"""
import glob, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)
from site_chrome import rate_text
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)
rd = lambda p: open(p, encoding="utf-8").read()

for s, want in [(str(0.4538 + 0.0089), "0.4627"), ("0.46270000000000006", "0.4627"), ("0.5000", "0.5000"), ("9.74309476946416", "9.74309476946416"),
                ("0.007182999999999999", "0.007183"), ("", ""), ("0.000012300000000000001", "0.0000123")]:
    ok(rate_text(s) == want, f"rate_text({s!r}) == {want!r}, got {rate_text(s)!r}")

page = rd("docs/tx/travis-county/index.html")
row = next(r for r in re.findall(r"<tr>.*?</tr>", page, re.S) if "Austin" in r)
cells = re.findall(r"<td class=num data-v='([^']*)'>", row)
ok(len(cells) >= 2 and cells[1] == "0.4627" and "0.4627</a>" in row, "Travis County Austin row shows 0.4627 in the 2022 column")
ok("0.46270000000000006" not in page, "Travis County page does not contain 0.46270000000000006")

ALLOW = {"docs/fl/history/duval-county/county/index.html": "9.74309476946416"}
files = sorted(glob.glob("docs/**/*.html", recursive=True)) + ["docs/llms.txt"]
bad = []
for f in files:
    t = rd(f)
    if f in ALLOW: t = t.replace(ALLOW[f], "")
    bad += [(f, m) for m in re.findall(r"\d+\.\d{10,}", t)]
ok(not bad, f"no number with 10 or more fractional digits in {len(files)} built files; found {bad[:3]}")
for f, v in ALLOW.items(): ok(v in rd(f), f"allowance {v} is still present on {f}")

print(f"\n{len(FAIL)} failed" if FAIL else "\nall passed"); sys.exit(1 if FAIL else 0)
