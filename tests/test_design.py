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
ok(re.search(r"<main id=main><h1>[^<]+</h1><p class=lead>", idx) and "<h2>How to read this</h2>" in idx and re.search(r"<h2 id=counties>Counties</h2><p class=filter id=county-filter-wrap hidden>.*?</p><ul class=counties>", idx), "home hierarchy: h1, lead, callout, How to read this, Counties")
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
d_n, d_tacd = len(_tacd_c | _alt_c), len(_tacd_c)
def _join(xs): xs = list(xs); return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]
d_names = _join(sorted(_alt_c))
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
    ok(f"Special districts: {len(_sdc)} of 67 " in _s and f"lists the {len(_t)} read" in _s and ((f"The other {len(_o)} ({_join(_o)}) come" in _s) if _o else "The other" not in _s),
       f"perturbed inputs (drop alt {_drop_alt}, drop TACD {_drop_tacd}) render {len(_sdc)} of 67 / lists the {len(_t)} / The other {len(_o)}: {_s[-160:]!r}")
found = set()
for p in pages + ["docs/llms.txt"]:
    found |= set(re.findall(r"(\d+) (?:of 67 Florida counties have|have) special-district rows", rd(p)))
ok(found == {str(n)}, f"every stated count equals {n}: {sorted(found)}")
src = rd("build.py") + rd("amend3.py") + rd("sources.py") + rd("site_chrome.py")
ok("45 have" not in src and "43 of" not in src, "no literal '45 have' / '43 of' in generator source")
# --- Tobias #3: county pages group rows as County / School / Municipalities / Special districts
GROUP_OF = {"county": "County", "school_district": "School", "municipality": "Municipalities", "special_district": "Special districts"}
gbad = []
_by = {}
for r in rows: _by.setdefault(r["county"], []).append(r)
for cty, rs in sorted(_by.items()):
    p = f"docs/fl/2025/{re.sub(r'[^a-z0-9]+', '-', cty.lower()).strip('-')}-county/index.html"; h = rd(p)
    want = [g for g in ("County", "School", "Municipalities") if any(GROUP_OF[r["body_type"]] == g for r in rs)]
    heads = re.findall(r"<h2(?: id=[^>]*)?>([^<]+)</h2>", h)
    got = [x for x in heads if x in GROUP_OF.values()]
    exp = want + (["Special districts"] if "<h2 id=special-districts>Special districts</h2>" in h else [])
    if got != exp: gbad.append((cty, got, exp)); continue
    # every row sits under its own group's heading, and each group's table holds exactly that group's rows
    parts = re.split(r"<h2(?: id=[^>]*)?>([^<]+)</h2>", h)
    for g, chunk in zip(parts[1::2], parts[2::2]):
        if g not in ("County", "School", "Municipalities"): continue
        types = re.findall(r"<tr(?: class=agg)?><td>[^<]*</td><td>([^<]+)</td>", chunk.split("<h2")[0])
        n_exp = sum(GROUP_OF[r["body_type"]] == g for r in rs)
        lab = {"County": {"County"}, "School": {"School district"}, "Municipalities": {"Municipality"}}[g]
        if len(types) != n_exp or set(types) - lab: gbad.append((cty, g, len(types), n_exp, sorted(set(types))))
ok(not gbad, f"county pages group rows under County / School / Municipalities / Special districts headings in that order, each group holding exactly its rows: {gbad[:3]}")
pb = rd("docs/fl/2025/palm-beach-county/index.html")
ok(all(f">{g}</h2>" in pb for g in ("County", "School", "Municipalities", "Special districts")), "Palm Beach shows all four groups")
ok(pb.index("<p id=agg-note>") < pb.index("<table") if "<p id=agg-note>" in pb else True, "agg-note still precedes the first table after grouping")

