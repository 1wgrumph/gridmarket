"""S76 red tests: ERCOT parsing by producer/spec shapes (R1-01, R1-02, R1-04, R1-07, R1-08, R1-11, R1-12).

Rule 7: payload shapes come from ERCOT's published Public API spec
(pubapi-apim-api.json, e361e39) and the real Worker snapshot body
(ercot-hackathon/src/snapshot.js); values are synthetic. See s76_spec.py.
"""

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from gridmarket_server import ercot

import s76_spec

NOW = datetime(2026, 9, 26, 14, 0, 10, tzinfo=UTC)
H14, H15 = "2026-09-26T14:00:00+00:00", "2026-09-26T15:00:00+00:00"
HELPER = Path(__file__).parent.parent.parent / "ercot-hackathon/test/snapshot-stub.mjs"


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


@pytest.fixture(autouse=True)
def frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ercot, "datetime", FrozenDatetime)
    monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "signals.db"))
    ercot.stats.snapshot_age_s = None


def rows(report: str, zone: str) -> list:
    return ercot.signals.series(report, zone, "2020-01-01", "2030-01-01")


# R1-01: parse_snapshot reads the Worker's real shape.
def test_s76_r1_01_snapshot_worker_shape_stores_sections() -> None:
    ercot.parse_snapshot(json.loads(json.dumps(s76_spec.SNAPSHOT)))
    assert ercot.signals.latest("SNAPSHOT-DEMAND", "ERCOT").value == 70234
    assert ercot.signals.latest("SNAPSHOT-HUBS", "HB_NORTH").value == 51.25
    assert ercot.signals.latest("SNAPSHOT-HUBS", "HB_HOUSTON").value == 48.5
    assert ercot.signals.latest("SNAPSHOT-DAM", "HB_NORTH").value == 60.75
    assert ercot.signals.latest("SNAPSHOT-SCED", "lambda").value == 36.5
    assert ercot.signals.latest("SNAPSHOT-DEMAND", "ERCOT").interval_start == "2026-09-26T14:00:00Z"
    # Null prices are skipped, never stored.
    assert ercot.signals.latest("SNAPSHOT-HUBS", "HB_SOUTH") is None
    assert ercot.signals.latest("SNAPSHOT-HUBS", "HB_WEST") is None


def test_s76_r1_01_snapshot_partial_failure_stores_rest_and_marks_section() -> None:
    payload = json.loads(json.dumps(s76_spec.SNAPSHOT))
    del payload["hubs"]
    payload["errors"] = {"spp": "np6-905 timeout"}
    ercot.parse_snapshot(payload)  # Must not raise: other sections are usable.
    assert ercot.signals.latest("SNAPSHOT-DEMAND", "ERCOT").value == 70234
    assert ercot.signals.latest("SNAPSHOT-SCED", "lambda").value == 36.5
    import os

    assert (os.environ["GRIDMARKET_DB"], "SNAPSHOT-HUBS") in ercot.signals.failed


def test_s76_r1_01_snapshot_all_failed_raises_and_keeps_age_unset() -> None:
    with pytest.raises(ValueError):
        ercot.parse_snapshot(json.loads(json.dumps(s76_spec.SNAPSHOT_ALL_FAILED)))
    assert rows("SNAPSHOT-DEMAND", "ERCOT") == []
    assert ercot.stats.snapshot_age_s is None


def test_s76_r1_01_contract_worker_build_snapshot_feeds_parse_snapshot() -> None:
    if shutil.which("node") is None:  # pragma: no cover
        pytest.skip("node is required for the Worker contract test")
    out = subprocess.run(
        ["node", str(HELPER)], capture_output=True, text=True, timeout=60, check=True
    )
    ercot.parse_snapshot(json.loads(out.stdout))
    assert ercot.signals.latest("SNAPSHOT-DEMAND", "ERCOT").value == 70234
    assert ercot.signals.latest("SNAPSHOT-HUBS", "HB_NORTH").value == 51.25
    assert ercot.signals.latest("SNAPSHOT-DAM", "HB_NORTH").value == 60.75
    assert ercot.signals.latest("SNAPSHOT-SCED", "lambda").value == 36.5


