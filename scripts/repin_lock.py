"""Re-pin data/SOURCES.lock entries to a hazeydata/openmillage commit, noise-only (OM-DATA-REPIN-001).

    python3 scripts/repin_lock.py --product PATH_TO_OPENMILLAGE_CLONE --commit SHA [--group tx,history] [--write]
    python3 scripts/repin_lock.py --product PATH --commit SHA --audit     # every lock entry, nothing written

For each lock entry in the chosen groups (tx = data/tx/*, history = data/history/*) the file at
<commit>:<source_path> is compared with the current site copy:
  identical      -> only "commit" changes;
  noise only     -> file and sha256 change. Noise only = same bytes outside changed cells, same header, row count and
                    row order, and every changed cell is old -> site_chrome.rate_text(old) with old > 15 significant
                    digits (relative change <= 1e-12);
  anything else  -> refused: exit 1, nothing written.
Without --write it only reports. --replace-pin OLD also rewrites the exact OLD commit string (full 40-hex, and its
7- and 8-char prefixes) to the new one in PIN_TEXT_FILES, so a branch-head pin can be re-pointed to the squash-merge
commit with one command:
    python3 scripts/repin_lock.py --product P --commit MERGE_SHA --replace-pin BRANCH_HEAD_SHA --write

Sanctioned data change (OM-FL-COVERAGE-001): --data-change PATH [PATH ...] re-pins exactly the listed lock paths to
<commit>:<source_path>, whatever changed (rows added, values changed), and nothing else. Every listed path must be a lock
entry and must exist at the commit; any other entry stays byte-unchanged. The noise-only check is not applied to these
paths, so use it only for a data change merged in the product repo. --group and --replace-pin do not apply.
    python3 scripts/repin_lock.py --product P --commit SHA --data-change data/special/a.csv data/special/b.csv --write
"""
import argparse, csv, hashlib, io, json, re, subprocess, sys
from decimal import Decimal

sys.path.insert(0, ".")
from site_chrome import rate_text

LOCK = "data/SOURCES.lock"
GROUPS = {"tx": "data/tx/", "history": "data/history/"}
PIN_TEXT_FILES = ["tests/test_tx_statepages.py", "tests/test_redo.py", "README.md", "content/SOURCE.md", "build.py"]


def sig(s):
    return len(Decimal(s).as_tuple().digits)


def classify(old, new):
    """-> ("identical"|"noise"|"other", changed_cells, detail)"""
    if old == new:
        return "identical", 0, ""
    try:
        o, n = old.decode("utf-8"), new.decode("utf-8")
    except UnicodeDecodeError:
        return "other", 0, "binary"
    if o.count("\r") != n.count("\r") or o.endswith("\n") != n.endswith("\n"):
        return "other", 0, "line endings differ"
    ol, nl = o.split("\n"), n.split("\n")
    if len(ol) != len(nl):
        return "other", 0, f"line count {len(ol)} -> {len(nl)}"
    changed = 0
    for i, (a, b) in enumerate(zip(ol, nl), 1):
        if a == b:
            continue
        ra, rb = next(csv.reader(io.StringIO(a))), next(csv.reader(io.StringIO(b)))
        if i == 1 or len(ra) != len(rb):
            return "other", changed, f"line {i}: header or field count differs"
        rebuilt = a
        for x, y in zip(ra, rb):
            if x == y:
                continue
            try:
                good = sig(x) > 15 and rate_text(x) == y and abs(float(x) - float(y)) <= 1e-12 * abs(float(x))
            except Exception:
                good = False
            if not good:
                return "other", changed, f"line {i}: {x!r} -> {y!r} is not float noise"
            rebuilt = re.sub(rf"(?:^|(?<=,)){re.escape(x)}(?=,|$)", y, rebuilt)
            changed += 1
        if rebuilt != b:
            return "other", changed, f"line {i}: bytes outside the noise cells differ"
    return "noise", changed, ""


