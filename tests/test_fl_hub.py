#!/usr/bin/env python3
"""OM-FL-COVERAGE-001 Phase 2: the Florida hub /fl/, the re-pinned FL special-district data (district_wide WMD rows) on county and
body pages, /fl/ breadcrumbs, sitemap and reproducibility. Every check names the spec AC it covers (13-22). Counts are computed from
the pinned data and the status file, never hard-coded. Run from the repo root after build.py, amend3.py and statepages.py:
python3 tests/test_fl_hub.py"""
import csv, glob, hashlib, html, json, os, re, shutil, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "scripts")); os.chdir(ROOT)
import sources, site_chrome as sc
import repin_lock as R
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)
def rd(p): return open(p, encoding="utf-8").read()
def csvrows(p): return list(csv.DictReader(open(p, newline="", encoding="utf-8")))
BASE = "https://openmillage.com"
C = sources.FL_HUB_COPY
HUB = "docs/fl/index.html"
slug = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
rows = sources.load_rows(); cov = sources.coverage(rows)
STATUS = csvrows(sources.STATUS_FILE)
OPEN = [r for r in STATUS if r["status"] != sources.PARTIAL]
PARTIAL = [r for r in STATUS if r["status"] == sources.PARTIAL]
SD_RAW = [r for r in csvrows(sources.SD_FILE) if r["body_type"] == "special_district"]
ALT_RAW = [r for r in csvrows(sources.ALT_FILE) if r["body_type"] == "special_district"]
# The rows this ticket added: district_wide (R1) rows, marked in the data itself (TACD file: mapping_confirmation; alt file: note)
NEW = [r for r in SD_RAW if (r.get("mapping_confirmation") or "").startswith("district_wide (R1)")] + [r for r in ALT_RAW if (r.get("note") or "").startswith("district_wide (R1)")]
NEW_C = sorted({r["county"] for r in NEW})
print(f"computed: {len(NEW)} district_wide rows in {len(NEW_C)} counties ({', '.join(NEW_C)}); open {[r['county'] for r in OPEN]}; partial {[r['county'] for r in PARTIAL]}")
def main_of(h): return h.split("<main id=main>", 1)[1].split("</main>", 1)[0]
def text(h): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()

# ---------------- AC13: SOURCES.lock re-pin ----------------
PIN = "9d1254726131ae7ccb22dff7d7890081b4f72773"
CHANGED = {sources.SD_FILE, sources.ALT_FILE, sources.STATUS_FILE}
lock = sources.read_lock()
pinned = {f["path"] for f in lock["files"] if f["commit"] == PIN}
ok(pinned == CHANGED and all(hashlib.sha256(open(f["path"], "rb").read()).hexdigest() == f["sha256"] for f in lock["files"]),
   f"AC13 exactly the {len(CHANGED)} changed FL special-district files are pinned to openmillage@{PIN[:8]} and every sha256 matches: {sorted(pinned)}")
ok(rd(sources.LOCK) == json.dumps(json.load(open(sources.LOCK)), indent=1) + "\n", "AC13 lock file keeps the repin_lock.py format (json indent=1 + newline)")
with tempfile.TemporaryDirectory(prefix="om-fl-hub-repin-") as t:
    prod, site = os.path.join(t, "prod"), os.path.join(t, "site")
    os.makedirs(os.path.join(prod, "d")); os.makedirs(os.path.join(site, "data"))
    g = lambda *a: subprocess.run(["git", "-C", prod, *a], capture_output=True, text=True, check=True).stdout.strip()
    g("init", "-q"); g("config", "user.email", "t@example.invalid"); g("config", "user.name", "t")
    for n, v in (("a", b"id,rate\nx,0.5\n"), ("b", b"id,rate\ny,1.0\n")): open(os.path.join(prod, "d", n + ".csv"), "wb").write(v)
    g("add", "."); g("commit", "-qm", "c1"); c1 = g("rev-parse", "HEAD")
    open(os.path.join(prod, "d", "a.csv"), "ab").write(b"z,0.7\n"); open(os.path.join(prod, "d", "b.csv"), "ab").write(b"w,2.0\n")
    g("commit", "-qam", "c2"); c2 = g("rev-parse", "HEAD")
    lk = {"files": []}
    for n in ("a", "b"):
        b = subprocess.run(["git", "-C", prod, "show", f"{c1}:d/{n}.csv"], capture_output=True, check=True).stdout
        open(os.path.join(site, "data", n + ".csv"), "wb").write(b)
        lk["files"].append({"path": f"data/{n}.csv", "repo": "x/y", "commit": c1, "source_path": f"d/{n}.csv", "sha256": hashlib.sha256(b).hexdigest()})
    open(os.path.join(site, "data/SOURCES.lock"), "w").write(json.dumps(lk, indent=1) + "\n")
    before = rd(os.path.join(site, "data/SOURCES.lock"))
    cwd = os.getcwd(); os.chdir(site)
    try:
        import io, contextlib
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc_noise = R.main(["--product", prod, "--commit", c2, "--group", "tx,history", "--write"])
            rc_unknown = R.main(["--product", prod, "--commit", c2, "--data-change", "data/a.csv", "data/nope.csv", "--write"])
            after_unknown = rd("data/SOURCES.lock")
            rc_ok = R.main(["--product", prod, "--commit", c2, "--data-change", "data/a.csv", "--write"])
        new = json.load(open("data/SOURCES.lock"))
        a_new, b_new = new["files"]
        ok(rc_unknown == 1 and after_unknown == before, "AC13 --data-change refuses a path that is not a lock entry and writes nothing")
        ok(rc_ok == 0 and a_new["commit"] == c2 and a_new["sha256"] == hashlib.sha256(open("data/a.csv", "rb").read()).hexdigest() and rd("data/a.csv").endswith("z,0.7\n")
           and b_new == lk["files"][1] and rd("data/b.csv") == "id,rate\ny,1.0\n",
           "AC13 --data-change re-pins only the listed path (file copied from the commit, commit + sha256 updated); the other entry and its file are unchanged")
        ok(R.classify(b"id,rate\nx,0.5\n", b"id,rate\nx,0.5\nz,0.7\n")[0] == "other", "AC13 the noise-only path still refuses an added row (unchanged)")
    finally:
        os.chdir(cwd)

