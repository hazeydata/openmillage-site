"""OM-PAGE-REDO-001 page layer, shared by build.py and amend3.py.
Layout: openmillage-meta 9911d28 (Variation B "Rate stack" on A's tokens). Copy: content/copy.md (Lindsay afab3f2, verbatim).
Charts: assets/charts/ (Her?), inlined so their text uses the self-hosted fonts in assets/fonts/.
Slots: HISTORY_LINE and HISTORY_CHART below are the two history slots; edit them (or copy.md) and rebuild."""
import html, os, re, shutil
E = lambda s: html.escape(str(s), quote=True)
COPY_FILE = "content/copy.md"
CHART_DIR = "assets/charts"
FONT_DIR = "assets/fonts"
SITE = "https://openmillage.com"
ISSUES = "https://github.com/hazeydata/openmillage-site/issues"
_C = open(COPY_FILE, encoding="utf-8").read()

def sec(name):
    m = re.search(r"^#+ " + re.escape(name) + r"\n(.*?)(?=^#+ |\Z)", _C, re.S | re.M)
    if not m: raise SystemExit(f"redo.py: copy section missing: {name!r}")
    return m.group(1).strip()

def md(t):
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", E(t))
    return re.sub(r"\[(.+?)\]\((https?://[^)\s]+)\)", r"<a href='\2'>\1</a>", t)

HEADLINE = sec("Headline")
_LEDE = sec("Lede").split("\n\n")
CREDIT_MD = next(p for p in _LEDE if p.startswith("Built by"))   # site-wide credit line slot (footer); text lives in copy.md
LEDE = [p for p in _LEDE if not p.startswith("*")]
FOOT = [p for p in _LEDE if p.startswith("*")]
HOWTO = [l[2:] for l in sec("How to read your bill").splitlines() if l.startswith("- ")]
INTRO = {k: sec(k) for k in ["The stack (home page)", "The stack (county pages)", "Over time (history pages)",
                             "Before you vote (ballot measure numbered 3 page)", "Who sets what",
                             "Get the data (home, county and ballot measure pages)", "Get the data (history pages)"]}

CONTACT = "fred@hazeydata.ai"  # site-wide contact slot (Spec R1)
def credit(): return f"<p class=credit data-slot=credit>{md(CREDIT_MD)}</p>"
def contact(): return f"<a href='mailto:{CONTACT}'>{CONTACT}</a>"
def lede(): return "<div class=lede>" + "".join(f"<p>{md(p)}</p>" for p in LEDE) + "".join(f"<p class=foot>{md(p)}</p>" for p in FOOT) + "</div>"
def howto(): return "<h2 id=how-to-read>How to read your bill</h2><ul class=how>" + "".join(f"<li>{md(b)}</li>" for b in HOWTO) + "</ul>"
def intro(k): return f"<p>{md(INTRO[k])}</p>"
def getdata(links, k="Get the data (home, county and ballot measure pages)"):
    return f"<h2 id=get-the-data>Get the data</h2>{intro(k)}<p class=muted>{links}</p>"

# --- history slots (filled 2026-10-23 from copy afab3f2 and Her?'s 7c1a525 re-cut). Key: county name.
def _over_time():
    body, foot = INTRO["Over time (history pages)"].split("\n\n")
    i = body.index("Alachua County")
    return body[:i].strip(), body[i:].strip(), foot.strip()
OVER_GENERIC, _AL_LINE, _AL_FOOT = _over_time()
HISTORY_LINE = {"Alachua": (_AL_LINE, _AL_FOOT)}            # county -> (sentence, footnote); counties without one show the generic intro only
HISTORY_CHART = {"Alachua": ("history-multiples", "Small multiples: Florida county, school board and city millage by year since 1996, Alachua highlighted")}

# --- charts
def _svg(name, w, pfx):
    s = open(os.path.join(CHART_DIR, f"her-{name}-{w}-dark.svg"), encoding="utf-8").read()
    s = s[s.index("<svg"):]
    s = re.sub(r"<metadata>.*?</metadata>", "", s, flags=re.S)
    s = re.sub(r"<style[^>]*>.*?</style>", "", s, flags=re.S)
    def attrs(m):
        out = []
        for d in m.group(1).split(";"):
            if ":" in d:
                k, v = d.split(":", 1); out.append(f'{k.strip()}="{v.strip()}"')
        return " " + " ".join(out)
    s = re.sub(r'\sstyle="([^"]*)"', attrs, s)
    s = re.sub(r'\s(width|height)="[0-9.]+pt"', "", s, count=2)
    s = re.sub(r'id="([^"]+)"', lambda m: f'id="{pfx}{m.group(1)}"', s)
    s = re.sub(r"url\(#([^)]+)\)", lambda m: f"url(#{pfx}{m.group(1)})", s)
    s = re.sub(r'href="#([^"]+)"', lambda m: f'href="#{pfx}{m.group(1)}"', s)
    s = re.sub(r"\n\s*", " ", s)
    return s.replace("<svg ", "<svg class=chart-svg aria-hidden=true focusable=false ", 1)

def chart(name, label, attrs="", caption=""):
    """Her?'s chart, 350 version below 768px and 720 version at >=768px (CSS), inlined so text renders in the self-hosted fonts."""
    return (f"<figure class=hero{attrs}><div class=chart>"
            f"<div class=chart-m role=img aria-label='{E(label)}'>{_svg(name, 350, name + '-m-')}</div><div class=chart-d role=img aria-label='{E(label)}'>{_svg(name, 720, name + '-d-')}</div></div>"
            f"<figcaption class=muted>{caption}Chart: Her? &middot; her-{E(name)}-350/720-dark.svg</figcaption></figure>")

