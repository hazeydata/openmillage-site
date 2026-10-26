#!/usr/bin/env python3
"""C19: every history page's caption EDR link equals the EDR URL its own rows cite.
Run from the repo root after build.py and amend3.py: python3 tests/test_history_edr.py"""
import collections, glob, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)
import redo
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)
LINK = re.compile(r"<figcaption.*?</figcaption>", re.S)
EDR = re.compile(r"href='(https://edr\.state\.fl\.us[^']*)'>Florida Office")

hist = sorted(glob.glob("docs/fl/history/*-county/*/index.html"))
ok(len(hist) > 0, f"{len(hist)} history pages found")
checked, bad, seen = 0, [], {}
for p in hist:
    rows = json.load(open(os.path.join(os.path.dirname(p), "index.json")))["rows"]
    cnt = collections.Counter(r["source_url"] for r in rows if "edr.state.fl.us" in (r["source_url"] or ""))
    want = cnt.most_common(1)[0][0] if cnt else None
    caps = LINK.findall(open(p, encoding="utf-8").read())
    got = [u for c in caps for u in EDR.findall(c)]
    if not caps: continue  # no chart caption on this page
    checked += 1; seen[p] = (got, want, cnt.get(want, 0))
    if want is None:
        if got: bad.append((p, got, None))
    elif got != [want]: bad.append((p, got, want))
ok(checked >= 2, f"{checked} history pages with a caption checked")
ok(not bad, f"caption EDR link == URL the page's own EDR rows cite, on every page: {bad[:3]}")
# Pin current data so a constant URL can't pass by luck
a = "docs/fl/history/alachua-county/{}/index.html"
sd, co = seen.get(a.format("school")), seen.get(a.format("county"))
ok(sd and sd[1].endswith("/advaltxsd.xlsx") and sd[2] == 87 and sd[0] == [sd[1]], f"Alachua school caption = advaltxsd (87 rows): {sd}")
ok(co and co[1].endswith("/advaltxco.xlsx") and co[2] == 240 and co[0] == [co[1]], f"Alachua county caption = advaltxco (240 rows): {co}")
ok(sd and co and sd[0] != co[0], "school and county captions link different EDR workbooks")

# No EDR rows: no crash, no EDR link
ok(redo.page_edr_url([]) is None, "page_edr_url([]) is None (no crash)")
ok(redo.page_edr_url([{"source_url": "https://floridarevenue.com/x.pdf"}]) is None, "page_edr_url with only non-EDR rows is None")
cap = redo.history_caption(redo.page_edr_url([]))
ok("edr.state.fl.us" not in cap and "Economic &amp; Demographic" not in cap, "caption for a page with no EDR rows has no EDR link")
u = "https://edr.state.fl.us/Content/local-government/data/data-a-to-z/advaltxsd.xlsx"
ok(redo.page_edr_url([{"source_url": u}] * 2 + [{"source_url": u.replace("sd", "co")}]) == u, "page_edr_url picks the most-cited EDR URL")
print(f"{len(FAIL)} failures"); sys.exit(1 if FAIL else 0)
