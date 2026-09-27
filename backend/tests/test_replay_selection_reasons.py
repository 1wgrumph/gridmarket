"""DEC-GM-152, review 3: replay selection reasons match the captured prices.

Each new day's manifest selection_reason must state the HB_HOUSTON figures
the shape tests pin (daily min, daily max, evening max), with arithmetic
that balances, and the committed meta.json / PROVENANCE.md must carry that
same reason. 2026-08-26 is pinned unchanged.
"""

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DAYS = ["2026-07-20", "2026-08-17", "2026-08-23", "2026-08-24", "2026-08-31"]


def figures(day: str) -> tuple[float, float, float]:
    rows = json.loads(
        (ROOT / f"backend/gridmarket_server/data/replay/{day}/rt_prices.json").read_text()
    )["observations"]
    houston = [r["value"] for r in rows if r["point"] == "HB_HOUSTON"]
    evening = max(
        r["value"]
        for r in rows
        if r["point"] == "HB_HOUSTON" and 17 <= datetime.fromisoformat(r["central_label"]).hour < 21
    )
    return min(houston), max(houston), evening


def test_selection_reasons_state_tested_figures() -> None:
    for day in DAYS:
        reasons = {
            json.loads((ROOT / f"scripts/replay_data/sources_{day}.json").read_text())[
                "selection_reason"
            ],
            json.loads(
                (ROOT / f"backend/tests/fixtures/replay_raw/{day}/sources.json").read_text()
            )["selection_reason"],
        }
        assert len(reasons) == 1, f"{day}: manifest copies disagree"
        (reason,) = reasons
        low, high, evening = figures(day)
        spread = evening - low
        assert f"{evening:.2f} - {low:.2f} = {spread:.2f}" in reason, f"{day}: {reason}"
        assert f"{high:.2f}" in reason, f"{day}: peak missing from {reason}"
        meta = json.loads(
            (ROOT / f"backend/gridmarket_server/data/replay/{day}/meta.json").read_text()
        )
        assert meta["selection_reason"] == reason, f"{day}: meta.json reason differs"
        provenance = (
            ROOT / f"backend/gridmarket_server/data/replay/{day}/PROVENANCE.md"
        ).read_text()
        assert reason in provenance, f"{day}: PROVENANCE.md reason differs"
