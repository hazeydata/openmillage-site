#!/usr/bin/env python3
"""OM-SITE-SPECIAL-ISD-001 round 2: TX ISD chart and TX rate tables in headless Chrome with the built CSS (CHART-SPEC 10.6, Lucille 2).
Not part of CI (needs Chrome). Run by hand from the repo root after the build:
    python3 tests/browser_tx_layout.py [--width N]   # default 375; CHROME=/path/to/chrome to override /usr/bin/google-chrome
Serves docs/ on 127.0.0.1 (every other host resolves to nothing), drives one headless Chrome over --remote-debugging-pipe with a
throwaway profile (closed in finally; Chrome's TMPDIR/TMP/TEMP and profile all live inside this script's own TemporaryDirectory), sets the viewport and checks:
  min rendered text in svg.isd-t >= 12 px (font-size x display width / viewBox width) and no chart text outside the svg box;
  one line box per numeric cell (table.tx-rates td.num: no rate wraps mid-number); the ISD year table fits its wrapper;
  document.documentElement.scrollWidth == viewport width (no sideways page scroll). Also reports the TX hub height.
Nothing in docs/ is changed."""
import argparse, functools, http.server, json, os, signal, subprocess, sys, tempfile, threading, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
CHROME = os.environ.get("CHROME", "/usr/bin/google-chrome")
ISD_PAGES = ["tx/hopkins-county/cumby-collegiate-isd", "tx/bexar-county/northside-isd", "tx/nacogdoches-county/etoile-isd"]
OTHER = ["tx/hopkins-county", "tx/harris-county", "tx/property-tax-rates", "tx/school-districts"]
ap = argparse.ArgumentParser(); ap.add_argument("--width", type=int, default=375); WIDTH = ap.parse_args().width
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)

MEASURE = """new Promise(function(done){document.fonts.ready.then(function(){
var o={vw:window.innerWidth,doc_sw:document.documentElement.scrollWidth,doc_h:document.documentElement.scrollHeight};
var s=document.querySelector('svg.isd-t');
if(s){var r=s.getBoundingClientRect(),k=r.width/s.viewBox.baseVal.width,ts=[].slice.call(s.querySelectorAll('text'));
o.svg_w=r.width;o.svg_min_px=Math.min.apply(null,ts.map(function(t){return parseFloat(getComputedStyle(t).fontSize)*k}));o.svg_n_text=ts.length;
o.svg_text_outside=ts.filter(function(t){var b=t.getBoundingClientRect();return b.left<r.left-0.5||b.right>r.right+0.5}).map(function(t){return t.textContent});}
var w=document.querySelector('#t-isd');if(w){o.isd_wrap=w.parentNode.clientWidth;o.isd_table=w.scrollWidth;}
o.num_lines=[].map.call(document.querySelectorAll('table.tx-rates td.num'),function(td){var g=document.createRange();g.selectNodeContents(td);
var tops={};[].forEach.call(g.getClientRects(),function(q){if(q.width>0)tops[Math.round(q.top)]=1});return Object.keys(tops).length});
o.num_min_px=Math.min.apply(null,[].map.call(document.querySelectorAll('table.tx-rates td.num'),function(td){return parseFloat(getComputedStyle(td).fontSize)}));
done(o);});})"""

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
out = {}
try:
    with tempfile.TemporaryDirectory(prefix="om-tx-layout-") as tmp:
        ctmp = os.path.join(tmp, "chrome-tmp"); os.makedirs(ctmp)
        c = Chrome(os.path.join(tmp, "profile"), ctmp)
        try:
            for p in ISD_PAGES + OTHER:
                c.goto(f"{base}/{p}/", WIDTH, 800)
                out[p] = c.eval(MEASURE)
        finally:
            c.close()
finally:
    srv.shutdown(); srv.server_close()

for p, o in out.items():
    print(f"{p} @{WIDTH}: {json.dumps(o)}")
    if not o: ok(False, f"{p}: no measurement (page did not load or script did not run)"); continue
    ok(o["vw"] == WIDTH, f"{p}: viewport {o['vw']} px == {WIDTH}")
    ok(o["doc_sw"] == o["vw"], f"{p}: document scrollWidth {o['doc_sw']} == viewport {o['vw']} (no sideways page scroll)")
    if o["num_lines"]:
        ok(all(n == 1 for n in o["num_lines"]), f"{p}: one line box per rate cell ({len(o['num_lines'])} td.num, line counts {sorted(set(o['num_lines']))}); text {o['num_min_px']} px")
        ok(o["num_min_px"] >= 12, f"{p}: rate cell text {o['num_min_px']} px >= 12")
    if p in ISD_PAGES:
        ok("svg_min_px" in o and o["svg_min_px"] >= 12, f"CHART-SPEC 10.6 {p}: min rendered text in svg.isd-t {o.get('svg_min_px')} px >= 12 (display {o.get('svg_w')} px, {o.get('svg_n_text')} texts)")
        ok(o.get("svg_text_outside") == [], f"{p}: no chart text outside the svg box {o.get('svg_text_outside')}")
        ok(o["isd_table"] <= o["isd_wrap"], f"{p}: ISD year table {o['isd_table']} px fits its wrapper {o['isd_wrap']} px")
print(f"TX hub height @{WIDTH}: {out.get('tx/school-districts', {}).get('doc_h')} px")
print("FAILURES", len(FAIL)); sys.exit(1 if FAIL else 0)
