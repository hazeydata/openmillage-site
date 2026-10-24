#!/usr/bin/env python3
"""Static baseline page for the 2026 Florida ballot measure numbered 3 (ticket OM-FL-AMEND3-BASELINE-001).
Run after build.py. Reads 2025 adopted rows only; every number on the page is rendered next to its official
source link; checks below fail the build (exit 1) instead of writing a page that breaks a rule.
Deterministic: no clock reads, sorted inputs, fixed formatting. The slug is the single config value "slug"."""
import csv, datetime, html, json, os, re, sys
from zoneinfo import ZoneInfo
import sources
import site_chrome as sc
import redo
from analytics import GOATCOUNTER_TAG

CFG = json.load(open(os.environ.get("AMEND3_CONFIG", "amend3_config.json")))
BASE = os.environ.get("SITE_BASE", "https://openmillage.com").rstrip("/")
PATH = "/" + BASE.split("/", 3)[3] if BASE.count("/") > 2 else ""
OUT = os.environ.get("OUT", "docs"); SLUG = CFG["slug"].strip("/")
E = lambda s: html.escape(str(s), quote=True)

class BuildError(Exception): pass

def load_ballot(path):
    """Fail closed: the page needs fact's verified ballot facts. `title` must be the verbatim measure title
    (never the 'Ballot Number: N' label); `ballot_number` is rendered only as a label. fact_verified_by and
    fact_verified_at must be set (fact's sign-off); null or missing fails the build."""
    if not os.path.exists(path): raise BuildError(f"ballot facts file missing: {path}")
    b = json.load(open(path))
    for k in ("title", "ballot_number", "ballot_summary", "election_date", "source_url", "fact_verified_by", "fact_verified_at"):
        if b.get(k) in (None, ""): raise BuildError(f"ballot facts: required field {k!r} missing or empty")
    if re.search(r"ballot\s+number|amendment\s+\d", b["title"], re.I):
        raise BuildError(f"ballot facts: title {b['title']!r} is a label, not the measure title")
    if not re.match(r"https://([a-z]+\.)*(dos\.fl\.gov|dos\.myflorida\.com|myflorida\.com)/", b["source_url"]):
        raise BuildError("ballot facts: source_url is not a Florida Division of Elections URL")
    datetime.date.fromisoformat(b["election_date"])
    return b

def rows_from(path):
    return [r for r in csv.DictReader(open(path, newline="")) if r["state"] == "FL" and r["year"] == "2025" and r["rate_kind"] == "adopted"]

def district_key(r): return f"{re.sub(r'[^a-z0-9]+', '-', r['county'].lower()).strip('-')}|{r['body_id']}|{r['levy_component']}"

def fact_gate(districts, path):
    """Fact's special-district verification (key county|body_id|levy_component, since body_id repeats across counties).
    Fails closed unless every published district row is in fact's file with match=true and the same rate, and has its own
    https source link (the row's own source_url is the link), and fact's tacd_source_url must be set and point at a file in the TACD
    source list whose sha256 equals the row's sha256. Duplicate data rows or duplicate fact rows (same key) fail, and the row's
    county must equal fact's county exactly (case-sensitive), so a mis-cased row fails instead of dropping off the page."""
    if not os.path.exists(path): raise BuildError(f"special-district fact file missing: {path}")
    from decimal import Decimal
    fact, bad = {}, []
    for f in csv.DictReader(open(path, newline="")):
        if f["row_id"] in fact: bad.append(f"{f['row_id']}: duplicate fact row")
        fact[f["row_id"]] = f
    seen = set()
    for r in districts:
        k = district_key(r)
        if k in seen: bad.append(f"{k}: duplicate data row")
        seen.add(k)
    for r in districts:
        k = district_key(r); f = fact.get(k)
        if f is None: bad.append(f"{k}: not in fact file")
        elif f["county"] != r["county"]: bad.append(f"{k}: county {r['county']!r} is not an exact match for fact {f['county']!r}")
        elif f["match"].strip().lower() != "true": bad.append(f"{k}: fact match={f['match']!r}")
        elif Decimal(f["rate"]) != Decimal(r["rate"]): bad.append(f"{k}: rate {r['rate']} vs fact {f['rate']}")
        if not r["source_url"].startswith("https://"): bad.append(f"{k}: no source link")
        if f is not None:
            u = f.get("tacd_source_url", "").strip()
            if not u: bad.append(f"{k}: tacd_source_url blank")
            elif SRC_SHA.get(u) != r["sha256"]: bad.append(f"{k}: sha256 {r['sha256'][:12]} does not match the TACD source list for {u}")
    if bad: raise BuildError(f"special-district fact gate: {len(bad)} row(s) fail: " + "; ".join(bad[:5]))

