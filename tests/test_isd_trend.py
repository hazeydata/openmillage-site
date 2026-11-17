#!/usr/bin/env python3
"""OM-SITE-SPECIAL-ISD-001 AC29: the Texas school-district (ISD) total-rate small chart (CHART-SPEC.md) and the TX rate-table / hub
layout of round 2. Three blocks:
  1. the 37 checks of the dataviz reference check.py, ported to the site's own statepages functions and the pinned data/tx files
     (prints "n/37");
  2. CHART-SPEC section 10.5 on the built pages: aria-label == <h3> text on every ISD page, no <title> in svg.isd-t, one <circle> per
     year with a non-empty total, no segment across a missing year, and the Northside (Bexar), Etoile, Cumby and Spring Creek SVGs
     rendered with standalone=True byte-equal to the golden references in tests/fixtures/isd_trend/;
  3. static layout checks on the built CSS/markup: rate cells carry class=num inside table.tx-rates and style.css keeps them on one
     line; TX hub group headings and columns (LAYOUT (c), L3); no chart on the hub (Q4).
Expected values are read from the pinned CSVs independently of the builder; synthetic edge cases live in memory only.
Run from the repo root after build.py, amend3.py and statepages.py:  python3 tests/test_isd_trend.py"""
import csv, glob, html, os, re, sys, xml.etree.ElementTree as ET
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)
from decimal import Decimal
import statepages as T  # main() is guarded by __name__, so importing builds nothing
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg); return bool(cond)
rd = lambda p: open(p, encoding="utf-8").read()
NS = "{http://www.w3.org/2000/svg}"
YEARS = (2021, 2022, 2023, 2024, 2025)
FIX = "tests/fixtures/isd_trend"
REFS = [("tx-015-915-02", "northside-isd-bexar"), ("tx-174-910-02", "etoile-isd"), ("tx-112-905-02", "cumby-collegiate-isd"),
        ("tx-117-907-02", "spring-creek-isd")]
slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
def csvrows(p): return list(csv.DictReader(open(p, newline="", encoding="utf-8")))

# ---------------- pinned data, read independently of the builder (the reference load()) ----------------
bodies, totals, cites, latest = {}, [], {}, {}
for y in YEARS:
    prov = {(p["body_id"], p["levy_component"]): p for p in csvrows(f"data/tx/tx-{y}.provenance.csv")}
    for i, r in enumerate(csvrows(f"data/tx/tx-{y}.csv"), start=2):
        if r["body_type"] != "school_district": continue
        latest[r["body_id"]] = (r["taxing_body"], r["county"])  # latest year wins (site rule: latest-year name and home county)
        if r["levy_component"] != "total": continue
        p = prov.get((r["body_id"], "total"), {})
        b = bodies.setdefault(r["body_id"], {"by_year": {}})
        b["by_year"][y] = {"rate": r["rate"], "preliminary": p.get("preliminary", "")}
        totals.append(r["rate"])
        cites[(r["body_id"], y)] = {"file": f"data/tx/tx-{y}.csv", "row": i, "rate": r["rate"]}
for bid, b in bodies.items(): b["name"], b["county"] = latest[bid]
ceil = T.ceiling(totals)
print(f"computed: {len(bodies)} ISD bodies with a total row, {len(totals)} total rows, ceiling {ceil}")

