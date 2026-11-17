#!/usr/bin/env python3
"""Static build: data/ (pinned by data/SOURCES.lock) -> docs/ (GitHub Pages). Per-county pages, JSON API, sitemap, llms.txt."""
import collections, csv, json, os, re, html, datetime
import sources
from analytics import GOATCOUNTER_TAG
import site_chrome as sc
import redo
from sources import plural, COMBINED, load_rows, data_updated, coverage, coverage_sentence, EXTRA_KEYS, FL_SD_COPY, SD_HUB, FL_HUB_COPY, FL_HUB
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
                      (r"County Property Appraiser", "county property appraisers"), (r"Water Management District", FL_HUB_COPY["lead_wmd"])):
        if re.search(pat, agency): return name
    raise SystemExit(f"build.py: unmapped source_agency for homepage lead: {agency!r}")
def extra_name(agency):
    m = re.match(r"^(.+? County) Board of County Commissioners \(Resolution", agency)
    if m: return f"{m.group(1)} BOCC resolution"
    raise SystemExit(f"build.py: unmapped additional source_agency for homepage lead: {agency!r}")
name_list = sc.name_list
def source_lead(rows):
    order = ["Florida DOR", "EDR", "county property appraisers", FL_HUB_COPY["lead_wmd"]]
    prim = sorted({source_type(r["source_agency"]) for r in rows}, key=lambda t: (order.index(t) if t in order else len(order), t))
    extra = sorted({extra_name(a["source_agency"]) for r in rows for a in r.get("additional_sources") or []})
    return "from " + name_list(prim) + (f" (additional source{'s' if len(extra) > 1 else ''}: {name_list(extra)})" if extra else "")
LEAD_SRC = source_lead(rows)  # validates every source before anything is written to docs/
try:  # FL special-district bodies + H1 picks (data/ref/fl_special_body_h1.csv): a bad pick fails here, before anything is written
    SD_BODIES = sources.fl_bodies(rows, display=sc.display_name)
except sources.DataError as e: raise SystemExit(f"build.py: BUILD FAILED, {e}")
SD_SLUG = {bid: b["slug"] for bid, b in SD_BODIES.items()}
def sd_href(bid): return f"{PATH}/{SD_HUB}/{SD_SLUG[bid]}/"
os.makedirs(OUT, exist_ok=True)
cov = coverage(rows); COV = html.escape(coverage_sentence(cov))
NO_ROWS = "No special-district rows published yet for this county."
NYS = "not yet sourced"
FL_CRUMB = (FL_HUB_COPY["crumb"], f"{PATH}/{FL_HUB}/")  # every page under /fl/ starts its breadcrumb with the Florida hub (OM-FL-COVERAGE-001 AC19)
# Dated correction of earlier published copy (historical numbers, intentionally literal; exempt from the no-literal-count test).
CORRECTION = "Correction, Oct 23, 2026: we earlier said 165 special districts across 45 counties. The numbers above match the baseline CSV."
by = {}
for r in rows: by.setdefault((r["state"], r["year"], r["county"]), []).append(r)
urls = [BASE + "/"]
def page(path, title, body, jsonld=None, desc="", current=None, lead="", trail=None, h1=None, extra_ld=()):
    os.makedirs(os.path.dirname(os.path.join(OUT, path)) or OUT, exist_ok=True)
    ld = "".join(f'<script type="application/ld+json">{json.dumps(j)}</script>' for j in ([jsonld] if jsonld else []) + list(extra_ld))
    open(os.path.join(OUT, path), "w").write(f"<!doctype html><html lang=en><head><meta charset=utf-8><title>{html.escape(title)}</title>"
      f"<meta name=description content='{html.escape(desc, quote=True)}'><link rel=canonical href='{BASE}/{path[:-10] if path.endswith('index.html') else path}'>"
      f"{sc.head_extra(PATH)}{ld}{GOATCOUNTER_TAG}</head>{sc.body(PATH, html.escape(h1 or title), body, current, AMEND, lead, UPDATED, trail)}</html>")
open(f"{OUT}/style.css", "w").write(sc.CSS); redo.copy_assets(OUT)
GROUPS = [("County", "County", ("county",)), ("School", "School", ("school_district",)), ("Municipalities", "Municipal", ("municipality",))]  # (heading, caption word, body types)  # then Special districts (below)
COLS = [("Taxing body", 0), ("Type", 0), ("Levy", 0), ("Rate kind", 0), ("Rate", 1), ("Source", 0)]
HEAD_LEAD = "Official rates only, each row linked to its government source. "
def table(caption, cols, trs):
    th = "".join(f"<th scope=col{' class=num' if n else ''}>{c}</th>" for c, n in cols)
    return sc.tablewrap(caption, f"<table><caption>{html.escape(caption)}</caption><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>")
def src_link(r):
    return f"<a href='{html.escape(r['source_url'])}' aria-label='Source for {html.escape(sc.display_name(r['taxing_body']))}'>source</a>"