def tacd_sources(path):
    out = {}
    for r in csv.DictReader(open(path, newline="")):
        c = re.sub(r" (County City )?TACD\..*$", "", r["file"])[5:]
        out[r["file"]] = dict(r, county={"Saint Johns": "St. Johns", "Saint Lucie": "St. Lucie"}.get(c, c))
    return out
SRC = tacd_sources(CFG["tacd_sources_csv"]); SRC_SHA = {r["url"]: r["sha256"] for r in SRC.values()}
SRC_BY_COUNTY = {}
for _f, _r in sorted(SRC.items()): SRC_BY_COUNTY.setdefault(_r["county"], _r["url"])

def footnotes(path):
    """Fact's footnote wording, verbatim: the quoted text after 'Wording:' under each numbered heading."""
    out, n = {}, None
    for line in open(path):
        m = re.match(r"(\d+)\. ", line)
        if m: n = int(m.group(1))
        m = re.match(r'Wording: "(.*)"\s*$', line)
        if m and n is not None: out[n] = m.group(1)
    return out

FOOT = footnotes(CFG["footnotes_md"])

def link(u, text="source"): return f"<a href='{E(u)}'>{E(text)}</a>"

def who_sets_what():
    """Lindsay's intro verbatim; the county names it mentions link to their canonical county pages (that link is the source for the counts)."""
    counts = sources.alt_counts(sources.coverage(sources.load_rows())["alt_only"])
    t = redo.who_lead()[3:] + (" " + sources.alt_sentence(counts) if counts else "")
    for c in counts:
        t = re.sub(r"\b" + c + r" \(", f"<a href='{redo.SITE}/fl/2025/{c.lower()}-county/'>{c}</a> (", t, count=1)
    return f"<p>{t}</p>"

