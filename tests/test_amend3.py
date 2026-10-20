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
       "fact_verified_by": "fixture", "fact_verified_at": "2026-10-20T00:00-04:00"}
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
prose = html.unescape(re.sub(r"<[^>]+>", " ", page))  # page prose only: tags (and so row source-link hrefs) removed
ok("may change" not in prose.lower() and not re.search(r"\bEDR\b", prose) and "Economic & Demographic Research" not in prose and "Economic and Demographic Research" not in prose, "no 'may change' wording, no EDR (abbreviation or full name) in page prose")
ok("Each value on this page links to the official document it was read from." in page, "T1 FAQ sources answer names no agency")
nm = sum(r["body_type"] == "municipality" for r in rows)
ok(f"{nm} municipal" in page and nm == sum(r["body_type"] == "municipality" for r in csv.DictReader(open(A.CFG["rates_csv"]))), f"municipal row count computed from CSV ({nm})")
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
# multi-county rows (e.g. "Flagler/St. Johns") are shown but never counted as extra counties
multi = sorted({r["county"] for r in rows} - {c for c, _ in counties})
ok(len(counties) == 67 and n == 67 and "Coverage: 67 of 67 counties" in page and all("/" in m for m in multi), f"multi-county groups {multi} not counted; coverage 67 of 67")
ok(not re.search(r"\b54\s*(of|/)\s*66\b|of 66\b|/66\b", re.sub(r"<[^>]+>", " ", page)), "page never shows the TACD 54/66 figure")
# AC2 + AC11 with the real, fact-verified ballot file
real = json.load(open(A.CFG["ballot_json"]))
ok(all(v == "CONFIRMED" for v in real.get("verification_status", {}).values()) and real.get("verification_status"), "AC11 fact file: every field CONFIRMED")
rd = os.path.join(tmp, "real"); shutil.copytree("docs", rd)
r = subprocess.run([sys.executable, "amend3.py"], env=dict(os.environ, OUT=rd), capture_output=True, text=True)
ok(r.returncode == 0, f"real build exit 0: {(r.stdout + r.stderr).strip()[:300]}")
if r.returncode == 0:
    rp = open(os.path.join(rd, A.SLUG, "index.html")).read()
    ok(f"<h1>{html.escape(real['title'], quote=True)}</h1>" in rp and f">Ballot Number {real['ballot_number']}</a>" in rp, "AC2 real page: heading = verbatim title, ballot number as label")
    ok("&ldquo;" + html.escape(real["ballot_summary"], quote=True) + "&rdquo;" in rp, "AC2 real page: verbatim summary in quotes with link")
    ok(A.check(rp) == [] and "Coverage: 67 of 67 counties" in rp and "Amendment 3" not in rp, "real page passes AC1/5/6 checks, 67 of 67, no 'Amendment 3'")
# mutant killers (Test, 2026-10-20)
fcsv = os.path.join(tmp, "kinds.csv")
with open(A.CFG["rates_csv"]) as f: hdr_line = f.readline()
open(fcsv, "w").write(hdr_line + ",".join(["FL", "2025", "Testcounty", "X", "county", "x", "", "", "operating", "countywide", "aggregate_effective", "1.0", "mills", "a", "https://floridarevenue.com/x", "0", "2026-01-01T00:00:00+00:00"]) + "\n")
ok(A.rows_from(fcsv) == [], "M:32 rate_kind filter drops aggregate_effective rows")
ok(all(r["rate_kind"] == "adopted" for r in shown) and "aggregate_effective" not in page, "M:32 page shows adopted rows only")
det = "".join(re.findall(r"<details>.*?</details>", page, re.S))
ok(len(dist) > 0 and len(re.findall(r"<td class=rate", det)) == len(dist), f"M:54 all {len(dist)} special-district rows rendered inside collapsed <details>")
faq4 = page.replace("</dl>", "<dt>a</dt><dd>b</dd><dt>c</dt><dd>d</dd></dl>")
ok(any("FAQ" in e for e in A.check(faq4)), "M:93 a 4th FAQ item fails the check")
ok("<p>&ldquo;" + html.escape(FIX["title"], quote=True) + "&rdquo;</p>" in page, "M:61 title wrapped in opening and closing quote marks")
c66 = os.path.join(tmp, "c66.csv"); lines = open(A.CFG["counties_csv"]).read().splitlines(True); open(c66, "w").writelines(lines[:-1])
cj66 = os.path.join(tmp, "cfg66.json"); json.dump(dict(cfg, counties_csv=c66), open(cj66, "w"))
r = subprocess.run([sys.executable, "amend3.py"], env=dict(os.environ, OUT=os.path.join(tmp, "o66"), AMEND3_CONFIG=cj66), capture_output=True, text=True)
ok(r.returncode == 1 and "expected 67" in r.stderr, "M:104 a 66-county list fails the build")
p2, _ = A.render_amend3(rows, dist, A.load_ballot(bj), counties + [("Testland", "0"), ("Otherland", "1")])
ok("<p>Not yet collected: Testland, Otherland.</p>" in p2, "M:66 'Not yet collected' line names every missing county")
ok("Coverage: 67 of 69 counties" in p2, "M:66 coverage count still computed with missing counties")
nb = os.path.join(tmp, "nb.json"); json.dump({k: v for k, v in FIX.items() if k != "ballot_number"}, open(nb, "w"))
try: A.load_ballot(nb); ok(False, "M:22 ballot_number required")
except A.BuildError: ok(True, "M:22 ballot_number required")
for v, why in ((None, "null"), ("<absent>", "missing")):
    fb = {k: x for k, x in FIX.items() if not (k == "fact_verified_by" and v == "<absent>")}
    if v is None: fb["fact_verified_by"] = None
    pb = os.path.join(tmp, "fb.json"); json.dump(fb, open(pb, "w"))
    try: A.load_ballot(pb); ok(False, f"T2 fact_verified_by {why} fails closed")
    except A.BuildError: ok(True, f"T2 fact_verified_by {why} fails closed")
