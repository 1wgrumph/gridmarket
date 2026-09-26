from typing import Any


def tick(tx: Any = None, now: Any = None) -> None:
    pass


def stats(account_id: str) -> dict[str, float | bool]:
    return {
        "losses": 0,
        "loss_share": 0.0,
        "worst_loss": 0.0,
        "pnl": 0.0,
        "net_worth": 0.0,
        "dormant": False,
    }