def render_amend3(rows, districts, ballot, counties, sd_counties=None):
    if sd_counties is None: sd_counties = sources.coverage(sources.load_rows())["counties_with_rows"]
    names = [c for c, _ in counties]
    have = {r["county"] for r in rows}
    covered = [c for c in names if c in have]; missing = [c for c in names if c not in have]
    sd_have = [c for c in names if any(r["county"] == c for r in districts)]
    others = sorted(set(sd_counties) - set(sd_have)); alt_n = sources.alt_counts(others)  # appraiser rows only: own status, not "missing"
    sd_missing = [c for c in names if c not in sd_have and c not in others]
    sd_file = {c: SRC_BY_COUNTY[c] for c in sd_have}
    nt = {k: sum(r["body_type"] == k for r in rows) for k in ("county", "school_district", "municipality")}
    allrows = rows + districts
    asof = max(r["retrieved_at"] for r in allrows)
    asof_et = datetime.datetime.fromisoformat(asof).astimezone(ZoneInfo("America/New_York"))
    asof_src = next(r["source_url"] for r in sorted(allrows, key=lambda r: (r["retrieved_at"], r["source_url"])) if r["retrieved_at"] == asof)
    county_src = CFG["counties_source"]; ed = datetime.date.fromisoformat(ballot["election_date"])
    group = lambda c: sorted([r for r in rows if r["county"] == c], key=lambda r: ({"county": 0, "school_district": 1}.get(r["body_type"], 2), r["taxing_body"], r["levy_component"], r["levy_scope"]))
    nm = lambda r: E(sc.display_name(r['taxing_body']))
    def tr(r): return (f"<tr><td>{nm(r)}</td><td>{E(sc.label(r['body_type']))}</td><td>{E(sc.label(r['levy_component']))} ({E(sc.label(r['levy_scope']))})</td>"
                       f"<td class='rate num' data-body-id='{E(r['body_id'])}' data-levy='{E(r['levy_component'])}|{E(r['levy_scope'])}'>{E(r['rate'])} {E(r['unit'])} "
                       f"<a href='{E(r['source_url'])}' aria-label='Source for {nm(r)}'>source</a></td></tr>")
    def table(cap, trs):
        return sc.tablewrap(cap, f"<table><caption>{E(cap)}</caption><thead><tr><th scope=col>Taxing body</th><th scope=col>Type</th><th scope=col>Levy</th>"
                                 f"<th scope=col class=num>Adopted rate</th></tr></thead><tbody>{trs}</tbody></table>")
    sections, slugs = [], []
    for c in names + sorted(have - set(names)):
        rs = group(c)
        if not rs: continue
        ds = sorted([r for r in districts if r["county"] == c], key=lambda r: (r["taxing_body"], r["levy_component"]))
        det = (f"<details><summary>Special districts in {E(c)}</summary>{table('Special districts in ' + c, ''.join(tr(r) for r in ds))}</details>" if ds else "")
        fn = ""
        if ds and c in CFG["footnote_citations"]:
            fc = CFG["footnote_citations"][c]
            fn = (f"<p class=footnote>Note {fc['n']}: &ldquo;{E(FOOT[fc['n']])}&rdquo; Source: "
                  + "; ".join(f"{link(SRC[f]['url'], 'DOR 2025 TACD (' + SRC[f]['county'] + ')')}, {E(where)}" for f, where in fc["cites"]) + ".</p>")
        sid = E(re.sub(r'[^a-z0-9]+', '-', c.lower()).strip('-')); slugs.append((sid, c))
        sections.append(f"<section id='{sid}'><h3>{E(c)}</h3>{table('Adopted rates in ' + c, ''.join(tr(r) for r in rs))}{det}{fn}<a class=top href='#main'>Back to top</a></section>")
    jump = "<nav aria-label=\"Jump to county\" class=jump><ul>" + "".join(f"<li><a href='#{sid}'>{E(c)}</a></li>" for sid, c in slugs) + "</ul></nav>"
    n_sd = len(sd_counties)
    md = CFG["millage_definition"]; api = f"api/v1/fl/2025/{SLUG.split('/')[-1]}-baseline"
    srcs = sorted({(r["source_agency"], r["source_url"]) for r in allrows})
    edtxt = f"{ed.strftime('%B')} {ed.day}, {ed.year}"
    kicker = f"<p class=kicker>Ballot measure numbered {ballot['ballot_number']} · {link(CFG['election_date_source'], edtxt)}</p>"
    body = (
      f"<p>Election date: {ed.strftime('%B')} {ed.day}, {ed.year} ({link(CFG['election_date_source'])}).</p>"
      + redo.chart("county-dots", "Dot plot: 2025 county and school board countywide rates for each Florida county")
      + "<h2 id=before-you-vote>Before you vote</h2>" + redo.intro("Before you vote (ballot measure numbered 3 page)").replace("the 2025 adopted rates", f"the {link(srcs[0][1], '2025 adopted rates')}", 1)
      + (
      f"<p class=label>{link(ballot['source_url'], 'Ballot Number ' + str(ballot['ballot_number']))}</p>"
      f"<p>Florida Division of Elections, official ballot title and summary ({link(ballot['source_url'])}):</p>"
      f"<blockquote class=official><p>&ldquo;{E(ballot['title'])}&rdquo;</p><p>&ldquo;{E(ballot['ballot_summary'])}&rdquo;</p><p>{link(ballot['source_url'])}</p></blockquote>"
      )
      + redo.stack("Example county: Alachua, 2025", title_html=f"Example county: Alachua, {link(srcs[0][1], '2025')}", layers=[(sc.display_name(r["taxing_body"]), f"{sc.label(r['body_type'])} · {sc.label(r['levy_component']).lower()}, {sc.label(r['levy_scope'])}", f"{float(r['rate']):.4f}", r["source_url"]) for r in group("Alachua")[:3]])
      + f"<h2>Adopted millage by county</h2>"
      f"<p>These are 2025 adopted rates. As of {asof_et.strftime('%B')} {asof_et.day}, {asof_et.year}, {asof_et.strftime('%H:%M')} ET (latest retrieval of a source file used on this page; the footer's site data date covers every page, {link(asof_src)}).</p>"
      f"<p>Coverage: {len(covered)} of {len(names)} counties ({link(county_src['url'], 'county list: ' + county_src['agency'])}; rates: {link(srcs[0][1], 'Florida Department of Revenue')}).</p>"
      + (f"<p>Not yet collected: {', '.join(E(c) for c in missing)}.</p>" if missing else "")
      + "<details class=all><summary>Coverage by county</summary>"
      + f"<p>Special districts: {len(sd_have)} of {len(names)} Florida counties have special-district rows in this baseline ({sum(r['body_type'] == 'special_district' for r in districts)} rows), read from each county's 2025 TACD file ({link(CFG['tacd_index']['url'], 'Florida Department of Revenue TACD index')}): "
      + ", ".join(f"{E(c)} ({link(sd_file[c], 'TACD')})" for c in sd_have)
      + (f"; not yet collected for: {', '.join(E(c) for c in sd_missing)}" if sd_missing else "") + "."
      + (f" {E(sources.alt_status(alt_n))} {E(sources.alt_sentence(alt_n))}" if alt_n else "") + "</p>"
      + f"<p>Rows shown: {nt['county']} county, {nt['school_district']} school district, {nt['municipality']} municipal and {len(districts)} special-district rates ({link(srcs[0][1], 'Florida Department of Revenue')}).</p>" + "</details>"
      + "<h2 id=who-sets-what>Who sets what</h2>" + who_sets_what()
      + "<details class=all><summary>See all rates</summary>" + jump + "".join(sections) + "</details>"
      + redo.getdata(f"<a href='{PATH}/{api}.csv'>CSV</a> · <a href='{PATH}/{api}.json'>JSON</a>")
      + f"<h2>Questions</h2><dl><dt>What is millage?</dt><dd>{E(md['agency'])}: <q>{E(md['text'])}</q> {link(md['url'])}</dd>"
      f"<dt>Where do these rates come from?</dt><dd>Each value on this page links to the official document it was read from.</dd></dl>")
    title = ballot["title"]
    page = (f"<!doctype html><html lang=en><head><meta charset=utf-8><title>{E(title)}: Florida 2025 adopted millage baseline</title>"
            f"<link rel=canonical href='{BASE}/{SLUG}/'>{sc.head_extra(PATH)}{GOATCOUNTER_TAG}</head>"
            f"{sc.body(PATH, H1, body, 'amend', SLUG, '', sources.data_updated(sources.load_rows()), [('2025 adopted millage baseline', None)], kicker=kicker)}</html>\n")
    return page, allrows

