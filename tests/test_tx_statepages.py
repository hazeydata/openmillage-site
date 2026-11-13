#!/usr/bin/env python3
"""OM-SITE-TX-001: Texas hub + 254 county pages (statepages.py tx_*). Each check names the AC it covers.
Run from the repo root after build.py, amend3.py and statepages.py:  python3 tests/test_tx_statepages.py"""
import csv, glob, hashlib, html, html.parser, json, os, re, shutil, subprocess, sys, tempfile
from decimal import Decimal
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)
from analytics import GOATCOUNTER_TAG
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)
rd = lambda p: open(p, encoding="utf-8").read()
YEARS = [2021, 2022, 2023, 2024, 2025]
PIN = "5ceed4f493b7b4283606da18c089f44cde2321bf"
FACTS = {  # spec Facts table: file name under data/tx/ -> sha256 (OM-DATA-REPIN-001: 9 files re-hashed after float-noise removal)
    "tx-2021.csv": "9c560a6b12bc52d9f1d28c69e6c31aa6d153f30358f6dac4092ebf6f8dee63ac", "tx-2021.provenance.csv": "c9f3f0593d7e7c3b0de0c707fa24850e249fc498fcb7ca494855dfd0329c4428",
    "tx-2022.csv": "bc1d8a65cdff9b6b2f418cab9de2935042ad18e6a827a9cd843481683e1a067b", "tx-2022.provenance.csv": "1a47de8458c36957d75156ca0a2da8bf8aadde43eca276c058e2a1ff5b3423b3",
    "tx-2023.csv": "bffd88e29a6b761335bea9dac34e18688638d9fd4fd60ba34dd88970892387f1", "tx-2023.provenance.csv": "f3fd7d40a3c35b3347bb476bb87d275e1f339f6df69ead04b2abf0c685260e64",
    "tx-2024.csv": "add388dcbd0f00db8d680b0601eedc598d2157c9f519ed0df4470d76075d0c76", "tx-2024.provenance.csv": "a7ceca0798d182c10e664df32655adfc5d9fcf79bb134fdd0a1887cf13d86151",
    "tx-2025.csv": "c2c2f3a75017f2ca229cb1f2827f7eb10f0a72774a1d7bcfad62e415e3ccc5eb", "tx-2025.provenance.csv": "3ebb2ae494deb03903b8de86638e19181461ef94f34f36a1390010d948a91352",
    "tx_unit_basis.csv": "29a39389919c8dd6ec348915acd39db7ab78303f9eee49c38685c72f215b8316"}

class Tbl(html.parser.HTMLParser):
    """{table id: [[(text, href, title), ...] per row]}, header row included."""
    def __init__(self):
        super().__init__(convert_charrefs=True); self.t, self.cur, self.in_cell, self.id = {}, None, False, None; self.txt = self.href = self.ttl = self.atl = None
    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag == "table": self.id = a.get("id"); self.t[self.id] = []
        elif tag == "tr": self.cur = []
        elif tag in ("td", "th"): self.in_cell, self.txt, self.href, self.ttl, self.atl = True, "", None, a.get("title"), None
        elif tag == "a" and self.in_cell: self.href, self.atl = a.get("href"), a.get("title")
    def handle_data(self, d):
        if self.in_cell: self.txt += d
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.in_cell: self.cur.append((self.txt.strip(), self.href, self.atl or self.ttl)); self.in_cell = False
        elif tag == "tr" and self.cur is not None: self.t[self.id].append(self.cur); self.cur = None
def tables(path):
    p = Tbl(); p.feed(rd(path)); return p.t
def csvrows(p): return list(csv.DictReader(open(p, newline="", encoding="utf-8")))
slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

