import json
import os
import time
from collections import deque
from dataclasses import asdict
from threading import Lock
from urllib.request import Request, urlopen

from .contracts import CheckResult

_calls: deque[float] = deque()
_lock = Lock()


def enabled() -> bool:
    return os.getenv("GRIDMARKET_JEV") == "on"


def probability(check: CheckResult) -> float | None:
    if not enabled() or check.band not in ("review", "alert"):
        return None

    url = os.getenv("GRIDMARKET_JEV_URL")
    key = os.getenv("GRIDMARKET_JEV_KEY")
    if not url or not key:
        return None

    with _lock:
        now = time.monotonic()
        while _calls and now - _calls[0] >= 60:
            _calls.popleft()
        if len(_calls) >= 6:
            return None
        _calls.append(now)

    try:
        request = Request(
            url,
            data=json.dumps(asdict(check)).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        with urlopen(request, timeout=10) as response:
            value = json.load(response)["probability"]
        if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1:
            return float(value)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None
