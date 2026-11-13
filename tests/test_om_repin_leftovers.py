#!/usr/bin/env python3
"""OM-REPIN-LEFTOVERS-001: one product data pin for TX, history and NC; the staged TX charts name no stale pin.
Run from the repo root:  python3 tests/test_om_repin_leftovers.py"""
import glob, hashlib, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)

lock = {e["path"]: e for e in json.load(open("data/SOURCES.lock"))["files"]}
CH = "assets/charts/om-2026-11-06"
TX = ("data/tx/tx-2021.csv", "data/tx/tx-2025.csv")
counts, series = (json.load(open(f"{CH}/tx-yoy-{n}.json")) for n in ("counts", "series"))
for name, j in (("counts", counts), ("series", series)):
    ok(all(j["pin_commit"] == lock[p]["commit"] for p in TX), f"tx-yoy-{name}.json pin_commit equals the lock commit of both data/tx year files")
for p in TX:
    ok(counts["source_files"][os.path.basename(p)]["sha256"] == lock[p]["sha256"], f"tx-yoy-counts.json source sha256 equals the lock sha256 of {p}")

stale = [p for p in sorted(glob.glob(f"{CH}/*") + glob.glob("docs/charts/tx-*")) if b"2166c845" in open(p, "rb").read()]
ok(not stale, f"no stale pin 2166c845 in {CH}/ or docs/charts/tx-*; found {stale}")
pinned = [p for p in sorted(glob.glob(f"{CH}/*.svg")) if b"product pin" in open(p, "rb").read()]
ok(len(glob.glob(f"{CH}/*.svg")) == 2 and not pinned, f"the two SVG footers do not say 'product pin'; found {pinned}")

nc = {p: e for p, e in lock.items() if p.startswith("data/nc/")}
ok(len(nc) == 12, f"12 data/nc entries in the lock; found {len(nc)}")
ok({e["commit"] for e in nc.values()} == {lock[TX[0]]["commit"]} == {lock[TX[1]]["commit"]}, "all data/nc lock entries share the data/tx lock commit")
bad = [p for p, e in nc.items() if hashlib.sha256(open(p, "rb").read()).hexdigest() != e["sha256"]]
ok(not bad, f"every data/nc file matches its lock sha256; mismatches {bad}")

print(f"\n{len(FAIL)} failed" if FAIL else "\nall passed"); sys.exit(1 if FAIL else 0)
