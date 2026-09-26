"""S36: the strategy and prompt kit use the public sandbox contract."""

import ast
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from fastapi.responses import JSONResponse

from gridmarket_server import main, market

ROOT = Path(__file__).resolve().parents[2]
STRATEGY = ROOT / "examples/strategy-template/strategy.py"


def test_seit_gm_kit_01_strategy_cycle(tmp_path, monkeypatch):
    """SEIT-GM-KIT-01: real uvicorn, sandbox key, SDK wire calls, both limits."""
    assert STRATEGY.is_file(), "strategy template is absent"
    tree = ast.parse(STRATEGY.read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    assert imports <= sys.stdlib_module_names | {"gridmarket"}, imports - sys.stdlib_module_names
    assert "gridmarket" in imports, "strategy must import the repository SDK"

    monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "kit.db"))
    monkeypatch.setenv("GRIDMARKET_NWS", "off")
    app = main.create_app()
    scenario = {"prediction": None, "position": 0, "position_shape": None}
    calls = []

    @app.middleware("http")
    async def observe(request, call_next):
        path = request.url.path
        if path in {"/v1/predictions", "/v1/positions", "/v1/orders"}:
            entry = {"path": path, "authorization": request.headers.get("authorization")}
            if path == "/v1/orders" and request.method == "POST":
                entry["order"] = json.loads(await request.body())
            calls.append(entry)
            if path == "/v1/predictions" and scenario["prediction"] is not None:
                return JSONResponse(scenario["prediction"])
            if path == "/v1/positions" and scenario["position"]:
                return JSONResponse(scenario["position_shape"])
        response = await call_next(request)
        if path == "/v1/orders" and request.method == "POST":
            entry["status"] = response.status_code
        return response

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    url = f"http://127.0.0.1:{listener.getsockname()[1]}"
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="on"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert server.started, "test-local uvicorn failed to start"

        with httpx.Client(base_url=url, timeout=5) as http:
            response = http.get("/v1/market")
            response.raise_for_status()
            listing = response.json()
            products = listing if isinstance(listing, list) else listing["products"]
            product = next(p for p in products if p["status"].lower() == "open")
            prediction = {
                "zone": product["zone"],
                "delivery_hour": product["delivery_hour"],
                "score": 95,
                "level": "HIGH",
                "confidence": 1.0,
                "expected_value": 100.0,
                "market_price": 0.01,
                "drivers": [],
                "disclaimer": "Simulation estimate, not guaranteed profit.",
            }
            response = http.get("/v1/predictions")
            response.raise_for_status()
            real_shape = response.json()
            scenario["prediction"] = (
                [prediction]
                if isinstance(real_shape, list)
                else {**real_shape, "predictions": [prediction]}
            )

            for position in (0, 190):
                scenario["position"] = 0
                calls.clear()
                key_response = http.post("/v1/sandbox/keys", json={"label": "kit-test"})
                key_response.raise_for_status()
                key = key_response.json()["api_key"]
                if position:
                    current = http.get("/v1/positions", headers={"Authorization": f"Bearer {key}"})
                    current.raise_for_status()
                    row = {
                        "product_id": product["id"],
                        "quantity": position,
                        "net_quantity": position,
                        "net_position": position,
                    }
                    shape = current.json()
                    scenario["position_shape"] = (
                        [row] if isinstance(shape, list) else {**shape, "positions": [row]}
                    )
                    scenario["position"] = position
                env = {
                    **os.environ,
                    "GRIDMARKET_URL": url,
                    "GRIDMARKET_API_KEY": key,
                    "PYTHONPATH": os.pathsep.join(
                        (str(ROOT / "sdk/python"), str(ROOT / "backend"))
                    ),
                }
                result = subprocess.run(
                    [sys.executable, str(STRATEGY), "--once"],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                assert result.returncode == 0, result.stderr
                assert any(c["path"] == "/v1/predictions" for c in calls), "no prediction read"
                orders = [c for c in calls if c["path"] == "/v1/orders" and "order" in c]
                assert orders, "no order submitted through the public API"
                exposure = position
                for entry in orders:
                    assert entry["authorization"] == f"Bearer {key}"
                    assert entry["status"] in {200, 201}, entry
                    assert entry["order"]["product_id"] == product["id"]
                    quantity = entry["order"]["quantity"]
                    assert isinstance(quantity, int) and 1 <= quantity <= 50
                    exposure += quantity
                    assert exposure <= 200
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        assert not thread.is_alive(), "test-local uvicorn did not stop"


def test_seit_gm_kit_02_prompt_limits_and_sdk():
    """SEIT-GM-KIT-02: stated limits track the engine and SDK examples exist."""
    prompt_path = ROOT / "docs/llm/system-prompt.md"
    snippets_path = ROOT / "docs/llm/sdk-snippets.md"
    assert prompt_path.is_file(), "system prompt is absent"
    assert snippets_path.is_file(), "SDK snippets are absent"
    prompt = prompt_path.read_text()
    snippets = snippets_path.read_text()
    constants = {
        name: value
        for name, value in vars(market).items()
        if name.isupper() and isinstance(value, int) and not isinstance(value, bool)
    }
    order = [
        value
        for name, value in constants.items()
        if "ORDER" in name and ("MAX" in name or "LIMIT" in name)
    ]
    position = [
        value
        for name, value in constants.items()
        if "POSITION" in name and ("MAX" in name or "LIMIT" in name)
    ]
    assert order and set(order) == {50}, f"market.py order limit constants: {order}"
    assert position and set(position) == {200}, f"market.py position limit constants: {position}"
    assert re.search(rf"(?im)^.*\border\b[^\n]*\b{order[0]}\b[^\n]*\bcredits?\b", prompt)
    assert re.search(rf"(?im)^.*\bposition\b[^\n]*\b{position[0]}\b[^\n]*\bcredits?\b", prompt)
    assert re.search(r"(?i)never[^\n]*exceed[^\n]*position[^\n]*limit", prompt)
    assert re.search(r"(?i)simulat", prompt)
    assert "/openapi.json" in prompt
    assert all(code in prompt for code in ("ORDER_TOO_LARGE", "POSITION_LIMIT", "RATE_LIMITED"))
    assert re.search(r"(?i)rate limit", prompt)
    for text in (prompt, snippets):
        assert re.search(r"```python\s+[\s\S]*?from gridmarket import Client[\s\S]*?```", text)
        assert "Client(" in text
