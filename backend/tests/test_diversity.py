"""S30: diversity layers 2, 3, 5a, and the public diversity read."""

import json
import math
import random
import sqlite3
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import stdev

from fastapi.testclient import TestClient

from gridmarket_server import bots, main, population
from gridmarket_server.contracts import Signal

FAMILIES = {
    "price-spread",
    "load-pressure",
    "outage-pressure",
    "congestion-pressure",
    "heat-stress",
    "peak-period",
    "weather-alert",
    "DART",
}
SCHEMA = Path(main.__file__).with_name("schema.sql")


def test_seit_gm_bot_05_dirichlet_blends(monkeypatch) -> None:
    draws = []
    gammavariate = random.Random.gammavariate

    def record_draw(generator, alpha, beta):
        draws.append((alpha, beta))
        return gammavariate(generator, alpha, beta)

    monkeypatch.setattr(random.Random, "gammavariate", record_draw)
    specs = population.sample("diversity", n=2000)
    assert len(specs) == 2000
    for bot in specs:
        assert len(bot.blend) == 3
        assert bot.bot_type in bot.blend
        assert set(bot.blend) <= population.DEFAULT_COUNTS.keys()
        assert all(0 < weight < 1 for weight in bot.blend.values())
        assert math.isclose(sum(bot.blend.values()), 1, abs_tol=1e-12)
    assert abs(sum(bot.blend[bot.bot_type] for bot in specs) / len(specs) - 2 / 3) <= 0.03
    assert draws.count((6, 1)) >= len(specs)
    assert draws.count((1.5, 1)) >= 2 * len(specs)


def test_seit_gm_bot_05_signal_visibility_delay_bias_and_noise() -> None:
    specs = population.sample("diversity")
    subsets = [set(bot.info["families"]) for bot in specs]
    assert all(families <= FAMILIES for families in subsets)
    assert len({frozenset(families) for families in subsets}) >= 2
    for bot in specs:
        assert 0 <= bot.info["delay_s"] <= 900
        assert -0.10 <= bot.info["ev_bias"] <= 0.10
        assert 0.02 <= bot.info["noise"] <= 0.10

    observe = getattr(bots, "observe_signals", None)
    bot = next(bot for bot in specs if bot.info["families"] and bot.info["delay_s"] > 0)
    now = datetime(2026, 9, 26, 12, tzinfo=UTC)
    old = now - timedelta(hours=1)
    signals = [
        Signal(
            family,
            "LZ_HOUSTON",
            old.isoformat(),
            5,
            100.0,
            "index",
            old.isoformat(),
            old.isoformat(),
        )
        for family in FAMILIES
    ]
    family = next(iter(bot.info["families"]))
    recent = now - timedelta(seconds=bot.info["delay_s"] - 1)
    signals.append(
        Signal(
            family,
            "LZ_HOUSTON",
            recent.isoformat(),
            5,
            200.0,
            "index",
            recent.isoformat(),
            recent.isoformat(),
        )
    )
    observed = observe(bot, signals, now)
    assert set(observed) == set(bot.info["families"])
    biased = 100 * (1 + bot.info["ev_bias"])
    assert all(abs(value - biased) <= biased * bot.info["noise"] for value in observed.values())


def test_seit_gm_bot_06_bounded_learning_replays_from_ledger(tmp_path: Path) -> None:
    bot = population.sample("diversity", n=1)[0]
    assert 0.01 <= bot.learning_rate <= 0.05
    replay = getattr(bots, "thresholds_from_ledger", None)
    db_path = tmp_path / "bots.db"
    with sqlite3.connect(db_path) as db:
        db.executescript(SCHEMA.read_text())
        db.execute("INSERT INTO accounts(id, display_name) VALUES ('account', 'bot')")
        db.execute(
            "INSERT INTO bots(id, account_id, bot_index, bot_type, provider_id, profile_json) "
            "VALUES ('bot', 'account', ?, ?, ?, ?)",
            (bot.index, bot.bot_type, bot.provider_id, json.dumps(asdict(bot))),
        )
        db.execute(
            "INSERT INTO products(id, symbol, zone, delivery_hour) "
            "VALUES ('product', 'P', 'LZ_HOUSTON', '2026-09-26T12:00:00Z')"
        )
        db.execute(
            "INSERT INTO settlements(id, product_id, price_cents) VALUES ('s', 'product', 100)"
        )
        initial = replay(db, "diversity", bot.index)
        assert initial
        for name, state in initial.items():
            assert state["min"] <= state["value"] <= state["max"], name
            assert state["max"] > state["min"], name
        previous = initial
        moved = False
        for position_id, pnl in (("p1", 100), ("p2", -100)):
            db.execute(
                "INSERT INTO settled_positions(id, settlement_id, account_id, product_id, "
                "quantity, pnl_cents) VALUES (?, 's', 'account', 'product', 1, ?)",
                (position_id, pnl),
            )
            current = replay(db, "diversity", bot.index)
            assert current.keys() == previous.keys()
            for name, state in current.items():
                assert state["min"] <= state["value"] <= state["max"], name
                assert (state["min"], state["max"]) == (
                    previous[name]["min"],
                    previous[name]["max"],
                )
                assert abs(state["value"] - previous[name]["value"]) <= (
                    bot.learning_rate * (state["max"] - state["min"]) + 1e-12
                ), name
            moved |= current != previous
            previous = current
        assert moved
        db.commit()
    with sqlite3.connect(db_path) as restarted:
        assert replay(restarted, "diversity", bot.index) == previous


def test_seit_gm_ui_07_api_diversity_for_seeded_population(tmp_path: Path, monkeypatch) -> None:
    specs = population.sample("diversity")
    db_path = tmp_path / "bots.db"
    with sqlite3.connect(db_path) as db:
        db.executescript(SCHEMA.read_text())
        for bot in specs:
            bot_id = f"bot-{bot.index}"
            db.execute("INSERT INTO accounts(id, display_name) VALUES (?, ?)", (bot_id, bot_id))
            db.execute(
                "INSERT INTO bots(id, account_id, bot_index, bot_type, provider_id, profile_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (bot_id, bot_id, bot.index, bot.bot_type, bot.provider_id, json.dumps(asdict(bot))),
            )
        db.commit()
    monkeypatch.setenv("GRIDMARKET_DB", str(db_path))
    response = TestClient(main.create_app()).get("/v1/bots/diversity")
    assert response.status_code == 200
    result = response.json()
    expected_coverage = (
        sum(stdev(bot.traits[name] for bot in specs) >= 0.05 for name in specs[0].traits) / 7
    )
    counts = Counter(bot.bot_type for bot in specs)
    expected_entropy = -sum(
        (count / len(specs)) * math.log2(count / len(specs)) for count in counts.values()
    )
    assert 0 <= result["coverage"] <= 1
    assert result["coverage"] == expected_coverage
    assert abs(result["entropy"] - expected_entropy) <= 0.01
    assert len(result["points"]) == len(specs)
    assert sorted(
        (point["risk_appetite"], point["patience"]) for point in result["points"]
    ) == sorted((bot.traits["risk_appetite"], bot.traits["patience"]) for bot in specs)
