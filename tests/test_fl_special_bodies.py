#!/usr/bin/env python3
"""OM-SITE-SPECIAL-ISD-001 Phase 1: Florida independent special-district body pages (/fl/special-districts/<slug>/), the hub
(/fl/special-districts/), county-page links and discovery. Each check names the AC it covers. Expected rows are read from the
pinned CSVs independently of the builder. Run from the repo root after build.py, amend3.py and statepages.py:
    python3 tests/test_fl_special_bodies.py"""
import csv, glob, hashlib, html, html.parser, json, os, re, shutil, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)
import sources, site_chrome as sc
from analytics import GOATCOUNTER_TAG
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)
rd = lambda p: open(p, encoding="utf-8").read()
BASE = os.environ.get("SITE_BASE", "https://openmillage.com").rstrip("/")
PATH = "/" + BASE.split("/", 3)[3] if BASE.count("/") > 2 else ""
slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
HUB = "docs/fl/special-districts/index.html"
H1_FILE = "data/ref/fl_special_body_h1.csv"
NO_ROWS = "No special-district rows published yet for this county."

# ---------------- pinned data, read independently of the builder ----------------
def csvrows(p): return list(csv.DictReader(open(p, newline="", encoding="utf-8")))
RAW = [r for r in csvrows(sources.SD_FILE)] + [r for r in csvrows(sources.ALT_FILE) if r["body_type"] == "special_district"]
ok(all(r["body_type"] == "special_district" for r in RAW) and not any(r["body_type"] == "special_district" for r in csvrows(sources.ALT_FILE) if r["county"] == "Pasco"),
   "AC1 input = TACD special rows + alt-source special rows; the Pasco cite-only row is not a special-district row")
BODIES = {}
for r in RAW: BODIES.setdefault(r["body_id"], []).append(r)
PART = ("operating", "okeechobee_basin", "everglades_construction")  # LAYOUT (b)3 / L1, written out here, not imported from the builder
for b in BODIES.values(): b.sort(key=lambda r: (r["county"], PART.index(r["levy_component"]) if r["levy_component"] in PART else 3))  # counties A-Z; parts in PART order, others in file order
SLUG = {b: re.fullmatch(r"fl-(.+)-special_district", b).group(1) for b in BODIES}
LOADED = {sources.key(r): r for r in sources.load_rows()}
N = len(BODIES)
print(f"computed: {N} FL special-district bodies, {len(RAW)} rows, {len({r['county'] for r in RAW})} counties")

