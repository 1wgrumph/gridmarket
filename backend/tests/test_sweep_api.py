"""S79: sweep regressions through real TCP, the shipped SDK and seeded products.

Reproductions: dashboard two-argument buy; five 50-credit orders at 499 cents;
admin guesses/malformed headers; 60-request bursts; 60KB replay key; bot label;
and five IPv6 hosts in one /64. No external feed fixtures are used.
"""

import importlib.util
import json
import socket
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import uvicorn

from gridmarket_server import api, main

ROOT = Path(__file__).resolve().parents[2]
ADMIN = "s79-local-test-admin"


@pytest.fixture
def live(tmp_path, monkeypatch):
    monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "sweep.db"))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    monkeypatch.setenv("GRIDMARKET_ADMIN_KEY", ADMIN)
    monkeypatch.delenv("GRIDMARKET_WORKER_URL", raising=False)
    monkeypatch.syspath_prepend(str(ROOT / "sdk/python"))
    app = main.create_app()
    calls = []

    @app.middleware("http")
    async def record(request, call_next):
        body = await request.body()
        response = await call_next(request)
        calls.append((request.method, request.url.path, body, response.status_code))
        return response

    listener = socket.socket()
    listener.bind(("0.0.0.0", 0))
    listener.listen()
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", proxy_headers=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as http:
            yield http, calls, port
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        assert not thread.is_alive()


def client_for(http):
    from gridmarket import Client

    response = http.post("/v1/sandbox/keys", json={"label": "judge"})
    assert response.status_code == 200
    return Client(str(http.base_url), response.json()["api_key"])


def strategy_module():
    spec = importlib.util.spec_from_file_location(
        "sweep_strategy", ROOT / "examples/strategy-template/strategy.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r3_03_judge_snippet(live):
    http, calls, _ = live
    client = client_for(http)
    order = client.buy("FLEX-LZ_HOUSTON-18", 2)
    sent = [
        json.loads(body)
        for method, path, body, _ in calls
        if method == "POST" and path == "/v1/orders"
    ]
    assert sent[-1]["product_id"] == "FLEX-LZ_HOUSTON-18"
    assert sent[-1]["quantity"] == 2
    assert order["id"] in {row["id"] for row in client.orders()}


@pytest.mark.parametrize("status", [422, 429])
def test_r3_09_strategy_rejections(live, monkeypatch, capsys, status):
    http, calls, _ = live
    client = client_for(http)
    strategy = strategy_module()
    flex = [p for p in client.market() if p["symbol"].startswith("FLEX-")][:6]
    # Same stimulus as the sweep: real product identities, HIGH triggers only.
    # Errors and orders are produced by the real backend, never stubbed.
    predictions = [
        {
            "zone": p["zone"],
            "delivery_hour": p["delivery_hour"],
            "level": "HIGH",
            "expected_value": 6.0,
            "market_price": 4.99,
        }
        for p in flex
    ]
    monkeypatch.setattr(client, "predictions", lambda: predictions)
    if status == 429:
        clock = SimpleNamespace(monotonic=lambda: 100.0)
        monkeypatch.setattr(api, "time", clock)
        # Leave two keyed tokens: positions consumes one, first order consumes one.
        for _ in range(8):
            client.account()
    strategy.cycle(client)
    output = capsys.readouterr().out
    assert f": {status} " in output
    attempted = [row for row in calls if row[0:2] == ("POST", "/v1/orders")]
    if status == 422:
        assert [row[3] for row in attempted] == [200] * 4 + [422] * 2
    else:
        # Boundary rejections do not reach the observation middleware.
        assert len(attempted) == 1
    # The next cycle runs after refill; rejection never terminates the strategy.
    if status == 429:
        monkeypatch.setattr(api, "time", SimpleNamespace(monotonic=lambda: 160.0))
    strategy.cycle(client)
    assert "rejected" in capsys.readouterr().out


def test_r3_13_validation_names_field(live):
    http, _, _ = live
    response = http.post(
        "/v1/admin/bots", json={"count": 11}, headers={"Authorization": f"Bearer {ADMIN}"}
    )
    assert response.status_code == 422
    message = response.json()["error"]["message"]
    assert "count" in message and "10" in message
    client = client_for(http)
    response = http.post(
        "/v1/orders",
        json={"product_id": "x", "side": "buy", "quantity": "bad", "price_cents": 20},
        headers={"Authorization": f"Bearer {client.api_key}", "Idempotency-Key": "invalid"},
    )
    assert response.status_code == 422
    assert "quantity" in response.json()["error"]["message"]


@pytest.mark.parametrize("tunnel", [True, False])
def test_r5_07_admin_peer_before_key(live, tunnel):
    http, _, _ = live
    headers = {"CF-Connecting-IP": "203.0.113.5"} if tunnel else {}
    # Reach only our loopback listener using a real non-loopback source peer.
    transport = httpx.HTTPTransport(
        local_address=None if tunnel else socket.gethostbyname(socket.gethostname())
    )
    with httpx.Client(base_url=str(http.base_url), transport=transport, trust_env=False) as remote:
        responses = [
            remote.post(
                "/v1/admin/bots",
                json={"count": 1},
                headers={**headers, "Authorization": f"Bearer {key}"},
            )
            for key in ("wrong", ADMIN)
        ]
    assert [r.status_code for r in responses] == [403, 403]
    assert responses[0].content == responses[1].content


def test_r5_08_non_ascii_admin_header(live):
    http, _, _ = live
    response = http.post("/v1/admin/halt", headers={b"Authorization": b"Bearer \xff"}, json={})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/v1/orders"),
        ("POST", "/v1/admin/bots"),
        ("GET", "/openapi.json"),
        ("POST", "/v1/sandbox/keys"),
    ],
)
def test_r5_07_09_unauthenticated_bucket(live, monkeypatch, method, path):
    http, _, _ = live
    monkeypatch.setattr(api, "time", SimpleNamespace(monotonic=lambda: 100.0))
    responses = [
        http.request(method, path, headers={"Authorization": "Bearer wrong"}, json={"label": "!"})
        for _ in range(60)
    ]
    limited = [r for r in responses if r.status_code == 429]
    assert limited, [r.status_code for r in responses]
    assert limited[-1].json()["error"]["code"] == "RATE_LIMITED"
    assert int(limited[-1].headers["Retry-After"]) >= 1
    monkeypatch.setattr(api, "time", SimpleNamespace(monotonic=lambda: 160.0))
    assert http.get("/openapi.json").status_code == 200


