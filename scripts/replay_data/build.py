"""Rebuild the pinned ERCOT day offline, using only the Python standard library.

Input is the downloaded ZIP containing XLSX, or the recorded byte-cut excerpts
of those same archives. No forecast, interpolation or inferred availability.
"""

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
CENTRAL = ZoneInfo("America/Chicago")
POINTS = [
    f"{kind}_{zone}"
    for kind in ("HB", "LZ")
    for zone in ("HOUSTON", "NORTH", "SOUTH", "WEST")
]
HEADERS = {
    "rt_prices": [
        "Delivery Date",
        "Delivery Hour",
        "Delivery Interval",
        "Repeated Hour Flag",
        "Settlement Point Name",
        "Settlement Point Type",
        "Settlement Point Price",
    ],
    "da_prices": [
        "Delivery Date",
        "Hour Ending",
        "Repeated Hour Flag",
        "Settlement Point",
        "Settlement Point Price",
    ],
    "load": [
        "Hour Ending",
        "COAST",
        "EAST",
        "FWEST",
        "NORTH",
        "NCENT",
        "SOUTH",
        "SCENT",
        "WEST",
        "ERCOT",
    ],
}


class InputFailure(ValueError):
    """Typed input or qualification failure; no partial successful dataset."""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def iso(value):
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def day_bounds(day):
    local = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=CENTRAL)
    return local.astimezone(UTC), (local + timedelta(days=1)).astimezone(UTC)


def interval_start(day, hour, quarter, repeated):
    """ERCOT HE 1..24, interval 1..4; Y identifies the second repeated hour."""
    if not (1 <= hour <= 24 and 1 <= quarter <= 4 and repeated in ("N", "Y")):
        raise InputFailure("TIME_MAPPING: invalid HE, interval or repeated-hour flag")
    wall = datetime.combine(date.fromisoformat(day), datetime.min.time()) + timedelta(
        hours=hour - 1, minutes=15 * (quarter - 1)
    )
    candidates = sorted(
        {
            wall.replace(tzinfo=CENTRAL, fold=f).astimezone(UTC)
            for f in (0, 1)
            if wall.replace(tzinfo=CENTRAL, fold=f)
            .astimezone(UTC)
            .astimezone(CENTRAL)
            .replace(tzinfo=None)
            == wall
        }
    )
    if not candidates or (repeated == "Y" and len(candidates) != 2):
        raise InputFailure("TIME_MAPPING: nonexistent hour or unresolved repeated hour")
    return candidates[-1] if repeated == "Y" else candidates[0]


def read_rows(raw, source):
    """Parse captured archive envelopes and exact XLSX cell values, fail closed."""
    try:
        outer = zipfile.ZipFile(io.BytesIO(raw))
        inner = zipfile.ZipFile(io.BytesIO(outer.read(source["member"])))
        strings = [
            "".join(t.itertext())
            for t in ET.fromstring(inner.read("xl/sharedStrings.xml"))
        ]
        sheet = ET.fromstring(inner.read(source["sheet_path"]))
        if sheet.tag != NS + "worksheet":
            raise InputFailure("SCHEMA_INVALID: expected XLSX worksheet")
        rows = []
        for row in sheet.iter(NS + "row"):
            cells = {}
            for cell in row:
                address = cell.get("r", "")
                col = re.fullmatch(r"([A-Z]+)[0-9]+", address)
                if col is None or cell.find(NS + "f") is not None:
                    raise InputFailure("SCHEMA_INVALID: cell address or formula")
                value = cell.findtext(NS + "v")
                if value is None:
                    raise InputFailure("SCHEMA_INVALID: missing cell value")
                if cell.get("t") == "s":
                    value = strings[int(value)]
                elif cell.get("t") not in (None, "n"):
                    raise InputFailure("SCHEMA_INVALID: unsupported cell type")
                cells[col[1]] = value
            rows.append((int(row.attrib["r"]), cells))
    except zipfile.BadZipFile as exc:
        raise InputFailure("ARCHIVE_INVALID: expected ZIP containing XLSX") from exc
    except (KeyError, ET.ParseError, ValueError, IndexError) as exc:
        if isinstance(exc, InputFailure):
            raise
        raise InputFailure("SCHEMA_INVALID: malformed workbook") from exc
    if not rows:
        raise InputFailure("EMPTY_INPUT: worksheet has no rows")
    return rows