# --- Tobias #4: home county filter, progressive enhancement
fw = re.search(r"<p class=filter id=county-filter-wrap hidden><label for=county-filter>Filter counties</label><input type=search id=county-filter[^>]*>", idx)
ok(bool(fw), "home has a labelled county filter that is hidden in the markup (shows only when JS runs)")
js = re.search(r"<script>(\(function\(\)\{var w=document.getElementById\('county-filter-wrap'\).*?)</script>", idx, re.S)
ok(bool(js) and "w.hidden=false" in js.group(1) and "e.hidden=!m" in js.group(1) and "src=" not in js.group(0), "inline script un-hides the filter and filters list items; no external script")
nojs = re.sub(r"<script>.*?</script>", "", idx, flags=re.S)
ok(len(re.findall(r"<li><a href='[^']+-county/'>", nojs.split("<ul class=counties>")[1].split("</ul>")[0])) == len(_by), f"without JS the grid still lists all {len(_by)} county links")
# run the filter logic in node if available (behavioural); otherwise the static checks above stand
import shutil, subprocess, tempfile
if shutil.which("node"):
    lis = re.findall(r"<li><a href='[^']+'>([^<]+)</a>", idx.split("<ul class=counties>")[1].split("</ul>")[0])
    harness = """const names=%s;const items=names.map(n=>({hidden:false,querySelector:()=>({textContent:n})}));
const els={'county-filter-wrap':{hidden:true},'county-filter':{value:'',l:null,addEventListener(e,f){this.l=f}},'county-filter-count':{textContent:''}};
global.document={getElementById:id=>els[id],querySelectorAll:()=>items};
%s
const out=[els['county-filter-wrap'].hidden];for(const q of ['palm','  BEACH ','zzz','']){els['county-filter'].value=q;els['county-filter'].l();out.push([items.filter(i=>!i.hidden).map(i=>i.querySelector().textContent),els['county-filter-count'].textContent]);}
console.log(JSON.stringify(out));""" % (json.dumps(lis), js.group(1))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f: f.write(harness)
    res = json.loads(subprocess.run(["node", f.name], capture_output=True, text=True, check=True).stdout); os.unlink(f.name)
    beach = [x for x in lis if "beach" in x.lower()]
    ok(res[0] is False and res[1][0] == ["Palm Beach County, FL"] and res[2][0] == beach and res[2][1] == f"{len(beach)} of {len(lis)} counties"
       and res[3][0] == [] and res[3][1] == f"0 of {len(lis)} counties" and res[4][0] == lis and res[4][1] == "", f"filter behaviour in node: {[(r if isinstance(r, bool) else (len(r[0]), r[1])) for r in res]}")
else:
    ok(True, "node not available: filter behaviour checked statically only")

# --- Tobias #7: nav (Method, API), breadcrumbs, footer 'Data updated <date>' from the data
import site_chrome as sc
api_href = f"{PATH}/{sc.api_page(SLUG)}"; meth_href = f"{PATH}/{sc.METHOD_PAGE}"
ok(os.path.exists("docs/" + sc.api_page(SLUG)) and os.path.exists("docs/" + sc.METHOD_PAGE), f"Method ({sc.METHOD_PAGE}) and API ({sc.api_page(SLUG)}) targets exist in docs/")
navbad = [p for p in pages if not re.search(r"<nav aria-label=Site>.*?>Counties</a>.*?>Amendment 3</a> <a href='" + re.escape(meth_href) + r"'>Method</a> <a href='" + re.escape(api_href) + r"'>API</a></nav>", rd(p))]
ok(not navbad, f"every page's nav reads Counties · Amendment 3 · Method · API with working targets; failing {navbad[:3]}")
crbad = [p for p in county_pages if not re.search(r"</header><nav aria-label=Breadcrumb class=crumbs><a href='" + re.escape(PATH) + r"/'>OpenMillage</a> &rsaquo; <a href='" + re.escape(PATH) + r"/#counties'>Counties</a> &rsaquo; <span aria-current=page>[^<]+ County, FL</span></nav><main", rd(p))]
ok(not crbad, f"every county page has OpenMillage > Counties > <county> breadcrumbs; failing {crbad[:3]}")
ok(re.search(r"</header><nav aria-label=Breadcrumb class=crumbs><a href='" + re.escape(PATH) + r"/'>OpenMillage</a> &rsaquo; <span aria-current=page>[^<]+</span></nav><main", ah) is not None, "Amendment 3 page has breadcrumbs")
ok("aria-label=Breadcrumb" not in idx, "home has no breadcrumbs (it is the root)")
from zoneinfo import ZoneInfo
_lat = max(r["retrieved_at"] for r in rows); _d = datetime.datetime.fromisoformat(_lat).astimezone(ZoneInfo("America/New_York")).date()
_u = min(r["source_url"] for r in rows if r["retrieved_at"] == _lat)
upd = f"<footer><p>Site data updated <time datetime={_d.isoformat()}>{_d.strftime('%B')} {_d.day}, {_d.year}</time> (latest source retrieval across all pages, <a href='{html.escape(_u)}'>source</a>).</p>"
ftbad = [p for p in pages if upd not in rd(p)]
ok(not ftbad, f"every page footer says 'Data updated {_d}' from the latest retrieved_at in data/, linked to that source; failing {ftbad[:3]}")
ok("date.today" not in rd("site_chrome.py") and "data_updated(rows)" in rd("build.py"), "footer date is not the build clock")

# --- alt-county name join: 'A', 'A and B', 'A, B and C'
ok([sc.name_list(x) for x in (["A"], ["A", "B"], ["A", "B", "C"], ["A", "B", "C", "D"])] == ["A", "A and B", "A, B and C", "A, B, C and D"], "name_list joins 3+ names as 'A, B and C'")
ok("' and '.join" not in rd("amend3.py"), "amend3.py uses name_list, not ' and '.join")
# --- Tobias #1: body padding is 1rem on every side (not '0 1rem')
_body = re.findall(r"(?:^|\n|\})body\{([^}]*)\}", css)
_pads = [d.strip() for blk in _body for d in blk.split(";") if d.strip().startswith("padding")]
ok(_pads == ["padding:1rem"] or (len(_pads) == 1 and re.fullmatch(r"padding:(1rem)( 1rem){3}", _pads[0])), f"body padding is 1rem on all four sides: {_pads}")

