#!/usr/bin/env python3
"""OM-PAGE-REDO-001 checks on the generated site. Run from the repo root after build.py and amend3.py:
python3 tests/test_redo.py"""
import csv, glob, hashlib, html, io, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)
import redo, sources
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)
def rd(p): return open(p, encoding="utf-8").read()
pages = sorted(glob.glob("docs/**/*.html", recursive=True))
css = rd("docs/redo.css")

# --- fonts resolve locally
urls = re.findall(r"url\(([^)]+)\)", css)
ok(len(re.findall(r"@font-face", css)) >= 4 and urls and all(not re.match(r"['\"]?(https?:)?//", u) for u in urls), f"@font-face sources are local: {sorted(set(urls))}")
ok(all(os.path.isfile(os.path.join("docs", u.strip("'\""))) for u in urls), "every @font-face file exists under docs/fonts/")
ok(all(hashlib.sha256(open(f"docs/fonts/{n}", "rb").read()).digest() == hashlib.sha256(open(f"assets/fonts/{n}", "rb").read()).digest() for n in os.listdir("assets/fonts")), "docs/fonts/ are byte copies of Her?'s TTFs in assets/fonts/")
ok({f for f, _, _ in redo.FONTS} == {"Inter", "Space Grotesk"}, "Inter and Space Grotesk are both self-hosted")
ext = [p for p in pages + ["docs/style.css", "docs/redo.css"] if re.search(r"fonts\.(googleapis|gstatic)\.com|use\.typekit|fonts\.bunny|@import", rd(p))]
ok(not ext, f"no external font URLs or CSS imports anywhere: {ext[:3]}")
chart_pages = [p for p in pages if "chart-svg" in rd(p)]
ok(len(chart_pages) >= 3, f"Her? charts inlined on {len(chart_pages)} pages")
bad = [p for p in chart_pages if re.search(r"<img[^>]+\.svg", rd(p)) or "<metadata>" in rd(p) or not all(f in rd(p) for f in ("font-family=\"'Inter', sans-serif\"",))]
ok(not bad, f"charts are inline SVG text (not <img>, so they use the @font-face fonts), metadata stripped: {bad[:3]}")
for p in chart_pages:
    h = rd(p); fams = set(re.findall(r'font-family="([^"]+)"', h))
    if not all(re.match(r"'(Inter|Space Grotesk)'", f) for f in fams): ok(False, f"{p}: chart font families not self-hosted: {fams}")
ok(all(len(set(re.findall(r'\sid="([^"]+)"', rd(p)))) == len(re.findall(r'\sid="([^"]+)"', rd(p))) for p in chart_pages), "SVG ids are unique per page (350 and 720 copies prefixed)")

# --- history downloads beside each body page (spec items 15 and 17)
hist = sorted(glob.glob("docs/fl/history/*-county/*/index.html"))
ok(len(hist) == 134, f"{len(hist)} history body pages (67 counties x county, school)")
missing, unparse = [], []
for p in hist:
    d = os.path.dirname(p)
    for n in ("index.csv", "index.json"):
        if not os.path.isfile(os.path.join(d, n)): missing.append(os.path.join(d, n))
    try:
        rows = list(csv.DictReader(open(f"{d}/index.csv", newline="", encoding="utf-8"))); j = json.load(open(f"{d}/index.json"))
        if not rows or rows != j["rows"] or j["source"]["commit"][:7] != "7c1a525": unparse.append(d)
        h = rd(p)
        if "href='/" + d[5:] + "/index.csv'" not in h or "href='/" + d[5:] + "/index.json'" not in h: unparse.append(d + " (no links)")
    except Exception as e: unparse.append(f"{d}: {e}")
ok(not missing, f"index.csv and index.json beside every history page: missing {missing[:3]}")
ok(not unparse, f"every index.csv / index.json parses, matches, and is linked from its page: {unparse[:3]}")
al = list(csv.DictReader(open("docs/fl/history/alachua-county/county/index.csv", newline="")))
ok(any(r["year"] == "1996" and r["component"] == "operating" and r["millage"] == "9.25" for r in al), "Alachua county 1996 operating = 9.25 in index.csv (matches EDR sheet=1996!G7)")

