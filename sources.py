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
PARTIAL = "partial"  # status value in STATUS_FILE: some special-district rows published, others not yet sourced


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
    """Counts from the data and the pinned status file. A county the status file marks `partial` (some special-district rows
    published, others not yet sourced) counts as checked and is listed under "partial", not under "not_yet_sourced"."""
    counties = sorted(r["name"].removesuffix(" County") for r in _csv(COUNTIES_FILE))
    status = _csv(STATUS_FILE)
    open_ = sorted(r["county"] for r in status if r["status"] != PARTIAL)
    partial = sorted(r["county"] for r in status if r["status"] == PARTIAL)
    with_rows = sorted({r["county"] for r in rows if r["state"] == state and r["year"] == year and r["body_type"] == "special_district"})
    checked = [c for c in counties if c not in open_]
    in_csv = sorted({r["county"] for r in _csv(SD_FILE) if r["state"] == state and r["year"] == year and r["body_type"] == "special_district"})
    return {"in_csv": len(in_csv), "sd_rows_in_csv": sum(1 for r in _csv(SD_FILE) if r["state"] == state and r["year"] == year and r["body_type"] == "special_district"), "counties_in_csv": in_csv, "alt_only": [c for c in with_rows if c not in in_csv],
            "counties": counties, "checked": len(checked), "total": len(counties), "with_rows": len(with_rows),
            "no_rows": [c for c in checked if c not in with_rows], "not_yet_sourced": open_, "partial": partial, "counties_with_rows": with_rows}


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


# Alt-source rows (data/special/fl-2025-alt-sources.csv) come from two kinds of document; the kind is read from source_agency.
ALT_KINDS = (("pa", re.compile(r"County Property Appraiser")), ("wmd", re.compile(r"Water Management District")))


def alt_kinds(state="FL", year="2025"):
    """{county: kind} for every county with special-district rows in the alt-sources CSV. Unknown agency or a county whose
    alt rows mix kinds raises DataError."""
    out = {}
    for r in _csv(ALT_FILE):
        if r["state"] != state or r["year"] != year or r["body_type"] != "special_district":
            continue
        k = next((k for k, pat in ALT_KINDS if pat.search(r["source_agency"])), None)
        if k is None:
            raise DataError(f"alt-source agency of unknown kind: {r['source_agency']!r}")
        if out.setdefault(r["county"], k) != k:
            raise DataError(f"{r['county']}: alt-source rows mix document kinds")
    return out


def alt_counts(alt, state="FL", year="2025"):
    """{county: special-district rows} for the alt-only counties, counted from the alt-sources CSV."""
    rows = [r for r in _csv(ALT_FILE) if r["state"] == state and r["year"] == year and r["body_type"] == "special_district"]
    return {c: sum(1 for r in rows if r["county"] == c) for c in alt}


def _by_kind(counts):
    kinds = alt_kinds()
    out = {}
    for c, n in counts.items():  # a county with no alt row keeps the original (property appraiser) wording, as before this split
        out.setdefault(kinds.get(c, "pa"), {})[c] = n
    return [(k, out[k]) for k, _ in ALT_KINDS if k in out]


def alt_sentence(counts):
    """Body text: counties whose special-district rows come only from alt sources (not in the baseline CSV), one sentence per
    document kind: county property appraisers (FL_SD_COPY, kept wording) and water management district documents (FL_HUB_COPY).
    Wording: placeholder pending Lindsay; it no longer says the rows are on county pages only (OQ-11)."""
    out = []
    for kind, cs in _by_kind(counts):
        names = join_names([c + " (" + plural(n, "row") + ")" for c, n in cs.items()])
        copy = FL_SD_COPY if kind == "pa" else FL_HUB_COPY["alt"]
        out.append(copy["alt_tail_one" if len(cs) == 1 else "alt_tail_many"].format(names=names))
    return " ".join(out)


def alt_meta_sentence(counts):
    """Meta description / JSON-LD wording for the same counties."""
    return " ".join((FL_SD_COPY if kind == "pa" else FL_HUB_COPY["alt"])["alt_tail_meta"].format(names=join_names(list(cs))) for kind, cs in _by_kind(counts))


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
    "alt_tail_one": "{names} has special-district rates from its county property appraiser, not the baseline CSV.",  # kept (OQ-11 OK)
    "alt_tail_many": "{names} have special-district rates from their county property appraisers, not the baseline CSV.",  # kept (OQ-11 OK)
    "alt_tail_meta": "{names} special-district rows come from county appraisers, not the baseline CSV.",  # kept (OQ-11 OK)
    "home_lead_tail": "more come from county property appraisers, not the baseline CSV.",  # new (OQ-11 rewrite)
    "home_link": "Florida independent special districts: one page each, every rate sourced",  # new
    "county_link": "All Florida independent special districts",  # kept
    "hub_title": "Florida special district millage rates 2025",  # new
    "hub_h1": "Florida independent special districts, 2025",  # kept
    "hub_desc": "Every Florida independent special district with a sourced 2025 millage rate, one page each, every rate linked to its official source.",  # new
    "hub_intro": ("Independent special districts are local taxing bodies with their own boards, such as water management, fire, hospital and children's services districts. "
                  "Each sets its own millage (dollars per $1,000 of taxable value), and it applies only to property inside the district. "
                  "Pick a district to see its 2025 rate in every county where we have a sourced row."),  # new
    "hub_filter": "Filter by district or county",  # kept
    "hub_sources": "Source files",  # kept
    "hub_sources_summary": "Every source file behind these pages, by county",  # kept
    "body_title": "{name} millage rate 2025",  # new
    "body_desc": "{name} 2025 millage {rates} in {counties}, Florida, as published, each linked to its official source.",  # new
    "body_intro": ("An independent special district has its own board, which sets a millage that applies only to property inside the district. "
                   "Rates are in mills: dollars per $1,000 of taxable value. "
                   "This page lists every 2025 rate we have sourced for this district, by county."),  # new
    "also_printed": "Also printed as",  # kept
    "rows_note": ("One row per published rate, linked to its source file. The short code is the start of that file's sha256 fingerprint; hover it for the full value. "
                  "Rates are never added together."),  # new
    "absent_note": "A county missing from this table has no sourced row for this district. That doesn't mean the district levies nothing there: absent is not zero.",  # new
    "nys_lead": "Independent special districts in these counties are not yet sourced (absent is not zero):",  # new
    "nys_reason": {"no_file": "no 2025 TACD file", "exception": "2025 TACD file not yet verified"},  # no_file kept (spec wording); exception new
    "coverage_h2": "Coverage",  # kept
    "llms_line": ("- Florida independent special-district pages, 2025: hub {hub}; one page per district at {base}/fl/special-districts/<slug>/ "
                  "(slug = body_id without the leading 'fl-' and trailing '-special_district'), with index.json beside each page holding exactly that page's rows. "
                  "A county missing from a district's page has no sourced row there; absent is not zero, never read it as a 0 rate.\n"),  # kept
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