def show(product, commit, path):
    r = subprocess.run(["git", "-C", product, "show", f"{commit}:{path}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--group", default="tx,history")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--replace-pin")
    ap.add_argument("--data-change", nargs="+", metavar="PATH")
    a = ap.parse_args(argv)
    commit = subprocess.run(["git", "-C", a.product, "rev-parse", "--verify", a.commit + "^{commit}"],
                            capture_output=True, text=True, check=True).stdout.strip()
    lock = json.load(open(LOCK))
    if a.data_change:
        return data_change(a, commit, lock)
    prefixes = [GROUPS[g] for g in a.group.split(",")]
    refused, plan = [], []
    for f in lock["files"]:
        chosen = any(f["path"].startswith(p) for p in prefixes)
        if not (chosen or a.audit):
            continue
        new = show(a.product, commit, f["source_path"])
        cur = open(f["path"], "rb").read()
        kind, cells, why = ("other", 0, "missing at commit") if new is None else classify(cur, new)
        print(f"{'REPIN' if chosen else 'audit'}\t{f['path']}\t{f['commit'][:8]}->{commit[:8]}\t{kind}\tcells={cells}\t{why}")
        if chosen:
            (refused if kind == "other" else plan).append((f, new, kind))
    if refused:
        print(f"REFUSED: {len(refused)} chosen file(s) change beyond float noise; nothing written", file=sys.stderr)
        return 1
    if not a.write:
        return 0
    for f, new, kind in plan:
        if kind == "noise":
            open(f["path"], "wb").write(new)
        f["commit"], f["sha256"] = commit, hashlib.sha256(new).hexdigest()
    open(LOCK, "w").write(json.dumps(lock, indent=1) + "\n")
    if a.replace_pin:
        old = subprocess.run(["git", "-C", a.product, "rev-parse", "--verify", a.replace_pin + "^{commit}"],
                             capture_output=True, text=True, check=True).stdout.strip()
        for p in PIN_TEXT_FILES:
            t = open(p, encoding="utf-8").read()
            u = t.replace(old, commit)
            u = re.sub(rf"\b{old[:8]}\b", commit[:8], u)
            u = re.sub(rf"\b{old[:7]}\b", commit[:7], u)
            if u != t:
                open(p, "w", encoding="utf-8").write(u)
                print(f"pin text updated: {p}")
    print(f"wrote {LOCK}: {len(plan)} entries -> {commit}")
    return 0


def data_change(a, commit, lock):
    """Re-pin exactly the listed lock paths (a sanctioned data change); refuse unknown or missing paths before writing."""
    if a.audit or a.replace_pin:
        print("REFUSED: --data-change cannot be combined with --audit or --replace-pin", file=sys.stderr)
        return 1
    by_path = {f["path"]: f for f in lock["files"]}
    want = list(dict.fromkeys(a.data_change))
    unknown = [p for p in want if p not in by_path]
    if unknown:
        print(f"REFUSED: not lock entries: {unknown}; nothing written", file=sys.stderr)
        return 1
    plan = []
    for p in want:
        f = by_path[p]
        new = show(a.product, commit, f["source_path"])
        if new is None:
            print(f"REFUSED: {f['source_path']} missing at {commit[:8]}; nothing written", file=sys.stderr)
            return 1
        kind = classify(open(p, "rb").read(), new)[0]
        print(f"DATA\t{p}\t{f['commit'][:8]}->{commit[:8]}\t{kind}\tsha256={hashlib.sha256(new).hexdigest()[:12]}")
        plan.append((f, new))
    if not a.write:
        return 0
    for f, new in plan:
        open(f["path"], "wb").write(new)
        f["commit"], f["sha256"] = commit, hashlib.sha256(new).hexdigest()
    open(LOCK, "w").write(json.dumps(lock, indent=1) + "\n")
    print(f"wrote {LOCK}: {len(plan)} entries -> {commit} (data change)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
