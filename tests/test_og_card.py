"""Every page carries one large-image card (og:/twitter: tags) with its own og:url; docs/og-card.png is a 1200x630 PNG."""
import os, re, struct, sys
BASE = "https://openmillage.com"
errs, n = [], 0
def tag(h, attr, name): return re.findall(rf'<meta {attr}="{re.escape(name)}" content="([^"]*)">', h)
for root, _, files in os.walk("docs"):
    for f in sorted(files):
        if not f.endswith(".html"): continue
        n += 1; p = os.path.join(root, f); rel = os.path.relpath(p, "docs").replace(os.sep, "/"); h = open(p, encoding="utf-8").read()
        want = BASE + "/" + (rel[:-10] if rel.endswith("index.html") else rel)
        got = {k: tag(h, a, k) for a, k in [("property", "og:image"), ("property", "og:image:width"), ("property", "og:image:height"), ("property", "og:image:alt"),
               ("name", "twitter:card"), ("name", "twitter:image"), ("property", "og:url"), ("property", "og:title"), ("property", "og:description"), ("property", "og:type")]}
        for k, v in got.items():
            if len(v) != 1: errs.append(f"{rel}: {k} x{len(v)}")
        if any(len(v) != 1 for v in got.values()): continue
        g = {k: v[0] for k, v in got.items()}
        if g["og:image:width"] != "1200" or g["og:image:height"] != "630": errs.append(f"{rel}: image size tags")
        if not g["og:image:alt"].strip(): errs.append(f"{rel}: empty og:image:alt")
        if g["twitter:card"] != "summary_large_image": errs.append(f"{rel}: twitter:card")
        if g["og:image"] != g["twitter:image"] or not re.fullmatch(re.escape(BASE) + r"/\S+", g["og:image"]): errs.append(f"{rel}: image urls {g['og:image']} / {g['twitter:image']}")
        if g["og:url"] != want: errs.append(f"{rel}: og:url {g['og:url']} != {want}")
        if g["og:type"] != "website": errs.append(f"{rel}: og:type")
        if not g["og:title"].strip() or not g["og:description"].strip(): errs.append(f"{rel}: empty og:title/og:description")
b = open("docs/og-card.png", "rb").read(24) if os.path.exists("docs/og-card.png") else b""
if b[:8] != b"\x89PNG\r\n\x1a\n" or b[12:16] != b"IHDR" or struct.unpack(">II", b[16:24]) != (1200, 630): errs.append("docs/og-card.png missing or not a 1200x630 PNG")
if n == 0: errs.append("no pages found under docs/")
print("\n".join(errs[:30]) or f"ok: {n} pages")
sys.exit(1 if errs else 0)
