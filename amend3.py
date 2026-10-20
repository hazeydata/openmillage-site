#!/usr/bin/env python3
"""Static baseline page for the 2026 Florida ballot measure numbered 3 (ticket OM-FL-AMEND3-BASELINE-001).
Run after build.py. Reads 2025 adopted rows only; every number on the page is rendered next to its official
source link; checks below fail the build (exit 1) instead of writing a page that breaks a rule.
Deterministic: no clock reads, sorted inputs, fixed formatting. The slug is the single config value "slug"."""
import csv, datetime, html, json, os, re, sys
from zoneinfo import ZoneInfo

CFG = json.load(open(os.environ.get("AMEND3_CONFIG", "amend3_config.json")))
BASE = os.environ.get("SITE_BASE", "https://hazeydata.github.io/openmillage-site").rstrip("/")
PATH = "/" + BASE.split("/", 3)[3] if BASE.count("/") > 2 else ""
OUT = os.environ.get("OUT", "docs"); SLUG = CFG["slug"].strip("/")
E = lambda s: html.escape(str(s), quote=True)

class BuildError(Exception): pass

def load_ballot(path):
    """Fail closed: the page needs fact's verified ballot facts. `title` must be the verbatim measure title
    (never the 'Ballot Number: N' label); `ballot_number` is rendered only as a label. fact_verified_by may be null."""
    if not os.path.exists(path): raise BuildError(f"ballot facts file missing: {path}")
    b = json.load(open(path))
    for k in ("title", "ballot_number", "ballot_summary", "election_date", "source_url"):
        if b.get(k) in (None, ""): raise BuildError(f"ballot facts: required field {k!r} missing or empty")
    if re.search(r"ballot\s+number|amendment\s+\d", b["title"], re.I):
        raise BuildError(f"ballot facts: title {b['title']!r} is a label, not the measure title")
    if not re.match(r"https://([a-z]+\.)*(dos\.fl\.gov|dos\.myflorida\.com|myflorida\.com)/", b["source_url"]):
        raise BuildError("ballot facts: source_url is not a Florida Division of Elections URL")
    datetime.date.fromisoformat(b["election_date"])
    return b

def rows_from(path):
    return [r for r in csv.DictReader(open(path, newline="")) if r["state"] == "FL" and r["year"] == "2025" and r["rate_kind"] == "adopted"]

def link(u, text="source"): return f"<a href='{E(u)}'>{E(text)}</a>"

