"""Test that check_public.py correctly flags private markers in git repositories."""

import subprocess
import sys
from pathlib import Path


def test_check_public(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_public.py"
    assert script_path.is_file(), f"Scanner script not found at {script_path}"

    clean_file = repo_dir / "clean.txt"
    clean_file.write_text("public repository content\n", encoding="utf-8")
    subprocess.run(["git", "add", "clean.txt"], cwd=repo_dir, check=True, capture_output=True)

    # 1. Clean repository: expects 0
    res_clean = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_clean.returncode == 0
    assert res_clean.stdout == ""

    # 2. Add file with flagged pattern: expects 1 and file:line in output
    pattern = "/ho" + "me/"
    flagged_file = repo_dir / "flagged.txt"
    flagged_file.write_text(f"user path: {pattern}spectre\n", encoding="utf-8")
    subprocess.run(["git", "add", "flagged.txt"], cwd=repo_dir, check=True, capture_output=True)

    res_flagged = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_flagged.returncode == 1
    assert "flagged.txt:1" in res_flagged.stdout
    assert pattern in res_flagged.stdout


def test_check_public_flags_az_hq(tmp_path: Path) -> None:
    """DEC-GM-152 / ORC-7: check_public must flag files containing internal pattern az+hq."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_public.py"
    assert script_path.is_file(), f"Scanner script not found at {script_path}"

    pattern = "az" + "hq"
    flagged_file = repo_dir / "marker.txt"
    flagged_file.write_text(f"internal reference: {pattern} notes\n", encoding="utf-8")
    subprocess.run(["git", "add", "marker.txt"], cwd=repo_dir, check=True, capture_output=True)

    res = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 1
    assert "marker.txt:1" in res.stdout
    assert pattern in res.stdout
