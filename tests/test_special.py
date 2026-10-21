#!/usr/bin/env python3
"""OM-SITE-SPECIAL-DISTRICTS-001: FL 2025 independent special districts on county pages and JSON. Run from the repo root after
build.py and amend3.py: python3 tests/test_special.py"""
import csv, glob, html, json, os, re, shutil, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)
import sources
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)
API = "docs/api/v1/fl/2025"
def js(c): return json.load(open(f"{API}/{c}.json"))
def pg(c): return open(f"docs/fl/2025/{c}-county/index.html", encoding="utf-8").read()
SENT = "57 of 67 Florida counties checked against official sources; 46 have special-district rows."
NO_ROWS = "No special-district rows published yet for this county."
SPEC_NO_ROWS = ["Bradford", "Citrus", "Franklin", "Glades", "Hardee", "Highlands", "Nassau", "Okeechobee", "Polk", "Wakulla", "Walton"]
OPEN = ["Calhoun", "Clay", "Columbia", "Monroe", "Collier", "Sumter", "Gadsden", "Levy", "Taylor", "Liberty"]
CFTOD_SHA = "1f4e3b57663e35703d71d5338c0add294164c90813ef78275af7d978a9486a68"

def build_copy(mutate=None):
    tmp = tempfile.mkdtemp()
    for n in ("build.py", "sources.py", "amend3.py", "analytics.py", "amend3_config.json"): shutil.copy(n, tmp)
    shutil.copytree("data", os.path.join(tmp, "data"))
    if mutate: mutate(tmp)
    blocker = os.path.join(tmp, "nonet"); os.makedirs(blocker)
    open(os.path.join(blocker, "sitecustomize.py"), "w").write(
        "import socket\ndef _no(*a, **k): raise OSError('network disabled in build')\nsocket.socket.connect = _no\nsocket.create_connection = _no\nsocket.getaddrinfo = _no\n")
    env = dict(os.environ, PYTHONPATH=blocker, PYTHONDONTWRITEBYTECODE="1", DATA_GLOB="data/*.csv")
    r = subprocess.run([sys.executable, "build.py"], cwd=tmp, env=env, capture_output=True, text=True)
    return tmp, r

def append(path, line):
    return lambda t: open(os.path.join(t, path), "a").write(line)

lock = sources.read_lock()
rows = sources.load_rows(lock)
paths = {f["path"]: f for f in lock["files"]}
ok(set(paths) == {sources.BASE_FILE, sources.SD_FILE, sources.ALT_FILE, sources.STATUS_FILE}, "AC1 lock lists the four openmillage copies")
ok(all(f["repo"] == "hazeydata/openmillage" and re.fullmatch(r"[0-9a-f]{40}", f["commit"]) and re.fullmatch(r"[0-9a-f]{64}", f["sha256"]) for f in lock["files"]),
   "AC1 each lock entry has repo, 40-hex commit and 64-hex sha256")
tmp, r = build_copy(lambda t: open(os.path.join(t, sources.SD_FILE), "a").write("\n"))
ok(r.returncode != 0 and "sha256 mismatch" in r.stderr, "AC1 build fails when a data file differs from its lock sha256")
shutil.rmtree(tmp)
def bad_lock(t):
    p = os.path.join(t, sources.LOCK); l = json.load(open(p)); l["files"][0]["sha256"] = "0" * 64; json.dump(l, open(p, "w"))
tmp, r = build_copy(bad_lock)
ok(r.returncode != 0 and "sha256 mismatch" in r.stderr, "AC1 build fails when the lock sha256 is mutated")
shutil.rmtree(tmp)
tmp, r = build_copy(lambda t: shutil.copy(os.path.join(t, sources.BASE_FILE), os.path.join(t, "data/extra.csv")))
ok(r.returncode != 0 and "not listed" in r.stderr, "AC1 build fails when a data file is not listed in the lock")
shutil.rmtree(tmp)
tmp, r = build_copy()
ok(r.returncode == 0, "AC1 build succeeds with network disabled" + ("" if r.returncode == 0 else f": {r.stderr[-300:]}"))
src = open("build.py").read() + open("sources.py").read()
ok(not re.search(r"\b(urllib|requests|http\.client|socket|subprocess)\b", src), "AC1 build code imports no network or subprocess module")
wf = open(".github/workflows/build.yml").read()
ok(not re.search(r"\b(curl|wget|git clone|gh api|pip install)\b", wf), "AC1 CI workflow fetches nothing at build time")
ok("python3 tests/test_special.py" in wf, "CI runs tests/test_special.py")

n_base = len(list(csv.DictReader(open(sources.BASE_FILE)))); n_sd = len(list(csv.DictReader(open(sources.SD_FILE))))
n_alt = sum(r["body_type"] == "special_district" for r in csv.DictReader(open(sources.ALT_FILE)))
api_rows = [r for f in sorted(glob.glob(f"{API}/*.json")) if not os.path.basename(f).startswith("amendment-3") for r in json.load(open(f))]
ok((n_base, n_sd, n_alt) == (601, 161, 4) and n_base + n_sd + n_alt == len(rows) == len(api_rows) == 766,
   f"AC2 {n_base} + {n_sd} + {n_alt} = {n_base + n_sd + n_alt}; loaded {len(rows)}; JSON API {len(api_rows)}")