class Page(html.parser.HTMLParser):
    """Tables (rows of cells: text, [(href, title)], code titles, tag, section, attrs), h1, links in <main>, title, meta description, JSON-LD.
    A cell with rowspan=n is repeated at the start of the next n-1 rows of its section (flag "spanned"), so each logical row has all its cells."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.cell, self.row, self.h1, self.main_links, self.in_main, self.title, self.desc, self.ld = [], None, None, "", [], False, "", "", []
        self._t = self._h1 = self._ld = False
        self.sec, self.span = None, None
    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag == "main": self.in_main = True
        elif tag == "table": self.tables.append([]); self.sec = None; self.span = None
        elif tag in ("thead", "tbody"): self.sec = tag; self.span = None
        elif tag == "tr":
            self.row = []
            if self.span and self.span[1] > 0: self.row.append(dict(self.span[0], spanned=True)); self.span[1] -= 1
        elif tag in ("td", "th"):
            self.cell = {"text": "", "links": [], "codes": [], "tag": tag, "sec": self.sec, "attrs": a}
            if int(a.get("rowspan") or 1) > 1: self.span = [self.cell, int(a["rowspan"]) - 1]
        elif tag == "a":
            if self.cell is not None: self.cell["links"].append((a.get("href"), a.get("title")))
            if self.in_main: self.main_links.append(a.get("href"))
        elif tag == "code" and self.cell is not None: self.cell["codes"].append(a.get("title"))
        elif tag == "h1": self._h1 = True
        elif tag == "title": self._t = True
        elif tag == "meta" and a.get("name") == "description": self.desc = a.get("content")
        elif tag == "script" and a.get("type") == "application/ld+json": self._ld = True; self.ld.append("")
    def handle_data(self, d):
        if self.cell is not None: self.cell["text"] += d
        if self._h1: self.h1 += d
        if self._t: self.title += d
        if self._ld: self.ld[-1] += d
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None: self.cell["text"] = self.cell["text"].strip(); self.row.append(self.cell); self.cell = None
        elif tag == "tr" and self.row is not None: self.tables[-1].append(self.row); self.row = None
        elif tag == "h1": self._h1 = False
        elif tag == "title": self._t = False
        elif tag == "script": self._ld = False
        elif tag == "main": self.in_main = False
def parse(p):
    x = Page(); x.feed(rd(p)); x.close(); return x
def body_path(b): return f"docs/fl/special-districts/{SLUG[b]}/index.html"
def levy(r): return "(operating + debt, combined)" if r["levy_component"] == "all_components_combined" else sc.label(r["levy_component"])
def data_rows(t): return [row for row in t if row[-1]["sec"] != "thead" and (row[-1]["sec"] == "tbody" or row[0]["tag"] == "td")]

# ---------------- AC1: one page per body, computed ----------------
dirs = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob("docs/fl/special-districts/*/index.html"))
ok(len(dirs) == N and set(dirs) == set(SLUG.values()) and len(set(SLUG.values())) == N, f"AC1 {len(dirs)} body pages == {N} distinct body_ids (computed), slugs unique")
ok(all(os.path.isfile(f"docs/fl/special-districts/{s}/index.json") for s in SLUG.values()), "AC1 index.json beside every body page")

def body_note(r):  # the note shown for this row on its body page: the shared NWFWMD note (sources.NOTE_MERGED) or its own NOTE_UNDER_TABLE note
    m = sources.NOTE_MERGED.get(r["body_id"])
    return m[1] if m and r["county"] in m[0] else sources.NOTE_UNDER_TABLE[(r["county"], r["body_id"])]
# ---------------- AC2: one table row per CSV row ----------------
P = {b: parse(body_path(b)) for b in BODIES}
bad2, nrows = [], 0
for b, rs in BODIES.items():
    t = data_rows(P[b].tables[0]) if P[b].tables else []
    nrows += len(t)
    if len(t) != len(rs) or len(P[b].tables) != 1: bad2.append((b, "row count", len(t), len(rs))); continue
    for row, r in zip(t, rs):
        c, lv, rt, src = row
        want_note = LOADED[(r["county"], r["body_id"], r["levy_component"], r["rate_kind"])]["note"]
        if (r["county"], r["body_id"]) in sources.NOTE_UNDER_TABLE:  # by-eye r1 fix 3: the cell carries "Note N"; the note sits under the table
            m = re.search(r"#note-(\d+)", " ".join(h for h, _ in c["links"]))
            want_note = "Note" if m and f"<p class=footnote id=note-{m.group(1)}>Note: {html.escape(body_note(r))}</p>" in rd(body_path(b)) else "(numbered note missing)"
        if not (c["text"].startswith(r["county"]) and c["links"][0][0] == f"{PATH}/fl/2025/{slug(r['county'])}-county/" and lv["text"] == levy(r)
                and rt["text"] == f"{float(r['rate']):.4f}" and src["links"][0][0] == r["source_url"] and src["codes"] == [r["sha256"]]
                and (want_note or "") == c["text"][len(r["county"]):].strip()):
            bad2.append((b, r["county"], r["levy_component"]))
ok(not bad2 and nrows == len(RAW), f"AC2 {nrows} table rows == {len(RAW)} CSV rows; county, levy label, rate, source_url and sha256 (title) match row by row: {bad2[:3]}")
_raw_notes = [r for r in RAW if r.get("note")]
ok(_raw_notes and all(LOADED[sources.key(r)]["note"] for r in _raw_notes), f"AC2 every CSV row with a note ({len(_raw_notes)}) shows a note on its body page")

# ---------------- AC3-6: goldens ----------------
CFTOD_SHA = "1f4e3b57663e35703d71d5338c0add294164c90813ef78275af7d978a9486a68"
cf = parse("docs/fl/special-districts/cftod/index.html"); t = data_rows(cf.tables[0])
ok(cf.h1 == "Central Florida Tourism Oversight District" and len(t) == 1 and t[0][0]["text"].startswith("Orange") and t[0][1]["text"] == "(operating + debt, combined)"
   and t[0][2]["text"] == "12.4236" and "contentFileID=416847" in t[0][3]["links"][0][0] and t[0][3]["codes"] == [CFTOD_SHA] and "formerly reedy creek" in t[0][0]["text"].lower(),
   "AC3 golden CFTOD: H1, one Orange row, (operating + debt, combined), 12.4236, OCPA contentFileID=416847, sha256, note 'formerly Reedy Creek'")
SJR = ["Alachua", "Baker", "Brevard", "Clay", "Duval",  # Clay: OM-FL-COVERAGE-001 (SJRWMD FY 2025-26 Final Budget, alt row)
       "Flagler", "Indian River", "Lake", "Marion", "Orange", "Osceola", "Putnam", "Seminole", "St. Johns", "Volusia"]
sj = [row[0]["links"][0][0] for row in data_rows(parse("docs/fl/special-districts/sjrwmd/index.html").tables[0])]
ok(sj == [f"{PATH}/fl/2025/{slug(c)}-county/" for c in SJR], f"AC4 golden SJRWMD lists exactly the {len(SJR)} counties: {len(sj)} rows")
ok("fl-childrens-trust-alachua-special_district" in BODIES and SLUG["fl-childrens-trust-alachua-special_district"] == "childrens-trust-alachua", "AC5 slug childrens-trust-alachua exists in the data")
ct = data_rows(parse("docs/fl/special-districts/childrens-trust-alachua/index.html").tables[0])
ok(len(ct) == 1 and ct[0][0]["text"] == "Alachua" and ct[0][2]["text"] == "0.4500" and ct[0][3]["codes"] == ["6f6d8dfbc4466961fa1c45531cb734ae1f0863873188cf6810622827ec700861"],
   "AC5 golden Children's Trust of Alachua County: Alachua, 0.4500, sha256")
sf_h = rd("docs/fl/special-districts/sfwmd/index.html"); sf = data_rows(parse("docs/fl/special-districts/sfwmd/index.html").tables[0])
cty = lambda row: row[0]["links"][0][0].split("/")[-2][:-len("-county")]
bro = [r for r in sf if cty(r) == "broward"]; ora = [r for r in sf if cty(r) == "orange"]; col = [r for r in sf if cty(r) == "collier"]
parts = {}
for r in sf:
    if cty(r) not in ("broward", "orange", "collier"): parts.setdefault(cty(r), []).append((r[1]["text"], r[2]["text"]))
P3 = sorted([("Operating", "0.0948"), ("Okeechobee Basin", "0.1026"), ("Everglades Construction", "0.0327")])
# Collier (OM-FL-COVERAGE-001): operating 0.0948 then big_cypress_basin 0.0978 (label from FL_HUB_COPY; data value unchanged), never summed
ok([(r[1]["text"], r[2]["text"]) for r in col] == [("Operating", "0.0948"), (sources.FL_HUB_COPY["levy_labels"]["big_cypress_basin"], "0.0978")]
   and [r["levy_component"] for r in BODIES["fl-sfwmd-special_district"] if r["county"] == "Collier"] == ["operating", "big_cypress_basin"] and "0.1926" not in sf_h,
   "AC6/OM-FL-COVERAGE-001 AC15 SFWMD Collier: Operating 0.0948 and Big Cypress Basin 0.0978, in that order, no sum")
ok(len(sf) == 28 == len(BODIES["fl-sfwmd-special_district"]) and len(bro) == 1 and bro[0][1]["text"] == "(operating + debt, combined)" and bro[0][2]["text"] == "0.2301"
   and len(ora) == 1 and ora[0][1]["text"] == "Operating" and ora[0][2]["text"] == "0.2301" and "0.0948 + 0.1026 + 0.0327 = 0.2301" in ora[0][0]["text"]
   and len(parts) == 8 and all(sorted(v) == P3 for v in parts.values()), "AC6 SFWMD 28 rows as published (26 + Collier 2): Broward combined 0.2301, Orange operating 0.2301 with its note, 8 counties x 3 parts")
fn3 = re.search(r'^3\. .*?\nWording: "(.*)"\s*$', rd("data/ref/fl_special_district_footnotes.md"), re.M | re.S)
ok(fn3 and html.escape(fn3.group(1)) in sf_h and "Note 3:" in sf_h, "AC6 footnote 3 from data/ref/fl_special_district_footnotes.md shown on the SFWMD page")
ok(not re.search(r"(?i)<t[dh][^>]*>\s*(total|sum)\b", sf_h), "AC6 no total/sum row added by the site")

# ---------------- LAYOUT (b) / L1: row order inside a county ----------------
sf_rows = BODIES["fl-sfwmd-special_district"]
sf_cty = [cty(r) for r in sf]
ok([r["county"] for r in sf_rows] == sorted(r["county"] for r in sf_rows)
   and list(dict.fromkeys(sf_cty)) == [slug(c) for c in sorted({r["county"] for r in sf_rows})], "L1 SFWMD counties in alphabetical order, each county's rows contiguous")
ok(len(parts) == 8 and all([lv for lv, _ in v] == ["Operating", "Okeechobee Basin", "Everglades Construction"] for v in parts.values())
   and {"lee", "miami-dade"} <= set(parts), "L1 every 3-part SFWMD county (incl. Lee and Miami-Dade, whose file order differs) reads Operating, Okeechobee Basin, Everglades Construction")
_hh = [row[1]["text"] for row in data_rows(P["fl-hendry-hospital-special_district"].tables[0])]
ok(len(_hh) == 2 and _hh[0] == "Operating" and _hh == [levy(r) for r in BODIES["fl-hendry-hospital-special_district"]], f"L1 other components follow the fixed parts in file order (Hendry hospital: {_hh})")
ok(len(sf) == 28 and not re.search(r"(?i)<t[dh][^>]*>\s*(total|sum)\b", sf_h), "L1 AC6 unchanged: 28 SFWMD rows (26 + Collier 2, OM-FL-COVERAGE-001), no sum row")

# ---------------- LAYOUT caption: stacked-table caption is block-level at <=40rem ----------------
_css = rd("docs/style.css"); _i = _css.find("table.sd-rates thead"); _s = _css.rfind("@media", 0, _i); _d = 0; _blk = ""
for _k in range(_css.find("{", _s), len(_css)):
    _d += {"{": 1, "}": -1}.get(_css[_k], 0)
    if _d == 0: _blk = _css[_s:_k + 1]; break
ok(_i > 0 and _blk.replace(" ", "").startswith("@media(max-width:40rem)") and "table.sd-rates caption{display:block}" in _blk, "LAYOUT caption: table.sd-rates caption{display:block} sits inside the @media (max-width:40rem) block with the sd-rates rules")

# ---------------- LAYOUT (b) / L2: grouped, ARIA-roled markup on every body page ----------------
bad_l2 = []
for b, rs in BODIES.items():
    h = rd(body_path(b))
    m = re.search(r"<table class=sd-rates role=table>.*?</table>", h, re.S)
    if not m: bad_l2.append((b, "no table.sd-rates[role=table]")); continue
    t = m.group(0)
    tb = re.findall(r"<tbody role=rowgroup>(.*?)</tbody>", t, re.S)
    want = {}
    for r in rs: want[r["county"]] = want.get(r["county"], 0) + 1
    heads = [re.findall(r"<th scope=rowgroup rowspan=(\d+) role=rowheader><a href='([^']+)'", g) for g in tb]
    good = (len(tb) == len(want) == t.count("<tbody") and "<thead role=rowgroup><tr role=row>" in t
            and t.count("role=columnheader") == 4 and t.count("<th scope=col role=columnheader") == 4
            and all(len(hd) == 1 for hd in heads)
            and [(int(hd[0][0]), hd[0][1]) for hd in heads] == [(n, f"{PATH}/fl/2025/{slug(c)}-county/") for c, n in want.items()]
            and all(g.count("<tr role=row>") == n and g.count("<tr") == n for g, n in zip(tb, want.values()))
            and t.count("<td") == len(re.findall(r"<td(?: class=(?:num|src))? role=cell>", t)) == 3 * len(rs)
            and t.count("<td class=num role=cell>") == len(rs) and t.count("<td class=src role=cell>") == len(rs)
            and t.count("<tr") == t.count("<tr role=row>") == len(rs) + 1)
    if not good: bad_l2.append(b)
ok(not bad_l2, f"L2 every body page: table.sd-rates role=table, thead/tbody role=rowgroup, one tbody per county, county th scope=rowgroup rowspan=n role=rowheader, roles on every row and cell: {bad_l2[:3]}")
ok(all(row[2]["text"] == f"{float(r['rate']):.4f}" for row, r in zip(sf, sf_rows)) and any(row[2]["text"] == "0.0948" for row in sf),
   "L2 rate cells hold the bare rate (e.g. '0.0948'); the unit is in the header and caption")
import site_chrome as _sc
_css = _sc.CSS
ok("table.sd-rates td.num,table.sd-rates td.src{white-space:nowrap}" in _css and "table.sd-rates tbody+tbody{border-top:1px solid var(--border)}" in _css
   and "table.sd-rates tbody th,table.sd-rates tbody td{border-bottom:0}" in _css and re.search(r"@media \(max-width:40rem\)\{table\.sd-rates thead\{position:absolute;left:-9999px\}", _css)
   and "table.sd-rates tr{display:grid;grid-template-columns:1fr auto;column-gap:.75rem;border:0}" in _css
   and "td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}" in _css,
   "L2 CSS: rate right/tabular/nowrap, source nowrap, rule between county groups only, stacks at <= 40rem with a visually hidden thead")

# ---------------- AC7: names ----------------
picks = {r["body_id"]: r["h1"] for r in csvrows(H1_FILE)}
bad7 = []
for b, rs in BODIES.items():
    names = list(dict.fromkeys(sc.display_name(r["taxing_body"]) for r in rs))
    h, also = P[b].h1, re.search(r"<p>Also printed as: (.*?)</p>", rd(body_path(b)))
    if len(names) > 1:
        others = [n for n in names if n != picks.get(b)]
        if not (b in picks and h == picks[b] and picks[b] in names and also and all(f"<q>{html.escape(n)}</q>" in also.group(1) for n in others)): bad7.append(b)
    elif h != names[0] or also: bad7.append(b)
multi = [b for b, rs in BODIES.items() if len({r["taxing_body"] for r in rs}) > 1]
ok(not bad7 and sorted(picks) == sorted(multi), f"AC7 H1 is a published name ({len(multi)} multi-name bodies take theirs from {H1_FILE}; the rest show their one name); others under 'Also printed as': {bad7[:3]}")
ok(picks == {"fl-sebastian-inlet-special_district": "Sebastian Inlet District", "fl-boca-grande-fire-charlotte-special_district": "Boca Grande Fire Control District",
             "fl-hendry-hospital-special_district": "Hospital Authority (Hendry) - operating"}, "AC7 H1 picks are the OQ-6 defaults")

# ---------------- temp builds (no network) ----------------
BLOCK = "import socket\ndef _no(*a, **k): raise OSError('network disabled in build')\nsocket.socket.connect = _no\nsocket.create_connection = _no\nsocket.getaddrinfo = _no\n"
def build_in(tmp, mutate=None):
    for n in ("build.py", "sources.py", "amend3.py", "analytics.py", "site_chrome.py", "redo.py", "amend3_config.json"): shutil.copy(n, tmp)
    for n in ("assets", "content", "data"): shutil.copytree(n, os.path.join(tmp, n))
    if mutate: mutate(tmp)
    blocker = os.path.join(tmp, "nonet"); os.makedirs(blocker); open(os.path.join(blocker, "sitecustomize.py"), "w").write(BLOCK)
    env = dict(os.environ, PYTHONPATH=blocker, PYTHONDONTWRITEBYTECODE="1", DATA_GLOB="data/*.csv"); env.pop("OUT", None)
    return subprocess.run([sys.executable, "build.py"], cwd=tmp, env=env, capture_output=True, text=True)
def set_h1(body_id, h1):
    def m(tmp):
        p = os.path.join(tmp, H1_FILE); rs = csvrows(p)
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["body_id", "h1"], lineterminator="\n"); w.writeheader()
            w.writerows([{"body_id": r["body_id"], "h1": h1 if r["body_id"] == body_id else r["h1"]} for r in rs if h1 is not None or r["body_id"] != body_id])
    return m
for bid, h1, why in (("fl-sebastian-inlet-special_district", "Sebastian Inlet Dist.", "a non-published h1"),
                     ("fl-hendry-hospital-special_district", "Hospital Authority (Hendry)", "a coined h1 (no '- operating')"),
                     ("fl-sebastian-inlet-special_district", None, "a missing pick for a multi-name body")):
    with tempfile.TemporaryDirectory(prefix="om-sd-h1-") as tmp:
        r = build_in(tmp, set_h1(bid, h1))
        ok(r.returncode != 0 and "BUILD FAILED" in r.stderr and H1_FILE in r.stderr and not os.path.exists(os.path.join(tmp, "docs", "fl", "special-districts"))
           and not os.path.exists(os.path.join(tmp, "docs", "index.html")), f"AC7 mutation: {why} for {bid} fails the build (non-zero exit) and writes no pages")

# ---------------- AC8: coverage + not yet sourced ----------------
cov = sources.coverage(sources.load_rows()); sent = sources.coverage_sentence(cov); meta = sources.coverage_sentence(cov, meta=True)
newp = [HUB] + [body_path(b) for b in BODIES]
ONLY = re.compile(r"(?i)county pages? only|on (?:those|that|their|its) county pages?")
ok(all(html.escape(sent) in rd(p) for p in newp), f"AC8 computed coverage_sentence(cov) on the hub and all {N} body pages")
ok(not ONLY.search(sent) and not ONLY.search(meta) and not ONLY.search(sources.alt_sentence({"DeSoto": 1})), "AC8 neither alt tail (page or meta, plural or singular) says the rows are only on county pages")
ok(sent.startswith(f"{cov['checked']} of {cov['total']} Florida counties checked against official sources; {cov['in_csv']} have special-district rows in the Amendment 3 baseline CSV."),
   "AC8 computed head unchanged")
ok(all(meta in parse(p).desc and all(meta in json.loads(x)["description"] for x in parse(p).ld) for p in newp), "AC8 meta variant in meta description and JSON-LD description")
OPEN = [o for o in csvrows(sources.STATUS_FILE) if o["status"] != sources.PARTIAL]  # OM-FL-COVERAGE-001: `partial` counties have rows; listed separately
PARTIAL = [o["county"] for o in csvrows(sources.STATUS_FILE) if o["status"] == sources.PARTIAL]
bad8 = []
for p in newp:
    h = rd(p); m = re.search(r"<ul class=nys>(.*?)</ul>", h)
    lis = [html.unescape(x) for x in re.findall(r"<li>([^<]*)</li>", m.group(1))] if m else []
    want = sorted(f"{o['county']}: " + ("no 2025 TACD file" if o["status"] == "no_file" else sources.FL_SD_COPY["nys_reason"][o["status"]]) for o in OPEN)
    cells = [c["text"] for t in parse(p).tables for row in data_rows(t) for c in row[:1]]
    if sorted(lis) != want or any(c.startswith(o["county"]) for c in cells for o in OPEN): bad8.append(p)
# OM-FL-COVERAGE-001 (openmillage@9d125472): Liberty now has a sourced row, so it is no longer listed; every no_file county still reads "no 2025 TACD file"
_nys_hub = re.search(r"<ul class=nys>(.*?)</ul>", rd(HUB)).group(1)
ok(len(OPEN) == len(cov["not_yet_sourced"]) and not bad8 and all(f"{o['county']}: no 2025 TACD file" in _nys_hub for o in OPEN if o["status"] == "no_file") and "Liberty" not in _nys_hub,
   f"AC8 the {len(OPEN)} open counties listed as not yet sourced (each no_file county: no 2025 TACD file; Liberty not listed) with no rate cell, on hub and body pages: {bad8[:3]}")
_pl = html.escape(sources.FL_HUB_COPY["partial_list"].format(names=sources.join_names(PARTIAL)))
ok(PARTIAL == cov["partial"] and all(_pl in rd(p) for p in newp), f"AC8 the partial counties {PARTIAL} are named once as partial on hub and body pages, not as not yet sourced")
def drop_open(county):
    def m(tmp):
        p = os.path.join(tmp, sources.STATUS_FILE); ls = open(p, encoding="utf-8").read().splitlines(keepends=True)
        open(p, "w", encoding="utf-8").write("".join(l for l in ls if not l.startswith(county + ",")))
        lp = os.path.join(tmp, sources.LOCK); lk = json.load(open(lp))
        for f in lk["files"]:
            if f["path"] == sources.STATUS_FILE: f["sha256"] = hashlib.sha256(open(p, "rb").read()).hexdigest()
        json.dump(lk, open(lp, "w"), indent=1)
    return m
_drop = sorted(o["county"] for o in OPEN)[-1]
with tempfile.TemporaryDirectory(prefix="om-sd-cov-") as tmp:
    r = build_in(tmp, drop_open(_drop))
    _want = f"{cov['checked'] + 1} of {cov['total']} Florida counties checked against official sources"
    _pp = [os.path.join(tmp, "docs/fl/special-districts/index.html"), os.path.join(tmp, "docs/fl/special-districts/cftod/index.html")]
    ok(r.returncode == 0 and all(os.path.exists(x) and _want in rd(x) and f"<li>{_drop}:" not in rd(x) for x in _pp),
       f"AC8 perturbation: dropping {_drop} from the status file re-renders hub and body pages with '{_want}' and no {_drop} not-yet-sourced line")
# OM-FL-COVERAGE-001 close-out r2: exception wording per fl-closeout-item5-copy.md (sha 19da2450)
_EXC = "2025 TACD file checked, but we can't use it yet"
def _txt(p): return html.unescape(re.sub(r"<[^>]+>", "", rd(p)))
_hits = [f"{c}: {_EXC}" for c in ("Columbia", "Monroe", "Sumter")]
ok(sources.FL_SD_COPY["nys_reason"]["exception"] == _EXC
   and all(h in _txt(p) for h in _hits for p in ("docs/fl/special-districts/index.html", "docs/fl/special-districts/nwfwmd/index.html"))
   and not any("not yet verified" in open(os.path.join(d, f), encoding="utf-8").read() for d, _, fs in os.walk("docs") for f in fs if f.endswith(".html")),
   "AC8 exception reads exactly the approved copy for Columbia, Monroe, Sumter on hub and a body page; 'not yet verified' appears in no docs HTML")

# ---------------- AC9: hub ----------------
hub = parse(HUB); hh = rd(HUB)
body_links = [h for h in hub.main_links if re.fullmatch(re.escape(PATH) + r"/fl/special-districts/[^/]+/", h or "")]
ok(len(body_links) == len(set(body_links)) == N and {h.split("/")[-2] for h in body_links} == set(SLUG.values()), f"AC9 hub links each body page once: {len(body_links)} == {N}")
ht = data_rows(hub.tables[0])
ok(all(set(row[1]["text"].split(", ")) == {r["county"] for r in BODIES[next(b for b in BODIES if SLUG[b] == row[0]["links"][0][0].split("/")[-2])]} for row in ht)
   and "id=sd-filter" in hh, "AC9 hub is filterable by county: each row lists the body's counties; filter input present")
main = hh.split("<main id=main>")[1].split("</main>")[0]
BYNAME = sorted(BODIES, key=lambda b: (re.sub(r"^the\s+", "", P[b].h1.casefold()), SLUG[b]))  # displayed name, casefold, leading "The " ignored
ok(" mills" not in main and not re.search(r"\d\.\d{4}", main) and "sortable" not in main and [row[0]["text"] for row in ht] == [P[b].h1 for b in BYNAME],
   "AC9 no rates, no ranking or sort-by-rate on the hub (rows by displayed name)")
_hub_names = [row[0]["text"] for row in ht]
_ct = "The Children's Trust (Miami-Dade)"
ok("by name</caption>" in hh and _ct in _hub_names and all(_hub_names.index(_ct) > _hub_names.index(n) for n in _hub_names if n.casefold() < "children's trust")
   and all(_hub_names.index(_ct) < _hub_names.index(n) for n in _hub_names if not n.startswith("The ") and n.casefold() > "children's trust (miami-dade)")
   and "14 counties:" not in hh,
   "LAYOUT (c) FL hub: caption 'by name'; 'The Children's Trust (Miami-Dade)' sorts as 'Children's Trust' (under C); no optional county count")
_byslug = [P[b].h1 for b in sorted(BODIES, key=lambda b: SLUG[b])]
ok(_byslug != [P[b].h1 for b in BYNAME] and _hub_names != _byslug, "LAYOUT (c) FL hub order is by displayed name, not slug order (the two differ in this data)")

# ---------------- AC10/11: county pages ----------------
bad10 = []
for c in cov["counties_with_rows"]:
    p = f"docs/fl/2025/{slug(c)}-county/index.html"; h = rd(p)
    sec = parse(p).tables[-1]
    rs = [r for r in RAW if r["county"] == c]
    links = [row[0]["links"][0][0] if row[0]["links"] else None for row in data_rows(sec)]
    want = [f"{PATH}/fl/special-districts/{SLUG[r['body_id']]}/" for r in LOADED.values() if r["county"] == c and r["body_type"] == "special_district"]
    if "<h2 id=special-districts>" not in h or links != want or len(want) != len(rs): bad10.append(c)
ok(not bad10 and len(cov["counties_with_rows"]) == len({r["county"] for r in RAW}), f"AC10 each of the {len(cov['counties_with_rows'])} county pages with special rows links every special-district row to its body page: {bad10[:3]}")
ok(all(NO_ROWS in rd(f"docs/fl/2025/{slug(c)}-county/index.html") and "/fl/special-districts/" not in rd(f"docs/fl/2025/{slug(c)}-county/index.html").split("Special districts</h2>")[1].split("<p>Source:")[0]
       for c in cov["no_rows"]), f"AC10 the {len(cov['no_rows'])} no-row counties keep '{NO_ROWS}'")
# the 67 census counties (docs/fl/2025/ also holds pages for cross-county towns such as "Flagler/St. Johns"; those are not counties)
cps = [f"docs/fl/2025/{slug(c)}-county/index.html" for c in cov["counties"]]
bad11 = [p for p in cps if f"href='{PATH}/fl/history/{p.split('/')[-2]}/school/'" not in rd(p) or not os.path.isfile(f"docs/fl/history/{p.split('/')[-2]}/school/index.html")]
ok(len(cps) == cov["total"] and not bad11, f"AC11 all {len(cps)} FL county pages link their existing /fl/history/<county>-county/school/ page: {bad11[:3]}")
ok(f"href='{PATH}/fl/special-districts/'" in rd("docs/index.html"), "AC10 home page links the hub")

# ---------------- AC22-26: discovery ----------------
locs = re.findall(r"<loc>([^<]+)</loc>", rd("docs/sitemap.xml"))
want_urls = [f"{BASE}/fl/special-districts/"] + [f"{BASE}/fl/special-districts/{s}/" for s in SLUG.values()]
allp = sorted(glob.glob("docs/**/*.html", recursive=True))
ok(all(u in locs for u in want_urls) and len(locs) == len(set(locs)) == len(allp) - len({"docs/tx/index.html"} & set(allp)), f"AC22 all {len(want_urls)} new pages in sitemap.xml; sitemap locs {len(locs)} == docs pages {len(allp)} minus the /tx/ alias")
titles = {}
for p in allp: titles.setdefault(parse(p).title, []).append(p)
bad23 = []
for p in newp:
    x = parse(p); h = rd(p); head = h.split("</head>")[0]; url = f"{BASE}/{p[5:-10]}"
    lds = [json.loads(s) for s in x.ld]
    srcs = {u for u in x.main_links if u and re.match(r"https?://", u)}
    good = (GOATCOUNTER_TAG in head and f"<link rel=canonical href='{url}'>" in head and url.startswith("https://openmillage.com/") and len(titles[x.title]) == 1 and x.desc
            and len(lds) == 1 and lds[0]["@type"] == "Dataset" and set(lds[0]["isBasedOn"]) == srcs and srcs and lds[0]["url"] == url)
    if p != HUB: good = good and x.title == f"{x.h1} millage rate 2025"
    if not good: bad23.append(p)
descs = [parse(p).desc for p in newp]
ok(not bad23 and len(set(descs)) == len(descs), f"AC23 GoatCounter tag, canonical openmillage.com URL, unique title ('<Name> property tax rate 2025'), unique meta description, Dataset JSON-LD with isBasedOn == source URLs on the page: {bad23[:3]}")
bad24 = []
for b, rs in BODIES.items():
    j = json.load(open(f"docs/fl/special-districts/{SLUG[b]}/index.json"))
    if not (isinstance(j, list) and len(j) == len(rs) == len(data_rows(P[b].tables[0]))
            and all(list(x) == sources.BASE_KEYS + sources.EXTRA_KEYS and [x[k] for k in sources.BASE_KEYS] == [r[k] for k in sources.BASE_KEYS] for x, r in zip(j, rs))):
        bad24.append(b)
ok(not bad24, f"AC24 each index.json holds exactly the page's rows: 17 base keys first (name, order, value vs CSV), then the additive keys with nulls kept: {bad24[:3]}")
ok(any(x["note"] is None for b in BODIES for x in json.load(open(f"docs/fl/special-districts/{SLUG[b]}/index.json"))), "AC24 null additive keys are kept, not dropped")
EST = re.compile(r"(?i)\b(estimat\w*|approximately|about \d|projected|ranked|rank)\b")
ok(not [p for p in newp if EST.search(re.sub(r"<[^>]+>", " ", rd(p).split("<main id=main>")[1].split("</main>")[0]))] and not any(">0.0000 mills<" in rd(p) for p in newp),
   "AC25 no estimate/rank wording and no 0.0000 rate on new pages")
llms = rd("docs/llms.txt")
ok(sum(f"{BASE}/fl/special-districts/<slug>/" in l and "absent is not zero" in l.lower() for l in llms.splitlines()) == 1 and f"{BASE}/fl/special-districts/" in llms,
   "AC26 llms.txt has one line for the FL special-district page family (URL pattern + absent-is-not-zero rule)")

# ---------------- AC27: no network, deterministic, docs/ current ----------------
def snap(d):
    out = {}
    for p in sorted(glob.glob(os.path.join(d, "docs/**/*"), recursive=True)):
        if os.path.isfile(p): out[os.path.relpath(p, d)] = re.sub(rb"<lastmod>[^<]*</lastmod>", b"", open(p, "rb").read())
    return out
with tempfile.TemporaryDirectory(prefix="om-sd-a-") as t1, tempfile.TemporaryDirectory(prefix="om-sd-b-") as t2:
    r1 = build_in(t1); r2 = build_in(t2)
    s1, s2 = snap(t1), snap(t2)
    ok(r1.returncode == 0 and r2.returncode == 0, "AC27 build succeeds with network disabled (socket blocked)" + ("" if r1.returncode == 0 else f": {r1.stderr[-300:]}"))
    ok(s1 == s2 and s1, f"AC27 two builds produce byte-identical docs/ ({len(s1)} files) apart from sitemap lastmod")
    fresh = {k: v for k, v in s1.items() if k.startswith("docs/fl/special-districts/")}
    ok(fresh and all(open(k, "rb").read() == v for k, v in fresh.items()) and len(fresh) == len(glob.glob("docs/fl/special-districts/**/*.*", recursive=True)),
       f"AC27 committed docs/fl/special-districts/ equals a fresh build ({len(fresh)} files)")
src = rd("build.py") + rd("sources.py")
ok(not re.search(r"\b(urllib|requests|http\.client|socket|subprocess)\b", src), "AC27 build code imports no network or subprocess module")

# ---------------- OM-FL-COVERAGE-001 close-out ----------------
# (a) unit in the header and caption (from the data), bare numbers in the cells
bad_u = []
for b, rs in BODIES.items():
    h = rd(body_path(b)); t = h.split("<table", 1)[1].split("</table>", 1)[0]
    heads = re.findall(r"<th scope=col role=columnheader( class=num)?>([^<]*)</th>", t)
    cap = re.search(r"<caption>(.*?)</caption>", t).group(1)
    cells = re.findall(r"<td class=num role=cell>([^<]*)</td>", t)
    trs = re.findall(r"<tr role=row>.*?</tr>", t, flags=re.S)
    if not (all(r["unit"] == "mills" for r in rs) and [x[1] for x in heads] == ["County", "Levy", "Rate (mills)", "Source"]
            and cap.endswith(" (mills)") and cells == [f"{float(r['rate']):.4f}" for r in rs]
            and not any(" mills" in re.sub(r"<[^>]+>", "", tr) for tr in trs)):
        bad_u.append(b)
ok(len(BODIES) and not bad_u, f"CLOSEOUT every body page ({len(BODIES)}): header 'Rate (mills)', caption ends ' (mills)', cells are the data rate .4f, no ' mills' in a row: {bad_u[:3]}")
# (b) single-note pages say "Note" / "Note: "; the multi-note hub keeps "Note N"
NOTE_P = r"<(?:p|div) class=footnote id=note-(\d+)>(?:<p>)?(Note(?: \d+)?)([: (])"
single, bad_s = [], []
for p in sorted(glob.glob("docs/fl/**/index.html", recursive=True)):
    h = rd(p)
    if p.endswith("sfwmd/index.html"): continue  # its "Note 3" is the Amendment 3 footnote, not a numbered note
    ids = re.findall(NOTE_P, h)
    if len(ids) == 1:
        single.append(p.removeprefix("docs/fl/").removesuffix("/index.html"))
        if ids[0][1] != "Note" or f"<a href='#note-{ids[0][0]}'>Note</a>" not in h.replace("<a href='#note-", "<a href='#note-") and "#note-" in h: bad_s.append(p)
    if any(re.search(r"Note 1\b", x) for x in [re.sub(r"<[^>]+>", " ", h)]) and len(ids) == 1: bad_s.append(p)
hub = rd("docs/fl/index.html")
ok(single and not bad_s and all(any(k in x for x in single) for k in ("special-districts/nwfwmd", "special-districts/sjrwmd", "calhoun", "liberty", "clay")),
   f"CLOSEOUT single-note FL pages read 'Note' / 'Note: ' (anchor ids unchanged): {single} bad {bad_s}")
ok(all(f"<a href='#note-{n}'>Note {n}</a>" in hub and f"id=note-{n}><p>Note {n} (" in hub for n in (1, 2, 3, 4)) and "<a href='#note-1'>Note</a>" not in hub, "CLOSEOUT the hub keeps Note 1 to Note 4")
# (c) each note paragraph's TACD link and sha are in one span matched by a white-space:nowrap rule; (d) css size
_cssf = rd("docs/style.css")
_nw = [m for m in re.findall(r"([^{}]*)\{white-space:nowrap\}", _cssf) if ".nw" in m.split(",")]
SPAN = r"<span class=nw><a href='[^']+' aria-label='[^']+'>source</a> <code title='[0-9a-f]{64}'>[0-9a-f]{8}</code></span>"
STATUS_C = [r["county"] for r in csv.DictReader(open("data/special/tacd_county_status_open.csv", newline="", encoding="utf-8"))]
bad_nw = [c for c in STATUS_C if not re.search(SPAN + "(?:</p>)", rd(f"docs/fl/2025/{slug(c)}-county/index.html"))]
hub_sp = re.findall(SPAN + "</p>", hub)
ok(_nw and not bad_nw and len(hub_sp) == len(STATUS_C) and not re.search(r"<td[^>]*>[^<]*<a[^>]*>source</a> <span class=nw", hub),
   f"CLOSEOUT TACD link and sha share one span.nw (matched by a white-space:nowrap rule) in {len(hub_sp)} hub notes and {len(STATUS_C)} county pages: {bad_nw}")
ok(len(_cssf.encode()) <= 5900, f"CLOSEOUT style.css {len(_cssf.encode())} bytes <= 5900")
# ---------------- AC31: docs match code ----------------
rm = rd("README.md")
ok(all(s in rm for s in ("/fl/special-districts/", H1_FILE, "python3 tests/test_fl_special_bodies.py", "FL_SD_COPY")), "AC31 README describes the pages, the h1 override file, the copy block and the test command")
print("FAILURES", len(FAIL)); sys.exit(1 if FAIL else 0)
