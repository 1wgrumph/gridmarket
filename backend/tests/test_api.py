"""S02 API boundaries: authentication, replay, limits, onboarding and CORS."""

import hashlib
import re
import sqlite3
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from gridmarket_server import adversary, main, market

SCHEMA = Path(__file__).resolve().parents[1] / "gridmarket_server/schema.sql"
ORIGIN = "https://gridmarket-worker.example"
ORDER = {"product_id": "future", "side": "buy", "quantity": 1, "price_cents": 20}


def api_key(account: str) -> str:
    return "gm_" + hashlib.sha256(account.encode()).hexdigest()[:32]


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "api.db"
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA.read_text())
        for account, sandbox in (("member", False), ("sandbox", True)):
            db.execute("INSERT INTO accounts(id,display_name) VALUES (?,?)", (account, account))
            db.execute(
                "INSERT INTO api_keys(id,account_id,key_hash,label) VALUES (?,?,?,?)",
                (account, account, hashlib.sha256(api_key(account).encode()).hexdigest(), account),
            )
            if sandbox:
                db.execute(
                    "INSERT INTO sandbox_issuance(id,address_hash,account_id) VALUES (?,?,?)",
                    ("initial", "seed", account),
                )
        db.execute(
            "INSERT INTO products(id,symbol,zone,delivery_hour) "
            "VALUES ('future','FLEX-LZ_HOUSTON-test','LZ_HOUSTON','2099-01-01T18:00:00+00:00')"
        )
        db.execute("INSERT INTO providers VALUES ('base_sim','Base Simulation',1)")
        db.execute(
            "INSERT INTO assets VALUES ('member_asset','member','base_sim','LZ_HOUSTON',13.5,13.5,2.7,5,5)"
        )
        db.commit()
    monkeypatch.setenv("GRIDMARKET_DB", str(path))
    monkeypatch.setenv("GRIDMARKET_CORS_ORIGIN", ORIGIN)
    monkeypatch.setenv("GRIDMARKET_ADMIN_KEY", "gm_s02_admin_local")
    monkeypatch.setenv("GRIDMARKET_BOT_MASTER_SEED", "s02-api")
    monkeypatch.setenv("GRIDMARKET_BOT_SECRET", "s02-local-test-secret")
    with TestClient(main.create_app()) as client:
        yield path, client


def headers(account: str, key: str | None = None) -> dict[str, str]:
    result = {"Authorization": f"Bearer {api_key(account)}"}
    if key:
        result["Idempotency-Key"] = key
    return result


def snapshot(path: Path) -> dict[str, int]:
    with sqlite3.connect(path) as db:
        tables = (
            "accounts",
            "api_keys",
            "orders",
            "trades",
            "reservations",
            "idempotency",
            "sandbox_issuance",
            "events",
        )
        return {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables
        }


def error(response, status: int, code: str) -> None:
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["message"]


def test_dir_p1a_11_market_status_exposes_anomalies(api):
    _, client = api
    response = client.get("/v1/market/status")
    assert response.status_code == 200
    assert response.json()["anomalies"] == []


@pytest.mark.parametrize(
    "body,auth,status,code,account",
    [
        (ORDER, {}, 401, "UNAUTHENTICATED", None),
        (ORDER, headers("member"), 400, "IDEMPOTENCY_KEY_REQUIRED", "member"),
        ({**ORDER, "quantity": "bad"}, headers("member", "bad"), 422, "VALIDATION_ERROR", "member"),
        ({**ORDER, "quantity": 0}, headers("member", "zero"), 422, "VALIDATION_ERROR", "member"),
        ({**ORDER, "quantity": 51}, headers("member", "large"), 422, "ORDER_TOO_LARGE", "member"),
        (
            {**ORDER, "price_cents": 100001},
            headers("member", "cash"),
            422,
            "INSUFFICIENT_FUNDS",
            "member",
        ),
        (
            {**ORDER, "product_id": "missing"},
            headers("member", "missing"),
            422,
            "UNKNOWN_PRODUCT",
            "member",
        ),
    ],
)
def test_dir_p1a_11_order_rejections_are_observed_once(
    api, monkeypatch, body, auth, status, code, account
):
    path, client = api
    observe = Mock(wraps=adversary.observe)
    monkeypatch.setattr(adversary, "observe", observe)
    before = snapshot(path)
    error(client.post("/v1/orders", headers=auth, json=body), status, code)
    observe.assert_called_once_with(
        {"entry_type": "rejection", "account_id": account, "code": code}
    )
    assert snapshot(path) == before


