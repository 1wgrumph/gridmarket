"""SEIT-GM-QUANT-01 red tests for the qlib strategy (AC-GM-QUANT-01, DES-GM-QUANT).

Import ``gridmarket_server.quant_strategy`` and ``qlib`` inside each test, never
at module import, so a missing module fails in the call.

S41 contract, all names already frozen in CONTRACTS.md or DES-GM-QUANT:

- ``main([])`` reads ``GRIDMARKET_URL`` and ``GRIDMARKET_API_KEY``, loads
  predictions, the account, and the market through ``gridmarket.Client``, and
  sends orders only via ``Client.place_order``.
- Product id is ``FLEX-<zone>-<delivery_hour>``. Buy the highest ``score``.
- Risk (AC-GM-MKT-03, AC-GM-MKT-04): quantity is an int from 1 to 50; a buy
  must leave abs(net position) <= 200; ``price_cents * quantity`` must fit in
  ``cash_cents`` for buys and for sells that are not capacity-limited; a sell
  of a product listed in ``available_capacity`` must be <= that ``credits``
  value.
- ``main(["--backtest"])`` reads a JSON list of ``{date, score, realized}``
  rows on stdin and writes only ``{"rank_ic", "n", "start", "end"}`` on
  stdout. ``rank_ic`` is the Spearman rank correlation of ``score`` vs
  ``realized`` (not Pearson). ``n`` is the row count. ``start`` and ``end``
  are the minimum and maximum ``date``.
- Importing the module must not import ``qlib``. ``--backtest`` does.
- ``deploy/Dockerfile`` and ``deploy/compose.yaml`` must not name the quant extra.
"""

import contextlib
import importlib
import io
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STRATEGY_KEY = "gm_" + "a" * 32
DECOY_KEY = "gm_" + "b" * 32
TOP_PRODUCT = "FLEX-LZ_HOUSTON-18"
SPOT_PRODUCT = "FLEX-LZ_HOUSTON-16"
MAX_ORDER = 50
MAX_POSITION = 200
OPEN_POSITION = 190
CASH_CENTS = 100_000
SPOT_CAPACITY = 4
ROWS = [
    {"date": "2026-09-01", "zone": "LZ_HOUSTON", "delivery_hour": "18", "score": 1, "realized": 1},
    {"date": "2026-09-02", "zone": "LZ_NORTH", "delivery_hour": "18", "score": 2, "realized": 100},
    {"date": "2026-09-03", "zone": "LZ_SOUTH", "delivery_hour": "18", "score": 3, "realized": 2},
    {"date": "2026-09-04", "zone": "LZ_WEST", "delivery_hour": "18", "score": 4, "realized": 3},
    {"date": "2026-09-05", "zone": "LZ_HOUSTON", "delivery_hour": "19", "score": 10, "realized": 4},
]
IMAGE_EXTRA = re.compile(r"--extra\s+quant|\bpyqlib\b|\[quant\]")


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    for rank, index in enumerate(order, start=1):
        ranks[index] = float(rank)
    return ranks


def _pearson(left: list[float], right: list[float]) -> float:
    count = len(left)
    mean_left = sum(left) / count
    mean_right = sum(right) / count
    numerator = sum((x - mean_left) * (y - mean_right) for x, y in zip(left, right))
    left_scale = sum((x - mean_left) ** 2 for x in left) ** 0.5
    right_scale = sum((y - mean_right) ** 2 for y in right) ** 0.5
    return numerator / (left_scale * right_scale)


def _spearman(left: list[float], right: list[float]) -> float:
    return _pearson(_ranks(left), _ranks(right))


def _skip_without_quant_extra() -> None:
    if importlib.util.find_spec("qlib") is None:
        pytest.skip("QUANT_EXTRA_ABSENT")


def _prediction(zone: str, hour: str, score: float) -> dict[str, object]:
    return {
        "zone": zone,
        "delivery_hour": hour,
        "score": score,
        "level": "high" if score > 0.5 else "low",
        "confidence": 0.8,
        "expected_value": 0.4,
        "market_price": 0.25,
        "drivers": [{"factor": "load", "contribution": 0.1, "detail": "fixture"}],
        "disclaimer": "fixture",
        "generated_at": "2026-09-26T12:00:00Z",
    }