# ---------------- AC14: county pages ----------------
def county_page(c): return rd(f"docs/fl/2025/{slug(c)}-county/index.html")
bad14 = []
for r in NEW:
    h = county_page(r["county"]); sd = h.split("<h2 id=special-districts>", 1)[-1]
    if not (f"href='{html.escape(r['source_url'])}'" in sd and r["unit"] == "mills" and "<th scope=col class=num>Rate (mills)</th>" in sd and f"<td class=num>{float(r['rate']):.4f}</td>" in sd and f"<code title='{r['sha256']}'>" in sd
            and f"/fl/special-districts/{sources.sd_slug(r['body_id'])}/" in sd):
        bad14.append((r["county"], r["body_id"], r["levy_component"]))
ok(NEW and not bad14, f"AC14 the {len(NEW_C)} counties' pages render all {len(NEW)} new rows with rate, source link, sha256 and body-page link: missing {bad14}")
reasons = {r["county"]: r["reason"] for r in STATUS}
def more(v): return f"<details class=reason-more><summary>{html.escape(C['reason_more'])}</summary><p>{html.escape(v)}</p></details>"
ok(PARTIAL and all(html.escape(C["partial_line"].format(reason=sources.plain_reason(r["county"], reasons[r["county"]]))) + "</p>" + more(reasons[r["county"]]) in county_page(r["county"])
                   and "<p>Independent special districts: not yet sourced" not in county_page(r["county"]) for r in PARTIAL),
   f"AC14 partial counties {[r['county'] for r in PARTIAL]} show the partial-coverage line (FL_HUB_COPY) and their rows, not the not-yet-sourced block")
ok(sorted(cov["not_yet_sourced"]) == sorted(r["county"] for r in OPEN) and all("<p>Independent special districts: not yet sourced." in county_page(r["county"]) for r in OPEN)
   and not any(r["county"] in NEW_C for r in OPEN),
   f"AC14 the {len(OPEN)} open counties from the status file ({', '.join(r['county'] for r in OPEN)}) keep 'not yet sourced'")
home = rd("docs/index.html")
lis = re.findall(r"<li><a href='/fl/2025/[^']+'>([^<]+) County, FL</a>(.*?)</li>", home)
ok(sorted(c for c, rest in lis if C["partial_badge"] in rest) == sorted(cov["partial"]) and sorted(c for c, rest in lis if "special districts not yet sourced" in rest) == sorted(cov["not_yet_sourced"]),
   "AC14 home county list: the not-yet-sourced badge is on the open counties only, the partial badge on the partial counties only")

# ---------------- AC15: body pages ----------------
bodies = sources.fl_bodies(rows, display=sc.display_name)
bad15 = []
for r in NEW:
    h = rd(f"docs/fl/special-districts/{sources.sd_slug(r['body_id'])}/index.html")
    if f"href='/fl/2025/{slug(r['county'])}-county/'" not in h.split("<table class=sd-rates", 1)[1].split("</table>", 1)[0]: bad15.append((r["body_id"], r["county"]))
wmd = sorted({sources.sd_slug(r["body_id"]) for r in NEW})
ok(not bad15, f"AC15 body pages {wmd} list every new county in their rate table: missing {bad15}")
bcb = [r for r in NEW if r["levy_component"] == "big_cypress_basin"]
sf = rd("docs/fl/special-districts/sfwmd/index.html")
ok(bcb and all(r["body_id"] == "fl-sfwmd-special_district" for r in bcb) and f"<td role=cell>{html.escape(C['levy_labels']['big_cypress_basin'])}</td>" in sf
   and sc.label("big_cypress_basin") == C["levy_labels"]["big_cypress_basin"] and all(r["levy_component"] == "big_cypress_basin" for r in bcb)
   and any(r["levy_component"] == "big_cypress_basin" for r in json.load(open("docs/fl/special-districts/sfwmd/index.json"))),
   "AC15 SFWMD shows the big_cypress_basin component for Collier with its copy label; the data value is unchanged in index.json")
