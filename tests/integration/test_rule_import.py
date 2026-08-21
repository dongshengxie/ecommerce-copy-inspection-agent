from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from contracts.models import Rule
from db.models.core import QualityRuleModel
from db.repositories.rules import RuleRepository
from scripts import import_rules

ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = ROOT / "data/rules/food_rules.json"


def _load_rules() -> list[Rule]:
    with RULES_PATH.open(encoding="utf-8") as file:
        return [Rule.model_validate(item) for item in json.load(file)]


def test_rule_import_is_idempotent_and_reads_enabled_food_rules_in_id_order(
    db_session,
) -> None:
    repository = RuleRepository(db_session)

    assert repository.import_rules(_load_rules()) == 25
    assert repository.import_rules(_load_rules()) == 0

    enabled_rules = repository.list_enabled_food_rules()
    assert [rule.rule_id for rule in enabled_rules] == sorted(
        rule.rule_id for rule in _load_rules()
    )


def test_publish_food_baseline_retires_prior_active_versions_and_keeps_new_baseline_active(
    db_session,
) -> None:
    repository = RuleRepository(db_session)
    baseline = _load_rules()
    legacy_rule = baseline[0].model_copy(update={"version": "1.0.0"})
    repository.import_rules([legacy_rule])

    publication = repository.publish_rules(baseline)

    assert publication.imported_count == 25
    assert publication.retired_count == 1
    active_rule_versions = [
        (rule.rule_id, rule.version) for rule in repository.list_enabled_food_rules()
    ]
    assert active_rule_versions == sorted(
        (rule.rule_id, rule.version) for rule in baseline
    )
    legacy_record = db_session.scalar(
        select(QualityRuleModel).where(
            QualityRuleModel.rule_id == legacy_rule.rule_id,
            QualityRuleModel.version == legacy_rule.version,
        )
    )
    assert legacy_record is not None
    assert legacy_record.status == "disabled"
    assert legacy_record.content_json["status"] == "enabled"


def test_import_script_publishes_the_file_as_the_active_baseline(
    db_session, monkeypatch
) -> None:
    baseline = _load_rules()
    legacy_rule = baseline[0].model_copy(update={"version": "1.0.0"})
    RuleRepository(db_session).import_rules([legacy_rule])
    db_session.commit()
    session_factory = sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(
        import_rules, "create_engine_and_session", lambda _settings: session_factory
    )

    publication = import_rules.import_rules_file(RULES_PATH)

    assert publication.imported_count == 25
    assert publication.retired_count == 1