# special-district fact gate (fact file keyed county|body_id|levy_component)
try: A.fact_gate(dist, A.CFG["district_fact_csv"]); ok(True, f"fact gate passes: all {len(dist)} district rows MATCH fact, each with its own https source link")
except A.BuildError as e: ok(False, f"fact gate passes: {e}")
import copy
d2 = copy.deepcopy(dist); d2[0]["rate"] = str(float(d2[0]["rate"]) + 1)
try: A.fact_gate(d2, A.CFG["district_fact_csv"]); ok(False, "fact gate fails on a rate differing from fact")
except A.BuildError: ok(True, "fact gate fails on a rate differing from fact")
d3 = copy.deepcopy(dist); d3[0]["county"] = "Nowhere"
try: A.fact_gate(d3, A.CFG["district_fact_csv"]); ok(False, "fact gate fails on a row missing from fact")
except A.BuildError: ok(True, "fact gate fails on a row missing from fact")
d4 = copy.deepcopy(dist); d4[0]["source_url"] = ""
try: A.fact_gate(d4, A.CFG["district_fact_csv"]); ok(False, "fact gate fails on a district row without a source link")
except A.BuildError: ok(True, "fact gate fails on a district row without a source link")
d6 = copy.deepcopy(dist); d6[0]["source_url"] = "http://" + d6[0]["source_url"].split("://", 1)[1]
try: A.fact_gate(d6, A.CFG["district_fact_csv"]); ok(False, "fact gate fails on an http:// (not https) source link")
except A.BuildError as e: ok("no source link" in str(e), "fact gate fails on an http:// (not https) source link")
def fact_file(fr, name):
    fp = os.path.join(tmp, name)
    with open(fp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fr[0].keys()), lineterminator="\n"); w.writeheader(); w.writerows(fr)
    return fp
frows0 = list(csv.DictReader(open(A.CFG["district_fact_csv"], newline="")))
fm = copy.deepcopy(frows0); fm[0]["match"] = "false"; fpm = fact_file(fm, "fact_matchfalse.csv")
try: A.fact_gate(dist, fpm); ok(False, "fact gate fails on fact match=false")
except A.BuildError as e: ok("match='false'" in str(e), "fact gate fails on fact match=false")
try: A.fact_gate(dist + [copy.deepcopy(dist[0])], A.CFG["district_fact_csv"]); ok(False, "fact gate fails on a duplicate data row")
except A.BuildError as e: ok("duplicate data row" in str(e), "fact gate fails on a duplicate data row")
try: A.fact_gate(dist, fact_file(frows0 + [copy.deepcopy(frows0[0])], "fact_dup.csv")); ok(False, "fact gate fails on a duplicate fact row")
except A.BuildError as e: ok("duplicate fact row" in str(e), "fact gate fails on a duplicate fact row")
d7 = copy.deepcopy(dist); i7 = next(i for i, r in enumerate(d7) if r["county"] == "Alachua"); d7[i7]["county"] = "ALACHUA"
try: A.fact_gate(d7, A.CFG["district_fact_csv"]); ok(False, "fact gate fails on a mis-cased county (ALACHUA), exact key match")
except A.BuildError as e: ok("not an exact match" in str(e), "fact gate fails on a mis-cased county (ALACHUA), exact key match")
cjm = os.path.join(tmp, "cfg_matchfalse.json"); json.dump(dict(cfg, district_fact_csv=fpm), open(cjm, "w"))
r = subprocess.run([sys.executable, "amend3.py"], env=dict(os.environ, OUT=os.path.join(tmp, "omf"), AMEND3_CONFIG=cjm), capture_output=True, text=True)
ok(r.returncode == 1 and "fact gate" in r.stderr and not os.path.exists(os.path.join(tmp, "omf", A.SLUG, "index.html")), "main() runs the fact gate: a match=false fact row fails the real build")
try: A.fact_gate(dist, os.path.join(tmp, "none.csv")); ok(False, "fact gate fails closed without the fact file")
except A.BuildError: ok(True, "fact gate fails closed without the fact file")
# tacd_source_url blank / sha256 mismatch fail the build
fpath = A.CFG["district_fact_csv"]; frows = list(csv.DictReader(open(fpath, newline="")))
for mut, why in (("blank", "tacd_source_url blank"), ("sha", "sha256 mismatch")):
    fr = copy.deepcopy(frows)
    if mut == "blank": fr[0]["tacd_source_url"] = ""
    d5 = copy.deepcopy(dist)
    if mut == "sha": d5[0]["sha256"] = "0" * 64
    fp = os.path.join(tmp, f"fact_{mut}.csv")
    with open(fp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(frows[0].keys()), lineterminator="\n"); w.writeheader(); w.writerows(fr)
    try: A.fact_gate(d5, fp); ok(False, f"fact gate fails on {why}")
    except A.BuildError as e: ok(why.split()[0] in str(e), f"fact gate fails on {why}")