def sd_levy(r): return f"({COMBINED[r['levy_component']]})" if r['levy_component'] in COMBINED else sc.label(r['levy_component'])
NOTE_LABEL = "Note {n}"  # numbered-note label, the pattern of the Amendment 3 footnotes (SFWMD "Note 3")
def note_ref(n): return f"<a href='#note-{n}'>{NOTE_LABEL.format(n=n)}</a>"
def numbered_notes(rs, taken=()):
    """{key(r): (n, text)} for rows whose note is shown as a numbered note under the table (sources.NOTE_UNDER_TABLE), in row order,
    numbered from 1 skipping numbers already used on the page (`taken`). Display only: r['note'] (the data note) is not changed."""
    out, n = {}, 0
    for r in rs:
        t = sources.NOTE_UNDER_TABLE.get((r["county"], r["body_id"]))
        if t and sources.key(r) not in out:
            n += 1
            while n in taken: n += 1
            out[sources.key(r)] = (n, t)
    return out
def notes_block(nn): return "".join(f"<p class=footnote id=note-{n}>{NOTE_LABEL.format(n=n)}: {html.escape(t)}</p>" for n, t in sorted(nn.values()))
def cell_note(r, nn):
    if sources.key(r) in nn: return f"<br><small class=muted>{note_ref(nn[sources.key(r)][0])}</small>"
    return f"<br><small class=muted>{html.escape(r['note'])}</small>" if r['note'] else ""
def reason_more(verbatim):
    """Plain reason's audit trail: the status file's recorded reason, verbatim, one click away."""
    return f"<details class=reason-more><summary>{html.escape(FL_HUB_COPY['reason_more'])}</summary><p>{html.escape(verbatim)}</p></details>"
REASONS = {c: w for c, _, w in sources.open_counties()}
def sd_tr(r, nn={}):
    note = cell_note(r, nn)
    return (f"<tr><td class=sd-body><a href='{sd_href(r['body_id'])}'>{html.escape(sc.display_name(r['taxing_body']))}</a>{note}</td><td>{html.escape(sd_levy(r))}</td><td class=num>{float(r['rate']):.4f} {r['unit']}</td>"
            f"<td>{src_link(r)} <code title='{r['sha256']}'>{r['sha256'][:8]}</code></td></tr>")
def base_tr(r):
    agg = r['rate_kind'] == 'aggregate_effective'
    kind = f"<span class=badge>{html.escape(sc.rate_kind_copy('aggregate_effective', 'badge'))}</span> <a href='#agg-note' aria-label='What this means'>?</a>" if agg else html.escape(sc.label(r['rate_kind']))
    return (f"<tr{' class=agg' if agg else ''}><td>{html.escape(sc.display_name(r['taxing_body']))}</td><td>{html.escape(sc.label(r['body_type']))}</td>"
            f"<td>{html.escape(sc.label(r['levy_component']))} ({html.escape(sc.label(r['levy_scope']))})</td><td>{kind}</td>"
            f"<td class=num>{float(r['rate']):.4f} {r['unit']}</td><td>{src_link(r)}</td></tr>")
links = []
# Progressive enhancement: without JS the filter stays hidden and the full grid shows; with JS it filters the list in place.
FILTER_JS = ("<script>(function(){var w=document.getElementById('county-filter-wrap'),i=document.getElementById('county-filter'),"
  "o=document.getElementById('county-filter-count'),li=document.querySelectorAll('ul.counties li');if(!w||!i)return;w.hidden=false;"
  "function f(){var q=i.value.trim().toLowerCase(),n=0;li.forEach(function(e){var a=e.querySelector('a'),m=!q||a.textContent.toLowerCase().indexOf(q)>-1;e.hidden=!m;if(m)n++;});"
  "o.textContent=q?n+' of '+li.length+' counties':'';}i.addEventListener('input',f);f();})();</script>")
# --- History body pages (spec items 15/17): /fl/history/<county>-county/<level>/ with index.csv and index.json beside each page.
# Data: data/history/fl_millage_history.csv, pinned in data/SOURCES.lock to hazeydata/openmillage@5ceed4f.
HIST_FILE = "data/history/fl_millage_history.csv"
HIST_PIN = next(f["commit"] for f in sources.read_lock()["files"] if f["path"] == HIST_FILE)
HIST_LEVELS = {"county": "County", "school": "School board"}
def hist_path(co, lv): return f"fl/history/{slug(co)}-county/{lv}/index.html"
HIST_FIELDS = list(next(csv.reader(open(HIST_FILE, newline="", encoding="utf-8"))))
HIST = {}
for r in csv.DictReader(open(HIST_FILE, newline="", encoding="utf-8")):
    if r["level"] in HIST_LEVELS: HIST.setdefault((r["entity_name"], r["level"]), []).append(r)
