#!/usr/bin/env python3
"""NC rates (FY2021-22..FY2025-26), FL 2025 rolled-back vs adopted pages (OM-SITE-NC-ROLLBACK-001) and Texas county/city
total rates (2021-2025, OM-SITE-TX-001).
Run after build.py. Every number shown comes from a row of a pinned CSV (data/SOURCES.lock, hazeydata/openmillage)
and sits next to a link to that row's official source. Fails closed (exit 1, nothing written) on a missing input; the Texas
pins (data/tx/*) are verified against the lock before any page is written."""
import csv, datetime, html, json, os, re, shutil, struct, sys
from decimal import Decimal
import site_chrome as sc
import sources
from analytics import GOATCOUNTER_TAG

BASE = os.environ.get("SITE_BASE", "https://openmillage.com").rstrip("/")
PATH = "/" + BASE.split("/", 3)[3] if BASE.count("/") > 2 else ""
OUT = os.environ.get("OUT", "docs")
E = lambda s: html.escape(str(s), quote=True)
YEARS = [2021, 2022, 2023, 2024, 2025]
FY = {y: f"FY{y}-{str(y+1)[2:]}" for y in YEARS}
CHARTS = "assets/charts/om-2026-11-02"
# Public copy of the pinned data: this (public) repo at a fixed commit (the #18 squash-merge commit on main). Checked 200 logged out on 2026-11-02.
SITE_DATA = "https://github.com/hazeydata/openmillage-site/{}/1f1d9a3b8dea39062f91d96c0e06183202e6a805/data/{}"
F200 = "https://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0200-0299/0200/Sections/0200.065.html"
NC_SLUG, FL_SLUG = "nc/property-tax-rates", "fl/rolled-back-rate"
def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
def rows(p): return list(csv.DictReader(open(p, encoding="utf-8")))

def alt_text():
    t = open(f"{CHARTS}/alt-text.md").read()
    return {m[0]: m[1].strip() for m in re.findall(r"^## (\S+)\.png\n(.+?)(?=\n## |\Z)", t, flags=re.S | re.M)}

SORT_JS = """<script>document.querySelectorAll('table.sortable').forEach(function(t){t.querySelectorAll('th').forEach(function(h,i){var b=document.createElement('button');b.type='button';b.textContent=h.textContent;b.className='sortbtn';h.textContent='';h.appendChild(b);b.onclick=function(){var tb=t.tBodies[0],r=[].slice.call(tb.rows),d=h.getAttribute('aria-sort')==='ascending'?-1:1;r.sort(function(x,y){var a=x.cells[i].dataset.v||x.cells[i].textContent.trim(),c=y.cells[i].dataset.v||y.cells[i].textContent.trim(),na=parseFloat(a),nc=parseFloat(c);return (isNaN(na)||isNaN(nc)?a.localeCompare(c):na-nc)*d});t.querySelectorAll('th').forEach(function(o){o.removeAttribute('aria-sort')});h.setAttribute('aria-sort',d>0?'ascending':'descending');r.forEach(function(x){tb.appendChild(x)})}})})</script>"""
FILTER_JS = """<script>document.querySelectorAll('.filter input[data-g]').forEach(function(i){var g=document.getElementById(i.dataset.g);i.oninput=function(){var q=i.value.toLowerCase();[].forEach.call(g.children,function(d){var m=!q||d.dataset.q.indexOf(q)>=0;d.hidden=!m;d.open=!!q&&m})}});document.querySelectorAll('.filter input[data-t]').forEach(function(i){var t=document.getElementById(i.dataset.t);i.oninput=function(){var q=i.value.toLowerCase();[].forEach.call(t.tBodies[0].rows,function(r){r.hidden=q&&r.textContent.toLowerCase().indexOf(q)<0})}})</script>"""

def doc(path, title, desc, inner, trail, updated, canonical=None):
    url = f"{BASE}/{path[:-10]}"
    page = (f"<!doctype html><html lang=en><head><meta charset=utf-8><title>{E(title)}</title><meta name=description content='{E(desc)}'>"
            f"<link rel=canonical href='{canonical or url}'>{sc.head_extra(PATH)}{GOATCOUNTER_TAG}</head>"
            + sc.body(PATH, E(title.split(':')[0]), inner, updated=updated, trail=trail) + SORT_JS + FILTER_JS + "</html>")
    os.makedirs(os.path.dirname(f"{OUT}/{path}"), exist_ok=True); open(f"{OUT}/{path}", "w").write(page)
    return url

def updated_of(rs):
    return sources.data_updated(sources.load_rows())  # site-wide footer date, same as every other page

def figure(name, alt, cap, w, h, note=""):
    note = "".join(f"<p class=footnote>{E(l)}</p>" for l in note.split("\n") if l) if note else ""
    return (f"<figure class=chart data-chart='{name}'><div>"
            f"<img src='{PATH}/charts/{name}.png' width={w} height={h} alt='{E(alt)}'></div>"
            f"<figcaption class=muted>{cap} <a href='{PATH}/charts/{name}.svg'>SVG</a>.</figcaption>{note}</figure>")

# ---------- North Carolina ----------
def nc_load():
    data = {}
    for y in YEARS:
        prov = {p["body_id"]: p for p in rows(f"data/nc/nc-{y}.provenance.csv")}
        for i, r in enumerate(rows(f"data/nc/nc-{y}.csv"), start=2):
            r["_row"], r["_prov"] = i, prov.get(r["body_id"], {})
            data.setdefault(y, []).append(r)
    return data