def normalize(rows, source, day, kind):
    headers = HEADERS[kind]
    columns = [chr(65 + i) for i in range(len(headers))]
    if rows[0][0] != 1 or rows[0][1] != dict(zip(columns, headers)):
        raise InputFailure("SCHEMA_INVALID: source columns differ from pinned schema")
    result = []
    date_label = date.fromisoformat(day).strftime("%m/%d/%Y")
    for number, cells in rows[1:]:
        if cells.keys() != rows[0][1].keys():
            raise InputFailure("SCHEMA_INVALID: incomplete row")
        values = [cells[c] for c in columns]
        if not values[0].startswith(date_label):
            continue
        try:
            if kind == "load":
                if not re.fullmatch(re.escape(date_label) + r" \d{2}:00", values[0]):
                    raise InputFailure(
                        "TIME_MAPPING: unresolved load hour-ending label"
                    )
                hour, quarter, flag, point, value = (
                    int(values[0][-5:-3]),
                    1,
                    "N",
                    "ERCOT",
                    values[9],
                )
            elif kind == "rt_prices":
                _, hour, quarter, flag, point, point_type, value = values
                if point not in POINTS:
                    continue
                # LZEW is a distinct energy-weighted price, not the requested LZ SPP.
                if point_type == "LZEW" and point.startswith("LZ_"):
                    continue
                if point_type != ("HU" if point.startswith("HB_") else "LZ"):
                    raise InputFailure(
                        "SCHEMA_INVALID: unexpected settlement point type"
                    )
                hour, quarter = int(hour), int(quarter)
            else:
                _, ending, flag, point, value = values
                if point not in POINTS:
                    continue
                if not re.fullmatch(r"\d{2}:00", ending):
                    raise InputFailure("TIME_MAPPING: invalid DAM hour ending")
                hour, quarter = int(ending[:2]), 1
            price = Decimal(value)
            if not price.is_finite() or (kind == "load" and not 0 < price < 150000):
                raise InputFailure("VALUE_INVALID: nonfinite or impossible load")
            start = interval_start(day, hour, quarter, flag)
        except (ValueError, ArithmeticError) as exc:
            if isinstance(exc, InputFailure):
                raise
            raise InputFailure("VALUE_INVALID: malformed number or time") from exc
        minutes = 15 if kind == "rt_prices" else 60
        result.append(
            {
                "interval_start": iso(start),
                "interval_end": iso(start + timedelta(minutes=minutes)),
                "central_label": start.astimezone(CENTRAL).isoformat(),
                "point": point,
                "value": float(price),
                "published_at": source["archive_published_at"],
                "available_at": None,
                "retrieved_at": source["retrieved_at"],
                "quality": "settlement_only_original_availability_unknown",
                "provenance": {"source": kind, "row": number},
            }
        )
    return sorted(result, key=lambda r: (r["interval_start"], r["point"]))


