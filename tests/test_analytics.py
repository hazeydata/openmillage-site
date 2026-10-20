#!/usr/bin/env python3
"""OM-SITE-ANALYTICS-001: every .html page under docs/ must carry the cookieless GoatCounter tag inside <head>,
outside any HTML comment. Run from the repo root after build.py and amend3.py:  python3 tests/test_analytics.py"""
import glob, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)
from analytics import GOATCOUNTER_TAG
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)
# pinned literals, independent of the constant
SITE = "https://openmillage.goatcounter.com/count"; JS = "https://gc.zgo.at/count.js"
ok(f"data-goatcounter='{SITE}'" in GOATCOUNTER_TAG and f"src='{JS}'" in GOATCOUNTER_TAG, "constant carries the pinned site code and count.js")
TAG_RE = re.compile(r"<script\b[^>]*\bdata-goatcounter=(['\"])" + re.escape(SITE) + r"\1[^>]*\bsrc=(['\"])" + re.escape(JS) + r"\2[^>]*>\s*</script>")
pages = sorted(glob.glob("docs/**/*.html", recursive=True))
walked = sorted(os.path.join(d, f) for d, _, fs in os.walk("docs") for f in fs if f.endswith(".html"))
ok(pages == walked, f"glob finds every .html page a recursive walk finds ({len(walked)})")
locs = re.findall(r"<loc>([^<]+)</loc>", open("docs/sitemap.xml", encoding="utf-8").read())
ok(len(locs) > 0 and len(pages) == len(locs), f"page count {len(pages)} equals sitemap URL count {len(locs)}")
bad = []
for p in walked:
    t = re.sub(r"<!--.*?-->", "", open(p, encoding="utf-8").read(), flags=re.S)
    m = re.search(r"<head\b[^>]*>(.*?)</head>", t, re.S | re.I)
    if not m or not TAG_RE.search(m.group(1)): bad.append(p)
ok(not bad, f"all {len(walked)} pages carry the pinned tag inside <head>, outside comments" + (f"; bad: {bad}" if bad else ""))
ok("docs/fl/amendment-3/index.html" in walked and "docs/fl/amendment-3/index.html" not in bad, "amendment-3 page carries the tag")
ok(re.search(r"run:\s*python3 tests/test_analytics\.py", open(".github/workflows/build.yml").read()) is not None, "build.yml runs test_analytics.py")
print("FAILURES", len(FAIL)); sys.exit(1 if FAIL else 0)
