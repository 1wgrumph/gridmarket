"""Initialize an empty exchange without replacing persisted account state."""

import json
import os
import sqlite3
from dataclasses import asdict

from . import keys, population
from .providers import enabled


def seed(db: sqlite3.Connection) -> None:
    from .market import list_products

    for name, adapter in enabled().items():
        db.execute(
            "INSERT OR IGNORE INTO providers(id,display_name) VALUES (?,?)",
            (name, adapter.display_name),
        )
        db.execute("INSERT OR IGNORE INTO provider_health(provider_id) VALUES (?)", (name,))
    if db.execute("SELECT 1 FROM accounts LIMIT 1").fetchone():
        return
    master = os.getenv("GRIDMARKET_BOT_MASTER_SEED", "20260926")
    specs = population.sample(master)
    # Without a configured bot secret, seed random keys; never invent a shared secret.
    secret = os.getenv("GRIDMARKET_BOT_SECRET")
    for spec in specs:
        account_id = f"bot_{spec.index}"
        db.execute(
            "INSERT INTO accounts(id,display_name,cash_cents) VALUES (?,?,?)",
            (account_id, f"{spec.bot_type} {spec.index}", round(spec.start_cash * 100)),
        )
        key = keys.bot_key(spec.index, secret) if secret else keys.sandbox_key()
        keys.store(db, account_id, key, account_id)
        db.execute(
            "INSERT INTO bots(id,account_id,bot_index,bot_type,provider_id,profile_json) "
            "VALUES (?,?,?,?,?,?)",
            (
                account_id,
                account_id,
                spec.index,
                spec.bot_type,
                spec.provider_id,
                json.dumps(asdict(spec)),
            ),
        )
        for index, capacity in enumerate(spec.household["batteries"]):
            limit = min(10.0, max(2.0, capacity * 0.37))
            db.execute(
                "INSERT INTO assets VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    f"{account_id}_battery_{index}",
                    account_id,
                    spec.provider_id,
                    spec.household["zone"],
                    capacity,
                    capacity,
                    capacity * spec.household["reserve_pct"],
                    limit,
                    limit,
                ),
            )
    db.execute("INSERT INTO bot_meta VALUES ('master_seed',?)", (master,))
    db.execute("INSERT INTO bot_meta VALUES ('population_digest',?)", (population.digest(specs),))
    list_products(db)