for k in HIST: HIST[k].sort(key=lambda r: (r["year"], r["component"]))
for (st, yr, co), rs in sorted(by.items()):
    p = f"{st.lower()}/{yr}/{slug(co)}-county/index.html"; urls.append(f"{BASE}/{p[:-10]}")
    base = [r for r in rs if r['body_type'] != 'special_district']; sds = [r for r in rs if r['body_type'] == 'special_district']
    groups = []
    for gname, cap, bts in GROUPS:
        g = [r for r in base if r['body_type'] in bts]
        if g: groups.append(f"<h2 id={slug(gname)}>{gname}</h2>" + table(f"{cap} rates in {co} County", COLS, "".join(base_tr(r) for r in g)))
    SDCOLS = [("Taxing body", 0), ("Levy", 0), ("Rate", 1), ("Source", 0)]
    nn = numbered_notes(sds)
    sdt = lambda: (table(f"Independent special districts in {co} County", SDCOLS, "".join(sd_tr(r, nn) for r in sds))
                   + notes_block(nn) + f"<p><a href='{PATH}/{SD_HUB}/'>{html.escape(FL_SD_COPY['county_link'])}</a></p>")
    if co in cov['not_yet_sourced']:
        sdh = (f"<p>Independent special districts: {NYS}. The official source for this county has not been checked yet; absent is not zero.</p>"
               + f"<p>{html.escape(sources.plain_reason(co, REASONS[co]))}</p>" + reason_more(REASONS[co]))
    elif co not in cov['counties']:
        sdh = ""
    elif co in cov['partial']:
        sdh = (f"<p class=partial>{html.escape(FL_HUB_COPY['partial_line'].format(reason=sources.plain_reason(co, REASONS[co])))}</p>" + reason_more(REASONS[co]) + sdt())
    elif not sds:
        sdh = f"<p>{NO_ROWS}</p>"
    else:
        sdh = sdt()
    fl_link = f"<p class=muted><a href='{PATH}/{FL_HUB}/'>{html.escape(FL_HUB_COPY['home_link'])}</a></p>"  # statewide count lives on /fl/ (by-eye r1 fix 5)
    sdh = f"<h2 id=special-districts>Special districts</h2>{fl_link}{sdh}" if sdh else fl_link
    api = f"api/v1/{st.lower()}/{yr}/{slug(co)}.json"
    os.makedirs(os.path.dirname(f"{OUT}/{api}"), exist_ok=True); json.dump(rs, open(f"{OUT}/{api}", "w"), indent=1)
    ds = {"@context": "https://schema.org", "@type": "Dataset", "name": f"{co} County, {st} property tax millage rates {yr}",
          "description": f"Official {yr} millage rates for taxing bodies in {co} County, {st}.", "license": "https://creativecommons.org/licenses/by/4.0/",
          "temporalCoverage": yr, "url": f"{BASE}/{p[:-10]}", "dateModified": max(r['retrieved_at'] for r in rs)[:10], "creator": {"@type": "Organization", "name": "Hazey Data"}, "spatialCoverage": f"{co} County, {st}", "isBasedOn": sorted({r['source_url'] for r in rs} | {a['source_url'] for r in rs for a in r['additional_sources'] or []}),
          "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{BASE}/{api}"}]}
    srcs = sorted({(r['source_agency'], r['source_url']) for r in rs}); ret = max(r['retrieved_at'] for r in rs)[:10]
    nagg = sum(r['rate_kind'] == 'aggregate_effective' for r in rs)
    note = (f"<p id=agg-note>{html.escape(sc.rate_kind_copy('aggregate_effective', 'note'))}</p>" if nagg else "")
    meta = "<p>Source: " + "; ".join(f"{html.escape(a)} (<a href='{html.escape(u)}' aria-label='{html.escape('Source file from ' + a)}'>source file</a>)" for a, u in srcs) + f". Retrieved {ret} (UTC).</p>"
    layers = []  # AC6: every layer renders a value or '— no value in data'
    for bt, who, sub in (("county", "County", "County · set by the county commission"), ("school_district", "School district", "School district · set by the school board")):
        lr = [r for r in rs if r['body_type'] == bt]
        cw = [r for r in lr if r['levy_scope'] == 'countywide' and r['rate_kind'] == 'adopted']
        if cw: layers += [(sc.display_name(r['taxing_body']), f"{sc.label(r['body_type'])} · {sc.label(r['levy_component']).lower()}, countywide", f"{float(r['rate']):.4f}", r['source_url']) for r in cw]
        elif lr: layers += [(sc.display_name(r['taxing_body']), f"{sc.label(r['body_type'])} · {sc.label(r['levy_component']).lower()}, {sc.label(r['levy_scope']).lower()}", f"{float(r['rate']):.4f}", r['source_url'], f"<span class=badge>{html.escape(sc.rate_kind_copy(r['rate_kind'], 'stack_badge'))}</span>") for r in lr]
        else: layers.append((who, sub, "— no value in data", None))
    for bt, who, sub in (("municipality", "Cities", "Municipality · set by each city commission; applies only inside that city"),
                         ("special_district", "Special district levies", "Special district · set by each district board; applies only inside that district")):
        lr = sorted((r for r in rs if r['body_type'] == bt and r['rate_kind'] == 'adopted'), key=lambda r: float(r['rate']))
        n = len({r['taxing_body'] for r in lr})
        layers.append((f"{who} ({n})" if bt == 'municipality' else f"Special district levies ({len(lr)})", sub, f"{float(lr[0]['rate']):.4f}–{float(lr[-1]['rate']):.4f}" if len(lr) > 1 else f"{float(lr[0]['rate']):.4f}", lr[0]['source_url'])
                      if lr else (who, sub, "— no value in data", None))
    hist = [(lv, f"{PATH}/{hist_path(co, lv)[:-10]}") for lv in HIST_LEVELS if (co, lv) in HIST]
    top = ((redo.chart("alachua-bar", "Bar chart: Alachua County 2025 county and school board operating rates, side by side", caption=redo.SOURCE_LINK) if co == "Alachua" else "")
           + redo.intro("The stack (county pages)") + (redo.stack(f"{co} County, {yr} adopted rates", layers) if layers else "")
           + "<p class=muted>One layer per taxing authority. Not a total: add only the layers that apply to your parcel.</p>"
           + (("<p>History since 1996: " + " · ".join(f"<a href='{h}'>{HIST_LEVELS[lv]}</a>" for lv, h in hist) + "</p>") if hist else "")
           + redo.howto() + "<h2 id=who-sets-what>Who sets what</h2>" + redo.who_lead() + "</p>")
    page(p, f"{co} County, {st} property tax rates ({yr})",
         top + note + "<details class=all><summary>See all rates</summary>" + "".join(groups) + "</details>"
         + f"{sdh}{meta}<p>JSON: <a href='{PATH}/{api}'>{api}</a></p>" + redo.getdata(f"<a href='{PATH}/{api}'>JSON</a> · <a href='{PATH}/api/v1/fl/2025/{AMEND.split('/')[-1]}-baseline.csv'>CSV (all counties)</a>"), ds,
         f"Official {yr} property tax millage rates for {plural(len(rs), 'levy', 'levies')} in {co} County, {st}, each linked to its government source. Retrieved {ret}.", lead=HEAD_LEAD, trail=[FL_CRUMB, (f"{co} County, {st}", None)])
    links.append(f"<li><a href='{PATH}/{p[:-10]}'>{html.escape(co)} County, {st}</a> <span class=muted>({plural(len(rs), 'rate')})</span>"
                 + (" <span class=badge>special districts not yet sourced</span>" if co in cov['not_yet_sourced'] else "")
                 + (f" <span class=badge>{html.escape(FL_HUB_COPY['partial_badge'])}</span>" if co in cov['partial'] else "") + "</li>")