# ---------------- block 1: check.py, ported (37 checks) ----------------
res = []
for bid, sl in REFS:
    b = bodies[bid]
    svg = T.isd_trend_svg(b["name"], b["by_year"], ceil, standalone=True); p = f"{sl} (statepages standalone)"
    root = ET.fromstring(svg)
    claim = T.isd_claim(b["name"], b["by_year"])
    res.append(ok(root.get("role") == "img" and root.get("aria-label") == claim, f"{p}: role=img, aria-label == template"))
    res.append(ok(not list(root.iter(NS + "title")), f"{p}: no <title>"))
    texts = [t.text for t in root.iter(NS + "text")]
    res.append(ok(not any(b["name"] in (t or "") for t in texts), f"{p}: no visible title (district name not drawn)"))
    fs = [float(x) for x in re.findall(r"font-size:([\d.]+)px", svg)]
    vbw = float(root.get("viewBox").split()[2])
    res.append(ok(min(fs) * 360 / vbw >= 12 and min(fs) * 335 / vbw >= 12, f"{p}: min font {min(fs)} -> {min(fs)*360/vbw:.2f}px @360 desktop, {min(fs)*335/vbw:.2f}px @335 (375 viewport - 2 x 20 px redo.css padding)"))
    present = [y for y in YEARS if y in b["by_year"] and b["by_year"][y]["rate"]]
    res.append(ok(len(list(root.iter(NS + "circle"))) == len(present), f"{p}: {len(present)} points for {len(present)} years with a rate (no zero-filled points)"))
    nseg = sum(1 for a, c in zip(YEARS, YEARS[1:]) if a in present and c in present)
    res.append(ok(len([l for l in root.iter(NS + "line") if "ln" in l.get("class")]) == nseg, f"{p}: {nseg} segments, none across a gap"))
    nums = [t for t in texts if re.fullmatch(r"\d*\.\d+|\d+", t or "") and t not in {str(y) for y in YEARS} and t != "0"]
    res.append(ok(all(any(cites[(bid, y)]["rate"] == n for y in present) for n in nums), f"{p}: value labels {nums} are verbatim CSV rates"))
n = 0; widest = max(len(t) for t in totals)
for bid, b in bodies.items():
    T.isd_trend_svg(b["name"], b["by_year"], ceil); n += 1
res.append(ok(n == len(T.tx_isds()) and n > 1000, f"all {n} ISD bodies render (no ChartError)"))
res.append(ok(T.ISD_X[2025] + T.ISD_LABEL_GAP + widest * 0.6 * T.ISD_FONT <= T.ISD_W and T.ISD_X[2021] - T.ISD_LABEL_GAP - widest * 0.6 * T.ISD_FONT >= 0,
              f"widest rate string ({widest} chars at 0.6em) fits left and right of the frame"))
R = lambda v, p="false": {"rate": v, "preliminary": p}
e_all = {2023: R("")}
res.append(ok(T.isd_trend_svg("X ISD", e_all, ceil) == "" and T.isd_claim("X ISD", e_all) is None, "edge all-null (row with empty rate): no SVG, no claim"))
e1 = {2022: R("1.1")}
res.append(ok(T.isd_claim("X ISD", e1) == "X ISD’s total tax rate was 1.1 per $100 of taxable value in 2022. Years not listed: 2021 and 2023–2025.", "edge single year: claim"))
e25 = {2025: R("0.9", "true")}
s25 = T.isd_trend_svg("X ISD", e25, ceil)
res.append(ok('class="hp"' in s25 and 'text-anchor="start">0.9<' in s25 and "Years not listed: 2021–2024." in T.isd_claim("X ISD", e25)
              and "(preliminary)" in T.isd_claim("X ISD", e25), "edge 2025-only: hollow point, label right, (preliminary), 2021-2024 not listed"))
ef = {y: R("1.0", "true" if y == 2025 else "false") for y in YEARS}
res.append(ok(T.isd_claim("X ISD", ef) == "X ISD’s total tax rate was 1.0 per $100 of taxable value in both 2021 and 2025 (preliminary).", "edge flat: 'was ... in both'"))
eg = {2021: R("1.2"), 2022: R("1.1"), 2024: R("1.0"), 2025: R("1.0", "true")}
sg = T.isd_trend_svg("X ISD", eg, ceil)
res.append(ok(sg.count('class="ln') == 2 and ">not listed<" in sg and 'x="288" y="155" text-anchor="middle">preliminary' in sg, "edge middle gap 2023: 2 segments, note under 2023, preliminary stays centred"))
eg2 = {2021: R("1.2"), 2022: R("1.1"), 2023: R("1.0"), 2025: R("1.0", "true")}
res.append(ok('text-anchor="end">preliminary' in T.isd_trend_svg("X ISD", eg2, ceil), "edge 2024-only gap: preliminary right-aligned clear of the note"))
try:
    T.isd_trend_svg("X ISD", {2021: R("1"), 2023: R("")}, ceil); res.append(ok(False, "edge touching not listed / not reported runs raise"))
