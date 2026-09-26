---
name: spec-diagram
description: Draw a specification figure (classes F1-F8) with azdiagram from a per-class YAML input, producing SVG plus editable draw.io, and lint it. Use when a section's figure trigger fires or a figure needs changing. Do not use for tables or prose.
---

# spec-diagram

## Procedure

1. Pick the class: F1 Context, F2 Decomposition (BDD), F3 Interface (IBD),
   F4 Deployment and trust boundary, F5 Sequence, F6 Activity, F7 State
   machine, F8 Timing.
2. Write `spec/<name>/figures/<stem>.yaml`. Every input has `class`, `title`,
   `max_width`, `max_height` (pixels), and one body:
   - F1-F4, F6, F7: `nodes: [{id, label}]`, `edges: [{from, to, label}]`,
     optional `direction: TB|LR`. Laid out by Graphviz `dot`, which must be
     on PATH.
   - F5: `participants: [{id, label}]`, `messages: [{from, to, label}]` in
     time order.
   - F8: `lanes: [{id, label, states: [{at, value}]}]`.
   See `spec/template/figures/system-context.yaml`.
3. Render: `PYTHONPATH=tools uv run --project backend --frozen python -m azdiagram render spec/<name>/figures/<stem>.yaml`.
   This writes `<stem>.svg` and `<stem>.drawio` beside the input from one
   layout. Commit all three. Re-render after every YAML change; edit the
   YAML, not the outputs.
4. Reference the SVG under its caption: `Figure (Fn): <caption>` then
   `![<caption>](figures/<stem>.svg)`.

## Pass rule

`PYTHONPATH=tools uv run --project backend --frozen python -m azdiagram lint spec/<name>/`
exits 0: no two node boxes overlap and no figure exceeds its `max_width` or
`max_height`. A missing Graphviz is an error, never a pass.
