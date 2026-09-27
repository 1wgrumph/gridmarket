"""UX-12: exchange counts use persisted positions and distinct participants."""

import os
import sqlite3
from pathlib import Path

from test_s63_exchange import api  # noqa: F401


def test_exchange_counts_include_asset_owners_and_do_not_double_count(api):  # noqa: F811
    summary = api.get("/v1/market/status").json()
    assert summary["open_interest"] == 1
    assert summary["active_traders"] == 2
    providers = api.get("/v1/providers").json()
    assert next(p for p in providers if p["id"] == "base_sim")["participants"] == 2

    with sqlite3.connect(Path(os.environ["GRIDMARKET_DB"])) as db:
        db.execute("UPDATE products SET status='settled'")
        db.execute("UPDATE bots SET dormant=1")
    empty = api.get("/v1/market/status").json()
    assert empty["open_interest"] == 0
    assert empty["active_traders"] == 0
