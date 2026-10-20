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
JS_TYPES = {"", "text/javascript", "application/javascript", "module"}
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
            self.hits.append((list(self.stack), (a.get("type") or "").strip().lower()))
        if tag not in VOID: self.stack.append(tag)
    def handle_startendtag(self, tag, attrs): self.handle_starttag(tag, attrs); tag in VOID or self.stack.pop()
    def handle_endtag(self, tag):
        if tag in self.stack:
            while self.stack.pop() != tag: pass

def good(path):
    f = TagFinder(); f.feed(open(path, encoding="utf-8").read()); f.close()
    return any("head" in st and not INERT & set(st) and "body" not in st and ty in JS_TYPES for st, ty in f.hits)

walked = sorted(os.path.relpath(os.path.join(d, n), "docs") for d, _, fs in os.walk("docs") for n in fs if n.endswith(".html"))
pages = sorted(os.path.relpath(p, "docs") for p in glob.glob("docs/**/*.html", recursive=True))
ok(pages == walked and walked, f"glob finds every .html page a recursive walk finds ({len(walked)})")
locs = re.findall(r"<loc>([^<]+)</loc>", open("docs/sitemap.xml", encoding="utf-8").read())
ok(len(locs) > 0 and len(walked) == len(locs), f"page count {len(walked)} equals sitemap URL count {len(locs)}")
# docs/ page set equals a fresh build.py + amend3.py run in a temp dir
tmp = tempfile.mkdtemp()
for n in ("build.py", "amend3.py", "analytics.py", "amend3_config.json"): shutil.copy(n, tmp)
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

def ci_steps(path):
    """Jobs -> list of (job_keys, step_keys). Uses PyYAML if installed, otherwise a strict line parse of this
    workflow's layout (2-space jobs, 4-space job keys, '      - ' steps, 8-space step keys). Comments are dropped."""
    try:
        import yaml
        y = yaml.safe_load(open(path))
        return [(j, s) for j in (y.get("jobs") or {}).values() for s in (j.get("steps") or [])]
    except ImportError: pass
    out, job, step, injobs = [], None, None, False
    for line in open(path):
        if re.match(r"\s*#", line) or not line.strip(): continue
        line = line.rstrip("\n")
        if re.match(r"^\S", line): injobs = line.startswith("jobs:"); continue
        if not injobs: continue
        if m := re.match(r"^  (\S[^:]*):\s*$", line): job = {}; continue
        if job is None: continue
        if m := re.match(r"^    ([\w-]+):\s*(.*)$", line): job[m[1]] = m[2]; continue
        if m := re.match(r"^      - ([\w-]+):\s*(.*)$", line): step = {m[1]: m[2]}; out.append((job, step)); continue
        if (m := re.match(r"^        ([\w-]+):\s*(.*)$", line)) and step is not None: step[m[1]] = m[2]
    return out
steps = [(j, s) for j, s in ci_steps(".github/workflows/build.yml") if str(s.get("run", "")).strip() == "python3 tests/test_analytics.py"]
ok(len(steps) == 1 and all(k not in d for j, s in steps for d in (j, s) for k in ("if", "continue-on-error")),
   f"build.yml has exactly one unconditional step 'run: python3 tests/test_analytics.py' (no if:/continue-on-error on step or job); found {len(steps)}")
print("FAILURES", len(FAIL)); sys.exit(1 if FAIL else 0)