# R1-02: report parsers read spec columns.
def test_s76_r1_02_np6_905_spec_columns() -> None:
    ercot.parse_report(
        "NP6-905-CD", s76_spec.np6_905([["2026-09-26", 10, 1, "LZ_HOUSTON", "LZ", 50.1, False]])
    )
    signal = ercot.signals.latest("NP6-905-CD", "LZ_HOUSTON")
    assert (signal.value, signal.interval_start, signal.interval_minutes, signal.unit) == (
        50.1,
        H14,
        15,
        "$/MWh",
    )
    assert signal.published_at == "2026-09-26T14:15:00+00:00"  # Interval end; no publish column.


def test_s76_r1_02_np4_190_hour_ending_string() -> None:
    ercot.parse_report(
        "NP4-190-CD", s76_spec.np4_190([["2026-09-26", "10:00", "LZ_HOUSTON", 61.0, False]])
    )
    signal = ercot.signals.latest("NP4-190-CD", "LZ_HOUSTON")
    assert (signal.value, signal.interval_start, signal.interval_minutes) == (61.0, H14, 60)
    assert signal.published_at == H15


def test_s76_r1_02_np3_565_wide_row_unpivots_and_rolls_up() -> None:
    ercot.parse_report(
        "NP3-565-CD",
        s76_spec.np3_565(
            [
                                ["2026-09-26T08:30:00", "2026-09-26", "10:00", 18000, 2000, 6000,
                                 1500, 14000, 9000, 4000, 1300, 55800, "E", True, False]
                            ]
        ),
    )
    assert ercot.signals.latest("NP3-565-CD", "Coast").value == 18000
    assert ercot.signals.latest("NP3-565-CD", "Far West").value == 6000
    assert ercot.signals.latest("NP3-565-CD", "Coast").interval_start == H14
    assert ercot.signals.latest("NP3-565-CD", "Coast").published_at == "2026-09-26T08:30:00"
    assert ercot.signals.latest("NP3-565-CD", "LZ_HOUSTON").value == 18000
    assert ercot.signals.latest("NP3-565-CD", "LZ_NORTH").value == 17500
    assert ercot.signals.latest("NP3-565-CD", "LZ_SOUTH").value == 13000
    assert ercot.signals.latest("NP3-565-CD", "LZ_WEST").value == 7300


def test_s76_r1_02_np3_565_skips_retired_model_rows() -> None:
    ercot.parse_report(
        "NP3-565-CD",
        s76_spec.np3_565(
            [
                                ["2026-09-26T08:30:00", "2026-09-26", "10:00", 1, 1, 1, 1, 1, 1,
                                 1, 1, 8, "OLD", False, False]
                            ]
        ),
    )
    assert rows("NP3-565-CD", "Coast") == []
    assert rows("NP3-565-CD", "LZ_HOUSTON") == []


def test_s76_r1_02_np3_233_operating_date_wide_zones() -> None:
    ercot.parse_report(
        "NP3-233-CD",
        s76_spec.np3_233([["2026-09-26T08:05:00", "2026-09-26", 10, 3000, 4000, 1500, 2310]]),
    )
    assert ercot.signals.latest("NP3-233-CD", "LZ_HOUSTON").value == 2310
    assert ercot.signals.latest("NP3-233-CD", "LZ_SOUTH").value == 3000
    assert ercot.signals.latest("NP3-233-CD", "LZ_NORTH").value == 4000
    assert ercot.signals.latest("NP3-233-CD", "LZ_WEST").value == 1500
    assert ercot.signals.latest("NP3-233-CD", "LZ_HOUSTON").interval_start == H14
    assert ercot.signals.latest("NP3-233-CD", "LZ_HOUSTON").published_at == "2026-09-26T08:05:00"


def test_s76_r1_02_np6_86_central_timestamp_converts_to_utc() -> None:
    ercot.parse_report("NP6-86-CD", s76_spec.np6_86([s76_spec.sced_row("2026-09-26T09:05:13", "C1", 125.5)]))
    signal = ercot.signals.latest("NP6-86-CD", "C1")
    assert signal.value == 125.5
    assert signal.interval_start == "2026-09-26T14:05:13+00:00"  # 09:05 CDT.