def test_dir_p1a_11_direct_order_checks_halt_and_observes_rejection(api, monkeypatch):
    _, _client = api
    observe = Mock(wraps=adversary.observe)
    halted = Mock(wraps=adversary.halted)
    monkeypatch.setattr(adversary, "observe", observe)
    monkeypatch.setattr(adversary, "halted", halted)
    with market.connection(write=True) as db:
        market.place_order(db, "member", ORDER)
        with pytest.raises(market.HTTPException) as failure:
            market.place_order(db, "member", {**ORDER, "quantity": 51})
        assert failure.value.detail["code"] == "ORDER_TOO_LARGE"
        assert halted.call_count == 2
        halted.assert_called_with(db, "member")
    observe.assert_called_once_with(
        {"entry_type": "rejection", "account_id": "member", "code": "ORDER_TOO_LARGE"}
    )


def test_seit_gm_api_01_bearer_auth_and_hash_only_storage(api):
    path, client = api
    assert client.get("/v1/account", headers=headers("member")).status_code == 200
    before = snapshot(path)
    for auth in ({}, {"Authorization": "gm_member"}, {"Authorization": "Bearer wrong"}):
        error(client.get("/v1/account", headers=auth), 401, "UNAUTHENTICATED")
        error(client.post("/v1/orders", headers=auth, json=ORDER), 401, "UNAUTHENTICATED")
    assert snapshot(path) == before
    with sqlite3.connect(path) as db:
        hashes = [row[0] for row in db.execute("SELECT key_hash FROM api_keys")]
    assert hashes and all(re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes)
    assert hashlib.sha256(api_key("member").encode()).hexdigest() in hashes


def test_seit_gm_api_02_idempotency_replays_once_and_rejects_conflict(api):
    path, client = api
    error(
        client.post("/v1/orders", headers=headers("member"), json=ORDER),
        400,
        "IDEMPOTENCY_KEY_REQUIRED",
    )
    assert snapshot(path)["orders"] == 0
    first = client.post("/v1/orders", headers=headers("member", "same"), json=ORDER)
    assert first.status_code in (200, 201)
    replay = client.post("/v1/orders", headers=headers("member", "same"), json=ORDER)
    assert replay.status_code == first.status_code
    assert replay.json() == first.json()
    error(
        client.post("/v1/orders", headers=headers("member", "same"), json={**ORDER, "quantity": 2}),
        409,
        "IDEMPOTENCY_CONFLICT",
    )
    assert snapshot(path)["orders"] == 1


def test_seit_gm_api_04_caller_scoping_and_provider_surface(api):
    _, client = api
    providers = client.get("/v1/providers")
    assert providers.status_code == 200
    assert any(provider["id"] == "base_sim" for provider in providers.json())
    created = client.post("/v1/orders", headers=headers("member", "scoped"), json=ORDER)
    assert created.status_code in (200, 201)
    order_id = created.json()["id"]
    assert any(
        item["id"] == order_id
        for item in client.get("/v1/orders", headers=headers("member")).json()
    )
    assert all(
        item["id"] != order_id
        for item in client.get("/v1/orders", headers=headers("sandbox")).json()
    )
    assert client.get(f"/v1/orders/{order_id}", headers=headers("sandbox")).status_code == 404
    assert client.delete(f"/v1/orders/{order_id}", headers=headers("sandbox")).status_code == 404
    assert client.get("/v1/assets/member_asset", headers=headers("sandbox")).status_code == 404


@pytest.mark.parametrize("account,burst", [("member", 40), ("sandbox", 10)])
def test_seit_gm_api_03_keyed_rate_limits_have_no_extra_order(api, account: str, burst: int):
    path, client = api
    for _ in range(burst + 100):
        response = client.get("/v1/account", headers=headers(account))
        if response.status_code == 429:
            break
        assert response.status_code == 200
    else:
        assert False, "keyed rate limit did not reject a burst"
    before = snapshot(path)
    response = client.post("/v1/orders", headers=headers(account, "limited"), json=ORDER)
    error(response, 429, "RATE_LIMITED")
    assert response.headers["Retry-After"]
    assert snapshot(path) == before


def test_seit_gm_api_03_public_rate_limit_is_per_address(api):
    _, client = api
    for _ in range(100):
        response = client.get("/v1/market/status", headers={"CF-Connecting-IP": "198.51.100.10"})
        if response.status_code == 429:
            break
        assert response.status_code == 200
    else:
        assert False, "public rate limit did not reject a burst"
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert (
        client.get("/v1/market/status", headers={"CF-Connecting-IP": "198.51.100.11"}).status_code
        == 200
    )


def test_seit_gm_api_05_worker_origin_only_on_public_reads(api):
    _, client = api
    public = (
        "/v1/market",
        "/v1/market/FLEX-LZ_HOUSTON-test",
        "/v1/market/history",
        "/v1/market/activity",
        "/v1/predictions",
        "/v1/predictions/LZ_HOUSTON",
        "/v1/router",
    )
    for path in public:
        assert (
            client.get(path, headers={"Origin": ORIGIN}).headers.get("Access-Control-Allow-Origin")
            == ORIGIN
        )
        assert (
            "Access-Control-Allow-Origin"
            not in client.get(path, headers={"Origin": "https://other.example"}).headers
        )
    for method, path in (
        ("GET", "/v1/account"),
        ("GET", "/v1/orders"),
        ("POST", "/v1/orders"),
        ("POST", "/v1/sandbox/keys"),
        ("POST", "/v1/admin/bots"),
    ):
        response = client.request(method, path, headers={"Origin": ORIGIN})
        assert "Access-Control-Allow-Origin" not in response.headers, path