# ---------- Florida hub /fl/ (OM-FL-COVERAGE-001) ----------
FL_HUB = "fl"
# PLACEHOLDER COPY pending the writing pass (Lindsay) and the by-eye pass (Ann), OM-FL-COVERAGE-001: every new reader-facing
# string of the /fl/ hub, the "partial" county line, the water-management-district alt-source wording, the big_cypress_basin
# levy label and the Florida breadcrumb label lives here only. Counts and county names are always computed, never written here.
FL_HUB_COPY = {
    "crumb": "Florida",  # breadcrumb label linking /fl/ on every page under /fl/
    "title": "Florida property tax rates by county: sources and coverage, 2025",
    "h1": "Florida property tax rates, 2025",
    "desc": ("Every Florida county page, with what we have sourced for each county's independent special districts "
             "and what is not yet sourced. No estimates."),
    "intro": ("Each county page lists the 2025 millage rates we have from official sources, each linked to its source. "
              "The table below also shows how far we have got with each county's independent special districts."),
    "absent": "A county or district with no row has not been sourced yet: absent is not zero.",
    "with_rows": ("{n} of {total} Florida counties have at least one sourced special-district row: {csv} from the county's "
                  "2025 TACD file and {alt} only from other official documents."),
    "sections_h2": "Florida pages",
    "sections": {"special_districts": "Independent special districts, one page each",
                 "amendment_3": "Amendment 3: the 2025 adopted millage baseline",
                 "rolled_back": "Rolled-back rate vs adopted millage, 2025"},
    "table_h2": "Counties",
    "table_caption": "Florida county pages and special-district coverage, 2025",
    "th_county": "County page",
    "th_sd": "Independent special districts",
    "status_sourced": "sourced ({bodies})",
    "status_sourced_alt": "sourced ({bodies}, {kind})",
    "alt_kind": {"wmd": "water management district document", "pa": "county property appraiser document"},
    "status_partial": "partial ({bodies} sourced). Recorded reason: {reason}",
    "status_open": "not yet sourced: {reason}",
    "status_none": "no special-district rows published yet",
    "status_multi": "city spanning more than one county; see each county's page",
    "body": ("body", "bodies"),
    "partial_line": "Partial coverage: some independent special districts in this county are sourced and others are not yet. Recorded reason: {reason}",
    "partial_list": "Partial coverage (some districts sourced, others not yet): {names}.",
    "partial_badge": "special districts partly sourced",
    "levy_labels": {"big_cypress_basin": "Big Cypress Basin"},  # display label only; the data value stays big_cypress_basin
    "lead_wmd": "water management districts",  # homepage source-type name for alt rows from WMD documents
    "home_lead_tail_split": "{pa} more come from county property appraisers and {wmd} from water management district documents, not the baseline CSV.",
    "home_link": "Florida: every county page and special-district coverage",
    "alt": {
        "alt_tail_one": "{names} has special-district rates from a water management district document, not the baseline CSV.",
        "alt_tail_many": "{names} have special-district rates from water management district documents, not the baseline CSV.",
        "alt_tail_meta": "{names} special-district rows come from water management district documents, not the baseline CSV.",
    },
    "llms_line": ("- Florida hub: {url} (every Florida county page and each county's special-district coverage: sourced, partial "
                  "or not yet sourced with the recorded reason; absent is not zero).\n"),
}


def fl_hub_status(label, cov, rows, state="FL", year="2025"):
    """(kind, text) for one county label's special-district coverage, computed from the rows and the status file.
    kind: sourced | sourced_alt | partial | open | none | multi."""
    C = FL_HUB_COPY
    reasons = {c: (st, why) for c, st, why in open_counties()}
    bodies = sorted({r["body_id"] for r in rows if r["state"] == state and r["year"] == year and r["county"] == label and r["body_type"] == "special_district"})
    nb = plural(len(bodies), *C["body"])
    if label not in cov["counties"]:
        return "multi", C["status_multi"]
    if label in cov["not_yet_sourced"]:
        return "open", C["status_open"].format(reason=reasons[label][1])
    if label in cov["partial"]:
        return "partial", C["status_partial"].format(bodies=nb, reason=reasons[label][1])
    if not bodies:
        return "none", C["status_none"]
    if label in cov["alt_only"]:
        return "sourced_alt", C["status_sourced_alt"].format(bodies=nb, kind=C["alt_kind"][alt_kinds()[label]])
    return "sourced", C["status_sourced"].format(bodies=nb)
