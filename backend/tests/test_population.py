"""S28 red tests for the stdlib bot sampler (SEIT-GM-BOT-02/04/08, SEIT-GM-ECON-01)."""

import ast
import hashlib
import importlib
import json
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

from gridmarket_server import population
from gridmarket_server.contracts import BotSpec

TRAITS = (
    "risk appetite",
    "patience",
    "reaction delay",
    "loss aversion",
    "herd versus contrarian",
    "daily activity pattern",
    "wealth",
)
UNIT_TRAITS = (
    "risk appetite",
    "patience",
    "loss aversion",
    "herd versus contrarian",
)
COUNTS = {
    "market maker": 4,
    "score follower": 12,
    "DART trader": 8,
    "heat seller": 14,
    "saver": 12,
    "alert reactor": 6,
    "noise trader": 4,
}
SOURCE = Path(population.__file__).read_text()


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float:
    rx, ry = _ranks(xs), _ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    assert dx > 0 and dy > 0
    return num / (dx * dy)


def _record(spec: BotSpec) -> dict:
    return {
        "index": spec.index,
        "bot_type": spec.bot_type,
        "blend": spec.blend,
        "traits": spec.traits,
        "info": spec.info,
        "household": spec.household,
        "employed": spec.employed,
        "pay": spec.pay,
        "pay_offset_s": spec.pay_offset_s,
        "start_cash": spec.start_cash,
        "learning_rate": spec.learning_rate,
        "provider_id": spec.provider_id,
    }


def _canonical_digest(specs: list[BotSpec]) -> str:
    rows = [_record(spec) for spec in sorted(specs, key=lambda spec: spec.index)]
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _correlation_matrix() -> list[list[float]]:
    found: list[list[list[float]]] = []
    for name, value in vars(population).items():
        if name.startswith("_") or not isinstance(value, (list, tuple)) or len(value) != 7:
            continue
        rows: list[list[float]] = []
        ok = True
        for row in value:
            if not isinstance(row, (list, tuple)) or len(row) != 7:
                ok = False
                break
            if not all(
                isinstance(item, (int, float)) and not isinstance(item, bool) for item in row
            ):
                ok = False
                break
            rows.append([float(item) for item in row])
        if ok:
            found.append(rows)
    assert len(found) == 1
    matrix = found[0]
    for i, row in enumerate(matrix):
        assert row[i] == 1
        for j in range(i):
            assert abs(row[j] - matrix[j][i]) < 1e-9
    off = [abs(matrix[i][j]) for i in range(7) for j in range(i)]
    assert max(off) >= 0.2
    return matrix


def _zone_weights() -> dict[str, float]:
    found = []
    for name, value in vars(population).items():
        if name.startswith("_") or not isinstance(value, dict) or not value:
            continue
        if (
            all(isinstance(key, str) and isinstance(item, float) for key, item in value.items())
            and abs(sum(value.values()) - 1.0) < 1e-6
        ):
            found.append(value)
    assert len(found) == 1
    return found[0]


