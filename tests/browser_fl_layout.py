#!/usr/bin/env python3
"""OM-SITE-SPECIAL-ISD-001 LAYOUT (b)6: FL body-page county table at 375 px, measured in headless Chrome with the built CSS.
Not part of CI (needs Chrome). Run by hand from the repo root after the build:
    python3 tests/browser_fl_layout.py [--width N]   # default 375; CHROME=/path/to/chrome to override /usr/bin/google-chrome
Serves docs/ on 127.0.0.1 (every other host resolves to nothing), drives one headless Chrome over --remote-debugging-pipe with a
throwaway profile (closed in finally; Chrome's TMPDIR/TMP/TEMP and profile all live inside this script's own TemporaryDirectory), sets the viewport (default 375 px) and checks:
  table.scrollWidth <= wrapper.clientWidth (no horizontal scroll), one line box per td.num (no rate wraps), min text in <main> >= 12 px.
OM-FL-COVERAGE-001 by-eye r2 (Ann, R1 and the details should-fix), always at 375 and 390 px whatever --width is:
  county pages (Collier, Levy, Liberty): the special-district table's scrollWidth <= its wrapper's clientWidth, and every Source link
  and its sha <code> lies fully inside the viewport and inside the wrapper (nothing clipped or scrolled off), and each bare rate stays on one line;
  /fl/ and Columbia: every <details class=reason-more> summary is >= 44 px tall and keeps its marker (display list-item, text indented).
  --probe-flex also reports what `display:flex` on that summary would do to the marker (diagnostic only, no PASS/FAIL).
Nothing in docs/ is changed."""
import argparse, functools, http.server, json, os, signal, subprocess, sys, tempfile, threading, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
CHROME = os.environ.get("CHROME", "/usr/bin/google-chrome")
PAGES = ["fl/special-districts/sfwmd", "fl/special-districts/cftod", "fl/special-districts/sjrwmd"]
ap = argparse.ArgumentParser(); ap.add_argument("--width", type=int, default=375); ap.add_argument("--probe-flex", action="store_true")
ARGS = ap.parse_args(); WIDTH = ARGS.width
COUNTY_PAGES = ["fl/2025/collier-county", "fl/2025/levy-county", "fl/2025/liberty-county"]
SUMMARY_PAGES = ["fl", "fl/2025/columbia-county"]
COUNTY_WIDTHS = (375, 390)
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)

MEASURE = """new Promise(function(done){document.fonts.ready.then(function(){
var w=document.querySelector('.tablewrap'),t=w&&w.querySelector('table.sd-rates'),o={vw:window.innerWidth};
if(t){o.wrap=w.clientWidth;o.table=t.scrollWidth;var cp=t.querySelector('caption');o.cap=cp?cp.getBoundingClientRect().width:-1;o.tbl=t.getBoundingClientRect().width;o.rows=t.querySelectorAll('tbody tr').length;
o.num_lines=[].map.call(t.querySelectorAll('td.num'),function(td){var r=document.createRange();r.selectNodeContents(td);
var tops={};[].forEach.call(r.getClientRects(),function(q){if(q.width>0)tops[Math.round(q.top)]=1});return Object.keys(tops).length});}
var f=[].filter.call(document.querySelectorAll('main *'),function(e){return [].some.call(e.childNodes,function(n){return n.nodeType==3&&n.textContent.trim()})})
.filter(function(e){var s=getComputedStyle(e);return s.display!='none'&&s.visibility!='hidden'&&e.getClientRects().length&&e.getBoundingClientRect().left>-1000});
o.min_text_px=Math.min.apply(null,f.map(function(e){return parseFloat(getComputedStyle(e).fontSize)}));
o.doc_overflow=document.documentElement.scrollWidth>window.innerWidth;done(o);});})"""