def locator_label(loc):
    loc = loc or ""
    m = re.fullmatch(r"sheet=(\d{4})!([A-Z]{1,3}\d{1,6})", loc)
    if m: return f"Sheet {m.group(1)}, cell {m.group(2)}"
    m = re.fullmatch(r"sheet=(\d{4});column=not_in_sheet", loc)
    if m: return f"Sheet {m.group(1)} (not in sheet)"
    m = re.fullmatch(r"scanned_pdf;page=(\d{1,5})(?:;[a-z_]+)*", loc)
    if m: return f"Scanned PDF, page {m.group(1)}"
    return "Source"
def hist_tr(r):
    v = f"{sc.rate_text(r['millage'])} mills" if r["status"] == "published" and r["millage"] != "" else f"— no value in data ({html.escape(sc.label(r['null_reason'] or r['status']))})"
    return (f"<tr><td>{r['year']}</td><td>{html.escape(sc.label(r['component']))}</td><td class=num>{v}</td>"
            f"<td><a href='{html.escape(r['source_url'])}' data-locator='{html.escape(r['source_locator'] or '', quote=True)}' aria-label='Source for {r['year']} {html.escape(sc.label(r['component']))}'>{locator_label(r['source_locator'])}</a></td></tr>")
for (co, lv), hrs in sorted(HIST.items()):
    hp = hist_path(co, lv); d = os.path.dirname(f"{OUT}/{hp}"); os.makedirs(d, exist_ok=True); urls.append(f"{BASE}/{hp[:-10]}")
    with open(f"{d}/index.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HIST_FIELDS, lineterminator="\n"); w.writeheader(); w.writerows(hrs)
    json.dump({"source": {"repo": "hazeydata/openmillage", "commit": HIST_PIN, "path": "data/fl_millage_history.csv"}, "county": co, "level": lv, "rows": hrs}, open(f"{d}/index.json", "w"), indent=1)
    yrs = sorted({r["year"] for r in hrs}); line = redo.HISTORY_LINE.get(co); ch = redo.HISTORY_CHART.get(co)
    chart_html = (redo.chart(ch[0], ch[1], f" id=history-chart data-slot=history-chart data-src='{PATH}/{hp[:-10]}index.json'", redo.history_caption(redo.page_edr_url(hrs)) + f"Re-cut on openmillage@{HIST_PIN[:7]}") if ch
                  else f"<figure class=hero id=history-chart data-slot=history-chart data-src='{PATH}/{hp[:-10]}index.json'></figure>")
    other = [(l, f"{PATH}/{hist_path(co, l)[:-10]}") for l in HIST_LEVELS if l != lv and (co, l) in HIST]
    page(hp, f"{co} County, FL {HIST_LEVELS[lv].lower()} millage history, {yrs[0]}–{yrs[-1]}",
         chart_html + "<h2 id=over-time>Over time</h2>"
         + f"<p data-slot=history-line>{redo.md(redo.OVER_GENERIC)}" + (f" {redo.md(line[0])}</p><p class=foot>{redo.md(line[1])}" if line else "") + "</p>"
         + "<details class=all><summary>See all years</summary>" + table(f"{HIST_LEVELS[lv]} millage by year, {co} County", [("Year", 0), ("Component", 0), ("Millage", 1), ("Source", 0)], "".join(hist_tr(r) for r in hrs)) + "</details>"
         + "".join(f"<p>Also: <a href='{h}'>{HIST_LEVELS[l]} history</a> · <a href='{PATH}/fl/2025/{slug(co)}-county/'>{html.escape(co)} County 2025 rates</a></p>" for l, h in other)
         + redo.getdata(f"<a href='{PATH}/{hp[:-10]}index.csv'>CSV</a> · <a href='{PATH}/{hp[:-10]}index.json'>JSON</a> (openmillage@{HIST_PIN[:7]})"),
         None, f"{HIST_LEVELS[lv]} millage in {co} County, Florida, by year since {yrs[0]}, each value linked to its official source file.",
         lead=HEAD_LEAD, trail=[FL_CRUMB, (f"{co} County, FL", f"{PATH}/fl/2025/{slug(co)}-county/"), (f"History: {HIST_LEVELS[lv]}", None)])
# --- FL independent special-district body pages + hub (OM-SITE-SPECIAL-ISD-001): /fl/special-districts/<slug>/ with index.json beside each.
# Rows: every special_district row of the merged FL set (sources.fl_bodies); rates via the county-page renderer; nothing summed, ranked or estimated.
import amend3 as _a3  # footnote wording + its source citations, shared with the Amendment 3 page (data/ref/fl_special_district_footnotes.md)
SD_FOOTNOTES = {"fl-sfwmd-special_district": "Broward"}  # body_id -> amend3_config footnote_citations key whose footnote applies to that body
NYS_LIST = [x for x in sources.open_counties() if x[1] != sources.PARTIAL]  # status file rows; `partial` counties have rows and are listed separately
def nys_block():
    return (f"<p>{html.escape(FL_SD_COPY['nys_lead'])}</p><ul class=nys>"
            + "".join(f"<li>{html.escape(c)}: {html.escape(FL_SD_COPY['nys_reason'][st])}</li>" for c, st, _ in sorted(NYS_LIST)) + "</ul>"
            + (f"<p>{html.escape(FL_HUB_COPY['partial_list'].format(names=sources.join_names(cov['partial'])))}</p>" if cov['partial'] else ""))
def cov_block():
    return f"<h2 id=coverage>{html.escape(FL_SD_COPY['coverage_h2'])}</h2><p class=muted>{COV}</p>" + nys_block()
def county_href(co): return f"{PATH}/fl/2025/{slug(co)}-county/"
def body_table(caption, brs, nn={}):
    """LAYOUT (b): one <tbody> per county (rows already in sources.sd_row_order), county as <th scope=rowgroup rowspan=n> on the
    group's first row; explicit ARIA roles so the table keeps its semantics when stacked at <= 40rem (CSS table.sd-rates)."""
    groups = {}
    for r in brs: groups.setdefault(r["county"], []).append(r)
    note = lambda r: cell_note(r, nn)
    tbodies = []
    for co, g in groups.items():
        trs = []
        for i, r in enumerate(g):
            head = (f"<th scope=rowgroup rowspan={len(g)} role=rowheader><a href='{county_href(co)}'>{html.escape(co)}</a>{note(r)}</th>" if i == 0 else "")
            trs.append(f"<tr role=row>{head}<td role=cell>{html.escape(sd_levy(r))}{'' if i == 0 else note(r)}</td><td class=num role=cell>{float(r['rate']):.4f} {r['unit']}</td>"
                       f"<td class=src role=cell>{src_link(r)} <code title='{r['sha256']}'>{r['sha256'][:8]}</code></td></tr>")
        tbodies.append("<tbody role=rowgroup>" + "".join(trs) + "</tbody>")
    th = "".join(f"<th scope=col role=columnheader{' class=num' if n else ''}>{c}</th>" for c, n in [("County", 0), ("Levy", 0), ("Rate", 1), ("Source", 0)])
    return sc.tablewrap(caption, f"<table class=sd-rates role=table><caption>{html.escape(caption)}</caption><thead role=rowgroup><tr role=row>{th}</tr></thead>{''.join(tbodies)}</table>")
def footnote(key):
    fc = CFG["footnote_citations"][key]
    return (f"<p class=footnote>{NOTE_LABEL.format(n=fc['n'])}: &ldquo;{html.escape(_a3.FOOT[fc['n']])}&rdquo; Source: "
            + "; ".join(f"<a href='{html.escape(_a3.SRC[f]['url'])}'>{html.escape('DOR 2025 TACD (' + _a3.SRC[f]['county'] + ')')}</a>, {html.escape(w)}" for f, w in fc["cites"]) + ".</p>")
hub_trs = []
def hub_key(b):  # hub caption says "by name": the displayed name, case-insensitive, a leading "The " ignored; slug breaks ties
    return (re.sub(r"^the\s+", "", b["h1"].casefold()), b["slug"])
for bid, b in sorted(SD_BODIES.items(), key=lambda kv: hub_key(kv[1])):
    brs, name = b["rows"], b["h1"]
    sp = f"{SD_HUB}/{b['slug']}/index.html"; d = os.path.dirname(f"{OUT}/{sp}"); os.makedirs(d, exist_ok=True); urls.append(f"{BASE}/{sp[:-10]}")
    json.dump(brs, open(f"{d}/index.json", "w"), indent=1)
    ctys = sorted({r["county"] for r in brs}); cty_txt = sc.name_list(ctys) + (" County" if len(ctys) == 1 else " counties")
    also = [n for n in b["names"] if n != name]
    nn = numbered_notes(brs, taken={CFG["footnote_citations"][SD_FOOTNOTES[bid]]["n"]} if bid in SD_FOOTNOTES else ())
    inner = (f"<p class=lead>{html.escape(FL_SD_COPY['body_intro'].format(name=name))}</p>"
             + (f"<p>{html.escape(FL_SD_COPY['also_printed'])}: " + "; ".join(f"<q>{html.escape(n)}</q>" for n in also) + "</p>" if also else "")
             + f"<h2 id=rates>2025 rates</h2><p class=muted>{html.escape(FL_SD_COPY['rows_note'])}</p>"
             + body_table(f"{name}, 2025 rates by county", brs, nn) + notes_block(nn)
             + (footnote(SD_FOOTNOTES[bid]) if bid in SD_FOOTNOTES else "")
             + f"<p>{html.escape(FL_SD_COPY['absent_note'])}</p>" + cov_block()
             + f"<p>JSON: <a href='{PATH}/{sp[:-10]}index.json'>index.json</a> · <a href='{PATH}/{SD_HUB}/'>{html.escape(FL_SD_COPY['county_link'])}</a></p>")
    ds = {"@context": "https://schema.org", "@type": "Dataset", "name": f"{name}, Florida property tax millage rates 2025",
          "description": f"Official 2025 millage rates for {name}, an independent special district in {cty_txt}, Florida. {coverage_sentence(cov, meta=True)} Absent is not zero.",
          "license": "https://creativecommons.org/licenses/by/4.0/", "temporalCoverage": "2025", "url": f"{BASE}/{sp[:-10]}",
          "dateModified": max(r['retrieved_at'] for r in brs)[:10], "creator": {"@type": "Organization", "name": "Hazey Data"},
          "spatialCoverage": [f"{c} County, FL" for c in ctys], "isBasedOn": sorted({r['source_url'] for r in brs}),
          "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{BASE}/{sp[:-10]}index.json"}]}
    page(sp, FL_SD_COPY["body_title"].format(name=name), inner, ds,
         FL_SD_COPY["body_desc"].format(name=name, rates="rate" if len(brs) == 1 else "rates", counties=cty_txt) + " " + coverage_sentence(cov, meta=True),
         lead=HEAD_LEAD, trail=[FL_CRUMB, (FL_SD_COPY["hub_h1"], f"{PATH}/{SD_HUB}/"), (name, None)], h1=name)
    hub_trs.append(f"<tr><td><a href='{PATH}/{sp[:-10]}'>{html.escape(name)}</a></td><td>{html.escape(', '.join(ctys))}</td></tr>")