def test_seit_gm_api_06_sandbox_key_once_and_default_label(api):
    path, client = api
    response = client.post(
        "/v1/sandbox/keys", headers={"CF-Connecting-IP": "198.51.100.20"}, json={}
    )
    assert response.status_code in (200, 201)
    issued = response.json()
    assert re.fullmatch(r"gm_[A-Za-z0-9_-]{32}", issued["api_key"])
    assert issued["account_id"]
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT cash_cents,flex_credits FROM accounts WHERE id=?", (issued["account_id"],)
        ).fetchone() == (100000, 0)
        assert (
            db.execute(
                "SELECT key_hash FROM api_keys WHERE account_id=?", (issued["account_id"],)
            ).fetchone()[0]
            == hashlib.sha256(issued["api_key"].encode()).hexdigest()
        )
    account = client.get("/v1/account", headers={"Authorization": f"Bearer {issued['api_key']}"})
    assert account.status_code == 200 and issued["api_key"] not in account.text


def test_seit_gm_api_06_address_and_total_caps_and_label_pattern(api):
    path, client = api
    address = {"CF-Connecting-IP": "198.51.100.21"}
    for label in ("Judge 1", "A_B", "bot-3"):
        assert client.post(
            "/v1/sandbox/keys", headers=address, json={"label": label}
        ).status_code in (200, 201)
    before = snapshot(path)
    error(
        client.post("/v1/sandbox/keys", headers=address, json={"label": "fourth"}),
        429,
        "RATE_LIMITED",
    )
    assert snapshot(path) == before
    for label in ("", "x" * 25, "bad!", "line\nbreak"):
        error(
            client.post(
                "/v1/sandbox/keys",
                headers={"CF-Connecting-IP": "198.51.100.22"},
                json={"label": label},
            ),
            422,
            "VALIDATION_ERROR",
        )
    assert snapshot(path) == before
    with sqlite3.connect(path) as db:
        current = db.execute("SELECT COUNT(*) FROM sandbox_issuance").fetchone()[0]
        for index in range(300 - current):
            account = f"cap-{index}"
            db.execute("INSERT INTO accounts(id,display_name) VALUES (?,?)", (account, account))
            db.execute(
                "INSERT INTO sandbox_issuance(id,address_hash,account_id) VALUES (?,?,?)",
                (account, account, account),
            )
        db.commit()
    before = snapshot(path)
    error(
        client.post(
            "/v1/sandbox/keys",
            headers={"CF-Connecting-IP": "198.51.100.23"},
            json={"label": "after cap"},
        ),
        503,
        "SANDBOX_CAP",
    )
    assert snapshot(path) == before


@pytest.mark.parametrize(
    "path",
    (
        "/v1/admin/bots",
        "/v1/admin/providers/base_sim/outage",
        "/v1/admin/halt",
    ),
)
def test_seit_gm_api_07_admin_guard_rejects_wrong_key_and_tunnel(api, path: str):
    db_path, client = api
    before = snapshot(db_path)
    error(
        client.post(path, headers={"Authorization": "Bearer wrong"}, json={}),
        401,
        "UNAUTHENTICATED",
    )
    error(
        client.post(
            path,
            headers={
                "Authorization": "Bearer gm_s02_admin_local",
                "CF-Connecting-IP": "198.51.100.24",
            },
            json={},
        ),
        403,
        "FORBIDDEN",
    )
    assert snapshot(db_path) == before
    local = client.post(path, headers={"Authorization": "Bearer gm_s02_admin_local"}, json={})
    assert local.status_code not in (401, 403)


def test_seit_gm_api_04_05_market_surface_in_openapi(api):
    _, client = api
    response = client.get("/openapi.json")
    assert response.status_code == 200
    routes = response.json()["paths"]
    for path, method in (
        ("/v1/market", "get"),
        ("/v1/market/{symbol}", "get"),
        ("/v1/market/history", "get"),
        ("/v1/market/activity", "get"),
        ("/v1/providers", "get"),
        ("/v1/sandbox/keys", "post"),
        ("/v1/account", "get"),
        ("/v1/portfolio", "get"),
        ("/v1/positions", "get"),
        ("/v1/trades", "get"),
        ("/v1/assets", "get"),
        ("/v1/assets/{id}", "get"),
        ("/v1/orders", "post"),
        ("/v1/orders", "get"),
        ("/v1/orders/{id}", "get"),
        ("/v1/orders/{id}", "delete"),
    ):
        assert method in routes.get(path, {}), (method, path)