def _assert_stdlib_only() -> None:
    tree = ast.parse(SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules = [node.module]
        else:
            continue
        for module in modules:
            root = module.split(".", 1)[0]
            assert root in sys.stdlib_module_names or root == "gridmarket_server", module


def test_SEIT_GM_BOT_04_sampler_traits_and_household(monkeypatch) -> None:
    """Per-bot Random seeds, copula traits, and household bounds."""
    _assert_stdlib_only()
    assert "NormalDist" in SOURCE
    assert "cholesky" in SOURCE.lower()
    seen: list[object] = []

    class Spy(random.Random):
        def __init__(self, x=None) -> None:
            seen.append(x)
            super().__init__(x)

    monkeypatch.setattr(random, "Random", Spy)
    if "Random" in population.__dict__:
        monkeypatch.setattr(population, "Random", Spy)
    importlib.reload(population)
    try:
        master = "seed-bot-04"
        seen.clear()
        specs = population.sample(master, 0, 60)
        assert seen == [f"{master}:{i}" for i in range(60)]
        seen.clear()
        population.sample(master, 5, 2)
        assert seen == [f"{master}:5", f"{master}:6"]
        weights = _zone_weights()
        for spec in specs:
            assert list(spec.traits) == list(TRAITS) or set(spec.traits) == set(TRAITS)
            for name in UNIT_TRAITS:
                assert 0.0 < spec.traits[name] < 1.0
            for name in TRAITS:
                assert isinstance(spec.traits[name], float)
            batteries = spec.household["batteries"]
            assert len(batteries) in (1, 2)
            assert all(5 <= size <= 40 for size in batteries)
            assert spec.household["zone"] in weights
            assert 0.15 <= spec.household["reserve_pct"] <= 0.50
            schedule = spec.household["schedule"]
            assert len(schedule) == 24
            assert all(weight >= 0 for weight in schedule)
        alone = population.sample(master, 5, 1)[0]
        within = population.sample(master, 0, 6)[5]
        assert alone == within
        assert population.sample("other-master", 0, 1)[0] != population.sample(master, 0, 1)[0]
    finally:
        monkeypatch.undo()
        importlib.reload(population)


def test_SEIT_GM_BOT_02_type_counts_and_lonestar(monkeypatch) -> None:
    """Default 60-bot mix, and >=20 LoneStar customers only while that adapter is on."""
    monkeypatch.delenv("GRIDMARKET_LONESTAR", raising=False)
    off = population.sample("seed-bot-02", 0, 60)
    assert Counter(spec.bot_type for spec in off) == COUNTS
    assert all(spec.provider_id != "lonestar" for spec in off)
    monkeypatch.setenv("GRIDMARKET_LONESTAR", "on")
    on = population.sample("seed-bot-02", 0, 60)
    assert Counter(spec.bot_type for spec in on) == COUNTS
    assert sum(spec.provider_id == "lonestar" for spec in on) >= 20


def test_SEIT_GM_BOT_08_digest_and_sample_stats() -> None:
    """Same master seed, same canonical digest; 2,000-bot tolerances."""
    master = "seed-bot-08"
    left = population.sample(master, 0, 2000)
    right = population.sample(master, 0, 2000)
    other = population.sample("seed-bot-08-other", 0, 2000)
    assert population.digest(left) == population.digest(right)
    assert population.digest(left) == _canonical_digest(left)
    assert population.digest(left) != population.digest(other)
    matrix = _correlation_matrix()
    weights = _zone_weights()
    batteries = [size for spec in left for size in spec.household["batteries"]]
    assert abs(statistics.median(batteries) - 13.5) / 13.5 <= 0.10
    zones = Counter(spec.household["zone"] for spec in left)
    for zone, weight in weights.items():
        assert abs(zones[zone] / len(left) - weight) <= 0.05
    columns = [[spec.traits[name] for spec in left] for name in TRAITS]
    for i in range(7):
        for j in range(i):
            rho = _spearman(columns[i], columns[j])
            assert abs(rho - matrix[i][j]) <= 0.10


def test_SEIT_GM_ECON_01_economy_draws() -> None:
    """Cash, pay, employment, schedule shape, and the two rank correlations."""
    seeded = population.sample("seed-econ-01", 0, 60)
    assert sum(spec.employed for spec in seeded) == 39
    wide = population.sample("seed-econ-01", 0, 2000)
    cash = [spec.start_cash for spec in wide]
    pay = [spec.pay for spec in wide]
    employed = [1.0 if spec.employed else 0.0 for spec in wide]
    appetite = [spec.traits["risk appetite"] for spec in wide]
    assert all(100 <= value <= 10_000 for value in cash)
    assert all(10 <= value <= 150 for value in pay)
    assert all(0 <= spec.pay_offset_s < 1800 for spec in wide)
    assert len({spec.pay_offset_s for spec in wide}) > 1
    assert abs(statistics.median(cash) - 1000) / 1000 <= 0.10
    assert abs(statistics.median(pay) - 40) / 40 <= 0.10
    assert abs(sum(employed) / len(wide) - 0.65) <= 0.03
    assert abs(_spearman(cash, employed) - 0.3) <= 0.10
    assert abs(_spearman(cash, appetite) - 0.2) <= 0.10
    for spec in wide:
        schedule = spec.household["schedule"]
        shoulder = sum(schedule[hour] for hour in (6, 7, 8, 17, 18, 19))
        midday = sum(schedule[hour] for hour in range(9, 17))
        if spec.employed:
            assert shoulder > midday
        else:
            assert midday > shoulder
