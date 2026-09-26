"""azdiagram: per-class YAML figure input to SVG plus draw.io, and a figure lint.

Figure classes (DEC-SPEC-006): F1 context, F2 decomposition, F3 interface,
F4 deployment, F5 sequence, F6 activity, F7 state machine, F8 timing.
F1-F4, F6 and F7 are laid out by Graphviz (``dot -Tjson``); F5 and F8 use the
pure-Python grid renderer. Both outputs are written from one layout, so every
node box has the same x, y, width and height in the SVG and the draw.io file.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

import yaml

GRAPH_CLASSES = {"F1", "F2", "F3", "F4", "F6", "F7"}
GRID_CLASSES = {"F5", "F8"}
PAD = 20.0
FONT = 12
BOX_W, BOX_H = 120.0, 40.0


@dataclass
class Box:
    id: str
    label: str
    x: float
    y: float
    w: float
    h: float


@dataclass
class Line:
    id: str
    points: list[tuple[float, float]]
    label: str = ""
    source: str | None = None
    target: str | None = None
    arrow: bool = True
    dashed: bool = False
    label_at: tuple[float, float] | None = None


@dataclass
class Layout:
    title: str
    width: float
    height: float
    boxes: list[Box] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)


@dataclass
class Rendered:
    svg: Path
    drawio: Path
    engine: str


def load(src: Path) -> dict:
    spec = yaml.safe_load(Path(src).read_text())
    if not isinstance(spec, dict):
        raise TypeError("figure input is not a YAML mapping")
    cls = spec.get("class")
    if cls not in GRAPH_CLASSES | GRID_CLASSES:
        raise ValueError(f"class {cls!r} is not one of F1-F8")
    for key in ("max_width", "max_height"):
        if not isinstance(spec.get(key), (int, float)):
            raise TypeError(f"{key} is required and must be a number")
    return spec


def _ids(items: list, what: str) -> set[str]:
    ids = [item["id"] for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate {what} id")
    return set(ids)


def _check_refs(links: list, known: set[str]) -> None:
    for link in links:
        for end in (link["from"], link["to"]):
            if end not in known:
                raise ValueError(f"unknown id {end!r}")


def _dot_layout(spec: dict) -> Layout:
    dot = shutil.which("dot")
    if dot is None:
        raise RuntimeError(
            f"Graphviz 'dot' is required for class {spec['class']}; not on PATH"
        )
    nodes, edges = spec.get("nodes") or [], spec.get("edges") or []
    _check_refs(edges, _ids(nodes, "node"))
    q = json.dumps  # a JSON string literal is a valid quoted DOT id for these labels
    lines = [
        "digraph G {",
        f"rankdir={spec.get('direction', 'TB')};",
        f'node [shape=box, fontname="Helvetica", fontsize={FONT}, margin="0.2,0.1"];',
        f'edge [fontname="Helvetica", fontsize={FONT - 2}];',
    ]
    lines += [f"{q(n['id'])} [label={q(n.get('label', n['id']))}];" for n in nodes]
    lines += [
        f"{q(e['from'])} -> {q(e['to'])} [label={q(e.get('label', ''))}];"
        for e in edges
    ]
    lines.append("}")
    graph = json.loads(
        subprocess.run(
            [dot, "-Tjson"],
            input="\n".join(lines),
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    _, _, bb_w, bb_h = (float(v) for v in graph["bb"].split(","))

    def flip(x: float, y: float) -> tuple[float, float]:
        return x + PAD, bb_h - y + PAD

    layout = Layout(spec.get("title", ""), bb_w + 2 * PAD, bb_h + 2 * PAD)
    objects = graph.get("objects", [])
    for obj in objects:
        cx, cy = flip(*(float(v) for v in obj["pos"].split(",")))
        w, h = float(obj["width"]) * 72, float(obj["height"]) * 72
        label = next(n.get("label", n["id"]) for n in nodes if n["id"] == obj["name"])
        layout.boxes.append(Box(obj["name"], label, cx - w / 2, cy - h / 2, w, h))
    for i, edge in enumerate(graph.get("edges", [])):
        tokens = edge["pos"].split()
        end = None
        if tokens[0].startswith("e,"):
            end = tokens.pop(0)[2:]
        if tokens and tokens[0].startswith("s,"):
            tokens.pop(0)
        points = [flip(*(float(v) for v in t.split(","))) for t in tokens]
        if end:
            points.append(flip(*(float(v) for v in end.split(","))))
        layout.lines.append(
            Line(
                f"edge-{i + 1}",
                points,
                edge.get("label", ""),
                objects[edge["tail"]]["name"],
                objects[edge["head"]]["name"],
                label_at=flip(*(float(v) for v in edge["lp"].split(",")))
                if "lp" in edge
                else None,
            )
        )
    return layout


def _sequence_layout(spec: dict) -> Layout:
    parts, msgs = spec.get("participants") or [], spec.get("messages") or []
    _check_refs(msgs, _ids(parts, "participant"))
    gap, step = 80.0, 50.0
    x_of = {}
    layout = Layout(spec.get("title", ""), 0, 0)
    for i, p in enumerate(parts):
        x = PAD + i * (BOX_W + gap)
        x_of[p["id"]] = x + BOX_W / 2
        layout.boxes.append(Box(p["id"], p.get("label", p["id"]), x, PAD, BOX_W, BOX_H))
    bottom = PAD + BOX_H + step * (len(msgs) + 1)
    for p in parts:
        x = x_of[p["id"]]
        layout.lines.append(
            Line(
                f"life-{p['id']}",
                [(x, PAD + BOX_H), (x, bottom)],
                arrow=False,
                dashed=True,
            )
        )
    for i, m in enumerate(msgs):
        y = PAD + BOX_H + step * (i + 1)
        layout.lines.append(
            Line(
                f"msg-{i + 1}",
                [(x_of[m["from"]], y), (x_of[m["to"]], y)],
                m.get("label", ""),
                m["from"],
                m["to"],
            )
        )
    layout.width = PAD * 2 + len(parts) * BOX_W + max(len(parts) - 1, 0) * gap
    layout.height = bottom + PAD
    return layout


def _timing_layout(spec: dict) -> Layout:
    lanes = spec.get("lanes") or []
    _ids(lanes, "lane")
    plot_w, gap = 600.0, 10.0
    times = [s["at"] for lane in lanes for s in lane.get("states") or []]
    span = max(times, default=0) - min(times, default=0)
    start = min(times, default=0)
    end = start + (span * 1.1 if span else 1)
    scale = plot_w / (end - start)
    plot_x = PAD + BOX_W + gap
    layout = Layout(spec.get("title", ""), plot_x + plot_w + PAD, 0)
    for i, lane in enumerate(lanes):
        y = PAD + i * (BOX_H + gap)
        layout.boxes.append(
            Box(lane["id"], lane.get("label", lane["id"]), PAD, y, BOX_W, BOX_H)
        )
        states = sorted(lane.get("states") or [], key=lambda s: s["at"])
        for k, state in enumerate(states):
            until = states[k + 1]["at"] if k + 1 < len(states) else end
            x0, x1 = (
                plot_x + (state["at"] - start) * scale,
                plot_x + (until - start) * scale,
            )
            layout.boxes.append(
                Box(
                    f"{lane['id']}-s{k + 1}", str(state["value"]), x0, y, x1 - x0, BOX_H
                )
            )
    layout.height = PAD * 2 + len(lanes) * BOX_H + max(len(lanes) - 1, 0) * gap
    return layout


def layout(spec: dict) -> tuple[Layout, str]:
    if spec["class"] in GRAPH_CLASSES:
        return _dot_layout(spec), "graphviz"
    if spec["class"] == "F5":
        return _sequence_layout(spec), "grid"
    return _timing_layout(spec), "grid"


def _svg(lay: Layout) -> str:
    root = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": f"{lay.width:g}",
            "height": f"{lay.height:g}",
            "viewBox": f"0 0 {lay.width:g} {lay.height:g}",
            "font-family": "Helvetica, Arial, sans-serif",
            "font-size": str(FONT),
        },
    )
    ET.SubElement(root, "title").text = lay.title
    defs = ET.SubElement(root, "defs")
    marker = ET.SubElement(
        defs,
        "marker",
        id="arrow",
        markerWidth="10",
        markerHeight="7",
        refX="10",
        refY="3.5",
        orient="auto",
    )
    ET.SubElement(marker, "polygon", points="0 0, 10 3.5, 0 7")
    ET.SubElement(
        root,
        "rect",
        x="0",
        y="0",
        width=f"{lay.width:g}",
        height=f"{lay.height:g}",
        fill="white",
    )
    for line in lay.lines:
        pts = " ".join(f"{x:g},{y:g}" for x, y in line.points)
        attrs = {"points": pts, "fill": "none", "stroke": "black"}
        if line.arrow:
            attrs["marker-end"] = "url(#arrow)"
        if line.dashed:
            attrs["stroke-dasharray"] = "4 4"
        g = ET.SubElement(root, "g", {"class": "line", "data-id": line.id})
        ET.SubElement(g, "polyline", attrs)
        if line.label:
            (x0, y0), (x1, y1) = line.points[0], line.points[-1]
            lx, ly = line.label_at or ((x0 + x1) / 2, (y0 + y1) / 2 - 4)
            text = ET.SubElement(
                g, "text", x=f"{lx:g}", y=f"{ly:g}", **{"text-anchor": "middle"}
            )
            text.text = line.label
    for box in lay.boxes:
        g = ET.SubElement(root, "g", id=box.id)
        ET.SubElement(
            g,
            "rect",
            x=f"{box.x:g}",
            y=f"{box.y:g}",
            width=f"{box.w:g}",
            height=f"{box.h:g}",
            fill="white",
            stroke="black",
        )
        text = ET.SubElement(
            g,
            "text",
            x=f"{box.x + box.w / 2:g}",
            y=f"{box.y + box.h / 2 + 4:g}",
            **{"text-anchor": "middle"},
        )
        text.text = box.label
    ET.indent(root)
    return ET.tostring(root, encoding="unicode") + "\n"


def _drawio(lay: Layout, name: str) -> str:
    mxfile = ET.Element("mxfile", host="azdiagram")
    diagram = ET.SubElement(mxfile, "diagram", id=name, name=lay.title or name)
    model = ET.SubElement(
        diagram,
        "mxGraphModel",
        pageWidth=f"{lay.width:g}",
        pageHeight=f"{lay.height:g}",
    )
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    for box in lay.boxes:
        cell = ET.SubElement(
            root,
            "mxCell",
            id=box.id,
            value=box.label,
            vertex="1",
            parent="1",
            style="rounded=0;whiteSpace=wrap;html=1;",
        )
        ET.SubElement(
            cell,
            "mxGeometry",
            x=f"{box.x:g}",
            y=f"{box.y:g}",
            width=f"{box.w:g}",
            height=f"{box.h:g}",
            **{"as": "geometry"},
        )
    for line in lay.lines:
        style = (
            "html=1;"
            + ("" if line.arrow else "endArrow=none;")
            + ("dashed=1;" if line.dashed else "")
        )
        attrs = {
            "id": line.id,
            "value": line.label,
            "edge": "1",
            "parent": "1",
            "style": style,
        }
        if line.source:
            attrs |= {"source": line.source, "target": line.target}
        cell = ET.SubElement(root, "mxCell", attrs)
        geometry = ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
        (x0, y0), (x1, y1) = line.points[0], line.points[-1]
        ET.SubElement(
            geometry, "mxPoint", x=f"{x0:g}", y=f"{y0:g}", **{"as": "sourcePoint"}
        )
        ET.SubElement(
            geometry, "mxPoint", x=f"{x1:g}", y=f"{y1:g}", **{"as": "targetPoint"}
        )
    ET.indent(mxfile)
    return ET.tostring(mxfile, encoding="unicode") + "\n"


def render(src: Path, out_dir: Path) -> Rendered:
    src, out_dir = Path(src), Path(out_dir)
    lay, engine = layout(load(src))
    out_dir.mkdir(parents=True, exist_ok=True)
    svg, drawio = out_dir / f"{src.stem}.svg", out_dir / f"{src.stem}.drawio"
    svg.write_text(_svg(lay))
    drawio.write_text(_drawio(lay, src.stem))
    return Rendered(svg, drawio, engine)


def _overlaps(boxes: list[Box]) -> list[str]:
    # Touching edges are not an overlap: timing segments share a border.
    return [
        f"boxes {a.id} and {b.id} overlap"
        for a, b in combinations(boxes, 2)
        if a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h
    ]


def _lint_yaml(path: Path) -> list[str]:
    spec = load(path)
    lay, _ = layout(spec)
    findings = [f"{path.name}: {f}" for f in _overlaps(lay.boxes)]
    if lay.width > spec["max_width"] or lay.height > spec["max_height"]:
        findings.append(
            f"{path.name}: figure size {lay.width:g}x{lay.height:g} exceeds limit "
            f"{spec['max_width']:g}x{spec['max_height']:g}"
        )
    return findings


def _lint_drawio(path: Path) -> list[str]:
    boxes = []
    for cell in ET.parse(path).iter("mxCell"):
        geometry = cell.find("mxGeometry")
        if cell.get("vertex") == "1" and geometry is not None:
            x, y, w, h = (
                float(geometry.get(k, 0)) for k in ("x", "y", "width", "height")
            )
            boxes.append(Box(cell.get("id", "?"), cell.get("value", ""), x, y, w, h))
    return [f"{path.name}: {f}" for f in _overlaps(boxes)]


def _is_figure_input(path: Path) -> bool:
    if path.suffix == ".drawio":
        return True
    if path.suffix not in {".yaml", ".yml"}:
        return False
    # A directory walk skips other YAML (such as spec.yaml); a named file is always linted.
    try:
        return "class" in (yaml.safe_load(path.read_text()) or {})
    except (yaml.YAMLError, TypeError):
        return True


def lint(paths) -> list[str]:
    files: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if _is_figure_input(f))
        else:
            files.append(p)
    findings = []
    for f in files:
        try:
            findings += _lint_drawio(f) if f.suffix == ".drawio" else _lint_yaml(f)
        except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
            findings.append(f"{f.name}: invalid figure input: {exc}")
    return findings
