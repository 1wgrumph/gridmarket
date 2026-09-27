"""C3 API bounds. Public FastAPI surface; synthetic catalog only."""

import importlib.util
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

_PATH = Path(__file__).resolve().parent / "fixtures/replay_test/synthetic.py"
_SPEC = importlib.util.spec_from_file_location("replay_synthetic_api", _PATH)
syn = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(syn)


def zulu(day: str, hour: int, minute: int = 0) -> str:
    year, month, dom = (int(part) for part in day.split("-"))
    return syn.iso(datetime(year, month, dom, hour, minute, tzinfo=syn.CHI))


@contextmanager
def catalog(tmp_path, monkeypatch, **days):
    root = tmp_path / "catalog"
    for day, options in days.items():
        syn.write_day(root, day, **(options or {}))
    with syn.client(root, monkeypatch) as api:
        yield api


def _error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


def test_C3_days_lists_dst_lengths_and_esr_gap(tmp_path, monkeypatch):
    with catalog(
        tmp_path,
        monkeypatch,
        **{
            "2026-03-08": {"include_esr": False},
            "2026-06-15": {},
            "2026-11-01": {},
        },
    ) as api:
        response = api.get("/v1/replay/days")
        assert response.status_code == 200, response.text
        listed = {row["day"]: row for row in response.json()["days"]}
    assert listed["2026-03-08"]["quarters"] == 92
    assert "esr" in listed["2026-03-08"]["gaps"]
    assert listed["2026-06-15"]["quarters"] == 96
    assert listed["2026-06-15"]["synthetic"] is True
    assert listed["2026-06-15"]["claims_external_observation"] is False
    assert "esr" not in listed["2026-06-15"]["gaps"]
    assert listed["2026-11-01"]["quarters"] == 100
    assert [row["day"] for row in response.json()["days"]] == sorted(listed)


def test_C3_unknown_day_is_404_and_a_known_day_runs(tmp_path, monkeypatch):
    day = "2026-06-15"
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        ok = syn.post(api, syn.body(day, ["fixed_schedule"], [syn.asset()]))
        assert ok.status_code == 200, ok.text
        missing = syn.post(api, syn.body("1999-01-01", ["fixed_schedule"], [syn.asset()]))
    _error(missing, 404, "NOT_FOUND")


def test_C3_missing_run_is_404(tmp_path, monkeypatch):
    day = "2026-06-15"
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        made = syn.post(api, syn.body(day, ["fixed_schedule"], [syn.asset()]))
        assert made.status_code == 200, made.text
        missing = api.get("/v1/replay/does-not-exist")
        again = api.get(f"/v1/replay/{made.json()['run_id']}")
    _error(missing, 404, "NOT_FOUND")
    assert again.status_code == 200
    assert again.content == made.content


def test_C3_bounds_422(tmp_path, monkeypatch):
    day = "2026-06-15"
    asset = syn.asset()
    good = syn.body(day, ["fixed_schedule"], [asset])
    windows = []
    for index, (start, end) in enumerate(syn.quarters(day)[:21]):
        windows.append(
            {
                "type": "provider_offline",
                "provider_id": "base_sim",
                "start": syn.iso(start),
                "end": syn.iso(end),
            }
        )
        if index == 20:
            break
    cases = [
        syn.body(day, [], [asset]),
        syn.body(day, ["fixed_schedule", "fixed_schedule"], [asset]),
        syn.body(day, ["no_such_policy"], [asset]),
        syn.body(
            day,
            ["fixed_schedule", "price_based", "esr_informed", "fixed_schedule"],
            [asset],
        ),
        syn.body(day, ["fixed_schedule"], []),
        syn.body(day, ["fixed_schedule"], [asset] * 1001),
        {**good, "disruptions": windows},
        {
            **good,
            "disruptions": [
                {
                    "type": "provider_offline",
                    "provider_id": "missing_provider",
                    "start": zulu(day, 17, 0),
                    "end": zulu(day, 17, 15),
                }
            ],
        },
        {
            **good,
            "disruptions": [
                {
                    "type": "provider_offline",
                    "provider_id": "base_sim",
                    "start": zulu(day, 17, 15),
                    "end": zulu(day, 17, 0),
                }
            ],
        },
        {
            **good,
            "disruptions": [
                {
                    "type": "provider_offline",
                    "provider_id": "base_sim",
                    "start": zulu(day, 17, 1),
                    "end": zulu(day, 17, 16),
                }
            ],
        },
        {
            **good,
            "disruptions": [
                {
                    "type": "feed_interrupt",
                    "source": "not_a_source",
                    "start": zulu(day, 17, 0),
                    "end": zulu(day, 17, 15),
                }
            ],
        },
        {
            **good,
            "disruptions": [
                {
                    "type": "provider_offline",
                    "provider_id": "base_sim",
                    "start": "2026-06-14T00:00:00Z",
                    "end": "2026-06-14T00:15:00Z",
                }
            ],
        },
    ]
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        for payload in cases:
            _error(syn.post(api, payload), 422, "VALIDATION_ERROR")