pages = glob.glob("docs/fl/special-districts/*/index.html")
old_bodies = {r["body_id"] for r in SD_RAW + ALT_RAW if r not in NEW}
ok(len(pages) == len(bodies) and {r["body_id"] for r in NEW} <= old_bodies, f"AC15 FL special-district body page count is {len(pages)} == bodies in the data, and the new rows add no body (count unchanged)")
with_rows = sorted({r["county"] for r in SD_RAW + ALT_RAW})
hub = rd(HUB); hm = main_of(hub)
wr = C["with_rows"].format(n=len(with_rows), total=cov["total"], csv=len({r["county"] for r in SD_RAW}), alt=len(set(with_rows) - {r["county"] for r in SD_RAW}))
ok(cov["with_rows"] == len(with_rows) and html.escape(wr) in hm, f"AC15 hub 'counties with rows' is computed: {len(with_rows)} ({wr})")

# ---------------- AC16: hub links ----------------
county_dirs = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob("docs/fl/2025/*/index.html"))
links = re.findall(r"href='([^']+)'", hm)
c_links = sorted({l.split("/")[3] for l in links if re.fullmatch(r"/fl/2025/[^/]+/", l)})
ok(os.path.exists(HUB) and c_links == county_dirs, f"AC16 hub links all {len(county_dirs)} FL county pages")
ok(all(l in links for l in ("/fl/special-districts/", "/fl/amendment-3/", "/fl/rolled-back-rate/")) and all(os.path.exists(f"docs{l}index.html") for l in ("/fl/special-districts/", "/fl/amendment-3/", "/fl/rolled-back-rate/")),
   "AC16 hub links /fl/special-districts/, /fl/amendment-3/ and /fl/rolled-back-rate/ (all built)")
ok(not re.search(r"href='/fl/(2025|history)/'", hub) and not os.path.exists("docs/fl/2025/index.html") and not os.path.exists("docs/fl/history/index.html"),
   "AC16 hub does not link /fl/2025/ or /fl/history/ (OQ-7: no index there)")

# ---------------- AC17: coverage table, recomputed independently ----------------
labels = sorted({r["county"] for r in csvrows(sources.BASE_FILE)})
census = {r["name"].removesuffix(" County") for r in csvrows(sources.COUNTIES_FILE)}
tacd_c = {r["county"] for r in SD_RAW}
multi = sorted(set(labels) - census)
def want_status(c):
    n = len({r["body_id"] for r in SD_RAW + ALT_RAW if r["county"] == c})
    nb = sources.plural(n, *C["body"])
    if c not in census: return "multi", C["status_multi"] if all(len(l.split("/")) == 2 for l in multi) else C["status_multi_more"]
    st = next((r for r in STATUS if r["county"] == c), None)
    if st and st["status"] != sources.PARTIAL: return "open", C["status_open"].format(reason=f"Note {NOTE_N[c]}")
    if st: return "partial", C["status_partial"].format(bodies=nb, reason=f"Note {NOTE_N[c]}")
    if not n: return "none", C["status_none"]
    if c not in tacd_c:
        ag = {r["source_agency"] for r in ALT_RAW if r["county"] == c}
        kind = "wmd" if all("Water Management District" in a for a in ag) else "pa" if all("County Property Appraiser" in a for a in ag) else None
        return "sourced_alt", C["status_sourced_alt"].format(bodies=nb, kind=C["alt_kind"][kind])
    return "sourced", C["status_sourced"].format(bodies=nb)
NOTE_N = {c: i + 1 for i, c in enumerate(c for c in labels if c in {r["county"] for r in STATUS})}  # numbered in table order
trs = re.findall(r"<tr data-status=(\w+)><td(?: class=hub-county)?><a href='/fl/2025/([^']+)/'>([^<]+)</a></td><td>((?:[^<]|<a href='#note-\d+'>Note \d+</a>)*)</td></tr>", hm)
show = lambda c: " / ".join(c.split("/"))  # display only: space around the slash of a two-county city label
undisplay = {show(c): c for c in labels}
got = [(undisplay.get(html.unescape(name), html.unescape(name)), k, text(t)) for k, _, name, t in trs]
ok([g[0] for g in got] == labels and all((k, t) == want_status(c) for c, k, t in got), f"AC17 one row per county label ({len(labels)}), each status recomputed from the CSVs + status file: mismatches {[(c, k) for c, k, t in got if (k, t) != want_status(c)][:3]}")
kinds = {k for _, k, _ in got}
def hub_note(c):
    m = re.search(rf"<div class=footnote id=note-{NOTE_N[c]}><p>(.*?)</p>(<details class=reason-more>.*?</details>)</div>", hm)
    return m and (html.unescape(m.group(1)), m.group(2))
