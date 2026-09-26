import hashlib

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


def sample(
    master: str, start_index: int = 0, n: int = 60, seed: str | None = None
) -> list[BotSpec]:
    types = [kind for kind, count in DEFAULT_COUNTS.items() for _ in range(count)]
    return [
        BotSpec(
            index=i,
            bot_type=types[i % len(types)],
            blend={types[i % len(types)]: 1.0},
            traits={},
            info={"families": [], "delay_s": 0, "ev_bias": 0.0, "noise": 0.0},
            household={
                "batteries": [13.5],
                "zone": "LZ_HOUSTON",
                "reserve_pct": 0.2,
                "schedule": [1.0] * 24,
            },
            employed=False,
            pay=0.0,
            pay_offset_s=0,
            start_cash=1000.0,
            learning_rate=0.0,
            provider_id="base_sim",
        )
        for i in range(start_index, start_index + n)
    ]


def digest(specs: list[BotSpec]) -> str:
    return hashlib.sha256(repr(specs).encode()).hexdigest()