pas = [r for r in js("pasco") if r["body_type"] == "county" and r["levy_component"] == "operating" and r["rate_kind"] == "adopted"]
ok(len(pas) == 1 and len(pas[0]["additional_sources"] or []) == 1 and pas[0]["rate"] == "7.4042"
   and "25-348" in pas[0]["additional_sources"][0]["source_url"] and re.fullmatch(r"[0-9a-f]{64}", pas[0]["additional_sources"][0]["sha256"]),
   "AC3 one Pasco county operating row with the Resolution 25-348 cite as its single additional source")
def pasco_rate(t):
    p = os.path.join(t, sources.ALT_FILE); s = open(p).read().replace(",adopted,7.4042,mills,Pasco", ",adopted,7.4043,mills,Pasco")
    open(p, "w").write(s); relock(t)
def relock(t):
    import hashlib
    p = os.path.join(t, sources.LOCK); l = json.load(open(p))
    for f in l["files"]: f["sha256"] = hashlib.sha256(open(os.path.join(t, f["path"]), "rb").read()).hexdigest()
    json.dump(l, open(p, "w"))
tmp, r = build_copy(pasco_rate)
ok(r.returncode != 0 and "differs" in r.stderr, "AC3 build fails when the Pasco cite rate differs from the base row")
shutil.rmtree(tmp)

keys = [sources.key(r) for r in rows]
ok(len(keys) == len(set(keys)), "AC4 no duplicate (county, body_id, levy_component, rate_kind)")
def dup(t):
    p = os.path.join(t, sources.SD_FILE); ls = open(p).read().splitlines(); open(p, "w").write("\n".join(ls + [ls[1]]) + "\n"); relock(t)
tmp, r = build_copy(dup)
ok(r.returncode != 0 and "duplicate key" in r.stderr, "AC4 a duplicated row fails the build instead of being dropped")
shutil.rmtree(tmp)

sd = [r for r in api_rows if r["body_type"] == "special_district"]
ok(len(sd) == 165 and all(re.match(r"^https?://\S+$", r["source_url"]) and re.fullmatch(r"[0-9a-f]{64}", r["sha256"]) for r in sd),
   f"AC5 all {len(sd)} special_district rows have an http(s) source_url and 64-hex sha256")
def no_sha(t):
    p = os.path.join(t, sources.SD_FILE); s = open(p).read().replace("6f6d8dfbc4466961fa1c45531cb734ae1f0863873188cf6810622827ec700861", "", 1)
    open(p, "w").write(s); relock(t)
tmp, r = build_copy(no_sha)
ok(r.returncode != 0 and "without source_url or sha256" in r.stderr, "AC5 a special-district row without sha256 fails the build")
shutil.rmtree(tmp)

ok(all(r["levy_component"] not in ("mstu", "dependent_special_district") and r["rate_kind"] == "adopted" for r in sd), "AC6 no mstu or dependent row from the special-district files")
agg_csv = [{k: r[k] for k in sources.BASE_KEYS} for r in csv.DictReader(open(sources.BASE_FILE)) if r["rate_kind"] == "aggregate_effective"]
agg_api = [{k: r[k] for k in sources.BASE_KEYS} for r in api_rows if r["rate_kind"] == "aggregate_effective"]
ok(len(agg_csv) == 55 and sorted(map(str, agg_csv)) == sorted(map(str, agg_api)), f"AC6 the {len(agg_api)} aggregate_effective rows keep their 17 base values")

cov = sources.coverage(rows)
with_rows = cov["counties_with_rows"]
for c in with_rows:
    h = pg(re.sub(r"[^a-z0-9]+", "-", c.lower()).strip("-")); sec = h.split("Special districts</h2>", 1)[-1]
    srows = [r for r in rows if r["county"] == c and r["body_type"] == "special_district"]
    if not ("Special districts</h2>" in h and all(html.escape(r["taxing_body"]) in sec and f"title='{r['sha256']}'>{r['sha256'][:8]}</code>" in sec and html.escape(r["source_url"]) in sec
            and (r["levy_component"] == "all_components_combined" or html.escape(r["levy_component"]) in sec) and f"<td style='text-align:right;white-space:nowrap'>{float(r['rate']):.4f} {r['unit']}</td>" in sec for r in srows)):
        FAIL.append(f"AC7 {c}")
ok(not [f for f in FAIL if f.startswith("AC7")], f"AC7 {len(with_rows)} county pages carry a Special districts section with name, levy, rate, source link and sha256")

main_or = json.load(open("tests/fixtures/orange-main.json")); now_or = js("orange")
ok(all(list(r)[:17] == sources.BASE_KEYS and list(r)[17:] == sources.EXTRA_KEYS for r in api_rows), "AC8 every JSON row has the 17 base keys in order, then the additive keys")
ok([{k: r[k] for k in sources.BASE_KEYS} for r in now_or if r["body_type"] != "special_district"] == main_or, "AC8 existing orange.json rows keep their base values")