def check_coverage(rows, day, kind):
    start, end = day_bounds(day)
    minutes = 15 if kind == "rt_prices" else 60
    points = ["ERCOT"] if kind == "load" else POINTS
    expected = {
        (iso(start + timedelta(minutes=i * minutes)), p)
        for i in range(int((end - start).total_seconds() // (60 * minutes)))
        for p in points
    }
    keys = [(r["interval_start"], r["point"]) for r in rows]
    if len(set(keys)) != len(keys):
        raise InputFailure("DUPLICATE_KEY: repeated point/interval")
    if set(keys) != expected:
        raise InputFailure(
            f"COVERAGE_GAP: {kind}, missing={len(expected - set(keys))}, extra={len(set(keys) - expected)}"
        )


def extract(raw, source, day):
    """Repack original XML byte slices; never regenerate a source cell or value."""
    outer = zipfile.ZipFile(io.BytesIO(raw))
    inner = zipfile.ZipFile(io.BytesIO(outer.read(source["member"])))
    strings = [
        "".join(t.itertext()) for t in ET.fromstring(inner.read("xl/sharedStrings.xml"))
    ]
    label = date.fromisoformat(day).strftime("%m/%d/%Y")
    cuts = []
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for name in inner.namelist():
            data = inner.read(name)
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):

                def retain(match, name=name):
                    row = match.group()
                    node = ET.fromstring(
                        b'<root xmlns="' + NS[1:-1].encode() + b'">' + row + b"</root>"
                    )[0]
                    keep = node.get("r") == "1"
                    if name == source["sheet_path"]:
                        cell = node.find(NS + "c")
                        value = cell.findtext(NS + "v")
                        if cell.get("t") == "s" and strings[int(value)].startswith(
                            label
                        ):
                            keep = True
                    if keep:
                        cuts.append(
                            {
                                "member": name,
                                "start": match.start(),
                                "end": match.end(),
                                "sha256": sha(row),
                            }
                        )
                    return row if keep else b""

                data = re.sub(rb"<row\b[^>]*>.*?</row>", retain, data, flags=re.DOTALL)
            z.writestr(
                zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)),
                data,
                compress_type=zipfile.ZIP_DEFLATED,
            )
    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w") as z:
        z.writestr(
            zipfile.ZipInfo(source["member"], (1980, 1, 1, 0, 0, 0)),
            output.getvalue(),
            compress_type=zipfile.ZIP_DEFLATED,
        )
    return packed.getvalue(), cuts


