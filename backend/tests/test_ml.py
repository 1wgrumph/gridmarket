"""SEIT-GM-ML-01. Imports of ml and ml_data stay inside each test (no S01 stub).

Hour fixture (fixtures/ml/hour.json): delivery_hour is the hour-ending instant.
Index 0 of load_forecast_next_24h and outage_next_168h is that hour. The last
rt_spp_last_hour value is the current RT SPP. Even-count medians average the
two central values. WAC and RAC county is the first 5 digits of the geocode;
zone weight is the sum of (WAC C000 - RAC C000) for counties in county_zone.csv.
A Worker request at time t is refused when 5 earlier requests have timestamps
greater than t - 60. predictions[i] lines up with the i-th input row whose
delivery date falls in the test range, in input order.
"""

import gzip
import json
import math
from datetime import UTC, date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from zoneinfo import ZoneInfo

import pytest

FIX = Path(__file__).resolve().parent / "fixtures" / "ml"
TRAIN = (date(2026, 1, 5), date(2026, 2, 1))
TEST = (date(2026, 2, 2), date(2026, 2, 8))
FEATURES = (
    "hour_of_day",
    "peak_flag",
    "temperature",
    "price_spread",
    "load_pressure",
    "outage_pressure",
    "congestion_pressure",
    "population_weight",
)
ROUTES = (
    "/api/report/np6-905-cd/spp_node_zone_hub",
    "/api/report/np4-190-cd/dam_stlmnt_pnt_prices",
    "/api/report/np3-565-cd/lf_by_model_weather_zone",
    "/api/report/np3-233-cd/hourly_res_outage_cap",
    "/api/report/np6-86-cd/shdw_prices_bnd_trns_const",
)


def _ml():
    from gridmarket_server import ml

    return ml


def _ml_data():
    from gridmarket_server import ml_data

    return ml_data


def _rows() -> list[dict]:
    return json.loads((FIX / "rows.json").read_text())


def _dates() -> list[date]:
    start = date(2026, 1, 5)
    return [start + timedelta(days=i) for i in range(35)]


def _county_zone() -> dict[str, str]:
    mapping = {}
    for line in (FIX / "county_zone.csv").read_text().splitlines()[1:]:
        if line.strip():
            county, zone = line.split(",")
            mapping[county] = zone
    return mapping


def _gzip(path: Path, text: str) -> None:
    with gzip.GzipFile(path, "wb", mtime=0) as handle:
        handle.write(text.encode())


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start
        while end + 1 < len(order) and values[order[end + 1]] == values[order[start]]:
            end += 1
        average = (start + end) / 2 + 1
        for index in range(start, end + 1):
            ranks[order[index]] = average
        start = end + 1
    return ranks


def _spearman(left: list[float], right: list[float]) -> float:
    xs = _rank([float(value) for value in left])
    ys = _rank([float(value) for value in right])
    count = len(xs)
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(xs, ys, strict=True))
    den_x = sum((a - mean_x) ** 2 for a in xs) ** 0.5
    den_y = sum((b - mean_y) ** 2 for b in ys) ** 0.5
    return num / (den_x * den_y)


def _reject(case: str) -> None:
    ml = _ml()
    rows = _rows()
    train, test, token = TRAIN, TEST, "overlap"
    if case == "overlap":
        test = (date(2026, 2, 1), date(2026, 2, 7))
    elif case == "short_train":
        train = (date(2026, 1, 5), date(2026, 1, 31))
        test = (date(2026, 2, 1), date(2026, 2, 7))
        token = r"\b28\b"
    elif case == "short_test":
        test = (date(2026, 2, 2), date(2026, 2, 7))
        token = r"\b7\b"
    for fn in (ml.split_by_date, ml.evaluate):
        with pytest.raises(ValueError, match=token):
            fn(rows, train, test)


def test_seit_gm_ml_01_features() -> None:
    ml_data = _ml_data()
    row = ml_data.build_features(FIX)[0]
    assert row["zone"] == "LZ_HOUSTON"
    assert row["hour_of_day"] == 15 and row["hour_of_day"] is not True
    assert row["peak_flag"] == 1 and row["peak_flag"] is not True
    assert row["temperature"] == 90
    assert row["price_spread"] == pytest.approx(20)
    assert row["load_pressure"] == pytest.approx(23)
    assert row["outage_pressure"] == pytest.approx(500)
    assert row["congestion_pressure"] == pytest.approx(23)
    assert row["population_weight"] == 64


