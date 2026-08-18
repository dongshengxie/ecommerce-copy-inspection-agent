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
    elasticsearch_url: str
    elasticsearch_index_prefix: str
    bge_api_base_url: str
    bge_api_key: str
    bge_embedding_model: str
    bge_reranker_model: str
    deepseek_api_key: str
    deepseek_model: str

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
            elasticsearch_url=os.environ.get("ELASTICSEARCH_URL", "http://127.0.0.1:9200"),
            elasticsearch_index_prefix=os.environ.get("ELASTICSEARCH_INDEX_PREFIX", "food_rules"),
            bge_api_base_url=os.environ.get("BGE_API_BASE_URL", ""),
            bge_api_key=os.environ.get("BGE_API_KEY", ""),
            bge_embedding_model=os.environ.get("BGE_EMBEDDING_MODEL", "BAAI/bge-m3"),
            bge_reranker_model=os.environ.get(
                "BGE_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"
            ),
            deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            deepseek_model=os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        )

    def database_url(self, database_name: str | None = None) -> str:
        database = database_name or self.mysql_database
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{database}?charset=utf8mb4"
        )
