from sqlalchemy import create_engine, inspect


def test_phase_two_migration_creates_only_approved_tables(
    migrated_test_database: str,
) -> None:
    engine = create_engine(migrated_test_database)
    business_tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
    assert business_tables == {
        "products",
        "product_revisions",
        "quality_rules",
        "inspection_tasks",
        "inspection_results",
        "inspection_issues",
        "agent_traces",
    }
    engine.dispose()
