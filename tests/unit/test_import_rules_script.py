from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_import_rules_script_runs_directly_from_project_root() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/import_rules.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "用法：python scripts/import_rules.py" in result.stderr
