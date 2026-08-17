from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings  # noqa: E402  # Supports direct script execution from project root.
from contracts.models import Rule  # noqa: E402
from db.repositories.rules import RuleRepository  # noqa: E402
from db.session import create_engine_and_session  # noqa: E402


def load_rules(path: Path) -> list[Rule]:
    """Load a UTF-8 JSON rules file into the frozen Rule Contract."""
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, list):
        raise ValueError("规则文件根节点必须是 JSON 数组")
    return [Rule.model_validate(item) for item in payload]


def import_rules_file(path: Path) -> int:
    """Validate and import rules in one database transaction."""
    session_factory = create_engine_and_session(Settings.from_environment())
    with session_factory() as session:
        imported_count = RuleRepository(session).import_rules(load_rules(path))
        session.commit()
        return imported_count


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("用法：python scripts/import_rules.py <规则 JSON 文件>")
    imported_count = import_rules_file(Path(sys.argv[1]))
    print(f"已导入 {imported_count} 条规则。")


if __name__ == "__main__":
    main()
