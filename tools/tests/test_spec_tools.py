"""SEIT-GM-SPEC-02 (spec_lint) and spec_build front matter and Appendix A.

Section source format (DEC-SPEC-005, DEC-SPEC-006), as in fixtures/spec/:

- YAML front matter with a ``requirements`` list (the requirements the section
  binds), then one ``## <title>`` heading.
- ``**BLUF:** ...`` and a ``**Frame**`` list with ``**Who:**``, ``**What:**``,
  ``**Why:**``, ``**How:**``, ``**When:**``, ``**Where:**``.
- Captions ``Table (T<n>): <caption>`` before a Markdown table and
  ``Figure (F<n>): <caption>`` before an image.
- Table trigger: a bullet list of 3 or more items that share 2 or more
  ``key: value`` attributes. Figure trigger: a list naming 3 or more entities
  joined by ``->`` (relationships or state transitions), or an ordered list of
  3 or more steps (time order).

Contract exercised here:

- ``spec_lint.lint_section(text) -> list[str]`` (one finding per defect) and
  ``python tools/spec_lint.py <dir>`` (exit non-zero on any finding).
- ``spec_build.build(src_dir, out_path)`` and
  ``python tools/spec_build.py <src_dir> <out_path>``: ``spec.yaml`` (title,
  document_id, revisions) plus ``NN-*.md`` sections in file-name order.

spec_lint and spec_build have no S01 stub, so they are imported inside each
test (CMD-RED-GREEN).
"""

import importlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "spec"
CONFORMING = (FIXTURES / "conforming.md").read_text()
FRAME_FIELDS = ("Who", "What", "Why", "How", "When", "Where")

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def spec_lint():
    return importlib.import_module("spec_lint")


def spec_build():
    return importlib.import_module("spec_build")


def with_requirements(count: int) -> str:
    listed = "".join(f"  - AC-GM-TEST-{n:02d}\n" for n in range(1, count + 1))
    return re.sub(
        r"requirements:\n(?:  - .*\n)+", f"requirements:\n{listed}", CONFORMING
    )


def replace_once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, old
    return text.replace(old, new)


def run_tool(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOLS / script), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )


FIGURE_BLOCK = (
    "Figure (F1): Market context\n\n![Market context](figures/market-context.svg)\n"
)
TABLE_BLOCK = """Table (T2): Generator fleet

| Generator | Capacity | Zone |
|---|---|---|
| Solar | 100 MW | West |
| Wind | 200 MW | Panhandle |
| Gas | 300 MW | Houston |
"""
ATTRIBUTE_LIST = """- **Solar** — capacity: 100 MW; zone: West
- **Wind** — capacity: 200 MW; zone: Panhandle
- **Gas** — capacity: 300 MW; zone: Houston
"""
ARROW_LIST = """- ERCOT Worker -> Market
- Bot population -> Market
- Market -> Dashboard
"""
ORDERED_STEPS = """1. The Worker polls ERCOT.
2. The market reprices open orders.
3. The dashboard shows the new prices.
"""


def test_seit_gm_spec_02_conforming_section_passes() -> None:
    assert spec_lint().lint_section(CONFORMING) == []


def test_seit_gm_spec_02_five_requirements_pass() -> None:
    assert spec_lint().lint_section(with_requirements(5)) == []


def test_seit_gm_spec_02_six_requirements_fail() -> None:
    findings = spec_lint().lint_section(with_requirements(6))

    assert len(findings) == 1
    assert "requirement" in findings[0].lower() and "5" in findings[0]


def test_seit_gm_spec_02_missing_bluf_fails() -> None:
    text = replace_once(
        CONFORMING,
        "**BLUF:** The market matches energy orders every interval and publishes clearing prices.\n",
        "",
    )

    findings = spec_lint().lint_section(text)

    assert len(findings) == 1
    assert "BLUF" in findings[0]


@pytest.mark.parametrize("field", FRAME_FIELDS)
def test_seit_gm_spec_02_missing_frame_field_fails(field: str) -> None:
    text = re.sub(
        rf"^- \*\*{field}:\*\* .*\n", "", CONFORMING, count=1, flags=re.MULTILINE
    )
    assert text != CONFORMING

    findings = spec_lint().lint_section(text)

    assert len(findings) == 1
    assert "Frame" in findings[0] and field in findings[0]


@pytest.mark.parametrize(
    ("old", "new", "bad_class"),
    [
        ("Table (T2):", "Table (T9):", "T9"),
        ("Figure (F1):", "Figure (F9):", "F9"),
    ],
)
def test_seit_gm_spec_02_class_outside_t1_t8_f1_f8_fails(
    old: str, new: str, bad_class: str
) -> None:
    findings = spec_lint().lint_section(replace_once(CONFORMING, old, new))

    assert len(findings) == 1
    assert bad_class in findings[0]


