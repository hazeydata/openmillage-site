#!/usr/bin/env python3
"""NC rates (FY2021-22..FY2025-26) and FL 2025 rolled-back vs adopted pages (OM-SITE-NC-ROLLBACK-001).
Run after build.py. Every number shown comes from a row of a pinned CSV (data/SOURCES.lock, hazeydata/openmillage@9578336)
and sits next to a link to that row's official source. Fails closed (exit 1, nothing written) on a missing input."""
import csv, datetime, html, os, re, shutil, sys
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
NC_SLUG, FL_SLUG = "nc/property-tax-rates", "fl/rolled-back-rate"
def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
def rows(p): return list(csv.DictReader(open(p, encoding="utf-8")))

def alt_text():
    t = open(f"{CHARTS}/alt-text.md").read()
    return {m[0]: m[1].strip() for m in re.findall(r"^## (\S+)\.png\n(.+?)(?=\n## |\Z)", t, flags=re.S | re.M)}

SORT_JS = """<script>document.querySelectorAll('table.sortable').forEach(function(t){t.querySelectorAll('th').forEach(function(h,i){var b=document.createElement('button');b.type='button';b.textContent=h.textContent;b.className='sortbtn';h.textContent='';h.appendChild(b);b.onclick=function(){var tb=t.tBodies[0],r=[].slice.call(tb.rows),d=h.getAttribute('aria-sort')==='ascending'?-1:1;r.sort(function(x,y){var a=x.cells[i].dataset.v||x.cells[i].textContent.trim(),c=y.cells[i].dataset.v||y.cells[i].textContent.trim(),na=parseFloat(a),nc=parseFloat(c);return (isNaN(na)||isNaN(nc)?a.localeCompare(c):na-nc)*d});t.querySelectorAll('th').forEach(function(o){o.removeAttribute('aria-sort')});h.setAttribute('aria-sort',d>0?'ascending':'descending');r.forEach(function(x){tb.appendChild(x)})}})})</script>"""
FILTER_JS = """<script>document.querySelectorAll('.filter input').forEach(function(i){var t=document.getElementById(i.dataset.t);i.oninput=function(){var q=i.value.toLowerCase();[].forEach.call(t.tBodies[0].rows,function(r){r.hidden=q&&r.textContent.toLowerCase().indexOf(q)<0})}})</script>"""

def doc(path, title, desc, inner, trail, updated):
    url = f"{BASE}/{path[:-10]}"
    page = (f"<!doctype html><html lang=en><head><meta charset=utf-8><title>{E(title)}</title><meta name=description content='{E(desc)}'>"
            f"<link rel=canonical href='{url}'>{sc.head_extra(PATH)}{GOATCOUNTER_TAG}</head>"
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
          "<p class=footnote id=fn-unit>1. North Carolina law caps these rates per $100 of value, so per $100 is also inferred from statute: city rates under <a href='https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_160A/GS_160A-209.html'>G.S. 160A-209(d)</a>, city service districts under <a href='https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_160A/GS_160A-542.html'>G.S. 160A-542(c)</a> and county service districts under <a href='https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_153A/GS_153A-307.html'>G.S. 153A-307</a>. <a href='#fnref-unit'>Back</a></p>")
FIRE_P = "<p><strong>Rural fire districts: not collected yet.</strong> This page shows county and city rates only. Fire, rescue and other special-district rates aren't on it.</p>"

# Verbatim from the footnote of dataviz nc-rates-fell.py / .svg (mathtext escapes removed)
FELL_NOTE = ("Source: hazeydata/openmillage data/nc-2021.csv and data/nc-2025.csv (body_type = county, one row per county; North Carolina Department of Revenue).\n"
 "Unit basis: per $100 is stated by the source for FY2025-26 only; for FY2021-22 it is inferred (reference/nc_unit_basis.csv).\n"
 "All 100 counties present in both years; none missing. 81 fell, 9 rose, 10 unchanged.\n"
 "Rate drops often follow a county revaluation (rates fall when values are reassessed); revaluation years are not recorded in these files, so they are not marked.")