ok({"sourced", "sourced_alt", "partial", "open"} <= kinds and all(C["status_open"].format(reason=f"Note {NOTE_N[r['county']]}") in [t for _, _, t in got] for r in OPEN)
   and all(f"<a href='#note-{NOTE_N[r['county']]}'>Note {NOTE_N[r['county']]}</a>" in hm for r in STATUS)
   and all(hub_note(r["county"]) == (f"Note {NOTE_N[r['county']]} ({r['county']}): {sources.plain_reason(r['county'], r['reason'])}", more(r["reason"])) for r in STATUS),
   f"AC17 statuses present: sourced, sourced_alt (alt-source only, marked), partial, open; every status-file county's cell links its numbered note (plain reason + recorded reason verbatim) ({sorted(kinds)})")
alt_wmd = [c for c, k, t in got if k == "sourced_alt" and C["alt_kind"]["wmd"] in t]
ok(sorted(alt_wmd) == sorted(c for c in cov["alt_only"] if sources.alt_kinds()[c] == "wmd"), f"AC17 water-management-district-document counties are marked distinctly: {alt_wmd}")
# The recorded reasons from the status file are quoted verbatim (spec AC17) and may cite printed figures from the source file; they are
# removed before checking that the hub itself shows no rate.
hm_own = hm
for r in STATUS: hm_own = hm_own.replace(html.escape(r["reason"]), " ")
ok(" mills" not in hm_own and not re.search(r"\d\.\d{3,}", hm_own) and "<svg" not in hm and "<img" not in hm and "<figure" not in hm and not re.search(r"(?i)\b(rank|estimate|total rate)\b", text(hm_own)),
   "AC17 hub shows no rate, total, rank, estimate or chart (OQ-5)")
ok("absent is not zero" in text(hm).lower(), "AC17 hub carries the spec line 'absent is not zero' (any case)")
ok(C["absent"] in text(hm), f"AC17 hub visible text carries the wired absent string exactly: {C['absent']!r}")
# AC17 (amended, Lucille 2 Nov 17 2:20 PM ET): hub cell = short status + note marker; plain note under the table; the recorded reason
# word for word in a <details>. For every status-file county, the exact recorded reason (CSV, read here independently) must be the
# text inside a <details class=reason-more> on the committed docs/fl/index.html and on that county's committed page.
def reason_more_texts(h):
    out = []
    for d in re.findall(r"<details class=reason-more>(.*?)</details>", h, flags=re.S):
        out.append(html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<summary>.*?</summary>", "", d, count=1, flags=re.S))))
    return out
_hub_rm = reason_more_texts(rd(HUB))
_bad17 = [(r["county"], p) for r in csvrows(sources.STATUS_FILE)
          for p in (HUB, f"docs/fl/2025/{slug(r['county'])}-county/index.html")
          if r["reason"] not in (_hub_rm if p == HUB else reason_more_texts(rd(p)))]
ok(STATUS and not _bad17,
   f"AC17 (amended, Lucille 2 Nov 17 2:20 PM ET): the exact recorded reason of each status-file county ({', '.join(r['county'] for r in STATUS)}) is the text of a <details class=reason-more> on {HUB} and on the county's page: missing {_bad17}")

# ---------------- AC18: head, sitemap, llms.txt ----------------
def head(h):
    t = html.unescape(re.search(r"<title>(.*?)</title>", h).group(1)); m = re.search(r"<meta name=description content='([^']*)'>", h); d = html.unescape(m.group(1)) if m else None
    lds = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h.split("</head>")[0])]
    return t, d, lds
ht, hd, hl = head(hub); mt, md, _ = head(home)
titles = {head(rd(p))[0] for p in glob.glob("docs/**/*.html", recursive=True) if p != HUB and "<title>" in rd(p)}
ok(ht == C["title"] and hd == C["desc"] and ht != mt and hd != md and ht not in titles, "AC18 hub title and description come from FL_HUB_COPY and differ from the home page's (title unique site-wide)")
ok(f"<link rel=canonical href='{BASE}/fl/'>" in hub, "AC18 canonical https://openmillage.com/fl/")
types = [x["@type"] for x in hl]
bl = next((x for x in hl if x["@type"] == "BreadcrumbList"), {})
ds = next((x for x in hl if x["@type"] == "Dataset"), {})
ok(sorted(types) == ["BreadcrumbList", "Dataset"] and [i["item"] for i in bl.get("itemListElement", [])] == [BASE + "/", BASE + "/fl/"]
   and ds.get("url") == BASE + "/fl/" and ds.get("license") == "https://creativecommons.org/licenses/by/4.0/" and ds.get("creator", {}).get("name") == "Hazey Data"
   and set(ds.get("isBasedOn", [])) == {r["source_url"] for r in SD_RAW + ALT_RAW} and "Absent is not zero" in ds.get("description", ""),
   "AC18 BreadcrumbList JSON-LD (OpenMillage > Florida) and the Dataset JSON-LD pattern (url, licence, creator, isBasedOn = special-district sources)")