SD_FILTER_JS = ("<script>(function(){var w=document.getElementById('sd-filter-wrap'),i=document.getElementById('sd-filter'),"
  "o=document.getElementById('sd-filter-count'),tr=document.querySelectorAll('#sd-bodies tbody tr');if(!w||!i)return;w.hidden=false;"
  "function f(){var q=i.value.trim().toLowerCase(),n=0;tr.forEach(function(e){var m=!q||e.textContent.toLowerCase().indexOf(q)>-1;e.hidden=!m;if(m)n++;});"
  "o.textContent=q?n+' of '+tr.length+' districts':'';}i.addEventListener('input',f);f();})();</script>")
def hub_sources():
    by_u = {}
    for b in SD_BODIES.values():
        for r in b["rows"]: by_u.setdefault((r["source_url"], r["source_agency"]), set()).add(r["county"])
    items = sorted(((sc.name_list(sorted(cs)), a, u) for (u, a), cs in by_u.items()))
    return (f"<h2 id=sources>{html.escape(FL_SD_COPY['hub_sources'])}</h2><details class=all><summary>{html.escape(FL_SD_COPY['hub_sources_summary'])}</summary><ul>"
            + "".join(f"<li>{html.escape(c)}: {html.escape(a)} (<a href='{html.escape(u)}' aria-label='{html.escape('Source file for ' + c)}'>source file</a>)</li>" for c, a, u in items) + "</ul></details>")
