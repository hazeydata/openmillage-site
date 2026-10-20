#!/usr/bin/env python3
"""OM-SITE-ANALYTICS-001: every .html page under docs/ must carry the shared cookieless GoatCounter tag.
Run from the repo root after build.py and amend3.py:  python3 tests/test_analytics.py"""
import glob, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)
from analytics import GOATCOUNTER_TAG
pages = sorted(glob.glob("docs/**/*.html", recursive=True))
missing = [p for p in pages if GOATCOUNTER_TAG not in open(p, encoding="utf-8").read()]
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)
ok(len(pages) > 0, f"docs/ has {len(pages)} .html pages")
ok(not missing, f"all {len(pages)} pages carry the GoatCounter tag" + (f"; missing: {missing}" if missing else ""))
ok(os.path.exists("docs/fl/amendment-3/index.html") and "docs/fl/amendment-3/index.html" not in missing, "amendment-3 page carries the GoatCounter tag")
print("FAILURES", len(FAIL)); sys.exit(1 if FAIL else 0)