def build(raw_dir, output, manifest, excerpt_dir=None):
    sources = manifest["sources"]
    day = manifest["day"]
    excerpt_manifest = raw_dir / "excerpts.json"
    excerpts = (
        json.loads(excerpt_manifest.read_text()) if excerpt_manifest.exists() else {}
    )
    products = {}
    extracted = {}
    coverage = {}
    for kind, source in sources.items():
        raw = (raw_dir / source["file"]).read_bytes()
        digest = sha(raw)
        record = excerpts.get(kind, {})
        if digest != source["raw_sha256"] and not (
            digest == record.get("sha256")
            and record.get("parent_sha256") == source["raw_sha256"]
            and record.get("day") == day
        ):
            raise InputFailure(f"HASH_MISMATCH: {kind}")
        rows = normalize(read_rows(raw, source), source, day, kind)
        check_coverage(rows, day, kind)
        coverage[kind] = {
            "complete": True,
            "observations": len(rows),
            "points": ["ERCOT"] if kind == "load" else POINTS,
        }
        products[kind + ".json"] = encoded(
            {
                "schema_version": 1,
                "day": day,
                "unit": "MW" if kind == "load" else "$/MWh",
                "resolution_minutes": 15 if kind == "rt_prices" else 60,
                "aggregation": "hourly average"
                if kind == "load"
                else "settlement point price",
                "observations": rows,
            }
        )
        if excerpt_dir:
            if digest != source["raw_sha256"]:
                raise InputFailure(
                    "HASH_MISMATCH: excerpts must be cut from full captured parents"
                )
            data, cuts = extract(raw, source, day)
            excerpt_dir.mkdir(parents=True, exist_ok=True)
            (excerpt_dir / source["file"]).write_bytes(data)
            extracted[kind] = {
                "day": day,
                "sha256": sha(data),
                "parent_sha256": digest,
                "transformation": "retain original header/day row byte ranges and XLSX metadata; repack ZIP",
                "retained_row_ranges": cuts,
            }
    products["esr.json"] = encoded(
        {
            "schema_version": 1,
            "day": day,
            "zone": "ERCOT",
            "status": "unavailable",
            "observations": [],
            "gaps": manifest["optional_gaps"],
        }
    )
    start, end = day_bounds(day)
    transformation = {
        "command": "python3 scripts/replay_data/build.py --raw-dir RAW_DIR --output OUTPUT_DIR",
        "script": "scripts/replay_data/build.py",
        "script_sha256": sha(Path(__file__).read_bytes()),
    }
    meta = {
        "schema_version": 1,
        "day": day,
        "selection_reason": manifest["selection_reason"],
        "sources": sources,
        "transformation": transformation,
        "time_conventions": {
            "timezone": "America/Chicago",
            "interval_start": iso(start),
            "interval_end": iso(end),
            "intervals": "UTC half-open [start,end)",
            "quarters": int((end - start).total_seconds() / 900),
            "hour_ending": "HE 1 starts 00:00; HE 24 ends next midnight; RT interval 1..4",
            "repeated_hour": "N first occurrence, Y second occurrence; nonexistent/unresolved times rejected",
            "dst_note": "D is CDT (UTC-05:00), no transition. Calendar supports 92/96/100 quarters; load archive ambiguous DST labels are rejected.",
            "published_at": "captured archive publication, not original interval publication; null when unknown",
            "available_at": "null: original availability and correction history not established",
        },
        "qualification": {
            "required_sources": coverage,
            "optional_gaps": manifest["optional_gaps"],
            "decision_eligible_series": [],
            "settlement_only_series": sorted(sources),
            "availability_gap": "ORIGINAL_AVAILABILITY_UNKNOWN: all required series; strict policy inputs unavailable",
            "status": "complete_settlement_day_with_explicit_availability_gaps",
        },
        "normalized_sha256": {name: sha(data) for name, data in products.items()},
    }
    products["meta.json"] = encoded(meta)
    lines = [
        f"# ERCOT replay provenance: {day}",
        "",
        manifest["selection_reason"],
        "",
        "Historical ERCOT observations; simulated households, batteries, procurement and outcomes.",
        "All required series are settlement/display-only: original publication/availability and revision history are unknown.",
        "`published_at` identifies the captured archive version; it is never backdated to the operating interval.",
        "",
        "## Captured sources",
        "",
    ]
    for kind, source in sources.items():
        lines += [
            f"### {kind} ({source['report_id']})",
            f"- URL: {source['url']}",
            f"- Retrieved UTC: {source['retrieved_at']}; HTTP {source['http_status']}",
            f"- Raw SHA-256: `{source['raw_sha256']}`",
            f"- Original filename: `{source['original_filename']}`",
            f"- Member: `{source['member']}`; sheet: `{source['sheet_name']}` (`{source['sheet_path']}`)",
            f"- Archive publication: {source['archive_published_at']}; correction version: {source['correction_version']}",
            f"- Pinned schema SHA-256: `{source['schema_sha256']}`",
            "",
        ]
    lines += [
        "## Transformation",
        "",
        f"`{transformation['command']}`",
        "",
        f"Script SHA-256: `{transformation['script_sha256']}`.",
        "Parse the actual ZIP/XLSX shared-string and worksheet bytes; select D and the eight named points, retaining HU/LZ and excluding LZEW.",
        "Convert hour-ending/quarter labels to UTC. Keep hourly load at hourly resolution. No filling, interpolation or price clipping.",
        "Canonical JSON is sorted by UTC start and point; numeric source values are converted to JSON numbers without price rounding.",
        "Normalized output hashes are in meta.json; meta.json SHA-256: `"
        + sha(products["meta.json"])
        + "`.",
        "",
        "## Reproduction and fixture provenance",
        "",
        "Run the same command with RAW_DIR=backend/tests/fixtures/replay_raw for a byte-identical complete rebuild.",
        "Create those excerpts from the downloaded parents with `--excerpt-dir backend/tests/fixtures/replay_raw`.",
        "excerpts.json records parent/output hashes and original uncompressed XML row byte ranges. Retained row bytes and all shared strings are unchanged; ZIP envelopes are repacked.",
        "Tests use explicitly labelled mutations of these captured parents for malformed, empty and error-envelope inputs.",
        "",
        "## Optional gaps",
        "",
    ]
    lines += [
        f"- {gap['code']}: {gap['reason']} Source: {gap['url']}"
        for gap in manifest["optional_gaps"]
    ]
    products["PROVENANCE.md"] = ("\n".join(lines) + "\n").encode()
    output.mkdir(parents=True, exist_ok=True)
    for name, data in products.items():
        (output / name).write_bytes(data)
    if excerpt_dir:
        (excerpt_dir / "excerpts.json").write_bytes(encoded(extracted))
    return {
        "day": day,
        "files": len(products),
        "bytes": sum(map(len, products.values())),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--manifest", type=Path, default=Path(__file__).with_name("sources.json")
    )
    parser.add_argument("--excerpt-dir", type=Path)
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                build(
                    args.raw_dir,
                    args.output,
                    json.loads(args.manifest.read_text()),
                    args.excerpt_dir,
                )
            )
        )
    except (InputFailure, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