# R1-08: roll-up per hour, not one row for the last hour.
def test_s76_r1_08_np3_565_roll_up_keeps_every_hour() -> None:
    ercot.parse_report(
        "NP3-565-CD",
        s76_spec.np3_565(
            [
                [f"2026-09-26T08:3{i}:00", "2026-09-26", f"1{i}:00", 18000, 2000, 6000,
                 1500, 14000, 9000, 4000, 1300, 55800, "E", True, False]
                for i in (0, 1)
            ]
        ),
    )
    he10 = [s.value for s in ercot.signals.series("NP3-565-CD", "LZ_HOUSTON", H14, H15)]
    he11 = [
        s.value
        for s in ercot.signals.series("NP3-565-CD", "LZ_HOUSTON", H15, "2026-09-26T16:00:00+00:00")
    ]
    assert he10 == [18000] and he11 == [18000]


# R1-11: DST hour endings never collide.
def test_s76_r1_11_fall_back_repeated_hour_is_distinct() -> None:
    assert ercot._hour("2026-11-01", 1) == "2026-11-01T05:00:00+00:00"
    assert ercot._hour("2026-11-01", 2) == "2026-11-01T06:00:00+00:00"
    assert ercot._hour("2026-11-01", 2, dst=True) == "2026-11-01T07:00:00+00:00"
    assert ercot._hour("2026-11-01", 3) == "2026-11-01T08:00:00+00:00"


def test_s76_r1_11_spring_forward_skipped_hour_is_distinct() -> None:
    assert ercot._hour("2026-03-08", 1) == "2026-03-08T06:00:00+00:00"
    assert ercot._hour("2026-03-08", 3) == "2026-03-08T07:00:00+00:00"
    assert ercot._hour("2026-03-08", 4) == "2026-03-08T08:00:00+00:00"


def test_s76_r1_11_dst_flag_flows_through_report_parse() -> None:
    ercot.parse_report(
        "NP4-190-CD",
        s76_spec.np4_190(
            [
                ["2026-11-01", "02:00", "LZ_A", 1.0, False],
                ["2026-11-01", "02:00", "LZ_B", 2.0, True],
            ]
        ),
    )
    first = ercot.signals.latest("NP4-190-CD", "LZ_A").interval_start
    second = ercot.signals.latest("NP4-190-CD", "LZ_B").interval_start
    assert (first, second) == ("2026-11-01T06:00:00+00:00", "2026-11-01T07:00:00+00:00")


# R1-12: repeatedHourFlag resolves the ambiguous SCED hour.
def test_s76_r1_12_sced_repeated_hour_flag_sets_fold() -> None:
    ercot.parse_report(
        "NP6-86-CD",
        s76_spec.np6_86(
            [
                s76_spec.sced_row("2026-11-01T01:05:13", "C_FIRST", 1.0, repeated=False),
                s76_spec.sced_row("2026-11-01T01:05:13", "C_SECOND", 2.0, repeated=True),
            ]
        ),
    )
    assert ercot.signals.latest("NP6-86-CD", "C_FIRST").interval_start == "2026-11-01T06:05:13+00:00"
    assert ercot.signals.latest("NP6-86-CD", "C_SECOND").interval_start == "2026-11-01T07:05:13+00:00"


# R1-04: stale means the measurement is old, not the fetch.
def test_s76_r1_04_old_interval_fetched_now_is_stale_with_data_age() -> None:
    ercot.parse_report(
        "NP6-905-CD", s76_spec.np6_905([["2026-06-28", 1, 1, "LZ_HOUSTON", "LZ", 21.0, False]])
    )
    (row,) = [r for r in ercot.signal_api() if r["zone"] == "LZ_HOUSTON"]
    assert row["stale"] is True
    assert row["age_s"] > 3600
    assert ercot.signals.staleness("NP6-905-CD") > 3600


def test_s76_r1_04_current_interval_fetched_now_is_fresh() -> None:
    ercot.parse_report(
        "NP6-905-CD", s76_spec.np6_905([["2026-09-26", 10, 1, "LZ_HOUSTON", "LZ", 50.1, False]])
    )
    (row,) = [r for r in ercot.signal_api() if r["zone"] == "LZ_HOUSTON"]
    assert row["stale"] is False
    assert row["age_s"] < 60


# R1-07: re-polling one interval upserts instead of duplicating rows.
def test_s76_r1_07_repeated_poll_of_same_interval_stores_one_row() -> None:
    payload = s76_spec.np6_905([["2026-09-26", 10, 1, "LZ_HOUSTON", "LZ", 50.1, False]])
    for _ in range(4):
        ercot.parse_report("NP6-905-CD", payload)
    stored = rows("NP6-905-CD", "LZ_HOUSTON")
    assert len(stored) == 1
    assert sum(s.interval_minutes for s in stored) == 15