def cell(r):
    if r is None: return "<td class=num data-v=''>not listed</td>"
    p = r["_prov"]; basis = p.get("unit_basis", "")
    t = f"nc-{r['year']}.csv row {r['_row']}; DOR sheet '{p.get('source_sheet','')}' cell {p.get('source_cell','')}; unit {basis}"
    return f"<td class=num data-v='{E(r['rate'])}'><a href='{E(r['source_url'])}' title='{E(t)}'>{E(r['rate'])}</a>{'' if basis=='stated' else '<sup>i</sup>'}</td>"

def change(a, b):
    if a is None or b is None or not a["rate"] or not b["rate"]: return "<td class=num data-v=''>n/a</td>"
    d = Decimal(b["rate"]) - Decimal(a["rate"])
    return f"<td class=num data-v='{d}'>{'+' if d > 0 else ''}{d}</td>"

def nc_table(cap, tid, bodies, by):
    trs = []
    for bid, name in bodies:
        rs = [by[y].get(bid) for y in YEARS]
        trs.append(f"<tr><td>{E(name)}</td>" + "".join(cell(r) for r in rs) + change(rs[0], rs[-1]) + "</tr>")
    head = "<th scope=col>Taxing body</th>" + "".join(f"<th scope=col class=num>{FY[y]}</th>" for y in YEARS) + "<th scope=col class=num>Change FY2021-22 to FY2025-26</th>"
    return sc.tablewrap(cap, f"<table class=sortable id={tid}><caption>{E(cap)}</caption><thead><tr>{head}</tr></thead><tbody>{''.join(trs)}</tbody></table>")

UNIT_P = ("<p class=callout><strong>About the unit.</strong> Every rate here is dollars per $100 of assessed value, so 0.5000 means 50 cents per $100. "
          "Only North Carolina DOR's FY2025-26 county rate PDF states that unit (\u201c(All rates per $100 valuation*)\u201d, "
          "<a href='https://www.ncdor.gov/2025-2026-county-tax-rates-finalpdf/open'>source</a>). The DOR spreadsheets the other rates come from carry no unit label, "
          "so for those rates the unit is inferred, not stated. In DOR's words from our data notes: \u201cNC DOR doesn't state a unit for this rate; we read it as per $100 based on older DOR tables\u201d "
          "(<a href='https://www.ncdor.gov/documents/reports/table67-1/open'>Table 67</a>). Rates marked <sup>i</sup> use the inferred unit.<sup><a href='#fn-unit' id=fnref-unit>1</a></sup></p>"
          "<p class=footnote id=fn-unit>1. North Carolina law caps these rates per $100 of value, so per $100 is also inferred from statute: county general rates under <a href='https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_153A/GS_153A-149.html'>G.S. 153A-149(c)</a>, city rates under <a href='https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_160A/GS_160A-209.html'>G.S. 160A-209(d)</a>, city service districts under <a href='https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_160A/GS_160A-542.html'>G.S. 160A-542(c)</a> and county service districts under <a href='https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_153A/GS_153A-307.html'>G.S. 153A-307</a>. <a href='#fnref-unit'>Back</a></p>")
FIRE_P = "<p><strong>Rural fire districts: not collected yet.</strong> This page shows county and city rates only. Fire, rescue and other special-district rates aren't on it.</p>"

# From the footnote of dataviz nc-rates-fell.py / .svg (mathtext escapes removed); source line repointed to the public
# openmillage-site copy (the image still names the private repo until dataviz re-renders)
FELL_NOTE = ("Source: hazeydata/openmillage-site data/nc/nc-2021.csv and data/nc/nc-2025.csv (body_type = county, one row per county; North Carolina Department of Revenue).\n"
 "Unit basis: per $100 is stated by the source for FY2025-26 only; for FY2021-22 it is inferred (see page note).\n"
 "All 100 counties present in both years; none missing. 81 fell, 9 rose, 10 unchanged.\n"
 "Rate drops often follow a county revaluation (rates fall when values are reassessed); revaluation years are not recorded in these files, so they are not marked.")

RATIO = re.compile(r"ratio/appraisal county ([A-Za-z .'-]+?)\s*$")
def muni_list(data, c):
    """(body_id, display name) for one county's towns, sorted by name then body_id (stable across builds).
    A name shared by more than one row gets '(in <county>)' only when the DOR row's own label names its
    ratio/appraisal county (provenance source_label, latest year that has it); otherwise no label."""
    name, where = {}, {}
    for y in YEARS:  # later years overwrite, so the latest name/label wins
        for r in data[y]:
            if r["body_type"] == "municipal" and r["county"] == c:
                name[r["body_id"]] = r["taxing_body"]
                m = RATIO.search(r["_prov"].get("source_label", ""))
                if m: where[r["body_id"]] = m[1]
    count = {}
    for n in name.values(): count[n] = count.get(n, 0) + 1
    out = [(b, f"{n} (in {where[b]})" if count[n] > 1 and b in where else n) for b, n in name.items()]
    return sorted(out, key=lambda x: (name[x[0]], x[0]))

