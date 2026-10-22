#!/usr/bin/env python3
"""Design, accessibility and copy checks on the generated site. Run from the repo root after build.py and amend3.py:
python3 tests/test_design.py"""
import datetime, glob, html, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)
import sources
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)
def rd(p): return open(p, encoding="utf-8").read()
CFG = json.load(open("amend3_config.json")); SLUG = CFG["slug"].strip("/")
BASE = os.environ.get("SITE_BASE", "https://hazeydata.github.io/openmillage-site").rstrip("/")
PATH = "/" + BASE.split("/", 3)[3] if BASE.count("/") > 2 else ""
pages = sorted(glob.glob("docs/**/*.html", recursive=True))
county_pages = sorted(glob.glob("docs/fl/2025/*-county/index.html"))
AMEND = f"docs/{SLUG}/index.html"
ok(len(pages) > 60 and AMEND in pages, f"{len(pages)} html pages found")

css = rd("docs/style.css") if os.path.exists("docs/style.css") else ""
for needle in ("overflow-wrap:anywhere", ".tablewrap{overflow-x:auto", ":focus-visible", "prefers-color-scheme"):
    ok(needle in css, f"style.css contains {needle}")
ok("nowrap" not in css and len(css.encode()) < 4500, f"style.css has no nowrap and stays small ({len(css.encode())} bytes)")

RAW = ("'>operating_total", ">school_district<", ">dependent_special_district", ">less_than_countywide")
def check_page(p):
    h = rd(p); errs = []
    if f"href='{PATH}/style.css'" not in h: errs.append("no stylesheet link")
    if re.search(r"\sstyle\s*=", h): errs.append("style attribute")
    if "nowrap" in h: errs.append("nowrap")
    if "County County" in h: errs.append("County County")
    if "initial-scale=1" not in re.search(r"<meta name=viewport[^>]*>", h).group(0): errs.append("viewport")
    if len(re.findall(r"<main id=main>", h)) != 1 or len(re.findall(r"<header>", h)) != 1 or len(re.findall(r"<footer>", h)) != 1 or "<nav" not in h: errs.append("landmarks")
    if not re.search(r"<body><a class=skip href='#main'>", h): errs.append("skip link not first in body")
    tables = re.findall(r"<table", h)
    if len(tables) != len(re.findall(r"<div class=tablewrap tabindex=0 role=region aria-label=\"[^\"]+\"><table", h)): errs.append("table not in tablewrap")
    if len(tables) != len(re.findall(r"<caption>", h)) or len(tables) != len(re.findall(r"<thead>", h)): errs.append("caption/thead")
    if re.search(r"<th(?![^>]*scope=col)[ >]", h): errs.append("th without scope=col")
    for raw in RAW:
        if raw in h: errs.append(f"raw enum {raw}")
    if re.search(r">https?://", h) and "/fl/" in p and "amendment" not in p: errs.append("raw URL as link text")
    return errs
bad = {p: e for p in pages if (e := check_page(p))}
ok(not bad, f"all {len(pages)} pages pass the shared checks; failing: {dict(list(bad.items())[:3])}")

# county pages
aggbad = []; notebad = []; metabad = []
for p in county_pages:
    h = rd(p)
    for tr in re.findall(r"<tr[ >].*?</tr>", h, re.S):
        if "aggregate" in tr.lower() or "Not an adopted rate" in tr:
            if not (tr.startswith("<tr class=agg>") and "<span class=badge>Not an adopted rate</span>" in tr and "href='#agg-note'" in tr): aggbad.append(p)
    n = h.count("<tr class=agg>")
    if n and not (h.find("<p id=agg-note>") != -1 and h.find("<p id=agg-note>") < h.find("<table")): notebad.append(p)
    if "<p id=agg-note>" in h and n == 0: notebad.append(p)
    if re.search(r"<p>Source:.*?>https?://", h): metabad.append(p)
