#!/usr/bin/env python3
"""Static build: data/ (pinned by data/SOURCES.lock) -> docs/ (GitHub Pages). Per-county pages, JSON API, sitemap, llms.txt."""
import json, os, re, html, datetime
from analytics import GOATCOUNTER_TAG
from sources import COMBINED, load_rows, coverage, coverage_sentence, EXTRA_KEYS
BASE = os.environ.get("SITE_BASE", "https://hazeydata.github.io/openmillage-site").rstrip("/")
PATH = "/" + BASE.split("/", 3)[3] if BASE.count("/") > 2 else ""
OUT = "docs"; os.makedirs(OUT, exist_ok=True)
slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
rows = load_rows()
cov = coverage(rows); COV = html.escape(coverage_sentence(cov))
NO_ROWS = "No special-district rows published yet for this county."
NYS = "not yet sourced"
by = {}
for r in rows: by.setdefault((r["state"], r["year"], r["county"]), []).append(r)
urls = [BASE + "/"]
def page(path, title, body, jsonld=None, desc=""):
    os.makedirs(os.path.dirname(os.path.join(OUT, path)) or OUT, exist_ok=True)
    ld = f'<script type="application/ld+json">{json.dumps(jsonld)}</script>' if jsonld else ""
    open(os.path.join(OUT, path), "w").write(f"<!doctype html><html lang=en><head><meta charset=utf-8><title>{html.escape(title)}</title>"
      f"<meta name=description content='{html.escape(desc, quote=True)}'><link rel=canonical href='{BASE}/{path[:-10] if path.endswith('index.html') else path}'>"
      f"<meta name=viewport content='width=device-width'>{ld}{GOATCOUNTER_TAG}</head><body><h1>{html.escape(title)}</h1>{body}"
      f"<footer><p>Official rates only, each row linked to its government source. <a href='{PATH}/llms.txt'>llms.txt</a> · <a href='{PATH}/'>All counties</a></p></footer></body></html>")
MUTED = "style='color:#666;font-size:0.85em'"
def sd_levy(r): return f"({COMBINED[r['levy_component']]})" if r['levy_component'] in COMBINED else r['levy_component']
def sd_tr(r):
    note = f"<br><small {MUTED}>{html.escape(r['note'])}</small>" if r['note'] else ""
    return (f"<tr><td>{html.escape(r['taxing_body'])}{note}</td><td>{html.escape(sd_levy(r))}</td><td style='text-align:right;white-space:nowrap'>{float(r['rate']):.4f} {r['unit']}</td>"
            f"<td style='white-space:nowrap'><a href='{html.escape(r['source_url'])}'>source</a> <code title='{r['sha256']}'>{r['sha256'][:8]}</code></td></tr>")
links = []
for (st, yr, co), rs in sorted(by.items()):
    p = f"{st.lower()}/{yr}/{slug(co)}-county/index.html"; urls.append(f"{BASE}/{p[:-10]}")
    base = [r for r in rs if r['body_type'] != 'special_district']; sds = [r for r in rs if r['body_type'] == 'special_district']
    trs = "".join(f"<tr><td>{html.escape(r['taxing_body'])}</td><td>{r['body_type']}</td><td>{r['levy_component']} ({r['levy_scope']})</td><td>{r['rate_kind']}</td>"
                  f"<td>{float(r['rate']):.4f} {r['unit']}</td><td><a href='{html.escape(r['source_url'])}'>source</a></td></tr>" for r in base)
    if co in cov['not_yet_sourced']:
        sdh = f"<p>Independent special districts: {NYS}. The official source for this county has not been checked yet; absent is not zero.</p>"
    elif co not in cov['counties']:
        sdh = ""
    elif not sds:
        sdh = f"<p>{NO_ROWS}</p>"
    else:
        sdh = "<table><tr><th>Taxing body</th><th>Levy</th><th>Rate</th><th>Source</th></tr>" + "".join(sd_tr(r) for r in sds) + "</table>"
    sdh = f"<h2 style='margin-top:2em'>Special districts</h2><p {MUTED}>{COV}</p>{sdh}" if sdh else f"<p {MUTED}>{COV}</p>"
    api = f"api/v1/{st.lower()}/{yr}/{slug(co)}.json"
    os.makedirs(os.path.dirname(f"{OUT}/{api}"), exist_ok=True); json.dump(rs, open(f"{OUT}/{api}", "w"), indent=1)
    ds = {"@context": "https://schema.org", "@type": "Dataset", "name": f"{co} County, {st} property tax millage rates {yr}",
          "description": f"Official {yr} millage rates for taxing bodies in {co} County, {st}.", "license": "https://creativecommons.org/licenses/by/4.0/",
          "temporalCoverage": yr, "url": f"{BASE}/{p[:-10]}", "dateModified": max(r['retrieved_at'] for r in rs)[:10], "creator": {"@type": "Organization", "name": "Hazey Data"}, "spatialCoverage": f"{co} County, {st}", "isBasedOn": sorted({r['source_url'] for r in rs} | {a['source_url'] for r in rs for a in r['additional_sources'] or []}),
          "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{BASE}/{api}"}]}
    srcs = sorted({(r['source_agency'], r['source_url']) for r in rs}); ret = max(r['retrieved_at'] for r in rs)[:10]
    nagg = sum(r['rate_kind'] == 'aggregate_effective' for r in rs)
    note = (f"<p><strong>Note:</strong> {nagg} row(s) marked <em>aggregate_effective</em> are not adopted rates: they are Florida DOR totals of less-than-countywide levies divided by countywide taxable value. Do not use them as any one body's millage.</p>" if nagg else "")
    meta = "<p>Source: " + "; ".join(f"{html.escape(a)} (<a href='{html.escape(u)}'>{html.escape(u)}</a>)" for a, u in srcs) + f". Retrieved {ret} (UTC).</p>"
    page(p, f"{co} County, {st} property tax rates ({yr})",
         f"<table><tr><th>Taxing body</th><th>Type</th><th>Levy</th><th>Rate kind</th><th>Rate</th><th>Source</th></tr>{trs}</table>{note}{sdh}{meta}<p>JSON: <a href='{PATH}/{api}'>{api}</a></p>", ds,
         f"Official {yr} property tax millage rates for {len(rs)} levies in {co} County, {st}, each linked to its government source. Retrieved {ret}.")
    links.append(f"<li><a href='{PATH}/{p[:-10]}'>{html.escape(co)} County, {st}</a> ({len(rs)} rates)</li>")
