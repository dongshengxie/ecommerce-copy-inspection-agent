from __future__ import annotations

import json
from pathlib import Path

from contracts.models import Rule
from db.repositories.rules import RuleRepository

ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = ROOT / "data/rules/food_rules.json"


def _load_rules() -> list[Rule]:
    with RULES_PATH.open(encoding="utf-8") as file:
        return [Rule.model_validate(item) for item in json.load(file)]


def test_rule_import_is_idempotent_and_reads_enabled_food_rules_in_id_order(
    db_session,
) -> None:
    repository = RuleRepository(db_session)

    assert repository.import_rules(_load_rules()) == 10
    assert repository.import_rules(_load_rules()) == 0

    enabled_rules = repository.list_enabled_food_rules()
    assert [rule.rule_id for rule in enabled_rules] == sorted(
        rule.rule_id for rule in _load_rules()
    )