# --- Footer date on PERTURBED data: copy the repo to a tmp dir, move one row's retrieved_at, rebuild there, and the footer must follow
import shutil as _sh, subprocess as _sp, tempfile as _tf, hashlib as _hl
_tmp = _tf.mkdtemp(prefix="om-footer-")
try:
    _sh.copytree(ROOT, os.path.join(_tmp, "r"), ignore=_sh.ignore_patterns(".git", "docs", "__pycache__"))
    _r = os.path.join(_tmp, "r"); _csvp = os.path.join(_r, "data/fl-2025.csv")
    _lines = open(_csvp, encoding="utf-8").read().splitlines(keepends=True)
    _hdr = next(csv.reader([_lines[0]])); _ri = _hdr.index("retrieved_at"); _si = _hdr.index("source_url")
    _row = next(csv.reader([_lines[1]]))
    _new = "2026-11-05T03:30:00+00:00"   # 23:30 ET on November 4: also checks the ET conversion
    _old = _row[_ri]; assert _old in _lines[1] and _old < _new
    _lines[1] = _lines[1].replace(_old, _new, 1); open(_csvp, "w", encoding="utf-8").write("".join(_lines))
    _lk = json.load(open(os.path.join(_r, "data/SOURCES.lock")))
    for _f in _lk["files"]:
        if _f["path"] == "data/fl-2025.csv": _f["sha256"] = _hl.sha256(open(_csvp, "rb").read()).hexdigest()
    json.dump(_lk, open(os.path.join(_r, "data/SOURCES.lock"), "w"), indent=1)
    _env = dict(os.environ, DATA_GLOB="data/*.csv")
    _b = _sp.run([sys.executable, "build.py"], cwd=_r, env=_env, capture_output=True, text=True)
    _a = _sp.run([sys.executable, "amend3.py"], cwd=_r, env=_env, capture_output=True, text=True)
    ok(_b.returncode == 0 and _a.returncode == 0, f"perturbed build ok: {(_b.stderr + _a.stderr)[-300:]}")
    _want = f"Site data updated <time datetime=2026-11-04>November 4, 2026</time> (latest source retrieval across all pages, <a href='{html.escape(_row[_si])}'>source</a>)"
    _pp = [os.path.join(_r, "docs", x) for x in ("index.html", "fl/2025/palm-beach-county/index.html", "fl/2025/orange-county/index.html", f"{SLUG}/index.html")]
    _miss = [x for x in _pp if not os.path.exists(x) or _want not in rd(x)]
    ok(not _miss, f"footer follows a moved retrieved_at on perturbed data (home, Palm Beach, Orange, Amendment 3): failing {[os.path.relpath(x, _r) for x in _miss]}")
finally:
    _sh.rmtree(_tmp, ignore_errors=True)

# --- amend3.check: the footer exemption covers only the data-computed <time>; a future year anywhere else in that paragraph, or a wrong date, is caught
import amend3 as _A3
_fp = re.search(r"<footer>.*?</footer>", ah, re.S).group(0)
ok(_A3.check(ah) == [], "real Amendment 3 page passes amend3.check")
ok(any("future-year" in e for e in _A3.check(ah.replace("(latest source retrieval across all pages,", "(latest source retrieval across all pages, through 2027,"))), "future year beside the footer date is still caught")
_bad = re.sub(r"<time datetime=[0-9-]+>[^<]*</time>", "<time datetime=2027-01-02>January 2, 2027</time>", _fp, 1)
ok(any("footer date" in e for e in _A3.check(ah.replace(_fp, _bad))), "a footer date that is not the data date (2027) is caught")
ok(any("footer date" in e for e in _A3.check(ah.replace(_fp, _fp.replace("Site data updated", "Data refreshed")))), "a missing footer date is caught")
ok(re.search(r"As of [A-Z][a-z]+ \d+, \d{4}, \d\d:\d\d ET \(latest retrieval of a source file used on this page; the footer's site data date covers every page, <a ", ah) is not None, "Amendment 3 'as of' is labelled as this page's sources, distinct from the site footer date")
ok("Municipal rates in " in rd("docs/fl/2025/palm-beach-county/index.html") and "Municipalities rates" not in "".join(rd(p) for p in county_pages), "caption reads 'Municipal rates', never 'Municipalities rates'")
ok(all(re.findall(r"<h2(?: id=[^ >]+)?>(County|School|Municipalities|Special districts)</h2>", rd(p)) == re.findall(r"<h2 id=[a-z-]+>(County|School|Municipalities|Special districts)</h2>", rd(p)) for p in county_pages), "every group heading, including Special districts, has an id")
print("FAILURES", len(FAIL)); sys.exit(1 if FAIL else 0)
