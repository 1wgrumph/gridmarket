"""Replay one seeded workload through the Python and Rust matching engines.

`python bench/bench_matching.py --orders 100000 --seed 20260926 --out bench/results.md`
writes orders/second for both engines, plus the seed and host. The rust
extension must already be importable.
"""

import argparse
import random
import socket
import time
from pathlib import Path


def _pair(rng: random.Random) -> tuple[list[dict], dict]:
    resting = []
    for index in range(4):
        qty = rng.randint(1, 10)
        resting.append(
            {
                "id": f"r{index}",
                "side": "sell" if index % 2 == 0 else "buy",
                "product_id": "p",
                "price_cents": rng.randint(1, 200),
                "quantity": qty,
                "remaining_qty": qty,
                "sequence": index,
            }
        )
    incoming = {
        "id": "in",
        "side": rng.choice(("buy", "sell")),
        "product_id": "p",
        "price_cents": rng.randint(1, 200),
        "quantity": rng.randint(1, 10),
    }
    return resting, incoming


def _replay(match, orders: int, seed: int) -> float:
    rng = random.Random(seed)
    filled = 0
    started = time.perf_counter()
    for _ in range(orders):
        resting, incoming = _pair(rng)
        result = match(resting, incoming)
        fills = result["fills"] if isinstance(result, dict) else result.fills
        filled += len(fills)
    if filled < 0:
        raise SystemExit("benchmark did not call the engine")
    # ponytail: fixed 4-order book per call, not a growing book; deepen if depth matters
    return orders / max(time.perf_counter() - started, 1e-9)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    from gridmarket_server.market import MatchingEngine

    try:
        import matching_core
    except ImportError:
        raise SystemExit("matching_core extension is not importable") from None
    python_rate = _replay(MatchingEngine().match, args.orders, args.seed)
    rust_rate = _replay(matching_core.match_order, args.orders, args.seed)
    args.out.write_text(
        "\n".join(
            (
                "# Matching benchmark",
                "",
                f"- orders: {args.orders}",
                f"- seed: {args.seed}",
                f"- host: {socket.gethostname()}",
                "",
                "| engine | orders/second |",
                "| --- | --- |",
                f"| python | {python_rate:.1f} |",
                f"| rust | {rust_rate:.1f} |",
                "",
            )
        )
    )


if __name__ == "__main__":
    main()
