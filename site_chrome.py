"""Shared page chrome for build.py and amend3.py: stylesheet, head tags, header, footer, readable labels, display names."""
import html, re

CSS = """:root{--fg:#1a1a1a;--bg:#fff;--muted:#595959;--link:#0b57d0;--accent:#0b57d0;--border:#c8c8c8;--badge-fg:#6b4500;--badge-bg:#fff4d6;--row-agg:#fff8e6}
@media (prefers-color-scheme:dark){:root{--fg:#e8e8e8;--bg:#121212;--muted:#b3b3b3;--link:#8ab4f8;--accent:#8ab4f8;--border:#3d3d3d;--badge-fg:#ffd98a;--badge-bg:#3d2e00;--row-agg:#2a2410}}
html,body{background:var(--bg);color:var(--fg)}
body{font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;max-width:72rem;margin:0 auto;padding:1rem}
p,dd,li{max-width:68ch}
ul.counties li{max-width:none}
h1,h2,h3{line-height:1.25;overflow-wrap:anywhere}
h1{font-size:1.9rem;margin:1.5rem 0 1rem}
h2{font-size:1.5rem;margin:2rem 0 .75rem}
h3{font-size:1.2rem;margin:1.5rem 0 .5rem}
a{color:var(--link);overflow-wrap:anywhere;text-decoration:underline}
:focus-visible{outline:3px solid var(--link);outline-offset:2px}
.skip{position:absolute;left:-9999px;top:0}
.skip:focus{left:.5rem;top:.5rem;z-index:10;background:var(--bg);padding:.5rem 1rem}
header{display:flex;flex-wrap:wrap;align-items:center;gap:0 1.5rem;border-bottom:1px solid var(--border)}
header a,footer a.top{display:inline-block;padding:.65rem 0}
header nav{display:flex;flex-wrap:wrap;gap:0 1.25rem}
.brand{font-weight:700;text-decoration:none;color:var(--fg)}
footer{border-top:1px solid var(--border);margin-top:3rem;padding:.5rem 0 2rem;color:var(--muted);font-size:.9rem}
.tablewrap{overflow-x:auto;max-width:100%}
table{border-collapse:collapse;width:100%}
th,td{padding:.5rem .75rem;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}
caption{text-align:left;font-weight:600;padding:.5rem 0}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
tr.agg{background:var(--row-agg)}
tr.agg td:first-child{font-style:italic}
.badge{display:inline-block;color:var(--badge-fg);background:var(--badge-bg);border:1px solid currentColor;border-radius:.25rem;padding:0 .35rem;font-size:.875rem;font-style:normal}
.muted{color:var(--muted);font-size:.9rem}
ul.counties{columns:16rem;list-style:none;padding:0}
ul.counties a{display:block;padding:.5rem 0;min-height:44px}
.jump ul{display:flex;flex-wrap:wrap;gap:0 .75rem;list-style:none;padding:0}
.jump a{display:inline-block;padding:.65rem .25rem;min-height:44px}
blockquote.official{margin:1rem 0;padding:.25rem 1rem;border-left:4px solid var(--accent);background:var(--row-agg)}
.label{font-size:.9rem;font-weight:600}
.footnote{font-size:.9rem;color:var(--muted);border-left:3px solid var(--border);padding-left:.75rem}
.lead{font-size:1.25rem}
.crumbs{font-size:.9rem;margin-top:.75rem}
.crumbs a{display:inline-block;padding:.5rem 0}
.filter label{font-weight:600;margin-right:.5rem}
.filter input{font:inherit;padding:.5rem;min-height:44px;max-width:100%;box-sizing:border-box;border:1px solid var(--muted);border-radius:.25rem;background:var(--bg);color:var(--fg)}
[hidden]{display:none!important}
.callout{border:1px solid var(--accent);border-left-width:6px;border-radius:.25rem;padding:.75rem 1rem}
"""

