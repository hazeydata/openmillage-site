#!/usr/bin/env python3
"""Tests for amend3.py (OM-FL-AMEND3-BASELINE-001, ACs 1-10). Run from the repo root after build.py:
    python3 tests/test_amend3.py
Uses a fixture ballot file (test-only values) so the page renders even while fact's file is pending."""
import csv, html, http.server, json, os, re, shutil, subprocess, sys, tempfile, threading, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)
import amend3 as A
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)
FIX = {"title": "FIXTURE MEASURE TITLE", "ballot_number": 3, "ballot_summary": "Fixture summary text; this measure will take effect in 2027.",
       "election_date": "2026-11-03", "source_url": "https://constitutionalinitiatives.dos.fl.gov/Home/InitDetail?account=10&seqnum=110",
       "fact_verified_by": None, "fact_verified_at": None}
tmp = tempfile.mkdtemp(); bj = os.path.join(tmp, "ballot.json"); json.dump(FIX, open(bj, "w"))
counties = [(r["name"].removesuffix(" County"), r["geoid"]) for r in csv.DictReader(open(A.CFG["counties_csv"]))]
rows = A.rows_from(A.CFG["rates_csv"]); dist = A.rows_from(A.CFG["districts_csv"]) if os.path.exists(A.CFG["districts_csv"]) else []
page, shown = A.render_amend3(rows, dist, A.load_ballot(bj), counties)

# R3: template never names the measure itself
ok(not re.search(r"amendment\s*3", open("amend3.py").read(), re.I), "template contains no literal 'Amendment 3'")
ok("Amendment 3" not in page, "rendered page contains no 'Amendment 3'")
# AC1 sourcing check passes, and a planted unsourced number fails
ok(A.check(page) == [], "AC1/5/6 checks pass on the rendered page: %s" % A.check(page)[:3])
ok(any("without source link" in e for e in A.check(page.replace("</footer>", "<p>Total 42 mills</p></footer>"))), "AC1 unsourced number is caught")
# AC2 fail closed
for bad, why in ((None, "missing file"), ({**FIX, "title": "Ballot Number: 3"}, "label as title"), ({k: v for k, v in FIX.items() if k != "title"}, "no title")):
    p = os.path.join(tmp, "bad.json")
    if bad is None: p = os.path.join(tmp, "nope.json")
    else: json.dump(bad, open(p, "w"))
    try: A.load_ballot(p); ok(False, f"AC2 fails closed on {why}")
    except A.BuildError: ok(True, f"AC2 fails closed on {why}")
ok("<h1>FIXTURE MEASURE TITLE</h1>" in page and ">Ballot Number 3</a>" in page and "Ballot Number 3</h1>" not in page, "heading = title, ballot number only as label")
ok("&ldquo;" + html.escape(FIX["ballot_summary"], quote=True) + "&rdquo;" in page, "AC2 summary rendered verbatim in quotes")
# AC3 table values equal CSV
cells = re.findall(r"<td class=rate data-body-id='([^']*)' data-levy='([^']*)'>([^ ]+) ([a-z]+) <a href='([^']+)'", page)
src = {(r["body_id"], html.escape(r["levy_component"] + "|" + r["levy_scope"], quote=True), r["county"]): r for r in shown}
mism = sum(1 for b, l, v, u, s in cells if not any(k[0] == b and k[1] == l and r["rate"] == v and r["unit"] == u and html.escape(r["source_url"], quote=True) == s for k, r in src.items()))
ok(len(cells) == len(shown) and mism == 0, f"AC3 {len(cells)} table values vs {len(shown)} CSV rows, {mism} mismatches")
# AC4 coverage computed, missing named
have = {r["county"] for r in rows}; n = sum(c in have for c, _ in counties); miss = [c for c, _ in counties if c not in have]
ok(f"Coverage: {n} of 67 counties" in page, f"AC4 coverage reads '{n} of 67 counties'")
ok(all(html.escape(c) in page.split("Not yet collected:")[1].split("</p>")[0] for c in miss) if miss else "Not yet collected" not in page, f"AC4 missing counties listed by name ({len(miss)})")
# AC5/6 lints
ok(any("forecast" in e for e in A.check(page.replace("</footer>", "<p>Rates are expected to change <a href='https://x'>s</a></p></footer>"))), "AC5 forecast word caught outside quote")
ok(not any("forecast" in e for e in A.check(page)), "AC5 forecast words inside the official quote are allowed")
ok(any("advocacy" in e for e in A.check(page.replace("</footer>", "<p>a tax hike</p></footer>"))), "AC6 advocacy word caught")
ok("may change" not in page.lower() and "EDR" not in page, "no 'may change' wording, no EDR")
# AC7 as-of = max retrieved_at in ET
import datetime; from zoneinfo import ZoneInfo
m = datetime.datetime.fromisoformat(max(r["retrieved_at"] for r in shown)).astimezone(ZoneInfo("America/New_York"))
ok(f"As of {m.strftime('%B')} {m.day}, {m.year}, {m.strftime('%H:%M')} ET" in page and "These are 2025 adopted rates." in page, "AC7 as-of date in ET + 2025 adopted statement")
# AC8 FAQ
ok(len(re.findall("<dt>", page)) <= 3 and "<q>" + html.escape(A.CFG["millage_definition"]["text"], quote=True) + "</q>" in page and "what will happen" not in page.lower(), "AC8 <=3 FAQ items, DOR definition verbatim")
# AC9 + AC10: full build twice, byte-identical, files match rows, local preview 200 and sitemap counts the URL
cfg = dict(A.CFG, ballot_json=bj); cj = os.path.join(tmp, "cfg.json"); json.dump(cfg, open(cj, "w"))
outs = []
for i in (1, 2):
    od = os.path.join(tmp, f"out{i}"); env = dict(os.environ, OUT=od, AMEND3_CONFIG=cj)
    shutil.copytree("docs", od) if os.path.isdir("docs") else os.makedirs(od)
    r = subprocess.run([sys.executable, "amend3.py"], env=env, capture_output=True, text=True); ok(r.returncode == 0, f"build {i} exit 0 {r.stderr[-200:]}")
    outs.append(open(os.path.join(od, A.SLUG, "index.html"), "rb").read())
ok(outs[0] == outs[1], "AC10 two builds byte-identical")
od = os.path.join(tmp, "out1"); api = os.path.join(od, "api/v1/fl/2025", A.SLUG.split("/")[-1] + "-baseline")
ok(len(list(csv.DictReader(open(api + ".csv")))) == len(shown) == len(json.load(open(api + ".json"))), "AC9 CSV/JSON hold exactly the rows shown")
ok(f"/{A.SLUG}/</loc>" in open(os.path.join(od, "sitemap.xml")).read() if os.path.exists(os.path.join(od, "sitemap.xml")) else False, "AC10 sitemap lists the URL")
h = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *a: http.server.SimpleHTTPRequestHandler(*a, directory=od))
threading.Thread(target=h.serve_forever, daemon=True).start()
code = urllib.request.urlopen(f"http://127.0.0.1:{h.server_port}/{A.SLUG}/").status; h.shutdown()
ok(code == 200, f"AC10 local preview returns {code}")
# real ballot file: must fail closed while title / ballot_number are absent
r = subprocess.run([sys.executable, "amend3.py"], env=dict(os.environ, OUT=os.path.join(tmp, "real")), capture_output=True, text=True)
print("INFO real build:", r.returncode, r.stdout.strip() or r.stderr.strip()[:200])
shutil.rmtree(tmp)
print("FAILURES", len(FAIL)); sys.exit(1 if FAIL else 0)