def nc_pages(alts):
    data = nc_load()
    by = {y: {r["body_id"]: r for r in data[y]} for y in YEARS}
    upd = updated_of(data[2025])
    counties = sorted({r["county"] for r in data[2025] if r["body_type"] == "county" and r["county"]})
    urls, cty_trs = [], []
    up = dn = same = 0
    for c in counties:
        cid = next(r["body_id"] for r in data[2025] if r["body_type"] == "county" and r["county"] == c)
        a, b = by[2021].get(cid), by[2025].get(cid)
        if a and b:
            d = Decimal(b["rate"]) - Decimal(a["rate"]); up += d > 0; dn += d < 0; same += d == 0
        munis = sorted({(r["body_id"], r["taxing_body"]) for y in YEARS for r in data[y] if r["body_type"] == "municipal" and r["county"] == c}, key=lambda x: x[1])
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
    hub_tbl = nc_table("County general rates, per $100 of value", "t-nc", [(cid, f"{c} County") for c, cid in cty_trs], by)
    hub_tbl = hub_tbl.replace("<td>", "<td>", 1)
    for c, cid in cty_trs:
        hub_tbl = hub_tbl.replace(f"<td>{E(c)} County</td>", f"<td><a href='{PATH}/nc/{slug(c)}-county/'>{E(c)} County</a></td>", 1)
    inner = (f"<p class=lead>Between FY2021-22 and FY2025-26, {dn} of North Carolina's 100 counties lowered their general property tax rate, {up} raised it and {same} kept it the same. "
             "Rates below are per $100 of assessed value, straight from NC Department of Revenue spreadsheets.</p>"
             + UNIT_P + FIRE_P
             + figure("nc-rates-rose-flat", alts["nc-rates-rose-flat"], "Counties whose general rate rose or held, FY2021-22 vs FY2025-26, per $100 of value. Source: NC DOR, via the table below.", 1600, 1216)
             + figure("nc-rates-fell", alts["nc-rates-fell"], "Counties whose general rate fell, FY2021-22 vs FY2025-26, per $100 of value. Source: NC DOR, via the table below.", 1600, 3448, note=FELL_NOTE)
             + "<h2>Every county, five years</h2><div class=filter><label for=f-nc>Find a county</label><input id=f-nc data-t=t-nc></div>" + hub_tbl
             + f"<p class=muted>Change is the FY2025-26 rate minus the FY2021-22 rate, both from DOR. Click a column heading to sort. Each county page also lists its cities and towns. Data file: "
               f"<a href='https://github.com/hazeydata/openmillage/tree/9578336ec76597bb3e98542e809b987442d80b63/data'>hazeydata/openmillage data/nc-2021..2025.csv</a>.</p>")
    urls.insert(0, doc(f"{NC_SLUG}/index.html", "North Carolina property tax rates by county, FY2021-22 to FY2025-26",
                       "What every North Carolina county charges per $100 of value and how it moved over five years, each rate linked to NC DOR.",
                       inner, [("North Carolina", None)], upd))
    return urls

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
        src = f"<a href='{E(r['source_url'])}' title='fl-2025-rollback.csv row {r['_row']}'>{E(r['source_table'] or 'DOR')}, p. {E(r['source_page'])}</a>"
        pos = "above" if r["_d"] > 0 else "below" if r["_d"] < 0 else "equal"
        return (f"<tr><td>{E(r['county'])}</td><td>{E(r['taxing_body'])}</td><td>{E(sc.label(r['body_subtype']))}</td><td>{E(sc.label(r['levy_component']))}</td>"
                f"<td class=num data-v='{r['rolled_back_mills']}'>{E(r['rolled_back_mills'])}</td><td class=num data-v='{r['adopted_mills']}'>{E(r['adopted_mills'])}</td>"
                f"<td class=num data-v='{r['_d']}'>{'+' if r['_d']>0 else ''}{r['_d']}</td><td>{pos}</td><td>{src}</td></tr>")
    head = "".join(f"<th scope=col{' class=num' if n else ''}>{h}</th>" for h, n in [("County",0),("Taxing body",0),("Type",0),("Levy",0),("Rolled-back (mills)",1),("Adopted (mills)",1),("Adopted minus rolled-back",1),("Position",0),("Source",0)])
    tbl = sc.tablewrap("Florida 2025 rolled-back vs adopted", f"<table class=sortable id=t-fl><caption>Florida 2025 operating levies: rolled-back vs adopted millage</caption><thead><tr>{head}</tr></thead><tbody>{''.join(tr(r) for r in sorted(ok, key=lambda r:(r['county'], r['taxing_body'])))}</tbody></table>")
    exl = "".join(f"<li>{E(e['scope'])}: {E(e['reason_text'])}</li>" for e in exc)
    skl = "".join(f"<li>{E(r['taxing_body'])} ({E(r['county'])}): rolled-back {E(r['rolled_back_mills'] or 'not printed')}, adopted {E(r['adopted_mills'] or 'not printed')} (<a href='{E(r['source_url'])}'>source</a>, row {r['_row']})</li>" for r in skipped)
    inner = (f"<p class=lead>In 2025, {up} of the {len(ok)} Florida levies we could compare were adopted above their rolled-back rate, {eq} matched it and {dn} came in below it. "
             "Under Florida's TRIM law, adopting a rate above the rolled-back rate counts as a tax increase.</p>"
             "<h2>What the rolled-back rate is</h2><p>The rolled-back rate is the millage that would raise the same property tax revenue as last year, leaving out new construction. "
             "Every taxing authority computes it each summer during TRIM (Truth in Millage). Florida DOR publishes each authority's rolled-back and adopted rates after the fact "
             "(<a href='https://floridarevenue.com/property/Documents/method.pdf'>DOR method</a>). One mill is $1 per $1,000 of taxable value.</p>"
             + figure("fl-rollback", alts["fl-rollback"], f"Adopted minus rolled-back millage, {len(ok)} Florida 2025 levies. Source: Florida DOR, via the table below.", 1600, 900)
             + "<h2>Every levy</h2><div class=filter><label for=f-fl>Find a county or body</label><input id=f-fl data-t=t-fl></div>" + tbl
             + "<p class=muted>Adopted minus rolled-back is computed from the two DOR figures in the same row. Click a column heading to sort. Data file: "
               "<a href='https://github.com/hazeydata/openmillage/blob/9578336ec76597bb3e98542e809b987442d80b63/data/fl-2025-rollback.csv'>fl-2025-rollback.csv</a>.</p>"
             + f"<h2>What isn't here</h2><p>These aren't in DOR's statewide rolled-back reports, so they aren't on this page:</p><ul>{exl}</ul>"
             + (f"<p>{len(skipped)} rows are in our file but can't be compared because a rate is missing or the rolled-back rate is zero:</p><ul>{skl}</ul>" if skipped else ""))
    return [doc(f"{FL_SLUG}/index.html", "Florida rolled-back rate vs adopted millage, 2025",
                "Where each Florida taxing authority's 2025 adopted millage sits against its rolled-back rate, from Florida DOR, levy by levy.",
                inner, [("Florida rolled-back rate", None)], updated_of(rs))], (len(rs), len(ok), up, eq, dn, len(skipped))