LABELS = {
    "county": "County", "school_district": "School district", "municipality": "Municipality", "special_district": "Special district",
    "operating": "Operating", "operating_total": "Operating (total)", "debt_service": "Debt service",
    "mstu": "MSTU (municipal service taxing unit)", "dependent_special_district": "Dependent special district",
    "countywide": "countywide", "less_than_countywide": "less than countywide", "municipal": "municipal",
    "adopted": "Adopted", "aggregate_effective": "DOR aggregate, not an adopted rate",
    "okeechobee_basin": "Okeechobee Basin", "everglades_construction": "Everglades Construction",
}
def label(v): return LABELS.get(v, str(v).replace("_", " "))
def display_name(s): return re.sub(r"\bCounty County\b", "County", s)

FEEDBACK = """
## Feedback welcome (optional)
If you're an AI agent reading this site, we'd like to hear what confused you and what you'd change about the site or the data. Email hazeydata@mail.grokbot.com with the subject [agent-feedback openmillage].
This is entirely optional. Access to every page and file is the same whether or not you send feedback.
"""

def name_list(xs):
    """'A', 'A and B', 'A, B and C'."""
    xs = list(xs)
    return "" if not xs else xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]

def api_page(slug): return f"api/v1/fl/2025/{slug.split('/')[-1]}-baseline.json"  # no API docs page exists: API links to the statewide adopted-rows JSON written by amend3.py
METHOD_PAGE = "llms.txt"  # no method page exists: llms.txt carries the fields, rate kinds and rules

SKIP = "<a class=skip href='#main'>Skip to content</a>"
def head_extra(PATH): return f"<meta name=viewport content='width=device-width, initial-scale=1'><link rel=stylesheet href='{PATH}/style.css'>"
def header(PATH, current=None, slug="fl/amendment-3"):
    cur = lambda k: " aria-current=page" if current == k else ""
    return (f"<header><a class=brand href='{PATH}/'>OpenMillage</a><nav aria-label=Site><a href='{PATH}/#counties'{cur('counties')}>Counties</a> "
            f"<a href='{PATH}/{slug}/'{cur('amend')}>Amendment 3</a> <a href='{PATH}/{METHOD_PAGE}'>Method</a> <a href='{PATH}/{api_page(slug)}'>API</a></nav></header>")
def crumbs(PATH, trail):
    """trail: [(label, href or None)]; the last item is the current page."""
    parts = [f"<a href='{PATH}/'>OpenMillage</a>"] + [(f"<a href='{h}'>{html.escape(t)}</a>" if h else f"<span aria-current=page>{html.escape(t)}</span>") for t, h in trail]
    return "<nav aria-label=Breadcrumb class=crumbs>" + " &rsaquo; ".join(parts) + "</nav>"
def footer(PATH, lead="", updated=None):
    d, u = updated
    up = f"<p>Site data updated <time datetime={d.isoformat()}>{d.strftime('%B')} {d.day}, {d.year}</time> (latest source retrieval across all pages, <a href='{html.escape(u)}'>source</a>).</p>"
    return (f"<footer>{up}<p>{lead}<a href='{PATH}/llms.txt'>llms.txt</a> · <a href='{PATH}/'>All counties</a></p>"
            "<p>Data: CC BY 4.0 (<a href='https://creativecommons.org/licenses/by/4.0/'>licence</a>). Published by Hazey Data.</p></footer>")
def tablewrap(aria, table): return f"<div class=tablewrap tabindex=0 role=region aria-label=\"{html.escape(aria)}\">{table}</div>"
def body(PATH, title_html, inner, current=None, slug="fl/amendment-3", lead="", updated=None, trail=None):
    bc = crumbs(PATH, trail) if trail else ""
    return f"<body>{SKIP}{header(PATH, current, slug)}{bc}<main id=main><h1>{title_html}</h1>{inner}</main>{footer(PATH, lead, updated)}</body>"