# --- pin
lock = json.load(open("data/SOURCES.lock")); hl = [f for f in lock["files"] if f["path"] == "data/history/fl_millage_history.csv"]
ok(len(hl) == 1 and hl[0]["repo"] == "hazeydata/openmillage" and hl[0]["commit"].startswith("7c1a525") and hl[0]["source_path"] == "data/fl_millage_history.csv", "history CSV pinned in data/SOURCES.lock to hazeydata/openmillage@7c1a525")
ok(hl and hashlib.sha256(open(hl[0]["path"], "rb").read()).hexdigest() == hl[0]["sha256"] == "0d74a1f09ccc579bfe459ce0d309fc8c94139998d7775106a425e4f213041869", "history CSV sha256 matches the lock and the 7c1a525 file")
ok(sources.read_lock() is not None, "sources.read_lock accepts the lock with the history entry")

# --- slots (history chart, history line, credit) are present, marked, and filled from the source files
ah = rd("docs/fl/history/alachua-county/county/index.html")
fig = re.search(r"<figure class=hero id=history-chart data-slot=history-chart data-src='/fl/history/alachua-county/county/index.json'>(.*?)</figure>", ah, re.S)
ok(fig and "chart-svg" in fig.group(1) and "her-history-multiples-350/720-dark.svg" in fig.group(1), "Alachua history-chart slot holds Her?'s history-multiples (350 + 720)")
ok(all(re.search(r"<figure class=hero id=history-chart data-slot=history-chart data-src='[^']+index.json'>", rd(p)) for p in hist), "every history page has the marked history-chart slot")
line = re.search(r"<p data-slot=history-line>(.*?)</p>", ah, re.S)
want = html.escape("Alachua County's county and school board countywide rate, for example, fell from 21.2 mills in 1997 to 13.9 in 2025.†", quote=True)
ok(line and want in line.group(1), "Alachua history-line slot holds the final 21.2 -> 13.9 sentence (copy afab3f2)")
ok(all("<p data-slot=history-line>" in rd(p) for p in hist), "every history page has the marked history-line slot")
ok(not any(re.search(r"ON HOLD|\{\{KEY_NUMBER|Pending re-cut", rd(p)) for p in pages), "no ON HOLD boxes or KEY_NUMBER placeholders left")
CREDIT = "<p class=credit data-slot=credit>Built by Fred Hazelton and his team of AI bots. Spot a problem? <a href='https://github.com/hazeydata/openmillage-site/issues'>Tell us</a> and we&#x27;ll fix it in public.</p>"
CONTACT_A = "<a href='mailto:fred@hazeydata.ai'>fred@hazeydata.ai</a>"
ok(all(CONTACT_A in re.search(r"<footer>.*?</footer>", rd(p), re.S).group(0) for p in pages), f"Spec R1: footer mailto fred@hazeydata.ai on every page ({len(pages)} pages)")
ok("fred@hazeydata.ai" in rd("docs/llms.txt") and "mail.grokbot.com" not in rd("docs/llms.txt"), "Spec R1: llms.txt contact is fred@hazeydata.ai")
ok(all(CREDIT in re.search(r"<footer>.*?</footer>", rd(p), re.S).group(0) for p in pages), f"credit line, with 'Tell us' linking to the site issues, in every footer ({len(pages)} pages)")
idx = rd("docs/index.html")
ok(CREDIT.replace(" class=credit data-slot=credit", "") in idx.split("<footer>")[0], "credit line is also the 4th lede paragraph on home")

# --- copy verbatim from content/copy.md
plain = lambda h: html.unescape(re.sub(r"<[^>]+>", "", h))
src_copy = rd("content/copy.md")
for needle in [redo.HEADLINE] + [re.sub(r"\[(.+?)\]\([^)]+\)", r"\1", p) for p in redo.LEDE] + [re.sub(r"\*\*", "", b) for b in redo.HOWTO]:
    if needle not in plain(idx): ok(False, f"home copy missing verbatim: {needle[:60]!r}")
ok(f"<h1>{html.escape(redo.HEADLINE)}</h1>" in idx and redo.HEADLINE in src_copy, "home h1 is Lindsay's headline")
ok(redo.INTRO["The stack (county pages)"] in plain(rd("docs/fl/2025/alachua-county/index.html")), "county page has the county stack intro verbatim")
amd = plain(rd("docs/fl/amendment-3/index.html"))
ok(redo.INTRO["Before you vote (ballot measure numbered 3 page)"] in amd and redo.INTRO["Who sets what"] in amd, "amendment page has 'Before you vote' and 'Who sets what' verbatim")

