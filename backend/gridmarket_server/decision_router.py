from collections.abc import Callable

from fastapi import APIRouter

from .contracts import CheckResult

router = APIRouter()
registry: dict[str, Callable[[], list[CheckResult]]] = {}


def register(family: str, fn: Callable[[], list[CheckResult]]) -> None:
    registry[family] = fn


def evaluate() -> list[CheckResult]:
    return []


def tick() -> None:
    pass
