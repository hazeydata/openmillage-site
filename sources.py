import csv, glob, hashlib, json, os, re

BASE_KEYS = ["state", "year", "county", "taxing_body", "body_type", "body_id", "nces_leaid", "fips", "levy_component", "levy_scope",
             "rate_kind", "rate", "unit", "source_agency", "source_url", "sha256", "retrieved_at"]
EXTRA_KEYS = ["source_page", "extraction", "printed_label", "independence", "note", "also_cited", "additional_sources"]
BASE_FILE = "data/fl-2025.csv"
SD_FILE = "data/special/fl-2025-special-districts.csv"
ALT_FILE = "data/special/fl-2025-alt-sources.csv"
STATUS_FILE = "data/special/tacd_county_status_open.csv"
COUNTIES_FILE = "data/ref/fl_census_counties_2024.csv"
LOCK = "data/SOURCES.lock"
COMBINED = {"all_components_combined": "operating + debt, combined"}
HEX = re.compile(r"^[0-9a-f]{64}$")


class DataError(Exception):
    pass


def read_lock(path=LOCK):
    lock = json.load(open(path))
    listed = {f["path"] for f in lock["files"]}
    on_disk = {p for p in glob.glob("data/**/*", recursive=True) if os.path.isfile(p) and not p.startswith("data/ref/") and p != LOCK}
    on_disk |= set(glob.glob(os.environ.get("DATA_GLOB", "data/*.csv")))
    if on_disk - listed:
        raise DataError(f"data files not listed in {path}: {sorted(on_disk - listed)}")
    for f in lock["files"]:
        if not (f.get("repo") and f.get("commit") and f.get("source_path")):
            raise DataError(f"lock entry incomplete: {f['path']}")
        got = hashlib.sha256(open(f["path"], "rb").read()).hexdigest()
        if got != f["sha256"]:
            raise DataError(f"sha256 mismatch for {f['path']}: lock {f['sha256']} file {got}")
    return lock


def _csv(path):
    return list(csv.DictReader(open(path, newline="", encoding="utf-8")))


def _row(r, **extra):
    out = {k: r[k] for k in BASE_KEYS}
    out.update({k: None for k in EXTRA_KEYS})
    out.update(extra)
    return out


def _sd(r, label):
    return _row(r, source_page=r.get("source_page") or None, extraction=r.get("extraction") or None, printed_label=r.get(label) or None,
                independence=r.get("independence") or None, note=r.get("note") or None, also_cited=r.get("also_cited") or None)


def key(r):
    return (r["county"], r["body_id"], r["levy_component"], r["rate_kind"])


def load_rows(lock=None):
    lock = lock or read_lock()
    paths = {f["path"] for f in lock["files"]}
    for p in (BASE_FILE, SD_FILE, ALT_FILE, STATUS_FILE):
        if p not in paths:
            raise DataError(f"{p} missing from lock")
    rows = [_row(r) for r in _csv(BASE_FILE)]
    sd = [_sd(r, "tacd_column_label") for r in _csv(SD_FILE)]
    alt = _csv(ALT_FILE)
    sd += [_sd(r, "printed_label") for r in alt if r["body_type"] == "special_district"]
    for r in sd:
        if r["body_type"] != "special_district" or r["levy_component"] in ("mstu", "dependent_special_district") or r["rate_kind"] != "adopted":
            raise DataError(f"not an independent special-district row: {key(r)}")
        if not re.match(r"^https?://\S+$", r["source_url"] or "") or not HEX.match(r["sha256"] or ""):
            raise DataError(f"special-district row without source_url or sha256: {key(r)}")
    index = {}
    for r in rows + sd:
        if key(r) in index:
            raise DataError(f"duplicate key {key(r)}")
        index[key(r)] = r
    for a in alt:
        if a["body_type"] == "special_district":
            continue
        k = key(a)
        if k not in index:
            raise DataError(f"cite-only row has no base row: {k}")
        b = index[k]
        if b["rate"] != a["rate"] or b["unit"] != a["unit"]:
            raise DataError(f"cite-only rate {a['rate']} differs from base {b['rate']}: {k}")
        b["additional_sources"] = (b["additional_sources"] or []) + [{"source_agency": a["source_agency"], "source_url": a["source_url"],
                                   "sha256": a["sha256"], "source_page": a["source_page"] or None, "retrieved_at": a["retrieved_at"]}]
    return rows + sd


def coverage(rows, state="FL", year="2025"):
    counties = sorted(r["name"].removesuffix(" County") for r in _csv(COUNTIES_FILE))
    open_ = sorted(r["county"] for r in _csv(STATUS_FILE))
    with_rows = sorted({r["county"] for r in rows if r["state"] == state and r["year"] == year and r["body_type"] == "special_district"})
    checked = [c for c in counties if c not in open_]
    return {"counties": counties, "checked": len(checked), "total": len(counties), "with_rows": len(with_rows),
            "no_rows": [c for c in checked if c not in with_rows], "not_yet_sourced": open_, "counties_with_rows": with_rows}


def coverage_sentence(cov):
    return f"{cov['checked']} of {cov['total']} Florida counties checked against official sources; {cov['with_rows']} have special-district rows."
