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
NOTE_OVERRIDES = {
    ("Orange", "fl-sjrwmd-special_district"): "Rate as printed in the county's 2025 final millage table.",
    ("Orange", "fl-sfwmd-special_district"): "Shown as one combined rate. Orange County's authority list prints it in three parts: 0.0948 + 0.1026 + 0.0327 = 0.2301.",
    ("Orange", "fl-cftod-special_district"): "Formerly Reedy Creek Improvement District. Independent special district. Printed as one combined operating and debt rate, levied only in mill code 70 (Bay Lake, Lake Buena Vista and unincorporated Reedy Creek).",
}
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
                independence=r.get("independence") or None, note=NOTE_OVERRIDES.get((r["county"], r["body_id"]), r.get("note") or None), also_cited=r.get("also_cited") or None)


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
    in_csv = sorted({r["county"] for r in _csv(SD_FILE) if r["state"] == state and r["year"] == year and r["body_type"] == "special_district"})
    return {"in_csv": len(in_csv), "sd_rows_in_csv": sum(1 for r in _csv(SD_FILE) if r["state"] == state and r["year"] == year and r["body_type"] == "special_district"), "counties_in_csv": in_csv, "alt_only": [c for c in with_rows if c not in in_csv],
            "counties": counties, "checked": len(checked), "total": len(counties), "with_rows": len(with_rows),
            "no_rows": [c for c in checked if c not in with_rows], "not_yet_sourced": open_, "counties_with_rows": with_rows}


def data_updated(rows):
    """Footer date: the latest retrieved_at across all published rows (from the data, not the build clock), as an
    America/New_York date, plus the source_url of that retrieval (ties broken by URL)."""
    import datetime
    from zoneinfo import ZoneInfo
    latest = max(r["retrieved_at"] for r in rows)
    url = min(r["source_url"] for r in rows if r["retrieved_at"] == latest)
    return datetime.datetime.fromisoformat(latest).astimezone(ZoneInfo("America/New_York")).date(), url


def plural(n, one, many=None):
    """'1 rate', '2 rates': the count followed by the noun, singular only when n == 1."""
    return f"{n} {one if n == 1 else (many or one + 's')}"


def join_names(xs):
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def alt_counts(alt, state="FL", year="2025"):
    """{county: special-district rows} for the alt-only counties, counted from the alt-sources CSV."""
    rows = [r for r in _csv(ALT_FILE) if r["state"] == state and r["year"] == year and r["body_type"] == "special_district"]
    return {c: sum(1 for r in rows if r["county"] == c) for c in alt}


def alt_sentence(counts):
    """Body text: counties whose special-district rows come only from county property appraisers (not in the baseline CSV).
    Wording: FL_SD_COPY (placeholder pending Lindsay); it no longer says the rows are on county pages only (OQ-11)."""
    names = join_names([c + " (" + plural(n, "row") + ")" for c, n in counts.items()])
    return FL_SD_COPY["alt_tail_one" if len(counts) == 1 else "alt_tail_many"].format(names=names)


def alt_meta_sentence(counts):
    """Meta description / JSON-LD wording for the same counties."""
    return FL_SD_COPY["alt_tail_meta"].format(names=join_names(list(counts)))


def coverage_sentence(cov, meta=False):
    """Counts match the published Amendment 3 baseline CSV (TACD special-district rows). Counties whose only special-district
    rows come from county property appraisers (alt sources, county pages/JSON only) are named separately, not counted."""
    counts = alt_counts(cov["alt_only"])
    tail = (" " + (alt_meta_sentence if meta else alt_sentence)(counts) if counts else "")
    return (f"{cov['checked']} of {cov['total']} Florida counties checked against official sources; {cov['in_csv']} have special-district rows "
            f"in the Amendment 3 baseline CSV.{tail}")


