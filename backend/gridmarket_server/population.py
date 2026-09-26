"""Deterministic, standard-library bot population draws."""

import hashlib
import json
import math
import os
import random
from dataclasses import asdict
from statistics import NormalDist

from .contracts import BotSpec

DEFAULT_COUNTS = {
    "market maker": 4,
    "score follower": 12,
    "DART trader": 8,
    "heat seller": 14,
    "saver": 12,
    "alert reactor": 6,
    "noise trader": 4,
}

TRAITS = (
    "risk appetite",
    "patience",
    "reaction delay",
    "loss aversion",
    "herd versus contrarian",
    "daily activity pattern",
    "wealth",
)

CORRELATION = (
    (1, 0.1, -0.1, -0.25, 0.2, 0.05, 0.2),
    (0.1, 1, 0.25, 0.3, -0.1, 0.1, 0.05),
    (-0.1, 0.25, 1, 0.05, 0, 0.2, 0),
    (-0.25, 0.3, 0.05, 1, -0.1, 0, -0.1),
    (0.2, -0.1, 0, -0.1, 1, 0, 0),
    (0.05, 0.1, 0.2, 0, 0, 1, 0),
    (0.2, 0.05, 0, -0.1, 0, 0, 1),
)

ZONE_WEIGHTS = {
    "LZ_HOUSTON": 0.35,
    "LZ_NORTH": 0.30,
    "LZ_SOUTH": 0.20,
    "LZ_WEST": 0.15,
}

UNIT_TRAITS = frozenset(
    {
        "risk appetite",
        "patience",
        "loss aversion",
        "herd versus contrarian",
    }
)


def _cholesky(matrix: tuple[tuple[float, ...], ...]) -> list[list[float]]:
    lower = [[0.0] * len(matrix) for _ in matrix]
    for i in range(len(matrix)):
        for j in range(i + 1):
            rest = sum(lower[i][k] * lower[j][k] for k in range(j))
            lower[i][j] = (
                math.sqrt(matrix[i][i] - rest) if i == j else (matrix[i][j] - rest) / lower[j][j]
            )
    return lower


_FACTOR = _cholesky(CORRELATION)
_NORMAL = NormalDist()


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def sample(
    master: str, start_index: int = 0, n: int = 60, seed: str | None = None
) -> list[BotSpec]:
    types = [kind for kind, count in DEFAULT_COUNTS.items() for _ in range(count)]
    specs = []
    for index in range(start_index, start_index + n):
        rng = random.Random(f"{master}:{index}" if seed is None else f"{master}:{index}:{seed}")
        independent = [rng.gauss(0, 1) for _ in TRAITS]
        latent = [
            sum(_FACTOR[i][j] * independent[j] for j in range(i + 1)) for i in range(len(TRAITS))
        ]
        uniforms = [_NORMAL.cdf(value) for value in latent]
        traits = {
            name: (
                float(1 / (1 + math.exp(-z)))
                if name in UNIT_TRAITS
                else float(_clamp(u, 1e-9, 1 - 1e-9))
            )
            for name, u, z in zip(TRAITS, uniforms, latent, strict=True)
        }
        employed = latent[6] * 0.42 + rng.normalvariate(0, 0.91) > -0.42
        kind = types[index % len(types)]
        zone = rng.choices(list(ZONE_WEIGHTS), list(ZONE_WEIGHTS.values()))[0]
        batteries = [
            round(_clamp(rng.lognormvariate(math.log(13.5), 0.48), 5, 40), 2)
            for _ in range(1 + (rng.random() < 0.25))
        ]
        schedule = [
            (1.0 + rng.random() * 0.2)
            * (
                (2.0 if hour in (6, 7, 8, 17, 18, 19) else 0.1)
                if employed
                else (1.5 if 9 <= hour <= 16 else 0.1)
            )
            for hour in range(24)
        ]
        specs.append(
            BotSpec(
                index=index,
                bot_type=kind,
                blend={kind: 1.0},
                traits=traits,
                info={"families": [], "delay_s": 0, "ev_bias": 0.0, "noise": 0.0},
                household={
                    "batteries": batteries,
                    "zone": zone,
                    "reserve_pct": round(rng.uniform(0.15, 0.5), 4),
                    "schedule": schedule,
                },
                employed=employed,
                pay=round(_clamp(rng.lognormvariate(math.log(40), 0.5), 10, 150), 2),
                pay_offset_s=rng.randrange(1800),
                start_cash=round(_clamp(1000 * math.exp(0.8 * latent[6]), 100, 10000), 2),
                learning_rate=0.0,
                provider_id=(
                    "lonestar"
                    if os.getenv("GRIDMARKET_LONESTAR") == "on" and index % 3 == 0
                    else "base_sim"
                ),
            )
        )
    return specs


def digest(specs: list[BotSpec]) -> str:
    rows = [asdict(spec) for spec in sorted(specs, key=lambda spec: spec.index)]
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()
