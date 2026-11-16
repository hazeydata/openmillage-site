#!/usr/bin/env python3
"""OM-SITE-SPECIAL-ISD-001 LAYOUT (b)6: FL body-page county table at 375 px, measured in headless Chrome with the built CSS.
Not part of CI (needs Chrome). Run by hand from the repo root after the build:
    python3 tests/browser_fl_layout.py [--width N]   # default 375; CHROME=/path/to/chrome to override /usr/bin/google-chrome
Serves docs/ on 127.0.0.1 (every other host resolves to nothing), drives one headless Chrome over --remote-debugging-pipe with a
throwaway profile (closed in finally; Chrome's TMPDIR/TMP/TEMP and profile all live inside this script's own TemporaryDirectory), sets the viewport (default 375 px) and checks:
  table.scrollWidth <= wrapper.clientWidth (no horizontal scroll), one line box per td.num (no rate wraps), min text in <main> >= 12 px.
Nothing in docs/ is changed."""
import argparse, functools, http.server, json, os, signal, subprocess, sys, tempfile, threading, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
CHROME = os.environ.get("CHROME", "/usr/bin/google-chrome")
PAGES = ["fl/special-districts/sfwmd", "fl/special-districts/cftod", "fl/special-districts/sjrwmd"]
ap = argparse.ArgumentParser(); ap.add_argument("--width", type=int, default=375); WIDTH = ap.parse_args().width
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)

MEASURE = """new Promise(function(done){document.fonts.ready.then(function(){
var w=document.querySelector('.tablewrap'),t=w&&w.querySelector('table.sd-rates'),o={vw:window.innerWidth};
if(t){o.wrap=w.clientWidth;o.table=t.scrollWidth;o.rows=t.querySelectorAll('tbody tr').length;
o.num_lines=[].map.call(t.querySelectorAll('td.num'),function(td){var r=document.createRange();r.selectNodeContents(td);
var tops={};[].forEach.call(r.getClientRects(),function(q){if(q.width>0)tops[Math.round(q.top)]=1});return Object.keys(tops).length});}
var f=[].filter.call(document.querySelectorAll('main *'),function(e){return [].some.call(e.childNodes,function(n){return n.nodeType==3&&n.textContent.trim()})})
.filter(function(e){var s=getComputedStyle(e);return s.display!='none'&&s.visibility!='hidden'&&e.getClientRects().length&&e.getBoundingClientRect().left>-1000});
o.min_text_px=Math.min.apply(null,f.map(function(e){return parseFloat(getComputedStyle(e).fontSize)}));
o.doc_overflow=document.documentElement.scrollWidth>window.innerWidth;done(o);});})"""

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
    with tempfile.TemporaryDirectory(prefix="om-fl-layout-") as tmp:
        ctmp = os.path.join(tmp, "chrome-tmp"); os.makedirs(ctmp)
        c = Chrome(os.path.join(tmp, "profile"), ctmp)
        try:
            for p in PAGES:
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
    ok(o["table"] <= o["wrap"], f"LAYOUT (b)6 {p}: table.scrollWidth {o['table']} <= wrapper.clientWidth {o['wrap']} (no horizontal scroll)")
    ok(o["num_lines"] and all(n == 1 for n in o["num_lines"]), f"LAYOUT (b)6 {p}: one line box per td.num ({len(o['num_lines'])} rate cells, line counts {sorted(set(o['num_lines']))})")
    ok(o["min_text_px"] >= 12, f"LAYOUT (b)6 {p}: min text {o['min_text_px']} px >= 12")
    ok(not o["doc_overflow"], f"{p}: page does not scroll sideways")
print("FAILURES", len(FAIL)); sys.exit(1 if FAIL else 0)