except T.ChartError: res.append(ok(True, "edge touching not listed / not reported runs raise ChartError"))
print(f"check.py port: {sum(res)}/{len(res)} PASS")
ok(len(res) == 37 and all(res), f"check.py port runs all 37 reference checks ({sum(res)}/{len(res)})")

# ---------------- block 2: CHART-SPEC section 10.5 on the built pages ----------------
ISDS = T.tx_isds()
ok(T.isd_ceiling(ISDS) == ceil == Decimal("0.25") * (max(Decimal(t) for t in totals if t) / Decimal("0.25")).to_integral_value(rounding="ROUND_CEILING"),
   f"shared ceiling from tx_isds() == independent ceiling ({ceil}; max total {max(Decimal(t) for t in totals if t)})")
ok(all(T.isd_chart_rows(ISDS[bid]) == bodies[bid]["by_year"] for bid in bodies) and set(bodies) <= set(ISDS),
   "chart rows (rate string, provenance preliminary flag) equal the pinned total rows for every ISD; nothing filled")
_fake = {"by_year": {y: {"total": {"rate": "1.0", "_prov": {"preliminary": "true" if y == 2023 else "false"}}} for y in (2022, 2023)}}
_fr = T.isd_chart_rows(_fake); _fs = T.isd_trend_svg("X ISD", _fr, ceil)
ok(_fr[2023]["preliminary"] == "true" and '<circle class="hp" cx="180"' in _fs and '<line class="ln pre" x1="126"' in _fs and "(preliminary)" in T.isd_claim("X ISD", _fr),
   "preliminary comes from the provenance flag, not a hard-coded 2025 (synthetic 2023 flag -> hollow 2023 point, dashed segment into it)")
for bid, sl in REFS:
    b = ISDS[bid]
    got = (T.isd_trend_svg(b["name"], T.isd_chart_rows(b), T.isd_ceiling(ISDS), standalone=True) + "\n").encode()
    ok(got == open(f"{FIX}/ref-{sl}.svg", "rb").read(), f"10.5 {sl}: standalone SVG byte-equal to the golden reference ({len(got)} bytes)")
ok(T.ISD_STYLE in rd(f"{FIX}/ref-northside-isd-bexar.svg") and T.ISD_STYLE in rd("docs/style.css") and T.ISD_DISPLAY in rd("docs/style.css"),
   "ISD_STYLE (== the reference <style>) and the .isd-t display rule are in style.css once")

SVG_RE = re.compile(r"<svg class=\"isd-t\"[^>]*>.*?</svg>", re.S)
bad = {k: [] for k in ("aria", "title", "circles", "segs", "place", "nochart", "values")}
npages = ncharts = 0
for bid, b in sorted(ISDS.items()):
    h = rd(f"docs/{b['path']}"); npages += 1
    by = bodies.get(bid, {"by_year": {}})["by_year"]
    present = [y for y in YEARS if y in by and by[y]["rate"]]
    svgs = SVG_RE.findall(h)
    if not present:
        if svgs or "<h3>" in h: bad["nochart"].append(bid)
        continue
    ncharts += 1
    if len(svgs) != 1: bad["place"].append(bid); continue
    svg = svgs[0]
    m = re.search(r"<h2>Tax rates by year</h2>(?:<p>[^<]*</p>)?<h3>([^<]*)</h3>(<svg class=\"isd-t\".*?</svg>)<div class=tablewrap", h, re.S)
    if not m or m.group(2) != svg: bad["place"].append(bid); continue
    label = re.search(r' aria-label="([^"]*)"', svg).group(1)
    if not (m.group(1) == label and html.unescape(label) == T.isd_claim(b["name"], by) and ' role="img"' in svg): bad["aria"].append(bid)
    if re.search(r"<title|<desc", svg): bad["title"].append(bid)
    if svg.count("<circle") != len(present): bad["circles"].append(bid)
    segs = [(int(a), int(c)) for a, c in re.findall(r'<line class="ln(?: pre)?" x1="(\d+)" y1="[^"]*" x2="(\d+)"', svg)]
    slot = {x: y for y, x in T.ISD_X.items()}
    want = {(T.ISD_X[a], T.ISD_X[c]) for a, c in zip(YEARS, YEARS[1:]) if a in present and c in present}
    if set(segs) != want or len(segs) != len(want) or any(slot[c] - slot[a] != 1 for a, c in segs): bad["segs"].append(bid)
    labels = re.findall(r'<text class="v"[^>]*>([^<]*)</text>', svg)
    if not labels or any(html.unescape(v) not in {by[y]["rate"] for y in present} for v in labels): bad["values"].append(bid)
