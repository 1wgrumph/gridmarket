"""Key generation and hash-only persistence."""

import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
import uuid


def sandbox_key() -> str:
    return "gm_" + secrets.token_urlsafe(24)


def bot_key(index: int, secret: str | None = None) -> str:
    secret = secret if secret is not None else os.environ["GRIDMARKET_BOT_SECRET"]
    digest = hmac.digest(secret.encode(), f"bot:{index}".encode(), "sha256")
    return "gm_" + base64.urlsafe_b64encode(digest).decode()[:32]


def store(db: sqlite3.Connection, account_id: str, key: str, label: str) -> None:
    db.execute(
        "INSERT INTO api_keys(id,account_id,key_hash,label) VALUES (?,?,?,?)",
        (uuid.uuid4().hex, account_id, hashlib.sha256(key.encode()).hexdigest(), label),
    )


def issue(db: sqlite3.Connection, label: str, address: str | None = None) -> dict[str, str]:
    account_id, key = uuid.uuid4().hex, sandbox_key()
    db.execute("INSERT INTO accounts(id,display_name) VALUES (?,?)", (account_id, label))
    store(db, account_id, key, label)
    if address is not None:
        db.execute(
            "INSERT INTO sandbox_issuance(id,address_hash,account_id) VALUES (?,?,?)",
            (uuid.uuid4().hex, hashlib.sha256(address.encode()).hexdigest(), account_id),
        )
    return {"account_id": account_id, "api_key": key, "label": label}


if __name__ == "__main__":
    import argparse

    from .market import connection

    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["issue"])
    parser.add_argument("--sandbox", action="store_true")
    parser.add_argument("--name", default="Sandbox")
    args = parser.parse_args()
    with connection(write=True) as db:
        result = issue(db, args.name, "owner" if args.sandbox else None)
    print(result["api_key"])
