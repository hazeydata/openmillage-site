#!/usr/bin/env python3
"""OM-DATA-REPIN-001: scripts/repin_lock.py accepts only float-noise changes, and the pinned data has no float noise.
Run from the repo root:  python3 tests/test_repin_lock.py"""
import csv, glob, os, re, sys
from decimal import Decimal
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "scripts")); os.chdir(ROOT)
import repin_lock as R
FAIL = []
def ok(cond, msg): print(("PASS " if cond else "FAIL ") + msg); cond or FAIL.append(msg)

H = b"id,rate,note\n"
ok(R.classify(H + b"a,0.5,x\n", H + b"a,0.5,x\n")[0] == "identical", "identical bytes -> identical")
k, n, _ = R.classify(H + b"a,0.46270000000000006,x\n", H + b"a,0.4627,x\n")
ok((k, n) == ("noise", 1), "0.46270000000000006 -> 0.4627 is noise (1 cell)")
ok(R.classify(H + b"a,0.4627,x\n", H + b"a,0.4628,x\n")[0] == "other", "a real value change is refused")
ok(R.classify(H + b"a,0.5000,x\n", H + b"a,0.5,x\n")[0] == "other", "a <=15-digit value reformatted is refused")
ok(R.classify(H + b"a,1e-06,x\n", H + b"a,0.000001,x\n")[0] == "other", "exponent form with few digits reformatted is refused")
ok(R.classify(H + b"a,0.46270000000000006,inferred\n", H + b"a,0.4627,statutory_per_100\n")[0] == "other", "a text change next to noise is refused")
ok(R.classify(H + b"a,0.46270000000000006,x\n", H + b"a,0.4627,x\nb,1,y\n")[0] == "other", "an added row is refused")
ok(R.classify(H + b"a,0.5,x\n", b"id,note,rate\na,x,0.5\n")[0] == "other", "a header change is refused")
ok(R.classify(H + b"a,0.5,x\n", H.replace(b"\n", b"\r\n") + b"a,0.5,x\r\n")[0] == "other", "a line-ending change is refused")

bad = []
for p in sorted(glob.glob("data/tx/*.csv") + glob.glob("data/history/*.csv")):
    for i, row in enumerate(csv.reader(open(p, newline="", encoding="utf-8")), 1):
        bad += [(p, i, c) for c in row if re.fullmatch(r"-?\d+\.\d+", c) and len(Decimal(c).as_tuple().digits) > 15]
ok(not bad, f"no cell with more than 15 significant digits in data/tx and data/history; found {bad[:3]}")

print(f"\n{len(FAIL)} failed" if FAIL else "\nall passed"); sys.exit(1 if FAIL else 0)
