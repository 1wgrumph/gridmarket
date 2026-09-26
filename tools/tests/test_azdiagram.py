"""SEIT-GM-SPEC-01: azdiagram renders SVG and draw.io from one layout and lints it.

Contract exercised here (AC-GM-SPEC-01, DES-GM-SPEC):

- ``azdiagram.render(src, out_dir)`` reads one per-class YAML figure input and
  writes ``<stem>.svg`` and ``<stem>.drawio`` into ``out_dir``. It returns an
  object with ``svg`` and ``drawio`` paths and ``engine`` (``"graphviz"`` for
  F1-F4, F6, F7; ``"grid"`` for F5 and F8).
- Every node box appears in the SVG as ``<g id="<node id>">`` holding a
  ``<rect>``, and in the uncompressed draw.io file as
  ``<mxCell id="<node id>" vertex="1">`` with an ``mxGeometry``; both carry the
  same x, y, width and height.
- ``azdiagram.lint(paths)`` returns a list of finding strings for YAML inputs,
  ``.drawio`` files, or directories; ``python -m azdiagram lint <path>`` exits
  non-zero when there is any finding.

azdiagram has no S01 stub, so it is imported inside each test (CMD-RED-GREEN).
"""

import importlib
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "azdiagram"
GRAPH_CLASSES = ("F1", "F2", "F3", "F4", "F6", "F7")
TOLERANCE = 0.5

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def azdiagram():
    return importlib.import_module("azdiagram")


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def svg_boxes(path: Path) -> dict[str, tuple[float, float, float, float]]:
    boxes = {}
    for group in ET.parse(path).iter():
        if local(group.tag) != "g" or "id" not in group.attrib:
            continue
        rect = next((c for c in group if local(c.tag) == "rect"), None)
        if rect is not None:
            boxes[group.attrib["id"]] = tuple(
                float(rect.attrib[k]) for k in ("x", "y", "width", "height")
            )
    return boxes


def drawio_cells(path: Path) -> list[ET.Element]:
    return [c for c in ET.parse(path).iter() if local(c.tag) == "mxCell"]


def drawio_boxes(path: Path) -> dict[str, tuple[float, float, float, float]]:
    boxes = {}
    for cell in drawio_cells(path):
        if cell.attrib.get("vertex") != "1":
            continue
        geometry = next(c for c in cell if local(c.tag) == "mxGeometry")
        boxes[cell.attrib["id"]] = tuple(
            float(geometry.attrib.get(k, 0)) for k in ("x", "y", "width", "height")
        )
    return boxes


def graph_input(tmp_path: Path, figure_class: str, **limits: int) -> Path:
    text = (
        (FIXTURES / "graph.yaml")
        .read_text()
        .replace("class: F1", f"class: {figure_class}")
    )
    for key, value in limits.items():
        text = text.replace(f"{key}: 2000", f"{key}: {value}")
    src = tmp_path / f"graph-{figure_class.lower()}.yaml"
    src.write_text(text)
    return src


def assert_same_boxes(svg: Path, drawio: Path, ids: list[str]) -> dict:
    in_svg, in_drawio = svg_boxes(svg), drawio_boxes(drawio)
    for node in ids:
        assert node in in_svg, f"{node} missing from SVG"
        assert node in in_drawio, f"{node} missing from draw.io"
        assert in_svg[node] == pytest.approx(in_drawio[node], abs=TOLERANCE), node
    return in_svg


def run_cli(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, **(env or {})}
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(TOOLS), env.get("PYTHONPATH")])
    )
    return subprocess.run(
        [sys.executable, "-m", "azdiagram", *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


@pytest.mark.parametrize("figure_class", GRAPH_CLASSES)
def test_seit_gm_spec_01_graph_class_writes_svg_and_drawio_from_one_graphviz_layout(
    tmp_path: Path, figure_class: str
) -> None:
    mod = azdiagram()
    result = mod.render(graph_input(tmp_path, figure_class), tmp_path / "out")

    assert result.engine == "graphviz"
    assert result.svg == tmp_path / "out" / f"graph-{figure_class.lower()}.svg"
    assert result.drawio == tmp_path / "out" / f"graph-{figure_class.lower()}.drawio"
    boxes = assert_same_boxes(
        result.svg, result.drawio, ["worker", "market", "bots", "dashboard"]
    )
    assert len({(x, y) for x, y, _, _ in boxes.values()}) == 4, "nodes share a position"

    edges = {
        (c.attrib.get("source"), c.attrib.get("target"))
        for c in drawio_cells(result.drawio)
        if c.attrib.get("edge") == "1"
    }
    assert edges >= {("worker", "market"), ("bots", "market"), ("market", "dashboard")}


def test_seit_gm_spec_01_graph_class_needs_graphviz_and_reports_it_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = azdiagram()
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))

    with pytest.raises(RuntimeError, match="(?i)graphviz"):
        mod.render(graph_input(tmp_path, "F1"), tmp_path / "out")