def test_seit_gm_ml_01_peak_flag() -> None:
    ml_data = _ml_data()
    chicago = ZoneInfo("America/Chicago")
    cases = (
        (datetime(2026, 1, 6, 7, tzinfo=chicago), 1),
        (datetime(2026, 1, 6, 6, tzinfo=chicago), 0),
        (datetime(2026, 1, 6, 15, tzinfo=chicago), 1),
        (datetime(2026, 1, 6, 22, tzinfo=chicago), 1),
        (datetime(2026, 1, 6, 23, tzinfo=chicago), 0),
        (datetime(2026, 1, 10, 15, tzinfo=chicago), 0),
        (datetime(2026, 1, 1, 15, tzinfo=chicago), 0),
        (datetime(2026, 1, 1, 22, tzinfo=chicago), 0),
        (datetime(2023, 1, 2, 15, tzinfo=chicago), 0),
        (datetime(2023, 1, 3, 15, tzinfo=chicago), 1),
        (datetime(2026, 5, 25, 15, tzinfo=chicago), 0),
        (datetime(2026, 7, 3, 15, tzinfo=chicago), 1),
        (datetime(2026, 7, 4, 15, tzinfo=chicago), 0),
        (datetime(2026, 9, 7, 15, tzinfo=chicago), 0),
        (datetime(2026, 11, 26, 15, tzinfo=chicago), 0),
        (datetime(2026, 12, 25, 15, tzinfo=chicago), 0),
        (datetime(2026, 7, 15, 2, tzinfo=chicago), 0),
        (datetime(2026, 7, 15, 7, tzinfo=UTC), 0),
    )
    for instant, expected in cases:
        flag = ml_data.peak_flag(instant)
        assert flag == expected and flag is not True and flag is not False


def test_seit_gm_ml_01_zone_weight(tmp_path: Path) -> None:
    ml_data = _ml_data()
    weight = ml_data.zone_population_weight(FIX / "wac.csv.gz", FIX / "rac.csv.gz", _county_zone())
    assert {zone: value for zone, value in weight.items() if value != 0} == {
        "LZ_HOUSTON": 64,
        "LZ_NORTH": 20,
        "LZ_SOUTH": -15,
    }
    wac = tmp_path / "wac.csv.gz"
    rac = tmp_path / "rac.csv.gz"
    _gzip(wac, "w_geocode,C000\n480000000000001,3\n")
    _gzip(rac, "h_geocode,C000\n480000000000001,8\n")
    got = ml_data.zone_population_weight(wac, rac, {"48000": "LZ_WEST"})
    assert got.get("LZ_WEST") == -5
    assert not any(value for zone, value in got.items() if zone != "LZ_WEST")


def test_seit_gm_ml_01_split() -> None:
    ml = _ml()
    train_rows, test_rows = ml.split_by_date(_rows(), TRAIN, TEST)
    assert {row["delivery_hour"][:10] for row in train_rows} == {
        day.isoformat() for day in _dates()[:28]
    }
    assert {row["delivery_hour"][:10] for row in test_rows} == {
        day.isoformat() for day in _dates()[28:]
    }
    assert len(train_rows) == 112 and len(test_rows) == 28
    first = next(
        row
        for row in train_rows
        if row["delivery_hour"].startswith("2026-01-05") and row["zone"] == "LZ_HOUSTON"
    )
    assert first["temperature"] == 1 and first["realized_rt"] == 1


def test_seit_gm_ml_01_split_overlap() -> None:
    _reject("overlap")


def test_seit_gm_ml_01_split_short_train() -> None:
    _reject("short_train")


def test_seit_gm_ml_01_split_short_test() -> None:
    _reject("short_test")


def test_seit_gm_ml_01_spearman_importances() -> None:
    ml = _ml()
    rows = _rows()
    result = ml.evaluate(rows, TRAIN, TEST)
    held = [
        row
        for row in rows
        if TEST[0].isoformat() <= row["delivery_hour"][:10] <= TEST[1].isoformat()
    ]
    realized = [row["realized_rt"] for row in held]
    assert len(held) == 28
    assert result["spearman_score"] == pytest.approx(
        _spearman([row["deterministic_score"] for row in held], realized)
    )
    assert result["spearman_score"] == pytest.approx(-1)
    model_rho = _spearman(result["predictions"], realized)
    assert result["spearman_model"] == pytest.approx(model_rho)
    assert model_rho > 0.8
    assert result["spearman_model"] != pytest.approx(result["spearman_score"])
    assert type(result["model"]).__name__ == "HistGradientBoostingRegressor"
    assert result["model"].n_features_in_ == 8
    importances = {name: float(value) for name, value in result["importances"].items()}
    assert set(importances) == set(FEATURES)
    assert all(math.isfinite(value) for value in importances.values())
    others = [value for name, value in importances.items() if name != "temperature"]
    assert importances["temperature"] > max(others)


def test_seit_gm_ml_01_ercot_budget() -> None:
    ml_data = _ml_data()
    payload = json.loads((FIX / "report.json").read_text())
    body = (FIX / "report.json").read_bytes()
    hits: list[tuple[str, str | None]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            hits.append((self.path.split("?", 1)[0], self.headers.get("x-gridmarket-key")))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        with pytest.raises(ValueError):
            ml_data.fetch_report(base, "/api/report/not-allowlisted", key="fixture-key", now=0.0)
        assert hits == []
        for route in ROUTES:
            assert ml_data.fetch_report(base, route, key="fixture-key", now=0.0) == payload
        assert [path for path, _key in hits] == list(ROUTES)
        with pytest.raises(ValueError, match=r"\b5\b"):
            ml_data.fetch_report(base, ROUTES[0], key="fixture-key", now=0.0)
        with pytest.raises(ValueError, match=r"\b5\b"):
            ml_data.fetch_report(base, ROUTES[0], key="fixture-key", now=59.0)
        assert len(hits) == 5
        assert ml_data.fetch_report(base, ROUTES[0], key="fixture-key", now=60.0) == payload
        assert len(hits) == 6
        assert all(key == "fixture-key" for _path, key in hits)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