def test_seit_gm_spec_02_attribute_list_without_table_fails() -> None:
    text = replace_once(CONFORMING, TABLE_BLOCK, ATTRIBUTE_LIST)

    findings = spec_lint().lint_section(text)

    assert len(findings) == 1
    assert "table" in findings[0].lower()


@pytest.mark.parametrize(
    "trigger", [ARROW_LIST, ORDERED_STEPS], ids=["relationship", "time-order"]
)
def test_seit_gm_spec_02_related_entities_without_figure_fail(trigger: str) -> None:
    text = replace_once(CONFORMING, FIGURE_BLOCK, "")
    text = replace_once(text, ARROW_LIST, trigger)

    findings = spec_lint().lint_section(text)

    assert len(findings) == 1
    assert "figure" in findings[0].lower()


def test_seit_gm_spec_02_cli_exit_code_follows_findings(tmp_path: Path) -> None:
    good, bad = tmp_path / "good", tmp_path / "bad"
    good.mkdir()
    bad.mkdir()
    (good / "02-market.md").write_text(CONFORMING)
    (bad / "02-market.md").write_text(with_requirements(6))

    assert spec_lint().lint_section(CONFORMING) == []
    assert run_tool("spec_lint.py", str(good)).returncode == 0
    failed = run_tool("spec_lint.py", str(bad))
    assert failed.returncode != 0
    assert "02-market.md" in failed.stdout + failed.stderr


def built(tmp_path: Path) -> str:
    src = tmp_path / "src"
    shutil.copytree(FIXTURES / "src", src)
    out = tmp_path / "Specification.md"
    spec_build().build(src, out)
    return out.read_text()


def block(text: str, heading: str) -> str:
    match = re.search(rf"^#+ {heading}\s*$", text, flags=re.MULTILINE)
    assert match, f"no {heading} heading"
    rest = text[match.end() :]
    following = re.search(r"^#+ ", rest, flags=re.MULTILINE)
    return rest[: following.start()] if following else rest


def test_seit_gm_spec_03_build_generates_front_matter_before_sections(
    tmp_path: Path,
) -> None:
    text = built(tmp_path)

    assert re.match(r"# GridMarket Fixture Specification\s*$", text.splitlines()[0])
    assert "GM-SPEC-FIXTURE" in text
    first_section = text.index("## Overview")
    for heading in (
        "Revision History",
        "Table of Contents",
        "List of Tables",
        "List of Figures",
    ):
        position = re.search(rf"^#+ {heading}", text, flags=re.MULTILINE)
        assert position and position.start() < first_section, heading

    history = block(text, "Revision History")
    assert "0.1" in history and "Initial draft" in history
    assert "0.2" in history and "Added market section" in history

    toc = block(text, "Table of Contents")
    assert toc.index("Overview") < toc.index("Market") < toc.index("Appendix A")

    tables = block(text, "List of Tables")
    assert re.search(r"Table 1\b.*Deliverables", tables)
    assert re.search(r"Table 2\b.*Generator fleet", tables)
    figures = block(text, "List of Figures")
    assert re.search(r"Figure 1\b.*Market context", figures)

    assert "requirements:" not in text, "section front matter leaked into the build"
    assert text.index("## Overview") < text.index("## Market")


def test_seit_gm_spec_03_build_generates_appendix_a_traceability(
    tmp_path: Path,
) -> None:
    text = built(tmp_path)

    appendix = re.search(r"^#+ Appendix A\b.*$", text, flags=re.MULTILINE)
    assert appendix and appendix.start() > text.index("## Market")
    rows = text[appendix.end() :].splitlines()
    for requirement, section in (
        ("AC-GM-DATA-01", "Overview"),
        ("AC-GM-MKT-01", "Market"),
        ("AC-GM-MKT-02", "Market"),
    ):
        assert any(requirement in row and section in row for row in rows), requirement


def test_seit_gm_spec_03_build_is_reproducible_through_cli(tmp_path: Path) -> None:
    spec_build()
    src = tmp_path / "src"
    shutil.copytree(FIXTURES / "src", src)
    first, second = tmp_path / "first.md", tmp_path / "second.md"

    assert run_tool("spec_build.py", str(src), str(first)).returncode == 0
    assert run_tool("spec_build.py", str(src), str(second)).returncode == 0
    assert first.read_bytes() == second.read_bytes()
    assert first.read_text() == built(tmp_path / "api")