def nc_updated(data):
    """Footer for NC pages: latest NC DOR retrieval (not the site-wide Florida one), as an America/New_York date."""
    from zoneinfo import ZoneInfo
    allr = [r for y in YEARS for r in data[y]]
    lat = max(r["retrieved_at"] for r in allr)
    # Ties on the latest retrieval: link the newest fiscal year (FY2025-26), then the smallest URL, for a stable choice.
    url = min((-y, r["source_url"]) for y in YEARS for r in data[y] if r["retrieved_at"] == lat)[1]
    d = datetime.datetime.fromisoformat(lat.replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York")).date()
    return d, url, "latest NC DOR retrieval for these pages"

def cents(d): return f"{'+' if d > 0 else '−' if d < 0 else ''}{abs(d) * 100:.1f}"

def nc_pages(alts):
    data = nc_load()
    by = {y: {r["body_id"]: r for r in data[y]} for y in YEARS}
    upd = nc_updated(data)
    counties = sorted({r["county"] for r in data[2025] if r["body_type"] == "county" and r["county"]})
    urls, cty_trs = [], []
    up = dn = same = 0
    for c in counties:
        cid = next(r["body_id"] for r in data[2025] if r["body_type"] == "county" and r["county"] == c)
        a, b = by[2021].get(cid), by[2025].get(cid)
        if a and b:
            d = Decimal(b["rate"]) - Decimal(a["rate"]); up += d > 0; dn += d < 0; same += d == 0
        munis = muni_list(data, c)
        cur = b or a
        lead = (f"<p class=lead>{E(c)} County's general property tax rate is <strong>{E(b['rate'])} per $100</strong> of assessed value in FY2025-26, "
                f"{'up' if d > 0 else 'down' if d < 0 else 'unchanged'} from {E(a['rate'])} in FY2021-22"
                + (f" ({'+' if d>0 else ''}{d})" if d else "") + f". Cities and towns add their own rate on top for property inside their limits.</p>") if a and b else ""
        inner = (lead + UNIT_P
                 + "<h2>County rate</h2>" + nc_table(f"{c} County rate, per $100 of value", "t-county", [(cid, f"{c} County")], by)
                 + (f"<h2>City and town rates in {E(c)} County</h2>"
                    + nc_table(f"City and town rates in {c} County, per $100 of value", "t-muni", munis, by) if munis else "")
                 + FIRE_P
                 + "<p class=muted>Each rate links to the DOR spreadsheet for its year; hover for the exact row and cell. "
                   "\u201cnot listed\u201d means DOR's sheet for that year has no row for that body. A town in two counties shows once per county portion.</p>"
                 + f"<p><a href='{PATH}/{NC_SLUG}/'>All 100 North Carolina counties</a></p>")
        p = f"nc/{slug(c)}-county/index.html"
        urls.append(doc(p, f"{c} County NC property tax rate, FY2021-22 to FY2025-26",
                        f"{c} County, North Carolina property tax rates per $100 of value for the county and its cities, FY2021-22 to FY2025-26, each linked to NC DOR.",
                        inner, [("North Carolina", f"{PATH}/{NC_SLUG}/"), (f"{c} County", None)], upd))
        cty_trs.append((c, cid))
    moves = []
    for c, cid in cty_trs:
        a, b = by[2021].get(cid), by[2025].get(cid)
        if a and b: moves.append((Decimal(b["rate"]) - Decimal(a["rate"]), c))
    rise = sorted([m for m in moves if m[0] > 0], key=lambda m: (-m[0], m[1]))[:3]
    fall = sorted([m for m in moves if m[0] < 0], key=lambda m: (m[0], m[1]))[:3]
    lst = lambda ms: sc.name_list([f"{c} ({cents(d)} cents)" for d, c in ms])
    keys_rose = (f"<p class=keynums><strong>In numbers:</strong> {up} counties raised their rate and {same} kept it the same. "
                 f"Biggest rises per $100: {lst(rise)}.</p>")
    keys_fell = (f"<p class=keynums><strong>In numbers:</strong> {dn} counties lowered their rate. Biggest drops per $100: {lst(fall)}.</p>")
    hub_tbl = nc_table("County general rates, per $100 of value", "t-nc", [(cid, f"{c} County") for c, cid in cty_trs], by)
    hub_tbl = hub_tbl.replace("<td>", "<td>", 1)
    for c, cid in cty_trs:
        hub_tbl = hub_tbl.replace(f"<td>{E(c)} County</td>", f"<td><a href='{PATH}/nc/{slug(c)}-county/'>{E(c)} County</a></td>", 1)
    inner = (f"<p class=lead>Between FY2021-22 and FY2025-26, {dn} of North Carolina's 100 counties lowered their general property tax rate, {up} raised it and {same} kept it the same. "
             "Rates below are per $100 of assessed value, straight from NC Department of Revenue spreadsheets.</p>"
             + UNIT_P + FIRE_P
             + figure("nc-rates-rose-flat", alts["nc-rates-rose-flat"], "Counties whose general rate rose or held, FY2021-22 vs FY2025-26, per $100 of value. Source: NC DOR, via the table below.", 1600, 1216) + keys_rose
             + figure("nc-rates-fell", alts["nc-rates-fell"], "Counties whose general rate fell, FY2021-22 vs FY2025-26, per $100 of value. Source: NC DOR, via the table below.", 1600, 3448, note=FELL_NOTE) + keys_fell
             + "<h2>Every county, five years</h2><div class=filter><label for=f-nc>Find a county</label><input id=f-nc data-t=t-nc></div>" + hub_tbl
             + f"<p class=muted>Change is the FY2025-26 rate minus the FY2021-22 rate, both from DOR. Click a column heading to sort. Each county page also lists its cities and towns. Data files: "
               f"<a href='{SITE_DATA.format('tree', 'nc')}'>nc-2021.csv to nc-2025.csv</a>.</p>")
    urls.insert(0, doc(f"{NC_SLUG}/index.html", "North Carolina property tax rates by county, FY2021-22 to FY2025-26",
                       "What every North Carolina county charges per $100 of value and how it moved over five years, each rate linked to NC DOR.",
                       inner, [("North Carolina", None)], upd))
    return urls

# ---------- Texas (OM-SITE-TX-001) ----------
TX_CHARTS = "assets/charts/om-2026-11-06"
TX_SLUG = "tx/property-tax-rates"
TX_FILES = [f"data/tx/tx-{y}{s}.csv" for y in YEARS for s in ("", ".provenance")] + ["data/tx/tx_unit_basis.csv"]
TX_DATA_URL = "https://github.com/hazeydata/openmillage-site/tree/main/data/tx"
TX_CHART_FILES = [f"tx-rates-{n}.{e}" for n in ("rose-held", "fell") for e in ("png", "svg")] + ["tx-yoy-counts.json", "tx-yoy-series.json"]
TX_SCOPE = ("county", "municipal")  # v1 pages: body_type in TX_SCOPE and levy_component == total only
UNIT_LOCATORS = ("Tex. Tax Code \u00a726.04(c)(1)-(2)", "Tex. Tax Code \u00a726.062(d)(1)", "Tex. Tax Code \u00a726.07")
TX_PRELIM_P = ("<p class=\"banner prelim\"><strong>2025 is preliminary</strong> (Texas Comptroller Working version). "
               "A Working or Final label on the source does not clear this flag.</p>")
TX_UNIT_P = ("<p class=callout><strong>About the unit.</strong> Every rate here is dollars per $100 of taxable value, so 0.5000 means 50 cents per $100. "
             "Texas Tax Code states that unit: \u201cdollars per $100 of taxable value\u201d (<a href='https://statutes.capitol.texas.gov/Docs/TX/htm/TX.26.htm'>Tex. Tax Code \u00a726.04(c)</a>), "
             "\u201cTotal tax rate (per $100 of value)\u201d (<a href='https://statutes.capitol.texas.gov/Docs/TX/htm/TX.26.htm'>\u00a726.062(d)(1)</a>), "
             "and for non-ISD bodies \u201cper $100 valuation\u201d (<a href='https://statutes.capitol.texas.gov/Docs/TX/htm/TX.26.htm'>\u00a726.07</a>). "
             "Unit basis: <code>statutory_per_100</code>.</p>")
TX_COVER_P = ("<p><strong>School districts and special districts: in the data, not on these pages yet.</strong> This page shows county and city rates only. "
              "School-district and special-district rates are in the pinned Texas data files but are not listed here yet.</p>")
TX_LEGEND_P = ("<p class=muted>Each rate links to the Comptroller source for its year; hover for the data file and row. \u201cnot reported\u201d means the pinned file has an empty rate "
               "for that body and year. \u201cnot listed\u201d means that year\u2019s file has no row for that body.</p>")
TX_FELL_NOTE = ("Source: hazeydata/openmillage-site data/tx/tx-2021.csv and data/tx/tx-2025.csv (body_type = county, levy_component = total, one row per county; Texas Comptroller).\n"
                "Unit basis: statutory_per_100 (Tex. Tax Code \u00a726.04(c), \u00a726.062(d)(1), \u00a726.07).\n"
                "{compared} of {total} counties compared; {excl}. {dn} fell, {up} rose, {same} unchanged.\n"
                "2025 rates are preliminary (Comptroller Working version).")
NUMWORD = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five"}

def tx_load():
    """Verify every data/tx/* file against data/SOURCES.lock (listed, hazeydata/openmillage, 40-hex commit, sha256) and only then
    read it. Raises sources.DataError on any gap; nothing is written by this function. Rates are read from these files only."""
    lock = {f["path"]: f for f in json.load(open(sources.LOCK))["files"]}
    miss = [p for p in TX_FILES if p not in lock]
    if miss: raise sources.DataError(f"Texas pins missing from {sources.LOCK}: {miss}")
    for p in TX_FILES:
        f = lock[p]
        if f.get("repo") != "hazeydata/openmillage" or not re.fullmatch(r"[0-9a-f]{40}", f.get("commit", "")) or not f.get("source_path"):
            raise sources.DataError(f"Texas lock entry incomplete: {p}")
        if not os.path.isfile(p): raise sources.DataError(f"Texas pinned file missing on disk: {p}")
        got = sources.hashlib.sha256(open(p, "rb").read()).hexdigest()
        if got != f["sha256"]: raise sources.DataError(f"sha256 mismatch for {p}: lock {f['sha256']} file {got}")
    basis = rows("data/tx/tx_unit_basis.csv")
    for bt in TX_SCOPE:
        for loc in UNIT_LOCATORS:
            if not any(b["basis"] == "statutory_per_100" and b["body_type"] == bt and b["locator"] == loc for b in basis):
                raise sources.DataError(f"tx_unit_basis.csv lacks statutory_per_100 / {bt} / {loc}")
    data = {}
    for y in YEARS:
        prov = {(p["body_id"], p["levy_component"]): p for p in rows(f"data/tx/tx-{y}.provenance.csv")}
        data[y] = []
        for i, r in enumerate(rows(f"data/tx/tx-{y}.csv"), start=2):
            if r["body_type"] in TX_SCOPE and r["levy_component"] == "total":
                r["_row"], r["_prov"] = i, prov.get((r["body_id"], "total"), {})
                if r["unit"] != "per_100_valuation" or r["year"] != str(y): raise sources.DataError(f"unexpected unit/year in tx-{y}.csv row {i}")
                data[y].append(r)
    return data

def tx_stats(data):
    """County YoY (rose/fell/unchanged) from county totals with a non-empty rate in both 2021 and 2025; checked against the staged chart counts."""
    by = {y: {r["body_id"]: r for r in data[y] if r["body_type"] == "county"} for y in YEARS}
    counties = sorted(((r["county"], bid) for bid, r in by[2025].items()), key=lambda x: (x[0], x[1]))
    moves, excl = [], []
    for c, bid in counties:
        a, b = by[2021].get(bid), by[2025].get(bid)
        if a and b and a["rate"] and b["rate"]: moves.append((Decimal(b["rate"]) - Decimal(a["rate"]), c, bid))
        else: excl.append((c, bid, a, b))
    st = {"by": by, "counties": counties, "moves": moves, "excl": excl, "total": len(counties),
          "up": sum(m[0] > 0 for m in moves), "dn": sum(m[0] < 0 for m in moves), "same": sum(m[0] == 0 for m in moves)}
    staged = json.load(open(f"{TX_CHARTS}/tx-yoy-counts.json"))
    want = (staged["rose"], staged["fell"], staged["unchanged"], staged["excluded_null_pairs"], staged["compared"])
    got = (st["up"], st["dn"], st["same"], len(excl), len(moves))
    if want != got: raise sources.DataError(f"YoY counts recomputed from pinned CSVs {got} disagree with staged chart counts {want} (rose, fell, unchanged, excluded, compared)")
    return st

def tx_updated(data):
    from zoneinfo import ZoneInfo
    lat = max(r["retrieved_at"] for y in YEARS for r in data[y])
    url = min((-y, r["source_url"]) for y in YEARS for r in data[y] if r["retrieved_at"] == lat)[1]
    d = datetime.datetime.fromisoformat(lat.replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York")).date()
    return d, url, "latest Texas Comptroller retrieval for these pages"

def tx_cell(r, y):
    if r is None: return "<td class=num data-v=''>not listed</td>"
    p = r["_prov"]
    t = f"data/tx/tx-{y}.csv row {r['_row']}" + (f"; Comptroller sheet '{p.get('source_sheet','')}' cell {p.get('source_cell','')}" if p.get("source_cell") else "")
    if not r["rate"]: return f"<td class=num data-v='' title='{E(t)}'>not reported</td>"
    return f"<td class=num data-v='{E(r['rate'])}'><a href='{E(r['source_url'])}' title='{E(t)}'>{E(r['rate'])}</a></td>"

def tx_table(cap, tid, bodies, by, link=False):
    trs = []
    for bid, name in bodies:
        rs = [by[y].get(bid) for y in YEARS]
        lab = f"<a href='{PATH}/tx/{slug(name)}/'>{E(name)}</a>" if link else E(name)
        trs.append(f"<tr><td>{lab}</td>" + "".join(tx_cell(r, y) for r, y in zip(rs, YEARS)) + change(rs[0], rs[-1]) + "</tr>")
    head = "<th scope=col>Taxing body</th>" + "".join(f"<th scope=col class=num>{y}</th>" for y in YEARS) + f"<th scope=col class=num>Change {YEARS[0]} to {YEARS[-1]}</th>"
    return sc.tablewrap(cap, f"<table class=sortable id={tid}><caption>{E(cap)}</caption><thead><tr>{head}</tr></thead><tbody>{''.join(trs)}</tbody></table>")

def tx_muni_list(data, c):
    """(body_id, taxing_body from the latest year that has the body) for municipal totals whose CSV county field is c, sorted by (name, body_id)."""
    name = {}
    for y in YEARS:  # later years overwrite, so the latest name wins
        for r in data[y]:
            if r["body_type"] == "municipal" and r["county"] == c: name[r["body_id"]] = r["taxing_body"]
    return sorted(name.items(), key=lambda x: (x[1], x[0]))

def png_size(path):
    b = open(path, "rb").read(24)
    return struct.unpack(">II", b[16:24])

def tx_lead_county(c, a, b):
    ra, rb = a["rate"] if a else "", b["rate"] if b else ""
    if rb and ra:
        d = Decimal(rb) - Decimal(ra)
        mv = f"up from {E(ra)} in 2021 (+{d})" if d > 0 else f"down from {E(ra)} in 2021 (\u2212{abs(d)})" if d < 0 else f"unchanged from {E(ra)} in 2021"
        return (f"<p class=lead>{E(c)}\u2019s county total property tax rate is <strong>{E(rb)} per $100</strong> of taxable value in 2025, {mv}. "
                "Cities add their own rate on top for property inside their limits.</p>")
    if rb:
        return (f"<p class=lead>{E(c)}\u2019s county total property tax rate is <strong>{E(rb)} per $100</strong> of taxable value in 2025. "
                "Its 2021 rate is not reported in the pinned Comptroller file. Cities add their own rate on top for property inside their limits.</p>")
    was = f" (2021 was {E(ra)})" if ra else ""
    return (f"<p class=lead>{E(c)}\u2019s county total property tax rate for 2025 is <strong>not reported</strong> in the pinned Comptroller file{was}. "
            "Cities add their own rate on top for property inside their limits when listed.</p>")

def tx_pages(data, st, alts):
    by = {y: {r["body_id"]: r for r in data[y]} for y in YEARS}
    upd = tx_updated(data)
    hub_url = f"{BASE}/{TX_SLUG}/"
    urls = []
    for c, cid in st["counties"]:
        munis = tx_muni_list(data, c)
        a, b = by[2021].get(cid), by[2025].get(cid)
        inner = (TX_PRELIM_P + tx_lead_county(c, a, b) + TX_UNIT_P
                 + "<h2>County rate</h2>" + tx_table(f"{c} rate, per $100 of value", "t-county", [(cid, c)], by)
                 + (f"<h2>City rates in {E(c)}</h2>" + tx_table(f"City rates in {c}, per $100 of value", "t-muni", munis, by)
                    if munis else f"<h2>City rates in {E(c)}</h2><p>No city rates are listed for {E(c)} in the pinned files.</p>")
                 + TX_COVER_P + TX_LEGEND_P + f"<p><a href='{PATH}/{TX_SLUG}/'>All {st['total']} Texas counties</a></p>")
        urls.append(doc(f"tx/{slug(c)}/index.html", f"{c} TX property tax rate, {YEARS[0]} to {YEARS[-1]}",
                        f"{c}, Texas county and city property tax rates per $100 of taxable value, {YEARS[0]} to {YEARS[-1]}, each linked to the Texas Comptroller. 2025 is preliminary.",
                        inner, [("Texas", f"{PATH}/{TX_SLUG}/"), (c, None)], upd))
    rise = sorted([m for m in st["moves"] if m[0] > 0], key=lambda m: (-m[0], m[1]))[:3]
    fall = sorted([m for m in st["moves"] if m[0] < 0], key=lambda m: (m[0], m[1]))[:3]
    lst = lambda ms: sc.name_list([f"{c} ({cents(d)} cents)" for d, c, _ in ms])
    up, dn, same, n = st["up"], st["dn"], st["same"], st["total"]
    keys_rose = f"<p class=keynums><strong>In numbers:</strong> {up} counties raised their rate and {same} kept it the same. Biggest rises per $100: {lst(rise)}.</p>"
    keys_fell = f"<p class=keynums><strong>In numbers:</strong> {dn} counties lowered their rate. Biggest drops per $100: {lst(fall)}.</p>"
    ex = len(st["excl"])
    if all(b and not b["rate"] and a and a["rate"] for _, _, a, b in st["excl"]):
        exwhy = f"{NUMWORD.get(ex, ex)} {'county has' if ex == 1 else 'counties have'} no reported 2025 total rate, so {'it is' if ex == 1 else 'they are'} left out of that count."
        exnote = (f"{E(st['excl'][0][0])} excluded because its 2025 total rate is not reported" if ex == 1
                  else "excluded for a total rate that is not reported in 2025: " + ", ".join(c for c, *_ in st["excl"]))
    else:
        exwhy = f"{NUMWORD.get(ex, ex)} {'county is' if ex == 1 else 'counties are'} missing a total rate in 2021 or 2025 and left out of that count."
        exnote = "excluded for a missing total rate in 2021 or 2025: " + ", ".join(c for c, *_ in st["excl"])
    note = TX_FELL_NOTE.format(compared=len(st["moves"]), total=n, excl=exnote, dn=dn, up=up, same=same)
    fig = lambda k, cap, **kw: figure(f"tx-rates-{k}", alts[f"tx-rates-{k}"], cap, *png_size(f"{TX_CHARTS}/tx-rates-{k}.png"), **kw)
    hub_tbl = tx_table("County total rates, per $100 of value", "t-tx", [(cid, c) for c, cid in st["counties"]], by, link=True)
    inner = (TX_PRELIM_P
             + f"<p class=lead>Between {YEARS[0]} and {YEARS[-1]}, {dn} of Texas\u2019s {n} counties lowered their county total property tax rate, {up} raised it and {same} kept it the same. "
               f"{exwhy} Rates below are per $100 of taxable value, straight from Texas Comptroller files.</p>"
             + TX_UNIT_P + TX_COVER_P
             + fig("rose-held", "Counties whose county total rate rose or held, 2021 vs 2025, per $100 of value. Source: Texas Comptroller, via the table below.") + keys_rose
             + fig("fell", "Counties whose county total rate fell, 2021 vs 2025, per $100 of value. Source: Texas Comptroller, via the table below.", note=note) + keys_fell
             + "<h2>Every county, five years</h2><div class=filter><label for=f-tx>Find a county</label><input id=f-tx data-t=t-tx></div>" + hub_tbl
             + TX_LEGEND_P
             + f"<p class=muted>Change is the {YEARS[-1]} rate minus the {YEARS[0]} rate, both from the Comptroller. Click a column heading to sort. Each county page also lists its cities. Data files: "
               f"<a href='{TX_DATA_URL}'>tx-2021.csv to tx-2025.csv</a>.</p>")
    title = f"Texas property tax rates by county, {YEARS[0]} to {YEARS[-1]}"
    desc = ("Texas county and city property tax rates for 2021\u20132025, per $100 of taxable value, from Texas Comptroller files. 2025 is preliminary. "
            "School and special districts are in the data files but not listed on these pages yet.")
    trail = [("Texas", None)]
    hub = doc(f"{TX_SLUG}/index.html", title, desc, inner, trail, upd)
    doc("tx/index.html", title, desc, inner, trail, upd, canonical=hub)  # OQ-5: same hub at /tx/, canonical on the property-tax-rates URL
    return [hub] + urls

TX_LLMS = ("- Texas county and city total property tax rates, 2021\u20132025, dollars per $100 of taxable value (statutory_per_100), every rate linked to the Texas Comptroller. "
           "2025 is preliminary (Comptroller Working version). School-district and special-district rates are in the pinned data files but not listed on these pages yet. "
           "Hub: {hub} \u2014 one page per county: {base}/tx/<county-slug>/ (for example {base}/tx/anderson-county/).\n")

def tx_copy_charts():
    for n in TX_CHART_FILES: shutil.copyfile(f"{TX_CHARTS}/{n}", f"{OUT}/charts/{n}")

# ---------- Florida rolled-back ----------
def fl_page(alts):
    rs = rows("data/rollback/fl-2025-rollback.csv")
    for i, r in enumerate(rs, start=2): r["_row"] = i
    ok = [r for r in rs if r["rolled_back_mills"] and r["adopted_mills"] and Decimal(r["rolled_back_mills"]) > 0]
    skipped = [r for r in rs if r not in ok]
    for r in ok: r["_d"] = Decimal(r["adopted_mills"]) - Decimal(r["rolled_back_mills"])
    up = sum(r["_d"] > 0 for r in ok); dn = sum(r["_d"] < 0 for r in ok); eq = sum(r["_d"] == 0 for r in ok)
    exc = rows("data/rollback/fl-2025-rollback-exclusions.csv")
    def tr(r):
        src = f"<a href='{E(r['source_url'])}' title='{E(r['source_table'] or 'DOR')}; fl-2025-rollback.csv row {r['_row']}'>PDF p.{E(r['source_page'])}</a>"
        lv = "" if r["levy_component"] == "operating" else f" ({E(sc.label(r['levy_component']))})"
        return (f"<tr><td>{E(r['taxing_body'])}{lv}<br><span class=muted>{E(sc.label(r['body_subtype']))}</span></td>"
                f"<td class=num data-v='{r['rolled_back_mills']}'>{E(r['rolled_back_mills'])}</td><td class=num data-v='{r['adopted_mills']}'>{E(r['adopted_mills'])}</td>"
                f"<td class=num data-v='{r['_d']}'>{'+' if r['_d']>0 else ''}{r['_d']}</td><td>{src}</td></tr>")
    head = "".join(f"<th scope=col{' class=num' if n else ''}>{h}</th>" for h, n in [("Taxing body",0),("Rolled-back",1),("Adopted",1),("Difference",1),("Source",0)])
    groups = []
    for cty in sorted({r["county"] for r in ok}):
        g = sorted([r for r in ok if r["county"] == cty], key=lambda r: (r["taxing_body"], r["body_id"], r["levy_component"]))
        u = sum(r["_d"] > 0 for r in g); q = sum(r["_d"] == 0 for r in g); w = sum(r["_d"] < 0 for r in g)
        tid = "t-fl-" + slug(cty)
        groups.append(f"<details class=cgroup data-q='{E(cty.lower())} {E(' '.join(r['taxing_body'].lower() for r in g))}'><summary>{E(cty)}: {len(g)} levies, {u} above, {q} equal, {w} below</summary>"
                      + sc.tablewrap(f"Levies, {cty}", f"<table class=sortable id={tid}><caption>{E(cty)}: rolled-back vs adopted, mills</caption><thead><tr>{head}</tr></thead><tbody>{''.join(tr(r) for r in g)}</tbody></table>")
                      + "</details>")
    tbl = "<div id=fl-groups>" + "".join(groups) + "</div>"
    top = max(ok, key=lambda r: (r["_d"], r["body_id"])); low = min(ok, key=lambda r: (r["_d"], r["body_id"]))
    ds = sorted(r["_d"] for r in ok); n = len(ds); med = ds[n // 2] if n % 2 else (ds[n // 2 - 1] + ds[n // 2]) / 2
    keys = (f"<p class=keynums><strong>In numbers:</strong> {up} levies above the rolled-back rate, {eq} equal and {dn} below. "
            f"Median difference: {'+' if med > 0 else ''}{med.quantize(Decimal('0.01'))} mills. Highest: {E(top['taxing_body'])} ({E(top['county'])}), +{top['_d']} mills. "
            f"Lowest: {E(low['taxing_body'])} ({E(low['county'])}), {low['_d']} mills.</p>")
    exl = "".join(f"<li>{E(e['scope'])}: {E(re.sub(r'\s*Fact check: \S+$', '', e['reason_text']))}</li>" for e in exc)
    skl = "".join(f"<li>{E(r['taxing_body'])} ({E(r['county'])}): rolled-back {E(r['rolled_back_mills'] or 'not printed')}, adopted {E(r['adopted_mills'] or 'not printed')} (<a href='{E(r['source_url'])}'>source</a>, row {r['_row']})</li>" for r in skipped)
    inner = (f"<p class=lead>In 2025, {up} of the {len(ok)} Florida levies we could compare were adopted above their rolled-back rate, {eq} matched it and {dn} came in below it. "
             f"Under Florida law, the percent by which an adopted rate exceeds the rolled-back rate is called \u201cthe percentage increase in property taxes\u201d (<a href='{F200}'>F.S. 200.065(2)(d)</a>).</p>"
             "<h2>What the rolled-back rate is</h2><p>The rolled-back rate is the millage that would raise the same property tax revenue as last year, leaving out new construction "
             f"(<a href='{F200}'>F.S. 200.065(1)</a>). "
             "Every taxing authority computes it each summer during TRIM (Truth in Millage). Florida DOR publishes each authority's rolled-back and adopted rates after the fact "
             "(<a href='https://floridarevenue.com/property/Documents/method.pdf'>DOR method</a>). One mill is $1 per $1,000 of taxable value.</p>"
             + figure("fl-rollback", alts["fl-rollback"], f"Adopted minus rolled-back millage, {len(ok)} Florida 2025 levies. Source: Florida DOR, via the table below.", 1600, 840) + keys
             + "<h2>Every levy, by county</h2><p>Open a county to see its levies. Difference is adopted minus rolled-back, in mills.</p><div class=filter><label for=f-fl>Find a county or body</label><input id=f-fl data-g=fl-groups></div>" + tbl
             + "<p class=muted>Adopted minus rolled-back is computed from the two DOR figures in the same row. Click a column heading to sort. Data file: "
               f"<a href='{SITE_DATA.format('blob', 'rollback/fl-2025-rollback.csv')}'>fl-2025-rollback.csv</a>.</p>"
             + f"<h2>What isn't here</h2><p>These aren't in DOR's statewide rolled-back reports, so they aren't on this page:</p><ul>{exl}</ul>"
             + (f"<p>{len(skipped)} rows are in our file but can't be compared because a rate is missing or the rolled-back rate is zero:</p><ul>{skl}</ul>" if skipped else ""))
    return [doc(f"{FL_SLUG}/index.html", "Florida rolled-back rate vs adopted millage, 2025",
                "Where each Florida taxing authority's 2025 adopted millage sits against its rolled-back rate, from Florida DOR, levy by levy.",
                inner, [("Florida rolled-back rate", None)], updated_of(rs))], (len(rs), len(ok), up, eq, dn, len(skipped))

def main():
    need = [f"data/nc/nc-{y}{s}.csv" for y in YEARS for s in ("", ".provenance")] + ["data/rollback/fl-2025-rollback.csv", "data/rollback/fl-2025-rollback-exclusions.csv", f"{CHARTS}/alt-text.md",
            f"{TX_CHARTS}/alt-text.md"] + [f"{TX_CHARTS}/{n}" for n in TX_CHART_FILES]
    miss = [p for p in need if not os.path.exists(p)]
    if miss: print(f"statepages: BUILD FAILED, missing {miss}", file=sys.stderr); return 1
    try:  # verify and parse every Texas pin before anything is written
        tx_data = tx_load(); tx_st = tx_stats(tx_data)
    except sources.DataError as e: print(f"statepages: BUILD FAILED, {e}", file=sys.stderr); return 1
    alts = alt_text()
    tx_alts = {m[0]: m[1].strip() for m in re.findall(r"^## (\S+)\.png\n(.+?)(?=\n## |\Z)", open(f"{TX_CHARTS}/alt-text.md").read(), flags=re.S | re.M)}
    os.makedirs(f"{OUT}/charts", exist_ok=True)
    for n in ("nc-rates-rose-flat", "nc-rates-fell", "fl-rollback"):
        for ext in ("png", "svg"): shutil.copyfile(f"{CHARTS}/{n}.{ext}", f"{OUT}/charts/{n}.{ext}")
    tx_copy_charts()
    urls = nc_pages(alts); fl, stats = fl_page(alts); urls += fl
    tx = tx_pages(tx_data, tx_st, tx_alts)
    sm = f"{OUT}/sitemap.xml"; s = open(sm).read()
    lm = (re.findall(r"<lastmod>([^<]+)</lastmod>", s) or [""])[0]
    add = "".join(f"<url><loc>{u}</loc>" + (f"<lastmod>{lm}</lastmod>" if lm else "") + "</url>" for u in urls + tx if f"<loc>{u}</loc>" not in s)
    open(sm, "w").write(s.replace("</urlset>", add + "</urlset>"))
    lt = f"{OUT}/llms.txt"; txt = open(lt).read()
    for line in (f"- North Carolina property tax rates by county, FY2021-22 to FY2025-26: {urls[0]}\n", f"- Florida 2025 rolled-back vs adopted millage: {fl[0]}\n",
                 TX_LLMS.format(hub=tx[0], base=BASE)):
        if line not in txt:
            txt = txt[:-len(sc.FEEDBACK)] + line + sc.FEEDBACK if txt.endswith(sc.FEEDBACK) else txt + line
    open(lt, "w").write(txt)
    print(f"statepages: wrote {len(urls) + len(tx) + 1} pages ({len(tx)} Texas incl. /tx/ alias); TX rose/fell/unchanged/excluded = {tx_st['up']}/{tx_st['dn']}/{tx_st['same']}/{len(tx_st['excl'])}; FL rows/compared/above/equal/below/skipped = {stats}"); return 0

if __name__ == "__main__": sys.exit(main())