hub_tbl = sc.tablewrap("Florida independent special districts", "<table id=sd-bodies><caption>Florida independent special districts with a sourced 2025 rate, by name</caption>"
                       "<thead><tr><th scope=col>Special district</th><th scope=col>Counties with a sourced row</th></tr></thead><tbody>" + "".join(hub_trs) + "</tbody></table>")
page(f"{SD_HUB}/index.html", FL_SD_COPY["hub_title"],
     f"<p class=lead>{html.escape(FL_SD_COPY['hub_intro'])}</p>"
     + f"<p class=filter id=sd-filter-wrap hidden><label for=sd-filter>{html.escape(FL_SD_COPY['hub_filter'])}</label><input type=search id=sd-filter autocomplete=off aria-describedby=sd-filter-count> <span id=sd-filter-count class=muted role=status aria-live=polite></span></p>"
     + hub_tbl + cov_block() + hub_sources() + SD_FILTER_JS,
     {"@context": "https://schema.org", "@type": "Dataset", "name": FL_SD_COPY["hub_h1"], "description": FL_SD_COPY["hub_desc"] + " " + coverage_sentence(cov, meta=True) + " Absent is not zero.",
      "license": "https://creativecommons.org/licenses/by/4.0/", "temporalCoverage": "2025", "url": f"{BASE}/{SD_HUB}/", "creator": {"@type": "Organization", "name": "Hazey Data"},
      "isBasedOn": sorted({r['source_url'] for b in SD_BODIES.values() for r in b["rows"]})},
     FL_SD_COPY["hub_desc"] + " " + coverage_sentence(cov, meta=True), lead=HEAD_LEAD, trail=[FL_CRUMB, (FL_SD_COPY["hub_h1"], None)], h1=FL_SD_COPY["hub_h1"])