def _product(product_id: str, zone: str, hour: str) -> dict[str, str]:
    return {
        "id": product_id,
        "symbol": product_id,
        "zone": zone,
        "delivery_hour": hour,
        "status": "open",
    }


PREDICTIONS = [
    _prediction("LZ_HOUSTON", "18", 0.91),
    _prediction("LZ_NORTH", "18", 0.22),
    _prediction("LZ_HOUSTON", "16", 0.05),
]
PRODUCTS = [
    _product(TOP_PRODUCT, "LZ_HOUSTON", "18"),
    _product("FLEX-LZ_NORTH-18", "LZ_NORTH", "18"),
    _product(SPOT_PRODUCT, "LZ_HOUSTON", "16"),
]
ACCOUNT = {
    "cash_cents": CASH_CENTS,
    "positions": [{"product_id": TOP_PRODUCT, "quantity": OPEN_POSITION}],
    "available_capacity": [{"product_id": SPOT_PRODUCT, "credits": SPOT_CAPACITY}],
}


def _handler(state: dict[str, list]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def _json(self, code: int, payload: object) -> None:
            raw = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _record(self, body: dict[str, object] | None) -> None:
            state["requests"].append(
                {
                    "method": self.command,
                    "path": self.path.split("?", 1)[0],
                    "authorization": self.headers.get("Authorization"),
                    "idempotency_key": self.headers.get("Idempotency-Key"),
                    "body": body,
                }
            )

        def do_GET(self) -> None:
            self._record(None)
            path = self.path.split("?", 1)[0]
            if path == "/v1/predictions":
                self._json(200, PREDICTIONS)
            elif path == "/v1/market":
                self._json(200, PRODUCTS)
            elif path == "/v1/account":
                self._json(200, ACCOUNT)
            else:
                self._json(404, {"error": {"code": "NOT_FOUND", "message": path}})

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            self._record(body)
            path = self.path.split("?", 1)[0]
            if path != "/v1/orders":
                self._json(404, {"error": {"code": "NOT_FOUND", "message": path}})
                return
            self._json(
                200,
                {
                    "id": f"ord-{len(state['requests'])}",
                    "account_id": "quant-sandbox",
                    "product_id": body.get("product_id"),
                    "side": body.get("side"),
                    "quantity": body.get("quantity"),
                    "remaining_qty": body.get("quantity"),
                    "price_cents": body.get("price_cents"),
                    "status": "open",
                    "created_at": "2026-09-26T12:00:00Z",
                },
            )

    return Handler


@pytest.fixture
def market_server():
    state: dict[str, list] = {"requests": [], "sdk": []}
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}", state
    finally:
        server.shutdown()
        server.server_close()


def _assert_risk(orders: list[dict[str, object]]) -> None:
    net = {TOP_PRODUCT: OPEN_POSITION}
    spent = 0
    capacity = {SPOT_PRODUCT: SPOT_CAPACITY}
    bought_top = 0
    for order in orders:
        product_id = order["product_id"]
        side = order["side"]
        quantity = order["quantity"]
        price_cents = order["price_cents"]
        assert side in ("buy", "sell")
        assert type(quantity) is int and 1 <= quantity <= MAX_ORDER
        assert type(price_cents) is int and price_cents >= 1
        position = net.get(product_id, 0)
        if product_id in capacity and side == "sell":
            assert quantity <= capacity[product_id]
            capacity[product_id] -= quantity
        else:
            spent += price_cents * quantity
            assert spent <= CASH_CENTS
            position += quantity if side == "buy" else -quantity
            assert abs(position) <= MAX_POSITION
            net[product_id] = position
        if product_id == TOP_PRODUCT and side == "buy":
            bought_top += quantity
    assert 1 <= bought_top <= MAX_POSITION - OPEN_POSITION