def main():
    need = [f"data/nc/nc-{y}{s}.csv" for y in YEARS for s in ("", ".provenance")] + ["data/rollback/fl-2025-rollback.csv", "data/rollback/fl-2025-rollback-exclusions.csv", f"{CHARTS}/alt-text.md"]
    miss = [p for p in need if not os.path.exists(p)]
    if miss: print(f"statepages: BUILD FAILED, missing {miss}", file=sys.stderr); return 1
    alts = alt_text()
    os.makedirs(f"{OUT}/charts", exist_ok=True)
    for n in ("nc-rates-rose-flat", "nc-rates-fell", "fl-rollback"):
        for ext in ("png", "svg"): shutil.copyfile(f"{CHARTS}/{n}.{ext}", f"{OUT}/charts/{n}.{ext}")
    urls = nc_pages(alts); fl, stats = fl_page(alts); urls += fl
    sm = f"{OUT}/sitemap.xml"; s = open(sm).read()
    lm = (re.findall(r"<lastmod>([^<]+)</lastmod>", s) or [""])[0]
    add = "".join(f"<url><loc>{u}</loc>" + (f"<lastmod>{lm}</lastmod>" if lm else "") + "</url>" for u in urls if f"<loc>{u}</loc>" not in s)
    open(sm, "w").write(s.replace("</urlset>", add + "</urlset>"))
    lt = f"{OUT}/llms.txt"; txt = open(lt).read()
    lines = f"- North Carolina property tax rates by county, FY2021-22 to FY2025-26: {urls[0]}\n- Florida 2025 rolled-back vs adopted millage: {fl[0]}\n"
    if lines not in txt: open(lt, "w").write(txt[:-len(sc.FEEDBACK)] + lines + sc.FEEDBACK if txt.endswith(sc.FEEDBACK) else txt + lines)
    print(f"statepages: wrote {len(urls)} pages; FL rows/compared/above/equal/below/skipped = {stats}"); return 0

if __name__ == "__main__": sys.exit(main())