def stack(title, layers, title_html=None):
    """B 'Rate stack': one layer per taxing authority, no total (a total depends on the parcel)."""
    return (f"<div class=stack role=group aria-label='{E(title)}'><h3>{title_html or E(title)}</h3>" + "".join(
        f"<div class=layer><div class=who>{E(w)}<small>{E(sub)}</small>{flag}</div><div class=r>{E(r)}{f" <a href='{E(u)}' aria-label='Source for {E(w)}'>source</a>" if u else ""}</div></div>"
        for w, sub, r, u, flag in (tuple(l) + ('',) * (5 - len(l)) for l in layers)) + "</div>")

def copy_assets(out):
    os.makedirs(f"{out}/fonts", exist_ok=True)
    for f in sorted(os.listdir(FONT_DIR)): shutil.copyfile(os.path.join(FONT_DIR, f), f"{out}/fonts/{f}")
    open(f"{out}/redo.css", "w").write(CSS)

FONTS = [("Inter", 400, "Inter-400.ttf"), ("Inter", 600, "Inter-600.ttf"), ("Inter", 700, "Inter-700.ttf"), ("Space Grotesk", 600, "SpaceGrotesk-600.ttf")]
def _ff(PATH=""): return "".join(f"@font-face{{font-family:'{f}';font-weight:{w};font-style:normal;font-display:swap;src:url(fonts/{n}) format('truetype')}}\n" for f, w, n in FONTS)
CSS = _ff() + """:root{--bg:#03070F;--surface:#0A1628;--raised:#13243D;--line:#1E3352;--text:#E8EEF5;--muted:#9FB3C8;--cyan:#5FC4D6;--acc:#155140;
--font-head:'Space Grotesk',system-ui,sans-serif;--font-body:Inter,system-ui,sans-serif;
--s-1:4px;--s0:8px;--s1:16px;--s2:24px;--s3:32px;--s4:48px;--s5:64px;--s6:96px;
--fs--1:0.8rem;--fs0:1rem;--fs1:1.25rem;--fs2:1.563rem;--fs3:1.953rem;--fs4:2.441rem;--lh-body:1.6;--lh-head:1.15;--col:720px;--pad:20px;--radius:12px;
--fg:var(--text);--link:var(--cyan);--accent:var(--cyan);--border:var(--line);--badge-fg:var(--cyan);--badge-bg:var(--raised);--row-agg:var(--surface)}
@media(min-width:768px){:root{--fs3:2.441rem;--fs4:3.052rem}}
html,body{background:var(--bg);color:var(--text)}
body{font:var(--fs0)/var(--lh-body) var(--font-body);max-width:var(--col);padding:0 var(--pad) var(--pad)}
h1,h2,h3,.brand,summary{font-family:var(--font-head)}
h1{font-size:var(--fs4);line-height:var(--lh-head);font-weight:700;margin:var(--s4) 0 var(--s2);letter-spacing:-.01em}
h2{font-size:var(--fs2);line-height:var(--lh-head);margin:var(--s5) 0 var(--s1)}
p,li,dd{max-width:65ch}p{margin:0 0 var(--s2)}
.muted{color:var(--muted);font-size:var(--fs--1)}
.lede p:first-child,.lead{font-size:var(--fs1)}
.foot{font-size:var(--fs--1);color:var(--muted)}
ul.how{padding-left:1.2em;margin:0 0 var(--s2)}ul.how li{margin-bottom:var(--s1)}
.hero{margin:var(--s3) 0}.chart-svg{display:block;width:100%;height:auto}.chart-d{display:none}
@media(min-width:768px){.chart-m{display:none}.chart-d{display:block}}
.hero figcaption{margin-top:var(--s0)}
.stack{background:var(--surface);border:1px solid var(--line);border-left:6px solid var(--acc);border-radius:var(--radius);margin:var(--s3) 0;padding:var(--s1) var(--s2)}
.stack h3{font-size:var(--fs0);font-weight:600;color:var(--muted);margin:var(--s0) 0 var(--s1);text-transform:uppercase;letter-spacing:.06em}
.layer{display:flex;justify-content:space-between;align-items:baseline;gap:var(--s1);padding:var(--s1) 0;border-top:1px solid var(--line)}
.layer .who small{display:block;color:var(--muted);font-size:var(--fs--1)}
.layer .r{font:700 var(--fs2) var(--font-head);text-align:right}.layer .r a{font:400 var(--fs--1) var(--font-body);margin-left:var(--s0)}
details.all{margin:var(--s3) 0;border-top:1px solid var(--line);padding-top:var(--s2)}
blockquote.official p:first-child{text-transform:none;font-size:var(--fs0)}
.stack+p.muted{margin-top:var(--s1)}
.kicker{font:600 var(--fs--1) var(--font-head);color:var(--muted);letter-spacing:.04em;margin:var(--s4) 0 0}.kicker+h1{margin-top:var(--s0)}
details.all>summary{cursor:pointer;font-size:var(--fs1);font-weight:600;color:var(--cyan)}
table{font-size:var(--fs--1)}
.callout{background:var(--surface);border-color:var(--line);border-left-color:var(--cyan);border-radius:var(--radius)}
footer{margin-top:var(--s6);font-size:var(--fs--1)}
.credit{color:var(--text)}
"""