cf = [r for r in now_or if r["body_id"] == "fl-cftod-special_district"]
oh = pg("orange")
ok(len(cf) == 1 and cf[0]["taxing_body"] == "Central Florida Tourism Oversight District" and "display_rate" not in cf[0] and cf[0]["levy_component"] == "all_components_combined"
   and cf[0]["rate"] == "12.4236" and cf[0]["sha256"] == CFTOD_SHA and "formerly Reedy Creek" in cf[0]["note"] and "contentFileID=416847" in cf[0]["source_url"],
   "AC9 CFTOD JSON row golden")
ok(any("<td>Central Florida Tourism Oversight District<br>" in tr and re.findall(r"<td>([^<]*)</td>", tr)[0] == "(operating + debt, combined)"
   and "<td style='text-align:right;white-space:nowrap'>12.4236 mills</td>" in tr for tr in oh.split("<tr>")) and "formerly Reedy Creek" in oh
   and "contentFileID=416847" in oh and f"title='{CFTOD_SHA}'" in oh, "AC9 CFTOD on the Orange page")
ch = [r for r in js("alachua") if r["taxing_body"] == "Children's Trust of Alachua County"]
ok(len(ch) == 1 and ch[0]["rate"] == "0.4500" and ch[0]["sha256"].startswith("6f6d8dfb") and ch[0]["sha256"].endswith("0861")
   and "Children&#x27;s Trust of Alachua County" in pg("alachua") and "0.4500 mills" in pg("alachua"), "AC10 Children's Trust of Alachua County golden")
ok(len(now_or) == 20 and len(main_or) == 17 and any(r["body_type"] == "special_district" for r in now_or), f"AC11 orange.json has {len(now_or)} rows")

sentence = sources.coverage_sentence(cov)
pages = glob.glob("docs/fl/2025/*-county/index.html")
ok(all(sentence in open(p).read() for p in pages + ["docs/index.html"]), f"AC12 computed coverage sentence on index and all {len(pages)} county pages")
ok((cov["checked"], cov["total"]) == (57, 67) and cov["with_rows"] + len(cov["no_rows"]) == cov["checked"], f"AC12 computed {sentence}")
ok(all(NO_ROWS in pg(c.lower()) and "0.0000" not in pg(c.lower()).split("Special districts</h2>")[1].split("<p>Source:")[0] for c in cov["no_rows"]),
   f"AC13 the {len(cov['no_rows'])} computed no-rows counties show the fixed string: {cov['no_rows']}")
ok(sorted(cov["not_yet_sourced"]) == sorted(OPEN) and all("not yet sourced" in pg(c.lower()) and NO_ROWS not in pg(c.lower()) and "<th>Taxing body</th><th>Levy</th><th>Rate</th>" not in pg(c.lower()) for c in OPEN)
   and all(c in open("docs/index.html").read().split("<p>Independent special districts not yet sourced")[1].split("</p>")[0] for c in OPEN), "AC14 the 10 open counties are listed as not yet sourced on the index and their pages")
ok("aggregate_effective</em> are not adopted rates" in oh and "aggregate_effective</em>" not in oh.split("Special districts</h2>")[1], "AC15 aggregate_effective note still renders")
ok(not re.search(r"(?i)<t[dh]>(total|sum)", oh.split("Special districts</h2>")[1].split("<p>Source:")[0]), "AC15 no special-district totals row")

ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', oh).group(1))
pl = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', pg("pasco")).group(1))
ok(cf[0]["source_url"] in ld["isBasedOn"] and pas[0]["additional_sources"][0]["source_url"] in pl["isBasedOn"], "AC16 JSON-LD isBasedOn includes special-district and additional source URLs")
idx = open("docs/index.html").read(); llms = open("docs/llms.txt").read()
idesc = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', idx).group(1))["description"]
ok(all("independent special district" in t.lower() and sentence in t and "not zero" in t for t in (idesc, llms)), "AC16 index description and llms.txt mention special districts, coverage, absent is not zero")
ok(all(k in llms for k in sources.BASE_KEYS + sources.EXTRA_KEYS), "AC16 llms.txt names the 17 base keys and the additive keys")

def snap(d):
    out = {}
    for p in sorted(glob.glob(os.path.join(d, "docs/**/*"), recursive=True) + glob.glob(os.path.join(d, "docs/.nojekyll"))):
        if os.path.isfile(p): out[os.path.relpath(p, d)] = re.sub(rb"<lastmod>[^<]*</lastmod>", b"", open(p, "rb").read())
    return out
tmp, r = build_copy(); t2, r2 = build_copy()
ok(r.returncode == 0 and r2.returncode == 0 and snap(tmp) == snap(t2), f"AC19 two builds produce byte-identical docs/ ({len(snap(tmp))} files) apart from lastmod")
shutil.rmtree(tmp); shutil.rmtree(t2)
po = pg("polk"); i = [po.find(s) for s in ("Special districts</h2>", sentence, NO_ROWS)]
ok(-1 not in i and i == sorted(i), "visual: Polk order is heading, coverage, empty-state line")
print("FAILURES", len(FAIL)); sys.exit(1 if FAIL else 0)
