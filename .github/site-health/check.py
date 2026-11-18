#!/usr/bin/env python3
"""Live-site health check (stdlib only). Exit 1 on any failure.

Env: BASE_URL (default https://openmillage.com/), GITHUB_STEP_SUMMARY (optional).
Run from the repo root (reads docs/api/**/*.json and data/fl-2025.csv).
"""
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CANON = "https://openmillage.com"
UA = "openmillage-site-health (+https://github.com/hazeydata/openmillage-site)"
BASE = (os.environ.get("BASE_URL") or CANON + "/").strip()
if not BASE.endswith("/"):
    BASE += "/"
_p = urllib.parse.urlsplit(BASE)
ORIGIN = f"{_p.scheme}://{_p.netloc}"
ROOT = Path(__file__).resolve().parents[2]


def get(url, attempts=3, timeout=30):
    """Return (status, body_bytes, error). Retries network errors, 5xx and 429."""
    status, body, err = None, b"", None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(), None
        except urllib.error.HTTPError as e:
            status, err = e.code, f"HTTP {e.code}"
            if e.code != 429 and e.code < 500:
                return status, b"", err
        except Exception as e:  # network error, timeout, TLS, ...
            status, err = None, f"{type(e).__name__}: {e}"
        if i < attempts - 1:
            time.sleep(2 * 2 ** i)
    return status, body, err


failures = []


def fail(msg):
    failures.append(msg)


# 1. sitemap
urls = []
st, body, err = get(BASE + "sitemap.xml")
if st != 200:
    fail(f"sitemap.xml: {err or st}")
else:
    try:
        root = ET.fromstring(body)
        locs = [(e.text or "").strip() for e in root.iter() if e.tag.endswith("}loc") or e.tag == "loc"]
        urls = sorted({u for u in locs if u})
        if not urls:
            fail("sitemap.xml: no <loc> URLs")
    except ET.ParseError as e:
        fail(f"sitemap.xml: does not parse: {e}")


def rewrite(u):
    return ORIGIN + u[len(CANON):] if u.startswith(CANON) else u


sitemap_live = [rewrite(u) for u in urls]
extra = [BASE + "robots.txt", BASE + "llms.txt"]
api_files = sorted((ROOT / "docs" / "api").rglob("*.json"))
api_urls = [BASE + "api/" + f.relative_to(ROOT / "docs" / "api").as_posix() for f in api_files]
if not api_urls:
    fail("no docs/api/**/*.json files found in checkout")

jobs = [(u, False) for u in sitemap_live + extra] + [(u, True) for u in api_urls]


def run(job):
    url, is_json = job
    st, body, err = get(url)
    if st != 200:
        return url, f"{err or st}"
    if is_json:
        try:
            json.loads(body)
        except ValueError as e:
            return url, f"200 but invalid JSON: {e}"
    return url, None


with ThreadPoolExecutor(max_workers=16) as ex:
    results = list(ex.map(run, jobs))
ok = sum(1 for _, e in results if e is None)
for u, e in results:
    if e:
        fail(f"{u}: {e}")

# 2. county-page count
pat = re.compile(r"^/fl/2025/[^/]+/$")
county_pages = {urllib.parse.urlsplit(u).path for u in urls if pat.match(urllib.parse.urlsplit(u).path)}
with open(ROOT / "data" / "fl-2025.csv", newline="", encoding="utf-8") as f:
    counties = {r["county"] for r in csv.DictReader(f)}
if len(county_pages) != len(counties):
    fail(f"county pages in sitemap ({len(county_pages)}) != distinct counties in data/fl-2025.csv ({len(counties)})")

total = len(results)
line = f"health: {ok}/{total} 200 (base {BASE}; sitemap {len(urls)}, api {len(api_urls)}, county pages {len(county_pages)}/{len(counties)})"
print(line)
shown = failures[:50]
for m in shown:
    print("FAIL " + m)
if len(failures) > len(shown):
    print(f"... and {len(failures) - len(shown)} more")

summ = os.environ.get("GITHUB_STEP_SUMMARY")
if summ:
    with open(summ, "a", encoding="utf-8") as f:
        f.write(f"### Live pages, API JSON, county count\n\n`{line}`\n\n")
        if failures:
            f.write(f"**{len(failures)} failure(s)**\n\n")
            for m in shown:
                f.write(f"- {m}\n")
            f.write("\n")
        else:
            f.write("All checks passed.\n\n")
sys.exit(1 if failures else 0)
