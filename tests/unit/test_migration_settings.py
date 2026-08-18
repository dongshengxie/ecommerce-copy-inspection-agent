from db.migrations.config import database_url_from_environment


def test_migration_database_url_uses_mysql_settings_when_database_url_is_absent(
    monkeypatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MYSQL_HOST", "db.example.test")
    monkeypatch.setenv("MYSQL_PORT", "3308")
    monkeypatch.setenv("MYSQL_DATABASE", "inspection")
    monkeypatch.setenv("MYSQL_USER", "tester")
    monkeypatch.setenv("MYSQL_PASSWORD", "local-password")

    assert database_url_from_environment() == (
        "mysql+pymysql://tester:local-password@db.example.test:3308/inspection?charset=utf8mb4"
    )


def test_migration_database_url_prefers_explicit_database_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://explicit:secret@db:3306/explicit")

    assert database_url_from_environment() == "mysql+pymysql://explicit:secret@db:3306/explicit"


def test_migration_database_url_keeps_explicit_alembic_configuration(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    configured_url = "mysql+pymysql://test:test@127.0.0.1:3307/fixture_database"

    assert database_url_from_environment(configured_url) == configured_url
