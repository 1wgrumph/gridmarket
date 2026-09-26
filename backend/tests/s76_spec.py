"""Spec-shaped ERCOT payload builders for S76 red/green tests.

Provenance (rule 7): column names come from the filter parameters of ERCOT's
published Public API spec (ercot/api-specs pubapi-apim-api.json, commit
e361e39, 2024-02-21, sha256 108db99a...6b4f; From/To suffixes stripped).
Values are synthetic. Field objects ({name, label, dataType}) match the spec's
Field schema and gridstatus practice (columns = [f["name"] for f in fields]).
"""

from __future__ import annotations


def _fields(names: list[str]) -> list[dict]:
    return [{"name": name, "label": name, "dataType": "VARCHAR"} for name in names]


def report(names: list[str], rows: list[list], total_pages: int = 1) -> dict:
    return {
        "_meta": {
            "totalRecords": len(rows),
            "pageSize": len(rows),
            "totalPages": total_pages,
            "currentPage": 1,
        },
        "report": {},
        "fields": _fields(names),
        "data": rows,
    }


# NP6-905-CD: deliveryDate, deliveryHour, deliveryInterval, settlementPoint,
# settlementPointType, settlementPointPrice, DSTFlag. No publish-time column.
NP6_905_COLS = [
    "deliveryDate",
    "deliveryHour",
    "deliveryInterval",
    "settlementPoint",
    "settlementPointType",
    "settlementPointPrice",
    "DSTFlag",
]


def np6_905(rows: list[list], total_pages: int = 1) -> dict:
    return report(NP6_905_COLS, rows, total_pages)


# NP4-190-CD: deliveryDate, hourEnding (string), settlementPoint,
# settlementPointPrice, DSTFlag. No publish-time column.
NP4_190_COLS = ["deliveryDate", "hourEnding", "settlementPoint", "settlementPointPrice", "DSTFlag"]


def np4_190(rows: list[list], total_pages: int = 1) -> dict:
    return report(NP4_190_COLS, rows, total_pages)


# NP3-565-CD: one wide row per model and hour; eight weather-zone columns.
NP3_565_COLS = [
    "postedDatetime",
    "deliveryDate",
    "hourEnding",
    "coast",
    "east",
    "farWest",
    "north",
    "northCentral",
    "southCentral",
    "southern",
    "west",
    "systemTotal",
    "model",
    "inUseFlag",
    "DSTFlag",
]


def np3_565(rows: list[list], total_pages: int = 1) -> dict:
    return report(NP3_565_COLS, rows, total_pages)


# NP3-233-CD: operatingDate (not deliveryDate), hourEnding int, wide zone columns.
NP3_233_COLS = [
    "postedDatetime",
    "operatingDate",
    "hourEnding",
    "totalResourceMWZoneSouth",
    "totalResourceMWZoneNorth",
    "totalResourceMWZoneWest",
    "totalResourceMWZoneHouston",
]


def np3_233(rows: list[list], total_pages: int = 1) -> dict:
    return report(NP3_233_COLS, rows, total_pages)


# NP6-86-CD: SCEDTimestamp in Central prevailing time, no offset.
NP6_86_COLS = [
    "SCEDTimestamp",
    "repeatedHourFlag",
    "constraintID",
    "constraintName",
    "contingencyName",
    "shadowPrice",
    "maxShadowPrice",
    "limit",
    "value",
    "violatedMW",
    "fromStation",
    "toStation",
    "fromStationkV",
    "toStationkV",
    "CCTStatus",
]


def np6_86(rows: list[list], total_pages: int = 1) -> dict:
    return report(NP6_86_COLS, rows, total_pages)


def sced_row(stamp: str, name: str, price: float, repeated: bool = False) -> list:
    return [stamp, repeated, 1, name, "BASE CASE", price, 5251.0, 900, 900, 0, "A", "B", 345, 345, "COMP"]


# The Worker's real /api/snapshot body shape (ercot-hackathon/src/snapshot.js):
# demand.mw, hubs[{hub, price}], dam{hub, price}, sced.systemLambda, errors{}.
SNAPSHOT = {
    "asOf": "2026-09-26T14:00:00Z",
    "ct": {"date": "2026-09-26", "hour": 9, "minute": 0},
    "heNow": 10,
    "errors": {},
    "demand": {"mw": 70234, "timeEnding": "10:00", "todayPeak": 70234, "series": [70234]},
    "hubs": [
        {"hub": "HB_NORTH", "price": 51.25, "hour": 10, "interval": 1, "series": [51.25]},
        {"hub": "HB_HOUSTON", "price": 48.5, "hour": 10, "interval": 1, "series": [48.5]},
        {"hub": "HB_SOUTH", "price": None},
        {"hub": "HB_WEST", "price": None},
    ],
    "dam": {"hub": "HB_NORTH", "hourEnding": 10, "price": 60.75, "dart": -9.5, "dayPeak": 61},
    "sced": {"timestamp": "2026-09-26T09:55:00", "systemLambda": 36.5},
    "checks": [],
}

SNAPSHOT_ALL_FAILED = {
    "asOf": "2026-09-26T14:00:00Z",
    "ct": {"date": "2026-09-26", "hour": 9, "minute": 0},
    "heNow": 10,
    "errors": {"demand": "x", "spp": "x", "dam": "x", "adders": "x", "wind": "x", "solar": "x", "weather": "x"},
    "checks": [],
}
