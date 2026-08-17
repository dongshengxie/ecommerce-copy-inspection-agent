from __future__ import annotations

from app.config import Settings


def test_settings_loads_phase_four_retrieval_and_model_configuration(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ELASTICSEARCH_URL", "http://127.0.0.1:9200")
    monkeypatch.setenv("ELASTICSEARCH_INDEX_PREFIX", "food_rules")
    monkeypatch.setenv("BGE_API_BASE_URL", "https://bge.example/v1")
    monkeypatch.setenv("BGE_API_KEY", "test-bge-key")
    monkeypatch.setenv("BGE_EMBEDDING_MODEL", "bge-m3")
    monkeypatch.setenv("BGE_RERANKER_MODEL", "bge-reranker-v2-m3")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")

    settings = Settings.from_environment()

    assert settings.elasticsearch_url == "http://127.0.0.1:9200"
    assert settings.elasticsearch_index_prefix == "food_rules"
    assert settings.bge_api_base_url == "https://bge.example/v1"
    assert settings.bge_api_key == "test-bge-key"
    assert settings.bge_embedding_model == "bge-m3"
    assert settings.bge_reranker_model == "bge-reranker-v2-m3"
    assert settings.deepseek_api_key == "test-deepseek-key"
    assert settings.deepseek_model == "deepseek-chat"
