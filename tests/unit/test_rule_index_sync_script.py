from __future__ import annotations

from contracts.models import Rule
from scripts.sync_rules_to_es import rebuild_enabled_food_rules, sync_enabled_food_rules


def _rule() -> Rule:
    return Rule(
        rule_id="food-001",
        version="1.0.0",
        category="食品",
        field_scope=["description"],
        issue_type="claim",
        risk_level="medium",
        rule_strength="must",
        rule_text="不得宣称治疗效果",
        bad_examples=[],
        rewrite_hint="调整文案",
        status="enabled",
        effective_at="2026-01-01",
    )


class _IndexManager:
    def __init__(self) -> None:
        self.index_created = False
        self.synced_rules: list[Rule] = []

    def ensure_index(self) -> None:
        self.index_created = True

    def sync_rules(self, rules: list[Rule]) -> int:
        self.synced_rules = rules
        return len(rules)


class _RebuildIndexManager:
    def __init__(self) -> None:
        self.rebuilt_rules: list[Rule] = []

    def rebuild_rules(self, rules: list[Rule]) -> int:
        self.rebuilt_rules = rules
        return len(rules)


def test_sync_enabled_food_rules_indexes_only_rules_provided_by_the_read_boundary() -> None:
    manager = _IndexManager()

    synced_count = sync_enabled_food_rules(lambda: [_rule()], manager)

    assert synced_count == 1
    assert manager.index_created is True
    assert [rule.rule_id for rule in manager.synced_rules] == ["food-001"]


def test_rebuild_enabled_food_rules_replaces_the_derived_index_from_the_read_boundary() -> None:
    manager = _RebuildIndexManager()

    rebuilt_count = rebuild_enabled_food_rules(lambda: [_rule()], manager)

    assert rebuilt_count == 1
    assert [rule.rule_id for rule in manager.rebuilt_rules] == ["food-001"]