from analytics import GOATCOUNTER_TAG
ok(hub.split("</head>")[0].count(GOATCOUNTER_TAG) == 1, "AC18 GoatCounter tag once in <head>")
sm = rd("docs/sitemap.xml"); llms = rd("docs/llms.txt")
ok(sm.count(f"<loc>{BASE}/fl/</loc>") == 1 and C["llms_line"].format(url=f"{BASE}/fl/") in llms, "AC18 /fl/ is in sitemap.xml once and in llms.txt")

# ---------------- AC19: /fl/ breadcrumbs ----------------
CRUMB = f"<nav aria-label=Breadcrumb class=crumbs><a href='/'>OpenMillage</a> &rsaquo; <a href='/fl/'>{html.escape(C['crumb'])}</a> &rsaquo; "
fam = {"county": "docs/fl/2025/*/index.html", "special-district": "docs/fl/special-districts/**/index.html", "history": "docs/fl/history/**/index.html",
       "amendment-3": "docs/fl/amendment-3/index.html", "rolled-back-rate": "docs/fl/rolled-back-rate/index.html"}
counts, bad19 = {}, []
for k, pat in fam.items():
    ps = sorted(set(glob.glob(pat, recursive=True))); counts[k] = len(ps)
    bad19 += [p for p in ps if CRUMB not in rd(p)]
under = [p for p in glob.glob("docs/fl/**/*.html", recursive=True) if p != HUB]
ok(not bad19 and sum(counts.values()) == len(under), f"AC19 every page under docs/fl/ (except the hub itself) starts its breadcrumb with OpenMillage > Florida (/fl/): {counts}; failing {bad19[:3]}")
ok(counts["county"] == len(county_dirs) and counts["special-district"] == len(bodies) + 1 and counts["amendment-3"] == 1 and counts["rolled-back-rate"] == 1,
   f"AC19 family counts match the data: county {counts['county']}, special-district {counts['special-district']} (bodies + hub), history {counts['history']}")
ok("href='/fl/'" in main_of(home), "AC19 the home page links /fl/")
linking = [p for p in glob.glob("docs/**/*.html", recursive=True) if re.search(r"<a href=['\"](https://openmillage\.com)?/fl/['\"]", rd(p))]  # <a> links (the hub's own canonical <link> is not a link to it)
ok(len(linking) == sum(counts.values()) + 1 and len(linking) >= 293, f"AC19 pages with an <a> link to /fl/: {len(linking)} (= FL pages + home)")

# ---------------- AC20: copy block ----------------
src = rd("sources.py")
ok("# Copy from the writing pass (Lindsay, OM-FL-COVERAGE-001 fl-hub-copy.md, sha256 4f26f9bf), wired key for key; by-eye r1 layout fixes\n# from Ann applied" in src
   and "# Copy from the writing pass (Lindsay, OM-FL-COVERAGE-001 fl-hub-copy-r2.md, sha256 0e133591, section 4)" in src.split("NOTE_UNDER_TABLE = {")[0]
   and "placeholder pending Lindsay" not in src.split("NOTE_UNDER_TABLE = {")[0].rsplit("\n\n", 1)[-1],
   "AC20 FL_HUB_COPY is marked as the writing-pass copy with Ann's r1 fixes; the display-only NOTE_UNDER_TABLE notes are marked as writing-pass r2 copy (no placeholder marker)")
# Hub visible text: remove every FL_HUB_COPY string (formatted with computed values), the computed coverage sentence and the county
# names; what remains is punctuation only, so no reader-facing hub string lives outside the copy block.
rest = text(hm)
pieces = [C["h1"], C["intro"], C["absent"], C["sections_h2"], *C["sections"].values(), C["table_h2"], C["table_caption"], C["th_county"], C["th_sd"], wr,
          sources.coverage_sentence(cov)] + [t for _, _, t in got] + [show(c) for c in labels] + [C["reason_more"]] + [r["reason"] for r in STATUS] \
         + [f"Note {NOTE_N[r['county']]} ({r['county']}): {sources.plain_reason(r['county'], r['reason'])}" for r in STATUS]
for p in sorted(pieces, key=len, reverse=True): rest = rest.replace(text(html.escape(p)), " ")
ok(not re.sub(r"[\s.,:;()]", "", rest), f"AC20 every hub string in <main> comes from FL_HUB_COPY or is computed: leftover {rest[:120]!r}")
bm = rd("build.py").split("def fl_hub():", 1)[1].split("fl_hub()", 1)[0]
ok(not re.search(r"""(?<![\w\[])["'][A-Z][a-z]+ [a-z]+[^"']*["']""", bm), "AC20 the hub generator holds no reader-facing literal sentence")

# ---------------- AC21: sitemap == built pages ----------------
locs = re.findall(r"<loc>([^<]+)</loc>", sm)
canon = set()
for p in glob.glob("docs/**/*.html", recursive=True):
    m = re.search(r"<link rel=canonical href='([^']+)'>", rd(p)); url = BASE + "/" + p[len("docs/"):-len("index.html")]
    if m and m.group(1) == url: canon.add(url)