def test_seit_gm_spec_01_sequence_f5_uses_grid_renderer_without_graphviz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = azdiagram()
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))

    result = mod.render(FIXTURES / "sequence.yaml", tmp_path / "out")

    assert result.engine == "grid"
    assert result.svg.name == "sequence.svg" and result.drawio.name == "sequence.drawio"
    boxes = assert_same_boxes(result.svg, result.drawio, ["trader", "api", "market"])
    xs = [boxes[p][0] for p in ("trader", "api", "market")]
    assert xs == sorted(xs) and len(set(xs)) == 3, "participants not left to right"
    assert len({boxes[p][1] for p in boxes if p in ("trader", "api", "market")}) == 1

    messages = [
        c
        for c in drawio_cells(result.drawio)
        if c.attrib.get("edge") == "1" and c.attrib.get("id", "").startswith("msg-")
    ]
    assert [(m.attrib["source"], m.attrib["target"]) for m in messages] == [
        ("trader", "api"),
        ("api", "market"),
        ("market", "trader"),
    ]
    ys = [
        float(p.attrib["y"])
        for m in messages
        for p in m.iter()
        if local(p.tag) == "mxPoint" and p.attrib.get("as") == "sourcePoint"
    ]
    assert len(ys) == 3 and ys == sorted(ys) and len(set(ys)) == 3, (
        "messages not top to bottom"
    )


def test_seit_gm_spec_01_timing_f8_uses_grid_renderer_without_graphviz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = azdiagram()
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))

    result = mod.render(FIXTURES / "timing.yaml", tmp_path / "out")

    assert result.engine == "grid"
    boxes = assert_same_boxes(
        result.svg, result.drawio, ["poller", "market", "dashboard"]
    )
    ys = [boxes[lane][1] for lane in ("poller", "market", "dashboard")]
    assert ys == sorted(ys) and len(set(ys)) == 3, "lanes not top to bottom"


def test_seit_gm_spec_01_lint_passes_rendered_figures_within_limits(
    tmp_path: Path,
) -> None:
    mod = azdiagram()
    inputs = [
        graph_input(tmp_path, "F1"),
        FIXTURES / "sequence.yaml",
        FIXTURES / "timing.yaml",
    ]

    assert mod.lint(inputs) == []
    assert run_cli("lint", *map(str, inputs)).returncode == 0


def test_seit_gm_spec_01_lint_fails_overlapping_boxes(tmp_path: Path) -> None:
    mod = azdiagram()
    overlap = FIXTURES / "overlap.drawio"

    findings = mod.lint([overlap])

    assert len(findings) == 1
    assert "overlap" in findings[0].lower()
    assert "alpha" in findings[0] and "beta" in findings[0]
    cli = run_cli("lint", str(overlap))
    assert cli.returncode != 0
    assert "overlap" in (cli.stdout + cli.stderr).lower()


@pytest.mark.parametrize("limit", ["max_width", "max_height"])
def test_seit_gm_spec_01_lint_fails_figure_over_its_size_limit(
    tmp_path: Path, limit: str
) -> None:
    mod = azdiagram()
    src = graph_input(tmp_path, "F1", **{limit: 40})

    findings = mod.lint([src])

    assert len(findings) == 1
    assert "size" in findings[0].lower()
    assert src.name in findings[0]
    cli = run_cli("lint", str(src))
    assert cli.returncode != 0


def test_seit_gm_spec_01_lint_walks_a_directory(tmp_path: Path) -> None:
    mod = azdiagram()
    figures = tmp_path / "figures"
    figures.mkdir()
    (figures / "sequence.yaml").write_text((FIXTURES / "sequence.yaml").read_text())

    assert mod.lint([figures]) == []
    assert run_cli("lint", str(figures)).returncode == 0

    (figures / "overlap.drawio").write_text((FIXTURES / "overlap.drawio").read_text())
    assert len(mod.lint([figures])) == 1
    assert run_cli("lint", str(figures)).returncode != 0