H1 = "Florida 2025 adopted millage baseline"
BLOCK = re.compile(r"<(tr|p|li|dd|dt|h1|h2|h3|summary|caption|title)\b[^>]*>(.*?)</\1>", re.S)  # a table row is one block: its rate cell carries the link
def strip_official(h): return re.sub(r"<blockquote class=official>.*?</blockquote>|<q>.*?</q>", " ", h, flags=re.S)
def check(page):
    errs = []
    body = page.split("<body>", 1)[1].replace(f"<h1>{H1}</h1>", "")  # fixed layout title (meta 9911d28); 2025 is the data year sourced on every row
    for q in re.findall(r"<blockquote class=official>(.*?)</blockquote>", body, re.S):
        if not re.search(r"<a href='https?://", q): errs.append("official quote without source link")
    for tag, inner in BLOCK.findall(re.sub(r"<blockquote class=official>.*?</blockquote>", " ", body, flags=re.S)):
        text = html.unescape(re.sub(r"<[^>]+>", " ", inner))
        if re.search(r"\d", text) and not re.search(r"<a href='https?://", inner): errs.append(f"number without source link in <{tag}>: {text.strip()[:80]!r}")
    plain = re.sub(r"<[^>]+>", " ", strip_official(body)).lower()
    for w in CFG["forecast_terms"]:
        if re.search(r"\b" + re.escape(w.lower()), plain): errs.append(f"forecast term outside official quote: {w!r}")
    for w in CFG["advocacy_terms"]:
        if re.search(r"\b" + re.escape(w.lower()) + r"\b", plain): errs.append(f"advocacy term: {w!r}")
    if len(re.findall(r"<dt>", body)) > 3: errs.append("FAQ has more than 3 items")
    # Footer date: only the <time> element itself is exempt from the future-year rule, and only when it equals the date
    # computed from the data (sources.data_updated); any other date there, or any other text in that paragraph, is checked.
    want = sources.data_updated(sources.load_rows())[0]
    ft = re.findall(r"Site data updated <time datetime=([0-9-]+)>([^<]*)</time>", body)
    if len(ft) != 1: errs.append(f"footer date: expected one 'Site data updated' <time>, found {len(ft)}")
    elif ft[0] != (want.isoformat(), f"{want.strftime('%B')} {want.day}, {want.year}"): errs.append(f"footer date {ft[0]} is not the data date {want}")
    body = re.sub(r"(Site data updated )<time datetime=[0-9-]+>[^<]*</time>", r"\1", body)
    if re.search(r"\b20(2[6-9]|[3-9]\d)\b", re.sub(r"<[^>]+>", " ", re.sub(r"<blockquote class=official>.*?</blockquote>|<table>.*?</table>|Election date:.*?</p>|<p class=kicker>.*?</p>|As of .*?</p>", " ", body, flags=re.S))):
        errs.append("future-year number outside official quote / election date / as-of date")
    return errs