ok(len(locs) == len(set(locs)) == len(canon) and set(locs) == canon, f"AC21 sitemap <loc> count {len(locs)} == built (self-canonical) page count {len(canon)}, same set")

# ---------------- Round 2: writing pass (A) and by-eye r1 fixes (B) ----------------
# A3 status_multi is chosen by the data: "two counties" only when every city label spans exactly 2 counties
ok(sources.status_multi(["A/B", "C/D"]) == C["status_multi"] and sources.status_multi(["A/B", "C/D/E"]) == C["status_multi_more"] and sources.status_multi([]) == C["status_multi_more"]
   and C["status_multi_more"] == "Covers a city in more than one county. See each county's page.",
   "A3 status_multi when every label spans 2 counties, else the writer's fallback status_multi_more (synthetic labels)")
ok(multi and sources.multi_labels(cov) == multi and all(k == "multi" and t == sources.status_multi(multi) for c, k, t in got if c in multi)
   and (C["status_multi"] if all(len(l.split("/")) == 2 for l in multi) else C["status_multi_more"]) in [t for _, _, t in got],
   f"A3 the hub's city rows ({', '.join(multi)}) use the status_multi string the data selects")
# A4 reason_plain: shown only for a listed county whose recorded reason is unchanged; else the verbatim reason
RP = C["reason_plain"]
ok(sorted(RP) == sorted(r["county"] for r in STATUS) and all(sources.plain_reason(r["county"], r["reason"]) == RP[r["county"]]["text"]
   and RP[r["county"]]["for_sha256"] == hashlib.sha256(r["reason"].encode("utf-8")).hexdigest() for r in STATUS),
   "A4 reason_plain covers the status-file counties, each written for the pinned recorded reason (sha256 matches)")
ok(sources.plain_reason("Nowhere", "some recorded reason") == "some recorded reason", "A4 fallback: a county not in reason_plain shows its verbatim reason")
ok(all(sources.plain_reason(r["county"], r["reason"] + " (changed)") == r["reason"] + " (changed)" for r in STATUS),
   "A4 fallback: a changed recorded reason (sha256 no longer matches) shows the new verbatim reason, never the stale plain line")
# A5/B2 the reason_more <details> (verbatim recorded reason) on the hub and on each status-file county's page
ok(all(hm.count(more(r["reason"])) == 1 and more(r["reason"]) in county_page(r["county"]) for r in STATUS),
   f"A5/B2 <details class=reason-more> with the verbatim recorded reason on the hub and on the county pages of {[r['county'] for r in STATUS]}")
ok(all(html.escape(sources.plain_reason(r["county"], r["reason"])) in county_page(r["county"]).split(more(r["reason"]))[0].rsplit("<p", 1)[-1] for r in STATUS)
   and all(county_page(r["county"]).index("<p>Independent special districts: not yet sourced.") < county_page(r["county"]).index(more(r["reason"])) for r in OPEN),
   "B2 county pages: the plain reason sits right before its reason_more <details>; open counties keep the not-yet-sourced line before it")
ok(all(f"<p>Independent special districts: not yet sourced.</p><p>{html.escape(C['not_yet_line'])}</p><p>{html.escape(sources.plain_reason(r['county'], r['reason']))}</p>{more(r['reason'])}" in county_page(r["county"]) for r in OPEN)
   and not any(C["not_yet_line"] in html.unescape(county_page(r["county"])) for r in PARTIAL),
   f"B2 open county pages ({', '.join(r['county'] for r in OPEN)}): not_yet_line, then the plain reason, then the reason_more <details>; partial counties don't carry not_yet_line")
# B1 hub county column
cells = re.findall(r"<tr data-status=\w+><td[^>]*>(.*?)</td>", hm)
ok(len(cells) == len(labels) and not any(" County, FL" in c for c in cells) and all(f">{html.escape(show(c))}</a>" in hm for c in multi) and all(" / " in show(c) for c in multi),
   "B1 hub county cells carry no ' County, FL'; two-county city rows read 'A / B' (display only)")
css = rd("docs/style.css")
ok(sc.FL_NOWRAP == "#fl-coverage .hub-county{white-space:nowrap}" and sc.FL_NOWRAP in css and "#fl-coverage td a,.sd-body a{overflow-wrap:normal}" in css
   and len(re.findall(r"<td class=hub-county>", hm)) == len(labels) - len(multi),
   "B1/B4 CSS: hub county cells nowrap (not the city rows), county links and county-page body links never break mid-word")