def test_C3_accepts_three_strategies_and_twenty_disruptions(tmp_path, monkeypatch):
    day = "2026-06-15"
    disruptions = [
        {
            "type": "provider_offline",
            "provider_id": "base_sim",
            "start": syn.iso(start),
            "end": syn.iso(end),
        }
        for start, end in syn.quarters(day)[:20]
    ]
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        three = syn.post(
            api,
            syn.body(
                day,
                ["fixed_schedule", "price_based", "esr_informed"],
                [syn.asset()],
            ),
        )
        twenty = syn.post(
            api,
            syn.body(day, ["fixed_schedule"], [syn.asset()], disruptions=disruptions),
        )
    assert three.status_code == 200, three.text
    assert twenty.status_code == 200, twenty.text


def test_C3_accepts_1000_assets_and_rejects_1001(tmp_path, monkeypatch):
    day = "2026-06-15"
    held = {
        "capacity_kwh": "1",
        "initial_soc_kwh": "1",
        "min_reserve_kwh": "1",
        "max_charge_kw": "1",
        "max_discharge_kw": "1",
        "eta_round_trip": "1",
    }

    def fleet(count):
        return [syn.asset(asset_id=f"synthetic-{index:04d}", **held) for index in range(count)]

    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        _error(
            syn.post(api, syn.body(day, ["fixed_schedule"], fleet(1001))),
            422,
            "VALIDATION_ERROR",
        )
        accepted = syn.post(api, syn.body(day, ["price_based"], fleet(1000)))
    assert accepted.status_code == 200, accepted.text


def test_C3_oversize_is_413(tmp_path, monkeypatch):
    with catalog(tmp_path, monkeypatch, **{"2026-06-15": {}}) as api:
        blob = b'{"pad":"' + (b"x" * (2 * 1024 * 1024)) + b'"}'
        response = api.post(
            "/v1/replay", content=blob, headers={"content-type": "application/json"}
        )
    _error(response, 413, "PAYLOAD_TOO_LARGE")


def test_C3_rate_limit_is_429(tmp_path, monkeypatch):
    day = "2026-06-15"
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        for seed in range(6):
            response = syn.post(api, syn.body(day, ["price_based"], [syn.asset()], seed=seed))
            assert response.status_code == 200, response.text
        limited = syn.post(api, syn.body(day, ["price_based"], [syn.asset()], seed=6))
    _error(limited, 429, "RATE_LIMITED")


def test_C3_evicts_after_20_runs(tmp_path, monkeypatch):
    # Assumption: the replay limiter reads time.monotonic. Advance only its clock so 21
    # posts are not also a 429 and retention shows without sleeping; patching the
    # global time.monotonic also races asyncio's executor-shutdown timeout.
    from types import SimpleNamespace

    from gridmarket_server.replay import routes

    clock = {"now": 0.0}

    def monotonic():
        clock["now"] += 60
        return clock["now"]

    day = "2026-06-15"
    with catalog(tmp_path, monkeypatch, **{day: {}}) as api:
        monkeypatch.setattr(routes, "time", SimpleNamespace(monotonic=monotonic))
        ids = []
        for seed in range(21):
            response = syn.post(api, syn.body(day, ["price_based"], [syn.asset()], seed=seed))
            assert response.status_code == 200, response.text
            ids.append(response.json()["run_id"])
        oldest = api.get(f"/v1/replay/{ids[0]}")
        newest = api.get(f"/v1/replay/{ids[-1]}")
    _error(oldest, 404, "NOT_FOUND")
    assert newest.status_code == 200