def test_SEIT_GM_QUANT_01_trades_through_sdk_own_key_under_risk_limits(
    market_server, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SEIT-GM-QUANT-01: SDK place_order only, strategy key, risk limits held."""
    _skip_without_quant_extra()
    url, state = market_server
    sys.path.insert(0, str(ROOT / "sdk" / "python"))
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.setenv("GRIDMARKET_URL", url)
    monkeypatch.setenv("GRIDMARKET_API_KEY", STRATEGY_KEY)
    monkeypatch.setenv("GRIDMARKET_ADMIN_KEY", DECOY_KEY)
    from gridmarket import Client

    from gridmarket_server import quant_strategy

    original = Client.place_order

    def wrapped(self: Client, order: dict, idempotency_key: str):
        state["sdk"].append(
            {
                "api_key": self.api_key,
                "base_url": self.base_url,
                "order": order,
                "key": idempotency_key,
            }
        )
        return original(self, order, idempotency_key)

    monkeypatch.setattr(Client, "place_order", wrapped)
    quant_strategy.main([])

    posts = [row for row in state["requests"] if row["method"] == "POST"]
    assert any(row["path"] == "/v1/predictions" for row in state["requests"])
    assert posts and len(posts) == len(state["sdk"])
    for row, call in zip(posts, state["sdk"]):
        assert row["authorization"] == f"Bearer {STRATEGY_KEY}"
        assert DECOY_KEY not in (row["authorization"] or "")
        assert call["api_key"] == STRATEGY_KEY
        assert call["base_url"] == url
        assert row["idempotency_key"] and row["idempotency_key"] == call["key"]
        assert row["path"] == "/v1/orders"
        assert row["body"] == call["order"]
    assert {row["authorization"] for row in state["requests"]} == {f"Bearer {STRATEGY_KEY}"}
    _assert_risk([row["body"] for row in posts])


def test_SEIT_GM_QUANT_01_backtest_reports_spearman_rank_ic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SEIT-GM-QUANT-01: --backtest reports Spearman rank IC, n, and date range."""
    _skip_without_quant_extra()
    scores = [float(row["score"]) for row in ROWS]
    realized = [float(row["realized"]) for row in ROWS]
    spearman = _spearman(scores, realized)
    pearson = _pearson(scores, realized)
    assert spearman == pytest.approx(0.4)
    assert abs(pearson - spearman) > 1e-6
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(ROWS)))
    from gridmarket_server import quant_strategy

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        quant_strategy.main(["--backtest"])
    report = json.loads(stdout.getvalue())
    assert report["n"] == len(ROWS)
    assert report["start"] == ROWS[0]["date"]
    assert report["end"] == ROWS[-1]["date"]
    assert report["rank_ic"] == pytest.approx(spearman)
    assert abs(report["rank_ic"] - pearson) > 1e-6
    assert "qlib" in sys.modules


def test_SEIT_GM_QUANT_01_qlib_imported_only_with_quant_extra() -> None:
    """SEIT-GM-QUANT-01: qlib stays unloaded at import unless the quant extra is installed."""
    _skip_without_quant_extra()
    from importlib.metadata import version

    pyproject = (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    dependencies = pyproject.split("[project.optional-dependencies]", 1)[0]
    assert "pyqlib" not in dependencies
    assert "pyqlib==0.9.7" in pyproject
    assert version("pyqlib") == "0.9.7"
    for name in list(sys.modules):
        if name == "qlib" or name.startswith("qlib.") or name == "gridmarket_server.quant_strategy":
            del sys.modules[name]
    import gridmarket_server.quant_strategy as strategy

    assert "qlib" not in sys.modules
    assert "qlib" in Path(strategy.__file__).read_text(encoding="utf-8")


def test_SEIT_GM_QUANT_01_runtime_image_omits_quant_extra() -> None:
    """SEIT-GM-QUANT-01: runtime image files never reference the quant extra."""
    import gridmarket_server.quant_strategy as strategy

    assert strategy.__name__ == "gridmarket_server.quant_strategy"
    for rel in ("deploy/Dockerfile", "deploy/compose.yaml"):
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        assert IMAGE_EXTRA.search(text) is None, rel
