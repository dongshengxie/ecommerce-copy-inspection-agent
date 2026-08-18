from __future__ import annotations

import httpx

from rag.providers import SiliconFlowEmbeddingProvider, SiliconFlowRerankerProvider


def test_siliconflow_embedding_provider_reads_1024_dimension_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/embeddings"
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.25] * 1024}], "usage": {}},
        )

    provider = SiliconFlowEmbeddingProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        base_url="https://api.siliconflow.cn/v1",
        api_key="test-key",
        model="BAAI/bge-m3",
    )

    assert provider.embed("食品 茉莉花茶") == [0.25] * 1024


def test_siliconflow_reranker_returns_scores_in_original_document_order() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/rerank"
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 1, "relevance_score": 0.9},
                    {"index": 0, "relevance_score": 0.2},
                ],
                "meta": {"tokens": {"input_tokens": 3}},
            },
        )

    provider = SiliconFlowRerankerProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        base_url="https://api.siliconflow.cn/v1",
        api_key="test-key",
        model="BAAI/bge-reranker-v2-m3",
    )

    assert provider.rerank("规则", ["第一条", "第二条"]) == [0.2, 0.9]
