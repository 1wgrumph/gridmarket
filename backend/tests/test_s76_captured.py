"""S76: every owner-captured ERCOT response parses through the real code.

Skips when backend/tests/fixtures/ercot/captured/ is empty (capture with
scripts/capture_ercot.py once ERCOT credentials exist). Bodies must be
accompanied by a provenance sidecar whose sha256 matches.
"""

import hashlib
import json
from pathlib import Path

import pytest

from gridmarket_server import ercot

CAPTURED = Path(__file__).parent / "fixtures/ercot/captured"


def test_s76_captured_responses_parse(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GRIDMARKET_DB", str(tmp_path / "signals.db"))
    bodies = sorted(CAPTURED.glob("*.json")) if CAPTURED.is_dir() else []
    bodies = [path for path in bodies if not path.name.endswith(".provenance.json")]
    if not bodies:
        pytest.skip("no captured ERCOT responses; run scripts/capture_ercot.py (owner step)")
    for path in bodies:
        raw = path.read_bytes()
        sidecar = path.with_name(path.stem + ".provenance.json")
        assert sidecar.exists(), f"{path.name} is missing its provenance sidecar"
        provenance = json.loads(sidecar.read_text())
        assert provenance["sha256"] == hashlib.sha256(raw).hexdigest(), path.name
        assert "GRIDMARKET_WORKER_KEY" not in sidecar.read_text(), path.name
        body = json.loads(raw)
        if path.stem == "snapshot":
            ercot.parse_snapshot(body)
        else:
            report = path.stem.split("__")[0]
            assert report in ercot.REPORTS, path.name
            ercot.parse_report(report, body)