COUNTY_MEASURE = """new Promise(function(done){document.fonts.ready.then(function(){
var vw=document.documentElement.clientWidth,o={vw:window.innerWidth,cw:vw};
var w=[].filter.call(document.querySelectorAll('.tablewrap'),function(e){return (e.getAttribute('aria-label')||'').indexOf('Independent special districts in')==0})[0];
if(!w){done(o);return;}var t=w.querySelector('table'),wr=w.getBoundingClientRect();o.wrap=w.clientWidth;o.table=t.scrollWidth;
o.head=[].map.call(t.querySelectorAll('thead th'),function(e){return e.textContent});
o.src=[].map.call(t.querySelectorAll('tbody tr'),function(tr){var td=tr.lastElementChild,a=td.querySelector('a'),c=td.querySelector('code');
return [a,c].map(function(e){if(!e)return null;var r=e.getBoundingClientRect();return {t:e.textContent,l:+r.left.toFixed(1),r:+r.right.toFixed(1),in:r.left>=0&&r.right<=vw&&r.left>=wr.left-0.5&&r.right<=wr.right+0.5&&r.width>0}})});
o.num_lines=[].map.call(t.querySelectorAll('tbody td.num'),function(td){var r=document.createRange();r.selectNodeContents(td);
var tops={};[].forEach.call(r.getClientRects(),function(q){if(q.width>0)tops[Math.round(q.top)]=1});return Object.keys(tops).length});
o.doc_overflow=document.documentElement.scrollWidth>window.innerWidth;done(o);});})"""
SUMMARY_MEASURE = """new Promise(function(done){document.fonts.ready.then(function(){
done([].map.call(document.querySelectorAll('details.reason-more>summary'),function(s){var r=s.getBoundingClientRect(),g=document.createRange();g.selectNodeContents(s);
var cs=getComputedStyle(s);return {h:+r.height.toFixed(1),display:cs.display,cursor:cs.cursor,indent:+(g.getBoundingClientRect().left-r.left).toFixed(1),
text_mid:+((g.getBoundingClientRect().top+g.getBoundingClientRect().bottom)/2-r.top).toFixed(1)}}));});})"""
FLEX_PROBE = "(function(){var st=document.createElement('style');st.textContent='details.reason-more>summary{min-height:44px;display:flex;align-items:center;cursor:pointer}';document.head.appendChild(st);return 0})()"

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

class Chrome:
    """Minimal DevTools client over --remote-debugging-pipe (stdlib only): one headless Chrome, one throwaway profile."""
    def __init__(self, profile, tmpdir):
        r1, w1 = os.pipe(); r2, w2 = os.pipe()  # we write w1 -> Chrome reads fd 3; Chrome writes fd 4 -> we read r2
        def child(): os.dup2(r1, 3); os.dup2(w2, 4)
        self.p = subprocess.Popen([CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
                                   "--disable-extensions", "--disable-background-networking", "--disable-component-update", "--disable-sync",
                                   "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1", "--remote-debugging-pipe", f"--user-data-dir={profile}", "about:blank"],
                                  pass_fds=(3, 4), close_fds=True, preexec_fn=child, start_new_session=True, env=dict(os.environ, TMPDIR=tmpdir, TMP=tmpdir, TEMP=tmpdir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(r1); os.close(w2)
        self.w, self.r, self.buf, self.n = os.fdopen(w1, "wb", 0), os.fdopen(r2, "rb", 0), b"", 0
        tid = self.call("Target.createTarget", url="about:blank")["targetId"]
        self.sid = self.call("Target.attachToTarget", targetId=tid, flatten=True)["sessionId"]
        self.call("Page.enable", session=True)
    def _read(self):
        while b"\0" not in self.buf:
            chunk = self.r.read(1 << 16)
            if not chunk: raise RuntimeError("chrome closed the pipe")
            self.buf += chunk
        msg, self.buf = self.buf.split(b"\0", 1)
        return json.loads(msg)
    def call(self, method, session=False, **params):
        self.n += 1
        m = {"id": self.n, "method": method, "params": params}
        if session: m["sessionId"] = self.sid
        self.w.write(json.dumps(m).encode() + b"\0")
        while True:
            r = self._read()
            if r.get("id") == self.n:
                if "error" in r: raise RuntimeError(f"{method}: {r['error']}")
                return r["result"]
    def goto(self, url, width, height):
        self.call("Emulation.setDeviceMetricsOverride", session=True, width=width, height=height, deviceScaleFactor=1, mobile=False)
        self.call("Page.navigate", session=True, url=url)
        end = time.time() + 30
        while time.time() < end:
            if self._read().get("method") == "Page.loadEventFired": return
        raise TimeoutError(url)
    def eval(self, expr):
        return self.call("Runtime.evaluate", session=True, expression=expr, awaitPromise=True, returnByValue=True)["result"].get("value")
    def close(self):
        try: self.call("Browser.close")
        except Exception: pass
        try: self.p.wait(10)
        except Exception: pass
        try: os.killpg(self.p.pid, signal.SIGKILL)  # Chrome runs in its own session: also stops helpers still exiting, before the profile is removed
        except ProcessLookupError: pass
        if self.p.poll() is None: self.p.wait()
        for f in (self.w, self.r): f.close()

srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=os.path.join(ROOT, "docs")))
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}"
out, cout, sout, probe = {}, {}, {}, None
try:
    with tempfile.TemporaryDirectory(prefix="om-fl-layout-") as tmp:
        ctmp = os.path.join(tmp, "chrome-tmp"); os.makedirs(ctmp)
        c = Chrome(os.path.join(tmp, "profile"), ctmp)
        try:
            for p in PAGES:
                c.goto(f"{base}/{p}/", WIDTH, 800)
                out[p] = c.eval(MEASURE)
            for wd in COUNTY_WIDTHS:
                for p in COUNTY_PAGES:
                    c.goto(f"{base}/{p}/", wd, 800); cout[(p, wd)] = c.eval(COUNTY_MEASURE)
                for p in SUMMARY_PAGES:
                    c.goto(f"{base}/{p}/", wd, 800); sout[(p, wd)] = c.eval(SUMMARY_MEASURE)
            if ARGS.probe_flex:
                c.goto(f"{base}/fl/2025/columbia-county/", 375, 800); c.eval(FLEX_PROBE); probe = c.eval(SUMMARY_MEASURE)
        finally:
            c.close()
