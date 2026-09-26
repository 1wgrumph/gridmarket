"""S02 SDK and example exercise a real loopback uvicorn server."""

import importlib.util
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

from gridmarket_server import main

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "sdk.db"))
    monkeypatch.setenv("GRIDMARKET_BOT_MASTER_SEED", "s02-sdk")
    monkeypatch.setenv("GRIDMARKET_BOT_SECRET", "s02-local-test-secret")
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    config = uvicorn.Config(main.create_app(), host="127.0.0.1", port=0, log_level="error")
    instance = uvicorn.Server(config)
    thread = threading.Thread(target=instance.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not instance.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert instance.started, "loopback uvicorn did not start"
        port = instance.servers[0].sockets[0].getsockname()[1]
        yield f"http://127.0.0.1:{port}"
    finally:
        instance.should_exit = True
        thread.join(timeout=5)


def sdk_class():
    spec = importlib.util.spec_from_file_location(
        "gridmarket_sdk_s02", ROOT / "sdk/python/gridmarket/__init__.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Client


def sandbox(base_url: str) -> str:
    response = httpx.post(f"{base_url}/v1/sandbox/keys", json={"label": "SDK S02"}, timeout=5)
    assert response.status_code in (200, 201)
    return response.json()["api_key"]


def test_seit_gm_api_04_sdk_round_trip_over_real_uvicorn(server: str):
    key = sandbox(server)
    client = sdk_class()(base_url=server, api_key=key)
    products = client.market()
    assert products
    future = next(product for product in products if product["symbol"].startswith("FLEX-"))
    account = client.account()
    assert account["cash_cents"] == 100000
    order = client.place_order(
        {"product_id": future["id"], "side": "buy", "quantity": 1, "price_cents": 20},
        idempotency_key="sdk-s02-order",
    )
    assert order["id"] in {item["id"] for item in client.orders()}
    client.cancel_order(order["id"])
    assert any(
        item["id"] == order["id"] and item["status"] in ("cancelled", "canceled")
        for item in client.orders()
    )


def test_seit_gm_api_04_python_example_is_short_and_visible_in_activity(server: str):
    script = ROOT / "examples/python-trader/trade.py"
    assert script.is_file()
    assert len(script.read_text().splitlines()) <= 30
    key = sandbox(server)
    prior = httpx.get(f"{server}/v1/market/activity", timeout=5)
    assert prior.status_code == 200
    environment = os.environ.copy()
    environment.update(
        {
            "GRIDMARKET_API_KEY": key,
            "GRIDMARKET_URL": server,
            "PYTHONPATH": str(ROOT / "sdk/python"),
        }
    )
    result = subprocess.run(
        [sys.executable, str(script)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        activity = httpx.get(f"{server}/v1/market/activity", timeout=5)
        if activity.status_code == 200 and len(activity.json()) > len(prior.json()):
            break
        time.sleep(0.05)
    assert activity.status_code == 200 and len(activity.json()) > len(prior.json())
    environment["GRIDMARKET_API_KEY"] = "wrong"
    denied = subprocess.run(
        [sys.executable, str(script)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert denied.returncode != 0
    assert (
        "401" in denied.stdout + denied.stderr or "UNAUTHENTICATED" in denied.stdout + denied.stderr
    )
