"""S67 / DEC-GM-113: captured ERCOT bytes, calendar boundaries and qualification.

Method=test. Success requires source reconciliation and exact rebuild, complete
coverage and explicit availability gaps. Negative inputs are labelled mutations
of the captured archives, never claimed as observed ERCOT responses.
"""

import importlib.util
import io
import json
import re
import subprocess
import sys
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/replay_data/build.py"
RAW = Path(__file__).parent / "fixtures/replay_raw"
DATA = ROOT / "backend/gridmarket_server/data/replay/2026-08-26"


def builder():
    spec = importlib.util.spec_from_file_location("replay_build", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_c1_captured_archives_reproduce_every_committed_byte(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--raw-dir", str(RAW), "--output", str(tmp_path)],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(p.name for p in DATA.iterdir())
    for path in DATA.iterdir():
        assert (tmp_path / path.name).read_bytes() == path.read_bytes()


def test_c1_complete_source_resolution_units_and_known_rows():
    b = builder()
    start = datetime(2026, 8, 26, 5, tzinfo=UTC)
    for name, minutes, count, unit in [
        ("rt_prices", 15, 768, "$/MWh"),
        ("da_prices", 60, 192, "$/MWh"),
        ("load", 60, 24, "MW"),
    ]:
        data = json.loads((DATA / f"{name}.json").read_text())
        rows = data["observations"]
        source = json.loads((SCRIPT.parent / "sources.json").read_text())["sources"][name]
        raw_rows = dict(b.read_rows((RAW / source["file"]).read_bytes(), source))
        value_column = {"rt_prices": "G", "da_prices": "E", "load": "J"}[name]
        for observation in rows:
            original = raw_rows[observation["provenance"]["row"]]
            assert observation["value"] == float(original[value_column])
        assert data["unit"] == unit and data["resolution_minutes"] == minutes
        assert len(rows) == count
        points = ["ERCOT"] if name == "load" else b.POINTS
        for point in points:
            series = [r for r in rows if r["point"] == point]
            assert [r["interval_start"] for r in series] == [
                b.iso(start + timedelta(minutes=i * minutes)) for i in range(1440 // minutes)
            ]
            for row in series:
                assert datetime.fromisoformat(row["interval_end"]) - datetime.fromisoformat(
                    row["interval_start"]
                ) == timedelta(minutes=minutes)
                assert (
                    (0 < row["value"] < 150000)
                    if name == "load"
                    else (-10000 < row["value"] < 10000)
                )
                assert row["available_at"] is None
                assert row["quality"] == "settlement_only_original_availability_unknown"
                assert row["retrieved_at"] and row["provenance"]["row"] >= 2
        # Expected values transcribed directly from captured source rows.
        if name == "rt_prices":
            houston = [r["value"] for r in rows if r["point"] == "HB_HOUSTON"]
            assert houston[0] == 27.19
            assert min(houston) == 26.54 and max(houston) == 780.46
            assert (
                max(
                    r["value"]
                    for r in rows
                    if r["point"] == "HB_HOUSTON"
                    and 17 <= datetime.fromisoformat(r["central_label"]).hour < 21
                )
                == 453.3
            )
        elif name == "da_prices":
            assert next(r for r in rows if r["point"] == "HB_HOUSTON")["value"] == 28.18
        else:
            assert rows[0]["value"] == 68173.928287000002
    assert sum(p.stat().st_size for p in DATA.iterdir()) < 2_000_000


def test_c1_qualification_hashes_and_optional_gaps():
    b = builder()
    meta = json.loads((DATA / "meta.json").read_text())
    assert meta["day"] == "2026-08-26"
    assert all(v["complete"] for v in meta["qualification"]["required_sources"].values())
    assert meta["qualification"]["decision_eligible_series"] == []
    assert set(meta["qualification"]["settlement_only_series"]) == {
        "rt_prices",
        "da_prices",
        "load",
    }
    assert {g["code"] for g in meta["qualification"]["optional_gaps"]} == {
        "ESR_DAY_NOT_CAPTURED",
        "SCED_NOT_YET_PUBLISHED",
    }
    assert json.loads((DATA / "esr.json").read_text())["observations"] == []
    for name, digest in meta["normalized_sha256"].items():
        assert b.sha((DATA / name).read_bytes()) == digest
    assert meta["transformation"]["script_sha256"] == b.sha(SCRIPT.read_bytes())
    for source in meta["sources"].values():
        assert source["http_status"] == 200
        assert source["raw_sha256"] and source["schema_sha256"]
        assert source["correction_version"] == "unknown; pinned captured archive version"


def test_r3_normal_and_both_dst_days_and_hour_ending():
    """Calendar cases are synthetic internal inputs, not external observations."""
    b = builder()
    for day, quarters in [("2026-08-26", 96), ("2026-03-08", 92), ("2026-11-01", 100)]:
        start, end = b.day_bounds(day)
        assert (end - start).total_seconds() / 900 == quarters
    assert b.interval_start("2026-08-26", 24, 4, "N") == datetime(2026, 8, 27, 4, 45, tzinfo=UTC)
    assert b.interval_start("2026-11-01", 2, 1, "Y") - b.interval_start(
        "2026-11-01", 2, 1, "N"
    ) == timedelta(hours=1)
    for hour, flag in [(3, "N"), (1, "Y"), (2, "?")]:
        with pytest.raises(b.InputFailure, match="TIME_MAPPING"):
            b.interval_start("2026-03-08", hour, 1, flag)


def test_r1_mutations_of_captured_parent_fail_typed():
    b = builder()
    manifest = json.loads((SCRIPT.parent / "sources.json").read_text())
    for source in manifest["sources"].values():
        parent = (RAW / source["file"]).read_bytes()
        # Captured-parent truncation / empty mutations; error-envelope replacement
        # is explicitly synthetic, representing the mandated negative contract.
        for payload in [parent[:32], parent[:0], b'{"error":"mutated captured parent"}']:
            with pytest.raises(b.InputFailure, match="ARCHIVE_INVALID"):
                b.read_rows(payload, source)
        outer = zipfile.ZipFile(io.BytesIO(parent))
        inner = zipfile.ZipFile(io.BytesIO(outer.read(source["member"])))
        sheet = inner.read(source["sheet_path"])
        mutations = [
            (b"<broken", "SCHEMA_INVALID"),
            (re.sub(rb"<row\b[^>]*>.*?</row>", b"", sheet, flags=re.DOTALL), "EMPTY_INPUT"),
        ]
        for changed, code in mutations:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as archive:
                for info in inner.infolist():
                    archive.writestr(
                        info.filename,
                        changed if info.filename == source["sheet_path"] else inner.read(info),
                    )
            out = io.BytesIO()
            with zipfile.ZipFile(out, "w") as archive:
                archive.writestr(source["member"], buf.getvalue())
            with pytest.raises(b.InputFailure, match=code):
                b.read_rows(out.getvalue(), source)
    rt = manifest["sources"]["rt_prices"]
    rows = b.read_rows((RAW / rt["file"]).read_bytes(), rt)
    # Schema-valid captured-row removal and duplication must block qualification.
    good = b.normalize(rows, rt, manifest["day"], "rt_prices")
    with pytest.raises(b.InputFailure, match="COVERAGE_GAP"):
        b.check_coverage(good[:-1], manifest["day"], "rt_prices")
    with pytest.raises(b.InputFailure, match="DUPLICATE_KEY"):
        b.check_coverage(good + good[:1], manifest["day"], "rt_prices")