print(f"computed: {npages} ISD pages, {ncharts} with a chart")
ok(npages == len(ISDS) and ncharts == len([b for b in bodies.values() if any(v["rate"] for v in b["by_year"].values())]), f"10.5 every ISD page with a total rate has one chart ({ncharts} of {npages})")
ok(not bad["place"], f"10.5 <h3>claim</h3> + svg.isd-t sit after the table <h2> (and names note), before the table: {bad['place'][:3]}")
ok(not bad["aria"], f"10.5 aria-label == <h3> text (byte-identical) == the claim from the rows, role=img, on every ISD page: {bad['aria'][:3]}")
ok(not bad["title"], f"10.5 no <title>/<desc> inside svg.isd-t: {bad['title'][:3]}")
ok(not bad["circles"], f"10.5 circle count == years with a non-empty total: {bad['circles'][:3]}")
ok(not bad["segs"], f"10.5 segments only between consecutive years that both have a rate (none across a missing year): {bad['segs'][:3]}")
ok(not bad["values"], f"value labels are that body's CSV total rate strings: {bad['values'][:3]}")
ok(not bad["nochart"], f"no <h3>, no chart on a page with no total rate: {bad['nochart'][:3]}")
cb = next(bid for bid, b in ISDS.items() if b["path"] == "tx/hopkins-county/cumby-collegiate-isd/index.html")
ok("<h3>Cumby Collegiate ISD’s total tax rate went from 1.4203 per $100 of taxable value in 2021 to 1.1739 in 2025 (preliminary).</h3>" in rd(f"docs/{ISDS[cb]['path']}"),
   "Cumby: claim uses the H1 (latest-year) name and the CHART-SPEC section 9 values")
et = rd("docs/tx/nacogdoches-county/etoile-isd/index.html")
ok("<h3>Etoile ISD’s total tax rate was 1.3066 per $100 of taxable value in 2021. Years not listed: 2022–2025.</h3>" in et and ">not listed</text>" in et, "Etoile: single year, 2022–2025 not listed (gap, never 0)")
ok(all(k.startswith("claim_") is False or "{" in v for k, v in T.TX_ISD_COPY.items()) and all(k in T.TX_ISD_COPY for k in ("claim_went", "claim_same", "claim_one", "claim_prelim", "claim_missing")),
   "claim templates live in TX_ISD_COPY (values stay generated)")

# ---------------- block 3: layout (rate nowrap, TX hub) ----------------
import site_chrome as sc
css = rd("docs/style.css")
ok(sc.TX_RATES_NOWRAP == "table.tx-rates td.num{white-space:nowrap}" and sc.TX_RATES_NOWRAP in css and "font-variant-numeric:tabular-nums" in css.split("td.num,th.num{")[1].split("}")[0],
   "style.css keeps table.tx-rates td.num on one line (nowrap) and tabular-nums on td.num")
