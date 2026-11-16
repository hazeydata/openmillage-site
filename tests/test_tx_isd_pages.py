#!/usr/bin/env python3
"""OM-SITE-SPECIAL-ISD-001 Phase 2: Texas school-district (ISD) pages (/tx/<home-county-slug>/<isd-slug>/ + index.json), the hub
(/tx/school-districts/), county-page ISD lists, the TX_COVER_P replacement and discovery. Each check names the AC it covers.
Expected values are read from the pinned CSVs independently of the builder; counts are computed, never typed in.
Run from the repo root after build.py, amend3.py and statepages.py:  python3 tests/test_tx_isd_pages.py"""
import ast, csv, glob, html, html.parser, json, os, re, shutil, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)
from decimal import Decimal
import sources
from analytics import GOATCOUNTER_TAG
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)
rd = lambda p: open(p, encoding="utf-8").read()
BASE = "https://openmillage.com"
YEARS = [2021, 2022, 2023, 2024, 2025]
YTXT = "2021–2025"
COMP = ("mo", "is", "total")
slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
def csvrows(p): return list(csv.DictReader(open(p, newline="", encoding="utf-8")))
def RT(s):
    if len(Decimal(s).as_tuple().digits) <= 15: return s
    return format(Decimal(f"{float(s):.15g}"), "f")
HUB = "docs/tx/school-districts/index.html"
SP = {n.targets[0].id: n.value.value for n in ast.parse(rd("statepages.py")).body
      if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)}
PRELIM, UNIT = SP["TX_PRELIM_P"], SP["TX_UNIT_P"]
LOVING_LINE = "No school district lists this county as its home county in the Comptroller files we use."
COVER = "Special districts: in the data, not on these pages yet."

# ---------------- pinned data, read independently of the builder ----------------
B = {}          # body_id -> {year: {"name", "county", comp: (row, csv row number)}}
ALLROWS = {}    # body_id -> [(year, row, rownum)] in year order, file order
PROV = {}
TX_SPECIAL = set()
for y in YEARS:
    PROV[y] = {(p["body_id"], p["levy_component"]): p for p in csvrows(f"data/tx/tx-{y}.provenance.csv")}
    for i, r in enumerate(csvrows(f"data/tx/tx-{y}.csv"), start=2):
        if r["body_type"] == "special_district": TX_SPECIAL.add(r["body_id"])
        if r["body_type"] != "school_district": continue
        yr = B.setdefault(r["body_id"], {}).setdefault(y, {"name": r["taxing_body"], "county": r["county"]})
        yr[r["levy_component"]] = (r, i)
        ALLROWS.setdefault(r["body_id"], []).append((y, r, i))
N = len(B)
LATEST = {b: v[max(v)] for b, v in B.items()}
PATH = {b: f"tx/{slug(LATEST[b]['county'])}/{slug(LATEST[b]['name'])}/" for b in B}
HOME = {}
for b in B: HOME.setdefault(LATEST[b]["county"], []).append(b)
COUNTIES = sorted({r["county"] for r in csvrows("data/tx/tx-2025.csv") if r["body_type"] == "county"})
print(f"computed: {N} TX school-district bodies, {sum(len(v) for v in ALLROWS.values())} rows, {len(HOME)} home counties of {len(COUNTIES)}")