ok(all(f["tacd_source_url"].startswith("https://floridarevenue.com/") for f in frows) and len(frows) == len(dist), f"fact file: tacd_source_url set on all {len(frows)} rows")
# footnotes verbatim from fact's file, with DOR citations
fn = A.footnotes(A.CFG["footnotes_md"])
for c, fc in A.CFG["footnote_citations"].items():
    seg = page.split(f"<h3>{html.escape(c)}</h3>")[1].split("</section>")[0]
    ok(f"&ldquo;{html.escape(fn[fc['n']], quote=True)}&rdquo;" in seg and all(html.escape(A.SRC[f]["url"], quote=True) in seg for f, _ in fc["cites"]), f"footnote {fc['n']} ({c}) verbatim with DOR citation(s)")
ok("Other counties' TACDs print it in three parts" in fn[3], "Broward footnote says the split comes from other counties")
# Broward sum: computed from data, not typed
from decimal import Decimal as Dd
bro = [r for r in dist if r["county"] == "Broward" and r["body_id"] == "fl-sfwmd-special_district"]
parts = {}
for cty in ("Palm Beach", "St. Lucie"):
    parts[cty] = {r["levy_component"]: Dd(r["rate"]) for r in dist if r["county"] == cty and r["body_id"] == "fl-sfwmd-special_district"}
ok(len(bro) == 1 and all(sum(p.values()) == Dd(bro[0]["rate"]) and len(p) == 3 for p in parts.values()), f"Broward SFWMD {bro[0]['rate'] if bro else '?'} = sum of the three parts in Palm Beach and St. Lucie ({[str(sum(p.values())) for p in parts.values()]})")
nums = re.findall(r"\d+\.\d+", fn[3]); comps = parts["Palm Beach"]
ok(Dd(nums[0]) == Dd(bro[0]["rate"]) and [Dd(x) for x in nums[1:4]] == [comps["operating"], comps["okeechobee_basin"], comps["everglades_construction"]] and Dd(nums[4]) == sum(Dd(x) for x in nums[1:4]), "Broward footnote numbers equal the data and add up")
# AC4b special-district coverage, computed, missing named
sdc = [c for c, _ in counties if any(r["county"] == c for r in dist)]; sdm = [c for c, _ in counties if c not in sdc]
line = re.search(r"<p>Special districts: .*?</p>", page).group(0)
ok(f"Special districts: {len(sdc)} of 67 counties" in line and all(html.escape(c) in line for c in sdm), f"AC4b special districts {len(sdc)} of 67, {len(sdm)} missing named")
ok(len(sdc) == len({r["county"] for r in dist} & {c for c, _ in counties}), f"AC4b count equals counties with special-district rows ({len(sdc)})")
ok(html.escape(A.CFG["tacd_index"]["url"], quote=True) in line, "AC4b count links the DOR TACD index")
tl = dict(re.findall(r"([A-Z][A-Za-z.\- ]+?) \(<a href='([^']+)'>TACD</a>\)", line))
ok(sorted(tl) == sorted(sdc) and all(html.unescape(tl[c]) in {r["source_url"] for r in dist if r["county"] == c} for c in sdc), f"AC4b each of the {len(sdc)} counties links its own TACD file")
# 43/67 links come from the TACD source list
ok(all(html.unescape(u) == A.SRC_BY_COUNTY[c] for c, u in tl.items()), "AC4b county links come from the TACD source list")
shutil.rmtree(tmp)
print("FAILURES", len(FAIL)); sys.exit(1 if FAIL else 0)
