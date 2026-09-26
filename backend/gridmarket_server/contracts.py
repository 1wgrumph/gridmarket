"""Shared names frozen by CONTRACTS.md for implementation lanes."""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class Signal:
    report_id: str
    zone: str
    interval_start: str
    interval_minutes: int
    value: float
    unit: str
    published_at: str
    fetched_at: str


@dataclass
class WorkerStats:
    requests: int = 0
    errors: int = 0
    http_429: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    snapshot_age_s: float | None = None


class ProviderOffline(Exception):
    """A provider cannot supply capacity."""


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    family: Literal["market", "health"]
    subject: str
    horizon_s: int
    probability: float
    band: Literal["log", "review", "alert"]
    baseline: bool
    jev_probability: float | None
    created_at: str
    resolves_at: str
    outcome: bool | None = None


@dataclass(frozen=True)
class BotSpec:
    index: int
    bot_type: str
    blend: dict[str, float]
    traits: dict[str, float]
    info: dict[str, Any]
    household: dict[str, Any]
    employed: bool
    pay: float
    pay_offset_s: int
    start_cash: float
    learning_rate: float
    provider_id: str


@dataclass(frozen=True)
class Prediction:
    zone: str
    delivery_hour: str
    score: float
    level: str
    confidence: float
    expected_value: float
    market_price: float | None
    drivers: list[dict[str, Any]]
    disclaimer: str
    generated_at: str


class ProviderAdapter(Protocol):
    provider_id: str
    display_name: str

    def list_customers(self) -> list[dict[str, Any]]: ...
    def list_assets(self) -> list[dict[str, Any]]: ...
    def available_capacity(self, asset_id: str, hour: str) -> float: ...
    def reserve_capacity(self, tx: Any, asset_id: str, hour: str, kwh: float) -> str: ...
    def release_capacity(self, tx: Any, reservation_id: str) -> None: ...
    def verify_delivery(self, reservation_id: str) -> bool: ...
    def asset_status(self, asset_id: str) -> dict[str, Any]: ...
    def heartbeat(self) -> None: ...