# --- canonical URLs
canon = [re.search(r"<link rel=canonical href='([^']+)'>", rd(p)) for p in pages]
ok(all(c and c.group(1).startswith("https://openmillage.com/") for c in canon), "every canonical is https://openmillage.com/...")
ok(not any(re.search(r"https?://(www\.)?openmillage\.(github\.io|com\.)|http://openmillage\.com", rd(p)) for p in pages), "no non-canonical openmillage hosts")
sm = rd("docs/sitemap.xml"); ok("https://openmillage.com/fl/history/alachua-county/county/" in sm, "history pages are in the sitemap")

# --- layout markers (meta 9911d28, Variation B)
ah3 = rd("docs/fl/2025/alachua-county/index.html")
ok(ah3.index("class=stack") < ah3.index("<details class=all>") and "<summary>See all rates</summary>" in ah3, "county page: stack card before collapsed 'See all rates'")
ok("--col:720px" in css and "--cyan:#5FC4D6" in css and "--bg:#03070F" in css, "layout tokens from layout-spec (720 col, #5FC4D6, #03070F)")

# --- build14 review MUSTS (Tobias, 2026-10-23)
am = rd("docs/fl/amendment-3/index.html")
w = am.index("<h2 id=who-sets-what>")
ok(am.find("<details class=all><summary>See all rates</summary>", w) > w and not re.search(r"<section id=", am[w:am.find("<details class=all>", w)]), "M1 amendment: every county section sits inside one 'See all rates' details after Who sets what")
d0 = am.find("<details class=all>", w); d1 = am.find("</details><h2 id=get-the-data>", d0)
ok(d1 > d0 and am.count("<section id=", d0, d1) == am.count("<section id="), "M1 amendment: all county sections are inside the collapse")
ok("<h1>Florida 2025 adopted millage baseline</h1>" in am, "M2 amendment h1 is 'Florida 2025 adopted millage baseline'")
ok(am.index("<figure class=hero") < am.index("<p class=label>") and am.index("<figure class=hero") < am.index("<blockquote class=official>"), "M2 amendment: p.label and blockquote.official come after figure.hero")
ok(re.search(r"<main id=main><h1>[^<]+</h1><figure class=hero.*?</figure><div class=lede>", idx, re.S) is not None, "M3 home order is h1, figure.hero, .lede")
ok(not re.search(r"<p class=lead>\d+ official rates", idx) and idx.index("<div class=lede>") < idx.index("<p class=sources>"), "M3 home: the '... official rates' paragraph is not between h1 and hero")
c = idx.index("<h2 id=counties>")
ok(idx.startswith("<details class=all><summary>See all counties</summary>", c + len("<h2 id=counties>Counties</h2>")) and idx.index("<ul class=counties>") > c and idx.index("</ul></details>", c) > idx.index("<ul class=counties>"), "M4 home: county list inside 'See all counties' details")
ok("SpaceGrotesk" in css and "font-family:'Space Grotesk';font-weight:700" not in css, "nit: no Space Grotesk 700 @font-face")
ok(re.search(r"<main id=main><p class=kicker>Ballot measure numbered 3 · <a [^>]+>November 3, 2026</a></p><h1>Florida 2025 adopted millage baseline</h1>", am) is not None, "AC13 amendment kicker precedes h1")
import json as _j, glob as _g
def ac6(rows, h):
    """Errors for one county page: each of the 4 layers renders a value or '— no value in data'."""
    st = h[h.find("<div class=stack"):h.find("<p class=muted>One layer per taxing authority", h.find("<div class=stack"))]
    names = re.findall(r"<div class=who>(.*?)<small>", st); errs = []
    if not st: return ["no stack"]
    for bt, ph in (("county", "County"), ("school_district", "School district")):
        lr = [r for r in rows if r["body_type"] == bt]
        if not lr:
            if not re.search(rf"<div class=who>{ph}<small>[^<]*</small></div><div class=r>— no value in data", st): errs.append(f"{bt}: no placeholder")
        lab = {"county": "County ·", "school_district": "School district ·"}[bt]
        cw = [r for r in lr if r["levy_scope"] == "countywide" and r["rate_kind"] == "adopted"]
        for r in (cw or lr):
            pat = rf"<small>{lab}[^<]*</small>" + (rf"<span class=badge>not an adopted rate: {r['rate_kind']}</span>" if not cw else "") + rf"</div><div class=r>{re.escape(format(float(r['rate']), '.4f'))} <a href="
            if not re.search(pat, st): errs.append(f"{bt}: {r['taxing_body']} {r['rate']} not rendered")
    mu = {r["taxing_body"] for r in rows if r["body_type"] == "municipality" and r["rate_kind"] == "adopted"}
    sdl = [r for r in rows if r["body_type"] == "special_district" and r["rate_kind"] == "adopted"]
    if (f"Cities ({len(mu)})" if mu else "Cities<small>") not in st: errs.append("cities")
    if (f"Special district levies ({len(sdl)})" if sdl else "Special district levies<small>") not in st: errs.append("special district levies")
    if re.search(r"<div class=r>0(\.0+)?[ <]", st): errs.append("zero shown")
    return errs
