from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    mysql_host: str
    mysql_port: int
    mysql_database: str
    mysql_user: str
    mysql_password: str
    mysql_test_database: str

    @classmethod
    def from_environment(cls) -> Settings:
        return cls(
            mysql_host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
            mysql_port=int(os.environ.get("MYSQL_PORT", "3307")),
            mysql_database=os.environ.get("MYSQL_DATABASE", "ecommerce_copy_inspection"),
            mysql_user=os.environ.get("MYSQL_USER", "app"),
            mysql_password=os.environ.get("MYSQL_PASSWORD", "change-me-for-local-development"),
            mysql_test_database=os.environ.get(
                "MYSQL_TEST_DATABASE", "ecommerce_copy_inspection_test"
            ),
        )

    def database_url(self, database_name: str | None = None) -> str:
        database = database_name or self.mysql_database
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{database}?charset=utf8mb4"
        )
