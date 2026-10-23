#!/usr/bin/env python3
"""Static build: data/ (pinned by data/SOURCES.lock) -> docs/ (GitHub Pages). Per-county pages, JSON API, sitemap, llms.txt."""
import json, os, re, html, datetime
from analytics import GOATCOUNTER_TAG
import site_chrome as sc
from sources import COMBINED, load_rows, data_updated, coverage, coverage_sentence, EXTRA_KEYS
BASE = os.environ.get("SITE_BASE", "https://openmillage.com").rstrip("/")
PATH = "/" + BASE.split("/", 3)[3] if BASE.count("/") > 2 else ""
OUT = "docs"
slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
CFG = json.load(open("amend3_config.json"))
AMEND = CFG["slug"].strip("/")
_ed = datetime.date.fromisoformat(json.load(open(CFG["ballot_json"]))["election_date"])
ELECTION = f"{_ed.strftime('%B')} {_ed.day}, {_ed.year}"
rows = load_rows()
UPDATED = data_updated(rows)
def source_type(agency):
    """Map a row's source_agency to the short type named in the homepage lead. Unknown agencies fail the build."""
    for pat, name in ((r"^Florida Department of Revenue", "Florida DOR"), (r"^Florida Office of Economic & Demographic Research", "EDR"),
                      (r"County Property Appraiser", "county property appraisers")):
        if re.search(pat, agency): return name
    raise SystemExit(f"build.py: unmapped source_agency for homepage lead: {agency!r}")
def extra_name(agency):
    m = re.match(r"^(.+? County) Board of County Commissioners \(Resolution", agency)
    if m: return f"{m.group(1)} BOCC resolution"
    raise SystemExit(f"build.py: unmapped additional source_agency for homepage lead: {agency!r}")
name_list = sc.name_list
def source_lead(rows):
    order = ["Florida DOR", "EDR", "county property appraisers"]
    prim = sorted({source_type(r["source_agency"]) for r in rows}, key=lambda t: (order.index(t) if t in order else len(order), t))
    extra = sorted({extra_name(a["source_agency"]) for r in rows for a in r.get("additional_sources") or []})
    return "from " + name_list(prim) + (f" (additional source{'s' if len(extra) > 1 else ''}: {name_list(extra)})" if extra else "")
LEAD_SRC = source_lead(rows)  # validates every source before anything is written to docs/
os.makedirs(OUT, exist_ok=True)
cov = coverage(rows); COV = html.escape(coverage_sentence(cov))
NO_ROWS = "No special-district rows published yet for this county."
NYS = "not yet sourced"
by = {}
for r in rows: by.setdefault((r["state"], r["year"], r["county"]), []).append(r)
urls = [BASE + "/"]
def page(path, title, body, jsonld=None, desc="", current=None, lead="", trail=None):
    os.makedirs(os.path.dirname(os.path.join(OUT, path)) or OUT, exist_ok=True)
    ld = f'<script type="application/ld+json">{json.dumps(jsonld)}</script>' if jsonld else ""
    open(os.path.join(OUT, path), "w").write(f"<!doctype html><html lang=en><head><meta charset=utf-8><title>{html.escape(title)}</title>"
      f"<meta name=description content='{html.escape(desc, quote=True)}'><link rel=canonical href='{BASE}/{path[:-10] if path.endswith('index.html') else path}'>"
      f"{sc.head_extra(PATH)}{ld}{GOATCOUNTER_TAG}</head>{sc.body(PATH, html.escape(title), body, current, AMEND, lead, UPDATED, trail)}</html>")
open(f"{OUT}/style.css", "w").write(sc.CSS)
GROUPS = [("County", "County", ("county",)), ("School", "School", ("school_district",)), ("Municipalities", "Municipal", ("municipality",))]  # (heading, caption word, body types)  # then Special districts (below)
COLS = [("Taxing body", 0), ("Type", 0), ("Levy", 0), ("Rate kind", 0), ("Rate", 1), ("Source", 0)]
HEAD_LEAD = "Official rates only, each row linked to its government source. "
def table(caption, cols, trs):
    th = "".join(f"<th scope=col{' class=num' if n else ''}>{c}</th>" for c, n in cols)
    return sc.tablewrap(caption, f"<table><caption>{html.escape(caption)}</caption><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>")
def src_link(r):
    return f"<a href='{html.escape(r['source_url'])}' aria-label='Source for {html.escape(sc.display_name(r['taxing_body']))}'>source</a>"
def sd_levy(r): return f"({COMBINED[r['levy_component']]})" if r['levy_component'] in COMBINED else sc.label(r['levy_component'])
def sd_tr(r):
    note = f"<br><small class=muted>{html.escape(r['note'])}</small>" if r['note'] else ""
    return (f"<tr><td>{html.escape(sc.display_name(r['taxing_body']))}{note}</td><td>{html.escape(sd_levy(r))}</td><td class=num>{float(r['rate']):.4f} {r['unit']}</td>"
            f"<td>{src_link(r)} <code title='{r['sha256']}'>{r['sha256'][:8]}</code></td></tr>")