def main():
    try:
        ballot = load_ballot(CFG["ballot_json"])
        rows = rows_from(CFG["rates_csv"])
        districts = rows_from(CFG["districts_csv"]) if os.path.exists(CFG["districts_csv"]) else []
        fact_gate(districts, CFG["district_fact_csv"])
        counties = [(r["name"].removesuffix(" County"), r["geoid"]) for r in csv.DictReader(open(CFG["counties_csv"]))]
        if len(counties) != 67: raise BuildError(f"county list has {len(counties)} rows, expected 67")
        page, shown = render_amend3(rows, districts, ballot, counties, sources.coverage(sources.load_rows())["counties_with_rows"])
        errs = check(page)
        if errs: raise BuildError("page checks failed:\n  " + "\n  ".join(errs))
    except BuildError as e:
        print(f"amend3: BUILD FAILED (fail closed, no page written): {e}", file=sys.stderr); return 1
    os.makedirs(f"{OUT}/{SLUG}", exist_ok=True)
    open(f"{OUT}/{SLUG}/index.html", "w").write(page)
    api = f"{OUT}/api/v1/fl/2025/{SLUG.split('/')[-1]}-baseline"
    fields = list(csv.DictReader(open(CFG["rates_csv"]))).__iter__().__next__().keys()
    fields = list(fields)
    with open(api + ".csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n"); w.writeheader(); w.writerows(shown)
    json.dump([{k: r[k] for k in fields} for r in shown], open(api + ".json", "w"), indent=1)
    sm = f"{OUT}/sitemap.xml"; url = f"{BASE}/{SLUG}/"
    if os.path.exists(sm) and url not in open(sm).read():
        s = open(sm).read(); lm = (re.findall(r"<lastmod>([^<]+)</lastmod>", s) or [""])[0]
        open(sm, "w").write(s.replace("</urlset>", f"<url><loc>{url}</loc>" + (f"<lastmod>{lm}</lastmod>" if lm else "") + "</url></urlset>"))
    lt = f"{OUT}/llms.txt"; line = f"- Florida 2025 adopted millage baseline for the 2026 ballot measure numbered 3: {url}\n"
    if os.path.exists(lt) and line not in open(lt).read():
        txt = open(lt).read()
        open(lt, "w").write(txt[:-len(sc.FEEDBACK)] + line + sc.FEEDBACK if txt.endswith(sc.FEEDBACK) else txt + line)
    print(f"amend3: wrote {SLUG}/index.html ({len(shown)} rows)"); return 0

if __name__ == "__main__": sys.exit(main())