bad = []; npages = 0
for f in sorted(_g.glob("docs/api/v1/fl/2025/*.json")):
    if f.endswith("-baseline.json"): continue
    rows = _j.load(open(f)); npages += 1
    e = ac6(rows, rd(f"docs/fl/2025/{os.path.basename(f)[:-5]}-county/index.html"))
    if e: bad.append((os.path.basename(f), e))
ok(npages == len(_g.glob("docs/fl/2025/*-county/index.html")) and not bad, f"AC6 all {npages} county and split pages render every layer, value or '— no value in data' ({bad[:3]})")
_dr = _j.load(open("docs/api/v1/fl/2025/duval.json")); _dh = rd("docs/fl/2025/duval-county/index.html")
ok(any(r["body_type"] == "county" for r in _dr) and "not an adopted rate: aggregate_effective" in _dh and "11.0123" in _dh, "AC6 Duval county row shown with the not-adopted flag")
_mut = re.sub(r"<div class=layer><div class=who>Duval County[^<]*<small>.*?</div></div>", "", _dh, count=1, flags=re.S)
ok(_mut != _dh and ac6(_dr, _mut), "AC6 mutant: dropping Duval's county row from the stack makes the check fail")
for _sp in ("flagler-st-johns", "flagler-volusia", "gilchrist-levy", "manatee-sarasota"):
    ok(rd(f"docs/fl/2025/{_sp}-county/index.html").count("— no value in data") >= 2, f"AC6 split page {_sp} shows county and school placeholders")
# --- AC2: no raw hex in redo.css outside the token block (layout-spec)
_root = re.search(r":root\{[^}]*\}", css).group(0)
_spec = set(re.findall(r"#[0-9A-Fa-f]{6}", re.search(r":root\{[^\n]*", open("/workspace/tmp/om-redo-meta/cycles/2026-10-23-page-redo/layout-spec.md").read()).group(0))) if os.path.exists("/workspace/tmp/om-redo-meta/cycles/2026-10-23-page-redo/layout-spec.md") else None
ok(not re.findall(r"#[0-9A-Fa-f]{3,8}\b", css.replace(_root, "")), "AC2 redo.css has no raw hex outside the :root token block")
ok(set(re.findall(r"#[0-9A-Fa-f]{6}", _root)) == {"#03070F", "#0A1628", "#13243D", "#1E3352", "#E8EEF5", "#9FB3C8", "#5FC4D6", "#155140"} and (_spec is None or set(re.findall(r"#[0-9A-Fa-f]{6}", _root)) <= _spec), "AC2 token block hex = layout-spec tokens only")
# --- AC4 (Spec R1): CSS swap, one SVG visible, hidden one display:none, unique ids, each with text alternative
for _p in ("docs/index.html", "docs/fl/amendment-3/index.html", "docs/fl/2025/alachua-county/index.html"):
    _x = rd(_p); _ids = re.findall(r"\sid=['\"]?([^'\" >]+)", _x)
    ok(len(_ids) == len(set(_ids)), f"AC4 no duplicate ids in {_p}")
    ok(all(re.search(r"role=img aria-label='[^']+'", m) for m in re.findall(r"<div class=chart-[md][^>]*>", _x)) and _x.count("<div class=chart-m") == _x.count("<div class=chart-d") >= 1, f"AC4 each chart copy has its own text alternative in {_p}")
ok(".chart-d{display:none}" in css and "@media(min-width:768px){.chart-m{display:none}.chart-d{display:block}}" in css, "AC4 CSS: below 768 only chart-m, at >=768 only chart-d (hidden one display:none); rendered check at 390/767/768/1440 in tests/ac4_render.js")
_h = os.environ.get("OM_A3_HEIGHT_390")
if _h: ok(int(_h) <= 1.5 * 3757, f"AC12 amendment height at 390 ({_h}px) within 1.5x of mock 3757px")
print("FAILURES", len(FAIL)); sys.exit(1 if FAIL else 0)