# OM-FL-COVERAGE-001 by-eye r2 R1 adds exactly one selector list (site_chrome.FL_SD_TIGHT, the FL county special-district cells) to this rule.
mq = re.search(r"@media \(max-width:40rem\)\{table\.tx-rates th,table\.tx-rates td(?:," + re.escape(sc.FL_SD_TIGHT) + r")?\{padding:([^}]*)\}\}", css)
ok(bool(mq), f"style.css tightens table.tx-rates cell padding at <= 40rem ({mq and mq.group(1)})")
badnum = []
for bid, b in ISDS.items():
    h = rd(f"docs/{b['path']}")
    t = re.search(r"<table class=tx-rates id=t-isd>.*?</table>", h, re.S)
    if not t: badnum.append(bid); continue
    for tr in re.findall(r"<tr>(.*?)</tr>", t.group(0).split("<tbody>")[1]):
        cells = re.findall(r"<td([^>]*)>", tr)
        if any(c not in (" class=num",) and not c.startswith(" class=num ") for c in cells[-3:]) or len(cells) not in (4, 5): badnum.append(bid); break
ok(not badnum, f"every ISD year table is table.tx-rates and its M&O, I&S and total cells carry class=num: {badnum[:3]}")
txc = sorted(glob.glob("docs/tx/*-county/index.html"))
badtx = [p for p in txc if re.findall(r"<table[^>]*>", rd(p)) != [t for t in re.findall(r"<table[^>]*>", rd(p)) if "tx-rates" in t]
         or any(not re.fullmatch(r"<td class=num[ >].*", c) for t in re.findall(r"<table class='sortable tx-rates'.*?</table>", rd(p), re.S)
                for tr in re.findall(r"<tr>(.*?)</tr>", t.split("<tbody>")[1]) for c in re.findall(r"<td[^>]*>", tr)[1:])]
ok(txc and not badtx, f"every TX county-page rate table is table.tx-rates with class=num on every rate cell ({len(txc)} pages): {badtx[:3]}")
ok("tx-rates" in rd("docs/tx/property-tax-rates/index.html"), "the TX county hub table is table.tx-rates")
ok("tx-rates" not in "".join(rd(p) for p in glob.glob("docs/nc/**/*.html", recursive=True) + glob.glob("docs/fl/**/*.html", recursive=True)), "NC and FL tables are unchanged (no tx-rates class)")
hub = rd("docs/tx/school-districts/index.html")
hubcss = rd(f"{FIX}/hub-c.css").rstrip("\n")
ok(sc.TX_HUB_CSS.rstrip("\n") == hubcss and sc.TX_HUB_CSS in css and all(l.startswith("#isd-groups>details.cgroup") for l in sc.TX_HUB_CSS.split("\n")) and len(sc.TX_HUB_CSS.split("\n")) == 7, "LAYOUT (c) round 3: TX_HUB_CSS is hub-c.css (7 rules, all scoped to #isd-groups>details.cgroup) and is in style.css")
ng = len(re.findall(r"<details class=cgroup data-q='[^']*'><summary>[^<]*</summary><ul class=counties>", hub))
ok(ng > 200 and ng == hub.count("<details class=cgroup") and ng == hub.count("<summary>") and ng == len(T.tx_isd_by_county(ISDS)) and "<section class=cgroup" not in hub, f"LAYOUT (c) round 3: {ng} county groups are <details> with <summary> and ul.counties")
ok("<svg" not in hub.split("<main")[1] and "isd-t" not in hub, "Q4: no chart on the TX ISD hub")
ok(not [p for p in glob.glob(f"{FIX}/*") if re.search("/" + "workspace|/" + "home/box", rd(p))], "fixtures carry no local paths")

rm, wf = rd("README.md"), rd(".github/workflows/build.yml")
ok(all(x in rm for x in ("python3 tests/test_isd_trend.py", "tests/browser_tx_layout.py", "isd_trend_svg", "svg.isd-t", "table.tx-rates", "tests/fixtures/isd_trend/"))
   and "      - run: python3 tests/test_isd_trend.py\n" in wf, "README describes the chart, the nowrap tables and the test commands; CI runs this test")
print("FAILURES", len(FAIL)); sys.exit(1 if FAIL else 0)
