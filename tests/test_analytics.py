#!/usr/bin/env python3
"""OM-SITE-ANALYTICS-001: every .html page under docs/ must carry the cookieless GoatCounter tag as an executable
script inside <head> (not in a comment, <noscript> or <template>); docs/ must hold exactly the pages build.py and
amend3.py emit; CI must run this test unconditionally. Run from the repo root after build.py and amend3.py:
    python3 tests/test_analytics.py"""
import glob, html.parser, os, re, shutil, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); os.chdir(ROOT)
from analytics import GOATCOUNTER_TAG
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)
# pinned literals, independent of the constant
SITE = "https://openmillage.goatcounter.com/count"; JS = "https://gc.zgo.at/count.js"
ok(f"data-goatcounter='{SITE}'" in GOATCOUNTER_TAG and f"src='{JS}'" in GOATCOUNTER_TAG, "constant carries the pinned site code and count.js")
JS_TYPES = {"", "text/javascript", "application/javascript"}  # classic scripts only: no module, no nomodule
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
INERT = {"noscript", "template"}

class TagFinder(html.parser.HTMLParser):
    """Tracks enclosing elements; records each GoatCounter script with the elements around it. Comments never reach
    handle_starttag, so a commented-out tag is not counted."""
    def __init__(self):
        super().__init__(convert_charrefs=True); self.stack, self.hits = [], []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and a.get("data-goatcounter") == SITE and a.get("src") == JS:
            self.hits.append((list(self.stack), (a.get("type") or "").strip().lower(), "nomodule" in a))
        if tag not in VOID: self.stack.append(tag)
    def handle_startendtag(self, tag, attrs): self.handle_starttag(tag, attrs); tag in VOID or self.stack.pop()
    def handle_endtag(self, tag):
        if tag in self.stack:
            while self.stack.pop() != tag: pass

def good(path):
    f = TagFinder(); f.feed(open(path, encoding="utf-8").read()); f.close()
    return any("head" in st and not INERT & set(st) and "body" not in st and ty in JS_TYPES for st, ty, nomod in f.hits if not nomod)

walked = sorted(os.path.relpath(os.path.join(d, n), "docs") for d, _, fs in os.walk("docs") for n in fs if n.endswith(".html"))
pages = sorted(os.path.relpath(p, "docs") for p in glob.glob("docs/**/*.html", recursive=True))
ok(pages == walked and walked, f"glob finds every .html page a recursive walk finds ({len(walked)})")
locs = re.findall(r"<loc>([^<]+)</loc>", open("docs/sitemap.xml", encoding="utf-8").read())
ok(len(locs) > 0 and len(walked) == len(locs), f"page count {len(walked)} equals sitemap URL count {len(locs)}")
# docs/ page set equals a fresh build.py + amend3.py run in a temp dir
tmp = tempfile.mkdtemp()
for n in ("build.py", "sources.py", "amend3.py", "analytics.py", "amend3_config.json"): shutil.copy(n, tmp)
shutil.copytree("data", os.path.join(tmp, "data"))
env = dict(os.environ, DATA_GLOB="data/*.csv"); env.pop("OUT", None)
r1 = subprocess.run([sys.executable, "build.py"], cwd=tmp, env=env, capture_output=True, text=True)
r2 = subprocess.run([sys.executable, "amend3.py"], cwd=tmp, env=env, capture_output=True, text=True)
fresh = sorted(os.path.relpath(os.path.join(d, n), os.path.join(tmp, "docs")) for d, _, fs in os.walk(os.path.join(tmp, "docs")) for n in fs if n.endswith(".html"))
ok(r1.returncode == 0 and r2.returncode == 0 and fresh == walked, f"docs/ page set equals a fresh build ({len(fresh)} pages); missing {sorted(set(fresh)-set(walked))[:5]} extra {sorted(set(walked)-set(fresh))[:5]}")
shutil.rmtree(tmp)
bad = [p for p in walked if not good(os.path.join("docs", p))]
ok(not bad, f"all {len(walked)} pages carry the tag as an executable script in <head> (no comment/noscript/template)" + (f"; bad: {bad[:5]}" if bad else ""))
ok("fl/amendment-3/index.html" in walked and "fl/amendment-3/index.html" not in bad, "amendment-3 page carries the tag")

def ci_yaml(path):
    """PyYAML view, or None when PyYAML is not installed: (triggers, [(job, step)])."""
    try: import yaml
    except ImportError: return None
    y = yaml.safe_load(open(path))
    on = y.get("on", y.get(True))  # YAML 1.1 reads a bare 'on' key as True
    trig = set(on) if isinstance(on, dict) else set([on] if isinstance(on, str) else on or [])
    return trig, [(j, s) for j in (y.get("jobs") or {}).values() for s in (j.get("steps") or [])]
def ci_lines(path):
    """Strict line parse of this workflow's layout (2-space jobs/triggers, 4-space job keys, '      - ' steps,
    8-space step keys; keys may be quoted). Comments are dropped. Same shape as ci_yaml."""
    K = r"[\"']?([\w-]+)[\"']?"
    trig, out, job, step, top = set(), [], None, None, None
    for line in open(path):
        if re.match(r"\s*#", line) or not line.strip(): continue
        line = line.rstrip("\n")
        if m := re.match(r"^" + K + r":", line): top = m[1]; job = step = None; continue
        if top == "on":
            if m := re.match(r"^  " + K + r":", line): trig.add(m[1])
            continue
        if top != "jobs": continue
        if re.match(r"^  \S[^:]*:\s*$", line): job, step = {}, None; continue
        if job is None: continue
        if m := re.match(r"^    " + K + r":\s*(.*)$", line): job[m[1]] = m[2]; step = None; continue
        if m := re.match(r"^      - " + K + r":\s*(.*)$", line): step = {m[1]: m[2]}; out.append((job, step)); continue
        if (m := re.match(r"^        " + K + r":\s*(.*)$", line)) and step is not None: step[m[1]] = m[2]
    return trig, out
def ci_summary(trig, pairs):
    hits = [(j, s) for j, s in pairs if str(s.get("run", "")).strip() == "python3 tests/test_analytics.py"]
    return ("push" in trig, len(hits), sorted({k for j, s in hits for d in (j, s) for k in d if k in ("if", "continue-on-error", "strategy")}))
WF = ".github/workflows/build.yml"
lines_view, yaml_view = ci_summary(*ci_lines(WF)), ci_yaml(WF)
ok(yaml_view is None or ci_summary(*yaml_view) == lines_view, f"line parser and PyYAML agree on build.yml: lines={lines_view} yaml={yaml_view and ci_summary(*yaml_view)}")
ok(lines_view == (True, 1, []), f"build.yml runs on push and has exactly one unconditional step 'run: python3 tests/test_analytics.py' (no if:/continue-on-error/strategy on step or job); got push,count,flags={lines_view}")
print("FAILURES", len(FAIL)); sys.exit(1 if FAIL else 0)