# By-eye r2 R1 (Ann, layout-r2.md): on every county page's special-district table the unit is in the header "Rate (mills)" and each rate
# cell is the bare number, byte-identical to the data rate formatted as before minus the " mills" suffix; the body cells get the tighter
# <= 40rem padding; the sha <code> follows the source link after a breakable space in a cell with no nowrap, so it stacks under the link
# when the column is narrow. (Headless check at 375/390 px: tests/browser_fl_layout.py, not CI.)
sd_pages = {p: rd(p) for p in sorted(glob.glob("docs/fl/2025/*-county/index.html")) if "<td class=sd-body>" in rd(p)}
sd_rows_all = [r for r in rows if r["state"] == "FL" and r["year"] == "2025" and r["body_type"] == "special_district"]
def sd_trs(h): return re.findall(r"<tr><td class=sd-body>.*?</tr>", h)
def sd_head(h): return re.findall(r"<caption>Independent special districts in [^<]*</caption><thead><tr>(.*?)</tr></thead>", h)
bad_r1 = []
for p, h in sd_pages.items():
    want = sorted(f"<td class=num>{float(r['rate']):.4f}</td>" for r in sd_rows_all if f"/{slug(r['county'])}-county/" in p)
    got = sorted(re.search(r"<td class=num>[^<]*</td>", tr).group(0) for tr in sd_trs(h))
    if sd_head(h) != ["<th scope=col>Taxing body</th><th scope=col>Levy</th><th scope=col class=num>Rate (mills)</th><th scope=col>Source</th>"] or not want or got != want \
       or any(" mills" in re.sub(r"<[^>]+>", "", tr) for tr in sd_trs(h)) or not all(re.search(r">source</a> <code title='[0-9a-f]{64}'>[0-9a-f]{8}</code></td></tr>$", tr) for tr in sd_trs(h)):
        bad_r1.append(p)
ok(len(sd_pages) >= 3 and all(f"/{c}-county/" in " ".join(sd_pages) for c in ("collier", "levy", "liberty")) and not bad_r1 and all(r["unit"] == "mills" for r in sd_rows_all),
   f"R1 county special-district tables ({len(sd_pages)} pages incl. Collier, Levy, Liberty): header 'Rate (mills)', each rate cell the exact bare value, no ' mills' in any row, sha after a breakable space: bad {bad_r1}")
ok(sc.FL_SD_TIGHT == ".sd-body,.sd-body~td" and "@media (max-width:40rem){table.tx-rates th,table.tx-rates td,.sd-body,.sd-body~td{padding:.5rem .35rem}}" in css
   and not re.search(r"(sd-body~td|sd-body~\.num|code)[^{}]*\{[^}]*nowrap", css),
   "R1 CSS: the county special-district body cells use the tighter <= 40rem padding, and no nowrap rule reaches their Source cell or sha (the sha stacks under the link)")
ok("details.cgroup summary,.reason-more summary{cursor:pointer;padding:.6rem 0;min-height:44px}" in css and not re.search(r"reason-more[^{}]*summary[^{}]*\{[^}]*(display|list-style)", css),
   "r2 should-fix CSS: reason-more summaries get min-height 44px and cursor:pointer and keep display list-item (default marker)")
# B3 display-only numbered notes for the district_wide water-management-district rows
NU = sources.NOTE_UNDER_TABLE
TOK = ("district_wide", "(R1)", "also_cited", "less-than-county-wide blank")
ok(not any(t in v for v in NU.values() for t in TOK), "B3 the NOTE_UNDER_TABLE strings hold none of the raw tokens")
bad3 = []
for (c, bid), v in NU.items():
    raw = next(r for r in ALT_RAW if r["county"] == c and r["body_id"] == bid)
    api = [r for r in json.load(open(f"docs/api/v1/fl/2025/{slug(c)}.json")) if r["body_id"] == bid]
    for p in (f"docs/fl/2025/{slug(c)}-county/index.html", f"docs/fl/special-districts/{sources.sd_slug(bid)}/index.html"):
        h = rd(p); sec = h.split("<h2 id=special-districts>", 1)[-1].split("<h2 id=rates>", 1)[-1]  # county page: special-district section; body page: rates
        mg = sources.NOTE_MERGED.get(bid); vv = mg[1] if mg and c in mg[0] and "special-districts" in p else v  # body page of NWFWMD: the shared note
        m = re.search(rf"<p class=footnote id=note-(\d+)>Note \1: {re.escape(html.escape(vv))}</p>", sec)
        tb = sec.split("<table", 1)[1].split("</table>", 1)[0]
        if not (m and f"<small class=muted><a href='#note-{m.group(1)}'>Note {m.group(1)}</a></small>" in tb and html.escape(raw["note"]) not in h
                and sec.index("</table>") < m.start()): bad3.append(p)
    if not (api and all(r["note"] == raw["note"] for r in api)): bad3.append(f"api {c}")
ok(len(NU) == 3 and not bad3, f"B3 Calhoun/Liberty (NWFWMD) and Clay (SJRWMD): the cell carries only a 'Note N' link to a numbered note under the table, on the county page and the body page; JSON keeps the data note: {bad3}")
# nwfwmd_merged (Lindsay, fl-hub-copy-r3.md sha256 c50d7d1e): ONE note on the NWFWMD body page, Calhoun and Liberty both point at it;
# the Calhoun and Liberty county pages keep their own r2 notes.
NWFWMD_MERGED = ("Resolution No. 957 sets 0.0207 of a mill for all of Calhoun County and all of Liberty County, both named in its county "
                 "list. The meeting-packet copy of Resolution 957 isn't signed. Signed Resolution No. 958, in the Northwest Florida Water "
                 "Management District's FY 2025-26 Adopted Budget, confirms it was adopted, and we cite that as a second source. Florida "
                 "DOR's Data Book 2025 also lists both counties at 0.0207 county-wide, with no rate for only part of either county.")