@pytest.mark.parametrize("length", [129, 60000])
def test_r5_10_idempotency_size(live, length):
    http, _, _ = live
    client = client_for(http)
    product = client.market()[0]
    order = {"product_id": product["id"], "side": "buy", "quantity": 1, "price_cents": 20}
    response = http.post(
        "/v1/orders",
        json=order,
        headers={"Authorization": f"Bearer {client.api_key}", "Idempotency-Key": "x" * length},
    )
    assert response.status_code == 422
    assert "Idempotency-Key" in response.json()["error"]["message"]
    assert client.orders() == []
    assert client.place_order(order, "x" * 128)["id"]


@pytest.mark.parametrize("label", ["market maker 0", "MARKET_MAKER_0", "bot-60"])
def test_r5_11_sandbox_names_are_distinct(live, label):
    from gridmarket import Client

    http, _, _ = live
    issued = http.post("/v1/sandbox/keys", json={"label": label}).json()
    client = Client(str(http.base_url), issued["api_key"])
    assert client.account()["display_name"] == f"sandbox:{label}"
    product = client.market()[0]
    order = client.buy(product["id"], 1, 20)
    feed = http.get("/v1/market/activity").json()
    assert next(row for row in feed if row["id"] == order["id"])["label"] == f"sandbox:{label}"


def test_r5_12_ipv6_sandbox_cap(live):
    http, _, _ = live
    responses = [
        http.post(
            "/v1/sandbox/keys",
            json={"label": "judge"},
            headers={"CF-Connecting-IP": f"2001:db8::{i}"},
        )
        for i in range(1, 6)
    ]
    assert [r.status_code for r in responses] == [200, 200, 200, 429, 429]
    assert (
        http.post(
            "/v1/sandbox/keys", json={}, headers={"CF-Connecting-IP": "2001:db8:0:1::1"}
        ).status_code
        == 200
    )
