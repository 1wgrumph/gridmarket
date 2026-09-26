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
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from gridmarket_server.ercot import CENTRAL, REPORTS, _report_queries  # noqa: E402

MAX_PAGES = 20


def fetch(base: str, target: str, key: str, timeout: int) -> tuple[int, dict]:
    request = urllib.request.Request(base + target)
    if key and not target.startswith("/api/snapshot"):
        request.add_header("x-gridmarket-key", key)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode()[:300]
        except Exception:
            detail = ""
        print(f"error: {target} -> HTTP {exc.code} {detail}")
        raise SystemExit(1)


def save(out: Path, name: str, target: str, body: dict) -> None:
    raw = json.dumps(body, indent=2).encode()
    (out / f"{name}.json").write_bytes(raw)
    (out / f"{name}.provenance.json").write_text(
        json.dumps(
            {
                "source": target,
                "retrieved_at_utc": datetime.now(UTC).isoformat(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "note": "Real Worker response. The market key was sent by header and is not recorded.",
            },
            indent=2,
        )
    )
    print(f"saved {name}.json ({len(raw)} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="Capture directory to fill")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    base = os.environ.get("GRIDMARKET_WORKER_URL", "").rstrip("/")
    key = os.environ.get("GRIDMARKET_WORKER_KEY", "")
    if not base:
        print("error: set GRIDMARKET_WORKER_URL")
        raise SystemExit(2)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    status, body = fetch(base, "/api/snapshot", key, args.timeout)
    save(out, "snapshot", "/api/snapshot", body)

    now_ct = datetime.now(CENTRAL)
    for report, path in REPORTS.items():
        if report == "ESR" and os.environ.get("GRIDMARKET_ESR", "off") == "off":
            print("skipped ESR (GRIDMARKET_ESR is off)")
            continue
        query_list = _report_queries(report, now_ct) or [None]
        for index, params in enumerate(query_list):
            page = 1
            while True:
                target = path if params is None else f"{path}?{urllib.parse.urlencode({**params, 'page': page})}"
                _, body = fetch(base, target, key, args.timeout)
                save(out, f"{report}__q{index}__p{page}", target, body)
                total = int((body.get("_meta") or {}).get("totalPages") or 1)
                page += 1
                if page > min(total, MAX_PAGES):
                    if total > MAX_PAGES:
                        print(f"warning: {report} query {index} truncated at {MAX_PAGES} pages")
                    break


if __name__ == "__main__":
    main()