_nb = rd("docs/fl/special-districts/nwfwmd/index.html")
_notes = re.findall(r"<p class=footnote id=note-(\d+)>Note \1: (.*?)</p>", _nb)
_cells = re.findall(r"<small class=muted><a href='#note-(\d+)'>Note \1</a></small>", _nb)
_cty = {c: re.findall(rf"<p class=footnote id=note-\d+>Note \d+: (.*?)</p>", rd(f"docs/fl/2025/{slug(c)}-county/index.html")) for c in ("Calhoun", "Liberty")}
ok(len(_notes) == 1 and _notes[0][1] == html.escape(NWFWMD_MERGED) and len(_cells) == 2 and set(_cells) == {_notes[0][0]}
   and sources.NOTE_MERGED["fl-nwfwmd-special_district"][1] == NWFWMD_MERGED,
   f"B3b NWFWMD body page: exactly one note with the exact nwfwmd_merged text; the Calhoun and Liberty cells both point to it: {len(_notes)} notes, cells {_cells}")
ok(all(len(v) == 1 and v[0] == html.escape(NU[(c, "fl-nwfwmd-special_district")]) and v[0] != html.escape(NWFWMD_MERGED) for c, v in _cty.items()),
   "B3b the Calhoun and Liberty county pages still carry their own exact r2 notes (unmerged)")
# Raw tokens: none in the visible text of docs/fl/**/*.html and docs/index.html, outside <details class=reason-more> (the verbatim audit
# text, by design) and script / JSON-LD
def visible(h):
    h = re.sub(r"<details class=reason-more>.*?</details>", " ", h, flags=re.S)
    h = re.sub(r"<script\b.*?</script>", " ", h, flags=re.S); h = re.sub(r"<style\b.*?</style>", " ", h, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", " ", h))
vis_pages = sorted(glob.glob("docs/fl/**/*.html", recursive=True)) + ["docs/index.html"]
leak = [(p, t) for p in vis_pages for t in TOK if t in visible(rd(p))]
ok(HUB in vis_pages and len(vis_pages) == len(under) + 2 and not leak, f"B3 no raw token {TOK} in the visible text of {len(vis_pages)} pages (docs/fl/**, home): {leak[:5]}")
# B5 county pages link /fl/ instead of repeating the statewide coverage paragraph; /fl/ and home keep it
cps = sorted(glob.glob("docs/fl/2025/*/index.html")); sent = html.escape(sources.coverage_sentence(cov))
link = f"<p class=muted><a href='/fl/'>{html.escape(C['home_link'])}</a></p>"
ok(cps and all(link in rd(p) and sent not in rd(p) for p in cps) and sent in hm and sent in main_of(home),
   f"B5 all {len(cps)} county pages link /fl/ with home_link and drop the statewide paragraph; /fl/ and home keep it")

# ---------------- AC22: two builds byte-identical, no network ----------------
def build(tmp):
    for n in ("build.py", "sources.py", "amend3.py", "analytics.py", "site_chrome.py", "redo.py", "statepages.py", "amend3_config.json"): shutil.copy(n, tmp)
    for n in ("assets", "content", "data"): shutil.copytree(n, os.path.join(tmp, n))
    blocker = os.path.join(tmp, "nonet"); os.makedirs(blocker)
    open(os.path.join(blocker, "sitecustomize.py"), "w").write(
        "import socket\ndef _no(*a, **k): raise OSError('network disabled in build')\nsocket.socket.connect = _no\nsocket.create_connection = _no\nsocket.getaddrinfo = _no\n")
    env = dict(os.environ, PYTHONPATH=blocker, PYTHONDONTWRITEBYTECODE="1", DATA_GLOB="data/*.csv")
    rcs = [subprocess.run([sys.executable, s], cwd=tmp, env=env, capture_output=True, text=True) for s in ("build.py", "amend3.py", "statepages.py")]
    h = hashlib.sha256()
    for p in sorted(glob.glob(os.path.join(tmp, "docs/**/*"), recursive=True)):
        if os.path.isfile(p): h.update(os.path.relpath(p, tmp).encode()); h.update(open(p, "rb").read())
    return [r.returncode for r in rcs], h.hexdigest(), "".join(r.stderr for r in rcs)
with tempfile.TemporaryDirectory(prefix="om-fl-hub-a-") as a, tempfile.TemporaryDirectory(prefix="om-fl-hub-b-") as b:
    ra, rb = build(a), build(b)
    ok(ra[0] == rb[0] == [0, 0, 0] and ra[1] == rb[1], f"AC22 two builds (build.py, amend3.py, statepages.py) with the network disabled are byte-identical: rc {ra[0]} {rb[0]} {(ra[2] + rb[2])[-200:]}")

print(f"\nFAILURES {len(FAIL)}"); sys.exit(1 if FAIL else 0)