def render_amend3(rows, districts, ballot, counties):
    names = [c for c, _ in counties]
    have = {r["county"] for r in rows}
    covered = [c for c in names if c in have]; missing = [c for c in names if c not in have]
    sd_have = [c for c in names if any(r["county"] == c for r in districts)]; sd_missing = [c for c in names if c not in sd_have]
    sd_src = sorted({r["source_url"] for r in districts})[0] if districts else CFG["counties_source"]["url"]
    allrows = rows + districts
    asof = max(r["retrieved_at"] for r in allrows)
    asof_et = datetime.datetime.fromisoformat(asof).astimezone(ZoneInfo("America/New_York"))
    asof_src = next(r["source_url"] for r in sorted(allrows, key=lambda r: (r["retrieved_at"], r["source_url"])) if r["retrieved_at"] == asof)
    county_src = CFG["counties_source"]; ed = datetime.date.fromisoformat(ballot["election_date"])
    group = lambda c: sorted([r for r in rows if r["county"] == c], key=lambda r: ({"county": 0, "school_district": 1}.get(r["body_type"], 2), r["taxing_body"], r["levy_component"], r["levy_scope"]))
    def tr(r): return (f"<tr><td>{E(r['taxing_body'])}</td><td>{E(r['body_type'])}</td><td>{E(r['levy_component'])} ({E(r['levy_scope'])})</td>"
                       f"<td class=rate data-body-id='{E(r['body_id'])}' data-levy='{E(r['levy_component'])}|{E(r['levy_scope'])}'>{E(r['rate'])} {E(r['unit'])} {link(r['source_url'])}</td></tr>")
    hdr = "<tr><th>Taxing body</th><th>Type</th><th>Levy</th><th>Adopted rate</th></tr>"
    sections = []
    for c in names + sorted(have - set(names)):
        rs = group(c)
        if not rs: continue
        ds = sorted([r for r in districts if r["county"] == c], key=lambda r: (r["taxing_body"], r["levy_component"]))
        det = (f"<details><summary>Special districts in {E(c)}</summary><table>{hdr}{''.join(tr(r) for r in ds)}</table></details>" if ds else "")
        sections.append(f"<section id='{E(re.sub(r'[^a-z0-9]+', '-', c.lower()).strip('-'))}'><h3>{E(c)}</h3><table>{hdr}{''.join(tr(r) for r in rs)}</table>{det}</section>")
    md = CFG["millage_definition"]; api = f"api/v1/fl/2025/{SLUG.split('/')[-1]}-baseline"
    srcs = sorted({(r["source_agency"], r["source_url"]) for r in allrows})
    body = (
      f"<p class=label>{link(ballot['source_url'], 'Ballot Number ' + str(ballot['ballot_number']))}</p>"
      f"<p>Florida Division of Elections, official ballot title and summary ({link(ballot['source_url'])}):</p>"
      f"<blockquote class=official><p>&ldquo;{E(ballot['title'])}&rdquo;</p><p>&ldquo;{E(ballot['ballot_summary'])}&rdquo;</p><p>{link(ballot['source_url'])}</p></blockquote>"
      f"<p>Election date: {ed.strftime('%B')} {ed.day}, {ed.year} ({link(CFG['election_date_source'])}).</p>"
      f"<h2>Adopted millage by county</h2>"
      f"<p>These are 2025 adopted rates. As of {asof_et.strftime('%B')} {asof_et.day}, {asof_et.year}, {asof_et.strftime('%H:%M')} ET (latest retrieval of a source file, {link(asof_src)}).</p>"
      f"<p>Coverage: {len(covered)} of {len(names)} counties ({link(county_src['url'], 'county list: ' + county_src['agency'])}; rates: {link(srcs[0][1], 'Florida Department of Revenue')}).</p>"
      + (f"<p>Not yet collected: {', '.join(E(c) for c in missing)}.</p>" if missing else "")
      + f"<p>Special districts: {len(sd_have)} of {len(names)} counties have special-district rows ({link(sd_src, 'Florida Department of Revenue')})" + (f"; not yet collected for: {', '.join(E(c) for c in sd_missing)}" if sd_missing else "") + ".</p>"
      + "".join(sections)
      + f"<p>Rows shown on this page: <a href='{PATH}/{api}.csv'>CSV</a> · <a href='{PATH}/{api}.json'>JSON</a>.</p>"
      f"<h2>Questions</h2><dl><dt>What is millage?</dt><dd>{E(md['agency'])}: <q>{E(md['text'])}</q> {link(md['url'])}</dd>"
      f"<dt>Where do these rates come from?</dt><dd>Each rate links to the official file it was read from: "
      + "; ".join(f"{E(a)} ({link(u)})" for a, u in srcs) + ".</dd></dl>")
    title = ballot["title"]
    page = (f"<!doctype html><html lang=en><head><meta charset=utf-8><title>{E(title)}: Florida 2025 adopted millage baseline</title>"
            f"<link rel=canonical href='{BASE}/{SLUG}/'><meta name=viewport content='width=device-width'></head>"
            f"<body><h1>{E(title)}</h1>{body}<footer><p><a href='{PATH}/llms.txt'>llms.txt</a> · <a href='{PATH}/'>All counties</a></p></footer></body></html>\n")
    return page, allrows

BLOCK = re.compile(r"<(tr|p|li|dd|dt|h1|h2|h3|summary|caption|title)\b[^>]*>(.*?)</\1>", re.S)  # a table row is one block: its rate cell carries the link
def strip_official(h): return re.sub(r"<blockquote class=official>.*?</blockquote>|<q>.*?</q>", " ", h, flags=re.S)
def check(page):
    errs = []
    body = page.split("<body>", 1)[1]
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
    if re.search(r"\b20(2[6-9]|[3-9]\d)\b", re.sub(r"<[^>]+>", " ", re.sub(r"<blockquote class=official>.*?</blockquote>|<table>.*?</table>|Election date:.*?</p>|As of .*?</p>", " ", body, flags=re.S))):
        errs.append("future-year number outside official quote / election date / as-of date")
    return errs

def main():
    try:
        ballot = load_ballot(CFG["ballot_json"])
        rows = rows_from(CFG["rates_csv"])
        districts = rows_from(CFG["districts_csv"]) if os.path.exists(CFG["districts_csv"]) else []
        counties = [(r["name"].removesuffix(" County"), r["geoid"]) for r in csv.DictReader(open(CFG["counties_csv"]))]
        if len(counties) != 67: raise BuildError(f"county list has {len(counties)} rows, expected 67")
        page, shown = render_amend3(rows, districts, ballot, counties)
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
    if os.path.exists(lt) and line not in open(lt).read(): open(lt, "a").write(line)
    print(f"amend3: wrote {SLUG}/index.html ({len(shown)} rows)"); return 0

if __name__ == "__main__": sys.exit(main())
