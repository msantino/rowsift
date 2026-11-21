"""The release workflow refuses a tag that disagrees with the package version."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_release_tag.py"
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _run(tag: str, tmp_path: Path, version: str) -> subprocess.CompletedProcess[str]:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(f'[project]\nname = "rowsift"\nversion = "{version}"\n', encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), tag, str(pyproject)], capture_output=True, text=True
    )


def test_tag_and_version_agree(tmp_path: Path) -> None:
    assert _run("v0.2.0", tmp_path, "0.2.0").returncode == 0


def test_tag_and_version_disagree(tmp_path: Path) -> None:
    result = _run("v0.2.0", tmp_path, "0.1.0")
    assert result.returncode == 1
    assert "v0.2.0" in result.stderr


@pytest.mark.parametrize("tag", ["0.2.0", "v0.2", "release-1", "v0.2.0-rc1x", ""])
def test_a_tag_that_is_not_a_version_tag_is_refused(tag: str, tmp_path: Path) -> None:
    assert _run(tag, tmp_path, "0.2.0").returncode == 1


def test_the_workflow_runs_on_version_tags_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "tags:" in text
    assert '- "v*"' in text
    assert "branches" not in text
    assert "pull_request" not in text


def test_the_workflow_publishes_without_a_stored_credential() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "id-token: write" in text
    assert "pypa/gh-action-pypi-publish@" in text
    assert "secrets." not in text
    assert "password" not in text.lower()
    assert "check_release_tag.py" in text
