"""Admin kill-switch routes (stretch): halt and resume by scope."""

import hmac
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()

LOOPBACK = frozenset({"127.0.0.1", "::1", "testclient"})


def _reject(code: str, status: int) -> None:
    raise HTTPException(status, {"code": code, "message": code.replace("_", " ").capitalize()})


def _guard(request: Request) -> None:
    configured = os.getenv("GRIDMARKET_ADMIN_KEY", "")
    if not configured or not hmac.compare_digest(
        request.headers.get("Authorization", ""), "Bearer " + configured
    ):
        _reject("UNAUTHENTICATED", 401)
    if "CF-Connecting-IP" in request.headers:
        _reject("FORBIDDEN", 403)
    if request.client and request.client.host not in LOOPBACK:
        _reject("FORBIDDEN", 403)


@contextmanager
def _connection(write: bool = False):
    db = sqlite3.connect(os.getenv("GRIDMARKET_DB", "/data/gridmarket.db"), timeout=30)
    db.execute("PRAGMA foreign_keys=ON")
    try:
        if write:
            db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def _scope_account(scope: str) -> str | None:
    if scope == "market":
        return None
    if scope.startswith("account:") and len(scope) > len("account:"):
        return scope[len("account:") :]
    _reject("VALIDATION_ERROR", 422)
    raise AssertionError("unreachable")


def _event(db, kind: str, account_id: str | None, scope: str, reason: str) -> None:
    db.execute(
        "INSERT INTO events(id,entry_type,account_id,subject_id,payload_json) VALUES (?,?,?,?,?)",
        (uuid.uuid4().hex, kind, account_id, scope, json.dumps({"scope": scope, "reason": reason})),
    )


@router.post("/v1/admin/halt")
async def halt(request: Request) -> dict[str, str]:
    _guard(request)
    body = await request.json()
    scope = str(body.get("scope", ""))
    account_id = _scope_account(scope)
    reason = str(body.get("reason", ""))
    with _connection(write=True) as db:
        db.execute(
            "INSERT INTO halts(id,account_id,reason) VALUES (?,?,?)",
            (uuid.uuid4().hex, account_id, reason),
        )
        _event(db, "halt", account_id, scope, reason)
    return {"status": "halted", "scope": scope}


@router.post("/v1/admin/resume")
async def resume(request: Request) -> dict[str, str]:
    _guard(request)
    body = await request.json()
    scope = str(body.get("scope", ""))
    account_id = _scope_account(scope)
    reason = str(body.get("reason", ""))
    with _connection(write=True) as db:
        if account_id is None:
            cursor = db.execute(
                "UPDATE halts SET ended_at=CURRENT_TIMESTAMP"
                " WHERE account_id IS NULL AND ended_at IS NULL"
            )
        else:
            cursor = db.execute(
                "UPDATE halts SET ended_at=CURRENT_TIMESTAMP"
                " WHERE account_id=? AND ended_at IS NULL",
                (account_id,),
            )
        if cursor.rowcount:
            _event(db, "lift", account_id, scope, reason)
    return {"status": "resumed", "scope": scope}