# ---------------- pinned data, read independently of the builder ----------------
D = {y: csvrows(f"data/tx/tx-{y}.csv") for y in YEARS}
def tot(y, bt): return [r for r in D[y] if r["body_type"] == bt and r["levy_component"] == "total"]
CT = {y: {r["body_id"]: r for r in tot(y, "county")} for y in YEARS}
MU = {y: {r["body_id"]: r for r in tot(y, "municipal")} for y in YEARS}
COUNTIES = sorted({r["county"] for r in tot(2025, "county")})
CID = {r["county"]: b for b, r in CT[2025].items()}
hub_p = "docs/tx/property-tax-rates/index.html"
county_pages = sorted(glob.glob("docs/tx/*-county/index.html"))
alltx = sorted(glob.glob("docs/tx/**/*.html", recursive=True))
TXT = {p: rd(p) for p in alltx}
def prose(p):
    t = re.sub(r"<script.*?</script>|<head>.*?</head>", " ", TXT[p], flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", " ", t))
def RT(s):
    if len(Decimal(s).as_tuple().digits) <= 15: return s
    return format(Decimal(f"{float(s):.15g}"), "f")

def expect(r):
    """What a rate cell must show and link to for CSV row r (None = body absent that year)."""
    return ("not listed", None) if r is None else ("not reported", None) if r["rate"] == "" else (RT(r["rate"]), r["source_url"])

# ---------------- T1 pin and fail-closed ----------------
lock = {f["path"]: f for f in json.load(open("data/SOURCES.lock"))["files"]}
ok(len([p for p in lock if p.startswith("data/tx/")]) == 11 and all(
    lock.get("data/tx/" + n, {}).get("sha256") == h and lock["data/tx/" + n]["commit"] == PIN and lock["data/tx/" + n]["repo"] == "hazeydata/openmillage"
    and lock["data/tx/" + n]["source_path"] == (("reference/" if n == "tx_unit_basis.csv" else "data/") + n) for n, h in FACTS.items()),
   "AC1 lock lists all 11 TX files with repo, pin commit, product source_path and the spec Facts sha256")
ok(all(hashlib.sha256(open("data/tx/" + n, "rb").read()).hexdigest() == h for n, h in FACTS.items()), "AC1 on-disk data/tx/* bytes match the Facts-table sha256")

made = []
def sandbox(mutate=None):
    """Builder inputs plus the already-built docs/ with every TX artefact stripped, so only the TX inputs decide whether statepages succeeds."""
    t = tempfile.mkdtemp(prefix="tx-test-"); made.append(t)
    for n in ("sources.py", "statepages.py", "analytics.py", "site_chrome.py", "redo.py", "amend3_config.json"): shutil.copy(n, t)
    for n in ("assets", "content", "data"): shutil.copytree(n, os.path.join(t, n))
    shutil.copytree("docs", os.path.join(t, "docs"), ignore=lambda d, names: ["tx"] if os.path.basename(d) == "docs" else [n for n in names if n.startswith("tx-")] if d.endswith("charts") else [])
    sm = os.path.join(t, "docs/sitemap.xml"); open(sm, "w").write(re.sub(r"<url><loc>[^<]*/tx/[^<]*</loc>(<lastmod>[^<]*</lastmod>)?</url>", "", rd(sm)))
    lt = os.path.join(t, "docs/llms.txt"); open(lt, "w").write("".join(l for l in open(lt, encoding="utf-8").readlines(True) if not l.startswith("- Texas county and city")))
    mutate and mutate(t)
    return t
def run_sp(t, seed="0"):
    return subprocess.run([sys.executable, "statepages.py"], cwd=t, env=dict(os.environ, PYTHONHASHSEED=seed, DATA_GLOB="data/*.csv"), capture_output=True, text=True)
def flip(t):
    p = os.path.join(t, "data/tx/tx-2025.csv"); b = bytearray(open(p, "rb").read()); b[len(b) // 2] ^= 1; open(p, "wb").write(bytes(b))
def edit_lock(fn):
    def m(t):
        p = os.path.join(t, "data/SOURCES.lock"); l = json.load(open(p)); fn(l); json.dump(l, open(p, "w"), indent=1)
    return m
def nocommit(l): [f.pop("commit") for f in l["files"] if f["path"] == "data/tx/tx_unit_basis.csv"]
def nofile(l): l["files"] = [f for f in l["files"] if f["path"] != "data/tx/tx-2022.csv"]
for name, fn, want in (("AC1 one flipped byte in a pinned CSV", flip, "sha256 mismatch"), ("AC3 TX pin missing from the lock", edit_lock(nofile), "Texas pins missing"),
                       ("AC1 incomplete lock entry (no commit)", edit_lock(nocommit), "incomplete")):
    t = sandbox(fn); r = run_sp(t)
    ok(r.returncode != 0 and want in r.stderr and not os.path.exists(f"{t}/docs/tx") and not os.path.exists(f"{t}/docs/charts/tx-yoy-counts.json"),
       f"{name}: builder exits non-zero ({r.returncode}), reports '{want}', writes nothing under docs/tx/ (or TX charts)")
t = sandbox(lambda t: os.remove(os.path.join(t, "data/tx/tx-2023.provenance.csv"))); r = run_sp(t)
ok(r.returncode != 0 and not os.path.exists(f"{t}/docs/tx"), "AC3 a pinned file deleted from disk: non-zero exit, nothing under docs/tx/")
t = sandbox(); r = run_sp(t)
ok(r.returncode == 0 and os.path.exists(f"{t}/docs/tx/property-tax-rates/index.html"), "AC1 control: untouched pins build in the same sandbox")
# AC2: trace every data/ path the builder opens; each TX file read must be a lock entry
t = sandbox()
open(f"{t}/trace_run.py", "w").write("import builtins, json, runpy, sys\nseen = set(); o = builtins.open\n"
    "def op(f, *a, **k):\n    isinstance(f, str) and f.startswith('data/') and seen.add(f)\n    return o(f, *a, **k)\n"
    "builtins.open = op; sys.argv = ['statepages.py']; code = 0\n"
    "try: runpy.run_path('statepages.py', run_name='__main__')\nexcept SystemExit as e: code = e.code\n"
    "o('seen.json', 'w').write(json.dumps(sorted(seen))); sys.exit(code)\n")
r = subprocess.run([sys.executable, "trace_run.py"], cwd=t, capture_output=True, text=True)
seen = [p for p in json.load(open(f"{t}/seen.json")) if p.startswith("data/tx/")]
ok(r.returncode == 0 and len(seen) == 11 and all(p in lock for p in seen), f"AC2 the builder opened only lock-listed files under data/tx/ ({len(seen)} of 11 read; none outside the lock)")

# ---------------- T2 verbatim rates / goldens ----------------
anderson = tables("docs/tx/anderson-county/index.html")["t-county"][1]
ok(anderson[1][0] == "0.610535" and anderson[5][0] == "0.493907", "AC5 Anderson County total 2021=0.610535, 2025=0.493907 in the HTML table")
ok(all(anderson[1 + i][1] == CT[y]["tx-001-000-00"]["source_url"] for i, y in enumerate(YEARS)), "AC5 each Anderson cell links to its row's source_url")
andrews = tables("docs/tx/andrews-county/index.html")["t-county"][1]
ok(andrews[5][0] == "0.3598" and andrews[5][1] == CT[2025]["tx-002-000-00"]["source_url"], "AC5 Andrews County total 2025=0.3598 linked to its source_url")
ttl = anderson[5][2]
rown = next(i for i, r in enumerate(D[2025], start=2) if r["body_id"] == "tx-001-000-00" and r["levy_component"] == "total")
ok(anderson[0][0] == "Anderson County" and f"data/tx/tx-2025.csv row {rown};" in ttl and "sheet 'Detail' cell V4" in ttl, "AC4/5 county label is the CSV county field; hover names the site data file, CSV row, provenance sheet and cell")
hub = tables(hub_p)["t-tx"]
bad = [(row[0][0], y) for row in hub[1:] for y, cell in zip(YEARS, row[1:6]) if (cell[0], cell[1]) != expect(CT[y].get(CID[row[0][0]]))]
ok(len(hub) == 255 and not bad, f"AC4 every hub rate cell equals the CSV rate string byte-for-byte (or its missing label) and links to the row's source_url; bad {bad[:3]}")
bad = []
for c in COUNTIES:
    for row in tables(f"docs/tx/{slug(c)}/index.html").get("t-muni", [[]])[1:]:
        bid = next(b for y in YEARS[::-1] for b, r in MU[y].items() if r["county"] == c and r["taxing_body"] == row[0][0])
        bad += [(c, row[0][0], y) for y, cell in zip(YEARS, row[1:6]) if (cell[0], cell[1]) != expect(MU[y].get(bid))]
ok(not bad, f"AC4/9 every municipal cell on every county page equals the CSV rate (or not reported / not listed) with its source_url link; bad {bad[:3]}")
allowed = {RT(r["rate"]) for y in YEARS for bt in ("county", "municipal") for r in tot(y, bt) if r["rate"]}
series = json.load(open("docs/charts/tx-yoy-series.json")); counts_j = json.load(open("docs/charts/tx-yoy-counts.json"))
jrates = {x[k] for part in ("rose_or_held", "fell", "all_compared") for x in series[part] for k in ("rate_2021", "rate_2025")}
ok(jrates and jrates <= allowed, f"AC6 all {len(jrates)} chart JSON rate strings are in-scope CSV rates")
changes = {"0.5000"}  # the unit example in the callout
for bid, b in list(CT[2025].items()) + list(MU[2025].items()):
    a = (CT if bid in CT[2025] else MU)[2021].get(bid)
    if a and a["rate"] and b["rate"]: changes.add(str(abs(Decimal(RT(b["rate"])) - Decimal(RT(a["rate"])))))
decs = {d for p in alltx for d in re.findall(r"(?<![\w./-])0\.\d{3,}(?![\w./-])", prose(p))}
ok(not (decs - allowed - changes), f"AC6 every decimal in the text of all TX pages is a CSV rate, a Decimal change of two CSV rates, or the unit example; stray {sorted(decs - allowed - changes)[:5]}")
llms, sm = rd("docs/llms.txt"), rd("docs/sitemap.xml")
llms_tx = next(l for l in llms.split("\n") if l.startswith("- Texas county and city"))
ok(not re.search(r"\b\d\.\d{3,}\b", llms_tx + re.sub(r"<lastmod>.*?</lastmod>", "", sm)), "AC6 the llms.txt Texas line and the sitemap carry no rate numbers")

# ---------------- T3 null / missing ----------------
cul = tables("docs/tx/culberson-county/index.html")["t-county"][1]
ok(cul[5][0] == "not reported" and cul[5][1] is None and cul[1][0] == "0.162707" and cul[6][0] == "n/a" and "0" not in cul[5][0], "AC7 Culberson County 2025 total shows 'not reported' (no link, no 0), 2021 = 0.162707, Change = n/a")
ok("<strong>not reported</strong> in the pinned Comptroller file (2021 was 0.162707)" in TXT["docs/tx/culberson-county/index.html"], "AC7 Culberson lead uses the not-reported variant")
ok(sum(1 for y in YEARS for r in tot(y, "county") if r["rate"] == "") == 1 and CT[2025]["tx-055-000-00"]["rate"] == "", "AC7 at this pin the only empty county total is Culberson 2025 (no zero is ever substituted)")
new25 = sorted(set(MU[2025]) - set(MU[2021]))
checked = 0
for bid in new25:
    r = MU[2025][bid]; row = next(x for x in tables(f"docs/tx/{slug(r['county'])}/index.html")["t-muni"][1:] if x[0][0] == r["taxing_body"])
    checked += row[1][0] == "not listed" and row[1][1] is None and row[6][0] == "n/a" and row[5][0] == (RT(r["rate"]) if r["rate"] else "not reported")
ok(new25 and checked == len(new25), f"AC8 {len(new25)} municipal bodies in 2025 but absent in 2021 show 'not listed' in 2021 and Change n/a, never a borrowed value")
zero = [(p, c) for p in alltx for tid, rs in tables(p).items() if tid in ("t-tx", "t-county", "t-muni") for row in rs[1:] for c in row[1:6] if re.fullmatch(r"0(\.0+)?", c[0])]
csv_zero = {r["rate"] for y in YEARS for bt in ("county", "municipal") for r in tot(y, bt)} & {"0", "0.0"}
ok(all(c[0] in csv_zero for _, c in zero), f"AC9 a rate cell reads 0 / 0.0 only when a CSV total row has that literal rate ({len(zero)} such cells, CSV literals {sorted(csv_zero)})")

# ---------------- T4 scope ----------------
ok(len(hub) - 1 == 254 and len(county_pages) == 254, "AC10 hub table has 254 county rows; 254 county pages exist")
ok({p.split("/")[2] for p in county_pages} == {slug(c) for c in COUNTIES} and "docs/tx/anderson-county/index.html" in county_pages and all(r[0][1] == f"/tx/{slug(r[0][0])}/" for r in hub[1:]),
   "AC10 county pages sit at /tx/<slug(CSV county)>/ (e.g. /tx/anderson-county/) and the hub links to them")
ok(not any(re.search(r"school_district|special_district|Capital Creek", t) for t in TXT.values()), "AC11 no TX page mentions school_district, special_district or Capital Creek")
names = {n for p in alltx for tid, rs in tables(p).items() if tid in ("t-tx", "t-county", "t-muni") for row in rs[1:] for n in [row[0][0]]}
okn = set(COUNTIES) | {r["taxing_body"] for y in YEARS for r in tot(y, "municipal")}
ok(names <= okn, f"AC11 every body named in a TX table is a county or municipal total body; extras {sorted(names - okn)[:3]}")
def munis(c):
    name = {}
    for y in YEARS:
        for r in MU[y].values():
            if r["county"] == c: name[r["body_id"]] = r["taxing_body"]
    return [n for n, b in sorted((n, b) for b, n in name.items())]
bad = [c for c in COUNTIES if [r[0][0] for r in tables(f"docs/tx/{slug(c)}/index.html").get("t-muni", [[]])[1:]] != munis(c)]
ok(not bad and sum(len(munis(c)) for c in COUNTIES) >= 1090, f"AC12 each county page lists exactly its home-county municipal totals sorted by (taxing_body, body_id); failing {bad[:3]}")
am = tables("docs/tx/anderson-county/index.html")["t-muni"]
ok([r[0][0] for r in am[1:]] == ["Elkhart", "Frankston", "Palestine"] and [r[5][0] for r in am[1:]] == ["0.221748", "0.354502", "0.614285"], "AC12 Anderson County lists exactly Elkhart, Frankston, Palestine (2025: 0.221748, 0.354502, 0.614285)")
cols = {tuple(c[0] for c in rs[0]) for p in alltx for rs in tables(p).values()}
ok(cols == {("Taxing body", "2021", "2022", "2023", "2024", "2025", "Change 2021 to 2025")}, "AC13 every TX table has only total-rate year columns plus Change")
ok(not re.search(r"fmfc|\bgf_|\brb_|M&amp;O|I&amp;S|\bmo\b|\bis\b rate", "".join(prose(p) for p in alltx)), "AC13 no fund-component (M&O / I&S / GF / R&B / FMFC) labels in TX page text")

# ---------------- T5 unit / preliminary ----------------
ub = csvrows("data/tx/tx_unit_basis.csv")
ok(all("Every rate here is dollars per $100 of taxable value" in t and "<code>statutory_per_100</code>" in t and "§26.04(c)" in t and "§26.062(d)(1)" in t and "§26.07" in t for t in TXT.values()),
   f"AC14 all {len(alltx)} TX pages carry the unit callout (dollars per $100, statutory_per_100, §26.04(c), §26.062(d)(1), §26.07)")
ok({b["locator"] for b in ub} >= {"Tex. Tax Code §26.04(c)(1)-(2)", "Tex. Tax Code §26.062(d)(1)", "Tex. Tax Code §26.07"} and {b["basis"] for b in ub} == {"statutory_per_100"}
   and not re.search(r"<sup>i</sup>|inferred", "".join(TXT.values())), "AC14 callout citations are locators in the pinned tx_unit_basis.csv; the only basis value is statutory_per_100; no inferred marks")
ok(all("<p class=\"banner prelim\"><strong>2025 is preliminary</strong> (Texas Comptroller Working version). A Working or Final label on the source does not clear this flag.</p>" in t for t in TXT.values()),
   "AC15 preliminary banner on every TX page, stating a Working or Final label does not clear it")
fin = [p for p in alltx if re.search(r"\bfinal\b", TXT[p].replace("A Working or Final label on the source does not clear this flag.", ""), re.I)]
ok(not fin and not any(re.search(r"final", rd(f), re.I) for f in glob.glob("docs/charts/tx-*.json")), f"AC16 no TX page or chart JSON calls a rate final (only the banner's 'Working or Final label' clause); {fin[:2]}")
ok(all("School districts and special districts: in the data, not on these pages yet." in t for t in TXT.values()) and not any("not collected" in prose(p).lower() for p in alltx) and "not collected" not in llms_tx,
   "AC11/S1 coverage note says 'in the data, not on these pages yet' on every page; never 'not collected'")

# ---------------- T6 YoY ----------------
moves = [(Decimal(RT(b["rate"])) - Decimal(RT(CT[2021][bid]["rate"])), b["county"], bid) for bid, b in CT[2025].items() if b["rate"] and CT[2021][bid]["rate"]]
up, dn, same = (sum(m[0] > 0 for m in moves), sum(m[0] < 0 for m in moves), sum(m[0] == 0 for m in moves))
ok((up, dn, same, 254 - len(moves)) == (48, 194, 11, 1), f"AC17 recomputed from the pinned CSVs: rose/fell/unchanged/excluded = {(up, dn, same, 254 - len(moves))}, spec 48/194/11/1")
hubh = TXT[hub_p]
lead = re.search(r"<p class=lead>(.*?)</p>", hubh).group(1)
ok(f"{dn} of Texas’s 254 counties lowered" in lead and f", {up} raised it and {same} kept it the same." in lead and "One county has no reported 2025 total rate, so it is left out of that count." in lead, "AC17 hub lead integers equal the recomputed counts and mention the one excluded county")
ok(f"<strong>In numbers:</strong> {up} counties raised their rate and {same} kept it the same." in hubh and f"<strong>In numbers:</strong> {dn} counties lowered their rate." in hubh, "AC17 hub keynums equal the recomputed counts")
ok("Jeff Davis County (+58.7 cents), Willacy County (+56.3 cents) and Baylor County (+38.0 cents)" in hubh and "Cochran County (−26.1 cents), Bee County (−25.2 cents) and Hopkins County (−24.8 cents)" in hubh, "AC17 biggest movers (NC cents(), one decimal) match the recomputed pin")
ok("253 of 254 counties compared; Culberson County excluded because its 2025 total rate is not reported. 194 fell, 48 rose, 11 unchanged." in hubh, "AC17 chart source note: 253 of 254 compared, Culberson named")
ok((counts_j["rose"], counts_j["fell"], counts_j["unchanged"], counts_j["compared"], counts_j["excluded_null_pairs"]) == (up, dn, same, len(moves), 1), "AC17/18 chart counts JSON equals the recomputed counts")
rh = {x["body_id"]: x for x in series["rose_or_held"]}; fl = {x["body_id"]: x for x in series["fell"]}
ok(set(rh) == {b for d, c, b in moves if d >= 0} and set(fl) == {b for d, c, b in moves if d < 0} and (len(rh), len(fl)) == (59, 194), "AC18 chart series hold exactly the 59 rose/held and 194 fell counties of the filter (Culberson excluded)")
ok(all(x["rate_2021"] == CT[2021][b]["rate"] and x["rate_2025"] == CT[2025][b]["rate"] for b, x in {**rh, **fl}.items()), "AC18 chart series rate strings equal the CSV strings")
ok(not any(re.search(r"fetch\(|XMLHttpRequest|tx-yoy|<script[^>]*src=[^>]*json", t) for t in TXT.values()) and all(re.findall(r"<img src='([^']+)'", t) == [] or all(u.endswith(".png") for u in re.findall(r"<img src='([^']+)'", t)) for t in TXT.values()),
   "AC18 TX pages fetch no chart data (no fetch/XHR/json script; charts are static PNG/SVG figures only)")
bad = []
for row in hub[1:]:
    a, b = CT[2021][CID[row[0][0]]]["rate"], CT[2025][CID[row[0][0]]]["rate"]
    want = "n/a" if not a or not b else ("+" if Decimal(RT(b)) > Decimal(RT(a)) else "") + str(Decimal(RT(b)) - Decimal(RT(a)))
    if row[6][0] != want: bad.append((row[0][0], row[6][0], want))
ok(not bad and next(r for r in hub[1:] if r[0][0] == "Anderson County")[6][0] == "-0.116628" and "%" not in " ".join(c[0] for r in hub for c in r), f"AC19 Change = Decimal(2025) − Decimal(2021), else n/a; no percent column; bad {bad[:3]}")
ok(all(f"data-chart='tx-rates-{k}'" in hubh and f"/charts/tx-rates-{k}.png" in hubh and os.path.exists(f"docs/charts/tx-rates-{k}.png") and os.path.exists(f"docs/charts/tx-rates-{k}.svg") for k in ("rose-held", "fell")), "AC17/S6 both chart panels are on the hub with PNG + SVG copied into docs/charts/")
alts = rd("assets/charts/om-2026-11-06/alt-text.md")
ok(all(a.strip() in hubh.replace("&#x27;", "'") or html.escape(a.strip(), quote=True) in hubh for a in re.findall(r"^## \S+\.png\n(.+?)(?=\n## |\Z)", alts, flags=re.S | re.M)), "AC17 chart alt text on the hub is the dataviz alt-text.md text")

# ---------------- T7 chrome ----------------
ok(all(t.count(GOATCOUNTER_TAG) == 1 for t in TXT.values()), f"AC20 GoatCounter tag exactly once on all {len(alltx)} new TX pages")
locs = re.findall(r"<loc>([^<]+)</loc>", sm); txl = [u for u in locs if "/tx/" in u]
want_urls = ["https://openmillage.com/tx/property-tax-rates/"] + [f"https://openmillage.com/tx/{slug(c)}/" for c in COUNTIES]
ok(sorted(txl) == sorted(want_urls) and len(set(txl)) == len(txl) == 255, "AC21 sitemap lists the hub and all 254 county URLs exactly once, https://openmillage.com")
canon = {p: re.findall(r"<link rel=canonical href='([^']*)'>", TXT[p]) for p in alltx}
ok(all(len(v) == 1 and v[0].startswith("https://openmillage.com/tx/") for v in canon.values()) and not any("github.io" in t.split("<body>")[0] for t in TXT.values()), "AC21 each TX page has one canonical on https://openmillage.com (no http:, no github.io)")
ok(all(k in llms_tx for k in ("2021–2025", "$100 of taxable value", "statutory_per_100", "2025 is preliminary", "School-district and special-district rates are in the pinned data files but not listed on these pages yet", "/tx/property-tax-rates/", "/tx/<county-slug>/")),
   "AC22 llms.txt Texas line covers years, unit per $100, statutory basis, preliminary 2025, district note, hub and county URL pattern")
ok(os.path.exists("docs/tx/index.html") and canon["docs/tx/index.html"] == ["https://openmillage.com/tx/property-tax-rates/"] and
   re.sub(r"<link rel=canonical[^>]*>", "", TXT["docs/tx/index.html"]) == re.sub(r"<link rel=canonical[^>]*>", "", hubh) and "https://openmillage.com/tx/" not in txl,
   "AC23 /tx/ exists in docs/ as the same hub, canonical on /tx/property-tax-rates/ (live 200 check is post-merge: deferred-live)")
a_t, b_t = sandbox(), sandbox()
def snap(t):
    h = hashlib.sha256()
    for p in sorted(glob.glob(f"{t}/docs/tx/**/*.html", recursive=True) + glob.glob(f"{t}/docs/charts/tx-*")): h.update(p[len(t):].encode() + open(p, "rb").read())
    return h.hexdigest(), hashlib.sha256((rd(f"{t}/docs/sitemap.xml") + rd(f"{t}/docs/llms.txt")).encode()).hexdigest()
ra, rb = run_sp(a_t, "1"), run_sp(b_t, "12345")
ok(ra.returncode == 0 and rb.returncode == 0 and snap(a_t) == snap(b_t), "AC24 two builds under different PYTHONHASHSEED give byte-identical TX HTML, chart files, sitemap and llms.txt")
before = snap(b_t); rc = run_sp(b_t, "7")
ok(rc.returncode == 0 and snap(b_t) == before, "AC24 re-running statepages in place changes nothing (no duplicate sitemap or llms lines)")
cfg = json.load(open("amend3_config.json")); terms = cfg["forecast_terms"] + cfg["advocacy_terms"]
hits = sorted({t for p in alltx for t in terms if re.search(r"\b" + re.escape(t) + r"\b", prose(p).lower())})
internal = [p for p in alltx if re.search(r"\bOM-[A-Z0-9-]+|\bCEO\b|\bruling\b|Lucille|\bticket\b", TXT[p])]
ok(not hits and not internal, f"AC25 no forecast/advocacy terms and no CEO/ruling/OM-* wording on TX pages; hits {hits[:3]} {internal[:2]}")
ok(not re.search(r"\bFY\s?\d|fiscal year", "".join(prose(p) for p in alltx), re.I), "S2 no FY labels on TX pages (calendar years only)")
SITE_PIN = "c4c06dc21737d41a3dbfb0ac35b2fc3e3318c6f7"
PIN_URL = f"https://github.com/hazeydata/openmillage-site/tree/{SITE_PIN}/data/tx"
ok(all(TXT[p].count(PIN_URL) == 1 and "openmillage-site/tree/main/data/tx" not in TXT[p] for p in ("docs/tx/index.html", "docs/tx/property-tax-rates/index.html")),
   "TX-REPIN hub data-files link is pinned to the public site merge SHA (/tx/ and /tx/property-tax-rates/), not tree/main")
import ast  # statepages.py builds on import, so read the constant from its AST instead
SP_CONST = {n.targets[0].id: n.value.value for n in ast.parse(rd("statepages.py")).body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Constant)}
ok(SP_CONST.get("TX_DATA_URL") == PIN_URL, "TX-REPIN statepages.TX_DATA_URL constant itself equals the full pinned URL (not tree/main), independent of committed HTML")
for t in made: shutil.rmtree(t, ignore_errors=True)
print("FAILURES", len(FAIL)); sys.exit(1 if FAIL else 0)