def base_tr(r):
    agg = r['rate_kind'] == 'aggregate_effective'
    kind = "<span class=badge>Not an adopted rate</span> <a href='#agg-note' aria-label='What this means'>?</a>" if agg else html.escape(sc.label(r['rate_kind']))
    return (f"<tr{' class=agg' if agg else ''}><td>{html.escape(sc.display_name(r['taxing_body']))}</td><td>{html.escape(sc.label(r['body_type']))}</td>"
            f"<td>{html.escape(sc.label(r['levy_component']))} ({html.escape(sc.label(r['levy_scope']))})</td><td>{kind}</td>"
            f"<td class=num>{float(r['rate']):.4f} {r['unit']}</td><td>{src_link(r)}</td></tr>")
links = []
# Progressive enhancement: without JS the filter stays hidden and the full grid shows; with JS it filters the list in place.
FILTER_JS = ("<script>(function(){var w=document.getElementById('county-filter-wrap'),i=document.getElementById('county-filter'),"
  "o=document.getElementById('county-filter-count'),li=document.querySelectorAll('ul.counties li');if(!w||!i)return;w.hidden=false;"
  "function f(){var q=i.value.trim().toLowerCase(),n=0;li.forEach(function(e){var a=e.querySelector('a'),m=!q||a.textContent.toLowerCase().indexOf(q)>-1;e.hidden=!m;if(m)n++;});"
  "o.textContent=q?n+' of '+li.length+' counties':'';}i.addEventListener('input',f);f();})();</script>")
for (st, yr, co), rs in sorted(by.items()):
    p = f"{st.lower()}/{yr}/{slug(co)}-county/index.html"; urls.append(f"{BASE}/{p[:-10]}")
    base = [r for r in rs if r['body_type'] != 'special_district']; sds = [r for r in rs if r['body_type'] == 'special_district']
    groups = []
    for gname, cap, bts in GROUPS:
        g = [r for r in base if r['body_type'] in bts]
        if g: groups.append(f"<h2 id={slug(gname)}>{gname}</h2>" + table(f"{cap} rates in {co} County", COLS, "".join(base_tr(r) for r in g)))
    if co in cov['not_yet_sourced']:
        sdh = f"<p>Independent special districts: {NYS}. The official source for this county has not been checked yet; absent is not zero.</p>"
    elif co not in cov['counties']:
        sdh = ""
    elif not sds:
        sdh = f"<p>{NO_ROWS}</p>"
    else:
        sdh = table(f"Independent special districts in {co} County", [("Taxing body", 0), ("Levy", 0), ("Rate", 1), ("Source", 0)], "".join(sd_tr(r) for r in sds))
    sdh = f"<h2 id=special-districts>Special districts</h2><p class=muted>{COV}</p>{sdh}" if sdh else f"<p class=muted>{COV}</p>"
    api = f"api/v1/{st.lower()}/{yr}/{slug(co)}.json"
    os.makedirs(os.path.dirname(f"{OUT}/{api}"), exist_ok=True); json.dump(rs, open(f"{OUT}/{api}", "w"), indent=1)
    ds = {"@context": "https://schema.org", "@type": "Dataset", "name": f"{co} County, {st} property tax millage rates {yr}",
          "description": f"Official {yr} millage rates for taxing bodies in {co} County, {st}.", "license": "https://creativecommons.org/licenses/by/4.0/",
          "temporalCoverage": yr, "url": f"{BASE}/{p[:-10]}", "dateModified": max(r['retrieved_at'] for r in rs)[:10], "creator": {"@type": "Organization", "name": "Hazey Data"}, "spatialCoverage": f"{co} County, {st}", "isBasedOn": sorted({r['source_url'] for r in rs} | {a['source_url'] for r in rs for a in r['additional_sources'] or []}),
          "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{BASE}/{api}"}]}
    srcs = sorted({(r['source_agency'], r['source_url']) for r in rs}); ret = max(r['retrieved_at'] for r in rs)[:10]
    nagg = sum(r['rate_kind'] == 'aggregate_effective' for r in rs)
    note = (f"<p id=agg-note><strong>Note:</strong> {nagg} row(s) marked <em>aggregate_effective</em> are not adopted rates: they are Florida DOR totals of less-than-countywide levies divided by countywide taxable value. Do not use them as any one body's millage.</p>" if nagg else "")
    meta = "<p>Source: " + "; ".join(f"{html.escape(a)} (<a href='{html.escape(u)}' aria-label='{html.escape('Source file from ' + a)}'>source file</a>)" for a, u in srcs) + f". Retrieved {ret} (UTC).</p>"
    page(p, f"{co} County, {st} property tax rates ({yr})",
         note + "".join(groups)
         + f"{sdh}{meta}<p>JSON: <a href='{PATH}/{api}'>{api}</a></p>", ds,
         f"Official {yr} property tax millage rates for {len(rs)} levies in {co} County, {st}, each linked to its government source. Retrieved {ret}.", lead=HEAD_LEAD, trail=[("Counties", f"{PATH}/#counties"), (f"{co} County, {st}", None)])
    links.append(f"<li><a href='{PATH}/{p[:-10]}'>{html.escape(co)} County, {st}</a> <span class=muted>({len(rs)} rates)</span>"
                 + (" <span class=badge>special districts not yet sourced</span>" if co in cov['not_yet_sourced'] else "") + "</li>")