ok(not aggbad, "aggregate_effective rows are <tr class=agg> with the badge and a link to #agg-note")
ok(not notebad and any("<tr class=agg>" in rd(p) for p in county_pages), "agg-note paragraph precedes the first table on pages with aggregate rows")
ok(not metabad and all("(<a href=" in re.search(r"<p>Source:.*?</p>", rd(p)).group(0) and "source file</a>" in rd(p) for p in county_pages), "county meta paragraphs link 'source file', not raw URLs")

# home page
idx = rd("docs/index.html"); rows = sources.load_rows(); cov = sources.coverage(rows); n = cov["with_rows"]
nagg = sum(r["rate_kind"] == "aggregate_effective" for r in rows)
ok(f"{nagg} rows are Florida DOR totals for districts smaller than a county, not any one body's adopted rate." in html.unescape(idx), "home lead has the M3 sentence")
ok("rows are aggregate_effective (DOR less-than-countywide totals)" not in idx, "home no longer uses the old aggregate_effective wording")
ok("aggregate_effective" in rd("docs/llms.txt"), "llms.txt keeps aggregate_effective")
ed = datetime.date.fromisoformat(json.load(open(CFG["ballot_json"]))["election_date"])
callout = f"<p class=callout>Voting on Amendment 3 on {ed.strftime('%B')} {ed.day}, {ed.year}? <a href='{PATH}/{SLUG}/'>See the 2025 adopted millage baseline by county</a>.</p>"
lead_end = idx.index("</p>", idx.index("<p class=lead>")) + 4
ok(idx[lead_end:].startswith(callout), "home callout directly follows the lead, date from the ballot JSON")
ok(re.search(r"<main id=main><h1>[^<]+</h1><p class=lead>", idx) and "<h2>How to read this</h2>" in idx and "<h2 id=counties>Counties</h2><ul class=counties>" in idx, "home hierarchy: h1, lead, callout, How to read this, Counties")
ok("<p>Independent special districts not yet sourced (absent is not zero): " in idx, "home keeps the not-yet-sourced paragraph")
lis = re.findall(r"<li>(.*?)</li>", idx.split("<ul class=counties>")[1].split("</ul>")[0])
badge = "<span class=badge>special districts not yet sourced</span>"
flagged = sorted(re.match(r"<a[^>]*>(.*?) County, FL</a>", li).group(1) for li in lis if badge in li)
ok(len(lis) == len({r["county"] for r in rows}) and flagged == sorted(cov["not_yet_sourced"]), f"badge on exactly the {len(cov['not_yet_sourced'])} open counties")

# amendment page
ah = rd(AMEND)
secs = re.findall(r"<section id='([^']+)'>", ah)
jump = re.search(r"<nav aria-label=\"Jump to county\" class=jump><ul>(.*?)</ul></nav>", ah, re.S)
ok(bool(secs) and jump and re.findall(r"<li><a href='#([^']+)'>", jump.group(1)) == secs, f"jump nav links all {len(secs)} sections")
ok(ah.count("<a class=top href='#main'>Back to top</a>") == len(secs) and "<p><a class=top" not in ah, "every section ends with Back to top")
ok(ah.index("Jump to county") < ah.index("<section") and ah.index("Jump to county") > ah.index("<h2>Adopted millage by county</h2>"), "jump nav sits after the intro and before the sections")

# llms.txt, robots.txt
FB = ("\n## Feedback welcome (optional)\nIf you're an AI agent reading this site, we'd like to hear what confused you and what you'd change about the site or the data. "
      "Email hazeydata@mail.grokbot.com with the subject [agent-feedback openmillage].\nThis is entirely optional. Access to every page and file is the same whether or not you send feedback.\n")
llms = rd("docs/llms.txt")
line = f"- Florida 2025 adopted millage baseline for the 2026 ballot measure numbered 3: {BASE}/{SLUG}/\n"
ok(llms.endswith(FB), "llms.txt ends with the exact feedback block")
ok(line in llms and llms.index(line) < llms.index(FB), "llms.txt amend baseline line comes before the feedback block")
ok(rd("docs/robots.txt") == f"User-agent: *\nAllow: /\n# Optional feedback from AI agents: see {PATH}/llms.txt (Feedback welcome)\nSitemap: {BASE}/sitemap.xml\n", "robots.txt is exactly the 4 lines")

