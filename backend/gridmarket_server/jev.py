from .contracts import CheckResult


def enabled() -> bool:
    return False


def probability(check: CheckResult) -> float | None:
    return None