urls.append(f"{BASE}/{SD_HUB}/")
def home_tail():
    """Home lead: special-district rows outside the baseline CSV, split by alt-source document kind (computed)."""
    alt = [r for r in rows if r["body_type"] == "special_district" and r["county"] in cov["alt_only"]]
    if len(alt) != sum(r['body_type'] == 'special_district' for r in rows) - cov['sd_rows_in_csv']:
        raise SystemExit("build.py: special-district rows outside the baseline CSV are not all alt-only rows")
    kinds = sources.alt_kinds(); n = collections.Counter(kinds[r["county"]] for r in alt)
    if not n["wmd"]: return f"{n['pa']} {FL_SD_COPY['home_lead_tail']}"
    return FL_HUB_COPY["home_lead_tail_split"].format(pa=n["pa"], wmd=n["wmd"])
# --- Florida hub /fl/ (OM-FL-COVERAGE-001): every FL county page + computed special-district coverage per county label. No rates, totals or ranks.
def fl_hub():
    C = FL_HUB_COPY
    labels = sorted(co for (st, yr, co) in by if st == "FL" and yr == "2025")
    # Short status cells: {reason} becomes a "Note N" link to a numbered note under the table (plain reason + the recorded reason verbatim).
    mark = "\x00reason\x00"
    st = [(co, *sources.fl_hub_status(co, cov, rows, reason=mark)) for co in labels]
    noted = [co for co, k, t in st if mark in t]
    num = {co: i + 1 for i, co in enumerate(noted)}
    cell = lambda co, t: html.escape(t).replace(mark, note_ref(num[co])) if co in num else html.escape(t)
    trs = "".join(f"<tr data-status={k}><td{'' if k == 'multi' else ' class=hub-county'}><a href='{county_href(co)}'>{html.escape(sources.display_label(co))}</a></td><td>{cell(co, t)}</td></tr>" for co, k, t in st)
    tbl = sc.tablewrap(C["table_caption"], f"<table id=fl-coverage><caption>{html.escape(C['table_caption'])}</caption><thead><tr><th scope=col>{html.escape(C['th_county'])}</th>"
                       f"<th scope=col>{html.escape(C['th_sd'])}</th></tr></thead><tbody>{trs}</tbody></table>")
    tbl += "".join(f"<div class=footnote id=note-{num[co]}><p>{NOTE_LABEL.format(n=num[co])} ({html.escape(co)}): {html.escape(sources.plain_reason(co, REASONS[co]))}</p>{reason_more(REASONS[co])}</div>" for co in noted)
    S = C["sections"]
    secs = (f"<h2 id=sections>{html.escape(C['sections_h2'])}</h2><ul>"
            + "".join(f"<li><a href='{PATH}/{u}/'>{html.escape(S[k])}</a></li>" for k, u in (("special_districts", SD_HUB), ("amendment_3", AMEND), ("rolled_back", "fl/rolled-back-rate"))) + "</ul>")
    wr = C["with_rows"].format(n=cov["with_rows"], total=cov["total"], csv=cov["in_csv"], alt=len(cov["alt_only"]))
    inner = (f"<p class=lead>{html.escape(C['intro'])}</p><p>{html.escape(C['absent'])}</p>" + secs
             + f"<h2 id=counties>{html.escape(C['table_h2'])}</h2><p class=muted>{COV}</p><p>{html.escape(wr)}</p>" + tbl)
    srcs = sorted({r['source_url'] for b in SD_BODIES.values() for r in b["rows"]})
    ds = {"@context": "https://schema.org", "@type": "Dataset", "name": C["h1"], "description": C["desc"] + " " + coverage_sentence(cov, meta=True) + " Absent is not zero.",
          "license": "https://creativecommons.org/licenses/by/4.0/", "temporalCoverage": "2025", "url": f"{BASE}/{FL_HUB}/", "creator": {"@type": "Organization", "name": "Hazey Data"},
          "spatialCoverage": "Florida", "isBasedOn": srcs}
    bc = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
          {"@type": "ListItem", "position": 1, "name": "OpenMillage", "item": BASE + "/"}, {"@type": "ListItem", "position": 2, "name": C["crumb"], "item": f"{BASE}/{FL_HUB}/"}]}
    page(f"{FL_HUB}/index.html", C["title"], inner, ds, C["desc"], lead=HEAD_LEAD, trail=[(C["crumb"], None)], h1=C["h1"], extra_ld=[bc])
    urls.append(f"{BASE}/{FL_HUB}/")