page("index.html", "Florida property tax millage rates 2025, each linked to its official source", f"<p>{len(rows)} official rates from Florida DOR and EDR, retrieved {max(r['retrieved_at'] for r in rows)[:10]} (UTC). {sum(r['rate_kind']=='aggregate_effective' for r in rows)} rows are aggregate_effective (DOR less-than-countywide totals), not adopted rates. {sum(r['body_type']=='special_district' for r in rows)} rows are independent special districts.</p><p>{COV}</p><p>Independent special districts {NYS} (absent is not zero): {html.escape(', '.join(cov['not_yet_sourced']))}.</p><ul>{''.join(links)}</ul>",
     {"@context": "https://schema.org", "@type": "Dataset", "name": "OpenMillage", "description": f"Official property tax millage rates for counties, school districts, municipalities and independent special districts where sourced, with source links and file hashes. {coverage_sentence(cov)} Absent is not zero: a body with no row is not yet sourced.",
      "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Hazey Data"}, "url": BASE + "/"},
     f"Official Florida 2025 property tax millage rates for counties, school districts, municipalities and independent special districts where sourced, each with its government source link and file hash. {coverage_sentence(cov)} Absent is not zero.")
today = datetime.date.today().isoformat()
open(f"{OUT}/sitemap.xml", "w").write('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    + "".join(f"<url><loc>{u}</loc><lastmod>{today}</lastmod></url>" for u in urls) + "</urlset>")
open(f"{OUT}/robots.txt", "w").write(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
open(f"{OUT}/llms.txt", "w").write("# OpenMillage\n> Official US property tax rates (millage) per taxing body, each row linked to a government source with sha256 of the source file. Pilot: Florida 2025.\n\n"
    "## Data\n- JSON per county: " + BASE + "/api/v1/<state>/<year>/<county>.json\n- Fields: state, year, county, taxing_body, body_type, body_id, nces_leaid, fips (county 5-digit or Census place 7-digit GEOID), levy_component, levy_scope, rate_kind (adopted | aggregate_effective = DOR less-than-countywide levies divided by countywide taxable value), rate, unit (mills = $ per $1,000 taxable value), source_url, sha256, retrieved_at; additive keys (null when not applicable): " + ", ".join(EXTRA_KEYS[:-1]) + ", additional_sources (list of source_agency, source_url, sha256, source_page, retrieved_at)\n- Independent special districts (body_type special_district) are published per county. " + coverage_sentence(cov) + " Not yet sourced: " + ", ".join(cov['not_yet_sourced']) + ".\n\n"
    "## Rules\n- Rates are never estimated; if a body is missing, it is not yet collected.\n- Absent is not zero: a county or special district with no row has not been sourced yet; never read a missing rate as 0.\n- Special-district rates are never summed.\n")
open(f"{OUT}/.nojekyll", "w").write("")
print(len(urls), "pages", len(rows), "rows")