class Page(html.parser.HTMLParser):
    """Tables by id (rows of cells: text, href, title), h1, title, meta description, JSON-LD, links in <main> (href, text), h2 texts."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.t, self.row, self.cell, self.tid = {}, None, None, None
        self.h1 = self.title = self.desc = ""; self.ld, self.links, self.h2 = [], [], []
        self._h1 = self._t = self._ld = self._h2 = self.in_main = False; self._a = None
    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag == "main": self.in_main = True
        elif tag == "table": self.tid = a.get("id"); self.t[self.tid] = []
        elif tag == "tr": self.row = []
        elif tag in ("td", "th"): self.cell = {"text": "", "href": None, "title": a.get("title"), "tag": tag}
        elif tag == "a":
            if self.cell is not None: self.cell["href"], self.cell["title"] = a.get("href"), a.get("title") or self.cell["title"]
            if self.in_main: self._a = [a.get("href"), ""]; self.links.append(self._a)
        elif tag == "h1": self._h1 = True
        elif tag == "h2": self._h2 = True; self.h2.append("")
        elif tag == "title": self._t = True
        elif tag == "meta" and a.get("name") == "description": self.desc = a.get("content")
        elif tag == "script" and a.get("type") == "application/ld+json": self._ld = True; self.ld.append("")
    def handle_data(self, d):
        if self.cell is not None: self.cell["text"] += d
        if self._h1: self.h1 += d
        if self._h2: self.h2[-1] += d
        if self._t: self.title += d
        if self._ld: self.ld[-1] += d
        if self._a is not None: self._a[1] += d
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None: self.cell["text"] = self.cell["text"].strip(); self.row.append(self.cell); self.cell = None
        elif tag == "tr" and self.row is not None: self.t[self.tid].append(self.row); self.row = None
        elif tag == "a": self._a = None
        elif tag == "main": self.in_main = False
        elif tag == "h1": self._h1 = False
        elif tag == "h2": self._h2 = False
        elif tag == "title": self._t = False
        elif tag == "script": self._ld = False
def parse(p):
    x = Page(); x.feed(rd(p)); return x
def main_of(h): return h.split("<main id=main>")[1].split("</main>")[0]
def prose(h): return html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>", " ", h, flags=re.S)))

# ---------------- AC12: one page per body, paths unique ----------------
pages = sorted(glob.glob("docs/tx/*/*/index.html"))
want_pages = sorted(f"docs/{p}index.html" for p in PATH.values())
ok(len(set(PATH.values())) == N, f"AC12 computed page paths are unique ({len(set(PATH.values()))} paths for {N} bodies)")
ok(pages == want_pages and len(pages) == N, f"AC12 exactly one page per school-district body_id in the 2021-2025 union: {len(pages)} pages, computed {N}; "
   f"missing {sorted(set(want_pages) - set(pages))[:3]} extra {sorted(set(pages) - set(want_pages))[:3]}")
ok(all(p.split("/")[2].endswith("-county") and os.path.isfile(f"docs/tx/{p.split('/')[2]}/index.html") for p in pages), "AC12 every ISD page sits under an existing TX county page (/tx/<county>-county/<isd>/)")
P = {b: parse(f"docs/{PATH[b]}index.html") for b in sorted(B)}
H = {b: rd(f"docs/{PATH[b]}index.html") for b in sorted(B)}

# ---------------- AC13: year table, cell by cell vs CSV ----------------
def want_cell(hit, y):
    if hit is None: return ("not listed", None)
    r, i = hit
    if r["rate"] == "": return ("not reported", None)
    return (RT(r["rate"]), r["source_url"])
bad13, badt, badn = [], [], []
for b in sorted(B):
    t = P[b].t.get("t-isd")
    multi = len({v["name"] for v in B[b].values()}) > 1
    if not t or len(t) != 1 + len(YEARS): bad13.append((b, "shape")); continue
    hdr = [c["text"] for c in t[0]]
    if hdr != (["Year", "Name as printed", "M&O", "I&S", "Total"] if multi else ["Year", "M&O", "I&S", "Total"]): bad13.append((b, "header", hdr)); continue
    for y, row in zip(YEARS, t[1:]):
        yr = B[b].get(y, {})
        if row[0]["text"] != str(y): bad13.append((b, y, "year")); continue
        if multi and row[1]["text"] != (yr.get("name") or ""): badn.append((b, y))
        for c, cell in zip(COMP, row[2 if multi else 1:]):
            hit = yr.get(c)
            if (cell["text"], cell["href"]) != want_cell(hit, y): bad13.append((b, y, c, cell["text"]))
            elif hit and hit[0]["rate"] and not (hit[0]["sha256"] in (cell["title"] or "") and f"data/tx/tx-{y}.csv row {hit[1]};" in cell["title"]): badt.append((b, y, c))
ok(not bad13, f"AC13 every M&O / I&S / total cell on all {N} pages equals the CSV rate string (15-significant-digit rule) linked to that year's source_url, or 'not listed' / 'not reported': bad {bad13[:3]}")
ok(not badt, f"AC13 every linked rate cell's title carries the row's sha256 and its data/tx file row: bad {badt[:3]}")
ok(not badn, f"AC13/P5 a body printed under more than one name shows each year's published name: bad {badn[:3]}")
ok(sum(len(P[b].t["t-isd"][0]) == 5 for b in B) == sum(len({v['name'] for v in B[b].values()}) > 1 for b in B), "AC13 the name column appears only on bodies printed under more than one name")
ok(all(P[b].h1 == LATEST[b]["name"] for b in B), "AC13/P5 every H1 is the latest published taxing_body (never coined)")
CH = re.compile(r"(?i)\bchange\b|\byoy\b|year[- ]over[- ]year|%")
ok(not [b for b in B if CH.search(prose(main_of(H[b])))] and not any("sortable" in main_of(H[b]) for b in B), "AC13/P3 no Change / YoY / percent column or wording and no sortable (rankable) table on ISD pages")

# ---------------- AC14-16: goldens ----------------
def page_for(name, county): return next(b for b in B if LATEST[b]["name"] == name and LATEST[b]["county"] == county)
nb, nw = page_for("Northside ISD", "Bexar County"), page_for("Northside ISD", "Wilbarger County")
ok(PATH[nb] == "tx/bexar-county/northside-isd/" and PATH[nw] == "tx/wilbarger-county/northside-isd/" and os.path.isfile("docs/tx/wilbarger-county/northside-isd/index.html"),
   "AC14 Northside ISD (Bexar) at /tx/bexar-county/northside-isd/; Northside ISD (Wilbarger) is a separate page at /tx/wilbarger-county/northside-isd/")
g = P[nb].t["t-isd"][5]
SHA = "0d4e79b71a2d7c121c3f14739d2a9f84dc92036a9d831135818bc4a69d7c2d6b"
ok(rd("docs/tx/bexar-county/northside-isd/index.html") == H[nb] and [c["text"] for c in g[1:]] == ["0.6694", "0.3355", "1.0049"] and all(SHA in c["title"] for c in g[1:]),
   "AC14 Northside ISD (Bexar) 2025: M&O 0.6694, I&S 0.3355, total 1.0049, each with sha256 0d4e79b7…7c2d6b in its title")
cb = page_for("Cumby Collegiate ISD", "Hopkins County"); ct = P[cb].t["t-isd"]
ok(P[cb].h1 == "Cumby Collegiate ISD" and [r[1]["text"] for r in ct[1:]] == ["Cumby ISD"] * 3 + ["Cumby Collegiate ISD"] * 2
   and [r[4]["text"] for r in ct[1:]] == ["1.4203", "1.4229", "1.2375", "1.2352", "1.1739"], "AC15 Cumby: H1 'Cumby Collegiate ISD', 2021-2023 rows named 'Cumby ISD', totals 1.4203, 1.4229, 1.2375, 1.2352, 1.1739")
et, sc_ = next(b for b in B if LATEST[b]["name"] == "Etoile ISD"), next(b for b in B if LATEST[b]["name"] == "Spring Creek ISD")
etr, scr = P[et].t["t-isd"], P[sc_].t["t-isd"]
ok(all(c["text"] not in ("not listed", "not reported") for c in etr[1][1:]) and all(c["text"] == "not listed" and c["href"] is None for r in etr[2:] for c in r[1:]),
   "AC16 Etoile ISD shows its 2021 values and 'not listed' (no link) for 2022-2025")
ok(all(c["text"] == "not listed" for r in scr[4:] for c in r[1:]) and all(c["href"] for r in scr[1:4] for c in r[1:]), "AC16 Spring Creek ISD shows 2021-2023 values and 'not listed' for 2024-2025")
ok(not any(re.search(r"(?i)closed|consolidat|merged", prose(H[b])) for b in (et, sc_)), "AC16 neither page says the district closed, consolidated or merged")

# ---------------- AC17: flags ----------------
ok(all(PRELIM in H[b] and UNIT in H[b] for b in B) and PRELIM in rd(HUB) and UNIT in rd(HUB), f"AC17 all {N} ISD pages and the hub carry TX_PRELIM_P and TX_UNIT_P unchanged")
ok(not [b for b in B if re.search(r"(?i)\bfinal\b", H[b].replace("A Working or Final label on the source does not clear this flag.", ""))], "AC17 no ISD page calls a rate final (only the banner clause)")
ok(all(PROV[2025][(r["body_id"], r["levy_component"])]["preliminary"] == "true" for b in B for y, r, i in ALLROWS[b] if y == 2025), "AC17 every 2025 school-district row is flagged preliminary in the pinned provenance")

# ---------------- AC18: hub ----------------
hub, hubh = parse(HUB), rd(HUB)
isd_links = [h for h, _ in hub.links if h and re.fullmatch(r"/tx/[a-z0-9-]+-county/[a-z0-9-]+/", h)]
ok(sorted(isd_links) == sorted(f"/{p}" for p in PATH.values()) and len(isd_links) == N, f"AC18 hub links every ISD page exactly once ({len(isd_links)} links, computed {N})")
groups = re.findall(r"<section class=cgroup data-q='[^']*'><h2>(.*?)</h2><ul>(.*?)</ul></section>", hubh)
gc = [(html.unescape(h2).rsplit(" (", 1)[0], re.findall(r"href='([^']+)'", ul)) for h2, ul in groups]
ok([c for c, _ in gc] == sorted(HOME) and all(sorted(l) == sorted(f"/{PATH[b]}" for b in HOME[c]) for c, l in gc)
   and all(html.unescape(h2).endswith(f"({len(HOME[html.unescape(h2).rsplit(' (', 1)[0]])})") for h2, _ in groups),
   f"AC18 hub groups ISD links by home county ({len(gc)} groups, county order) with the computed count per county")
hm = main_of(hubh).replace(UNIT, "")
ok("<table" not in hm and "sortable" not in hm and not re.search(r"\d\.\d{3}", prose(hm)), "AC18 hub has no table, no ranking and no rates")
ok(all(f"href='/tx/school-districts/'" in rd(p) for p in ("docs/tx/property-tax-rates/index.html", "docs/tx/index.html")), "AC18 the TX hub (/tx/property-tax-rates/ and /tx/) links /tx/school-districts/")
ok("/tx/" not in rd("docs/index.html"), "AC18 the home page does not link Texas, so no hub link is added there")

# ---------------- AC19: county pages ----------------
bad19, nlist = [], 0
for c in COUNTIES:
    h = rd(f"docs/tx/{slug(c)}/index.html")
    sec = re.search(r"<h2 id=school-districts>(.*?)</h2>(.*?)(?=<p><strong>Special districts)", h, re.S)
    want = [f"/{PATH[b]}" for b in sorted(HOME.get(c, []), key=lambda b: (LATEST[b]["name"], b))]
    got = re.findall(r"<li><a href='([^']+)'>", sec.group(2)) if sec else None
    if got != want or (not want and LOVING_LINE not in sec.group(2)): bad19.append(c)
    nlist += bool(want)
ok(not bad19 and nlist == len(HOME) and len(COUNTIES) - nlist == 1, f"AC19 every TX county page lists exactly its home ISDs (name order) with links; {nlist} counties have at least one; bad {bad19[:3]}")
lov = rd("docs/tx/loving-county/index.html")
ok("Loving County" not in HOME and LOVING_LINE in lov and not re.search(r"\b0 (school )?districts?\b", prose(lov)), "AC19 Loving County shows the no-home-ISD line, never a 0")
seen = {}
for c in COUNTIES:
    for u in re.findall(r"<li><a href='(/tx/[a-z0-9-]+-county/[a-z0-9-]+/)'>", rd(f"docs/tx/{slug(c)}/index.html")): seen[u] = seen.get(u, 0) + 1
ok(len(seen) == N and set(seen.values()) == {1}, "AC19/OQ-5 each ISD appears on exactly one county page (its home county)")

# ---------------- AC20/21: cover line, no TX specials ----------------
txall = sorted(glob.glob("docs/tx/**/*.html", recursive=True))
TXH = {p: rd(p) for p in txall}
ok(all(COVER in t and "School districts and special districts" not in t for t in TXH.values()), f"AC20 all {len(txall)} TX pages carry the new cover line ('{COVER}') and not the old school-district wording")
ok(not any(re.search(r"special_district|Capital Creek|school_district", t) for t in TXH.values()), "AC20 no TX page mentions special_district, Capital Creek or the raw token school_district")
docs_files = [p for p in glob.glob("docs/**/*", recursive=True) if os.path.isfile(p) and not p.endswith((".png", ".woff2", ".woff", ".ico"))]
hit21 = [p for p in docs_files if re.search(r"tx-204-202-04|Capital Creek", open(p, encoding="utf-8", errors="replace").read())]
ok(not hit21, f"AC21 tx-204-202-04 and 'Capital Creek' appear nowhere in docs/ ({len(docs_files)} files): {hit21[:3]}")
ids = set()
for p in docs_files: ids |= set(re.findall(r"tx-\d{3}-\d{3}-\d{2}", open(p, encoding="utf-8", errors="replace").read()))
ok(TX_SPECIAL and not (ids & TX_SPECIAL), f"AC21 no TX special-district body_id ({len(TX_SPECIAL)} in the data) appears in docs/")

# ---------------- AC22-26: discovery ----------------
sm = rd("docs/sitemap.xml"); locs = re.findall(r"<loc>([^<]+)</loc>", sm)
allp = sorted(glob.glob("docs/**/*.html", recursive=True))
want_urls = [f"{BASE}/tx/school-districts/"] + [f"{BASE}/{p}" for p in PATH.values()]
ok(all(u in set(locs) for u in want_urls) and len(locs) == len(set(locs)) == len(allp) - 1, f"AC22 all {len(want_urls)} new TX URLs in sitemap.xml; sitemap locs {len(locs)} == docs pages {len(allp)} minus the /tx/ alias")
titles = {}
for p in allp: titles.setdefault(re.search(r"<title>(.*?)</title>", rd(p)).group(1), []).append(p)
dupname = {n for n in (LATEST[b]["name"] for b in B) if sum(LATEST[x]["name"] == n for x in B) > 1}
bad23 = []
for b in sorted(B):
    x, h = P[b], H[b]; head = h.split("</head>")[0]; url = f"{BASE}/{PATH[b]}"
    lds = [json.loads(s) for s in x.ld]
    table_srcs = {c["href"] for r in x.t["t-isd"][1:] for c in r if c["href"]}
    main_srcs = {u for u, _ in x.links if u and "comptroller.texas.gov" in u}
    name, county = LATEST[b]["name"], LATEST[b]["county"]
    want_t = f"{name} ({county}) tax rate {YTXT}" if name in dupname else f"{name} tax rate {YTXT}"
    good = (head.count(GOATCOUNTER_TAG) == 1 and f"<link rel=canonical href='{url}'>" in head and html.unescape(x.title) == want_t and len(titles[re.search(r"<title>(.*?)</title>", h).group(1)]) == 1
            and x.desc and len(lds) == 1 and lds[0]["@type"] == "Dataset" and set(lds[0]["isBasedOn"]) == table_srcs == main_srcs and table_srcs and lds[0]["url"] == url)
    if not good: bad23.append(b)
descs = [P[b].desc for b in B]
ok(not bad23 and len(set(descs)) == N, f"AC23 every ISD page: GoatCounter once in <head>, canonical openmillage.com URL, unique title '<Name> tax rate {YTXT}' (shared names add the county), unique meta description, Dataset JSON-LD with isBasedOn == the page's Comptroller source links: {bad23[:3]}")
ok(html.unescape(P[nb].title) == f"Northside ISD (Bexar County) tax rate {YTXT}" and html.unescape(P[nw].title) == f"Northside ISD (Wilbarger County) tax rate {YTXT}" and len(dupname) == 11,
   f"AC23 shared names are told apart by county in the title (e.g. 'Northside ISD (Bexar County) tax rate {YTXT}'); {len(dupname)} shared names")
hld = [json.loads(s) for s in hub.ld]
ok(hubh.split("</head>")[0].count(GOATCOUNTER_TAG) == 1 and f"<link rel=canonical href='{BASE}/tx/school-districts/'>" in hubh and len(titles[re.search(r"<title>(.*?)</title>", hubh).group(1)]) == 1 and hub.desc
   and len(hld) == 1 and hld[0]["@type"] == "Dataset" and set(hld[0]["isBasedOn"]) == {u for u, _ in hub.links if u and "comptroller.texas.gov" in u} == {r["source_url"] for v in ALLROWS.values() for _, r, _ in v},
   "AC23 hub: GoatCounter, canonical, unique title + description, Dataset JSON-LD isBasedOn == its source-file links == every school-district source_url")
KEYS = sources.BASE_KEYS + ["preliminary", "unit_basis"]
bad24 = []
for b in sorted(B):
    j = json.load(open(f"docs/{PATH[b]}index.json", encoding="utf-8"))
    want = [{**{k: r[k] for k in sources.BASE_KEYS}, "preliminary": PROV[y][(b, r["levy_component"])]["preliminary"], "unit_basis": PROV[y][(b, r["levy_component"])]["unit_basis"]} for y, r, i in ALLROWS[b]]
    shown = sum(1 for r in P[b].t["t-isd"][1:] for c in r[-3:] if c["text"] != "not listed")  # M&O, I&S, total cells that come from a row
    if not (isinstance(j, list) and j == want and all(list(x) == KEYS for x in j) and len(j) == shown): bad24.append(b)
ok(not bad24, f"AC24 each index.json holds exactly the page's rows: 17 base keys (name, order, value vs CSV) then preliminary, unit_basis from provenance; no derived numbers: {bad24[:3]}")
bad25 = []
for b in B:
    allowed = {RT(r["rate"]) for _, r, _ in ALLROWS[b] if r["rate"]}
    decs = set(re.findall(r"(?<![\w./-])\d+\.\d+(?![\w./-])", prose(main_of(H[b]).replace(UNIT, ""))))  # TX_UNIT_P: 0.5000 example + statute section numbers
    if decs - allowed or re.search(r"(?i)\b(estimat\w*|approximately|projected|ranked|rank)\b", prose(main_of(H[b]))): bad25.append((b, sorted(decs - allowed)[:3]))
ok(not bad25, f"AC25 every decimal on an ISD page is one of that body's CSV rate strings (outside the unchanged TX_UNIT_P callout); no estimate/rank wording: {bad25[:3]}")
COUNT_LIT = re.compile(r"(?<![\w.,#])(?:1,015|1015)(?![\w]|[.,]\d)")
ok(not COUNT_LIT.search(rd("statepages.py")), "AC25 no literal '1,015' / '1015' in statepages.py")
ok(f"{N:,} Texas independent school districts" in prose(main_of(hubh)), "AC25 the hub's district count is the computed body count")
llms = rd("docs/llms.txt")
lines = [l for l in llms.splitlines() if f"{BASE}/tx/<county-slug>/<district-slug>/" in l]
ok(len(lines) == 1 and "absent is not zero" in lines[0].lower() and f"{BASE}/tx/school-districts/" in lines[0] and "index.json" in lines[0] and not re.search(r"\b\d\.\d{3,}\b", lines[0]),
   "AC26 llms.txt has one line for the TX ISD page family (hub, URL pattern, index.json, absent-is-not-zero rule, no rate numbers)")

# ---------------- fail-closed: path collision ----------------
import statepages as spm  # main() is guarded by __name__, so importing builds nothing
_rows = spm.rows
def collide(p):
    rs = _rows(p)
    if p == "data/tx/tx-2025.csv":
        for r in rs:
            if r["body_id"] == nw: r["county"] = "Bexar County"
    return rs
spm.rows = collide
try: spm.tx_isds(); res = None
except sources.DataError as e: res = str(e)
spm.rows = _rows
ok(res is not None and "path collision" in res and "/tx/bexar-county/northside-isd/" in res, f"AC12 the build fails when two bodies would share a path ({res})")

# ---------------- AC27: no network, deterministic, docs/ current ----------------
BLOCK = "import socket\ndef _no(*a, **k): raise OSError('network disabled in build')\nsocket.socket.connect = _no\nsocket.create_connection = _no\nsocket.getaddrinfo = _no\n"
def build_in(tmp, seed):
    for n in ("build.py", "sources.py", "amend3.py", "statepages.py", "analytics.py", "site_chrome.py", "redo.py", "amend3_config.json"): shutil.copy(n, tmp)
    for n in ("assets", "content", "data"): shutil.copytree(n, os.path.join(tmp, n))
    blocker = os.path.join(tmp, "nonet"); os.makedirs(blocker); open(os.path.join(blocker, "sitecustomize.py"), "w").write(BLOCK)
    env = dict(os.environ, PYTHONPATH=blocker, PYTHONDONTWRITEBYTECODE="1", DATA_GLOB="data/*.csv", PYTHONHASHSEED=seed); env.pop("OUT", None)
    for s in ("build.py", "amend3.py", "statepages.py"):
        r = subprocess.run([sys.executable, s], cwd=tmp, env=env, capture_output=True, text=True)
        if r.returncode: return r
    return r
def snap(d):
    out = {}
    for p in sorted(glob.glob(os.path.join(d, "docs/**/*"), recursive=True)):
        if os.path.isfile(p): out[os.path.relpath(p, d)] = re.sub(rb"<lastmod>[^<]*</lastmod>", b"", open(p, "rb").read())
    return out
with tempfile.TemporaryDirectory(prefix="om-isd-a-") as t1, tempfile.TemporaryDirectory(prefix="om-isd-b-") as t2:
    r1, r2 = build_in(t1, "1"), build_in(t2, "4242")
    ok(r1.returncode == 0 and r2.returncode == 0, "AC27 full build (build.py, amend3.py, statepages.py) succeeds with network disabled (socket blocked)" + ("" if r1.returncode == 0 else f": {r1.stderr[-300:]}"))
    s1, s2 = snap(t1), snap(t2)
    ok(s1 == s2 and s1, f"AC27 two builds under different PYTHONHASHSEED give byte-identical docs/ ({len(s1)} files) apart from sitemap lastmod")
    fresh = {k: v for k, v in s1.items() if k.startswith("docs/tx/") or k in ("docs/llms.txt", "docs/sitemap.xml")}
    cur = {k: re.sub(rb"<lastmod>[^<]*</lastmod>", b"", open(k, "rb").read()) for k in fresh if os.path.isfile(k)}
    ok(fresh and cur == fresh and len(fresh) - 2 == len([p for p in glob.glob("docs/tx/**/*", recursive=True) if os.path.isfile(p)]),
       f"AC27 committed docs/tx/, llms.txt and sitemap.xml equal a fresh build ({len(fresh)} files)")
ok(not re.search(r"\b(urllib|requests|http\.client|socket|subprocess)\b", rd("statepages.py")), "AC27 statepages.py imports no network or subprocess module")

# ---------------- AC31: docs match code ----------------
rm = rd("README.md")
ok(all(s in rm for s in ("/tx/school-districts/", "/tx/<county-slug>/<district-slug>/", "TX_ISD_COPY", "python3 tests/test_tx_isd_pages.py", COVER)), "AC31 README describes the ISD pages, hub, copy block, cover line and the test command")
wf = rd(".github/workflows/build.yml")
ok("      - run: python3 tests/test_tx_isd_pages.py\n" in wf, "AC28 CI runs this test")
print("FAILURES", len(FAIL)); sys.exit(1 if FAIL else 0)