finally:
    srv.shutdown(); srv.server_close()

for p, o in out.items():
    print(f"{p} @{WIDTH}: {json.dumps(o)}")
    if not o: ok(False, f"{p}: no measurement (page did not load or script did not run)"); continue
    ok(o["vw"] == WIDTH, f"{p}: viewport {o['vw']} px == {WIDTH}")
    ok(o["table"] <= o["wrap"], f"LAYOUT (b)6 {p}: table.scrollWidth {o['table']} <= wrapper.clientWidth {o['wrap']} (no horizontal scroll)")
    ok(o["num_lines"] and all(n == 1 for n in o["num_lines"]), f"LAYOUT (b)6 {p}: one line box per td.num ({len(o['num_lines'])} rate cells, line counts {sorted(set(o['num_lines']))})")
    if WIDTH <= 640: ok(o["cap"] > 0 and abs(o["cap"] - o["tbl"]) < 0.5, f"LAYOUT caption {p}: caption width {o['cap']} == table width {o['tbl']}")
    ok(o["min_text_px"] >= 12, f"LAYOUT (b)6 {p}: min text {o['min_text_px']} px >= 12")
    ok(not o["doc_overflow"], f"{p}: page does not scroll sideways")
for (p, wd), o in cout.items():
    print(f"{p} @{wd}: {json.dumps(o)}")
    if not o or "wrap" not in o: ok(False, f"R1 {p} @{wd}: no special-district table measured"); continue
    ok(o["vw"] == wd, f"{p}: viewport {o['vw']} px == {wd}")
    ok(o["table"] <= o["wrap"], f"R1 {p} @{wd}: special-district table.scrollWidth {o['table']} <= wrapper.clientWidth {o['wrap']}")
    ok(o["src"] and all(a and c and a["in"] and c["in"] for a, c in o["src"]),
       f"R1 {p} @{wd}: every Source link and sha fully inside the viewport ({o['cw']} px) and the wrapper ({len(o['src'])} rows; rights {[(a['r'], c['r']) for a, c in o['src']]})")
    ok(o["num_lines"] and all(n == 1 for n in o["num_lines"]), f"R1 {p} @{wd}: one line box per rate cell (line counts {sorted(set(o['num_lines']))})")
    ok(not o["doc_overflow"], f"R1 {p} @{wd}: page does not scroll sideways")
for (p, wd), ss in sout.items():
    print(f"{p} @{wd} summaries: {json.dumps(ss)}")
    ok(ss and all(s["h"] >= 44 for s in ss), f"r2 should-fix {p} @{wd}: every reason-more summary >= 44 px tall ({sorted({s['h'] for s in ss})})")
    ok(ss and all(s["display"] == "list-item" and s["indent"] > 4 and s["cursor"] == "pointer" for s in ss), f"r2 should-fix {p} @{wd}: summaries keep the marker (display list-item, text indented {sorted({s['indent'] for s in ss})} px) and cursor:pointer")
if probe is not None: print(f"PROBE display:flex on Columbia reason-more summary @375 (not a check): {json.dumps(probe)}")
print("FAILURES", len(FAIL)); sys.exit(1 if FAIL else 0)