# ---------- FL independent special-district body pages (OM-SITE-SPECIAL-ISD-001) ----------
H1_FILE = "data/ref/fl_special_body_h1.csv"  # site-authored H1 picks for bodies printed under more than one name (not a data file; not lock-pinned)
SD_HUB = "fl/special-districts"
# PLACEHOLDER COPY pending Lindsay (writing brief OM-SITE-SPECIAL-ISD-001): every new reader-facing string for the FL
# special-district pages, the reworded alt-source tail of the coverage sentence and the home-page lead tail live here only,
# so her approved strings drop in without structural change. Fixed strings that must not be reworded are NOT here: the computed
# coverage head (coverage_sentence), "No special-district rows published yet for this county." (build.NO_ROWS), "not yet sourced".
FL_SD_COPY = {
    "alt_tail_one": "{names} has special-district rates from its county property appraiser, not the baseline CSV.",
    "alt_tail_many": "{names} have special-district rates from their county property appraisers, not the baseline CSV.",
    "alt_tail_meta": "{names} special-district rows come from county appraisers, not the baseline CSV.",
    "home_lead_tail": "more, from county property appraisers, are not in the baseline CSV.",
    "home_link": "Every Florida independent special district, one page each",
    "county_link": "All Florida independent special districts",
    "hub_title": "Florida special district property tax rates 2025",
    "hub_h1": "Florida independent special districts, 2025",
    "hub_desc": "Every Florida independent special district with a sourced 2025 millage rate, one page each, every rate linked to its government source.",
    "hub_intro": ("Independent special districts are taxing bodies with their own elected or appointed boards, such as water management, "
                  "fire, hospital and children's services districts. Each sets its own millage, and it applies only to property inside the district. "
                  "Pick a district to see its 2025 rate in every county where we have a sourced row."),
    "hub_filter": "Filter by district or county",
    "hub_sources": "Source files",
    "hub_sources_summary": "Every source file behind these pages, by county",
    "body_title": "{name} property tax rate 2025",
    "body_desc": "{name}: official 2025 millage {rates} in {counties}, Florida, each linked to its government source.",
    "body_intro": ("{name} is an independent special district. Its board sets its own millage, which applies only to property inside the district. "
                   "Rates are in mills: dollars per $1,000 of taxable value."),
    "also_printed": "Also printed as",
    "rows_note": "One row per published rate. Each rate links to its source file; hover the short code for the file's full sha256. Rates are shown as published, never summed.",
    "absent_note": "Counties not listed here have no sourced row for this district. That does not mean the district levies nothing there; absent is not zero.",
    "nys_lead": "Independent special districts not yet sourced in these counties (absent is not zero):",
    "nys_reason": {"no_file": "no 2025 TACD file", "exception": "2025 TACD file not yet reconciled"},
    "coverage_h2": "Coverage",
    "llms_line": ("- Florida independent special-district pages, 2025: hub {hub}; one page per district at {base}/fl/special-districts/<slug>/ "
                  "(slug = body_id without the leading 'fl-' and trailing '-special_district'), with index.json beside each page holding exactly that page's rows. "
                  "A county missing from a district's page has no sourced row there; absent is not zero, never read it as a 0 rate.\n"),
}


def sd_slug(body_id):
    m = re.fullmatch(r"fl-(.+)-special_district", body_id)
    if not m:
        raise DataError(f"special-district body_id not of the form fl-<slug>-special_district: {body_id}")
    return m.group(1)


# LAYOUT (b)3 / L1: inside a county the SFWMD-style parts read Operating, Okeechobee Basin, Everglades Construction; any other
# component follows in file order. Rows are reordered only: never relabelled, merged or summed.
SD_PART_ORDER = ("operating", "okeechobee_basin", "everglades_construction")


def sd_row_order(r):
    c = r["levy_component"]
    return (r["county"], SD_PART_ORDER.index(c) if c in SD_PART_ORDER else len(SD_PART_ORDER))


def fl_bodies(rows, h1_path=H1_FILE, display=lambda s: s):
    """{body_id: {"slug", "names": [published taxing_body strings, display form], "h1", "rows": [row...]}} for every
    special_district row of the merged FL set (TACD + alt-source special rows; cite-only rows are never special_district).
    The H1 is the published name; bodies printed under more than one name take theirs from h1_path, and that pick must be one of
    the body's published names. Raises DataError (before anything is written) on a bad pick, a missing pick or a slug collision."""
    out = {}
    for r in rows:
        if r["body_type"] == "special_district":
            out.setdefault(r["body_id"], {"rows": []})["rows"].append(r)
    picks = {}
    for p in _csv(h1_path) if os.path.exists(h1_path) else []:
        if p["body_id"] in picks:
            raise DataError(f"{h1_path}: duplicate body_id {p['body_id']}")
        picks[p["body_id"]] = p["h1"]
    for bid in picks:
        if bid not in out:
            raise DataError(f"{h1_path}: {bid} is not a special-district body in the data")
    slugs = {}
    for bid in sorted(out):
        b = out[bid]
        b["rows"].sort(key=sd_row_order)  # counties A-Z; inside a county SD_PART_ORDER, then any other component in file order (stable)
        names = []
        for r in b["rows"]:
            n = display(r["taxing_body"])
            if n not in names:
                names.append(n)
        b["names"] = names
        if bid in picks:
            if picks[bid] not in names:
                raise DataError(f"{h1_path}: h1 {picks[bid]!r} for {bid} is not one of its published names {names}")
            b["h1"] = picks[bid]
        elif len(names) > 1:
            raise DataError(f"{bid} is printed under {len(names)} names {names}; pick one of them in {h1_path}")
        else:
            b["h1"] = names[0]
        b["slug"] = sd_slug(bid)
        if b["slug"] in slugs:
            raise DataError(f"special-district page slug collision: {b['slug']} ({slugs[b['slug']]}, {bid})")
        slugs[b["slug"]] = bid
    return out


def open_counties():
    """[(county, status, reason)] from the pinned TACD status file, file order."""
    return [(r["county"], r["status"], r["reason"]) for r in _csv(STATUS_FILE)]