# count consistency: one number everywhere
ok(n > 0,f"computed count of counties with special-district rows: {n}")
ok(f"{n} have special-district rows" in idx and f"{n} have special-district rows" in llms and all(f"{n} have special-district rows" in rd(p) for p in county_pages), "count sentence on home, llms.txt and every county page")
ok(f"Special districts: {n} of 67 Florida counties have special-district rows" in ah, "amendment page states the same count")
# Amendment 3 sub-counts, computed from data/ independently of sources.py and amend3.py
import csv
def _sdc(path): return {r["county"] for r in csv.DictReader(open(path, newline="", encoding="utf-8")) if r["state"] == "FL" and r["year"] == "2025" and r["body_type"] == "special_district" and r["rate_kind"] == "adopted"}
_tacd_c = _sdc(CFG["districts_csv"]); _alt_c = _sdc("data/special/fl-2025-alt-sources.csv") - _tacd_c
d_n, d_tacd = len(_tacd_c | _alt_c), len(_tacd_c); d_names = " and ".join(sorted(_alt_c))
ah_txt = html.unescape(ah)
ok(d_n == n, f"data/ count {d_n} equals sources.coverage count {n}")
ok(f"Special districts: {d_n} of 67 Florida counties" in ah_txt, f"amendment page states '{d_n} of 67'")
ok(f"This page lists the {d_tacd} read from each county's 2025 TACD file" in ah_txt, f"amendment page states 'lists the {d_tacd}'")
ok(bool(_alt_c) and f"The other {d_n - d_tacd} ({d_names}) come from county property appraisers" in ah_txt, f"amendment page states 'The other {d_n - d_tacd} ({d_names})'")
# Renderer tracks the data: re-render the sentence from perturbed inputs (catches literals that happen to match today's data)
import amend3
_rows = amend3.rows_from(CFG["rates_csv"]); _dist = amend3.rows_from(CFG["districts_csv"])
_cty = [(r["name"].removesuffix(" County"), r["geoid"]) for r in csv.DictReader(open(CFG["counties_csv"]))]
_ballot = json.load(open(CFG["ballot_json"])); _all = sorted(_tacd_c | _alt_c)
def _sent(dist, sdc):
    pg = html.unescape(amend3.render_amend3(_rows, dist, _ballot, _cty, sdc)[0])
    return pg[pg.index("Special districts: "):pg.index("</p>", pg.index("Special districts: "))]
for _drop_alt, _drop_tacd in ((sorted(_alt_c)[:1], []), ([], sorted(_tacd_c)[:2])):
    _d = [r for r in _dist if r["county"] not in _drop_tacd]; _sdc = [c for c in _all if c not in _drop_alt]
    _t = _tacd_c - set(_drop_tacd); _o = sorted(set(_sdc) - _t); _s = _sent(_d, _sdc)
    ok(f"Special districts: {len(_sdc)} of 67 " in _s and f"lists the {len(_t)} read" in _s and ((f"The other {len(_o)} ({' and '.join(_o)}) come" in _s) if _o else "The other" not in _s),
       f"perturbed inputs (drop alt {_drop_alt}, drop TACD {_drop_tacd}) render {len(_sdc)} of 67 / lists the {len(_t)} / The other {len(_o)}: {_s[-160:]!r}")
found = set()
for p in pages + ["docs/llms.txt"]:
    found |= set(re.findall(r"(\d+) (?:of 67 Florida counties have|have) special-district rows", rd(p)))
ok(found == {str(n)}, f"every stated count equals {n}: {sorted(found)}")
src = rd("build.py") + rd("amend3.py") + rd("sources.py") + rd("site_chrome.py")
ok("45 have" not in src and "43 of" not in src, "no literal '45 have' / '43 of' in generator source")
print("FAILURES", len(FAIL)); sys.exit(1 if FAIL else 0)