fl_hub()
AL = sorted([r for r in rows if r["county"] == "Alachua" and r["levy_scope"] == "countywide" and r["rate_kind"] == "adopted" and r["body_type"] in ("county", "school_district")], key=lambda r: r["body_type"])
HOME_STACK = redo.stack("Example: Alachua County, 2025 adopted rates", [(sc.display_name(r["taxing_body"]), f"{sc.label(r['body_type'])} · {sc.label(r['levy_component']).lower()}, countywide", f"{float(r['rate']):.4f}", r["source_url"]) for r in AL])
HOME_HERO = redo.chart("county-dots", "Dot plot: 2025 county and school board countywide rates for each Florida county", caption=redo.DOTS_CAPTION) + redo.lede()
HOME_REDO = (redo.intro("The stack (home page)") + HOME_STACK + "<p class=muted>One layer per taxing authority. Not a total: add only the layers that apply to your parcel.</p>" + redo.howto())
page("index.html", "Florida property tax millage rates 2025, each linked to its official source", HOME_HERO + f"<p class=sources>{len(rows)} official rates {html.escape(LEAD_SRC)}, retrieved {max(r['retrieved_at'] for r in rows)[:10]} (UTC). {sum(r['rate_kind']=='aggregate_effective' for r in rows)} rows are Florida DOR totals for districts smaller than a county, not any one body's adopted rate. {cov['sd_rows_in_csv']} baseline rows are independent special districts. {html.escape(home_tail())}</p>"
     f"<p class=callout>Voting on Amendment 3 on {ELECTION}? <a href='{PATH}/{AMEND}/'>See the 2025 adopted millage baseline by county</a>.</p>"
     + HOME_REDO + f"<h2>How to read this</h2><p>{COV}</p><p><a href='{PATH}/{FL_HUB}/'>{html.escape(FL_HUB_COPY['home_link'])}</a></p><p><a href='{PATH}/{SD_HUB}/'>{html.escape(FL_SD_COPY['home_link'])}</a></p><p>Independent special districts {NYS} (absent is not zero): {html.escape(', '.join(cov['not_yet_sourced']))}.{(' ' + html.escape(FL_HUB_COPY['partial_list'].format(names=sources.join_names(cov['partial'])))) if cov['partial'] else ''}</p><p id=correction>{html.escape(CORRECTION)}</p>"
     f"<h2 id=counties>Counties</h2>"
     "<details class=all><summary>See all counties</summary>" f"<p class=filter id=county-filter-wrap hidden><label for=county-filter>Filter counties</label><input type=search id=county-filter autocomplete=off aria-describedby=county-filter-count> <span id=county-filter-count class=muted role=status aria-live=polite></span></p>"
     f"<ul class=counties>{''.join(links)}</ul></details>" + FILTER_JS
     + redo.newsletter() + redo.getdata(f"<a href='{PATH}/api/v1/fl/2025/{AMEND.split('/')[-1]}-baseline.csv'>CSV</a> · <a href='{PATH}/api/v1/fl/2025/{AMEND.split('/')[-1]}-baseline.json'>JSON</a>"),
     {"@context": "https://schema.org", "@type": "Dataset", "name": "OpenMillage", "description": f"Official property tax millage rates for counties, school districts, municipalities and independent special districts where sourced, with source links and file hashes. {coverage_sentence(cov, meta=True)} Absent is not zero: a body with no row is not yet sourced.",
      "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Hazey Data"}, "url": BASE + "/"},
     f"Official Florida 2025 property tax millage rates for counties, school districts, municipalities and independent special districts where sourced, each with its government source link and file hash. {coverage_sentence(cov, meta=True)} Absent is not zero.", current="counties", lead=HEAD_LEAD, h1=redo.HEADLINE)
today = datetime.date.today().isoformat()
open(f"{OUT}/sitemap.xml", "w").write('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    + "".join(f"<url><loc>{u}</loc><lastmod>{today}</lastmod></url>" for u in urls) + "</urlset>")
open(f"{OUT}/CNAME", "w").write(BASE.split("/")[2] + "\n")  # custom domain for GitHub Pages; survives rm -rf docs
open(f"{OUT}/robots.txt", "w").write(f"User-agent: *\nAllow: /\n# Optional feedback from AI agents: see {PATH}/llms.txt (Feedback welcome)\nSitemap: {BASE}/sitemap.xml\n")
open(f"{OUT}/llms.txt", "w").write("# OpenMillage\n> Official US property tax rates (millage) per taxing body, each row linked to a government source with sha256 of the source file. Pilot: Florida 2025.\n\n"
    "## Data\n- JSON per county: " + BASE + "/api/v1/<state>/<year>/<county>.json\n- Fields: state, year, county, taxing_body, body_type, body_id, nces_leaid, fips (county 5-digit or Census place 7-digit GEOID), levy_component, levy_scope, rate_kind (adopted | aggregate_effective = DOR less-than-countywide levies divided by countywide taxable value), rate, unit (mills = $ per $1,000 taxable value), source_url, sha256, retrieved_at; additive keys (null when not applicable): " + ", ".join(EXTRA_KEYS[:-1]) + ", additional_sources (list of source_agency, source_url, sha256, source_page, retrieved_at)\n- Independent special districts (body_type special_district) are published per county. " + coverage_sentence(cov) + " Not yet sourced: " + ", ".join(cov['not_yet_sourced']) + "." + ((" " + FL_HUB_COPY["partial_list"].format(names=sources.join_names(cov['partial']))) if cov['partial'] else "") + "\n" + FL_HUB_COPY["llms_line"].format(url=f"{BASE}/{FL_HUB}/") + FL_SD_COPY["llms_line"].format(hub=f"{BASE}/{SD_HUB}/", base=BASE) + "\n"
    "## Rules\n- Rates are never estimated; if a body is missing, it is not yet collected.\n- Absent is not zero: a county or special district with no row has not been sourced yet; never read a missing rate as 0.\n- Special-district rates are never summed.\n" + sc.FEEDBACK)
open(f"{OUT}/.nojekyll", "w").write("")
print(len(urls), "pages", len(rows), "rows")
