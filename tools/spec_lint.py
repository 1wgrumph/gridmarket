"""Lint specification section sources (AC-GM-SPEC-02, DEC-SPEC-005, DEC-SPEC-006).

A section source is YAML front matter with a ``requirements`` list, exactly one
heading, a ``**BLUF:**`` line, a ``**Frame**`` list with the six fields, prose,
and a captioned table or figure whenever the structural trigger fires.

Usage: ``python tools/spec_lint.py <section dir>``; exits 1 on any finding.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

MAX_REQUIREMENTS = 5
FRAME_FIELDS = ("Who", "What", "Why", "How", "When", "Where")
TABLE_CLASSES = {f"T{n}" for n in range(1, 9)}
FIGURE_CLASSES = {f"F{n}" for n in range(1, 9)}
SECTION_FILE = re.compile(r"^(\d+(?:\.\d+)*)-.+\.md$")
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
CAPTION = re.compile(r"^(Table|Figure) \(([A-Z]+\d+)\): (\S.*)$")
HEADING = re.compile(r"^(#{1,6}) (\S.*)$")
BULLET = re.compile(r"^[-*] (.*)$")
ORDERED = re.compile(r"^\d+\. ")
ATTRIBUTE = re.compile(r"^\s*(?:\*\*)?([A-Za-z][\w ]*?):(?:\*\*)?\s*\S")


def split_front_matter(text: str) -> tuple[dict | None, str]:
    match = FRONT_MATTER.match(text)
    if not match:
        return None, text
    data = yaml.safe_load(match.group(1))
    return (data if isinstance(data, dict) else {}), text[match.end() :]


def section_files(src_dir: Path) -> list[Path]:
    """Section sources in document order: numeric prefixes such as 04.1.2 sort naturally."""
    files = [f for f in Path(src_dir).iterdir() if SECTION_FILE.match(f.name)]
    return sorted(
        files,
        key=lambda f: tuple(int(n) for n in SECTION_FILE.match(f.name)[1].split(".")),
    )


def prose_lines(body: str) -> list[str]:
    """Body lines outside fenced code blocks; fenced lines become blank."""
    lines, fenced = [], False
    for line in body.splitlines():
        if line.startswith("```"):
            fenced = not fenced
            lines.append("")
        else:
            lines.append("" if fenced else line)
    return lines


def list_blocks(lines: list[str], pattern: re.Pattern) -> list[list[str]]:
    blocks, current = [], []
    for line in lines + [""]:
        if pattern.match(line):
            current.append(line)
        elif current:
            blocks.append(current)
            current = []
    return blocks


def _next_content(lines: list[str], index: int) -> str:
    return next((line for line in lines[index + 1 :] if line.strip()), "")


def lint_section(text: str) -> list[str]:
    findings = []
    meta, body = split_front_matter(text)
    if meta is None:
        findings.append("missing YAML front matter with a requirements list")
    else:
        requirements = meta.get("requirements")
        if not isinstance(requirements, list):
            findings.append("front matter requirements is not a list")
        elif len(requirements) > MAX_REQUIREMENTS:
            findings.append(
                f"binds {len(requirements)} requirements; at most {MAX_REQUIREMENTS} per section"
            )

    lines = prose_lines(body)
    headings = [line for line in lines if HEADING.match(line)]
    if len(headings) != 1:
        findings.append(
            f"has {len(headings)} headings; a section source has exactly one"
        )
    if not any(re.match(r"^\*\*BLUF:\*\* \S", line) for line in lines):
        findings.append("missing BLUF line (**BLUF:** ...)")
    for name in FRAME_FIELDS:
        if not any(re.match(rf"^[-*] \*\*{name}:\*\* \S", line) for line in lines):
            findings.append(f"Frame missing {name} field (- **{name}:** ...)")

    has_table = has_figure = False
    for i, line in enumerate(lines):
        match = CAPTION.match(line)
        if not match:
            continue
        kind, cls, _ = match.groups()
        valid = TABLE_CLASSES if kind == "Table" else FIGURE_CLASSES
        if cls not in valid:
            findings.append(
                f"{kind} class {cls} is outside {'T1-T8' if kind == 'Table' else 'F1-F8'}"
            )
        follow = _next_content(lines, i)
        if kind == "Table":
            has_table = True
            if not follow.startswith("|"):
                findings.append(
                    f"Table ({cls}) caption is not followed by a Markdown table"
                )
        else:
            has_figure = True
            if not follow.startswith("!["):
                findings.append(f"Figure ({cls}) caption is not followed by an image")

    bullets = list_blocks(lines, BULLET)
    if not has_table:
        for block in bullets:
            keys = [
                {
                    m[1].lower()
                    for part in re.split(r"[;,—]", item)
                    if (m := ATTRIBUTE.match(part))
                }
                for item in (BULLET.match(line)[1] for line in block)
            ]
            shared = {
                k for k in set().union(*keys) if sum(k in item for item in keys) >= 3
            }
            if len(shared) >= 2:
                findings.append(
                    "list of 3+ items sharing 2+ attributes needs a table (Table (Tn): caption)"
                )
                break
    if not has_figure:
        related = any(
            len(
                {e.strip() for line in block for e in BULLET.match(line)[1].split("->")}
            )
            >= 3
            for block in bullets
            if all("->" in line for line in block)
        )
        ordered = any(len(block) >= 3 for block in list_blocks(lines, ORDERED))
        if related or ordered:
            findings.append(
                "3+ related entities (-> list or ordered steps) need a figure "
                "(Figure (Fn): caption)"
            )
    return findings


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: spec_lint.py <section dir>", file=sys.stderr)
        return 2
    files = section_files(Path(argv[0]))
    if not files:
        print(f"{argv[0]}: no section sources (NN-*.md)")
        return 1
    failed = False
    for path in files:
        for finding in lint_section(path.read_text()):
            print(f"{path}: {finding}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
