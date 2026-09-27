"""Save real Worker responses for the ERCOT fixture set (owner step).

The owner runs this against the deployed Worker when ERCOT credentials exist::

    GRIDMARKET_WORKER_URL=https://<worker> GRIDMARKET_WORKER_KEY=<key> \\
        python scripts/capture_ercot.py --out backend/tests/fixtures/ercot/captured/

It replays the poller's own bounded queries (no invented parameters) and writes
one JSON body plus one provenance sidecar per response. The key travels only in
the request header; it is never printed, logged, or written to disk.

`backend/tests/test_s76_captured.py` runs every captured file through the real
parser whenever this directory is non-empty.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from gridmarket_server.ercot import CENTRAL, REPORTS, _report_queries  # noqa: E402

MAX_PAGES = 20
USER_AGENT = "gridmarket-capture/1.0"
PACING_SECONDS = 2.5
MAX_429_RETRIES = 4


def fetch(base: str, target: str, key: str, timeout: int) -> tuple[int, dict]:
    url = base + target
    for attempt in range(MAX_429_RETRIES + 1):
        request = urllib.request.Request(url)
        request.add_header("User-Agent", USER_AGENT)
        if key and not target.startswith("/api/snapshot"):
            request.add_header("x-gridmarket-key", key)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode()[:300]
            except Exception:
                pass
            if exc.code == 429 and attempt < MAX_429_RETRIES:
                wait = PACING_SECONDS
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                if retry_after:
                    try:
                        wait = float(retry_after)
                    except ValueError:
                        pass
                else:
                    m = re.search(r"(\d+(?:\.\d+)?)\s*seconds?", detail, re.IGNORECASE)
                    if m:
                        wait = float(m.group(1))
                    else:
                        m2 = re.search(r"in\s+(\d+)", detail, re.IGNORECASE)
                        if m2:
                            wait = float(m2.group(1))
                wait = max(1.0, min(wait, 30.0))
                print(f"HTTP 429 for {target}: waiting {wait:.1f}s (retry {attempt + 1}/{MAX_429_RETRIES})...")
                time.sleep(wait)
                continue
            print(f"error: {target} -> HTTP {exc.code} {detail}")
            raise SystemExit(1)
    raise SystemExit(1)


def save(out: Path, name: str, target: str, body: dict, key_sent: bool) -> None:
    raw = json.dumps(body, indent=2).encode()
    (out / f"{name}.json").write_bytes(raw)
    note = (
        "Real Worker response. The market key was sent by header and is not recorded."
        if key_sent
        else "Real Worker response. Retrieved without a market key."
    )
    (out / f"{name}.provenance.json").write_text(
        json.dumps(
            {
                "source": target,
                "retrieved_at_utc": datetime.now(UTC).isoformat(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "note": note,
            },
            indent=2,
        )
    )
    print(f"saved {name}.json ({len(raw)} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="Capture directory to fill")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument(
        "--first-page-only",
        action="store_true",
        help="Capture only the first page of each query",
    )
    args = parser.parse_args()
    base = os.environ.get("GRIDMARKET_WORKER_URL", "").rstrip("/")
    key = os.environ.get("GRIDMARKET_WORKER_KEY", "")
    if not base:
        print("error: set GRIDMARKET_WORKER_URL")
        raise SystemExit(2)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    status, body = fetch(base, "/api/snapshot", key, args.timeout)
    save(out, "snapshot", "/api/snapshot", body, key_sent=False)
    time.sleep(PACING_SECONDS)

    now_ct = datetime.now(CENTRAL)
    for report, path in REPORTS.items():
        if report == "ESR" and os.environ.get("GRIDMARKET_ESR", "off") == "off":
            print("skipped ESR (GRIDMARKET_ESR is off)")
            continue
        query_list = _report_queries(report, now_ct) or [None]
        for index, params in enumerate(query_list):
            page = 1
            while True:
                target = (
                    path
                    if params is None
                    else f"{path}?{urllib.parse.urlencode({**params, 'page': page})}"
                )
                _, body = fetch(base, target, key, args.timeout)
                key_sent = bool(key and not target.startswith("/api/snapshot"))
                save(out, f"{report}__q{index}__p{page}", target, body, key_sent)
                total = int((body.get("_meta") or {}).get("totalPages") or 1)
                time.sleep(PACING_SECONDS)
                if args.first_page_only or page >= min(total, MAX_PAGES):
                    if total > MAX_PAGES and not args.first_page_only:
                        print(f"warning: {report} query {index} truncated at {MAX_PAGES} pages")
                    break
                page += 1


if __name__ == "__main__":
    main()