page("index.html", "Florida property tax millage rates 2025, each linked to its official source", f"<p class=lead>{len(rows)} official rates {html.escape(LEAD_SRC)}, retrieved {max(r['retrieved_at'] for r in rows)[:10]} (UTC). {sum(r['rate_kind']=='aggregate_effective' for r in rows)} rows are Florida DOR totals for districts smaller than a county, not any one body's adopted rate. {cov['sd_rows_in_csv']} rows in the Amendment 3 baseline CSV are independent special districts; {sum(r['body_type']=='special_district' for r in rows) - cov['sd_rows_in_csv']} more from county property appraisers are on county pages only.</p>"
     f"<p class=callout>Voting on Amendment 3 on {ELECTION}? <a href='{PATH}/{AMEND}/'>See the 2025 adopted millage baseline by county</a>.</p>"
     f"<h2>How to read this</h2><p>{COV}</p><p>Independent special districts {NYS} (absent is not zero): {html.escape(', '.join(cov['not_yet_sourced']))}.</p>"
     f"<h2 id=counties>Counties</h2>"
     f"<p class=filter id=county-filter-wrap hidden><label for=county-filter>Filter counties</label><input type=search id=county-filter autocomplete=off aria-describedby=county-filter-count> <span id=county-filter-count class=muted role=status aria-live=polite></span></p>"
     f"<ul class=counties>{''.join(links)}</ul>" + FILTER_JS,
     {"@context": "https://schema.org", "@type": "Dataset", "name": "OpenMillage", "description": f"Official property tax millage rates for counties, school districts, municipalities and independent special districts where sourced, with source links and file hashes. {coverage_sentence(cov)} Absent is not zero: a body with no row is not yet sourced.",
      "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Hazey Data"}, "url": BASE + "/"},
     f"Official Florida 2025 property tax millage rates for counties, school districts, municipalities and independent special districts where sourced, each with its government source link and file hash. {coverage_sentence(cov)} Absent is not zero.", current="counties", lead=HEAD_LEAD)
today = datetime.date.today().isoformat()
open(f"{OUT}/sitemap.xml", "w").write('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    + "".join(f"<url><loc>{u}</loc><lastmod>{today}</lastmod></url>" for u in urls) + "</urlset>")
open(f"{OUT}/CNAME", "w").write(BASE.split("/")[2] + "\n")  # custom domain for GitHub Pages; survives rm -rf docs
open(f"{OUT}/robots.txt", "w").write(f"User-agent: *\nAllow: /\n# Optional feedback from AI agents: see {PATH}/llms.txt (Feedback welcome)\nSitemap: {BASE}/sitemap.xml\n")
open(f"{OUT}/llms.txt", "w").write("# OpenMillage\n> Official US property tax rates (millage) per taxing body, each row linked to a government source with sha256 of the source file. Pilot: Florida 2025.\n\n"
    "## Data\n- JSON per county: " + BASE + "/api/v1/<state>/<year>/<county>.json\n- Fields: state, year, county, taxing_body, body_type, body_id, nces_leaid, fips (county 5-digit or Census place 7-digit GEOID), levy_component, levy_scope, rate_kind (adopted | aggregate_effective = DOR less-than-countywide levies divided by countywide taxable value), rate, unit (mills = $ per $1,000 taxable value), source_url, sha256, retrieved_at; additive keys (null when not applicable): " + ", ".join(EXTRA_KEYS[:-1]) + ", additional_sources (list of source_agency, source_url, sha256, source_page, retrieved_at)\n- Independent special districts (body_type special_district) are published per county. " + coverage_sentence(cov) + " Not yet sourced: " + ", ".join(cov['not_yet_sourced']) + ".\n\n"
    "## Rules\n- Rates are never estimated; if a body is missing, it is not yet collected.\n- Absent is not zero: a county or special district with no row has not been sourced yet; never read a missing rate as 0.\n- Special-district rates are never summed.\n" + sc.FEEDBACK)
open(f"{OUT}/.nojekyll", "w").write("")
print(len(urls), "pages", len(rows), "rows")
